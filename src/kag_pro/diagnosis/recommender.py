"""Personalized exercise recommendation based on error history and knowledge graph."""


from kag_pro.core.generator import Generator
from kag_pro.core.vector_store import VectorStore
from kag_pro.kg.graph import KnowledgeGraph


class ExerciseRecommender:
    """Recommend practice exercises based on student error patterns and KG relationships."""

    def __init__(self, kg: KnowledgeGraph, vector_store: VectorStore, generator: Generator | None = None):
        self._kg = kg
        self._store = vector_store
        self._generator = generator or Generator()

    def recommend(self, error_history: list[dict], count: int = 3) -> dict:
        """Generate personalized exercise recommendations.

        Args:
            error_history: List of {knowledge_point, error_type, question, ...}
            count: Number of exercises to recommend

        Returns:
            dict with weak_points, exercises, learning_path
        """
        # Identify weak knowledge points
        weak_points = self._analyze_weak_points(error_history)

        # Use KG to find related prerequisite knowledge
        enriched = self._enrich_with_kg(weak_points)

        # Generate practice exercises
        exercises = self._generate_exercises(enriched, count)

        # Build learning path
        learning_path = self._build_learning_path(enriched)

        return {
            "weak_points": weak_points,
            "kg_enrichment": enriched,
            "exercises": exercises,
            "learning_path": learning_path,
        }

    def _analyze_weak_points(self, history: list[dict]) -> list[dict]:
        """Identify weak knowledge points from error history."""
        kp_counts = {}
        for item in history:
            kp = item.get("knowledge_point", "unknown")
            if kp not in kp_counts:
                kp_counts[kp] = {"count": 0, "error_types": [], "examples": []}
            kp_counts[kp]["count"] += 1
            kp_counts[kp]["error_types"].append(item.get("error_type", ""))
            kp_counts[kp]["examples"].append(item.get("question", ""))

        weak = []
        for kp, data in sorted(kp_counts.items(), key=lambda x: -x[1]["count"]):
            weak.append({
                "knowledge_point": kp,
                "error_count": data["count"],
                "error_types": list(set(data["error_types"])),
                "example_question": data["examples"][0] if data["examples"] else "",
            })
        return weak

    def _enrich_with_kg(self, weak_points: list[dict]) -> dict:
        """Use KG to find prerequisites and related knowledge for weak points."""
        enrichment = {"prerequisites": [], "related": [], "mistakes": []}

        for wp in weak_points:
            kp_name = wp["knowledge_point"]
            # Find KG entity matching this knowledge point
            for eid, entity in self._kg._entities.items():
                if kp_name in entity["name"] or entity["name"] in kp_name:
                    prereqs = self._kg.get_prerequisites(eid)
                    for p in prereqs:
                        enrichment["prerequisites"].append({"name": p["name"], "for": kp_name})
                    mistakes = self._kg.get_common_mistakes(eid)
                    for m in mistakes:
                        enrichment["mistakes"].append({"name": m["name"], "for": kp_name})
                    break

        return enrichment

    def _generate_exercises(self, enriched: dict, count: int) -> list[dict]:
        """Generate practice exercises targeting weak areas."""
        topics = []
        for wp in enriched.get("weak_points", enriched.get("weak_points", [])):
            topics.append(wp.get("knowledge_point", ""))
        for p in enriched.get("prerequisites", []):
            topics.append(p["name"])

        topics_str = "、".join(set(topics[:5]))

        prompt = f"""你是一位有经验的学科教师。学生的薄弱知识点是：{topics_str}。

请生成{count}道练习题，帮助学生巩固这些知识点。要求：
1. 每道题标注考察的知识点
2. 难度逐步递增（由易到难）
3. 针对常见错误类型设计陷阱选项或引导
4. 附带简短答案

输出格式（每道题）：
题号. (考察：知识点) 题目内容
   答案：简短答案"""

        exercises_text = self._generator.call(
            system="你是一位有经验的学科教师，善于设计针对性的练习题。",
            user=prompt,
            temperature=0.5,
            max_tokens=600,
        )
        exercises = []
        current = ""
        for line in exercises_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line[0].isdigit() and ("." in line[:3] or "、" in line[:3]):
                if current:
                    exercises.append({"content": current})
                current = line
            elif "答案" in line:
                current += " " + line
                exercises.append({"content": current})
                current = ""
            else:
                if current:
                    current += " " + line
        if current and len(exercises) < count:
            exercises.append({"content": current})
        return exercises[:count]

    def _build_learning_path(self, enriched: dict) -> list[str]:
        """Build a recommended learning path based on KG topology and weakness."""
        path = []
        seen = set()

        # Start with prerequisites (foundational knowledge)
        for p in enriched.get("prerequisites", []):
            if p["name"] not in seen:
                path.append(f"复习先修知识: {p['name']}")
                seen.add(p["name"])

        # Then tackle weak points
        for wp in enriched.get("weak_points", enriched.get("weak_points", [])):
            kp = wp.get("knowledge_point", "")
            if kp and kp not in seen:
                path.append(f"重点攻克: {kp}")
                seen.add(kp)

        # Finally review common mistakes
        for m in enriched.get("mistakes", []):
            if m["name"] not in seen:
                path.append(f"注意避免: {m['name']}")
                seen.add(m["name"])

        return path[:5]
