"""KG-enhanced retrieval with hybrid re-ranking."""


import jieba

from kag_pro.core.vector_store import VectorStore
from kag_pro.kg.graph import KnowledgeGraph


def _edit_distance_le1(a: str, b: str) -> bool:
    """True if two strings differ by at most one edit (insert/delete/replace)."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        return sum(1 for x, y in zip(a, b) if x != y) == 1
    # Length differs by exactly one: check single insertion/deletion
    if la > lb:
        a, b = b, a
    i = j = 0
    skipped = False
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
        elif skipped:
            return False
        else:
            skipped = True
            j += 1
    return True


class KGRetriever:
    """Combines vector similarity search with knowledge graph traversal."""

    def __init__(self, kg: KnowledgeGraph, vector_store: VectorStore, alpha: float = 0.6):
        self._kg = kg
        self._store = vector_store
        self._alpha = alpha  # Weight for vector score (1-alpha for graph score)

    def retrieve(self, query: str, top_k: int = 5, threshold: float = 0.3) -> list[dict]:
        # Step 1: Vector retrieval
        vector_hits = self._store.search(query=query, top_k=top_k * 2, threshold=threshold)

        if not vector_hits:
            return []

        # Step 2: Find KG entities mentioned in query
        kg_entities = self._find_entities(query)

        # Step 3: Re-rank with KG graph score
        scored = []
        for hit in vector_hits:
            vec_score = hit["score"]
            graph_score = self._compute_graph_score(hit["text"], kg_entities)
            combined = self._alpha * vec_score + (1 - self._alpha) * graph_score
            scored.append({**hit, "vector_score": vec_score, "graph_score": graph_score, "score": round(combined, 4)})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def _find_entities(self, query: str) -> list[dict]:
        """Entity linking: exact (incl. aliases) → jieba token fuzzy match.

        Replaces the old per-character fallback, which produced false hits
        whenever any single character of an entity name appeared in the query.
        """
        all_entities = list(self._kg._entities.values())

        # Pass 1: exact substring match, longest entity names first
        matched: list[dict] = []
        for entity in sorted(all_entities, key=lambda e: len(e["name"]), reverse=True):
            names = [entity["name"], *entity.get("metadata", {}).get("aliases", [])]
            if any(name and name in query for name in names):
                matched.append(entity)
        if matched:
            return matched[:3]

        # Pass 2: jieba token match — token equals name/alias, or differs by ≤1 edit
        tokens = [t.strip() for t in jieba.lcut(query) if len(t.strip()) >= 2]
        for entity in all_entities:
            names = [entity["name"], *entity.get("metadata", {}).get("aliases", [])]
            names = [n for n in names if len(n) >= 2]
            for token in tokens:
                if any(_edit_distance_le1(token, name) for name in names):
                    matched.append(entity)
                    break
        return matched[:3]

    def _compute_graph_score(self, text: str, query_entities: list[dict]) -> float:
        if not query_entities:
            return 0.0
        score = 0.0
        text_entities = []
        for _eid, entity in self._kg._entities.items():
            if entity["name"] in text:
                text_entities.append(entity)
        if not text_entities:
            return 0.0
        for qe in query_entities:
            for te in text_entities:
                if qe["id"] == te["id"]:
                    score += 1.0
                    continue
                neighbors = self._kg.get_neighbors(qe["id"], depth=1)
                for n in neighbors:
                    if n["id"] == te["id"]:
                        score += 0.5
                        break
        return min(score / max(len(query_entities), 1), 1.0)

    def get_enrichment(self, query: str) -> dict:
        """Get KG-enriched context: prerequisites and related concepts."""
        entities = self._find_entities(query)
        enrichment = {"prerequisites": [], "related": [], "mistakes": []}
        for entity in entities:
            prereqs = self._kg.get_prerequisites(entity["id"])
            for p in prereqs:
                enrichment["prerequisites"].append({"name": p["name"], "for": entity["name"]})
            mistakes = self._kg.get_common_mistakes(entity["id"])
            for m in mistakes:
                enrichment["mistakes"].append({"name": m["name"], "for": entity["name"]})
        return enrichment
