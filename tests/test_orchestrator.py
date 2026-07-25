"""Tests for EducationOrchestrator (event-driven, replaces RAGPipeline).

Uses lightweight in-memory fakes registered into a PluginRegistry so the
orchestration logic and event flow can be tested without any network/LLM.
"""

import json
import os
import tempfile

import pytest

from kag_pro.core.bootstrap import create_default_registry
from kag_pro.core.event_bus import EventBus, Events
from kag_pro.core.registry import PluginRegistry
from kag_pro.core.types import DiagnosisResult, QueryResult
from kag_pro.orchestration.orchestrator import EducationOrchestrator
from kag_pro.stage.detector import EducationStage


@pytest.fixture(autouse=True)
def _redirect_low_confidence_log(tmp_path, monkeypatch):
    """Keep low-confidence JSONL out of the repo during tests."""
    monkeypatch.setenv("LOW_CONFIDENCE_LOG", str(tmp_path / "low_conf.jsonl"))


# === Lightweight fakes ===

class FakeGenerator:
    def generate(self, question, context_chunks, enrichment=None):
        return f"answer:{question}"

    def call(self, system, user, temperature=0.3, max_tokens=800):
        return "called"


class FakeRevisingGenerator(FakeGenerator):
    """Generator whose answers fail verification once, then get revised."""

    def revise(self, question, context_chunks, unsupported_claims, previous_answer):
        return f"revised:{question}"


class FakeSelfConsistentGenerator(FakeGenerator):
    """Generator exposing self-consistency voting for objective questions."""

    def generate_self_consistent(self, question, context_chunks, enrichment=None, n=3):
        return (
            "答案：B。三角形内角和是180度。",
            {"votes": {"B": 2, "A": 1}, "winner": "B", "samples": n},
        )


class FakeDetector:
    def analyze(self, question, generator=None):
        return {"stage": "初中", "subject": "math", "knowledge_module": "kp", "reason": "r"}

    def detect(self, question, generator=None):
        return EducationStage.MIDDLE


class FakeRetriever:
    def __init__(self, hits=None):
        self._hits = hits if hits is not None else [
            {"text": "三角形内角和是180度。", "metadata": {"source": "geo.txt"}, "score": 0.9},
        ]

    def retrieve(self, query, stage=None, subject=None):
        return list(self._hits)


class FakeVerifier:
    def verify(self, question, answer):
        return {"faith_score": 1.0, "verdict": "HIGH"}


class FakeLowVerifier:
    """Verifier that fails the initial answer and passes the revised one."""

    def verify(self, question, answer):
        if answer.startswith("revised:"):
            return {
                "faith_score": 0.9, "verdict": "HIGH",
                "supported": [{"claim": "c1"}], "unsupported": [],
            }
        return {
            "faith_score": 0.2, "verdict": "LOW",
            "supported": [], "unsupported": [{"claim": "c1"}],
        }


class FakeStore:
    def __init__(self):
        self.added = []
        self.cached_entry = None
        self.stored = []

    def add_documents(self, docs):
        self.added.extend(docs)

    def count(self):
        return len(self.added)

    def clear(self):
        self.added = []

    def cache_lookup(self, query, stage="", threshold=0.95):
        return self.cached_entry

    def cache_store(self, query, answer, stage="", faith_score=1.0):
        self.stored.append({
            "query": query, "answer": answer,
            "stage": stage, "faith_score": faith_score,
        })


class FakeClassifier:
    def classify(self, question, student_answer, correct_answer):
        return {
            "error_type": "calculation_error",
            "knowledge_point": "四则运算",
            "hint": "先乘除后加减",
            "confidence": 0.8,
        }


class FakeDiagnoser:
    def __init__(self):
        self._classifier = FakeClassifier()

    def diagnose(self, question, student_answer, correct_answer, stage="middle"):
        return {
            "error_type": "calculation_error",
            "confidence": 0.8,
            "knowledge_point": "四则运算",
            "hint": "先乘除后加减",
            "remedial_content": "运算顺序：先算乘除，再算加减。",
            "personalized_feedback": "再仔细按顺序算一遍。",
        }

    def generate_exercises(self, knowledge_point, error_type, count=3):
        return f"exercises for {knowledge_point}"


