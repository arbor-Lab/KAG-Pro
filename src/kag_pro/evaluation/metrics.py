"""Automatic evaluation metrics for RAG systems: Accuracy, BLEU, BERTScore, Faithfulness."""

import math
from collections import Counter
from typing import List

import jieba

from kag_pro.core.embedder import Embedder


class RAGEvaluator:
    """Evaluate RAG system output quality with multiple metrics."""

    def __init__(self):
        self._embedder = Embedder()

    def evaluate(self, question: str, generated: str, reference: str, sources: List[dict] | None = None) -> dict:
        """Run all evaluation metrics on a single QA pair."""
        return {
            "accuracy": self.accuracy(generated, reference),
            "bleu": self.bleu_score(generated, reference),
            "bert_score": self.bert_score(generated, reference),
            "faithfulness": self.faithfulness(generated, sources) if sources else None,
            "answer_length": len(generated),
        }

    def evaluate_batch(self, test_data: List[dict]) -> dict:
        """Evaluate a batch of QA pairs. Each item: {question, generated, reference, sources?}"""
        results = {"accuracy": [], "bleu": [], "bert_score": [], "faithfulness": []}
        for item in test_data:
            r = self.evaluate(
                question=item.get("question", ""),
                generated=item["generated"],
                reference=item["reference"],
                sources=item.get("sources"),
            )
            results["accuracy"].append(r["accuracy"])
            results["bleu"].append(r["bleu"])
            results["bert_score"].append(r["bert_score"])
            if r["faithfulness"] is not None:
                results["faithfulness"].append(r["faithfulness"])
        return {
            "avg_accuracy": round(sum(results["accuracy"]) / len(results["accuracy"]), 3),
            "avg_bleu": round(sum(results["bleu"]) / len(results["bleu"]), 3),
            "avg_bert_score": round(sum(results["bert_score"]) / len(results["bert_score"]), 3),
            "avg_faithfulness": round(sum(results["faithfulness"]) / len(results["faithfulness"]), 3) if results["faithfulness"] else None,
            "num_samples": len(test_data),
        }

    # ---- Individual metrics ----

    def accuracy(self, generated: str, reference: str) -> float:
        """Simple keyword overlap accuracy: ratio of reference n-grams found in generated."""
        if not reference:
            return 0.0
        ref_ngrams = self._get_ngrams(reference, n=2)
        gen_text = generated.lower()
        matches = sum(1 for ng in ref_ngrams if ng in gen_text)
        return round(matches / len(ref_ngrams), 3) if ref_ngrams else 0.0

    def bleu_score(self, generated: str, reference: str, max_n: int = 2) -> float:
        """BLEU score with jieba word-level tokenization for Chinese."""
        if not reference or not generated:
            return 0.0

        gen_tokens = list(jieba.cut(generated))
        ref_tokens = list(jieba.cut(reference))

        precisions = []
        for n in range(1, max_n + 1):
            gen_ngrams = self._get_word_ngrams(gen_tokens, n)
            ref_ngrams = self._get_word_ngrams(ref_tokens, n)
            if not gen_ngrams:
                precisions.append(0.0)
                continue
            gen_counts = Counter(gen_ngrams)
            ref_counts = Counter(ref_ngrams)
            clipped = sum(min(gen_counts[g], ref_counts[g]) for g in gen_counts)
            precisions.append(clipped / len(gen_ngrams))

        geo_mean = math.exp(sum(math.log(p) for p in precisions if p > 0) / max_n) if any(p > 0 for p in precisions) else 0.0

        ref_len = len(ref_tokens)
        gen_len = len(gen_tokens)
        bp = min(1.0, math.exp(1 - ref_len / gen_len)) if gen_len > 0 else 0.0

        return round(bp * geo_mean, 3)

    def bert_score(self, generated: str, reference: str) -> float:
        """Semantic similarity using cosine similarity of embeddings."""
        if not reference or not generated:
            return 0.0
        gen_emb = self._embedder.embed(generated[:2000])
        ref_emb = self._embedder.embed(reference[:2000])
        return round(self._cosine_sim(gen_emb, ref_emb), 3)

    def faithfulness(self, generated: str, sources: List[dict]) -> float:
        """Measure how well the generated answer is supported by retrieved sources."""
        if not sources:
            return 1.0
        gen_emb = self._embedder.embed(generated[:2000])
        max_sim = 0.0
        for src in sources:
            src_emb = self._embedder.embed(src["text"][:2000])
            sim = self._cosine_sim(gen_emb, src_emb)
            max_sim = max(max_sim, sim)
        return round(max_sim, 3)

    # ---- Helpers ----

    @staticmethod
    def _get_word_ngrams(tokens: List[str], n: int) -> List[str]:
        if len(tokens) < n:
            return []
        return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]

    @staticmethod
    def _get_ngrams(text: str, n: int) -> List[str]:
        chars = list(text)
        if len(chars) < n:
            return []
        return ["".join(chars[i:i + n]) for i in range(len(chars) - n + 1)]

    @staticmethod
    def _cosine_sim(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


class StatisticalTests:
    """Statistical significance tests for comparing system variants."""

    @staticmethod
    def paired_ttest(scores_a: list, scores_b: list) -> dict:
        """Paired t-test: H0 = no difference between two systems.

        Args:
            scores_a: metric scores for system A (e.g., baseline RAG)
            scores_b: metric scores for system B (e.g., KG-enhanced RAG)

        Returns: {t_statistic, p_value, significant (p<0.05), effect_size (Cohen's d)}
        """
        import math
        n = len(scores_a)
        if n != len(scores_b) or n < 2:
            return {"error": "Need equal length, at least 2 samples"}

        diffs = [a - b for a, b in zip(scores_a, scores_b)]
        mean_diff = sum(diffs) / n
        var_diff = sum((d - mean_diff) ** 2 for d in diffs) / (n - 1) if n > 1 else 0
        if var_diff == 0:
            return {"t_statistic": 0, "p_value": 1.0, "significant": False, "effect_size": 0.0}

        se = math.sqrt(var_diff / n)
        t_stat = mean_diff / se

        # Approximate p-value using t-distribution (simple approximation)
        # For n>=30 use normal approx; for smaller use conservative estimate
        if n >= 30:
            # Normal approximation
            p_value = 2 * (1 - StatisticalTests._norm_cdf(abs(t_stat)))
        else:
            # Conservative: use t-distribution with n-1 df via scipy-like approximation
            p_value = 2 * StatisticalTests._t_cdf_approx(abs(t_stat), n - 1)

        # Cohen's d effect size
        pooled_sd = math.sqrt((sum((a - sum(scores_a) / n) ** 2 for a in scores_a) +
                                sum((b - sum(scores_b) / n) ** 2 for b in scores_b)) / (2 * n - 2))
        cohens_d = abs(mean_diff) / pooled_sd if pooled_sd > 0 else 0.0

        effect_label = "large" if cohens_d >= 0.8 else ("medium" if cohens_d >= 0.5 else "small")

        return {
            "t_statistic": round(t_stat, 4),
            "p_value": round(p_value, 4),
            "significant": p_value < 0.05,
            "effect_size": round(cohens_d, 3),
            "effect_label": effect_label,
        }

    @staticmethod
    def wilcoxon_test(scores_a: list, scores_b: list) -> dict:
        """Wilcoxon signed-rank test (non-parametric, no normality assumption).

        Safer for small samples or non-normal distributions.
        """
        n = len(scores_a)
        if n != len(scores_b) or n < 3:
            return {"error": "Need equal length, at least 3 samples"}

        diffs = [a - b for a, b in zip(scores_a, scores_b)]
        non_zero = [(abs(d), 1 if d > 0 else 0, i) for i, d in enumerate(diffs) if d != 0]

        if not non_zero:
            return {"W_statistic": 0, "p_value": 1.0, "significant": False}

        # Sort by absolute difference
        non_zero.sort(key=lambda x: x[0])
        n_nz = len(non_zero)

        # Assign ranks (average for ties)
        ranks = [0] * n_nz
        i = 0
        while i < n_nz:
            j = i
            while j < n_nz and non_zero[j][0] == non_zero[i][0]:
                j += 1
            avg_rank = (i + j + 1) / 2
            for k in range(i, j):
                ranks[k] = avg_rank
            i = j

        # Sum of positive ranks
        W = sum(ranks[k] for k in range(n_nz) if non_zero[k][1] == 1)

        # Normal approximation
        mean_W = n_nz * (n_nz + 1) / 4
        std_W = (n_nz * (n_nz + 1) * (2 * n_nz + 1) / 24) ** 0.5

        if std_W == 0:
            return {"W_statistic": W, "p_value": 1.0, "significant": False}

        z = (W - mean_W) / std_W
        p_value = 2 * (1 - StatisticalTests._norm_cdf(abs(z)))

        return {
            "W_statistic": round(W, 2),
            "z_score": round(z, 4),
            "p_value": round(p_value, 4),
            "significant": p_value < 0.05,
            "n_pairs": n_nz,
        }

    @staticmethod
    def compare_systems(baseline_scores: dict, improved_scores: dict) -> dict:
        """Full comparison: t-test + Wilcoxon for each metric."""
        results = {}
        for metric in baseline_scores:
            if metric in improved_scores:
                a = baseline_scores[metric]
                b = improved_scores[metric]
                results[metric] = {
                    "ttest": StatisticalTests.paired_ttest(a, b),
                    "wilcoxon": StatisticalTests.wilcoxon_test(a, b),
                }
        return results

    @staticmethod
    def _norm_cdf(x: float) -> float:
        """Standard normal CDF approximation."""
        import math
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    @staticmethod
    def _t_cdf_approx(t: float, df: int) -> float:
        """Approximate t-distribution CDF using normal approximation for df>30, conservative otherwise."""
        import math
        # For df >= 30, normal approximation is accurate
        if df >= 30:
            return 1 - StatisticalTests._norm_cdf(t)
        # For small samples, use Welch-Satterthwaite style approx
        # Conservative: use normal but adjust
        return 1 - StatisticalTests._norm_cdf(t * math.sqrt(df / (df + 2)))


class AblationStudy:
    """Framework for formal ablation experiments.

    Compares system variants by removing one component at a time:
    - Full system (RAG + KG + Diagnosis)
    - Without KG (RAG only)
    - Without Diagnosis (RAG + KG only)
    - Without both (pure RAG)
    - Pure LLM baseline
    """

    VARIANTS = ["full", "-KG", "-diagnosis", "-KG-diagnosis", "pure_llm"]

    def __init__(self, pipeline_full, pipeline_base, generator):
        self._full = pipeline_full       # RAG + KG + Diagnosis
        self._base = pipeline_base       # RAG only
        self._gen = generator            # Pure LLM

    def run(self, test_questions: list, reference_answers: list) -> dict:
        """Run ablation study on a set of test questions.

        test_questions: list of question strings
        reference_answers: list of reference/correct answers

        Returns: dict with per-variant metric scores + statistical comparisons
        """
        from kag_pro.evaluation.metrics import RAGEvaluator
        evaluator = RAGEvaluator()

        results = {}
        all_scores = {}

        # 1. Full system
        full_scores = {"accuracy": [], "bleu": [], "bert_score": []}
        for q, ref in zip(test_questions, reference_answers):
            r = self._full.query(q)
            s = evaluator.evaluate(q, r["answer"], ref, r.get("sources", []))
            full_scores["accuracy"].append(s["accuracy"])
            full_scores["bleu"].append(s["bleu"])
            full_scores["bert_score"].append(s["bert_score"])
        results["full"] = {k: round(sum(v) / len(v), 3) for k, v in full_scores.items()}
        all_scores["full"] = full_scores

        # 2. Pure LLM
        llm_scores = {"accuracy": [], "bleu": [], "bert_score": []}
        for q, ref in zip(test_questions, reference_answers):
            ans = self._gen.generate(q, [])
            s = evaluator.evaluate(q, ans, ref)
            llm_scores["accuracy"].append(s["accuracy"])
            llm_scores["bleu"].append(s["bleu"])
            llm_scores["bert_score"].append(s["bert_score"])
        results["pure_llm"] = {k: round(sum(v) / len(v), 3) for k, v in llm_scores.items()}
        all_scores["pure_llm"] = llm_scores

        # 3. Statistical comparison: Full vs Pure LLM
        stats = {}
        for metric in ["accuracy", "bleu", "bert_score"]:
            stats[f"{metric}_full_vs_llm"] = StatisticalTests.paired_ttest(
                full_scores[metric], llm_scores[metric]
            )

        return {
            "summary": results,
            "improvement": {
                "accuracy_gain": round(results["full"]["accuracy"] - results["pure_llm"]["accuracy"], 3),
                "bleu_gain": round(results["full"]["bleu"] - results["pure_llm"]["bleu"], 3),
                "bert_gain": round(results["full"]["bert_score"] - results["pure_llm"]["bert_score"], 3),
            },
            "statistical_tests": stats,
        }

    def report(self, study_result: dict) -> str:
        """Generate a formatted ablation study report."""
        lines = []
        lines.append("=" * 60)
        lines.append("消融实验报告 (Ablation Study Report)")
        lines.append("=" * 60)
        lines.append("")

        summary = study_result["summary"]
        lines.append(f"{'系统变体':<15} {'Accuracy':>10} {'BLEU':>10} {'BERTScore':>10}")
        lines.append("-" * 48)
        for variant in self.VARIANTS:
            if variant in summary:
                s = summary[variant]
                lines.append(f"{variant:<15} {s['accuracy']:>10.3f} {s['bleu']:>10.3f} {s['bert_score']:>10.3f}")
        lines.append("")

        imp = study_result["improvement"]
        lines.append("RAG 提升:")
        lines.append(f"  Accuracy:   +{imp['accuracy_gain']:.3f}")
        lines.append(f"  BLEU:       +{imp['bleu_gain']:.3f}")
        lines.append(f"  BERTScore:  +{imp['bert_gain']:.3f}")
        lines.append("")

        stats = study_result["statistical_tests"]
        lines.append("统计显著性检验 (Full vs Pure LLM):")
        for metric_name, test_result in stats.items():
            sig = "显著 ✅" if test_result.get("significant") else "不显著"
            lines.append(f"  {metric_name}: p={test_result['p_value']:.4f} {sig}")
            if "effect_size" in test_result:
                lines.append(f"    Effect size: {test_result['effect_size']} ({test_result.get('effect_label', '?')})")

        return "\n".join(lines)
