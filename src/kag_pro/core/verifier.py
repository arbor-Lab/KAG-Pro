"""Factual consistency verification — check if generated answer is supported by knowledge base."""


from kag_pro.core.embedder import Embedder
from kag_pro.core.vector_store import VectorStore


class FactualVerifier:
    """Verify whether LLM-generated claims are supported by the knowledge base."""

    def __init__(self, vector_store: VectorStore, threshold: float = 0.4):
        self._store = vector_store
        self._embedder = Embedder()
        self._threshold = threshold

    def verify(self, question: str, answer: str) -> dict:
        """Verify an answer against the knowledge base.

        Returns: dict with supported_claims, unsupported_claims, faith_score, details.
        """
        claims = self._extract_claims(answer)
        if not claims:
            return {"supported": [], "unsupported": [], "faith_score": 1.0, "details": "No claims to verify"}

        supported = []
        unsupported = []

        for claim in claims:
            is_supported, evidence = self._check_claim(claim)
            if is_supported:
                supported.append({"claim": claim, "evidence": evidence})
            else:
                unsupported.append({"claim": claim})

        faith_score = len(supported) / len(claims) if claims else 1.0
        faith_score = round(faith_score, 3)

        verdict = "HIGH" if faith_score >= 0.8 else ("MEDIUM" if faith_score >= 0.5 else "LOW")

        return {
            "supported": supported,
            "unsupported": unsupported,
            "faith_score": faith_score,
            "verdict": verdict,
            "total_claims": len(claims),
            "details": f"{len(supported)}/{len(claims)} claims supported by knowledge base",
        }

    def _extract_claims(self, text: str) -> list[str]:
        """Extract factual claims from answer text by splitting on sentences."""
        for sep in ["。", "！", "？", "；", "\n"]:
            text = text.replace(sep, "|||")
        parts = [p.strip() for p in text.split("|||") if p.strip()]
        # Filter: keep sentences with factual content (>10 chars, contains numbers or key terms)
        claims = []
        for p in parts:
            if len(p) > 10:
                claims.append(p)
        return claims[:8]  # Limit to avoid excessive API calls

    def _check_claim(self, claim: str) -> tuple[bool, str]:
        """Check if a single claim is supported by the knowledge base."""
        hits = self._store.search(query=claim, top_k=3, threshold=self._threshold)
        if not hits:
            return False, ""

        # Simple heuristic: if top hit is strongly relevant, claim is supported
        best = hits[0]
        if best["score"] >= self._threshold:
            return True, best["text"][:150]
        return False, ""
