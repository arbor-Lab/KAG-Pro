"""Education stage detector — LLM-driven knowledge module analysis."""

from enum import Enum


class EducationStage(Enum):
    PRIMARY = "primary"
    MIDDLE = "middle"
    HIGH = "high"
    UNIVERSITY = "university"


# Lightweight keyword cache for fast-path (avoids API call)
_FAST_KEYWORDS = {
    EducationStage.PRIMARY: [
        "加减", "乘除", "九九", "分数", "小数", "三角形", "长方形", "正方形",
        "周长", "面积", "时分秒", "等于多少", "拼音", "声母", "韵母",
    ],
    EducationStage.MIDDLE: [
        "方程", "函数", "勾股", "全等三角形", "因式分解", "二次函数",
        "牛顿", "压强", "浮力", "欧姆", "电路", "化学方程式", "配平",
        "蒸发", "熔化", "凝固", "升华", "凝华", "物态", "吸热", "放热",
    ],
    EducationStage.HIGH: [
        "导数", "微积分", "极限", "复数", "极值", "链式法则", "定积分",
        "洛伦兹", "电磁感应", "勒夏特列", "平衡常数", "电离平衡",
        "排列组合", "正态分布", "左手定则", "右手定则", "光电效应",
    ],
    EducationStage.UNIVERSITY: [
        "数据结构", "算法", "复杂度", "操作系统", "虚拟内存", "页表",
        "死锁", "二叉树", "快速排序", "偏导数", "矩阵", "特征值",
    ],
}


class StageDetector:
    """LLM-driven stage detection by knowledge module analysis.

    Primary method: LLM identifies the knowledge point → maps to stage.
    Fallback: keyword fast-path for instant responses without API call.
    """

    @classmethod
    def detect(cls, question: str, use_llm: bool = True, generator=None) -> EducationStage:
        """Detect education stage for a question.

        Args:
            question: the question text
            use_llm: if True, use LLM for deep analysis (more accurate)
            generator: optional shared GeneratorPort instance
        """
        # Fast path: keyword matching for instant detection
        fast_result = cls._keyword_detect(question)
        if fast_result:
            return fast_result

        # Deep path: LLM knowledge module analysis
        if use_llm:
            return cls._llm_detect(question, generator=generator)

        return EducationStage.MIDDLE  # Safe default

    @classmethod
    def _keyword_detect(cls, question: str) -> EducationStage | None:
        """Fast keyword matching. Returns None if uncertain."""
        scores = {stage: 0 for stage in EducationStage}
        for stage, keywords in _FAST_KEYWORDS.items():
            for kw in keywords:
                if kw in question:
                    scores[stage] += 1
        if sum(scores.values()) >= 2:
            return max(scores, key=scores.get)
        return None  # Uncertain → use LLM

    @classmethod
    def _llm_detect(cls, question: str, generator=None) -> EducationStage:
        """Use LLM to identify the knowledge module and map to stage."""
        from kag_pro.core.generator import Generator
        gen = generator or Generator()

        prompt = f"""分析下面这道题目考察的知识模块，然后判断它属于哪个学段。

题目：{question[:300]}

请按以下格式回答（不要加其他内容）：
知识模块：<具体的学科知识点名称，例如"初中物理-物态变化-蒸发吸热"或"高中数学-导数-极值判定">
学段：<小学/初中/高中/大学>
原因：<一句话解释为什么是这个学段>"""

        try:
            text = gen.call(
                system="你是一位教育分析专家。", user=prompt, temperature=0, max_tokens=80
            )

            # Parse knowledge module (reserved for future use)
            _knowledge_module = ""
            if "知识模块" in text or "知识模块" in text:
                for line in text.split("\n"):
                    if "知识模块" in line or "知识模块" in line:
                        _knowledge_module = line.split("：", 1)[-1].split(":", 1)[-1].strip()
                        break

            # Parse stage
            if "大学" in text:
                return EducationStage.HIGH  # 大学内容降级为高中
            if "高中" in text:
                return EducationStage.HIGH
            if "初中" in text:
                return EducationStage.MIDDLE

            return EducationStage.PRIMARY

        except Exception:
            return EducationStage.MIDDLE

    @classmethod
    def analyze(cls, question: str, generator=None) -> dict:
        """Full analysis: return knowledge module + stage + confidence."""
        from kag_pro.core.generator import Generator
        gen = generator or Generator()

        prompt = f"""分析下面这道题目考察的知识模块，然后判断它属于哪个学段。

题目：{question[:300]}

回答格式：
知识模块：<具体知识点名称>
学段：<小学/初中/高中/大学>
学科：<数学/物理/化学/生物/语文/英语/历史/地理/计算机>
原因：<一句话>"""

        try:
            text = gen.call(
                system="你是一位教育分析专家。", user=prompt, temperature=0, max_tokens=100
            )

            result = {"knowledge_module": "", "stage": "初中", "subject": "unknown", "reason": ""}
            for line in text.split("\n"):
                line = line.strip()
                if "知识模块" in line or "知识模块" in line:
                    result["knowledge_module"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()
                elif "学段" in line:
                    s = line.split("：", 1)[-1].split(":", 1)[-1].strip()
                    result["stage"] = s
                elif "学科" in line:
                    result["subject"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()
                elif "原因" in line:
                    result["reason"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            return result
        except Exception:
            return {"knowledge_module": "", "stage": "初中", "subject": "unknown", "reason": ""}

    @classmethod
    def get_stage_name(cls, stage: EducationStage) -> str:
        names = {
            EducationStage.PRIMARY: "小学",
            EducationStage.MIDDLE: "初中",
            EducationStage.HIGH: "高中",
            EducationStage.UNIVERSITY: "大学",
        }
        return names[stage]

    # Backward compatibility
    @classmethod
    def robust_detect(cls, question: str, generator=None) -> EducationStage:
        return cls.detect(question, use_llm=True, generator=generator)
