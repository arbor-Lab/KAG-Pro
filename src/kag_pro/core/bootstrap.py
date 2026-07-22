"""Default bootstrap — assembles the PluginRegistry with standard modules.

This replaces the manual wiring that was previously done in RAGPipeline.__init__.
All modules are registered as lazy factories (singletons) so they are only
created when first resolved.
"""

from kag_pro.core.registry import PluginRegistry


def create_default_registry(
    use_kg: bool = False,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    persist_dir: str | None = None,
) -> PluginRegistry:
    """Create and populate a registry with default module instances.

    Args:
        use_kg: if True, register KG-related services (knowledge-graph, kg-retriever, recommender)
        chunk_size: text splitter chunk size
        chunk_overlap: text splitter chunk overlap
        persist_dir: ChromaDB persistence directory (None = config default)

    Returns:
        A fully populated PluginRegistry.
    """
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
    from kag_pro.evaluation.metrics import RAGEvaluator
    from kag_pro.stage.detector import StageDetector

    registry = PluginRegistry()

    # === Shared singletons (created lazily on first resolve) ===

    registry.register("generator", lambda: Generator())

    registry.register("embedder", lambda: Embedder())

    registry.register(
        "vector-store",
        lambda: VectorStore(persist_dir=persist_dir),
    )

    registry.register(
        "text-splitter",
        lambda: ChineseTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap),
    )

    registry.register(
        "document-loader",
        lambda: DocumentLoader("."),  # directory set at call time
    )

    registry.register(
        "retriever",
        lambda: Retriever(vector_store=registry.resolve("vector-store")),
    )

    registry.register(
        "verifier",
        lambda: FactualVerifier(vector_store=registry.resolve("vector-store")),
    )

    registry.register("stage-detector", lambda: StageDetector())

    registry.register("error-classifier", lambda: ErrorClassifier())

    registry.register(
        "diagnoser",
        lambda: ErrorDiagnoser(
            vector_store=registry.resolve("vector-store"),
            generator=registry.resolve("generator"),
        ),
    )

    registry.register(
        "paper-generator",
        lambda: PaperGenerator(generator=registry.resolve("generator")),
    )

    registry.register("evaluator", lambda: RAGEvaluator())

    # === KG-dependent services (optional) ===

    if use_kg:
        from kag_pro.diagnosis.recommender import ExerciseRecommender
        from kag_pro.kg.extractor import EntityExtractor
        from kag_pro.kg.kg_retriever import KGRetriever

        registry.register(
            "knowledge-graph",
            lambda: EntityExtractor.build_default_kg(),
        )

        registry.register(
            "kg-retriever",
            lambda: KGRetriever(
                kg=registry.resolve("knowledge-graph"),
                vector_store=registry.resolve("vector-store"),
            ),
        )

        registry.register(
            "recommender",
            lambda: ExerciseRecommender(
                kg=registry.resolve("knowledge-graph"),
                vector_store=registry.resolve("vector-store"),
                generator=registry.resolve("generator"),
            ),
        )

    return registry
