"""Tests for TextbookGenerator P0 quality gates (no LLM API required)."""

import json

from kag_pro.datasets.textbook_generator import TextbookGenerator

COMPLETE_BODY = (
    "一、定义\n" + "分数表示把单位1平均分成若干份。" * 30 + "\n二、示例\n例1略。"
)
TRUNCATED_BODY = "一、定义\n在溶液或熔融"
OUTLINE = {"小学": {"数学": ["分数的意义"], "语文": ["声母与韵母"]}}


class FakeGenerator:
    """Scripted LLM stub: returns queued responses for generate/fact-check calls."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def call(self, system, user, temperature=0.3, max_tokens=800):
        self.calls.append({"system": system, "max_tokens": max_tokens})
        if self._responses:
            return self._responses.pop(0)
        return COMPLETE_BODY


def make_gen(responses=None, fallback=None):
    return TextbookGenerator(generator=FakeGenerator(responses or []), fallback=fallback)


class TestCompletenessGate:

    def test_complete_text_passes(self):
        assert TextbookGenerator.is_complete(COMPLETE_BODY) is True

    def test_short_text_rejected(self):
        assert TextbookGenerator.is_complete(TRUNCATED_BODY) is False

    def test_non_punct_ending_rejected(self):
        body = "内容" * 200 + "未完"
        assert TextbookGenerator.is_complete(body) is False

    def test_latex_ending_accepted(self):
        body = "公式推导" * 100 + "得 $\\frac{1}{2}$"
        assert TextbookGenerator.is_complete(body) is True


class TestGatedGeneration:

    def test_science_triggers_fact_check(self):
        fake = FakeGenerator([COMPLETE_BODY, "通过"])
        gen = TextbookGenerator(generator=fake, fallback=None)
        text, checked, model = gen._generate_gated("小学", "数学", "分数的意义")
        assert text == COMPLETE_BODY
        assert checked is True
        assert model == gen._model
        assert len(fake.calls) == 2  # generate + fact-check

    def test_humanities_skip_fact_check(self):
        fake = FakeGenerator([COMPLETE_BODY])
        gen = TextbookGenerator(generator=fake, fallback=None)
        text, checked, _model = gen._generate_gated("小学", "语文", "声母与韵母")
        assert text == COMPLETE_BODY
        assert checked is False
        assert len(fake.calls) == 1  # generate only

    def test_truncated_first_attempt_retried(self):
        fake = FakeGenerator([TRUNCATED_BODY, COMPLETE_BODY, "通过"])
        gen = TextbookGenerator(generator=fake, fallback=None)
        text, _c, _m = gen._generate_gated("小学", "数学", "分数的意义")
        assert text == COMPLETE_BODY

    def test_fact_check_failure_retried(self):
        fake = FakeGenerator([COMPLETE_BODY, "有误：公式错误", COMPLETE_BODY, "通过"])
        gen = TextbookGenerator(generator=fake, fallback=None)
        text, _c, _m = gen._generate_gated("小学", "数学", "分数的意义")
        assert text == COMPLETE_BODY

    def test_fact_check_wu_wu_not_misjudged(self):
        """Regression: "经检查无误" must NOT be treated as a rejection
        (old substring check `'有误' not in review` false-positived on it)."""
        fake = FakeGenerator([COMPLETE_BODY, "经检查无误，内容准确。"])
        gen = TextbookGenerator(generator=fake, fallback=None)
        text, checked, _m = gen._generate_gated("小学", "数学", "分数的意义")
        assert text == COMPLETE_BODY
        assert checked is True

    def test_all_attempts_fail_returns_empty(self):
        fake = FakeGenerator([TRUNCATED_BODY] * 5)
        gen = TextbookGenerator(generator=fake, fallback=None)
        text, _c, _m = gen._generate_gated("小学", "数学", "分数的意义")
        assert text == ""

    def test_api_error_retried_with_backoff(self, monkeypatch):
        """Transient API errors are caught and retried, not fatal."""
        import kag_pro.datasets.textbook_generator as tg

        monkeypatch.setattr(tg.time, "sleep", lambda _: None)

        class FlakyGenerator(FakeGenerator):
            def __init__(self):
                super().__init__([COMPLETE_BODY, "通过"])
                self._failures = 2

            def call(self, system, user, temperature=0.3, max_tokens=800):
                if self._failures > 0:
                    self._failures -= 1
                    raise RuntimeError("connection reset")
                return super().call(system, user, temperature, max_tokens)

        gen = TextbookGenerator(generator=FlakyGenerator(), fallback=None)
        text, checked, _m = gen._generate_gated("小学", "数学", "分数的意义")
        assert text == COMPLETE_BODY
        assert checked is True

    def test_persistent_api_error_returns_empty(self, monkeypatch):
        import kag_pro.datasets.textbook_generator as tg

        monkeypatch.setattr(tg.time, "sleep", lambda _: None)

        class DeadGenerator(FakeGenerator):
            def call(self, system, user, temperature=0.3, max_tokens=800):
                raise RuntimeError("API down")

        gen = TextbookGenerator(generator=DeadGenerator([]), fallback=None)
        text, _c, _m = gen._generate_gated("小学", "语文", "声母与韵母")
        assert text == ""


class DeadChannel(FakeGenerator):
    """Channel stub that always raises (simulates provider outage/refusal)."""

    def call(self, system, user, temperature=0.3, max_tokens=800):
        raise RuntimeError("API down")


class QwenChannel(FakeGenerator):
    """Fallback channel stub exposing a qwen model name."""

    model = "qwen-plus"


class TestFallbackChannel:

    def test_fallback_rescues_when_primary_dead(self, monkeypatch):
        """Primary channel dead -> DashScope fallback gets its own retry round."""
        import kag_pro.datasets.textbook_generator as tg

        monkeypatch.setattr(tg.time, "sleep", lambda _: None)
        fb = QwenChannel([COMPLETE_BODY, "通过"])
        gen = TextbookGenerator(generator=DeadChannel([]), fallback=fb)
        text, checked, model = gen._generate_gated("小学", "数学", "分数的意义")
        assert text == COMPLETE_BODY
        assert checked is True
        assert model == "qwen-plus"

    def test_fallback_not_used_when_primary_succeeds(self):
        fb = QwenChannel([COMPLETE_BODY, "通过"])
        gen = TextbookGenerator(
            generator=FakeGenerator([COMPLETE_BODY, "通过"]), fallback=fb
        )
        text, _c, model = gen._generate_gated("小学", "数学", "分数的意义")
        assert text == COMPLETE_BODY
        assert model == gen._model  # primary model recorded, not qwen
        assert fb.calls == []  # fallback never touched

    def test_both_channels_dead_returns_empty(self, monkeypatch):
        import kag_pro.datasets.textbook_generator as tg

        monkeypatch.setattr(tg.time, "sleep", lambda _: None)
        gen = TextbookGenerator(
            generator=DeadChannel([]), fallback=DeadChannel([])
        )
        text, _c, _m = gen._generate_gated("小学", "语文", "声母与韵母")
        assert text == ""


class TestGenerateFromOutline:

    def test_generates_files_and_manifest(self, tmp_path):
        gen = make_gen([COMPLETE_BODY, "通过", COMPLETE_BODY])
        count = gen.generate_from_outline(OUTLINE, tmp_path)
        assert count == 2
        mat = (tmp_path / "gen_ele_mat_01.txt").read_text(encoding="utf-8")
        assert mat.startswith("小学数学 - 分数的意义\n\n")
        manifest = json.loads(
            (tmp_path / "generation_manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["gen_ele_mat_01.txt"]["topic"] == "分数的意义"
        assert manifest["gen_ele_mat_01.txt"]["fact_checked"] is True
        assert manifest["gen_ele_chi_01.txt"]["fact_checked"] is False

    def test_complete_existing_file_skipped(self, tmp_path):
        existing = tmp_path / "gen_ele_mat_01.txt"
        existing.write_text("小学数学 - 分数的意义\n\n" + COMPLETE_BODY, encoding="utf-8")
        fake = FakeGenerator([COMPLETE_BODY])
        gen = TextbookGenerator(generator=fake, fallback=None)
        count = gen.generate_from_outline(OUTLINE, tmp_path)
        assert count == 1  # only the chinese file is new
        assert len(fake.calls) == 1

    def test_truncated_existing_file_regenerated(self, tmp_path):
        existing = tmp_path / "gen_ele_mat_01.txt"
        existing.write_text("小学数学 - 分数的意义\n\n" + TRUNCATED_BODY, encoding="utf-8")
        fake = FakeGenerator([COMPLETE_BODY, "通过", COMPLETE_BODY])
        gen = TextbookGenerator(generator=fake, fallback=None)
        count = gen.generate_from_outline(OUTLINE, tmp_path)
        assert count == 2
        assert COMPLETE_BODY in existing.read_text(encoding="utf-8")

    def test_failed_generation_leaves_no_file(self, tmp_path):
        fake = FakeGenerator([TRUNCATED_BODY] * 10)
        gen = TextbookGenerator(generator=fake, fallback=None)
        count = gen.generate_from_outline({"小学": {"语文": ["声母与韵母"]}}, tmp_path)
        assert count == 0
        assert not (tmp_path / "gen_ele_chi_01.txt").exists()

    def test_fallback_model_recorded_in_manifest(self, tmp_path, monkeypatch):
        import kag_pro.datasets.textbook_generator as tg

        monkeypatch.setattr(tg.time, "sleep", lambda _: None)
        fb = QwenChannel([COMPLETE_BODY])
        gen = TextbookGenerator(generator=DeadChannel([]), fallback=fb)
        count = gen.generate_from_outline(
            {"小学": {"语文": ["声母与韵母"]}}, tmp_path
        )
        assert count == 1
        manifest = json.loads(
            (tmp_path / "generation_manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["gen_ele_chi_01.txt"]["model"] == "qwen-plus"
