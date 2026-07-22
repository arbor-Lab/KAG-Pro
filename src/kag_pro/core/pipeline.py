"""Legacy pipeline module — now delegates to EducationOrchestrator.

This file is kept as a thin compatibility layer during the transition.
New code should use kag_pro.orchestration.EducationOrchestrator directly.
"""

from kag_pro.core.bootstrap import create_default_registry
from kag_pro.orchestration.orchestrator import EducationOrchestrator


class RAGPipeline:
    """Backward-compatible wrapper around EducationOrchestrator.

    Delegates all calls to the new event-driven orchestrator.
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        persist_dir: str | None = None,
        use_kg: bool = False,
    ):
        registry = create_default_registry(
            use_kg=use_kg,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            persist_dir=persist_dir,
        )
        self._orchestrator = EducationOrchestrator(registry)

    def index_documents(self, directory):
        return self._orchestrator.index_documents(directory)

    def query(self, question: str, verify: bool = False) -> dict:
        result = self._orchestrator.query(question, verify=verify)
        return result.to_dict()

    def diagnose(self, question: str, student_answer: str, correct_answer: str, stage: str | None = None) -> dict:
        result = self._orchestrator.diagnose(question, student_answer, correct_answer, stage=stage)
        return result.to_dict()

    def exercises(self, question: str, student_answer: str, correct_answer: str) -> dict:
        return self._orchestrator.exercises(question, student_answer, correct_answer)

    def evaluate(self, test_data: list) -> dict:
        return self._orchestrator.evaluate(test_data)

    def recommend_exercises(self, count: int = 3) -> dict:
        return self._orchestrator.recommend(count=count)

    @property
    def document_count(self) -> int:
        return self._orchestrator.document_count

    def clear_index(self) -> None:
        self._orchestrator.clear_index()
