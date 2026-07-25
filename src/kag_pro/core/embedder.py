"""Embedding generation via local BGE model or OpenAI-compatible API."""

import hashlib
from collections import OrderedDict

from kag_pro.utils.config import get_config


class Embedder:
    """Generate text embeddings using local BGE model (default) or remote API."""

    _local_model = None

    def __init__(self, model: str | None = None):
        config = get_config()
        self.model = model or config["embedding_model"]
        self._use_local = self.model.startswith("BAAI/") or self.model.startswith("bge-")

        if self._use_local:
            self._init_local()
        else:
            from openai import OpenAI
            api_key = config["embedding_api_key"] or config["openai_api_key"]
            base_url = config["embedding_base_url"] or config["openai_base_url"]
            self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._dimensions: int | None = None
        # Instance-level bounded LRU for single-text embeddings
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._cache_maxsize = 1024

    @classmethod
    def _init_local(cls):
        if cls._local_model is None:
            from sentence_transformers import SentenceTransformer
            config = get_config()
            model_name = config["embedding_model"]
            cls._local_model = SentenceTransformer(model_name, local_files_only=True)
            cls._local_model_name = model_name

    def embed(self, text: str) -> list[float]:
        key = text[:8000]
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return list(cached)
        embedding = self.embed_batch([text])[0]
        self._cache[key] = embedding
        if len(self._cache) > self._cache_maxsize:
            self._cache.popitem(last=False)
        return list(embedding)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        trimmed = [t[:8000] for t in texts]

        if self._use_local:
            embeddings = self._local_model.encode(
                trimmed, normalize_embeddings=True, show_progress_bar=False
            ).tolist()
        else:
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

    def clear_cache(self) -> None:
        self._cache.clear()
