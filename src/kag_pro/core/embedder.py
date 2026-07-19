"""Embedding generation via OpenAI API."""

import hashlib
from typing import List

from openai import OpenAI

from kag_pro.utils.config import get_config


class Embedder:
    """Generate text embeddings using OpenAI or local models."""

    def __init__(self, model: str | None = None):
        config = get_config()
        self.model = model or config["embedding_model"]
        self._client = OpenAI(
            api_key=config["openai_api_key"],
            base_url=config["openai_base_url"],
        )
        self._dimensions: int | None = None

    def embed(self, text: str) -> List[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        trimmed = [t[:8000] for t in texts]
        response = self._client.embeddings.create(model=self.model, input=trimmed)
        embeddings = [d.embedding for d in response.data]
        if self._dimensions is None and embeddings:
            self._dimensions = len(embeddings[0])
        return embeddings

    @property
    def dimensions(self) -> int | None:
        return self._dimensions

    @staticmethod
    def text_hash(text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()
