"""End-to-end tests for RAGPipeline."""

import os
import tempfile
from pathlib import Path

import pytest

from kag_pro.core.pipeline import RAGPipeline


class TestRAGPipeline:

    @pytest.fixture
    def sample_data_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_math.txt"
            filepath.write_text(
                "小学数学 - 分数初步\n\n"
                "分数的意义：把单位1平均分成若干份，\n"
                "表示这样的一份或几份的数，叫做分数。\n"
                "例如1/2表示把整体平均分成2份取1份。\n"
            )
            yield tmpdir

    @pytest.fixture
    def temp_persist_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set",
    )
    def test_index_and_query(self, sample_data_dir, temp_persist_dir):
        pipeline = RAGPipeline(persist_dir=temp_persist_dir)
        chunks = pipeline.index_documents(sample_data_dir)
        assert len(chunks) > 0
        assert pipeline.document_count > 0
        result = pipeline.query("什么是分数？")
        assert result["question"] == "什么是分数？"
        assert len(result["answer"]) > 0

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set",
    )
    def test_answer_contains_key_knowledge(self, sample_data_dir, temp_persist_dir):
        pipeline = RAGPipeline(persist_dir=temp_persist_dir)
        pipeline.index_documents(sample_data_dir)
        result = pipeline.query("什么是分数？")
        assert "分数" in result["answer"]

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set",
    )
    def test_clear_index(self, sample_data_dir, temp_persist_dir):
        pipeline = RAGPipeline(persist_dir=temp_persist_dir)
        pipeline.index_documents(sample_data_dir)
        assert pipeline.document_count > 0
        pipeline.clear_index()
        assert pipeline.document_count == 0

    def test_index_empty_directory(self, temp_persist_dir):
        with tempfile.TemporaryDirectory() as empty_dir:
            pipeline = RAGPipeline(persist_dir=temp_persist_dir)
            chunks = pipeline.index_documents(empty_dir)
            assert chunks == []
            assert pipeline.document_count == 0
