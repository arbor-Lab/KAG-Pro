"""Protocol interface definitions for all pluggable components.

Using typing.Protocol for structural subtyping — existing modules
automatically satisfy these interfaces without inheriting from them.
"""

from typing import Protocol, runtime_checkable

from kag_pro.core.types import DiagnosisResult, Document

# === RAG Interfaces ===

@runtime_checkable
class DocumentLoaderPort(Protocol):
    def load(self, directory: str) -> list[Document]: ...


@runtime_checkable
class TextSplitterPort(Protocol):
    def split(self, documents: list[Document]) -> list[Document]: ...


@runtime_checkable
class EmbedderPort(Protocol):
    def embed(self, text: str) -> list[float]: ...
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dimensions(self) -> int | None: ...


@runtime_checkable
class VectorStorePort(Protocol):
    def add_documents(self, documents: list[Document]) -> None: ...
    def search(
        self,
        query: str,
        top_k: int,
        threshold: float,
        stage_filter: str | None,
        subject_filter: str | None,
    ) -> list[dict]: ...
    def count(self) -> int: ...
    def clear(self) -> None: ...


@runtime_checkable
class RetrieverPort(Protocol):
    def retrieve(
        self, query: str, stage: str | None, subject: str | None
    ) -> list[dict]: ...


@runtime_checkable
class GeneratorPort(Protocol):
    def generate(self, question: str, context_chunks: list[dict]) -> str: ...
    def call(
        self, system: str, user: str, temperature: float, max_tokens: int
    ) -> str: ...


@runtime_checkable
class VerifierPort(Protocol):
    def verify(self, question: str, answer: str) -> dict: ...


# === Knowledge Graph Interfaces ===

@runtime_checkable
class KnowledgeGraphPort(Protocol):
    def add_entity(
        self, entity_id: str, name: str, entity_type: str, metadata: dict | None
    ) -> None: ...
    def add_relation(self, source: str, relation: str, target: str) -> None: ...
    def get_prerequisites(self, entity_id: str) -> list[dict]: ...
    def get_common_mistakes(self, entity_id: str) -> list[dict]: ...
    def get_neighbors(self, entity_id: str, depth: int) -> list[dict]: ...
    def search_entities(self, query: str) -> list[dict]: ...


@runtime_checkable
class KGRetrieverPort(Protocol):
    def retrieve(self, query: str, top_k: int, threshold: float) -> list[dict]: ...
    def get_enrichment(self, query: str) -> dict: ...


# === Diagnosis Interfaces ===

@runtime_checkable
class StageDetectorPort(Protocol):
    def detect(self, question: str) -> str: ...
    def analyze(self, question: str) -> dict: ...


@runtime_checkable
class ErrorClassifierPort(Protocol):
    def classify(
        self, question: str, student_answer: str, correct_answer: str
    ) -> dict: ...


@runtime_checkable
class DiagnoserPort(Protocol):
    def diagnose(
        self,
        question: str,
        student_answer: str,
        correct_answer: str,
        stage: str | None,
    ) -> DiagnosisResult: ...
    def generate_exercises(
        self, knowledge_point: str, error_type: str, count: int
    ) -> str: ...


@runtime_checkable
class RecommenderPort(Protocol):
    def recommend(self, error_history: list[dict], count: int) -> dict: ...


@runtime_checkable
class KnowledgeTracerPort(Protocol):
    def update(self, knowledge_point: str, correct: bool) -> dict: ...
    def predict(self, knowledge_point: str) -> float: ...
    def get_mastery(self, knowledge_point: str) -> str: ...
    def get_weakest(self, n: int) -> list[tuple[str, float]]: ...


# === Paper & Evaluation Interfaces ===

@runtime_checkable
class PaperGeneratorPort(Protocol):
    def generate(
        self,
        stage: str,
        subject: str,
        topics: list[str],
        count: int,
        difficulty: str,
        question_types: list[dict] | None,
    ) -> dict: ...


@runtime_checkable
class EvaluatorPort(Protocol):
    def evaluate(
        self,
        question: str,
        generated: str,
        reference: str,
        sources: list[dict] | None,
    ) -> dict: ...
    def evaluate_batch(self, test_data: list[dict]) -> dict: ...
