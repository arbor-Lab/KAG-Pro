"""Education stage detector based on keyword analysis."""

import re
from enum import Enum


class EducationStage(Enum):
    PRIMARY = "primary"
    MIDDLE = "middle"
    HIGH = "high"
    UNIVERSITY = "university"


# Keyword signatures for each stage
STAGE_KEYWORDS = {
    EducationStage.PRIMARY: {
        "weight": 1,
        "terms": [
            "加减", "加 减", "乘除", "九九", "分数", "小数", "三角形",
            "长方形", "正方形", "周长", "面积", "时分秒", "等于多少",
        ],
    },
    EducationStage.MIDDLE: {
        "weight": 2,
        "terms": [
            "方程", "一次函数", "因式分解", "二次函数",
            "牛顿", "力学", "重力", "化学反应", "化学方程式",
            "配平", "催化剂", "置换反应", "判别式",
        ],
    },
    EducationStage.HIGH: {
        "weight": 3,
        "terms": [
            "导数", "微积分", "极限", "向量", "复数", "概率",
            "电磁", "热力学", "有机化学", "遗传", "基因",
            "极值", "单调性", "链式法则", "定积分", "洛伦兹",
            "安培力", "勒夏特列", "平衡常数", "电离平衡",
            "排列组合", "正态分布", "左手定则", "右手定则",
            "条件概率", "电容器", "电势", "化学平衡",
        ],
    },
    EducationStage.UNIVERSITY: {
        "weight": 4,
        "terms": [
            "数据结构", "算法", "复杂度", "操作系统", "编译",
            "偏导数", "矩阵", "特征值", "拉普拉斯",
            "虚拟内存", "页表", "缺页", "进程调度", "线程",
            "快速排序", "归并排序", "死锁", "二叉树", "图论",
            "微分方程", "特征向量", "行列式",
        ],
    },
}


class StageDetector:
    """Detect education stage from question text."""

    @classmethod
    def detect(cls, question: str) -> EducationStage:
        """Detect the most likely education stage for a question."""
        scores = {stage: 0 for stage in EducationStage}

        for stage, config in STAGE_KEYWORDS.items():
            for term in config["terms"]:
                if term in question:
                    scores[stage] += config["weight"]

        # Fallback: check question complexity
        total_score = sum(scores.values())
        if total_score == 0:
            # No keywords matched, guess based on text length and complexity
            if len(question) < 15:
                return EducationStage.PRIMARY
            elif len(question) < 30:
                return EducationStage.MIDDLE
            return EducationStage.HIGH

        return max(scores, key=scores.get)

    @classmethod
    def get_stage_name(cls, stage: EducationStage) -> str:
        names = {
            EducationStage.PRIMARY: "小学",
            EducationStage.MIDDLE: "初中",
            EducationStage.HIGH: "高中",
            EducationStage.UNIVERSITY: "大学",
        }
        return names[stage]
