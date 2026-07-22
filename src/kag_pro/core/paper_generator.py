"""Paper generation — knowledge tree extraction and LLM-driven question generation."""

import json
import re
from collections import OrderedDict
from pathlib import Path

from kag_pro.core.generator import Generator


class KnowledgeTreeExtractor:
    def __init__(self, standards_path: str | None = None):
        if standards_path is None:
            standards_path = str(
                Path(__file__).resolve().parent.parent / "data" / "curriculum_standards.txt"
            )
        self._path = standards_path
        self._tree: dict[str, dict[str, list[str]]] = OrderedDict()
        self._parse()

    def _parse(self):
        text = Path(self._path).read_text(encoding="utf-8")
        sections = [s.strip() for s in re.split(r"=+\n", text.strip()) if s.strip()]
        stage_map = {"小学": "小学", "初中": "初中", "高中": "高中", "大学": "大学"}

        for i in range(1, len(sections), 2):
            if i + 1 >= len(sections):
                break
            header = sections[i]
            content = sections[i + 1]
            stage_name = None
            for key, label in stage_map.items():
                if key in header[:20]:
                    stage_name = label
                    break
            if stage_name is None:
                continue

            subjects: dict[str, list[str]] = OrderedDict()
            current_subject = None
            in_category = False

            for line in content.split("\n"):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue

                if stripped.startswith("[") and stripped.endswith("]"):
                    current_subject = stripped[1:-1]
                    if current_subject not in subjects:
                        subjects[current_subject] = []
                    in_category = False
                    continue

                if current_subject and (stripped.endswith(":") or stripped.endswith(":")) and ("错误" in stripped or "易错" in stripped):
                    in_category = True
                    continue

                if current_subject and in_category:
                    continue

                if current_subject and stripped:
                    subjects[current_subject].append(stripped)

            if subjects:
                if "语文" in subjects:
                    del subjects["语文"]
                self._tree[stage_name] = subjects

    def get_stages(self) -> list[str]:
        return list(self._tree.keys())

    def get_subjects(self, stage: str) -> list[str]:
        return list(self._tree.get(stage, {}).keys())

    def get_topics(self, stage: str, subject: str) -> list[str]:
        return self._tree.get(stage, {}).get(subject, [])

    def get_tree(self) -> dict:
        return dict(self._tree)


class PaperGenerator:
    def __init__(self, generator: Generator):
        self._generator = generator

    def generate(
        self,
        stage: str,
        subject: str,
        topics: list[str],
        count: int = 5,
        difficulty: str = "中等",
        question_types: list[dict] | None = None,
        allocations: list[dict] | None = None,
    ) -> dict:
        topics_str = "、".join(topics)

        alloc_detail = ""
        if allocations and len(allocations) > 0:
            by_topic = {}
            for a in allocations:
                tn = a.get("topic", 0)
                tp = a.get("type", "")
                cnt = a.get("count", 0)
                if tn not in by_topic:
                    by_topic[tn] = []
                by_topic[tn].append(f"{tp}{cnt}道" if cnt > 0 else "")
            parts = []
            for tn, types in by_topic.items():
                topic_name = topics[tn] if tn < len(topics) else f"知识点{tn+1}"
                detail = "、".join([t for t in types if t])
                if detail:
                    parts.append(f"{topic_name}：{detail}")
            alloc_detail = "\n".join(parts)

        type_instruction = ""
        if question_types and len(question_types) > 0:
            type_parts = []
            for qt in question_types:
                tname = qt.get("type", "")
                tcount = qt.get("count", 1)
                type_parts.append(f"{tname}{tcount}道")
            type_instruction = f"题型分布：{', '.join(type_parts)}。"
        else:
            type_instruction = f"题型不限，共{count}道题。"

        difficulty_instruction = ""
        if difficulty == "混合":
            difficulty_instruction = "难度分布：约40%基础、40%中等、20%提高。"
        else:
            difficulty_instruction = f"所有题目难度统一为：{difficulty}。"

        alloc_text = ""
        if alloc_detail:
            alloc_text = f"\n每题知识点分配：\n{alloc_detail}\n"

        prompt = f"""你是一位{stage}{subject}教师。请严格按以下要求生成恰好{count}道练习题，不多不少。

知识点：{topics_str}
{type_instruction}
{difficulty_instruction}{alloc_text}
请严格按照以下JSON格式输出：
{{
  "questions": [
    {{
      "id": 1,
      "type": "选择题",
      "question": "题目内容（选择题需包含ABCD四个选项）",
      "answer": "标准答案",
      "analysis": "解析",
      "difficulty": "基础/中等/提高"
    }}
  ]
}}

要求：
1. 必须恰好生成{count}道题
2. 选择题必须给出ABCD四个选项
3. 填空题答案完整，简答题答案要点清晰
4. 解析详细"""

        questions = []
        for attempt in range(3):
            text = self._generator.call(
                system=f"必须生成恰好{count}道题目。严格JSON输出。",
                user=prompt,
                temperature=0.5 + attempt * 0.1,
                max_tokens=4000,
            )
            try:
                json_match = re.search(r"\{[\s\S]*\}", text)
                data = json.loads(json_match.group()) if json_match else json.loads(text)
                questions = data.get("questions", [])
            except json.JSONDecodeError:
                questions = []
            if len(questions) >= count:
                questions = questions[:count]
                break

        if not questions:
            questions = [{"id": 1, "type": "简答题", "question": "生成失败", "answer": "", "analysis": "", "difficulty": "中等"}]

        for q in questions:
            q.setdefault("id", questions.index(q) + 1)
            q.setdefault("type", "简答题")
            q.setdefault("question", "")
            q.setdefault("answer", "")
            q.setdefault("analysis", "")
            q.setdefault("difficulty", difficulty if difficulty != "混合" else "中等")

        from datetime import datetime

        return {
            "title": f"{stage}{subject}练习卷 - {topics_str[:30]}{'...' if len(topics_str) > 30 else ''}",
            "stage": stage,
            "subject": subject,
            "topics": topics,
            "difficulty": difficulty,
            "question_types": question_types or [],
            "count": len(questions),
            "created_at": datetime.now().isoformat(),
            "questions": questions,
        }
