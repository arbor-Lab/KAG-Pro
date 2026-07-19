"""Retrieval strategy: query embedding + vector search with threshold."""

from typing import List

from kag_pro.core.vector_store import VectorStore
from kag_pro.utils.config import get_config


class Retriever:
    """Retrieve relevant document chunks from the vector store."""

    def __init__(self, vector_store: VectorStore, top_k: int | None = None, threshold: float | None = None):
        config = get_config()
        self._store = vector_store
        self._top_k = top_k if top_k is not None else config["retrieval_top_k"]
        self._threshold = threshold if threshold is not None else config["retrieval_threshold"]

    def retrieve(self, query: str) -> List[dict]:
        return self._store.search(query=query, top_k=self._top_k, threshold=self._threshold)

    @property
    def top_k(self) -> int:
        return self._top_k

    @property
    def threshold(self) -> float:
        return self._threshold
