"""Vector store using ChromaDB for local persistence."""

from pathlib import Path

import chromadb
from chromadb.config import Settings

from kag_pro.core.embedder import Embedder
from kag_pro.core.types import Document
from kag_pro.utils.config import get_config, get_project_root


class VectorStore:
    """ChromaDB-backed vector store for document embeddings."""

    COLLECTION_NAME = "kagpro_education"
    QA_COLLECTION_NAME = "kagpro_qa_cache"
    IMAGE_COLLECTION_NAME = "kagpro_images"

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
        # Semantic answer cache: verified Q→A pairs, hit by query similarity
        self._qa_collection = self._client.get_or_create_collection(
            name=self.QA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        # Image embeddings collection
        self._image_collection = self._client.get_or_create_collection(
            name=self.IMAGE_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(self, documents: list[Document]) -> None:
        if not documents:
            return
        texts = [doc.text for doc in documents]
        embeddings = self._embedder.embed_batch(texts)
        ids = [f"{self._embedder.text_hash(doc.text)}_{i}" for i, doc in enumerate(documents)]
        metadatas = [doc.metadata for doc in documents]
        self._collection.upsert(
            ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas
        )

    def search(self, query: str, top_k: int = 5, threshold: float = 0.0, stage_filter: str | None = None, subject_filter: str | None = None) -> list[dict]:
        query_embedding = self._embedder.embed(query)
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        hits: list[dict] = []
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
            doc_subject = metadata.get("subject", "unknown")
            subject_boost = 1.0
            if stage_filter and stage_filter != "unknown":
                if doc_stage == stage_filter:
                    stage_boost = 1.15
                elif doc_stage != "unknown":
                    stage_boost = 0.85
            if subject_filter and subject_filter != "unknown":
                if doc_subject == subject_filter:
                    subject_boost = 1.2
                elif doc_subject != "unknown":
                    subject_boost = 0.75
            hits.append({
                "text": results["documents"][0][i],
                "metadata": metadata,
                "score": round(similarity * stage_boost * subject_boost, 4),
                "subject_boost": round(subject_boost, 2),
                "raw_score": round(similarity, 4),
                "stage_boost": round(stage_boost, 2),
            })
        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits

    def count(self) -> int:
        return self._collection.count()

    def cache_lookup(
        self, query: str, stage: str = "", threshold: float = 0.95,
    ) -> dict | None:
        """Semantic answer-cache lookup. Returns cached entry or None.

        A hit requires similarity >= threshold AND matching stage (when the
        cached entry carries stage metadata).
        """
        if self._qa_collection.count() == 0:
            return None
        query_embedding = self._embedder.embed(query)
        results = self._qa_collection.query(
            query_embeddings=[query_embedding],
            n_results=1,
            include=["documents", "metadatas", "distances"],
        )
        if not results["ids"] or not results["ids"][0]:
            return None
        similarity = 1.0 - results["distances"][0][0]
        if similarity < threshold:
            return None
        metadata = results["metadatas"][0][0] or {}
        cached_stage = metadata.get("stage", "")
        if stage and cached_stage and cached_stage != stage:
            return None
        return {
            "answer": results["documents"][0][0],
            "similarity": round(similarity, 4),
            "faith_score": metadata.get("faith_score", 1.0),
            "stage": cached_stage,
        }

    def cache_store(
        self, query: str, answer: str, stage: str = "", faith_score: float = 1.0,
    ) -> None:
        """Store a verified Q→A pair in the semantic answer cache."""
        if not query or not answer:
            return
        embedding = self._embedder.embed(query)
        self._qa_collection.upsert(
            ids=[f"qa_{self._embedder.text_hash(query)}"],
            embeddings=[embedding],
            documents=[answer],
            metadatas=[{"stage": stage, "faith_score": float(faith_score)}],
        )

    def clear(self) -> None:
        self._client.delete_collection(name=self.COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        # Wipe the answer cache as well — it may reference deleted content
        self._client.delete_collection(name=self.QA_COLLECTION_NAME)
        self._qa_collection = self._client.get_or_create_collection(
            name=self.QA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        # Also clear image collection
        self._client.delete_collection(name=self.IMAGE_COLLECTION_NAME)
        self._image_collection = self._client.get_or_create_collection(
            name=self.IMAGE_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def get_image_collection(self):
        """获取图像向量集合。"""
        return self._image_collection

    def add_images(self, image_data: list[dict]) -> None:
        """
        批量添加图像到向量数据库。

        Args:
            image_data: 图像数据列表，每个元素包含：
                - image_path: 图像文件路径
                - embeddings: 图像向量（list[float]）
                - metadata: 元数据（可选）
                - description: 图像描述文本（可选）
        """
        if not image_data:
            return

        paths = [item["image_path"] for item in image_data]
        embeddings = [item["embeddings"] for item in image_data]
        metadatas = [item.get("metadata", {"type": "image"}) for item in image_data]

        # Ensure all have type field
        for meta in metadatas:
            if "type" not in meta:
                meta["type"] = "image"

        self._image_collection.upsert(
            ids=[Path(p).stem for p in paths],
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def search_images(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        threshold: float = 0.3,
    ) -> list[dict]:
        """
        根据查询向量搜索相似图像。

        Args:
            query_embedding: 查询向量（来自图像或文本嵌入器）
            top_k: 返回结果数量
            threshold: 相似度阈值

        Returns:
            搜索结果列表
        """
        results = self._image_collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        hits = []
        if not results["ids"] or not results["ids"][0]:
            return hits

        for i in range(len(results["ids"][0])):
            distance = results["distances"][0][i]
            similarity = 1.0 - distance
            if similarity < threshold:
                continue

            metadata = results["metadatas"][0][i] if results["metadatas"][0] else {}

            hits.append({
                "id": results["ids"][0][i],
                "image_path": metadata.get("image_path", ""),
                "description": metadata.get("description", ""),
                "score": round(similarity, 4),
                "distance": round(distance, 4),
                "metadata": metadata,
            })

        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits
