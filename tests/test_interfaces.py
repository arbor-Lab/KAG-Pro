"""Verify that concrete modules satisfy their Protocol interfaces.

Uses structural (hasattr) checks at the class level for every implementation,
plus runtime_checkable isinstance checks for the cheaply-instantiable ones.
This guards against silent interface drift when refactoring modules.
"""

from kag_pro.core import interfaces as I
from kag_pro.core.embedder import Embedder
from kag_pro.core.generator import Generator
from kag_pro.core.loader import DocumentLoader
from kag_pro.core.paper_generator import PaperGenerator
from kag_pro.core.retriever import Retriever
from kag_pro.core.splitter import ChineseTextSplitter
from kag_pro.core.vector_store import VectorStore
from kag_pro.core.verifier import FactualVerifier
from kag_pro.diagnosis.classifier import ErrorClassifier
from kag_pro.diagnosis.diagnoser import ErrorDiagnoser
from kag_pro.diagnosis.knowledge_tracing import KnowledgeTracer
from kag_pro.diagnosis.recommender import ExerciseRecommender
from kag_pro.evaluation.metrics import RAGEvaluator
from kag_pro.kg.graph import KnowledgeGraph
from kag_pro.kg.kg_retriever import KGRetriever
from kag_pro.stage.detector import StageDetector

# (implementation class, protocol, [required method names])
CLASS_PROTOCOL_MAP = [
    (DocumentLoader, I.DocumentLoaderPort, ["load"]),
    (ChineseTextSplitter, I.TextSplitterPort, ["split"]),
    (Embedder, I.EmbedderPort, ["embed", "embed_batch", "dimensions"]),
    (VectorStore, I.VectorStorePort, ["add_documents", "search", "count", "clear"]),
    (Retriever, I.RetrieverPort, ["retrieve"]),
    (Generator, I.GeneratorPort, ["generate", "call"]),
    (FactualVerifier, I.VerifierPort, ["verify"]),
    (
        KnowledgeGraph,
        I.KnowledgeGraphPort,
        [
            "add_entity",
            "add_relation",
            "get_prerequisites",
            "get_common_mistakes",
            "get_neighbors",
            "search_entities",
        ],
    ),
    (KGRetriever, I.KGRetrieverPort, ["retrieve", "get_enrichment"]),
    (StageDetector, I.StageDetectorPort, ["detect", "analyze"]),
    (ErrorClassifier, I.ErrorClassifierPort, ["classify"]),
    (ErrorDiagnoser, I.DiagnoserPort, ["diagnose", "generate_exercises"]),
    (ExerciseRecommender, I.RecommenderPort, ["recommend"]),
    (
        KnowledgeTracer,
        I.KnowledgeTracerPort,
        ["update", "predict", "get_mastery", "get_weakest"],
    ),
    (PaperGenerator, I.PaperGeneratorPort, ["generate"]),
    (RAGEvaluator, I.EvaluatorPort, ["evaluate", "evaluate_batch"]),
]


class TestInterfaceConformance:

    def test_all_classes_expose_required_methods(self):
        for cls, _proto, methods in CLASS_PROTOCOL_MAP:
            for method in methods:
                assert hasattr(cls, method), (
                    f"{cls.__name__} is missing '{method}' required by its interface"
                )

    def test_cheap_classes_isinstance_runtime_checkable(self):
        """Exercise runtime_checkable isinstance on classes safe to construct."""
        assert isinstance(DocumentLoader("."), I.DocumentLoaderPort)
        assert isinstance(ChineseTextSplitter(), I.TextSplitterPort)
        assert isinstance(KnowledgeGraph(), I.KnowledgeGraphPort)
        assert isinstance(StageDetector(), I.StageDetectorPort)
        assert isinstance(ErrorClassifier(), I.ErrorClassifierPort)
        assert isinstance(KnowledgeTracer(), I.KnowledgeTracerPort)

    def test_generator_has_unified_call_entry(self):
        # The refactor added a public call() as the unified LLM entry point.
        assert hasattr(Generator, "call")

    def test_protocols_are_runtime_checkable(self):
        # A negative check: a bare object must NOT satisfy a Protocol.
        assert not isinstance(object(), I.GeneratorPort)
        assert not isinstance(object(), I.KnowledgeGraphPort)
