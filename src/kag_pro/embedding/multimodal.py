"""Multimodal visual embedding and image understanding for KAG-Pro.

支持多种多模态视觉模型：
- CLIP: OpenAI 的对比学习图像 - 文本嵌入模型
- Qwen-VL: 通义千问视觉语言模型（通过 DashScope API）
- 本地 CLIP 模型：使用 sentence-transformers 的 CLIP 变体

主要功能：
1. 图像特征提取与向量化
2. 图像描述生成
3. 图文混合检索
4. 教育场景图像理解（数学图表、科学实验等）
"""

import base64
import io
from pathlib import Path
from typing import Protocol

try:
    import torch
    from PIL import Image
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import clip
    CLIP_AVAILABLE = True
except ImportError:
    CLIP_AVAILABLE = False

DASHSCOPE_AVAILABLE = True  # Will check at runtime


class ImageEmbedderPort(Protocol):
    """图像嵌入器的协议接口。"""

    def embed_image(self, image_path: str) -> list[float]:
        """将图像转换为向量表示。"""
        ...

    def embed_text(self, text: str) -> list[float]:
        """将文本转换为向量表示（用于跨模态检索）。"""
        ...

    def embed_batch(self, images: list[str]) -> list[list[float]]:
        """批量处理图像嵌入。"""
        ...


class MultimodalImageEmbedder:
    """多模态图像嵌入器，支持 CLIP 和 Qwen-VL 等多种模型。"""

    def __init__(
        self,
        model_type: str = "clip",
        device: str | None = None,
        api_key: str | None = None,
        **kwargs,
    ):
        """
        Args:
            model_type: 模型类型，可选 "clip"、"qwen-vl"
            device: 计算设备，"cpu" 或 "cuda"
            api_key: DashScope API key（仅用于 qwen-vl）
            **kwargs: 其他参数
        """
        if not TORCH_AVAILABLE:
            raise ImportError("torch is required for multimodal embedding")

        self.model_type = model_type
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.api_key = api_key  # Store for Qwen-VL API calls
        self.model = None
        self.preprocessor = None

        if model_type == "clip":
            self._init_clip(**kwargs)
        elif model_type == "qwen-vl":
            if not DASHSCOPE_AVAILABLE:
                raise ImportError("dashscope is required for qwen-vl")
            # Qwen-VL 通过 API 调用，无需本地模型加载
        else:
            raise ValueError(f"Unknown model_type: {model_type}")

    def _init_clip(self, model_name: str = "ViT-B/32"):
        """初始化 CLIP 模型。"""
        if not CLIP_AVAILABLE:
            raise ImportError("clip is required. Install with: pip install kag-pro[clip-embed]")

        print(f"Loading CLIP model: {model_name}...")
        self.model, self.preprocessor = clip.load(model_name, device=self.device, jit=False)
        self.model.eval()
        print(f"CLIP model loaded on {self.device}")

    def embed_image(self, image_path: str) -> list[float]:
        """将图像转换为向量表示。"""
        image = Image.open(image_path).convert("RGB")
        return self._embed_image_pil(image)

    def embed_image_from_base64(self, base64_str: str) -> list[float]:
        """从 base64 字符串加载并嵌入图像。"""
        image_data = base64.b64decode(base64_str)
        image = Image.open(io.BytesIO(image_data)).convert("RGB")
        return self._embed_image_pil(image)

    def _embed_image_pil(self, image: Image.Image) -> list[float]:
        """从 PIL Image 对象嵌入图像。"""
        if self.model_type == "clip":
            return self._clip_embed_image(image)
        elif self.model_type == "qwen-vl":
            return self._qwen_vl_embed_image(image)
        else:
            raise ValueError(f"Unsupported model type: {self.model_type}")

    def _clip_embed_image(self, image: Image.Image) -> list[float]:
        """使用 CLIP 嵌入图像。"""
        with torch.no_grad():
            image_features = self.model.encode_image(self.preprocessor(image).unsqueeze(0).to(self.device))
            features = image_features.squeeze().cpu().numpy().tolist()
            return features

    def _qwen_vl_embed_image(self, image: Image.Image) -> list[float]:
        """使用 Qwen-VL 获取图像特征（简化版，实际应调用 LLM 生成描述后再嵌入）。"""
        # Qwen-VL 主要通过自然语言交互，这里先生成图像描述，再返回空向量占位
        # 完整实现应在 pipeline 层调用 LLM 生成描述，然后使用文本嵌入器
        return [0.0] * 768  # placeholder

    def embed_text(self, text: str) -> list[float]:
        """嵌入文本（仅 CLIP 支持）。"""
        if self.model_type != "clip":
            raise NotImplementedError("Text embedding only supported for CLIP")

        if not CLIP_AVAILABLE:
            raise ImportError("clip is required for text embedding")

        with torch.no_grad():
            text_tokens = clip.tokenize([text]).to(self.device)
            text_features = self.model.encode_text(text_tokens)
            features = text_features.squeeze().cpu().numpy().tolist()
            return features

    def embed_batch(self, images: list[str]) -> list[list[float]]:
        """批量嵌入图像。"""
        return [self.embed_image(img) for img in images]

    def get_description(self, image_path: str, prompt: str = "请详细描述这张图片的内容，包括其中的文字、公式、图表等信息。") -> str:
        """为图像生成描述（使用 Qwen-VL）。"""
        if self.model_type != "qwen-vl":
            raise NotImplementedError("Description generation only supported for Qwen-VL")

        return self._qwen_vl_generate_description(image_path, prompt)

    def _qwen_vl_generate_description(self, image_path: str, prompt: str) -> str:
        """使用 Qwen-VL 生成图像描述。"""
        try:
            # 设置 API Key
            import dashscope
            from dashscope import MultiModalConversation
            api_key = self.api_key or dashscope.api_key
            if not api_key:
                raise ValueError("DashScope API key not set")

            messages = [
                {
                    'role': 'user',
                    'content': [
                        {'image': image_path},
                        {'text': prompt}
                    ]
                }
            ]

            response = MultiModalConversation.call(
                model='qwen-vl-max',
                messages=messages
            )

            if response.status_code == 200:
                return response.choices[0].message.content[0]['text']
            else:
                return f"Error: {response.code}: {response.message}"

        except Exception as e:
            return f"Failed to generate description: {str(e)}"


