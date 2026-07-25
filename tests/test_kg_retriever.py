"""Tests for KGRetriever entity linking (jieba-based, no per-char fallback)."""

from unittest.mock import MagicMock

from kag_pro.kg.graph import KnowledgeGraph
from kag_pro.kg.kg_retriever import KGRetriever, _edit_distance_le1


def make_kg() -> KnowledgeGraph:
    kg = KnowledgeGraph()
    kg.add_entity("e1", "函数", "concept")
    kg.add_entity("e2", "一次函数", "concept")
    kg.add_entity("e3", "三角形全等", "concept", metadata={"aliases": ["全等三角形"]})
    kg.add_relation("e2", "prerequisite", "e1")
    return kg


def make_retriever(kg: KnowledgeGraph) -> KGRetriever:
    return KGRetriever(kg=kg, vector_store=MagicMock())


class TestEditDistanceLe1:

    def test_identical(self):
        assert _edit_distance_le1("函数", "函数") is True

    def test_single_replace(self):
        assert _edit_distance_le1("函数", "函效") is True

    def test_single_insert_or_delete(self):
        assert _edit_distance_le1("函数", "函") is True
        assert _edit_distance_le1("函数", "函好数") is True

    def test_two_edits_rejected(self):
        assert _edit_distance_le1("函数", "方程") is False
        assert _edit_distance_le1("函数", "函好多数") is False


class TestFindEntities:

    def test_exact_substring_match_longest_first(self):
        retriever = make_retriever(make_kg())
        entities = retriever._find_entities("一次函数的图像怎么画？")
        names = [e["name"] for e in entities]
        assert "一次函数" in names
        # Longest match ranks first
        assert names[0] == "一次函数"

    def test_no_single_char_false_positive(self):
        """A query sharing only one character with an entity must NOT match."""
        retriever = make_retriever(make_kg())
        # "数" is a character of "函数" but the entity name is not in the query
        assert retriever._find_entities("这个数怎么算？") == []

    def test_alias_match(self):
        retriever = make_retriever(make_kg())
        entities = retriever._find_entities("全等三角形如何判定？")
        assert any(e["name"] == "三角形全等" for e in entities)

    def test_unrelated_query_returns_empty(self):
        retriever = make_retriever(make_kg())
        assert retriever._find_entities("今天天气怎么样？") == []


class TestRetrieveFusion:

    def test_retrieve_combines_vector_and_graph_scores(self):
        kg = make_kg()
        store = MagicMock()
        store.search.return_value = [
            {"text": "一次函数 y=kx+b 的图像是一条直线。", "metadata": {"source": "f.txt"}, "score": 0.8},
            {"text": "完全无关的段落。", "metadata": {"source": "g.txt"}, "score": 0.7},
        ]
        retriever = KGRetriever(kg=kg, vector_store=store)
        hits = retriever.retrieve("一次函数的图像", top_k=2)
        assert hits[0]["metadata"]["source"] == "f.txt"
        assert "vector_score" in hits[0] and "graph_score" in hits[0]