class FakeRecommender:
    def recommend(self, error_history, count=3):
        return {
            "weak_points": [{"knowledge_point": "四则运算"}],
            "exercises": [{"content": "q1"}],
            "learning_path": ["复习四则运算"],
        }


class FakeSplitter:
    def split(self, documents):
        return list(documents)


class FakePaperGenerator:
    def generate(self, stage, subject, topics, count=5, difficulty="中等", question_types=None):
        return {"title": "测验", "stage": stage, "subject": subject, "count": count,
                "questions": [{"id": i + 1} for i in range(count)]}


class FakeEvaluator:
    def evaluate_batch(self, test_data):
        return {"count": len(test_data), "avg_accuracy": 1.0}


def make_registry(
    with_kg: bool = False, hits=None,
    generator=None, verifier=None,
) -> PluginRegistry:
    r = PluginRegistry()
    r.register("stage-detector", FakeDetector())
    r.register("generator", generator or FakeGenerator())
    r.register("retriever", FakeRetriever(hits))
    r.register("verifier", verifier or FakeVerifier())
    r.register("vector-store", FakeStore())
    r.register("text-splitter", FakeSplitter())
    r.register("diagnoser", FakeDiagnoser())
    r.register("paper-generator", FakePaperGenerator())
    r.register("evaluator", FakeEvaluator())
    if with_kg:
        r.register("recommender", FakeRecommender())
    return r


