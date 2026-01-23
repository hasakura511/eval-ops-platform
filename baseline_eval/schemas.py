"""Pydantic schemas for baseline_eval."""

from typing import Optional, List
from pydantic import BaseModel, Field


class ResultCard(BaseModel):
    """Video content result card data."""
    title: str
    type: str = Field(description="Movie | Show | Person")
    genre: Optional[str] = None
    rating: Optional[str] = Field(None, description="Content rating: G, PG, PG-13, R, etc.")
    recommended_age: Optional[str] = None
    released: Optional[str] = None
    studio: Optional[str] = None
    description: Optional[str] = None
    cast: Optional[List[str]] = None
    directors: Optional[List[str]] = None


class Question(BaseModel):
    """A single evaluation question."""
    query: str
    query_type: str = Field(description="Browse | Similarity | Navigational")
    disambiguation: Optional[str] = Field(None, description="Target for Navigational queries")
    region: str = "USA"
    result: ResultCard


class Answer(BaseModel):
    """Answer to a question."""
    rating: str = Field(description="Perfect | Excellent | Good | Acceptable | Off-Topic | Problem")
    reasoning: str = Field(description="Single paragraph reasoning")
    lookup_performed: bool = False
    lookup_query: Optional[str] = None


class EvalTask(BaseModel):
    """Complete evaluation task."""
    task_id: str
    question: Question
    answer: Optional[Answer] = None
    submitted: bool = False


class TestSession(BaseModel):
    """A complete test session."""
    session_id: str
    test_name: str = "Video Complex Queries"
    started_at: str
    completed_at: Optional[str] = None
    tasks: List[EvalTask] = []
    total_questions: int = 0
    submitted_count: int = 0
    pass_rate: Optional[float] = None
