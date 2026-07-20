"""Vector store using ChromaDB for local persistence."""

from pathlib import Path
from typing import List

import chromadb
from chromadb.config import Settings

from kag_pro.core.loader import Document
from kag_pro.core.embedder import Embedder
from kag_pro.utils.config import get_config, get_project_root


class VectorStore:
    """ChromaDB-backed vector store for document embeddings."""

    COLLECTION_NAME = "kagpro_education"

    def __init__(self, persist_dir: str | None = None):
        config = get_config()
        persist_path = persist_dir or config["chroma_persist_dir"]
        if not Path(persist_path).is_absolute():
            persist_path = str(get_project_root() / persist_path)
        self._persist_dir = persist_path
        self._client = chromadb.PersistentClient(
            path=persist_path,
            settings=Settings(anonymized_telemetry=False),
        )
        self._embedder = Embedder()
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(self, documents: List[Document]) -> None:
        if not documents:
            return
        texts = [doc.text for doc in documents]
        embeddings = self._embedder.embed_batch(texts)
        ids = [self._embedder.text_hash(doc.text) for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        self._collection.upsert(
            ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas
        )

    def search(self, query: str, top_k: int = 5, threshold: float = 0.0, stage_filter: str | None = None) -> List[dict]:
        query_embedding = self._embedder.embed(query)
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        hits: List[dict] = []
        if not results["ids"] or not results["ids"][0]:
            return hits
        for i in range(len(results["ids"][0])):
            distance = results["distances"][0][i]
            similarity = 1.0 - distance
            if similarity < threshold:
                continue
            metadata = results["metadatas"][0][i]
            doc_stage = metadata.get("stage", "unknown")
            stage_boost = 1.0
            if stage_filter and stage_filter != "unknown":
                if doc_stage == stage_filter:
                    stage_boost = 1.15
                elif doc_stage != "unknown":
                    stage_boost = 0.85
            hits.append({
                "text": results["documents"][0][i],
                "metadata": metadata,
                "score": round(similarity * stage_boost, 4),
                "raw_score": round(similarity, 4),
                "stage_boost": round(stage_boost, 2),
            })
        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits

    def count(self) -> int:
        return self._collection.count()

    def clear(self) -> None:
        self._client.delete_collection(name=self.COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
