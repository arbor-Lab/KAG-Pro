"""Event-driven orchestrator — replaces the monolithic RAGPipeline.

Coordinates all pluggable modules through the PluginRegistry and EventBus,
publishing events at each stage of the query/diagnosis/recommendation flow.
"""


import json
import re
from datetime import UTC, datetime

from kag_pro.core.event_bus import EventBus, Events
from kag_pro.core.registry import PluginRegistry
from kag_pro.core.types import DiagnosisResult, QueryResult
from kag_pro.utils.config import get_config, get_project_root

_OPTION_PATTERN = re.compile(r"[A-E]\s*[.、．)]")


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
        # Retrieval-quality gate: below this best score, take the
        # clarification path instead of generating an unreliable answer.
        self._clarify_threshold = get_config()["retrieval_clarify_threshold"]
        # Semantic answer cache: similarity required to reuse a verified answer
        self._qa_cache_similarity = get_config()["qa_cache_similarity"]
        # Composite-confidence low watermark and self-consistency sample count
        self._low_conf_threshold = get_config()["confidence_low_threshold"]
        self._sc_samples = get_config()["self_consistency_samples"]
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

        # Step 3: Answer generation (retrieval-quality gate + answer cache)
        best_score = max((h.get("score", 0.0) for h in hits), default=0.0)
        clarification = bool(hits) and best_score < self._clarify_threshold
        store = None
        cached = None
        vote_info: dict = {}
        if clarification:
            bus.publish(Events.RETRIEVAL_WEAK, {
                "question": question, "best_score": best_score,
                "threshold": self._clarify_threshold,
            })
            answer = self._build_clarification(question, best_score, subject)
        else:
            store = self._registry.resolve("vector-store")
            cached = self._cache_lookup(store, question, stage)
            if cached:
                answer = cached["answer"]
                bus.publish(Events.ANSWER_CACHE_HIT, {
                    "question": question, "similarity": cached["similarity"],
                })
            else:
                gen = self._registry.resolve("generator")
                # Objective questions: self-consistency majority vote
                sc = getattr(gen, "generate_self_consistent", None)
                if self._is_objective_question(question) and callable(sc):
                    answer, vote_info = sc(
                        question, hits, enrichment=enrichment, n=self._sc_samples,
                    )
                else:
                    answer = gen.generate(question, hits, enrichment=enrichment)
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

        # Step 4: Factual verification + self-correction loop (optional)
        verification = None
        if verify and not clarification:
            if cached:
                # Cache entries were verified HIGH when stored
                verification = {
                    "faith_score": cached.get("faith_score", 1.0),
                    "verdict": "HIGH",
                    "from_cache": True,
                    "details": f"semantic cache hit (similarity {cached['similarity']:.2f})",
                }
                bus.publish(Events.ANSWER_VERIFIED, {
                    "question": question, "verification": verification,
                })
            else:
                verifier = self._registry.resolve("verifier")
                verification = verifier.verify(question, answer)
                bus.publish(Events.ANSWER_VERIFIED, {
                    "question": question, "verification": verification,
                })
                answer, verification = self._maybe_revise(
                    question, answer, hits, verification,
                )
                if vote_info:
                    verification["self_consistency"] = vote_info
                # Only verified-HIGH answers are worth caching
                self._cache_store(store, question, answer, stage, verification)

        # Step 5: Composite confidence + low-confidence sample collection
        if verification is not None:
            confidence = self._composite_confidence(best_score, verification, enrichment)
            verification["confidence"] = confidence
            verification["low_confidence"] = confidence < self._low_conf_threshold
            if verification["low_confidence"]:
                self._log_low_confidence(question, answer, stage, best_score, verification)

        return QueryResult(
            question=question,
            answer=answer,
            stage=stage,
            sources=sources,
            analysis=analysis,
            kg_enrichment=enrichment,
            verification=verification,
            clarification=clarification,
            cache_hit=cached is not None,
        )

    def _cache_lookup(self, store, question: str, stage: str) -> dict | None:
        """Semantic answer-cache lookup; never breaks the query on failure."""
        lookup = getattr(store, "cache_lookup", None)
        if not callable(lookup):
            return None
        try:
            return lookup(question, stage=stage, threshold=self._qa_cache_similarity)
        except Exception:
            return None

    @staticmethod
    def _cache_store(store, question: str, answer: str, stage: str, verification: dict) -> None:
        """Cache verified-HIGH answers; no-op when unsupported or failed."""
        save = getattr(store, "cache_store", None)
        if not callable(save) or verification.get("verdict") != "HIGH":
            return
        try:
            save(
                question, answer, stage=stage,
                faith_score=verification.get("faith_score", 1.0),
            )
        except Exception:
            pass

    def _maybe_revise(
        self, question: str, answer: str, hits: list[dict], verification: dict,
    ) -> tuple[str, dict]:
        """Self-correction loop: rewrite once when the verdict is LOW.

        Feeds unsupported claims back to the generator, re-verifies the
        revised answer, and publishes an answer.revised event.
        """
        if verification.get("verdict") != "LOW":
            return answer, verification
        unsupported = (verification.get("unsupported") or []) + (
            verification.get("contradicted") or []
        )
        if not unsupported:
            return answer, verification
        gen = self._registry.resolve("generator")
        revise = getattr(gen, "revise", None)
        if not callable(revise):
            return answer, verification
        revised = revise(question, hits, unsupported, answer)
        if not revised or not revised.strip():
            return answer, verification
        previous_faith = verification.get("faith_score")
        answer = revised.strip()
        verifier = self._registry.resolve("verifier")
        new_verification = verifier.verify(question, answer)
        new_verification["revised"] = True
        new_verification["previous_faith_score"] = previous_faith
        self._bus.publish(Events.ANSWER_REVISED, {
            "question": question,
            "previous_faith_score": previous_faith,
            "verification": new_verification,
        })
        return answer, new_verification

    @staticmethod
    def _is_objective_question(question: str) -> bool:
        """Detect choice questions by the presence of ≥2 option markers."""
        return len(_OPTION_PATTERN.findall(question)) >= 2

    @staticmethod
    def _composite_confidence(
        best_score: float, verification: dict, enrichment: dict,
    ) -> float:
        """Blend retrieval strength, factual faith and KG corroboration."""
        faith = verification.get("faith_score", 1.0)
        retrieval = min(max(best_score, 0.0), 1.0)
        kg = 1.0 if (enrichment.get("prerequisites") or enrichment.get("mistakes")) else 0.5
        return round(0.5 * faith + 0.3 * retrieval + 0.2 * kg, 3)

    def _log_low_confidence(
        self,
        question: str,
        answer: str,
        stage: str,
        best_score: float,
        verification: dict,
    ) -> None:
        """Append low-confidence samples to a JSONL sink for later evaluation."""
        try:
            path = get_project_root() / get_config()["low_confidence_log"]
            path.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "ts": datetime.now(UTC).isoformat(),
                "question": question,
                "answer": answer[:500],
                "stage": stage,
                "best_score": best_score,
                "faith_score": verification.get("faith_score"),
                "verdict": verification.get("verdict"),
                "confidence": verification.get("confidence"),
                "unsupported_claims": [
                    c.get("claim") for c in verification.get("unsupported", [])
                ],
                "contradicted_claims": [
                    c.get("claim") for c in verification.get("contradicted", [])
                ],
            }
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass  # Logging must never break the query path

    @staticmethod
    def _build_clarification(question: str, best_score: float, subject: str) -> str:
        """Deterministic clarification message for weak retrieval (no LLM)."""
        subj = "" if subject in ("", "unknown") else f"（当前识别学科：{subject}）"
        return (
            f"在当前教材库中没有找到与这个问题足够相关的内容"
            f"（最高相关度 {best_score:.2f}）{subj}。\n"
            "为了给出准确可靠的答案，请尝试：\n"
            "1. 换一种更具体的方式描述问题，例如包含关键术语或知识点名称\n"
            "2. 确认问题所属的学科和学段\n"
            "3. 补充题目背景或上下文信息\n"
            "补充信息后我会基于教材资料为你准确解答。"
        )

    # === Streaming pipeline (SSE) ===

    def query_stream(
        self, question: str, verify: bool = True, show_reasoning: bool = False,
    ):
        """Streaming version of query() — yields {"type": ..., "data": ...} dicts.

        Events (in order):
          thought (analysis) → thought (retrieval) → thought (kg_enrichment)?
          → reasoning_delta* → thought (reasoning)?
          → answer_delta* → thought (verification)?
          → meta → done
        """
        # Step 1: Stage detection
        detector = self._registry.resolve("stage-detector")
        gen = (
            self._registry.resolve("generator")
            if self._registry.has("generator") else None
        )
        analysis = detector.analyze(question, generator=gen)
        stage = self._normalize_stage(analysis.get("stage", "初中"))
        subject = analysis.get("subject", "unknown")
        yield {"type": "thought", "data": {
            "step": "analysis", "title": "问题分析",
            "description": self._build_analysis_desc(stage, subject, analysis),
            "detail": analysis.get("reason", ""),
        }}

        # Step 2: Retrieval
        enrichment, hits = self._retrieve(question, stage, subject)
        sources = self._format_sources(hits)
        src_names = [s["source"] for s in sources if s.get("source")]
        score_detail = "；".join(
            f"{s['source']}({s['score']:.2f})"
            for s in sources if s.get("source")
        )
        yield {"type": "thought", "data": {
            "step": "retrieval", "title": "知识检索",
            "description": f"检索到 {len(sources)} 条相关教材片段",
            "sources": src_names,
            "detail": score_detail,
        }}

        # Step 3: KG enrichment (optional)
        if enrichment:
            yield {"type": "thought", "data": self._build_kg_step(enrichment)}

        # Step 3.5: Retrieval-quality gate — clarify instead of hallucinating
        best_score = max((s.get("score", 0.0) for s in sources), default=0.0)
        if sources and best_score < self._clarify_threshold:
            text = self._build_clarification(question, best_score, subject)
            yield {"type": "thought", "data": {
                "step": "clarification", "title": "检索质量不足",
                "description": (
                    f"最高相关度 {best_score:.2f} 低于门控阈值 "
                    f"{self._clarify_threshold:.2f}，转入澄清而非生成不可靠答案"
                ),
            }}
            yield {"type": "answer_delta", "data": {"content": text}}
            yield {"type": "meta", "data": {
                "stage": stage,
                "sources": sources,
                "verification": None,
                "analysis": analysis,
                "kg_enrichment": enrichment,
                "answer": text,
                "clarification": True,
            }}
            yield {"type": "done", "data": {}}
            return

        # Step 4: Semantic answer cache — reuse verified answers instantly
        store = self._registry.resolve("vector-store")
        cached = self._cache_lookup(store, question, stage)
        if cached:
            verification = None
            if verify:
                verification = {
                    "faith_score": cached.get("faith_score", 1.0),
                    "verdict": "HIGH",
                    "from_cache": True,
                    "details": f"semantic cache hit (similarity {cached['similarity']:.2f})",
                }
            yield {"type": "thought", "data": {
                "step": "cache_hit", "title": "缓存命中",
                "description": (
                    f"命中已验证的历史答案（相似度 {cached['similarity']:.2f}），"
                    "跳过大模型生成"
                ),
            }}
            yield {"type": "answer_delta", "data": {"content": cached["answer"]}}
            if verification:
                yield {"type": "thought", "data": self._build_verification_step(verification)}
            yield {"type": "meta", "data": {
                "stage": stage,
                "sources": sources,
                "verification": verification,
                "analysis": analysis,
                "kg_enrichment": enrichment,
                "answer": cached["answer"],
                "clarification": False,
                "cache_hit": True,
            }}
            yield {"type": "done", "data": {}}
            return

        # Step 5: LLM reasoning (optional, pre-hoc, streaming)
        if show_reasoning and gen:
            reasoning_text = ""
            for chunk in self._stream_reasoning(gen, question, sources):
                reasoning_text += chunk
                yield {
                    "type": "reasoning_delta",
                    "data": {"content": chunk},
                }
            yield {"type": "thought", "data": {
                "step": "reasoning", "title": "推理过程",
                "description": reasoning_text,
            }}

        # Step 6: Answer generation (streaming, KG enrichment injected)
        answer = ""
        generator = self._registry.resolve("generator")
        for chunk in generator.generate_stream(question, hits, enrichment=enrichment):
            answer += chunk
            yield {"type": "answer_delta", "data": {"content": chunk}}

        # Step 7: Verification (optional)
        verification = None
        if verify:
            verifier = self._registry.resolve("verifier")
            verification = verifier.verify(question, answer)
            yield {
                "type": "thought",
                "data": self._build_verification_step(verification),
            }

            # Step 7.5: Self-correction loop on LOW verdict
            answer, verification = self._maybe_revise(
                question, answer, hits, verification,
            )
            if verification.get("revised"):
                yield {"type": "thought", "data": {
                    "step": "answer_revision", "title": "答案修正",
                    "description": (
                        f"初版可信度 {verification.get('previous_faith_score', 0):.0%} "
                        f"过低，已基于教材自动重写；修正后可信度 "
                        f"{verification.get('faith_score', 0):.0%}"
                    ),
                }}
                yield {"type": "answer_revised", "data": {
                    "content": answer, "verification": verification,
                }}

            # Composite confidence + low-confidence sample collection
            confidence = self._composite_confidence(best_score, verification, enrichment)
            verification["confidence"] = confidence
            verification["low_confidence"] = confidence < self._low_conf_threshold
            if verification["low_confidence"]:
                self._log_low_confidence(question, answer, stage, best_score, verification)

            # Cache verified-HIGH answers for future semantic hits
            self._cache_store(store, question, answer, stage, verification)

        # Final metadata
        yield {
            "type": "meta",
            "data": {
                "stage": stage,
                "sources": sources,
                "verification": verification,
                "analysis": analysis,
                "kg_enrichment": enrichment,
                "answer": answer,
                "clarification": False,
                "cache_hit": False,
            },
        }
        yield {"type": "done", "data": {}}

    # === Streaming helpers ===

    @staticmethod
    def _normalize_stage(raw_stage: str) -> str:
        """Normalize stage names to 小学/初中/高中."""
        if "小学" in raw_stage:
            return "小学"
        if "高中" in raw_stage or "大学" in raw_stage:
            return "高中"
        return "初中"

    @staticmethod
    def _build_analysis_desc(
        stage: str, subject: str, analysis: dict,
    ) -> str:
        """Build human-readable description for the analysis thought step."""
        parts = [f"学段: {stage}"]
        if subject and subject != "unknown":
            parts.append(f"学科: {subject}")
        km = analysis.get("knowledge_module", "")
        if km:
            parts.append(f"知识模块: {km}")
        return "，".join(parts)

    def _retrieve(
        self, question: str, stage: str, subject: str,
    ) -> tuple[dict, list[dict]]:
        """Run retrieval (KG-enhanced or plain vector).

        Returns (enrichment_dict, hits_list).
        """
        enrichment: dict = {}
        if self._registry.has("kg-retriever"):
            kg_ret = self._registry.resolve("kg-retriever")
            hits = kg_ret.retrieve(question)
            enrichment = kg_ret.get_enrichment(question)
        else:
            retriever = self._registry.resolve("retriever")
            stage_map = {"小学": "primary", "初中": "middle", "高中": "high"}
            stage_enum_val = stage_map.get(stage, "middle")
            hits = retriever.retrieve(
                question, stage=stage_enum_val, subject=subject,
            )
        return enrichment, hits

    @staticmethod
    def _format_sources(hits: list[dict]) -> list[dict]:
        """Format retrieval hits into output source dicts."""
        return [
            {
                "text": h["text"][:200] + ("..." if len(h["text"]) > 200 else ""),
                "source": h.get("metadata", {}).get("source", "unknown"),
                "score": h.get("score", 0),
                "vector_score": h.get("vector_score"),
                "graph_score": h.get("graph_score"),
            }
            for h in hits
        ]

    @staticmethod
    def _build_kg_step(enrichment: dict) -> dict:
        """Build thought-step dict for KG enrichment."""
        entities = enrichment.get("entities", [])
        rels = enrichment.get("relations", [])
        parts: list[str] = []
        if entities:
            parts.append(f"实体 {len(entities)} 个")
        if rels:
            parts.append(f"关系 {len(rels)} 条")
        return {
            "step": "kg_enrichment",
            "title": "图谱增强",
            "description": "，".join(parts) if parts else "知识图谱补充上下文",
            "detail": "；".join(str(e) for e in entities[:5]),
        }

    @staticmethod
    def _stream_reasoning(gen, question: str, sources: list[dict]):
        """Stream pre-hoc LLM reasoning — yields content chunks.

        Unlike the post-hoc version in server.py's _generate_reasoning(),
        this does NOT depend on the already-generated answer; it reasons
        from question + retrieved context only, enabling streaming before
        the answer is produced.
        """
        context_parts = [f"[{s['source']}] {s['text']}" for s in sources]
        context = "\n".join(context_parts) if context_parts else "无直接相关资料"
        prompt = (
            "请简要说明你将如何基于以下教材资料回答学生问题（150字以内）。\n\n"
            f"学生问题：{question}\n\n"
            f"检索到的教材资料：\n{context}\n\n"
            "请直接输出推理思路，说明从资料中提取了哪些关键信息、"
            "如何支撑回答以及关键判断依据。不要使用Markdown格式。"
        )
        yield from gen.call_stream(
            system="你是一位AI学习助教，请清晰说明你的推理过程。",
            user=prompt, temperature=0.2, max_tokens=300,
        )

    @staticmethod
    def _build_verification_step(verification: dict) -> dict:
        """Build thought-step dict for factual verification."""
        faith = verification.get("faith_score", 1.0)
        verdict = verification.get("verdict", "HIGH")
        return {
            "step": "verification",
            "title": "事实校验",
            "description": f"可信度: {faith:.0%}，判定: {verdict}",
            "detail": verification.get("details", ""),
        }

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
        allocations: list[dict] | None = None,
    ) -> dict:
        """Generate an exam paper."""
        gen = self._registry.resolve("paper-generator")
        paper = gen.generate(
            stage=stage, subject=subject, topics=topics,
            count=count, difficulty=difficulty,
            question_types=question_types,
            allocations=allocations,
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
