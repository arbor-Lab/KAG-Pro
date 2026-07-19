"""LLM answer generation using OpenAI GPT-4o."""

from typing import List

from openai import OpenAI

from kag_pro.utils.config import get_config


_SYSTEM_PROMPT = """\
你是一个面向中国小学生的AI学习助教。请根据提供的教材资料回答学生的问题。

要求：
1. 只基于提供的资料内容回答，不要编造资料中没有的信息
2. 用小学生能理解的语言，清晰简洁
3. 如果资料不足以回答问题，请诚实说明
4. 回答中适当举例子帮助理解\
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

    def generate(self, question: str, context_chunks: List[dict]) -> str:
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
                        "你是一个面向中国小学生的AI学习助教。"
                        "目前知识库中没有找到相关资料，请如实告知学生，"
                        "并尝试用你自己的知识简单回答。"
                    ),
                },
                {"role": "user", "content": question},
            ],
            temperature=0.3,
            max_tokens=400,
        )
        return response.choices[0].message.content or ""

    @staticmethod
    def _format_context(chunks: List[dict]) -> str:
        parts: List[str] = []
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("metadata", {}).get("source", "未知")
            score = chunk.get("score", 0)
            parts.append(
                f"[资料{i}] (来源: {source}, 相关度: {score:.2f})\n{chunk['text']}"
            )
        return "\n\n".join(parts)
