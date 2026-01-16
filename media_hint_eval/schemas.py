from typing import Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class TaskLinks(BaseModel):
    model_config = ConfigDict(extra="allow")

    google: Optional[str] = None
    youtube: Optional[str] = None
    imdb: Optional[str] = None
    translate: Optional[str] = None


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    task_id: str
    query: str
    result: str
    query_links: TaskLinks = Field(default_factory=TaskLinks)
    result_links: TaskLinks = Field(default_factory=TaskLinks)


class CacheMetadata(BaseModel):
    input_url: str
    final_url: Optional[str] = None
    status: Optional[int] = None
    page_status: Optional[str] = None
    timestamp: str
    error: Optional[str] = None
    html_path: Optional[str] = None
    screenshot_path: Optional[str] = None


class AlternativeCandidate(BaseModel):
    name: Optional[str] = None
    imdb_url: Optional[str] = None
    content_type: str = "unknown"
    imdb_votes: Optional[int] = None
    imdb_rating: Optional[float] = None
    starmeter: Optional[int] = None
    source: Optional[str] = None


class Features(BaseModel):
    task_id: str
    query: str
    result: str
    official_title: Optional[str] = None
    content_type: str = "unknown"
    imdb_votes: Optional[int] = None
    imdb_rating: Optional[float] = None
    starmeter: Optional[int] = None
    query_candidates: List[str] = Field(default_factory=list)
    alternatives: List[AlternativeCandidate] = Field(default_factory=list)
    best_alternative: Optional[AlternativeCandidate] = None
    result_imdb_ok: bool = False
    result_google_ok: bool = False
    result_imdb_blocked: bool = False
    result_google_blocked: bool = False
    evidence_refs: Dict[str, Optional[str]] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)


class ScoreDebug(BaseModel):
    mode: str
    gates: Dict[str, bool]
    features: Dict[str, object]
    score: float
    thresholds: Dict[str, object]
    evidence_refs: Dict[str, Optional[str]]


class ScoreOutput(BaseModel):
    task_id: str
    rating: str
    comment: str
    debug: ScoreDebug


class LabeledFeature(BaseModel):
    model_config = ConfigDict(extra="allow")

    task_id: str
    label: Optional[str] = None
    rating: Optional[str] = None
    features: Optional[Features] = None
