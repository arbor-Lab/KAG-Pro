"""RAG pipeline orchestrator: load -> split -> embed -> index -> query."""

from pathlib import Path
from typing import List

from kag_pro.core.loader import Document, DocumentLoader
from kag_pro.core.splitter import ChineseTextSplitter
from kag_pro.core.vector_store import VectorStore
from kag_pro.core.retriever import Retriever
from kag_pro.core.generator import Generator


class RAGPipeline:
    """End-to-end RAG pipeline for educational Q&A."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50, persist_dir: str | None = None):
        self._splitter = ChineseTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self._vector_store = VectorStore(persist_dir=persist_dir)
        self._retriever = Retriever(vector_store=self._vector_store)
        self._generator = Generator()

    def index_documents(self, directory: str | Path) -> List[Document]:
        loader = DocumentLoader(directory)
        documents = loader.load()
        if not documents:
            return []
        chunks = self._splitter.split(documents)
        self._vector_store.add_documents(chunks)
        return chunks

    def query(self, question: str) -> dict:
        hits = self._retriever.retrieve(question)
        answer = self._generator.generate(question, hits)
        sources = [
            {
                "text": h["text"][:200] + ("..." if len(h["text"]) > 200 else ""),
                "source": h.get("metadata", {}).get("source", "unknown"),
                "score": h["score"],
            }
            for h in hits
        ]
        return {"question": question, "answer": answer, "sources": sources}

    @property
    def document_count(self) -> int:
        return self._vector_store.count()

    def clear_index(self) -> None:
        self._vector_store.clear()
