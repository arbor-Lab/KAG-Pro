"""LLM answer generation via DeepSeek (OpenAI-compatible API)."""


import re

from openai import OpenAI

from kag_pro.utils.config import get_config

_SYSTEM_PROMPT = """\
你是一个面向中国K-12学生的AI学习助教。请根据提供的教材资料回答学生的问题。

回答规范：
1. 只基于提供的资料内容回答，不要编造资料中没有的信息
2. 用学生所在年级能理解的语言，清晰简洁
3. 如果资料不足以回答问题，明确说明"根据现有教材资料无法确认该内容"；需要补充时可以用一般知识作答，但必须标注"（此部分为一般知识，未经教材验证）"
4. 回答中适当举例子帮助理解
5. 严禁使用任何Markdown格式符号：不要用**加粗**、不要用-列表、不要用`代码块`
6. 题目解析类回答，每个选项或每个要点单独换行，使用自然的段落分隔
7. 选择题先给答案再逐一解析，解析用"A. xxx → 这是xxx现象"的格式
8. 若提供了前置知识或常见易错点信息，请在回答中自然融入易错点辨析提醒\
"""

_NO_CONTEXT_SYSTEM_PROMPT = (
    "你是一位专业的K-12学科教师。当前知识库中没有与该问题直接相关的教材资料，"
    "请基于你的专业知识认真回答，并在回答开头标注“（本回答基于一般知识，未经教材验证）”。"
    "回答要准确、清晰，适合学生的认知水平；对不确定的内容要明确说明不确定性。"
    "严禁使用Markdown符号(**加粗/-列表/`代码`)。"
    "题目解析类回答，每个要点单独换行，简洁明了。"
)


def _build_user_prompt(question: str, context_text: str, kg_info: str = "") -> str:
    """Build the user prompt, optionally injecting KG enrichment info."""
    kg_section = f"\n相关知识图谱信息：\n{kg_info}\n" if kg_info else ""
    return (
        f"参考资料：\n{context_text}\n{kg_section}"
        f"\n学生问题：{question}\n\n请根据以上参考资料回答学生的问题。"
    )