class MultimodalRetriever:
    """多模态检索器，支持图像 - 文本混合查询。"""

    def __init__(self, embedder: MultimodalImageEmbedder, vector_store):
        """
        Args:
            embedder: 多模态嵌入器实例
            vector_store: ChromaDB 向量存储实例
        """
        self.embedder = embedder
        self.vector_store = vector_store
        self._image_collection = None

    @property
    def image_collection(self):
        """获取或创建图像向量集合。"""
        if self._image_collection is None:
            self._image_collection = self.vector_store.get_collection("images")
        return self._image_collection

    def add_image(
        self,
        image_path: str,
        metadata: dict | None = None,
        description: str = "",
    ):
        """添加图像到向量数据库。"""
        embeddings = self.embedder.embed_image(image_path)

        doc_metadata = metadata or {}
        doc_metadata["type"] = "image"
        doc_metadata["description"] = description
        doc_metadata["image_path"] = image_path

        self.image_collection.add(
            ids=[Path(image_path).stem],
            embeddings=[embeddings],
            metadatas=[doc_metadata],
        )

    def search(
        self,
        query: str | Image.Image,
        top_k: int = 5,
        threshold: float = 0.3,
    ) -> list[dict]:
        """
        搜索相似图像。query 可以是文本或图像。

        Args:
            query: 文本查询或 PIL Image 对象
            top_k: 返回结果数量
            threshold: 相似度阈值

        Returns:
            搜索结果列表，包含图像路径、元数据和相似度分数
        """
        if isinstance(query, str):
            # 文本查询 -> 文本嵌入
            query_vector = self.embedder.embed_text(query)
        elif isinstance(query, Image.Image):
            # 图像查询 -> 图像嵌入
            query_vector = self.embedder._clip_embed_image(query)
        else:
            raise ValueError("Query must be a string (text) or PIL Image")

        results = self.image_collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where={"type": {"$eq": "image"}},
        )

        if not results["metadatas"] or not results["metadatas"][0]:
            return []

        formatted = []
        for i, meta in enumerate(results["metadatas"][0]):
            formatted.append({
                "image_path": meta.get("image_path", ""),
                "description": meta.get("description", ""),
                "score": results["distances"][0][i] if results["distances"] else 0.0,
                "metadata": meta,
            })

        return formatted


# ========== 辅助函数 ==========

def encode_image_to_base64(image_path: str) -> str:
    """将图像编码为 base64 字符串。"""
    image = Image.open(image_path).convert("RGB")
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def create_multimodal_embedder(
    model_type: str = "clip",
    model_name: str = "ViT-B/32",
    use_api: bool = False,
) -> MultimodalImageEmbedder:
    """工厂函数：创建多模态嵌入器。

    Args:
        model_type: "clip" 或 "qwen-vl"
        model_name: 模型名称（CLIP 使用）
        use_api: 是否使用 API（Qwen-VL 需要）

    Returns:
        配置好的嵌入器实例
    """
    if model_type == "qwen-vl":
        if not use_api:
            raise ValueError("Qwen-VL requires API mode")
        return MultimodalImageEmbedder(
            model_type="qwen-vl",
            device="cpu",  # Qwen-VL 通过 API 调用，不使用本地设备
        )
    else:
        return MultimodalImageEmbedder(
            model_type="clip",
            model_name=model_name,
        )
