"""RAG pipeline orchestrator with optional KG enhancement."""

from pathlib import Path
from typing import List

from kag_pro.core.loader import Document, DocumentLoader
from kag_pro.core.splitter import ChineseTextSplitter
from kag_pro.core.vector_store import VectorStore
from kag_pro.core.retriever import Retriever
from kag_pro.core.generator import Generator


class RAGPipeline:
    """End-to-end RAG pipeline with optional knowledge graph enhancement."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50, persist_dir: str | None = None, use_kg: bool = False):
        self._splitter = ChineseTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self._vector_store = VectorStore(persist_dir=persist_dir)
        self._retriever = Retriever(vector_store=self._vector_store)
        self._generator = Generator()
        self._diagnoser = None
        self._kg_retriever = None
        if use_kg:
            self._init_kg()

    def _init_kg(self):
        from kag_pro.kg.extractor import EntityExtractor
        from kag_pro.kg.kg_retriever import KGRetriever
        kg = EntityExtractor.build_default_kg()
        self._kg_retriever = KGRetriever(kg=kg, vector_store=self._vector_store)

    def index_documents(self, directory: str | Path) -> List[Document]:
        loader = DocumentLoader(directory)
        documents = loader.load()
        if not documents:
            return []
        chunks = self._splitter.split(documents)
        self._vector_store.add_documents(chunks)
        return chunks

    def query(self, question: str) -> dict:
        from kag_pro.stage.detector import StageDetector

        # KG-enhanced or standard retrieval
        if self._kg_retriever:
            hits = self._kg_retriever.retrieve(question)
            enrichment = self._kg_retriever.get_enrichment(question)
        else:
            hits = self._retriever.retrieve(question)
            enrichment = {}

        answer = self._generator.generate(question, hits)
        stage = StageDetector.detect(question)

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
            "stage": StageDetector.get_stage_name(stage),
            "sources": sources,
        }
        if enrichment:
            result["kg_enrichment"] = enrichment
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
        return result

    @property
    def document_count(self) -> int:
        return self._vector_store.count()

    def clear_index(self) -> None:
        self._vector_store.clear()
