"""Automated entity and relation extraction from educational text."""

import re
from typing import List, Tuple, Set

from kag_pro.kg.graph import KnowledgeGraph


class AutoExtractor:
    """Extract knowledge entities and relations from textbook text.

    Pipeline:
    1. Named Entity Recognition using seed vocabulary
    2. Relation Extraction using pattern matching
    3. LLM Validation for enrichment (optional)
    """

    SECTION_PATTERN = re.compile(
        r"(?:第[一二三四五六七八九十百千0-9]+[章节]|[一二三四五六七八九十]+|[0-9]+)[、.)）]?\s*(.+?)(?:\n|$)"
    )
    DEFINITION_PATTERN = re.compile(
        r"(.{2,20})(?:是|叫做|指|称为|定义为)(.{3,50})(?:[。；，\n]|$)"
    )
    PREREQUISITE_PATTERN = re.compile(
        r"(?:需要|必须先?掌握|前置知识|基于|在.*基础上).{0,10}(.{2,12})"
    )
    CONTAINS_PATTERN = re.compile(
        r"(.{2,12})(?:包括|包含|分为|主要有)(.{3,50})"
    )
    FORMULA_PATTERN = re.compile(
        r"(?:公式|定理|定律)[：:]\s*(.{3,30})"
    )

    def __init__(self, seed_vocabulary: Set[str] | None = None):
        self._vocab = seed_vocabulary or set()

    def load_seed_from_text(self, text: str) -> int:
        count = 0
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("- ") or line.startswith("  - "):
                term = line.lstrip("- ").split("(")[0].strip()
                if 2 <= len(term) <= 20:
                    self._vocab.add(term)
                    count += 1
        return count

    def extract_entities(self, text: str) -> List[Tuple[str, str, str]]:
        entities = []
        seen = set()

        for m in self.SECTION_PATTERN.finditer(text):
            name = m.group(1).strip()
            if 2 <= len(name) <= 20 and name not in seen:
                seen.add(name)
                entities.append((name, "concept", text[max(0, m.start() - 10):m.end() + 60]))

        for m in self.DEFINITION_PATTERN.finditer(text):
            name = m.group(1).strip()
            if 2 <= len(name) <= 20 and name not in seen and name in self._vocab:
                seen.add(name)
                entities.append((name, "concept", m.group(0)))

        for m in self.FORMULA_PATTERN.finditer(text):
            name = m.group(1).strip()
            if 2 <= len(name) <= 20 and name not in seen:
                seen.add(name)
                entities.append((name, "law", m.group(0)))

        for term in self._vocab:
            if term in text and term not in seen and len(term) >= 2:
                idx = text.find(term)
                snippet = text[max(0, idx - 5):idx + len(term) + 50]
                seen.add(term)
                entities.append((term, "concept", snippet))

        return entities[:30]

    def extract_relations(self, text: str, entities: List[str]) -> List[Tuple[str, str, str]]:
        relations = []
        entity_set = set(entities)

        for m in self.PREREQUISITE_PATTERN.finditer(text):
            target = m.group(1).strip()
            before = text[:m.start()]
            for entity in sorted(entity_set, key=lambda e: -len(e)):
                idx = before.rfind(entity)
                if idx >= 0 and target in entity_set:
                    relations.append((entity, "prerequisite", target))
                    break

        for m in self.CONTAINS_PATTERN.finditer(text):
            container = m.group(1).strip()
            contained_str = m.group(2).strip()
            if container in entity_set:
                for part in re.split(r"[、，,]", contained_str):
                    part = part.strip().split("(")[0].strip()
                    if part in entity_set and part != container:
                        relations.append((container, "contains", part))

        return relations[:20]

    def build_kg_from_texts(self, texts: List[str]) -> KnowledgeGraph:
        kg = KnowledgeGraph()
        all_entity_names = set()
        entity_id_map = {}

        for i, text in enumerate(texts):
            extracted = self.extract_entities(text)
            for name, etype, snippet in extracted:
                eid = f"auto_{len(entity_id_map):03d}"
                kg.add_entity(eid, name, etype, metadata={"snippet": snippet[:100], "source_idx": i})
                entity_id_map[name] = eid
                all_entity_names.add(name)

        for i, text in enumerate(texts):
            extracted = self.extract_relations(text, list(all_entity_names))
            for source, rel, target in extracted:
                if source in entity_id_map and target in entity_id_map:
                    try:
                        kg.add_relation(entity_id_map[source], rel, entity_id_map[target])
                    except ValueError:
                        pass

        return kg


class LLMEntityEnricher:
    """Use LLM to validate and enrich extracted entities and relations."""

    def __init__(self, generator=None):
        from kag_pro.core.generator import Generator
        self._gen = generator or Generator()

    def suggest_relations(self, entity_name: str, context: str) -> dict:
        prompt = f"""你是一位教育知识图谱专家。给定知识点：

知识点：{entity_name}
上下文：{context[:200]}

列出前置知识(最多2个)、包含子知识点(最多2个)、关联知识(最多2个)、常见错误(最多1个)。
输出格式：前置: xxx / 包含: xxx / 关联: xxx / 易错: xxx"""
        response = self._gen._client.chat.completions.create(
            model=self._gen._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=300,
        )
        text = response.choices[0].message.content or ""
        suggestions = {"prerequisite": [], "contains": [], "related_to": [], "common_mistake": []}
        for line in text.split("\n"):
            line = line.strip()
            if "前置" in line:
                suggestions["prerequisite"].append(line.split(":", 1)[-1].split("：", 1)[-1].strip().lstrip("/ "))
            elif "包含" in line:
                suggestions["contains"].append(line.split(":", 1)[-1].split("：", 1)[-1].strip().lstrip("/ "))
            elif "关联" in line:
                suggestions["related_to"].append(line.split(":", 1)[-1].split("：", 1)[-1].strip().lstrip("/ "))
            elif "易错" in line:
                suggestions["common_mistake"].append(line.split(":", 1)[-1].split("：", 1)[-1].strip().lstrip("/ "))
        return suggestions
