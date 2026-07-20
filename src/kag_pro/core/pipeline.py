"""RAG pipeline orchestrator with verification, evaluation, and recommendation."""

from pathlib import Path
from typing import List

from kag_pro.core.loader import Document, DocumentLoader
from kag_pro.core.splitter import ChineseTextSplitter
from kag_pro.core.vector_store import VectorStore
from kag_pro.core.retriever import Retriever
from kag_pro.core.generator import Generator


class RAGPipeline:
    """End-to-end RAG pipeline with KG enhancement, verification, and recommendation."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50, persist_dir: str | None = None, use_kg: bool = False):
        self._splitter = ChineseTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self._vector_store = VectorStore(persist_dir=persist_dir)
        self._retriever = Retriever(vector_store=self._vector_store)
        self._generator = Generator()
        self._diagnoser = None
        self._verifier = None
        self._recommender = None
        self._kg = None
        self._kg_retriever = None
        self._error_history: List[dict] = []
        if use_kg:
            self._init_kg()

    def _init_kg(self):
        from kag_pro.kg.extractor import EntityExtractor
        from kag_pro.kg.kg_retriever import KGRetriever
        self._kg = EntityExtractor.build_default_kg()
        self._kg_retriever = KGRetriever(kg=self._kg, vector_store=self._vector_store)

    def index_documents(self, directory: str | Path) -> List[Document]:
        loader = DocumentLoader(directory)
        documents = loader.load()
        if not documents:
            return []
        chunks = self._splitter.split(documents)
        self._vector_store.add_documents(chunks)
        return chunks

    def query(self, question: str, verify: bool = False) -> dict:
        from kag_pro.stage.detector import StageDetector

        stage_enum = StageDetector.robust_detect(question)
        stage_name = StageDetector.get_stage_name(stage_enum)

        # LLM knowledge module analysis (stage + subject)
        analysis = StageDetector.analyze(question)
        detected_subject = analysis.get("subject", "unknown")
        stage_name = analysis.get("stage", stage_name)
        if "小学" in stage_name: stage_name = "小学"
        elif "高中" in stage_name: stage_name = "高中"
        elif "大学" in stage_name: stage_name = "大学"
        else: stage_name = "初中"

        if self._kg_retriever:
            hits = self._kg_retriever.retrieve(question)
            enrichment = self._kg_retriever.get_enrichment(question)
        else:
            hits = self._retriever.retrieve(question, stage=stage_enum.value, subject=detected_subject)
            enrichment = {}

        answer = self._generator.generate(question, hits)

        # Include analysis in sources for debugging
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

        result = {
            "question": question,
            "answer": answer,
            "stage": stage_name,
            "sources": sources,
        }
        result["analysis"] = analysis
        if enrichment:
            result["kg_enrichment"] = enrichment

        # Factual consistency verification
        if verify:
            v = self._get_verifier()
            result["verification"] = v.verify(question, answer)

        return result

    def diagnose(self, question: str, student_answer: str, correct_answer: str, stage: str | None = None) -> dict:
        if self._diagnoser is None:
            from kag_pro.diagnosis.diagnoser import ErrorDiagnoser
            self._diagnoser = ErrorDiagnoser(vector_store=self._vector_store)
        from kag_pro.stage.detector import StageDetector
        if stage is None:
            detected = StageDetector.detect(question)
            stage = StageDetector.get_stage_name(detected)
        else:
            stage_map = {"primary": "小学", "middle": "初中", "high": "高中", "university": "大学"}
            stage = stage_map.get(stage, stage)
        result = self._diagnoser.diagnose(question, student_answer, correct_answer, stage=stage)
        result["stage"] = stage

        # Record error for recommendation
        self._error_history.append({
            "question": question,
            "knowledge_point": result["knowledge_point"],
            "error_type": result["error_type"],
        })

        # Get exercise recommendations
        if self._kg and len(self._error_history) >= 2:
            rec = self._get_recommender()
            result["exercises"] = rec.recommend(self._error_history, count=3)

        return result

    def evaluate(self, test_data: List[dict]) -> dict:
        """Run evaluation on a test dataset. Each item: {question, reference, sources?}"""
        from kag_pro.evaluation.metrics import RAGEvaluator
        evaluator = RAGEvaluator()
        scored_data = []
        for item in test_data:
            result = self.query(item["question"])
            scored_data.append({
                "question": item["question"],
                "generated": result["answer"],
                "reference": item.get("reference", ""),
                "sources": result.get("sources", []),
            })
        return evaluator.evaluate_batch(scored_data)

    def recommend_exercises(self, count: int = 3) -> dict:
        """Get exercise recommendations based on accumulated error history."""
        if not self._kg:
            return {"error": "KG not initialized. Use use_kg=True."}
        if not self._error_history:
            return {"error": "No error history. Run diagnose() first."}
        rec = self._get_recommender()
        return rec.recommend(self._error_history, count=count)

    @property
    def document_count(self) -> int:
        return self._vector_store.count()

    def clear_index(self) -> None:
        self._vector_store.clear()

    def _get_verifier(self):
        if self._verifier is None:
            from kag_pro.core.verifier import FactualVerifier
            self._verifier = FactualVerifier(vector_store=self._vector_store)
        return self._verifier

    def _get_recommender(self):
        if self._recommender is None:
            from kag_pro.diagnosis.recommender import ExerciseRecommender
            self._recommender = ExerciseRecommender(kg=self._kg, vector_store=self._vector_store)
        return self._recommender
