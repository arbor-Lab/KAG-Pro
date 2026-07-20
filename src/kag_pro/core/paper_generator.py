"""Paper generation — knowledge tree extraction and LLM-driven question generation."""

import re
import json
from pathlib import Path
from typing import List, Dict, Optional
from collections import OrderedDict

from kag_pro.core.generator import Generator


class KnowledgeTreeExtractor:
    """Parse curriculum_standards.txt into a stage → subject → topics tree."""

    def __init__(self, standards_path: Optional[str] = None):
        if standards_path is None:
            standards_path = str(
                Path(__file__).resolve().parent.parent / "data" / "curriculum_standards.txt"
            )
        self._path = standards_path
        self._tree: Dict[str, Dict[str, List[str]]] = OrderedDict()
        self._parse()

    def _parse(self):
        text = Path(self._path).read_text(encoding="utf-8")

        # Split into stage sections by separator lines
        sections = re.split(r"\n?=+\n", text)
        # Filter out preamble
        stage_map = {"小学": "小学", "初中": "初中", "高中": "高中", "大学": "大学"}

        for section in sections:
            section = section.strip()
            if not section:
                continue
            # Detect stage
            stage_name = None
            for key in stage_map:
                if key in section[:20]:
                    stage_name = stage_map[key]
                    break
            if stage_name is None:
                continue

            # Parse subjects and topics within the section
            subjects: Dict[str, List[str]] = OrderedDict()
            current_subject = None

            for line in section.split("\n"):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue

                # Subject header: [数学]
                if stripped.startswith("[") and stripped.endswith("]"):
                    current_subject = stripped[1:-1]
                    if current_subject not in subjects:
                        subjects[current_subject] = []
                    continue

                # Topic line: must be indented (at least 2 spaces) under a subject
                if current_subject and line.startswith("  "):
                    topic = stripped
                    # Skip category headers (lines ending with : that have no parens)
                    if topic.endswith("：") or topic.endswith(":"):
                        continue
                    # Skip sub-headings that look like categories (no parens, not a concrete topic)
                    # Clean the topic text
                    subjects[current_subject].append(topic)

            if subjects:
                self._tree[stage_name] = subjects

    def get_stages(self) -> List[str]:
        """Return list of available stages."""
        return list(self._tree.keys())

    def get_subjects(self, stage: str) -> List[str]:
        """Return list of subjects for a given stage."""
        stage_data = self._tree.get(stage, {})
        return list(stage_data.keys())

    def get_topics(self, stage: str, subject: str) -> List[str]:
        """Return list of knowledge point topics for a stage+subject."""
        return self._tree.get(stage, {}).get(subject, [])

    def get_tree(self) -> Dict:
        """Return the full parsed tree."""
        return dict(self._tree)


class PaperGenerator:
    """Generate practice papers using LLM based on selected knowledge points."""

    def __init__(self, generator: Generator):
        self._generator = generator

    def generate(
        self,
        stage: str,
        subject: str,
        topics: List[str],
        count: int = 5,
        difficulty: str = "中等",
    ) -> Dict:
        """Generate a paper with questions, answers, and analysis.

        Args:
            stage: education stage (小学/初中/高中/大学)
            subject: subject name (数学/物理/化学/生物/语文/英语/历史/地理)
            topics: selected knowledge points
            count: number of questions (1-20)
            difficulty: 基础/中等/提高/混合

        Returns:
            dict with keys: title, stage, subject, topics, difficulty, count,
            created_at, questions (list of {id, question, answer, analysis, difficulty})
        """
        topics_str = "、".join(topics)

        difficulty_instruction = ""
        if difficulty == "混合":
            difficulty_instruction = (
                f"难度分布：共{count}题，其中约40%基础题、40%中等题、20%提高题。"
            )
        else:
            difficulty_instruction = f"所有题目难度统一为：{difficulty}。"

        prompt = f"""你是一位{stage}{subject}教师。请根据以下知识点生成{count}道练习题。

知识点：{topics_str}
难度要求：{difficulty_instruction}

请严格按照以下JSON格式输出，不要加任何其他文字：
{{
  "questions": [
    {{
      "id": 1,
      "question": "题目内容",
      "answer": "标准答案",
      "analysis": "解析（包含解题思路、关键知识点提示、易错点提醒）",
      "difficulty": "基础/中等/提高"
    }}
  ]
}}

要求：
1. 题目要有代表性，覆盖所选知识点
2. 答案要准确完整
3. 解析要详细，包含思路点拨
4. 如果难度为混合，合理分配基础/中等/提高比例"""

        resp = self._generator._client.chat.completions.create(
            model=self._generator._model,
            messages=[
                {
                    "role": "system",
                    "content": f"你是一位经验丰富的{stage}{subject}教师。你生成的题目精确、答案规范、解析详尽。请严格按照JSON格式输出。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            max_tokens=3000,
        )

        text = resp.choices[0].message.content or ""

        # Parse JSON from response
        try:
            # Extract JSON block if wrapped in code fences
            json_match = re.search(r"\{[\s\S]*\}", text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(text)
            questions = data.get("questions", [])
        except json.JSONDecodeError:
            # Fallback: return raw text as a single question
            questions = [
                {
                    "id": 1,
                    "question": text[:500],
                    "answer": "（解析失败，请重试）",
                    "analysis": "",
                    "difficulty": difficulty if difficulty != "混合" else "中等",
                }
            ]

        # Ensure each question has required fields
        for q in questions:
            q.setdefault("id", questions.index(q) + 1)
            q.setdefault("question", "")
            q.setdefault("answer", "")
            q.setdefault("analysis", "")
            q.setdefault("difficulty", difficulty if difficulty != "混合" else "中等")

        from datetime import datetime

        return {
            "title": f"{stage}{subject}练习卷 — {topics_str[:30]}{'...' if len(topics_str) > 30 else ''}",
            "stage": stage,
            "subject": subject,
            "topics": topics,
            "difficulty": difficulty,
            "count": len(questions),
            "created_at": datetime.now().isoformat(),
            "questions": questions,
        }
