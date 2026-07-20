"""Lightweight knowledge graph for educational knowledge points."""

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class KnowledgeGraph:
    """In-memory graph of educational entities (knowledge points) and their relations.

    Supports:
    - Entity storage with metadata
    - Relation types: prerequisite, contains, related_to, common_mistake
    - Graph traversal for knowledge retrieval
    - JSON persistence
    """

    RELATION_TYPES = ["prerequisite", "contains", "related_to", "common_mistake"]

    def __init__(self):
        self._entities: Dict[str, dict] = {}
        self._relations: List[Tuple[str, str, str]] = []
        self._adj_out: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        self._adj_in: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

    def add_entity(self, entity_id: str, name: str, entity_type: str, metadata: dict | None = None) -> None:
        self._entities[entity_id] = {
            "id": entity_id,
            "name": name,
            "type": entity_type,
            "metadata": metadata or {},
        }

    def add_relation(self, source: str, relation: str, target: str) -> None:
        if relation not in self.RELATION_TYPES:
            raise ValueError(f"Unknown relation type: {relation}")
        if source not in self._entities:
            raise ValueError(f"Source entity not found: {source}")
        if target not in self._entities:
            raise ValueError(f"Target entity not found: {target}")
        self._relations.append((source, relation, target))
        self._adj_out[source].append((target, relation))
        self._adj_in[target].append((source, relation))

    def get_entity(self, entity_id: str) -> dict | None:
        return self._entities.get(entity_id)

    def search_entities(self, query: str) -> List[dict]:
        results = []
        for eid, entity in self._entities.items():
            if query.lower() in entity["name"].lower():
                results.append(entity)
        return results

    def get_neighbors(self, entity_id: str, depth: int = 1) -> List[dict]:
        if entity_id not in self._entities:
            return []
        visited: Set[str] = {entity_id}
        frontier = [entity_id]
        neighbors: List[dict] = []
        for _ in range(depth):
            next_frontier = []
            for node in frontier:
                for neighbor, rel in self._adj_out[node]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        entity = self._entities[neighbor]
                        neighbors.append({**entity, "relation": rel, "from": node})
                        next_frontier.append(neighbor)
                for neighbor, rel in self._adj_in[node]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        entity = self._entities[neighbor]
                        neighbors.append({**entity, "relation": f"inverse_{rel}", "from": node})
                        next_frontier.append(neighbor)
            frontier = next_frontier
        return neighbors

    def get_prerequisites(self, entity_id: str) -> List[dict]:
        prereqs = []
        for source, rel in self._adj_in[entity_id]:
            if rel == "prerequisite":
                prereqs.append(self._entities[source])
        return prereqs

    def get_common_mistakes(self, entity_id: str) -> List[dict]:
        mistakes = []
        for target, rel in self._adj_out[entity_id]:
            if rel == "common_mistake":
                mistakes.append(self._entities[target])
        return mistakes

    def entity_count(self) -> int:
        return len(self._entities)

    def relation_count(self) -> int:
        return len(self._relations)

    def save(self, path: str | Path) -> None:
        data = {
            "entities": self._entities,
            "relations": [
                {"source": s, "relation": r, "target": t}
                for s, r, t in self._relations
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> "KnowledgeGraph":
        kg = cls()
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for eid, entity in data["entities"].items():
            kg._entities[eid] = entity
        for rel in data["relations"]:
            kg._relations.append((rel["source"], rel["relation"], rel["target"]))
            kg._adj_out[rel["source"]].append((rel["target"], rel["relation"]))
            kg._adj_in[rel["target"]].append((rel["source"], rel["relation"]))
        return kg