class TestOrchestratorQuery:

    def test_query_returns_result(self):
        orch = EducationOrchestrator(make_registry())
        result = orch.query("三角形的内角和是多少？")
        assert isinstance(result, QueryResult)
        assert result.answer == "answer:三角形的内角和是多少？"
        assert result.stage == "初中"
        assert result.sources
        assert result.sources[0]["source"] == "geo.txt"

    def test_query_publishes_events(self):
        bus = EventBus()
        seen = []
        for e in (Events.QUERY_RECEIVED, Events.STAGE_DETECTED,
                  Events.RETRIEVAL_COMPLETED, Events.ANSWER_GENERATED):
            bus.subscribe(e, lambda d, _e=e: seen.append(_e))
        orch = EducationOrchestrator(make_registry(), bus)
        orch.query("三角形的内角和是多少？")
        assert Events.QUERY_RECEIVED in seen
        assert Events.STAGE_DETECTED in seen
        assert Events.RETRIEVAL_COMPLETED in seen
        assert Events.ANSWER_GENERATED in seen

    def test_query_verify_produces_verification(self):
        bus = EventBus()
        verified = []
        bus.subscribe(Events.ANSWER_VERIFIED, lambda d: verified.append(d))
        orch = EducationOrchestrator(make_registry(), bus)
        result = orch.query("q", verify=True)
        assert result.verification is not None
        assert result.verification["verdict"] == "HIGH"
        assert len(verified) == 1

    def test_query_empty_hits_publishes_retrieval_empty(self):
        bus = EventBus()
        empty = []
        bus.subscribe(Events.RETRIEVAL_EMPTY, lambda d: empty.append(d))
        orch = EducationOrchestrator(make_registry(hits=[]), bus)
        result = orch.query("完全不相关的问题")
        assert result.sources == []
        assert len(empty) == 1

    def test_weak_retrieval_takes_clarification_path(self):
        """Hits below the clarify gate must NOT reach the generator."""
        bus = EventBus()
        weak = []
        bus.subscribe(Events.RETRIEVAL_WEAK, lambda d: weak.append(d))
        hits = [{"text": "弱相关内容", "metadata": {"source": "weak.txt"}, "score": 0.35}]
        orch = EducationOrchestrator(make_registry(hits=hits), bus)
        result = orch.query("模糊的问题", verify=True)
        assert result.clarification is True
        assert "没有找到与这个问题足够相关的内容" in result.answer
        assert not result.answer.startswith("answer:")
        # Clarification path skips factual verification
        assert result.verification is None
        assert len(weak) == 1
        assert weak[0]["best_score"] == 0.35

    def test_low_verdict_triggers_self_correction(self):
        """LOW verdict rewrites the answer once and re-verifies."""
        bus = EventBus()
        revised_events = []
        bus.subscribe(Events.ANSWER_REVISED, lambda d: revised_events.append(d))
        orch = EducationOrchestrator(make_registry(
            generator=FakeRevisingGenerator(), verifier=FakeLowVerifier(),
        ), bus)
        result = orch.query("q", verify=True)
        assert result.answer == "revised:q"
        assert result.verification["revised"] is True
        assert result.verification["previous_faith_score"] == 0.2
        assert result.verification["faith_score"] == 0.9
        assert len(revised_events) == 1

    def test_low_verdict_without_revise_support_keeps_answer(self):
        """Generators without revise() keep the original answer."""
        orch = EducationOrchestrator(make_registry(verifier=FakeLowVerifier()))
        result = orch.query("q", verify=True)
        assert result.answer == "answer:q"
        assert "revised" not in result.verification

    def test_high_verdict_answer_is_cached(self):
        """Verified-HIGH answers are written to the semantic answer cache."""
        registry = make_registry()
        store = registry.resolve("vector-store")
        orch = EducationOrchestrator(registry)
        result = orch.query("三角形的内角和是多少？", verify=True)
        assert len(store.stored) == 1
        assert store.stored[0]["answer"] == result.answer
        assert store.stored[0]["stage"] == "初中"
        assert result.cache_hit is False

    def test_low_verdict_answer_not_cached_without_revision(self):
        """Answers stuck at LOW verdict must not enter the cache."""
        registry = make_registry(verifier=FakeLowVerifier())
        store = registry.resolve("vector-store")
        orch = EducationOrchestrator(registry)
        orch.query("q", verify=True)
        assert store.stored == []

    def test_cache_hit_skips_generation_and_verifier(self):
        """A cache hit reuses the verified answer without LLM/verifier calls."""

        class ExplodingGenerator(FakeGenerator):
            def generate(self, question, context_chunks, enrichment=None):
                raise AssertionError("generate() must not run on cache hit")

        registry = make_registry(generator=ExplodingGenerator())
        store = registry.resolve("vector-store")
        store.cached_entry = {
            "answer": "缓存的可靠答案", "similarity": 0.97, "faith_score": 0.9,
        }
        bus = EventBus()
        hits = []
        bus.subscribe(Events.ANSWER_CACHE_HIT, lambda d: hits.append(d))
        orch = EducationOrchestrator(registry, bus)
        result = orch.query("q", verify=True)
        assert result.answer == "缓存的可靠答案"
        assert result.cache_hit is True
        assert result.verification["from_cache"] is True
        assert result.verification["faith_score"] == 0.9
        assert len(hits) == 1

    def test_objective_question_uses_self_consistency(self):
        """Choice questions route through majority-vote generation."""
        orch = EducationOrchestrator(make_registry(generator=FakeSelfConsistentGenerator()))
        result = orch.query("下列说法正确的是？A. 甲 B. 乙", verify=True)
        assert result.answer.startswith("答案：B")
        assert result.verification["self_consistency"]["winner"] == "B"
        assert result.verification["self_consistency"]["votes"] == {"B": 2, "A": 1}

    def test_non_objective_question_skips_self_consistency(self):
        orch = EducationOrchestrator(make_registry(generator=FakeSelfConsistentGenerator()))
        result = orch.query("三角形的内角和是多少？")
        # Falls back to plain generate()
        assert result.answer == "answer:三角形的内角和是多少？"

    def test_composite_confidence_attached(self):
        """confidence = 0.5*faith + 0.3*best_score + 0.2*kg(0.5 without KG)."""
        orch = EducationOrchestrator(make_registry())
        result = orch.query("三角形的内角和是多少？", verify=True)
        # faith 1.0, best_score 0.9, no KG → 0.5 + 0.27 + 0.1 = 0.87
        assert result.verification["confidence"] == 0.87
        assert result.verification["low_confidence"] is False

    def test_low_confidence_sample_is_logged(self, tmp_path, monkeypatch):
        log_path = tmp_path / "custom_low_conf.jsonl"
        monkeypatch.setenv("LOW_CONFIDENCE_LOG", str(log_path))
        orch = EducationOrchestrator(make_registry(verifier=FakeLowVerifier()))
        result = orch.query("q", verify=True)
        # faith 0.2 → confidence 0.1+0.27+0.1 = 0.47 < 0.5
        assert result.verification["low_confidence"] is True
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["question"] == "q"
        assert record["verdict"] == "LOW"
        assert record["confidence"] < 0.5


