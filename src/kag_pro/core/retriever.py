"""Retrieval strategy: hybrid vector + lexical search with fused re-ranking."""

import re

import jieba

from kag_pro.core.vector_store import VectorStore
from kag_pro.utils.config import get_config

# Tokens that carry little discriminative value for lexical matching
_STOPWORDS = {
    "的", "是", "了", "在", "和", "与", "或", "什么", "怎么", "怎样", "如何",
    "为什么", "多少", "哪些", "吗", "呢", "吧", "啊", "请", "请问", "一下",
    "我们", "你", "我", "他", "她", "它", "这", "那", "这个", "那个",
}
_ASCII_OR_DIGIT = re.compile(r"[a-zA-Z0-9]")


def _content_terms(text: str) -> list[str]:
    """Extract content-bearing terms via jieba (drops stopwords/punct)."""
    terms = []
    for tok in jieba.lcut(text):
        tok = tok.strip()
        if not tok or tok in _STOPWORDS:
            continue
        if len(tok) >= 2 or _ASCII_OR_DIGIT.search(tok):
            terms.append(tok)
    return terms


class Retriever:
    """Hybrid retrieval: over-fetch vector candidates, fuse with lexical score.

    Vector similarity captures semantics; the jieba-based lexical score
    rescues keyword/term-exact documents (formulas, proper nouns) that pure
    embedding search tends to rank too low in education corpora.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        top_k: int | None = None,
        threshold: float | None = None,
        vector_weight: float | None = None,
        candidate_multiplier: int = 4,
    ):
        config = get_config()
        self._store = vector_store
        self._top_k = top_k if top_k is not None else config["retrieval_top_k"]
        self._threshold = threshold if threshold is not None else config["retrieval_threshold"]
        self._vector_weight = (
            vector_weight if vector_weight is not None else config["retrieval_vector_weight"]
        )
        self._candidate_multiplier = candidate_multiplier

    def retrieve(self, query: str, stage: str | None = None, subject: str | None = None) -> list[dict]:
        # Step 1: over-fetch vector candidates (threshold applied after fusion)
        candidates = self._store.search(
            query=query,
            top_k=self._top_k * self._candidate_multiplier,
            threshold=0.0,
            stage_filter=stage,
            subject_filter=subject,
        )
        if not candidates:
            return []

        # Step 2: lexical re-scoring
        query_terms = _content_terms(query)
        fused: list[dict] = []
        for hit in candidates:
            lexical = self._lexical_score(query_terms, hit["text"])
            vec_score = hit["score"]
            score = self._vector_weight * vec_score + (1 - self._vector_weight) * lexical
            if score < self._threshold:
                continue
            fused.append({
                **hit,
                "vector_score": vec_score,
                "lexical_score": round(lexical, 4),
                "score": round(score, 4),
            })

        # Step 3: fused ranking, cut to top_k
        fused.sort(key=lambda h: h["score"], reverse=True)
        return fused[: self._top_k]

    @staticmethod
    def _lexical_score(query_terms: list[str], text: str) -> float:
        """Coverage-based lexical score in [0, 1]; longer terms weigh more."""
        if not query_terms:
            return 0.0
        text_terms = set(_content_terms(text))
        total = sum(len(t) for t in query_terms)
        if total == 0:
            return 0.0
        covered = sum(len(t) for t in query_terms if t in text_terms or t in text)
        return min(covered / total, 1.0)

    @property
    def top_k(self) -> int:
        return self._top_k

    @property
    def threshold(self) -> float:
        return self._threshold

    @property
    def vector_weight(self) -> float:
        return self._vector_weight
