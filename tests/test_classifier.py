"""Tests for ErrorClassifier."""

from kag_pro.diagnosis.classifier import ErrorClassifier


class TestErrorClassifier:

    def test_missing_root_detection(self):
        result = ErrorClassifier.classify(
            question="解方程 x² - 4 = 0",
            student_answer="x=2",
            correct_answer="x=2 或 x=-2",
        )
        assert result["error_type"] == "missing_root"
        assert result["knowledge_point"] == "一元二次方程求根"
        assert result["confidence"] > 0

    def test_calculation_error(self):
        result = ErrorClassifier.classify(
            question="计算 (3+2)×4",
            student_answer="11",
            correct_answer="20",
        )
        assert result["error_type"] == "calculation_error"

    def test_default_fallback(self):
        result = ErrorClassifier.classify(
            question="什么是光合作用？",
            student_answer="植物呼吸",
            correct_answer="植物利用光能合成有机物",
        )
        assert result["error_type"] in ErrorClassifier.ERROR_PATTERNS
        assert "knowledge_point" in result
        assert "hint" in result

    def test_all_error_types_have_required_fields(self):
        for error_type, config in ErrorClassifier.ERROR_PATTERNS.items():
            assert "knowledge_point" in config
            assert "hint" in config
            assert "keywords" in config