class TestOrchestratorDiagnose:

    def test_diagnose_returns_result_and_records_error(self):
        bus = EventBus()
        recorded, completed = [], []
        bus.subscribe(Events.ERROR_RECORDED, lambda d: recorded.append(d))
        bus.subscribe(Events.DIAGNOSIS_COMPLETED, lambda d: completed.append(d))
        orch = EducationOrchestrator(make_registry(), bus)
        result = orch.diagnose("计算 (3+2)×4", "11", "20", stage="middle")
        assert isinstance(result, DiagnosisResult)
        assert result.stage == "初中"
        assert result.knowledge_point == "四则运算"
        assert len(orch.error_history) == 1
        assert len(recorded) == 1
        assert len(completed) == 1

    def test_diagnose_auto_recommends_after_two_errors(self):
        orch = EducationOrchestrator(make_registry(with_kg=True))
        orch.diagnose("q1", "a", "b", stage="middle")
        second = orch.diagnose("q2", "a", "b", stage="middle")
        assert second.exercises is not None
        assert len(orch.error_history) == 2


class TestOrchestratorRecommend:

    def test_recommend_without_recommender(self):
        orch = EducationOrchestrator(make_registry())
        out = orch.recommend()
        assert "error" in out

    def test_recommend_without_history(self):
        orch = EducationOrchestrator(make_registry(with_kg=True))
        out = orch.recommend()
        assert "error" in out

    def test_recommend_success(self):
        bus = EventBus()
        ready = []
        bus.subscribe(Events.RECOMMENDATION_READY, lambda d: ready.append(d))
        orch = EducationOrchestrator(make_registry(with_kg=True), bus)
        orch.diagnose("q1", "a", "b", stage="middle")
        out = orch.recommend(count=3)
        assert "exercises" in out
        assert len(ready) == 1


class TestOrchestratorMisc:

    def test_exercises(self):
        orch = EducationOrchestrator(make_registry())
        out = orch.exercises("计算题", "11", "20")
        assert out["knowledge_point"] == "四则运算"
        assert "四则运算" in out["exercises"]

    def test_generate_paper_publishes_event(self):
        bus = EventBus()
        papers = []
        bus.subscribe(Events.PAPER_GENERATED, lambda d: papers.append(d))
        orch = EducationOrchestrator(make_registry(), bus)
        paper = orch.generate_paper("初中", "数学", ["一元二次方程"], count=3)
        assert paper["count"] == 3
        assert len(paper["questions"]) == 3
        assert len(papers) == 1

    def test_evaluate(self):
        orch = EducationOrchestrator(make_registry())
        out = orch.evaluate([{"question": "q1", "reference": "r1"}])
        assert out["count"] == 1

    def test_document_count_and_clear(self):
        orch = EducationOrchestrator(make_registry())
        assert orch.document_count == 0
        orch.clear_index()
        assert orch.document_count == 0

    def test_index_documents_with_real_files(self):
        orch = EducationOrchestrator(make_registry())
        indexed = []
        orch.bus.subscribe(Events.DOCUMENTS_INDEXED, lambda d: indexed.append(d))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "01_math.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("分数的意义：把单位1平均分成若干份，表示这样一份或几份的数叫分数。")
            n = orch.index_documents(tmpdir)
            assert n >= 1
            assert len(indexed) == 1


class TestOrchestratorBootstrapWiring:
    """Smoke tests against the real bootstrap registry (no API key needed)."""

    def test_index_empty_directory_returns_zero(self):
        orch = EducationOrchestrator(create_default_registry())
        with tempfile.TemporaryDirectory() as empty_dir:
            assert orch.index_documents(empty_dir) == 0

    def test_registry_exposes_core_services(self):
        registry = create_default_registry(use_kg=True)
        for name in ("generator", "embedder", "vector-store", "retriever",
                     "stage-detector", "diagnoser", "paper-generator",
                     "evaluator", "knowledge-graph", "kg-retriever", "recommender"):
            assert registry.has(name), f"missing service: {name}"
