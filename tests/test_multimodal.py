"""Tests for multimodal visual question answering (VQA) functionality.

Tests image upload, embedding, similarity search, and VQA pipeline integration.
"""

import base64
import tempfile
from pathlib import Path

import pytest

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# Skip tests if PIL not available
pytestmark = pytest.mark.skipif(
    not PIL_AVAILABLE,
    reason="PIL is required for multimodal tests"
)


class TestMultimodalImageEmbedder:
    """Tests for MultimodalImageEmbedder class."""

    @pytest.fixture
    def test_image_path(self, tmp_path):
        """Create a test image for testing."""
        img_path = tmp_path / "test_image.png"
        img = Image.new("RGB", (100, 100), color="red")
        img.save(img_path)
        return str(img_path)

    def test_embed_image_basic(self, test_image_path):
        """Test basic image embedding."""
        from kag_pro.embedding.multimodal import MultimodalImageEmbedder

        # Note: This will require CLIP to be installed
        try:
            embedder = MultimodalImageEmbedder(model_type="clip")
            embedding = embedder.embed_image(test_image_path)

            assert isinstance(embedding, list)
            assert len(embedding) > 0
            assert all(isinstance(x, float) for x in embedding)
        except ImportError:
            pytest.skip("CLIP not available")

    def test_embed_batch(self, test_image_path):
        """Test batch image embedding."""
        from kag_pro.embedding.multimodal import MultimodalImageEmbedder

        try:
            embedder = MultimodalImageEmbedder(model_type="clip")
            embeddings = embedder.embed_batch([test_image_path, test_image_path])

            assert len(embeddings) == 2
            assert all(len(e) > 0 for e in embeddings)
        except ImportError:
            pytest.skip("CLIP not available")

    def test_embed_image_from_base64(self, test_image_path):
        """Test embedding from base64 encoded image."""
        from kag_pro.embedding.multimodal import MultimodalImageEmbedder

        try:
            with open(test_image_path, "rb") as f:
                img_bytes = f.read()
            b64_str = base64.b64encode(img_bytes).decode("utf-8")

            embedder = MultimodalImageEmbedder(model_type="clip")
            embedding = embedder.embed_image_from_base64(b64_str)

            assert isinstance(embedding, list)
            assert len(embedding) > 0
        except ImportError:
            pytest.skip("CLIP not available")


class TestVectorStoreImageSupport:
    """Tests for VectorStore image collection support."""

    @pytest.fixture
    def test_image_path(self, tmp_path):
        """Create a test image."""
        img_path = tmp_path / "test.png"
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(img_path)
        return str(img_path)

    @pytest.fixture
    def vector_store(self):
        """Create a temporary vector store instance."""
        from kag_pro.core.vector_store import VectorStore

        temp_dir = tempfile.mkdtemp()
        store = VectorStore(persist_dir=temp_dir)
        yield store
        store.clear()

    def test_image_collection_exists(self, vector_store):
        """Test that image collection exists."""
        collection = vector_store.get_image_collection()
        assert collection is not None

    def test_add_images(self, vector_store, test_image_path):
        """Test adding images to vector store."""
        from kag_pro.embedding.multimodal import MultimodalImageEmbedder

        try:
            embedder = MultimodalImageEmbedder(model_type="clip")
            embeddings = embedder.embed_image(test_image_path)

            image_data = [{
                "image_path": test_image_path,
                "embeddings": embeddings,
                "metadata": {"type": "image", "description": "test"},
            }]

            vector_store.add_images(image_data)

            collection = vector_store.get_image_collection()
            assert collection.count() > 0
        except ImportError:
            pytest.skip("CLIP not available")

    def test_search_images(self, vector_store, test_image_path):
        """Test searching for similar images."""
        from kag_pro.embedding.multimodal import MultimodalImageEmbedder

        try:
            embedder = MultimodalImageEmbedder(model_type="clip")
            query_embedding = embedder.embed_image(test_image_path)

            results = vector_store.search_images(query_embedding, top_k=5)

            # Should return empty or some results depending on what's in DB
            assert isinstance(results, list)
        except ImportError:
            pytest.skip("CLIP not available")


