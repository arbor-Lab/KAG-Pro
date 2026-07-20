"""KAG-Pro API server — FastAPI backend for the chat interface."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List

from kag_pro.core.pipeline import RAGPipeline
from kag_pro.core.paper_generator import KnowledgeTreeExtractor, PaperGenerator
from kag_pro.core.paper_store import PaperStore
from kag_pro.core.generator import Generator

app = FastAPI(title="KAG-Pro Chat", version="1.0")
def _detect_diagnosis(question: str):
    # Quick heuristic pre-check to avoid LLM call on every message
    answer_keywords = ['我选', '我的答案', '我填', '我写', '对不对', '对吗', '正确吗', '错了吗', '我答',
                       '我觉得是', '我认为是', '答案是', '应该选', '我觉着']
    has_answer = any(kw in question for kw in answer_keywords)
    has_question = ('?' in question or '？' in question or '题目' in question or '这题' in question
                    or '下列' in question or '正确的是' in question)
    if not has_answer:
        return False, question, "", ""
    try:
        gen = Generator()
        prompt = (
            "请分析以下用户输入，判断是否包含一个错题诊断请求。\n"
            "诊断请求特征：用户提供了原题、自己做错的答案或选项、以及正确答案或问对错。\n"
            "如果只是普通提问、要求做题、或没有同时提供题目和答案，则不是诊断请求。\n\n"
            "用户输入：\n" + question + "\n\n"
            "请以严格JSON格式回复，不要有任何其他内容：\n"
            '{"is_diagnosis": true/false, "question": "原题", "student_answer": "学生答案", "correct_answer": "正确答案"}'
        )
        resp = gen._call_llm(prompt)
        import json
        json_match = re.search(r'\{[^}]*\}', resp, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            if data.get("is_diagnosis"):
                return True, data.get("question", question), data.get("student_answer", ""), data.get("correct_answer", "")
    except Exception:
        pass
    return False, question, "", ""


_pipeline: Optional[RAGPipeline] = None
_knowledge_tree: Optional[KnowledgeTreeExtractor] = None
_paper_store: Optional[PaperStore] = None


def get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline(use_kg=True)
        data_dir = Path(__file__).resolve().parent.parent / "src" / "kag_pro" / "data" / "textbooks"
        _pipeline.clear_index()
        _pipeline.index_documents(str(data_dir))
    return _pipeline


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


# ---- Pydantic models ----

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


class DiagnosisRequest(BaseModel):
    question: str
    student_answer: str
    correct_answer: str


class DiagnosisResponse(BaseModel):
    error_type: str
    knowledge_point: str
    hint: str
    feedback: str


# ---- Paper models ----

class QuestionTypeItem(BaseModel):
    type: str
    count: int = 1


class AllocItem(BaseModel):
    topic: int = 0
    type: str = ""
    count: int = 0


class GeneratePaperRequest(BaseModel):
    stage: str
    subject: str
    topics: List[str]
    count: int = 5
    difficulty: str = "中等"
    question_types: List[QuestionTypeItem] = []
    allocations: List[AllocItem] = []


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


# ---- Existing endpoints ----

@app.post("/api/query", response_model=QueryResponse)
def query(req: QueryRequest):
    """Smart query: auto-detects diagnosis requests and routes accordingly."""
    try:
        pipeline = get_pipeline()

        # Auto-detect if this is a diagnosis request
        is_diag, parsed_q, student_ans, correct_ans = _detect_diagnosis(req.question)

        if is_diag and student_ans:
            # Route to diagnosis pipeline
            diag_result = pipeline.diagnose(parsed_q, student_ans, correct_ans or student_ans)
            # Build natural-language answer from diagnosis result
            lines = []
            if diag_result.get("error_type"):
                lines.append("【" + diag_result["error_type"] + "】")
            fb = diag_result.get("personalized_feedback") or diag_result.get("feedback", "")
            if fb:
                lines.append(fb)
            if diag_result.get("hint"):
                lines.append("提示：")
                lines.append(diag_result["hint"])
            answer = "\n\n".join(lines) if lines else fb

            sources = []
            for s in diag_result.get("sources", [])[:3]:
                sources.append(SourceItem(
                    text=s.get("text", ""),
                    source=s.get("source", "unknown"),
                    score=s.get("score", 0),
                ))

            return QueryResponse(
                question=req.question,
                answer=answer,
                stage=diag_result.get("stage", "未知"),
                sources=sources,
            )

        # Regular RAG query
        result = pipeline.query(req.question, verify=True)
        sources = []
        for s in result.get("sources", [])[:3]:
            sources.append(SourceItem(
                text=s.get("text", ""),
                source=s.get("source", ""),
                score=s.get("score", 0),
            ))
        verification = None
        if result.get("verification"):
            v = result["verification"]
            verification = VerificationInfo(
                faith_score=v.get("faith_score", 1.0),
                verdict=v.get("verdict", "HIGH"),
                details=v.get("details", ""),
            )
        return QueryResponse(
            question=result["question"],
            answer=result["answer"],
            stage=result["stage"],
            sources=sources,
            verification=verification,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/diagnose", response_model=DiagnosisResponse)
def diagnose(req: DiagnosisRequest):
    try:
        pipeline = get_pipeline()
        result = pipeline.diagnose(req.question, req.student_answer, req.correct_answer)
        return DiagnosisResponse(
            error_type=result["error_type"],
            knowledge_point=result["knowledge_point"],
            hint=result["hint"],
            feedback=result["personalized_feedback"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ExerciseResponse(BaseModel):
    knowledge_point: str
    exercises: str


@app.post("/api/exercises", response_model=ExerciseResponse)
def exercises(req: DiagnosisRequest):
    try:
        pipeline = get_pipeline()
        result = pipeline.exercises(req.question, req.student_answer, req.correct_answer)
        return ExerciseResponse(
            knowledge_point=result["knowledge_point"],
            exercises=result["exercises"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Paper endpoints ----

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
        gen = Generator()
        paper_gen = PaperGenerator(gen)
        qtypes = [qt.model_dump() for qt in req.question_types] if req.question_types else None
        paper = paper_gen.generate(
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


# ---- Health and static ----

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse(str(Path(__file__).resolve().parent / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=7860)
