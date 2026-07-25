"""Configuration loader from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_project_root = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_project_root / ".env")


def get_config() -> dict:
    """Return a dict of all relevant configuration values."""
    return {
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "openai_base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "dashscope_api_key": os.getenv("DASHSCOPE_API_KEY", ""),
        "llm_model": os.getenv("LLM_MODEL", "gpt-4o"),
        "embedding_model": os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        "embedding_base_url": os.getenv("EMBEDDING_BASE_URL", ""),
        "embedding_api_key": os.getenv("EMBEDDING_API_KEY", ""),
        "retrieval_top_k": int(os.getenv("RETRIEVAL_TOP_K", "5")),
        "retrieval_threshold": float(os.getenv("RETRIEVAL_THRESHOLD", "0.3")),
        # Below this best-score gate, retrieval is considered too weak to
        # ground an answer — the pipeline takes the clarification path.
        "retrieval_clarify_threshold": float(os.getenv("RETRIEVAL_CLARIFY_THRESHOLD", "0.4")),
        # Hybrid retrieval: weight of vector score in the fused ranking
        # (1 - weight goes to the jieba lexical score).
        "retrieval_vector_weight": float(os.getenv("RETRIEVAL_VECTOR_WEIGHT", "0.7")),
        # Semantic answer cache: minimum query similarity for a cache hit.
        "qa_cache_similarity": float(os.getenv("QA_CACHE_SIMILARITY", "0.95")),
        # Claim-level fact checking: "llm" = LLM-as-judge entailment,
        # "heuristic" = vector-similarity threshold only.
        "verifier_judge_mode": os.getenv("VERIFIER_JUDGE_MODE", "llm"),
        # Composite confidence below this marks the answer low-confidence.
        "confidence_low_threshold": float(os.getenv("CONFIDENCE_LOW_THRESHOLD", "0.5")),
        # Majority-vote samples for objective (choice) questions.
        "self_consistency_samples": int(os.getenv("SELF_CONSISTENCY_SAMPLES", "3")),
        # JSONL sink where low-confidence samples are collected for evaluation.
        "low_confidence_log": os.getenv("LOW_CONFIDENCE_LOG", "data/low_confidence_samples.jsonl"),
        "chroma_persist_dir": os.getenv("CHROMA_PERSIST_DIR", "data/chroma_db"),
    }


def get_project_root() -> Path:
    return _project_root
