"""ExerciseRecommender JSON 结构化生成回归测试。"""

from kag_pro.diagnosis.recommender import ExerciseRecommender


class _FakeKG:
    _entities: dict = {}

    def get_prerequisites(self, eid):
        return []

    def get_common_mistakes(self, eid):
        return []


class _FakeStore:
    pass


class _FakeGenerator:
    def __init__(self, reply: str):
        self._reply = reply
        self.calls: list[dict] = []
        self.model = "fake"

    def call(self, system, user, temperature=0.3, max_tokens=800):
        self.calls.append({"user": user, "max_tokens": max_tokens})
        return self._reply


def _make_recommender(reply: str) -> ExerciseRecommender:
    return ExerciseRecommender(_FakeKG(), _FakeStore(), generator=_FakeGenerator(reply))


def test_generate_exercises_json_parsed():
    """JSON 输出被解析为结构化练习题，content 保持兼容拼接格式。"""
    reply = (
        '{"exercises":['
        '{"knowledge_point":"分数加减法","question":"计算 $\\\\frac{1}{2}+\\\\frac{1}{3}$",'
        '"answer":"$\\\\frac{5}{6}$"},'
        '{"knowledge_point":"分数乘除法","question":"计算 2×3","answer":"6"}'
        "]}"
    )
    rec = _make_recommender(reply)
    result = rec.recommend(
        [{"knowledge_point": "分数加减法", "error_type": "概念不清", "question": "q1"}], count=2
    )
    exercises = result["exercises"]
    assert len(exercises) == 2
    assert exercises[0]["knowledge_point"] == "分数加减法"
    assert "(考察：分数加减法)" in exercises[0]["content"]
    assert "答案：" in exercises[0]["content"]
    assert "\\frac{1}{2}" in exercises[0]["question"]


def test_generate_exercises_invalid_json_degrades_gracefully():
    """模型返回非 JSON 时静默降级为空列表，不阻塞诊断主流程。"""
    rec = _make_recommender("1. 第一题\n2. 第二题（纯文本，非JSON）")
    result = rec.recommend(
        [{"knowledge_point": "拼音", "error_type": "记忆模糊", "question": "q1"}], count=2
    )
    assert result["exercises"] == []
    assert result["learning_path"]  # 学习路径不受影响