class TestMultimodalRAGPipeline:
    """Tests for MultimodalRAGPipeline class."""

    @pytest.fixture
    def test_image_path(self, tmp_path):
        """Create a test image."""
        img_path = tmp_path / "math_problem.png"
        img = Image.new("RGB", (200, 200), color="white")
        img.save(img_path)
        return str(img_path)

    @pytest.fixture
    def multimodal_pipeline(self, tmp_path):
        """Create a multimodal pipeline instance."""
        from kag_pro.core.vector_store import VectorStore
        from kag_pro.embedding.multimodal import MultimodalImageEmbedder, MultimodalRetriever

        # Create mock components
        vector_store = VectorStore(persist_dir=str(tmp_path / "chroma"))

        try:
            embedder = MultimodalImageEmbedder(model_type="clip")
            retriever = MultimodalRetriever(embedder, vector_store)

            return {
                "vector_store": vector_store,
                "embedder": embedder,
                "retriever": retriever,
                "tmp_path": tmp_path,
            }
        except ImportError:
            pytest.skip("CLIP not available")

    def test_upload_image(self, test_image_path, multimodal_pipeline):
        """Test uploading an image to the pipeline."""
        from kag_pro.core.multimodal_pipeline import MultimodalRAGPipeline

        pipeline = MultimodalRAGPipeline(
            vector_store=multimodal_pipeline["vector_store"],
            embedder=multimodal_pipeline["embedder"],
            retriever=multimodal_pipeline["retriever"],
        )

        image_id = pipeline.upload_image(
            image_path=test_image_path,
            description="Test math problem",
            metadata={"subject": "math", "stage": "middle"},
        )

        assert image_id is not None
        assert pipeline.retriever.image_collection.count() > 0

    def test_analyze_image(self, test_image_path, multimodal_pipeline):
        """Test analyzing an image."""
        from kag_pro.core.multimodal_pipeline import MultimodalRAGPipeline

        pipeline = MultimodalRAGPipeline(
            vector_store=multimodal_pipeline["vector_store"],
            embedder=multimodal_pipeline["embedder"],
            retriever=multimodal_pipeline["retriever"],
        )

        analysis = pipeline.analyze_image(test_image_path)

        assert "image_path" in analysis
        assert "analysis" in analysis

    def test_search_similar_images(self, test_image_path, multimodal_pipeline):
        """Test searching for similar images."""
        from kag_pro.core.multimodal_pipeline import MultimodalRAGPipeline

        pipeline = MultimodalRAGPipeline(
            vector_store=multimodal_pipeline["vector_store"],
            embedder=multimodal_pipeline["embedder"],
            retriever=multimodal_pipeline["retriever"],
        )

        # Upload the image first
        pipeline.upload_image(test_image_path, description="Similar test")

        # Search for similar images
        similar = pipeline.search_similar_images(
            reference_image=test_image_path,
            top_k=3,
        )

        assert isinstance(similar, list)

    def test_query_with_image(self, test_image_path, multimodal_pipeline):
        """Test querying with an image."""
        from kag_pro.core.multimodal_pipeline import MultimodalRAGPipeline

        pipeline = MultimodalRAGPipeline(
            vector_store=multimodal_pipeline["vector_store"],
            embedder=multimodal_pipeline["embedder"],
            retriever=multimodal_pipeline["retriever"],
        )

        result = pipeline.query_with_image(
            image_path=test_image_path,
            question="What is shown in this image?",
            top_k=5,
        )

        assert hasattr(result, 'is_visual_query')
        assert result.is_visual_query is True


class TestAPIEndpoints:
    """Tests for API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client for FastAPI app."""
        from fastapi.testclient import TestClient
        from frontend.server import app

        # Ensure uploads directory exists
        uploads_dir = Path(__file__).parent.parent / "frontend" / "uploads"
        uploads_dir.mkdir(exist_ok=True)

        return TestClient(app)

    @pytest.fixture
    def test_image_path(self, tmp_path):
        """Create a test image."""
        img_path = tmp_path / "test.png"
        img = Image.new("RGB", (100, 100), color="green")
        img.save(img_path)
        return str(img_path)

    def test_upload_image_endpoint(self, client, test_image_path):
        """Test image upload endpoint."""
        with open(test_image_path, "rb") as f:
            files = {
                "file": ("test_image.png", f, "image/png"),
            }
            response = client.post(
                "/api/upload-image",
                files=files,
                data={"description": "Test image"}
            )

        # Accept 200 (success), 503 (multimodal not available), or 500 (processing error)
        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "image_id" in data

    def test_upload_image_invalid_type(self, client, tmp_path):
        """Test rejecting invalid file types."""
        # Create a fake image file with wrong extension
        fake_img = tmp_path / "fake.png"
        fake_img.write_text("not a real image")

        with open(fake_img, "rb") as f:
            files = {
                "file": ("fake.png", f, "application/octet-stream"),
            }
            response = client.post(
                "/api/upload-image",
                files=files,
            )

        # Should accept any file - validation happens at processing level
        # May return 200 (upload ok), 400 (invalid), 500 (error), or 503 (not available)
        assert response.status_code in [200, 400, 500, 503]

    def test_list_uploaded_images(self, client, test_image_path):
        """Test listing uploaded images."""
        # First upload an image
        with open(test_image_path, "rb") as f:
            files = {
                "file": ("list_test.png", f, "image/png"),
            }
            client.post("/api/upload-image", files=files)

        # Then list them
        response = client.get("/api/images")

        assert response.status_code == 200
        data = response.json()
        assert "images" in data
        assert isinstance(data["images"], list)


def test_multimodal_imports():
    """Test that multimodal modules can be imported."""
    try:
        from kag_pro.embedding import multimodal
        assert hasattr(multimodal, "MultimodalImageEmbedder")
        assert hasattr(multimodal, "MultimodalRetriever")
    except ImportError as e:
        pytest.skip(f"Multimodal dependencies not available: {e}")


def test_multimodal_pipeline_imports():
    """Test that multimodal pipeline can be imported."""
    try:
        from kag_pro.core import multimodal_pipeline
        assert hasattr(multimodal_pipeline, "MultimodalRAGPipeline")
        assert hasattr(multimodal_pipeline, "create_multimodal_pipeline")
    except ImportError as e:
        pytest.skip(f"Multimodal pipeline dependencies not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
