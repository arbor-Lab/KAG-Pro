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
        "chroma_persist_dir": os.getenv("CHROMA_PERSIST_DIR", "data/chroma_db"),
    }


def get_project_root() -> Path:
    return _project_root
