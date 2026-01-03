"""
Main FastAPI application setup.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import adjudications, artifacts, executions, tasks, verifications, workflows
from app.core.config import settings
from app.routers import ingest

app = FastAPI(
    title="Eval Ops Platform",
    description="AI-First Evaluation Operations Platform",
    version="0.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Include routers
app.include_router(workflows.router, prefix="/api/v1/workflows", tags=["workflows"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(artifacts.router, prefix="/api/v1/artifacts", tags=["artifacts"])
app.include_router(executions.router, prefix="/api/v1/executions", tags=["executions"])
app.include_router(verifications.router, prefix="/api/v1/verifications", tags=["verifications"])
app.include_router(adjudications.router, prefix="/api/v1/adjudications", tags=["adjudications"])
app.include_router(ingest.router)


@app.get("/")
def root():
    return {
        "message": "Eval Ops Platform API",
        "version": "0.1.0",
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/ingest")
def ingest_ui():
    index_path = static_dir / "ingest.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Ingestion UI not found")
    return FileResponse(index_path)
