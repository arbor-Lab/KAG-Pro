"""Multimodal RAG pipeline for image-based educational queries.

支持：
1. 图像上传和预处理
2. 图像内容理解（使用 Qwen-VL 等视觉 LLM）
3. 图像特征提取和向量化存储
4. 基于图像的相似性问题检索
5. 图文混合问答
6. 教育场景优化（数学图表、科学实验、公式识别等）
"""

from pathlib import Path

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from kag_pro.core.types import QueryResult
from kag_pro.core.vector_store import VectorStore
from kag_pro.embedding.multimodal import MultimodalImageEmbedder, MultimodalRetriever


class MultimodalQueryResult(QueryResult):
    """包含图像相关信息的多模态查询结果。"""

    related_images: list[dict] = []  # 相关图像列表
    image_analysis: dict = {}  # 图像分析结果
    is_visual_query: bool = False  # 是否为图像查询


class MultimodalRAGPipeline:
    """多模态 RAG 管线，支持图像 - 文本混合处理。"""

    def __init__(
        self,
        vector_store: VectorStore,
        embedder: MultimodalImageEmbedder,
        retriever: MultimodalRetriever | None = None,
    ):
        """
        Args:
            vector_store: 向量存储实例
            embedder: 多模态嵌入器（CLIP 或 Qwen-VL）
            retriever: 多模态检索器（可选，自动生成）
        """
        self.vector_store = vector_store
        self.embedder = embedder
        self.retriever = retriever or MultimodalRetriever(embedder, vector_store)

    def upload_image(
        self,
        image_path: str,
        description: str = "",
        metadata: dict | None = None,
    ) -> str:
        """
        上传图像到知识库。

        Args:
            image_path: 图像文件路径
            description: 图像描述
            metadata: 额外元数据（学科、学段、知识点等）

        Returns:
            图像 ID
        """
        if not PIL_AVAILABLE:
            raise ImportError("PIL is required for image processing")

        # 验证图像文件
        img = Image.open(image_path)
        img.verify()  # 验证图片完整性

        # 添加到向量数据库
        self.retriever.add_image(
            image_path=image_path,
            metadata=metadata,
            description=description,
        )

        return Path(image_path).stem

    def analyze_image(self, image_path: str, prompt: str | None = None) -> dict:
        """
        分析图像内容。

        Args:
            image_path: 图像路径
            prompt: 自定义分析提示词

        Returns:
            分析结果，包括图像描述、关键元素、OCR 文本等
        """
        result = {
            "image_path": image_path,
            "description": "",
            "analysis": {},
            "extracted_text": "",
            "objects": [],
        }

        try:
            # 使用 Qwen-VL 生成详细分析
            if self.embedder.model_type == "qwen-vl":
                default_prompt = (
                    "请详细分析这张教育相关的图片。包括：\n"
                    "1. 图片的主要内容是什么？\n"
                    "2. 是否包含数学公式、化学方程式、图表或其他专业内容？\n"
                    "3. 是否有文字说明？请完整提取。\n"
                    "4. 这可能属于哪个学科和学段？\n"
                    "5. 图片中有哪些关键信息对学习有帮助？\n\n"
                    "请以结构化的 JSON 格式回复。"
                )

                analysis = self.embedder.get_description(
                    image_path,
                    prompt or default_prompt,
                )
                result["analysis"]["llm_output"] = analysis

            # 如果支持 CLIP，可以获取图像分类概率
            elif self.embedder.model_type == "clip":
                img = Image.open(image_path).convert("RGB")
                embeddings = self.embedder._clip_embed_image(img)
                result["embedding_dim"] = len(embeddings)

            result["description"] = "图像已分析完成"

        except Exception as e:
            result["error"] = f"图像分析失败：{str(e)}"

        return result

    def query_with_image(
        self,
        image_path: str,
        question: str | None = None,
        top_k: int = 5,
    ) -> MultimodalQueryResult:
        """
        基于图像进行问答。

        Args:
            image_path: 查询图像路径
            question: 附加问题（可选）
            top_k: 返回最多匹配数

        Returns:
            多模态查询结果
        """
        # 步骤 1：分析图像
        analysis = self.analyze_image(image_path)

        # 步骤 2：搜索相似知识块
        # 这里可以先提取图像的关键文本描述，然后用文本检索
        text_for_retrieval = analysis.get("analysis", {}).get("llm_output", "")

        if not text_for_retrieval and question:
            text_for_retrieval = f"图片内容：{question}"
        elif question:
            text_for_retrieval = question
        else:
            text_for_retrieval = "分析图片内容并回答问题"

        # 步骤 3：执行混合查询
        # TODO: 整合现有 RAG 管线，调用 generator 生成答案
        result = MultimodalQueryResult(
            question=text_for_retrieval,
            answer="",  # 待 LLM 生成
            sources=[],
            stage="unknown",
            related_images=[],
            image_analysis=analysis,
            is_visual_query=True,
        )

        # 同时搜索相似的视觉资源
        visual_results = self.search_similar_images(
            image_path,
            top_k=3,
        )
        result.related_images = visual_results

        return result

    def search_similar_images(
        self,
        reference_image: str | Image.Image,
        top_k: int = 5,
    ) -> list[dict]:
        """
        搜索与参考图像相似的图像。

        Args:
            reference_image: 参考图像路径或 PIL Image
            top_k: 返回数量

        Returns:
            相似图像列表
        """
        if isinstance(reference_image, str):
            embedding = self.embedder.embed_image(reference_image)
        elif PIL_AVAILABLE and isinstance(reference_image, Image.Image):
            embedding = self.embedder._clip_embed_image(reference_image)
        else:
            raise ValueError("reference_image must be a string path or PIL Image")

        return self.vector_store.search_images(
            query_embedding=embedding,
            top_k=top_k,
            threshold=0.3,
        )

    def batch_upload_images(
        self,
        image_paths: list[str],
        descriptions: list[str] | None = None,
        metadata_list: list[dict] | None = None,
    ) -> list[str]:
        """
        批量上传图像。

        Args:
            image_paths: 图像路径列表
            descriptions: 描述列表（可选）
            metadata_list: 元数据列表（可选）

        Returns:
            上传成功的图像 ID 列表
        """
        uploaded_ids = []

        for i, img_path in enumerate(image_paths):
            try:
                desc = descriptions[i] if descriptions and i < len(descriptions) else ""
                meta = metadata_list[i] if metadata_list and i < len(metadata_list) else None

                self.upload_image(img_path, description=desc, metadata=meta)
                uploaded_ids.append(Path(img_path).stem)

            except Exception as e:
                print(f"Failed to upload {img_path}: {e}")

        return uploaded_ids

    def visual_question_answering(
        self,
        image_path: str,
        question: str,
        generate_answer: bool = True,
    ) -> MultimodalQueryResult:
        """
        视觉问答（VQA）：针对图像中的具体内容回答问题。

        典型应用：
        - 数学题：根据函数图像求最值
        - 物理题：分析受力示意图
        - 化学题：识别分子结构图
        - 生物题：解析细胞结构图

        Args:
            image_path: 问题涉及的图像路径
            question: 具体问题
            generate_answer: 是否调用 LLM 生成答案

        Returns:
            VQA 结果
        """
        # 分析图像内容
        analysis = self.analyze_image(image_path)

        # 构造富上下文的问题
        enhanced_question = f"【图像内容】\n{analysis.get('analysis', {}).get('llm_output', '无可用图像描述')}\n\n【问题】\n{question}"

        result = MultimodalQueryResult(
            question=enhanced_question,
            answer="",
            sources=[],
            stage="unknown",
            related_images=[],
            image_analysis=analysis,
            is_visual_query=True,
        )

        if generate_answer:
            # TODO: 调用现有的 generator 组件生成答案
            # 这里需要使用 Prompt 模板将图像分析结果和原问题组合
            pass

        return result

    def create_visual_dataset(
        self,
        images_dir: str,
        output_path: str,
        auto_describe: bool = True,
    ) -> int:
        """
        从目录创建视觉数据集（用于训练/测试）。

        Args:
            images_dir: 图像目录
            output_path: 输出 JSON 文件路径
            auto_describe: 是否自动生成描述

        Returns:
            处理的图像数量
        """
        import json
        from pathlib import Path

        dataset = []
        image_files = list(Path(images_dir).glob("*.{png,jpg,jpeg,gif}"))

        for img_path in image_files:
            entry = {
                "path": str(img_path),
                "id": img_path.stem,
            }

            if auto_describe:
                analysis = self.analyze_image(str(img_path))
                entry["description"] = analysis.get("description", "")
                entry["analysis"] = analysis.get("analysis", {})

            dataset.append(entry)

        # 保存数据集
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)

        return len(dataset)


