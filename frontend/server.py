"""KAG-Pro API server — FastAPI backend powered by EducationOrchestrator.

Uses the new plugin architecture: PluginRegistry + EventBus + EducationOrchestrator.
Replaces the old RAGPipeline-based server with a cleaner, event-driven design.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List

from kag_pro.core.bootstrap import create_default_registry
from kag_pro.core.event_bus import EventBus
from kag_pro.orchestration.orchestrator import EducationOrchestrator
from kag_pro.core.paper_generator import KnowledgeTreeExtractor, PaperGenerator
from kag_pro.core.paper_store import PaperStore
from kag_pro.core.favorite_store import FavoriteStore
from kag_pro.core.generator import Generator

app = FastAPI(title="KAG-Pro Chat", version="2.0")


# === Singleton accessors ===

_orchestrator: Optional[EducationOrchestrator] = None
_knowledge_tree: Optional[KnowledgeTreeExtractor] = None
_paper_store: Optional[PaperStore] = None
_favorite_store: Optional[FavoriteStore] = None


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
    verification: Optional[VerificationInfo] = None
    analysis: dict = {}
    kg_enrichment: dict = {}


class DiagnosisRequest(BaseModel):
    question: str
    student_answer: str
    correct_answer: str


class DiagnosisResponse(BaseModel):
    error_type: str
    knowledge_point: str
    hint: str
    feedback: str


class ExerciseResponse(BaseModel):
    knowledge_point: str
    exercises: str


# ---- Paper models ----

class QuestionTypeItem(BaseModel):
    type: str
    count: int = 1


class GeneratePaperRequest(BaseModel):
    stage: str
    subject: str
    topics: List[str]
    count: int = 5
    difficulty: str = "中等"
    question_types: List[QuestionTypeItem] = []
    allocations: List[dict] = []


class SavePaperRequest(BaseModel):
    id: Optional[str] = None
    title: str
    stage: str
    subject: str
    topics: List[str]
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


# === Query endpoints ===

@app.post("/api/query", response_model=QueryResponse)
def query(req: QueryRequest):
    """Smart query: auto-detects diagnosis requests and routes accordingly."""
    try:
        orch = get_orchestrator()

        # Auto-detect if this is a diagnosis request (simple heuristic, no LLM call)
        answer_keywords = ['我选', '我的答案', '我填', '我写', '对不对', '对吗', '我答',
                           '我觉得是', '我认为是', '答案是', '应该选']
        has_answer = any(kw in req.question for kw in answer_keywords)

        if has_answer:
            # Try diagnosis routing — use simple extraction
            try:
                gen = orch.registry.resolve("generator")
                prompt = (
                    "请分析以下用户输入，判断是否包含一个错题诊断请求。\n"
                    "诊断请求特征：用户提供了原题、自己做错的答案或选项、以及正确答案或问对错。\n"
                    "如果只是普通提问、要求做题、或没有同时提供题目和答案，则不是诊断请求。\n\n"
                    f"用户输入：\n{req.question}\n\n"
                    '请以严格JSON格式回复：'
                    '{"is_diagnosis": true/false, "question": "原题", "student_answer": "学生答案", "correct_answer": "正确答案"}'
                )
                resp = gen.call(
                    system="你是一位输入分析助手。请严格按JSON格式回复。",
                    user=prompt, temperature=0, max_tokens=200,
                )
                import json
                json_match = re.search(r'\{[^}]*\}', resp, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    if data.get("is_diagnosis") and data.get("student_answer"):
                        diag_result = orch.diagnose(
                            data.get("question", req.question),
                            data["student_answer"],
                            data.get("correct_answer", data["student_answer"]),
                        )
                        lines = []
                        if diag_result.error_type:
                            lines.append(f"【{diag_result.error_type}】")
                        if diag_result.personalized_feedback:
                            lines.append(diag_result.personalized_feedback)
                        if diag_result.hint:
                            lines.append("提示：")
                            lines.append(diag_result.hint)
                        answer = "\n\n".join(lines) if lines else diag_result.personalized_feedback

                        return QueryResponse(
                            question=req.question,
                            answer=answer,
                            stage=diag_result.stage or "未知",
                            sources=[],
                        )
            except Exception:
                pass  # Fall through to regular query

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
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/diagnose", response_model=DiagnosisResponse)
def diagnose(req: DiagnosisRequest):
    try:
        orch = get_orchestrator()
        result = orch.diagnose(req.question, req.student_answer, req.correct_answer)
        return DiagnosisResponse(
            error_type=result.error_type,
            knowledge_point=result.knowledge_point,
            hint=result.hint,
            feedback=result.personalized_feedback,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/exercises", response_model=ExerciseResponse)
def exercises(req: DiagnosisRequest):
    try:
        orch = get_orchestrator()
        result = orch.exercises(req.question, req.student_answer, req.correct_answer)
        return ExerciseResponse(
            knowledge_point=result["knowledge_point"],
            exercises=result["exercises"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Paper endpoints ===

@app.get("/api/knowledge-tree")
def knowledge_tree():
    try:
        tree = get_knowledge_tree()
        return tree.get_tree()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/papers")
def save_paper(req: SavePaperRequest):
    try:
        store = get_paper_store()
        paper = store.save(req.model_dump())
        return paper
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/papers")
def list_papers():
    try:
        store = get_paper_store()
        return store.list_all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


# === Favorite endpoints ===

@app.post("/api/favorites")
def save_favorite(req: FavoriteSaveRequest):
    try:
        store = get_favorite_store()
        item = store.save(req.model_dump())
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/favorites")
def list_favorites(
    type: Optional[str] = None,
    subject: Optional[str] = None,
    knowledge_point: Optional[str] = None,
):
    try:
        store = get_favorite_store()
        return store.list_all(
            fav_type=type, subject=subject, knowledge_point=knowledge_point,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


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
