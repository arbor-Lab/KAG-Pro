"""KAG-Pro API server — FastAPI backend powered by EducationOrchestrator.

Uses the new plugin architecture: PluginRegistry + EventBus + EducationOrchestrator.
Replaces the old RAGPipeline-based server with a cleaner, event-driven design.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from kag_pro.core.bootstrap import create_default_registry
from kag_pro.core.event_bus import EventBus
from kag_pro.core.favorite_store import FavoriteStore
from kag_pro.core.paper_generator import KnowledgeTreeExtractor
from kag_pro.core.paper_store import PaperStore
from kag_pro.orchestration.orchestrator import EducationOrchestrator

app = FastAPI(title="KAG-Pro Chat", version="2.0")


# === Singleton accessors ===

_orchestrator: EducationOrchestrator | None = None
_knowledge_tree: KnowledgeTreeExtractor | None = None
_paper_store: PaperStore | None = None
_favorite_store: FavoriteStore | None = None


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
