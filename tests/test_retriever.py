"""Tests for Retriever."""

from unittest.mock import MagicMock

from kag_pro.core.retriever import Retriever


class TestRetriever:

    def test_retrieve_returns_results(self):
        store = MagicMock()
        store.search.return_value = [
            {"text": "三角形的内角和等于180度。", "metadata": {"source": "03_triangle.txt"}, "score": 0.92},
            {"text": "三角形具有稳定性。", "metadata": {"source": "03_triangle.txt"}, "score": 0.78},
        ]
        retriever = Retriever(vector_store=store, top_k=5, threshold=0.3)
        results = retriever.retrieve("三角形的内角和是多少？")
        assert len(results) == 2
        assert results[0]["score"] == 0.92
        store.search.assert_called_once_with(
            query="三角形的内角和是多少？",
            top_k=5,
            threshold=0.3,
            stage_filter=None,
            subject_filter=None,
        )

    def test_retrieve_empty_results(self):
        store = MagicMock()
        store.search.return_value = []
        retriever = Retriever(vector_store=store, top_k=5, threshold=0.3)
        results = retriever.retrieve("完全不相关的问题")
        assert results == []

    def test_retriever_properties(self):
        store = MagicMock()
        retriever = Retriever(vector_store=store, top_k=10, threshold=0.5)
        assert retriever.top_k == 10
        assert retriever.threshold == 0.5
