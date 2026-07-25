"""Tests for Retriever (hybrid vector + lexical fusion)."""

from unittest.mock import MagicMock

from kag_pro.core.retriever import Retriever


class TestRetriever:

    def test_retrieve_overfetches_and_fuses(self):
        store = MagicMock()
        store.search.return_value = [
            {"text": "三角形的内角和等于180度。", "metadata": {"source": "03_triangle.txt"}, "score": 0.92},
            {"text": "三角形具有稳定性。", "metadata": {"source": "03_triangle.txt"}, "score": 0.78},
        ]
        retriever = Retriever(vector_store=store, top_k=5, threshold=0.3)
        results = retriever.retrieve("三角形的内角和是多少？")
        assert len(results) == 2
        # Over-fetch: candidates pulled with multiplier and threshold=0.0
        store.search.assert_called_once_with(
            query="三角形的内角和是多少？",
            top_k=20,
            threshold=0.0,
            stage_filter=None,
            subject_filter=None,
        )
        # Fused score = 0.7 * vector + 0.3 * lexical; both fields attached
        assert results[0]["vector_score"] == 0.92
        assert results[0]["lexical_score"] == 1.0
        assert results[0]["score"] > results[0]["vector_score"]
        assert results[1]["lexical_score"] < results[0]["lexical_score"]

    def test_lexical_match_promotes_keyword_exact_doc(self):
        """A keyword-exact doc can outrank a semantically closer but off-topic one."""
        store = MagicMock()
        store.search.return_value = [
            {"text": "平行线的同位角相等。", "metadata": {"source": "a.txt"}, "score": 0.62},
            {"text": "勾股定理：直角三角形两直角边的平方和等于斜边的平方。", "metadata": {"source": "b.txt"}, "score": 0.55},
        ]
        retriever = Retriever(vector_store=store, top_k=5, threshold=0.3)
        results = retriever.retrieve("勾股定理是什么？")
        assert results[0]["metadata"]["source"] == "b.txt"
        assert results[0]["lexical_score"] == 1.0

    def test_threshold_applied_to_fused_score(self):
        store = MagicMock()
        store.search.return_value = [
            {"text": "完全无关的内容。", "metadata": {"source": "a.txt"}, "score": 0.32},
        ]
        retriever = Retriever(vector_store=store, top_k=5, threshold=0.3)
        # 0.7*0.32 + 0.3*0.0 = 0.224 < 0.3 → filtered out
        assert retriever.retrieve("勾股定理是什么？") == []

    def test_retrieve_empty_results(self):
        store = MagicMock()
        store.search.return_value = []
        retriever = Retriever(vector_store=store, top_k=5, threshold=0.3)
        results = retriever.retrieve("完全不相关的问题")
        assert results == []

    def test_retriever_properties(self):
        store = MagicMock()
        retriever = Retriever(vector_store=store, top_k=10, threshold=0.5, vector_weight=0.8)
        assert retriever.top_k == 10
        assert retriever.threshold == 0.5
        assert retriever.vector_weight == 0.8
