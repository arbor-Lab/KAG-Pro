"""Error diagnosis engine with knowledge retrieval and personalized feedback."""

from typing import Optional

from kag_pro.diagnosis.classifier import ErrorClassifier
from kag_pro.core.vector_store import VectorStore
from kag_pro.core.generator import Generator


_STAGE_PROMPTS = {
    "primary": "你是一位耐心的小学辅导老师，用简单有趣的语言、生活化的比喻来解释。",
    "middle": "你是一位有经验的初中辅导老师，善于发现学生的思维漏洞，用清晰的逻辑温和指正。",
    "high": "你是一位严谨的高中辅导老师，注重解题思路和规范步骤，帮助学生建立知识体系。",
    "university": "你是一位专业的大学助教，关注深层概念理解和严谨推导。",
}


class ErrorDiagnoser:
    """Analyze student errors and generate personalized feedback."""

    def __init__(self, vector_store: VectorStore):
        self._classifier = ErrorClassifier()
        self._store = vector_store
        self._generator = Generator()

    def diagnose(
        self,
        question: str,
        student_answer: str,
        correct_answer: str,
        stage: str = "middle",
    ) -> dict:
        """Analyze a student's wrong answer and provide personalized feedback."""
        classification = self._classifier.classify(
            question, student_answer, correct_answer
        )

        kp = classification["knowledge_point"]
        hint = classification["hint"]
        retrieved = self._store.search(query=kp, top_k=3, threshold=0.3)

        remedial_text = ""
        if retrieved:
            remedial_text = retrieved[0]["text"]

        feedback = self._generate_feedback(
            question=question,
            student_answer=student_answer,
            correct_answer=correct_answer,
            error_type=classification["error_type"],
            hint=hint,
            remedial_text=remedial_text,
            stage=stage,
        )

        return {
            "error_type": classification["error_type"],
            "confidence": classification["confidence"],
            "knowledge_point": kp,
            "hint": hint,
            "remedial_content": remedial_text[:300] + ("..." if len(remedial_text) > 300 else ""),
            "personalized_feedback": feedback,
        }

    def _generate_feedback(
        self,
        question: str,
        student_answer: str,
        correct_answer: str,
        error_type: str,
        hint: str,
        remedial_text: str,
        stage: str,
    ) -> str:
        persona = _STAGE_PROMPTS.get(stage, _STAGE_PROMPTS["middle"])

        prompt = f"""{persona}学生做错了一道题，请给出个性化学习反馈。

原题：{question}
学生的错误答案：{student_answer}
正确答案：{correct_answer}
诊断出的错误类型：{error_type}
提示：{hint}

相关知识点内容：
{remedial_text if remedial_text else "（暂无相关资料）"}

请按以下格式回复（不要用Markdown符号）：

错误分析：
（用1-2句话温和地指出学生错在哪里）

知识回顾：
（用2-3句话回顾相关的知识点，帮助学生理解正确解法）

总字数150-250字。"""
        return self._generator._client.chat.completions.create(
            model=self._generator._model,
            messages=[
                {"role": "system", "content": persona},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=400,
        ).choices[0].message.content or ""
    def generate_exercises(self, knowledge_point: str, error_type: str, count: int = 3) -> str:
        """Generate similar practice exercises for a given knowledge point.

        Args:
            knowledge_point: the knowledge point to practice
            error_type: the type of error the student made
            count: number of exercises (default 3)

        Returns:
            formatted exercise string with difficulty progression
        """
        prompt = f"""你是一位学科教师。学生在一个知识点上犯了错误，请生成{count}道同类型练习题帮助巩固。

知识点：{knowledge_point}
错误类型：{error_type}

要求：
1. 难度由低到高排列（基础 → 中等 → 提高）
2. 每道题标注难度
3. 每道题给出答案
4. 不要用Markdown符号
5. 总字数150-250字"""
        resp = self._generator._client.chat.completions.create(
            model=self._generator._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5, max_tokens=500,
        )
        return resp.choices[0].message.content or ""

