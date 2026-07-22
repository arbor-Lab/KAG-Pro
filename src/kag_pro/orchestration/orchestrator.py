"""Event-driven orchestrator — replaces the monolithic RAGPipeline.

Coordinates all pluggable modules through the PluginRegistry and EventBus,
publishing events at each stage of the query/diagnosis/recommendation flow.
"""


from kag_pro.core.event_bus import EventBus, Events
from kag_pro.core.registry import PluginRegistry
from kag_pro.core.types import DiagnosisResult, QueryResult


class EducationOrchestrator:
    """Event-driven orchestrator for the KAG-Pro education pipeline.

    Replaces RAGPipeline with a cleaner, decoupled design that uses
    the PluginRegistry for dependency resolution and the EventBus
    for inter-module communication.
    """

    def __init__(self, registry: PluginRegistry, bus: EventBus | None = None):
        self._registry = registry
        self._bus = bus or EventBus()
        self._error_history: list[dict] = []
        self._register_default_handlers()

    def _register_default_handlers(self):
        """Subscribe internal handlers to relevant events."""
        self._bus.subscribe(Events.ERROR_RECORDED, self._on_error_recorded)

    def _on_error_recorded(self, data: dict):
        """Internal handler for error.recorded events."""
        # Could trigger logging, analytics, or other side-effects
        pass

    # === Core pipeline methods ===

    def query(self, question: str, verify: bool = False) -> QueryResult:
        """Process a student question through the full RAG + KG pipeline."""
        bus = self._bus
        bus.publish(Events.QUERY_RECEIVED, {"question": question})

        # Step 1: Stage and subject detection
        detector = self._registry.resolve("stage-detector")
        generator = self._registry.resolve("generator") if self._registry.has("generator") else None
        analysis = detector.analyze(question, generator=generator)
        stage = analysis.get("stage", "初中")
        # Normalize stage names
        if "小学" in stage:
            stage = "小学"
        elif "高中" in stage:
            stage = "高中"
        elif "大学" in stage:
            stage = "高中"  # University content downgraded to high school
        else:
            stage = "初中"
        subject = analysis.get("subject", "unknown")
        bus.publish(Events.STAGE_DETECTED, {
            "question": question, "stage": stage,
            "subject": subject, "analysis": analysis,
        })

        # Step 2: Retrieval (KG-enhanced or plain vector)
        enrichment = {}
        if self._registry.has("kg-retriever"):
            kg_ret = self._registry.resolve("kg-retriever")
            hits = kg_ret.retrieve(question)
            enrichment = kg_ret.get_enrichment(question)
        else:
            retriever = self._registry.resolve("retriever")
            # Map Chinese stage names to enum values
            stage_map = {"小学": "primary", "初中": "middle", "高中": "high"}
            stage_enum_val = stage_map.get(stage, "middle")
            hits = retriever.retrieve(question, stage=stage_enum_val, subject=subject)

        if not hits:
            bus.publish(Events.RETRIEVAL_EMPTY, {"question": question})
        bus.publish(Events.RETRIEVAL_COMPLETED, {
            "question": question, "hits": hits, "enrichment": enrichment,
        })

        # Step 3: Answer generation
        gen = self._registry.resolve("generator")
        answer = gen.generate(question, hits)
        # Format sources for output
        sources = [
            {
                "text": h["text"][:200] + ("..." if len(h["text"]) > 200 else ""),
                "source": h.get("metadata", {}).get("source", "unknown"),
                "score": h.get("score", 0),
                "vector_score": h.get("vector_score"),
                "graph_score": h.get("graph_score"),
            }
            for h in hits
        ]
        bus.publish(Events.ANSWER_GENERATED, {
            "question": question, "answer": answer, "sources": sources,
        })

        # Step 4: Factual verification (optional)
        verification = None
        if verify:
            verifier = self._registry.resolve("verifier")
            verification = verifier.verify(question, answer)
            bus.publish(Events.ANSWER_VERIFIED, {
                "question": question, "verification": verification,
            })

        return QueryResult(
            question=question,
            answer=answer,
            stage=stage,
            sources=sources,
            analysis=analysis,
            kg_enrichment=enrichment,
            verification=verification,
        )

    def diagnose(
        self, question: str, student_answer: str, correct_answer: str,
        stage: str | None = None,
    ) -> DiagnosisResult:
        """Diagnose a student's error and generate personalized feedback."""
        diagnoser = self._registry.resolve("diagnoser")

        # Detect stage if not provided
        if stage is None:
            detector = self._registry.resolve("stage-detector")
            generator = self._registry.resolve("generator") if self._registry.has("generator") else None
            detected = detector.detect(question, generator=generator)
            from kag_pro.stage.detector import StageDetector
            stage = StageDetector.get_stage_name(detected)
        else:
            stage_map = {"primary": "小学", "middle": "初中", "high": "高中", "university": "大学"}
            stage = stage_map.get(stage, stage)

        # Run diagnosis (the diagnoser returns a dict, convert to DiagnosisResult)
        raw = diagnoser.diagnose(question, student_answer, correct_answer, stage=stage)

        # Handle both dict and DiagnosisResult returns
        if isinstance(raw, dict):
            result = DiagnosisResult(
                error_type=raw.get("error_type", ""),
                confidence=raw.get("confidence", 0.0),
                knowledge_point=raw.get("knowledge_point", ""),
                hint=raw.get("hint", ""),
                remedial_content=raw.get("remedial_content", ""),
                personalized_feedback=raw.get("personalized_feedback", ""),
                stage=stage,
            )
        else:
            result = raw
            result.stage = stage

        # Record error for recommendation
        self._error_history.append({
            "question": question,
            "knowledge_point": result.knowledge_point,
            "error_type": result.error_type,
        })
        self._bus.publish(Events.ERROR_RECORDED, {
            "question": question,
            "knowledge_point": result.knowledge_point,
            "error_type": result.error_type,
        })

        # Auto-recommend when enough history and KG available
        if self._registry.has("recommender") and len(self._error_history) >= 2:
            recommender = self._registry.resolve("recommender")
            result.exercises = recommender.recommend(self._error_history, count=3)

        self._bus.publish(Events.DIAGNOSIS_COMPLETED, {
            "question": question, "result": result.to_dict(),
        })
        return result

    def recommend(self, count: int = 3) -> dict:
        """Get exercise recommendations based on accumulated error history."""
        if not self._registry.has("recommender"):
            return {"error": "Recommender not available. Enable KG with use_kg=True."}
        if not self._error_history:
            return {"error": "No error history. Run diagnose() first."}
        recommender = self._registry.resolve("recommender")
        result = recommender.recommend(self._error_history, count=count)
        self._bus.publish(Events.RECOMMENDATION_READY, result)
        return result

    def exercises(self, question: str, student_answer: str, correct_answer: str) -> dict:
        """Generate practice exercises based on error classification."""
        diagnoser = self._registry.resolve("diagnoser")
        classifier = diagnoser._classifier
        c = classifier.classify(question, student_answer, correct_answer)
        return {
            "knowledge_point": c["knowledge_point"],
            "exercises": diagnoser.generate_exercises(c["knowledge_point"], c["error_type"]),
        }

    def index_documents(self, directory: str) -> int:
        """Load, split, and index documents from a directory."""
        from kag_pro.core.loader import DocumentLoader

        loader = DocumentLoader(directory)
        documents = loader.load()
        if not documents:
            return 0

        splitter = self._registry.resolve("text-splitter")
        chunks = splitter.split(documents)

        store = self._registry.resolve("vector-store")
        store.add_documents(chunks)

        self._bus.publish(Events.DOCUMENTS_INDEXED, {
            "count": len(chunks), "directory": directory,
        })
        return len(chunks)

    def generate_paper(
        self, stage: str, subject: str, topics: list[str],
        count: int = 5, difficulty: str = "中等",
        question_types: list[dict] | None = None,
    ) -> dict:
        """Generate an exam paper."""
        gen = self._registry.resolve("paper-generator")
        paper = gen.generate(
            stage=stage, subject=subject, topics=topics,
            count=count, difficulty=difficulty,
            question_types=question_types,
        )
        self._bus.publish(Events.PAPER_GENERATED, {
            "stage": stage, "subject": subject, "count": count,
        })
        return paper

    def evaluate(self, test_data: list[dict]) -> dict:
        """Run evaluation on a test dataset."""
        evaluator = self._registry.resolve("evaluator")
        scored_data = []
        for item in test_data:
            result = self.query(item["question"])
            scored_data.append({
                "question": item["question"],
                "generated": result.answer,
                "reference": item.get("reference", ""),
                "sources": result.sources,
            })
        return evaluator.evaluate_batch(scored_data)

    # === Utility properties ===

    @property
    def document_count(self) -> int:
        store = self._registry.resolve("vector-store")
        return store.count()

    @property
    def error_history(self) -> list[dict]:
        return list(self._error_history)

    def clear_index(self) -> None:
        store = self._registry.resolve("vector-store")
        store.clear()

    @property
    def bus(self) -> EventBus:
        return self._bus

    @property
    def registry(self) -> PluginRegistry:
        return self._registry
