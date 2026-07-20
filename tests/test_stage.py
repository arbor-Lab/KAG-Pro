"""Tests for StageDetector."""

from kag_pro.stage.detector import StageDetector, EducationStage


class TestStageDetector:

    def test_primary_math(self):
        stage = StageDetector.detect("三角形的内角和是多少度？")
        assert stage == EducationStage.PRIMARY

    def test_primary_fraction(self):
        stage = StageDetector.detect("什么是分数？")
        assert stage == EducationStage.PRIMARY

    def test_middle_equation(self):
        stage = StageDetector.detect("用求根公式解一元二次方程 x²-5x+6=0")
        assert stage == EducationStage.MIDDLE

    def test_middle_chemistry(self):
        stage = StageDetector.detect("影响化学反应速率的因素有哪些？")
        assert stage == EducationStage.MIDDLE

    def test_middle_physics(self):
        stage = StageDetector.detect("根据牛顿第二定律 F=ma 计算加速度")
        assert stage == EducationStage.MIDDLE

    def test_high_calculus(self):
        stage = StageDetector.detect("求函数 f(x)=x³+2x 的导数")
        assert stage == EducationStage.HIGH

    def test_unknown_fallback_short(self):
        stage = StageDetector.detect("为什么？")
        assert stage == EducationStage.PRIMARY

    def test_unknown_fallback_long(self):
        stage = StageDetector.detect("请详细解释量子力学中的不确定性原理及其数学推导过程")
        # 20-char question with no keywords falls in MIDDLE range (15-30)
        assert stage == EducationStage.MIDDLE

    def test_get_stage_name(self):
        assert StageDetector.get_stage_name(EducationStage.PRIMARY) == "小学"
        assert StageDetector.get_stage_name(EducationStage.MIDDLE) == "初中"
        assert StageDetector.get_stage_name(EducationStage.HIGH) == "高中"
        assert StageDetector.get_stage_name(EducationStage.UNIVERSITY) == "大学"
