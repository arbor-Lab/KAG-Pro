"""KAG-Pro API server — FastAPI backend for the chat interface."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from kag_pro.core.pipeline import RAGPipeline

app = FastAPI(title="KAG-Pro Chat", version="1.0")

# Init pipeline once
_pipeline: Optional[RAGPipeline] = None


def get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline(use_kg=True)
        data_dir = Path(__file__).resolve().parent.parent / "src" / "kag_pro" / "data" / "textbooks"
        _pipeline.clear_index()
        _pipeline.index_documents(str(data_dir))
    return _pipeline


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    stage: str
    sources: list


class DiagnosisRequest(BaseModel):
    question: str
    student_answer: str
    correct_answer: str


class DiagnosisResponse(BaseModel):
    error_type: str
    knowledge_point: str
    hint: str
    feedback: str


@app.post("/api/query", response_model=QueryResponse)
def query(req: QueryRequest):
    try:
        pipeline = get_pipeline()
        result = pipeline.query(req.question, verify=True)
        return QueryResponse(
            question=result["question"],
            answer=result["answer"],
            stage=result["stage"],
            sources=result["sources"][:3],
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


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse(str(Path(__file__).resolve().parent / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=7860)