def create_multimodal_pipeline(
    use_clip: bool = True,
    clip_model: str = "ViT-B/32",
    use_qwen_vl_api: bool = False,
    persist_dir: str | None = None,
) -> MultimodalRAGPipeline:
    """工厂函数：创建多模态 RAG 管线。

    Args:
        use_clip: 使用本地 CLIP 模型
        clip_model: CLIP 模型名称
        use_qwen_vl_api: 使用 Qwen-VL API
        persist_dir: ChromaDB 持久化目录

    Returns:
        配置好的多模态管线实例
    """
    from kag_pro.core.bootstrap import create_default_registry
    from kag_pro.core.event_bus import EventBus
    from kag_pro.orchestration.orchestrator import EducationOrchestrator

    registry = create_default_registry(use_kg=True, persist_dir=persist_dir)
    EducationOrchestrator(registry, EventBus())
    vector_store = registry.resolve("vector-store")

    # 创建多模态嵌入器
    if use_qwen_vl_api:
        embedder = MultimodalImageEmbedder(
            model_type="qwen-vl",
            device="cpu",
        )
    else:
        embedder = MultimodalImageEmbedder(
            model_type="clip",
            model_name=clip_model,
        )

    return MultimodalRAGPipeline(
        vector_store=vector_store,
        embedder=embedder,
    )
