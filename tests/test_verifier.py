"""Tests for FactualVerifier (heuristic + LLM-as-judge modes)."""

from unittest.mock import MagicMock

from kag_pro.core.verifier import FactualVerifier

ANSWER = "三角形的内角和等于180度，这是欧氏几何的基本定理。勾股定理适用于所有三角形。"


def make_store(hits):
    store = MagicMock()
    store.search.return_value = hits
    return store


class FakeJudgeGenerator:
    """Scripted LLM judge — returns a fixed label for every claim."""

    def __init__(self, label: str):
        self._label = label
        self.calls = 0

    def call(self, system, user, temperature=0.0, max_tokens=10):
        self.calls += 1
        return self._label


class ExplodingJudgeGenerator:
    def call(self, system, user, temperature=0.0, max_tokens=10):
        raise RuntimeError("judge unavailable")


HITS = [{"text": "三角形内角和为180度。", "metadata": {"source": "geo.txt"}, "score": 0.9}]


class TestHeuristicMode:

    def test_hits_count_as_supported(self):
        verifier = FactualVerifier(make_store(HITS), judge_mode="heuristic")
        result = verifier.verify("q", ANSWER)
        assert result["judge_mode"] == "heuristic"
        assert result["verdict"] == "HIGH"
        assert len(result["supported"]) == result["total_claims"]
        assert result["contradicted"] == []

    def test_no_hits_marks_neutral(self):
        verifier = FactualVerifier(make_store([]), judge_mode="heuristic")
        result = verifier.verify("q", ANSWER)
        assert result["supported"] == []
        assert len(result["unsupported"]) == result["total_claims"]
        # Neutral claims score 0.5 each → MEDIUM
        assert result["verdict"] == "MEDIUM"
        assert result["faith_score"] == 0.5


class TestLLMJudgeMode:

    def test_contradiction_drives_low_verdict(self):
        verifier = FactualVerifier(
            make_store(HITS), generator=FakeJudgeGenerator("矛盾"),
        )
        result = verifier.verify("q", ANSWER)
        assert result["judge_mode"] == "llm"
        assert len(result["contradicted"]) == result["total_claims"]
        # 0.5 neutral base − 0.2 per contradiction → 0.0 → LOW
        assert result["faith_score"] == 0.0
        assert result["verdict"] == "LOW"

    def test_support_label_gives_high_verdict(self):
        verifier = FactualVerifier(
            make_store(HITS), generator=FakeJudgeGenerator("支持"),
        )
        result = verifier.verify("q", ANSWER)
        assert result["verdict"] == "HIGH"
        assert result["faith_score"] == 1.0

    def test_judge_is_called_per_claim(self):
        judge = FakeJudgeGenerator("支持")
        verifier = FactualVerifier(make_store(HITS), generator=judge)
        result = verifier.verify("q", ANSWER)
        assert judge.calls == result["total_claims"]

    def test_judge_failure_degrades_to_heuristic(self):
        verifier = FactualVerifier(
            make_store(HITS), generator=ExplodingJudgeGenerator(),
        )
        result = verifier.verify("q", ANSWER)
        # Strong similarity (0.9 ≥ threshold) still counts as support
        assert result["verdict"] == "HIGH"

    def test_empty_answer_needs_no_verification(self):
        verifier = FactualVerifier(make_store([]), generator=FakeJudgeGenerator("支持"))
        result = verifier.verify("q", "短句。")
        assert result["faith_score"] == 1.0
        assert result["details"] == "No claims to verify"
