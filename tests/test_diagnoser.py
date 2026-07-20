"""Tests for ErrorDiagnoser (integration with vector store)."""

import tempfile
from pathlib import Path

from kag_pro.core.vector_store import VectorStore
from kag_pro.core.loader import Document
from kag_pro.diagnosis.diagnoser import ErrorDiagnoser


class TestErrorDiagnoser:

    def test_diagnose_returns_all_fields(self):
        # Setup: create a minimal vector store with math content
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(persist_dir=tmpdir)
            doc = Document(
                text="一元二次方程的求根公式：x = (-b ± √(b²-4ac)) / 2a。当判别式大于0时有两个不相等的实数根。",
                metadata={"source": "algebra.txt"},
            )
            store.add_documents([doc])

            diagnoser = ErrorDiagnoser(vector_store=store)
            result = diagnoser.diagnose(
                question="解方程 x² - 4 = 0",
                student_answer="x=2",
                correct_answer="x=2 或 x=-2",
            )

            assert "error_type" in result
            assert "knowledge_point" in result
            assert "hint" in result
            assert "personalized_feedback" in result

    def test_diagnose_with_empty_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(persist_dir=tmpdir)
            diagnoser = ErrorDiagnoser(vector_store=store)
            result = diagnoser.diagnose(
                question="1+1=?",
                student_answer="3",
                correct_answer="2",
            )
            assert result["error_type"] is not None
            assert len(result["personalized_feedback"]) > 0
