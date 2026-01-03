from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    raw_text: str = Field(..., description="Raw Haiku evaluation output")


class ParsedError(BaseModel):
    index: Optional[int] = None
    field: Optional[str] = None
    from_value: Optional[str] = Field(default=None, alias="from")
    to_value: Optional[str] = Field(default=None, alias="to")
    checkbox: Optional[str] = None
    rationale_text: Optional[str] = None

    class Config:
        allow_population_by_field_name = True


class ParsedPayload(BaseModel):
    debug_info: Dict[str, Any] = {}
    ratings_table: List[Dict[str, Any]] = []
    errors: List[ParsedError] = []
    artifact_refs: List[str] = []


class IngestResponse(BaseModel):
    submission_id: str
    parsed: ParsedPayload
    patch_preview: Optional[str] = None
    verifier_violations: List[Dict[str, Any]] = []


class ApplyPatchResponse(BaseModel):
    ok: bool
    rubric_path: str
    applied_at: datetime
    already_applied: bool = False
