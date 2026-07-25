"""Tests for DocumentLoader stage/subject inference."""

from kag_pro.core.loader import DocumentLoader


class TestGenFilenameParsing:
    """gen_{stage}_{subject}_{nn}.txt convention from generate_textbooks.py."""

    def test_ele_mat_maps_to_primary_math(self):
        assert DocumentLoader._infer_stage("gen_ele_mat_01.txt") == "primary"
        assert DocumentLoader._infer_subject("gen_ele_mat_01.txt", "任意正文") == "math"

    def test_ele_oly_maps_to_primary_math(self):
        assert DocumentLoader._infer_stage("gen_ele_oly_01.txt") == "primary"
        assert DocumentLoader._infer_subject("gen_ele_oly_01.txt", "任意正文") == "math"

    def test_oly_math_even_without_keywords_in_text(self):
        text = "笼子里有若干只动物，总头数和总脚数已知。"
        assert DocumentLoader._infer_subject("gen_ele_oly_02.txt", text) == "math"

    def test_mid_phy_maps_to_middle_physics(self):
        assert DocumentLoader._infer_stage("gen_mid_phy_03.txt") == "middle"
        assert DocumentLoader._infer_subject("gen_mid_phy_03.txt", "任意正文") == "physics"

    def test_hig_his_maps_to_high_history(self):
        assert DocumentLoader._infer_stage("gen_hig_his_12.txt") == "high"
        assert DocumentLoader._infer_subject("gen_hig_his_12.txt", "任意正文") == "history"

    def test_unknown_codes_fall_back(self):
        # gen_gen_gen is the generator's fallback prefix for unmapped subjects
        assert DocumentLoader._infer_stage("gen_gen_gen_01.txt") == "unknown"
        assert DocumentLoader._infer_subject("gen_gen_gen_01.txt", "没有关键词的文本") == "general"


class TestLegacyInference:
    """Numeric-prefix stage inference and keyword subject inference still work."""

    def test_numeric_prefix_primary(self):
        assert DocumentLoader._infer_stage("01_分数初步.txt") == "primary"

    def test_numeric_prefix_middle(self):
        assert DocumentLoader._infer_stage("06_初中代数方程.txt") == "middle"

    def test_numeric_prefix_high(self):
        assert DocumentLoader._infer_stage("12_高中导数微积分.txt") == "high"

    def test_keyword_subject_math(self):
        assert DocumentLoader._infer_subject("01_分数初步.txt", "分数的意义") == "math"

    def test_keyword_fallback_general(self):
        assert DocumentLoader._infer_subject("notes.txt", "没有任何学科关键词") == "general"

    def test_unknown_stage(self):
        assert DocumentLoader._infer_stage("notes.txt") == "unknown"

    def test_stage_keyword_fallback_beyond_numeric_range(self):
        assert DocumentLoader._infer_stage("21_初中物理物态变化.txt") == "middle"
        assert DocumentLoader._infer_stage("22_小学科学启蒙.txt") == "primary"
        assert DocumentLoader._infer_stage("23_高中竞赛导论.txt") == "high"


class TestLoadIntegration:

    def test_load_assigns_gen_metadata(self, tmp_path):
        (tmp_path / "gen_ele_oly_01.txt").write_text("小学奥数 - 鸡兔同笼\n\n假设法讲解。", encoding="utf-8")
        docs = DocumentLoader(tmp_path).load()
        assert len(docs) == 1
        assert docs[0].metadata["stage"] == "primary"
        assert docs[0].metadata["subject"] == "math"

    def test_load_without_inference(self, tmp_path):
        (tmp_path / "gen_ele_mat_01.txt").write_text("内容", encoding="utf-8")
        docs = DocumentLoader(tmp_path).load(infer_stage=False)
        assert "stage" not in docs[0].metadata
        assert "subject" not in docs[0].metadata
