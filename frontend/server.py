"""KAG-Pro API server — FastAPI backend powered by EducationOrchestrator.

Uses the new plugin architecture: PluginRegistry + EventBus + EducationOrchestrator.
Replaces the old RAGPipeline-based server with a cleaner, event-driven design.

Supports multimodal visual question answering (VQA) with image upload and analysis.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Annotated
from fastapi import UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from kag_pro.core.bootstrap import create_default_registry
from kag_pro.core.event_bus import EventBus
from kag_pro.core.favorite_store import FavoriteStore
from kag_pro.core.multimodal_pipeline import MultimodalRAGPipeline, create_multimodal_pipeline
from kag_pro.core.paper_generator import KnowledgeTreeExtractor
from kag_pro.core.paper_store import PaperStore
from kag_pro.orchestration.orchestrator import EducationOrchestrator

app = FastAPI(title="KAG-Pro Chat", version="2.0")

# Static assets (KaTeX for LaTeX math rendering, etc.)
_static_dir = Path(__file__).resolve().parent / "static"
if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


# === Singleton accessors ===

_orchestrator: EducationOrchestrator | None = None
_knowledge_tree: KnowledgeTreeExtractor | None = None
_paper_store: PaperStore | None = None
_favorite_store: FavoriteStore | None = None
_multimodal_pipeline: MultimodalRAGPipeline | None = None


def get_orchestrator() -> EducationOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        registry = create_default_registry(use_kg=True)
        bus = EventBus()
        _orchestrator = EducationOrchestrator(registry, bus)
        data_dir = Path(__file__).resolve().parent.parent / "src" / "kag_pro" / "data" / "textbooks"
        _orchestrator.clear_index()
        _orchestrator.index_documents(str(data_dir))
    return _orchestrator


def get_multimodal_pipeline():
    """获取或创建多模态 VQA 管线。"""
    global _multimodal_pipeline
    if _multimodal_pipeline is None:
        # 检查是否启用了多模态依赖
        try:
            _multimodal_pipeline = create_multimodal_pipeline(
                use_clip=True,
                clip_model="ViT-B/32",
                persist_dir=str(Path(__file__).resolve().parent.parent / "data/chroma_db"),
            )
            print("Multimodal pipeline initialized with CLIP")
        except ImportError as e:
            print(f"Warning: Could not initialize multimodal pipeline: {e}")
            _multimodal_pipeline = None
    return _multimodal_pipeline


def get_knowledge_tree() -> KnowledgeTreeExtractor:
    global _knowledge_tree
    if _knowledge_tree is None:
        _knowledge_tree = KnowledgeTreeExtractor()
    return _knowledge_tree


def get_paper_store() -> PaperStore:
    global _paper_store
    if _paper_store is None:
        _paper_store = PaperStore()
    return _paper_store


def get_favorite_store() -> FavoriteStore:
    global _favorite_store
    if _favorite_store is None:
        _favorite_store = FavoriteStore()
    return _favorite_store


# === Pydantic models ===

class QueryRequest(BaseModel):
    question: str
    show_reasoning: bool = False


class SourceItem(BaseModel):
    text: str = ""
    source: str = ""
    score: float = 0.0


class VerificationInfo(BaseModel):
    faith_score: float = 1.0
    verdict: str = "HIGH"
    details: str = ""


# === Multimodal VQA models ===

class ImageUploadRequest(BaseModel):
    """图像上传请求模型。"""
    description: str = ""
    metadata: dict = {}


class ImageUploadResponse(BaseModel):
    """图像上传响应模型。"""
    success: bool
    image_id: str
    message: str
    analysis: dict | None = None


class VisualQueryRequest(BaseModel):
    """视觉查询请求模型。"""
    image_id: str  # 已上传图像的 ID
    question: str  # 针对图像的问题
    top_k: int = 5


class SimilarImageResponse(BaseModel):
    """相似图像搜索结果。"""
    images: list[dict] = []  # 包含 image_path, score, metadata


class QueryResponse(BaseModel):
    question: str
    answer: str
    stage: str
    sources: list[SourceItem] = []
    verification: VerificationInfo | None = None
    analysis: dict = {}
    kg_enrichment: dict = {}
    is_diagnosis: bool = False
    diagnosis_info: dict | None = None


class VisualQueryResponse(QueryResponse):
    """视觉查询响应模型（扩展 QueryResponse）。"""
    related_images: list[dict] = []
    image_analysis: dict = {}
    is_visual_query: bool = True


# ---- Paper models ----

class QuestionTypeItem(BaseModel):
    type: str
    count: int = 1


class GeneratePaperRequest(BaseModel):
    stage: str
    subject: str
    topics: list[str]
    count: int = 5
    difficulty: str = "中等"
    question_types: list[QuestionTypeItem] = []
    allocations: list[dict] = []


class SavePaperRequest(BaseModel):
    id: str | None = None
    title: str
    stage: str
    subject: str
    topics: list[str]
    difficulty: str
    question_types: list = []
    count: int
    questions: list
    created_at: str = ""


# ---- Favorite models ----

class FavoriteSaveRequest(BaseModel):
    type: str
    title: str = ""
    content: dict = {}
    subject: str = ""
    stage: str = ""
    knowledge_point: str = ""


# === Diagnosis auto-detection ===

_DIAGNOSIS_KEYWORDS = [
    '我选', '我的答案', '我填', '我写', '对不对', '对吗', '我答',
    '我觉得是', '我认为是', '答案是', '应该选',
    '我算的', '我得到的', '我做的', '我的解', '这样对',
    '这样做对', '错在哪', '哪里错了', '为什么错', '为什么不对',
    '我做错了', '我选错了', '我算错了',
]


def _try_diagnose(
    orch: EducationOrchestrator,
    question: str,
) -> QueryResponse | None:
    """Attempt to detect and process a diagnosis request from user input.

    Returns a QueryResponse with diagnosis results if the user's input
    contains a submitted wrong answer, otherwise returns None.
    """
    has_answer = any(kw in question for kw in _DIAGNOSIS_KEYWORDS)
    if not has_answer:
        return None

    try:
        gen = orch.registry.resolve("generator")
        prompt = (
            "请分析以下用户输入，判断是否包含一个错题诊断请求。\n"
            "诊断请求特征：用户提供了原题、自己做错的答案或选项，"
            "并询问对错或寻求帮助。\n"
            "如果只是普通提问、要求做题、或没有提供自己的答案，"
            "则不是诊断请求。\n\n"
            f"用户输入：\n{question}\n\n"
            '请以严格JSON格式回复：'
            '{"is_diagnosis": true/false, '
            '"question": "原题", '
            '"student_answer": "学生答案", '
            '"correct_answer": "正确答案（如用户未提供则留空字符串）"}'
        )
        resp = gen.call(
            system="你是一位输入分析助手。请严格按JSON格式回复。",
            user=prompt, temperature=0, max_tokens=300,
        )
        json_match = re.search(r'\{[^}]*\}', resp, re.DOTALL)
        if not json_match:
            return None

        data = json.loads(json_match.group())
        if not data.get("is_diagnosis") or not data.get("student_answer"):
            return None

        extracted_question = data.get("question", question)
        student_answer = data["student_answer"]
        correct_answer = data.get("correct_answer", "")

        # If correct answer is missing, use RAG to obtain it
        rag_answer = ""
        if not correct_answer.strip():
            rag_result = orch.query(extracted_question, verify=False)
            rag_answer = rag_result.answer
            correct_answer = rag_answer

        # Run diagnosis
        diag_result = orch.diagnose(
            extracted_question, student_answer, correct_answer,
        )

        # Build answer text
        lines = []
        if diag_result.error_type:
            lines.append(f"【{diag_result.error_type}】")
        if diag_result.personalized_feedback:
            lines.append(diag_result.personalized_feedback)
        if diag_result.hint:
            lines.append("提示：" + diag_result.hint)
        answer = "\n\n".join(lines) if lines else diag_result.personalized_feedback

        return QueryResponse(
            question=question,
            answer=answer,
            stage=diag_result.stage or "未知",
            sources=[],
            is_diagnosis=True,
            diagnosis_info={
                "error_type": diag_result.error_type,
                "knowledge_point": diag_result.knowledge_point,
                "hint": diag_result.hint,
                "confidence": diag_result.confidence,
                "student_answer": student_answer,
                "correct_answer": correct_answer,
                "question": extracted_question,
                "feedback": diag_result.personalized_feedback,
            },
        )
    except Exception:
        return None


# === Multimodal VQA endpoints ===

@app.post("/api/upload-image")
async def upload_image(
    file: Annotated[UploadFile, File(description="要上传的图像文件（PNG/JPG/JPEG）")],
    description: Annotated[str, Form(description="图像描述")] = "",
    metadata_json: Annotated[str | None, Form(description="元数据 JSON 字符串")] = None,
):
    """
    上传图像到知识库，支持后续的多模态检索和视觉问答。
    
    支持的格式：PNG, JPG, JPEG
    最大文件大小：10MB
    
    Returns:
        - success: 上传是否成功
        - image_id: 图像 ID
        - message: 状态消息
        - analysis: 可选的图像分析结果（如果启用了 Qwen-VL）
    """
    try:
        pipeline = get_multimodal_pipeline()
        
        if pipeline is None:
            raise HTTPException(
                status_code=503,
                detail="Multimodal support not available. Install with: pip install kag-pro[multimodal]",
            )
        
        # 验证文件类型
        if not file.filename or not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            raise HTTPException(status_code=400, detail="Invalid file type. Only PNG/JPG/JPEG allowed")
        
        # 检查文件大小（最大 10MB）
        file.seek(0, 2)  # Move to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large. Max size: 10MB")
        
        # 保存上传的图像
        uploads_dir = Path(__file__).resolve().parent.parent / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        
        image_path = uploads_dir / file.filename
        with open(image_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # 解析元数据
        metadata = {}
        if metadata_json:
            try:
                metadata = json.loads(metadata_json)
            except json.JSONDecodeError:
                pass
        
        # 上传到多模态管线
        image_id = pipeline.upload_image(
            image_path=str(image_path),
            description=description,
            metadata=metadata,
        )
        
        # 可选：自动分析图像内容
        analysis = None
        try:
            analysis_result = pipeline.analyze_image(str(image_path))
            if "error" not in analysis_result:
                analysis = analysis_result
        except Exception as e:
            print(f"Image analysis skipped: {e}")
        
        return ImageUploadResponse(
            success=True,
            image_id=image_id,
            message=f"Image uploaded: {image_path.name}",
            analysis=analysis,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/vqa", response_model=VisualQueryResponse)
def visual_question_answering(req: VisualQueryRequest):
    """
    视觉问答（VQA）：基于已上传图像进行问答。
    
    Args:
        req: 包含图像 ID 和问题
    
    Returns:
        多模态查询结果，包括答案和相关图像
    """
    try:
        pipeline = get_multimodal_pipeline()
        
        if pipeline is None:
            raise HTTPException(
                status_code=503,
                detail="Multimodal support not available",
            )
        
        # 查找图像路径
        uploads_dir = Path(__file__).resolve().parent.parent / "uploads"
        image_path = uploads_dir / f"{req.image_id}.png"
        
        if not image_path.exists():
            image_path = uploads_dir / f"{req.image_id}.jpg"
        
        if not image_path.exists():
            raise HTTPException(status_code=404, detail=f"Image not found: {req.image_id}")
        
        # 执行视觉问答
        result = pipeline.visual_question_answering(
            image_path=str(image_path),
            question=req.question,
            generate_answer=True,
        )
        
        # 转换为标准响应格式
        sources = []
        for img in result.related_images[:3]:
            sources.append(SourceItem(
                text=img.get("description", ""),
                source=img.get("image_path", ""),
                score=img.get("score", 0),
            ))
        
        return VisualQueryResponse(
            question=result.question,
            answer=result.answer,
            stage=result.stage,
            sources=sources,
            verification=None,
            analysis=result.analysis,
            kg_enrichment={},
            related_images=result.related_images,
            image_analysis=result.image_analysis,
            is_visual_query=True,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/search-similar-images")
def search_similar_images(req: VisualQueryRequest):
    """
    搜索与指定图像相似的图像。
    
    使用 CLIP 模型的图像嵌入进行相似度匹配。
    """
    try:
        pipeline = get_multimodal_pipeline()
        
        if pipeline is None:
            raise HTTPException(
                status_code=503,
                detail="Multimodal support not available",
            )
        
        # 查找图像路径
        uploads_dir = Path(__file__).resolve().parent.parent / "uploads"
        image_path = uploads_dir / f"{req.image_id}.png"
        
        if not image_path.exists():
            image_path = uploads_dir / f"{req.image_id}.jpg"
        
        if not image_path.exists():
            raise HTTPException(status_code=404, detail=f"Image not found: {req.image_id}")
        
        # 搜索相似图像
        similar = pipeline.search_similar_images(
            reference_image=str(image_path),
            top_k=req.top_k,
        )
        
        return SimilarImageResponse(images=similar)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/images")
def list_uploaded_images():
    """列出所有已上传的图像。"""
    try:
        uploads_dir = Path(__file__).resolve().parent.parent / "uploads"
        
        if not uploads_dir.exists():
            return {"images": []}
        
        images = []
        for file in uploads_dir.iterdir():
            if file.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                images.append({
                    "id": file.stem,
                    "filename": file.name,
                    "size": file.stat().st_size,
                    "created_at": file.stat().st_ctime,
                    "modified_at": file.stat().st_mtime,
                })
        
        return {"images": sorted(images, key=lambda x: x["modified_at"], reverse=True)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# === Query endpoints ===

@app.post("/api/query", response_model=QueryResponse)
def query(req: QueryRequest):
    """Smart query: auto-detects diagnosis requests and routes accordingly."""
    try:
        orch = get_orchestrator()

        # Auto-detect diagnosis requests from user input
        diag_response = _try_diagnose(orch, req.question)
        if diag_response is not None:
            return diag_response

        # Regular RAG query via orchestrator
        result = orch.query(req.question, verify=True)
        sources = []
        for s in result.sources[:3]:
            sources.append(SourceItem(
                text=s.get("text", ""),
                source=s.get("source", ""),
                score=s.get("score", 0),
            ))
        verification = None
        if result.verification:
            v = result.verification
            verification = VerificationInfo(
                faith_score=v.get("faith_score", 1.0),
                verdict=v.get("verdict", "HIGH"),
                details=v.get("details", ""),
            )
        return QueryResponse(
            question=result.question,
            answer=result.answer,
            stage=result.stage,
            sources=sources,
            verification=verification,
            analysis=result.analysis,
            kg_enrichment=result.kg_enrichment,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# === Streaming query endpoint (SSE) ===

def sse_format(event_type: str, data: dict) -> str:
    """Format a single SSE event string."""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/query/stream")
def query_stream(req: QueryRequest):
    """SSE streaming query endpoint.

    Events (in order):
      thought (analysis) → thought (retrieval) → thought (kg_enrichment)?
      → reasoning_delta* → thought (reasoning)?
      → answer_delta* → thought (verification)?
      → meta → done

    If the input is a diagnosis request, emits a single `diagnosis` event.
    """
    def event_stream():
        try:
            orch = get_orchestrator()

            # Auto-detect diagnosis requests (non-streaming, one-shot)
            diag_response = _try_diagnose(orch, req.question)
            if diag_response is not None:
                yield sse_format("diagnosis", diag_response.model_dump())
                yield sse_format("done", {})
                return

            # Stream pipeline events from orchestrator
            for event in orch.query_stream(
                req.question,
                verify=True,
                show_reasoning=req.show_reasoning,
            ):
                yield sse_format(event["type"], event["data"])
        except Exception as e:
            yield sse_format("error", {"message": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# === Paper endpoints ===

@app.get("/api/knowledge-tree")
def knowledge_tree():
    try:
        tree = get_knowledge_tree()
        return tree.get_tree()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/generate-paper")
def generate_paper(req: GeneratePaperRequest):
    try:
        orch = get_orchestrator()
        qtypes = [qt.model_dump() for qt in req.question_types] if req.question_types else None
        paper = orch.generate_paper(
            stage=req.stage,
            subject=req.subject,
            topics=req.topics,
            count=req.count,
            difficulty=req.difficulty,
            question_types=qtypes,
            allocations=req.allocations or None,
        )
        return paper
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/papers")
def save_paper(req: SavePaperRequest):
    try:
        store = get_paper_store()
        paper = store.save(req.model_dump())
        return paper
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/papers")
def list_papers():
    try:
        store = get_paper_store()
        return store.list_all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/papers/{paper_id}")
def get_paper(paper_id: str):
    try:
        store = get_paper_store()
        paper = store.get(paper_id)
        if paper is None:
            raise HTTPException(status_code=404, detail="Paper not found")
        return paper
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/papers/{paper_id}")
def delete_paper(paper_id: str):
    try:
        store = get_paper_store()
        ok = store.delete(paper_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Paper not found")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# === Favorite endpoints ===

@app.post("/api/favorites")
def save_favorite(req: FavoriteSaveRequest):
    try:
        store = get_favorite_store()
        item = store.save(req.model_dump())
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/favorites")
def list_favorites(
    type: str | None = None,
    subject: str | None = None,
    knowledge_point: str | None = None,
):
    try:
        store = get_favorite_store()
        return store.list_all(
            fav_type=type, subject=subject, knowledge_point=knowledge_point,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/favorites/{item_id}")
def get_favorite(item_id: str):
    try:
        store = get_favorite_store()
        item = store.get(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Favorite not found")
        return item
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/favorites/{item_id}")
def delete_favorite(item_id: str):
    try:
        store = get_favorite_store()
        ok = store.delete(item_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Favorite not found")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# === New v2 endpoints ===

@app.get("/api/v2/health")
def health_v2():
    """Health check with orchestrator status."""
    try:
        orch = get_orchestrator()
        return {
            "status": "ok",
            "document_count": orch.document_count,
            "error_history_count": len(orch.error_history),
            "services": orch.registry.list_services(),
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/api/v2/kg/search")
def kg_search(q: str):
    """Search the knowledge graph."""
    try:
        orch = get_orchestrator()
        if not orch.registry.has("knowledge-graph"):
            raise HTTPException(status_code=404, detail="KG not initialized")
        kg = orch.registry.resolve("knowledge-graph")
        entities = kg.search_entities(q)
        results = []
        for e in entities[:10]:
            prereqs = kg.get_prerequisites(e["id"])
            mistakes = kg.get_common_mistakes(e["id"])
            results.append({
                "entity": e,
                "prerequisites": [p["name"] for p in prereqs],
                "common_mistakes": [m["name"] for m in mistakes],
            })
        return {"results": results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# === Health and static ===

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse(str(Path(__file__).resolve().parent / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=7860)
