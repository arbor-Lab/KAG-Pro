"""LLM answer generation via DeepSeek (OpenAI-compatible API)."""


from openai import OpenAI

from kag_pro.utils.config import get_config

_SYSTEM_PROMPT = """\
你是一个面向中国K-12学生的AI学习助教。请根据提供的教材资料回答学生的问题。

回答规范：
1. 只基于提供的资料内容回答，不要编造资料中没有的信息
2. 用学生所在年级能理解的语言，清晰简洁
3. 如果资料不足以回答问题，用自己的知识直接作答，不要说"无法回答"
4. 回答中适当举例子帮助理解
5. 严禁使用任何Markdown格式符号：不要用**加粗**、不要用-列表、不要用`代码块`
6. 题目解析类回答，每个选项或每个要点单独换行，使用自然的段落分隔
7. 选择题先给答案再逐一解析，解析用"A. xxx → 这是xxx现象"的格式\
"""

_USER_PROMPT_TEMPLATE = """\
参考资料：
{context}

学生问题：{question}

请根据以上参考资料回答学生的问题。\
"""


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

    def generate(self, question: str, context_chunks: list[dict]) -> str:
        if not context_chunks:
            return self._generate_no_context(question)
        context_text = self._format_context(context_chunks)
        user_prompt = _USER_PROMPT_TEMPLATE.format(context=context_text, question=question)
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

    def _generate_no_context(self, question: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一位专业的K-12学科教师。即使知识库中没有直接相关的资料，"
                        "你也必须用自己的专业知识认真回答学生的每一个问题。"
                        "回答要准确、清晰，适合学生的认知水平。"
                        "如果是不确定的内容，请说明'根据一般知识'来提醒学生。"
                        "永远不要说'我无法回答'或'资料中没有'。"
                        "严禁使用Markdown符号(**加粗/-列表/`代码`)。"
                        "题目解析类回答，每个要点单独换行，简洁明了。"
                    ),
                },
                {"role": "user", "content": question},
            ],
            temperature=0.3,
            max_tokens=600,
        )
        return response.choices[0].message.content or ""

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
