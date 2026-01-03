"""
Main FastAPI application setup.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import tasks, workflows, artifacts, executions, verifications, adjudications

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

# Include routers
app.include_router(workflows.router, prefix="/api/v1/workflows", tags=["workflows"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(artifacts.router, prefix="/api/v1/artifacts", tags=["artifacts"])
app.include_router(executions.router, prefix="/api/v1/executions", tags=["executions"])
app.include_router(verifications.router, prefix="/api/v1/verifications", tags=["verifications"])
app.include_router(adjudications.router, prefix="/api/v1/adjudications", tags=["adjudications"])


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