class Generator:
    """Generate answers using OpenAI LLM with retrieved context."""

    def __init__(self, model: str | None = None):
        config = get_config()
        self._model = model or config["llm_model"]
        self._client = OpenAI(
            api_key=config["openai_api_key"],
            base_url=config["openai_base_url"],
        )

    def call(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        max_tokens: int = 800,
    ) -> str:
        """Unified LLM call entry point for all modules.

        Replaces direct access to _client.chat.completions.create().
        """
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    def call_stream(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        max_tokens: int = 800,
    ):  # type: ignore[override]
        """Streaming LLM call — yields content chunks for SSE pipelines."""
        stream = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    def generate(
        self,
        question: str,
        context_chunks: list[dict],
        enrichment: dict | None = None,
    ) -> str:
        if not context_chunks:
            return self._generate_no_context(question)
        context_text = self._format_context(context_chunks)
        user_prompt = _build_user_prompt(
            question, context_text, self._format_enrichment(enrichment),
        )
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        return response.choices[0].message.content or ""

    def revise(
        self,
        question: str,
        context_chunks: list[dict],
        unsupported_claims: list[dict],
        previous_answer: str,
    ) -> str:
        """Rewrite an answer whose claims failed factual verification.

        Feeds the unsupported claims plus retrieved evidence back to the LLM
        and asks for a corrected answer (self-correction loop, one pass).
        """
        context_text = (
            self._format_context(context_chunks) if context_chunks else "（无可用教材资料）"
        )
        claims_text = "\n".join(
            f"- {c.get('claim', '')}" for c in unsupported_claims if c.get("claim")
        )
        if not claims_text:
            return ""
        user_prompt = (
            f"学生问题：{question}\n\n"
            f"以下是此前生成的回答，但其中部分论断未通过教材事实校验：\n{previous_answer}\n\n"
            f"未通过校验的论断：\n{claims_text}\n\n"
            f"可参考的教材资料：\n{context_text}\n\n"
            "请重新生成完整回答，要求：\n"
            "1. 删除或修正上述未通过校验的论断\n"
            "2. 只保留能被教材资料支持的内容；教材无法支撑的必要补充，明确标注“（此为一般知识，未经教材验证）”\n"
            "3. 保持回答完整、清晰，适合学生阅读\n"
            "4. 严禁使用Markdown符号"
        )
        return self.call(
            system="你是一位严谨的K-12学科教师，负责修订未通过事实校验的回答。",
            user=user_prompt,
            temperature=0.1,
            max_tokens=800,
        )

    def generate_self_consistent(
        self,
        question: str,
        context_chunks: list[dict],
        enrichment: dict | None = None,
        n: int = 3,
    ) -> tuple[str, dict]:
        """Self-consistency voting for objective (choice) questions.

        Samples n answers at moderate temperature, extracts the choice letter
        from each, and returns the first answer of the majority camp.
        Falls back to a single deterministic generation on any failure.
        """
        if not context_chunks or n <= 1:
            return self.generate(question, context_chunks, enrichment=enrichment), {}
        context_text = self._format_context(context_chunks)
        user_prompt = _build_user_prompt(
            question, context_text, self._format_enrichment(enrichment),
        )
        votes: dict[str, list[str]] = {}
        for _ in range(n):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                    max_tokens=600,
                )
            except Exception:
                continue
            text = response.choices[0].message.content or ""
            letter = self._extract_choice(text)
            if letter:
                votes.setdefault(letter, []).append(text)
        if not votes:
            return self.generate(question, context_chunks, enrichment=enrichment), {}
        winner = max(votes, key=lambda k: len(votes[k]))
        vote_info = {
            "votes": {k: len(v) for k, v in votes.items()},
            "winner": winner,
            "samples": n,
        }
        return votes[winner][0], vote_info

    @staticmethod
    def _extract_choice(text: str) -> str | None:
        """Extract the final choice letter (A-E) from an answer text."""
        m = re.search(r"答案\s*[:：]?\s*([A-E])", text)
        if m:
            return m.group(1)
        m = re.search(r"^\s*(?:选\s*)?([A-E])\b", text)
        return m.group(1) if m else None

    def _generate_no_context(self, question: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _NO_CONTEXT_SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            temperature=0.3,
            max_tokens=600,
        )
        return response.choices[0].message.content or ""

    def generate_stream(
        self,
        question: str,
        context_chunks: list[dict],
        enrichment: dict | None = None,
    ):
        """Stream answer generation token by token — yields content chunks."""
        if not context_chunks:
            yield from self._generate_no_context_stream(question)
            return
        context_text = self._format_context(context_chunks)
        user_prompt = _build_user_prompt(
            question, context_text, self._format_enrichment(enrichment),
        )
        stream = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=800,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    def _generate_no_context_stream(self, question: str):
        """Stream answer when no context chunks are available."""
        stream = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _NO_CONTEXT_SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            temperature=0.3,
            max_tokens=600,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    @staticmethod
    def _format_enrichment(enrichment: dict | None) -> str:
        """Format KG enrichment (prerequisites / related / mistakes) for prompts."""
        if not enrichment:
            return ""

        def _names(items: list) -> list[str]:
            names = []
            for item in items:
                name = item.get("name") if isinstance(item, dict) else str(item)
                if name and name not in names:
                    names.append(name)
            return names

        parts: list[str] = []
        prereqs = _names(enrichment.get("prerequisites", []))
        related = _names(enrichment.get("related", []))
        mistakes = _names(enrichment.get("mistakes", []))
        if prereqs:
            parts.append("前置知识：" + "、".join(prereqs))
        if related:
            parts.append("相关概念：" + "、".join(related))
        if mistakes:
            parts.append("常见易错点：" + "、".join(mistakes))
        return "\n".join(parts)

    @staticmethod
    def _format_context(chunks: list[dict]) -> str:
        parts: list[str] = []
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("metadata", {}).get("source", "未知")
            score = chunk.get("score", 0)
            parts.append(
                f"[资料{i}] (来源: {source}, 相关度: {score:.2f})\n{chunk['text']}"
            )
        return "\n\n".join(parts)
