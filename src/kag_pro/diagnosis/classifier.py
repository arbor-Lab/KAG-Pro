"""Error type classifier for student answers across K-12 stages."""

import re


class ErrorClassifier:
    """Classify student error types and map them to knowledge points."""

    ERROR_PATTERNS = {
        "missing_root": {
            "keywords": ["x²", "x^2", "二次方程", "平方"],
            "patterns": [],
            "knowledge_point": "一元二次方程求根",
            "hint": "一元二次方程通常有两个根，开平方时注意正负号都要考虑。",
        },
        "discriminant_error": {
            "keywords": ["判别式", "Δ", "delta", "b²-4ac"],
            "patterns": [],
            "knowledge_point": "判别式Δ=b²-4ac",
            "hint": "先计算判别式Δ=b²-4ac：Δ>0两个实根，Δ=0一个重根，Δ<0无实根。",
        },
        "sign_error": {
            "keywords": ["移项", "变号", "去括号变号"],
            "patterns": [],
            "knowledge_point": "代数运算符号规则",
            "hint": "移项时要变号（加变减、减变加），括号前有负号时去括号每一项都要变号。",
        },
        "calculation_error": {
            "keywords": ["计算", "等于多少", "得数", "+", "-", "×", "÷"],
            "patterns": [],
            "knowledge_point": "四则运算与代数计算",
            "hint": "请检查计算步骤：先乘除后加减，有括号先算括号内，注意移项变号。",
        },
        "formula_misapplication": {
            "keywords": ["a=F/m", "求加速度", "F=ma", "求根公式", "顶点公式", "S=", "C="],
            "patterns": [],
            "knowledge_point": "公式应用",
            "hint": "请确认公式中每个符号的含义，特别注意正负号和分母。",
        },
        "incomplete_factorization": {
            "keywords": ["因式分解", "分解", "提取公因式"],
            "patterns": [],
            "knowledge_point": "因式分解",
            "hint": "因式分解要分解到不能再分为止，检查是否有公因式未提取或可用公式未用。",
        },
        "distribution_error": {
            "keywords": ["分配律", "括号", "乘法分配", "去括号"],
            "patterns": [],
            "knowledge_point": "乘法分配律",
            "hint": "a×(b+c)=a×b+a×c，括号外的数要分别乘以括号内的每一项。",
        },
        "force_mass_confusion": {
            "keywords": ["重力是多少", "重量", "G=mg", "地球引力"],
            "patterns": [],
            "knowledge_point": "质量与重力的区别",
            "hint": "质量(kg)和重力(N)是不同的物理量。G=mg，g≈10N/kg。",
        },
        "equation_not_balanced": {
            "keywords": ["化学方程式", "配平", "反应", "→"],
            "patterns": [],
            "knowledge_point": "化学方程式配平",
            "hint": "配平化学方程式时先数反应前后各原子个数，通过调整系数使两边相等。不能改化学式只能改系数。",
        },
        "reaction_type_error": {
            "keywords": ["化合", "分解", "置换", "复分解", "反应类型"],
            "patterns": [],
            "knowledge_point": "化学反应类型判断",
            "hint": "化合:A+B→AB，分解:AB→A+B，置换:单质+化合物→新单质+新化合物，复分解:两种化合物交换成分。",
        },
        "circuit_analysis_error": {
            "keywords": ["串联", "并联", "电路", "短路", "电流", "电压"],
            "patterns": [],
            "knowledge_point": "电路分析",
            "hint": "串联电路电流处处相等，并联电路电压相等。先判断串并联关系再计算。",
        },
        "force_analysis_error": {
            "keywords": ["受力", "摩擦力", "重力", "弹力", "支持力"],
            "patterns": [],
            "knowledge_point": "受力分析",
            "hint": "受力分析按顺序：重力→弹力→摩擦力→其他力。不遗漏、不多画。",
        },
        "chemical_formula_error": {
            "keywords": ["化学式", "化合价", "分子式", "元素符号"],
            "patterns": [],
            "knowledge_point": "化学式书写与化合价",
            "hint": "书写化学式：正价在前负价在后，化合价代数和为零。注意大小写和角标。",
        },
        "equilibrium_error": {
            "keywords": ["平衡移动", "勒夏特列", "催化剂", "平衡"],
            "patterns": [],
            "knowledge_point": "化学平衡移动",
            "hint": "催化剂只改变速率不改变平衡位置。压强只影响有气体且分子数变化的反应。",
        },
        "trigonometric_error": {
            "keywords": ["sin", "cos", "tan", "三角函数", "诱导公式"],
            "patterns": [],
            "knowledge_point": "三角函数运算",
            "hint": "注意诱导公式中的符号变化：奇变偶不变，符号看象限。",
        },
                "concept_confusion": {
            "keywords": ["定义", "概念", "区别", "是什么"],
            "patterns": [],
            "knowledge_point": "基础概念",
            "hint": "请回顾相关定义，区分相似概念的关键差异。",
        },
        "missing_condition": {
            "keywords": ["条件", "当", "若", "已知", "设"],
            "patterns": [],
            "knowledge_point": "解题条件分析",
            "hint": "解题前先明确已知条件和隐含条件，特别是一元二次方程中a≠0的限制。",
        },
    }

    @classmethod
    def classify(
        cls,
        question: str,
        student_answer: str,
        correct_answer: str,
    ) -> dict:
        """Classify the error type and return diagnostic info."""
        best_match = None
        best_score = 0

        # Quadratic equation context detection
        is_quadratic = bool(re.search(r"x[²^2]|二次方程|平方", question))

        for error_type, config in cls.ERROR_PATTERNS.items():
            score = 0

            for kw in config["keywords"]:
                if kw in question or kw in student_answer:
                    score += 1

            # missing_root only applies to quadratic equations
            if error_type == "missing_root" and not is_quadratic:
                score = 0

            if len(student_answer) < len(correct_answer) * 0.5:
                if error_type == "missing_root":
                    score += 2
                elif error_type == "missing_condition":
                    score += 1

            if score > best_score:
                best_score = score
                best_match = error_type

        if best_match is None or best_score == 0:
            best_match = "concept_confusion"

        config = cls.ERROR_PATTERNS[best_match]
        confidence = min(best_score / 5.0, 1.0)

        return {
            "error_type": best_match,
            "confidence": round(confidence, 2),
            "knowledge_point": config["knowledge_point"],
            "hint": config["hint"],
            "description": f"{config['hint'][:30]}...",
        }
