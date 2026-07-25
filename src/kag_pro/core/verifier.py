"""Factual consistency verification — check if generated answer is supported by knowledge base.

Two judge modes:
- "llm": LLM-as-judge entailment per claim (支持/中立/矛盾 three-way), using
  the top retrieved evidence. Similarity alone cannot detect contradiction.
- "heuristic": original vector-similarity threshold fallback.
"""

from kag_pro.core.embedder import Embedder
from kag_pro.core.vector_store import VectorStore
from kag_pro.utils.config import get_config

_JUDGE_SYSTEM = (
    "你是事实一致性判定器。根据给定的教材证据判断论断是否成立，"
    "只输出三个词之一：支持、中立、矛盾。不要输出任何其他内容。"
)

_JUDGE_PROMPT_TEMPLATE = """\
论断：{claim}

教材证据：{evidence}

请判断：教材证据是否支持该论断？只回答：支持、中立 或 矛盾。\
"""


class FactualVerifier:
    """Verify whether LLM-generated claims are supported by the knowledge base."""

    def __init__(
        self,
        vector_store: VectorStore,
        threshold: float = 0.4,
        generator=None,
        judge_mode: str | None = None,
    ):
        config = get_config()
        self._store = vector_store
        self._embedder = Embedder()
        self._threshold = threshold
        self._generator = generator
        self._judge_mode = judge_mode or config["verifier_judge_mode"]

    def verify(self, question: str, answer: str) -> dict:
        """Verify an answer against the knowledge base.

        Returns: dict with supported, unsupported, contradicted lists,
        faith_score, verdict, judge_mode and details.
        """
        claims = self._extract_claims(answer)
        if not claims:
            return {
                "supported": [], "unsupported": [], "contradicted": [],
                "faith_score": 1.0, "verdict": "HIGH",
                "judge_mode": self._judge_mode, "details": "No claims to verify",
            }

        supported: list[dict] = []
        unsupported: list[dict] = []  # neutral — no evidence found
        contradicted: list[dict] = []  # evidence actively disagrees

        for claim in claims:
            label, evidence = self._check_claim(claim)
            entry = {"claim": claim}
            if evidence:
                entry["evidence"] = evidence
            if label == "supported":
                supported.append(entry)
            elif label == "contradicted":
                contradicted.append(entry)
            else:
                unsupported.append(entry)

        total = len(claims)
        raw = (len(supported) + 0.5 * len(unsupported)) / total
        # Contradictions are worse than missing evidence — penalize harder
        faith_score = max(0.0, min(1.0, raw - 0.2 * len(contradicted)))
        faith_score = round(faith_score, 3)

        verdict = "HIGH" if faith_score >= 0.8 else ("MEDIUM" if faith_score >= 0.5 else "LOW")

        return {
            "supported": supported,
            "unsupported": unsupported,
            "contradicted": contradicted,
            "faith_score": faith_score,
            "verdict": verdict,
            "judge_mode": self._judge_mode if self._generator else "heuristic",
            "total_claims": total,
            "details": (
                f"{len(supported)}/{total} supported, "
                f"{len(unsupported)} neutral, {len(contradicted)} contradicted"
            ),
        }

    def _extract_claims(self, text: str) -> list[str]:
        """Extract factual claims from answer text by splitting on sentences."""
        for sep in ["。", "！", "？", "；", "\n"]:
            text = text.replace(sep, "|||")
        parts = [p.strip() for p in text.split("|||") if p.strip()]
        # Filter: keep sentences with factual content (>10 chars)
        claims = []
        for p in parts:
            if len(p) > 10:
                claims.append(p)
        return claims[:8]  # Limit to avoid excessive API calls

    def _check_claim(self, claim: str) -> tuple[str, str]:
        """Classify one claim as supported / neutral / contradicted."""
        hits = self._store.search(query=claim, top_k=3, threshold=self._threshold)
        if not hits:
            return "neutral", ""

        best = hits[0]
        if self._generator is None or self._judge_mode != "llm":
            # Heuristic fallback: strong vector similarity counts as support
            if best["score"] >= self._threshold:
                return "supported", best["text"][:150]
            return "neutral", ""

        return self._llm_judge(claim, best)

    def _llm_judge(self, claim: str, best_hit: dict) -> tuple[str, str]:
        """LLM-as-judge entailment: 支持 / 中立 / 矛盾 against top evidence."""
        evidence = best_hit["text"][:300]
        try:
            raw = self._generator.call(
                system=_JUDGE_SYSTEM,
                user=_JUDGE_PROMPT_TEMPLATE.format(claim=claim, evidence=evidence),
                temperature=0.0,
                max_tokens=10,
            )
        except Exception:
            # Judge failure must not break verification — degrade to heuristic
            if best_hit["score"] >= self._threshold:
                return "supported", best_hit["text"][:150]
            return "neutral", ""
        if "矛盾" in raw:
            return "contradicted", evidence[:150]
        if "支持" in raw:
            return "supported", evidence[:150]
        return "neutral", evidence[:150]
