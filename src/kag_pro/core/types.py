"""Shared data types for the KAG-Pro plugin architecture.

These dataclasses replace ad-hoc dict passing between modules,
providing type-safe contracts for inter-plugin communication.
"""

from dataclasses import dataclass, field


@dataclass
class Document:
    """A single document with text content and metadata."""

    text: str
    metadata: dict = field(default_factory=dict)

    def __repr__(self) -> str:
        src = self.metadata.get("source", "unknown")
        return f"Document(source={src!r}, chars={len(self.text)})"


@dataclass
class RetrievalHit:
    """A single retrieval result from vector search or KG-enhanced search."""

    text: str
    metadata: dict
    score: float
    vector_score: float | None = None
    graph_score: float | None = None


@dataclass
class QueryContext:
    """Intermediate context built during query processing."""

    question: str
    stage: str = ""
    subject: str = ""
    analysis: dict = field(default_factory=dict)
    hits: list[dict] = field(default_factory=list)
    enrichment: dict = field(default_factory=dict)


@dataclass
class QueryResult:
    """Final result of a query operation."""

    question: str
    answer: str
    stage: str
    sources: list[dict]
    analysis: dict = field(default_factory=dict)
    kg_enrichment: dict = field(default_factory=dict)
    verification: dict | None = None
    clarification: bool = False
    cache_hit: bool = False

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "answer": self.answer,
            "stage": self.stage,
            "sources": self.sources,
            "analysis": self.analysis,
            "kg_enrichment": self.kg_enrichment,
            "verification": self.verification,
            "clarification": self.clarification,
            "cache_hit": self.cache_hit,
        }


@dataclass
class DiagnosisResult:
    """Result of an error diagnosis operation."""

    error_type: str
    confidence: float
    knowledge_point: str
    hint: str
    remedial_content: str
    personalized_feedback: str
    stage: str = ""
    exercises: dict | None = None

    def to_dict(self) -> dict:
        return {
            "error_type": self.error_type,
            "confidence": self.confidence,
            "knowledge_point": self.knowledge_point,
            "hint": self.hint,
            "remedial_content": self.remedial_content,
            "personalized_feedback": self.personalized_feedback,
            "stage": self.stage,
            "exercises": self.exercises,
        }
