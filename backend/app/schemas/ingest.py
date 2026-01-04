from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    model_config = {"protected_namespaces": ()}

    raw_text: str = Field(..., description="Raw evaluation output (DEBUG INFO through ERRORS)")
    agent_prompt: Optional[str] = Field(default=None, description="Full prompt text, stored as-is")
    model_name: Optional[str] = Field(default="unknown", description="Model name (e.g., 'claude-3-5-sonnet')")
    model_version: Optional[str] = Field(default=None, description="Model version (e.g., '20241022')")
    guideline_version: Optional[str] = Field(default=None, description="Reference to guideline/PDF version")


class ParsedError(BaseModel):
    model_config = {"populate_by_name": True}

    index: Optional[int] = None
    field: Optional[str] = None
    from_value: Optional[str] = Field(default=None, alias="from")
    to_value: Optional[str] = Field(default=None, alias="to")
    checkbox: Optional[str] = None
    rationale_text: Optional[str] = None


class ParsedPayload(BaseModel):
    debug_info: Dict[str, Any] = Field(default_factory=dict)
    ratings_table: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[ParsedError] = Field(default_factory=list)
    artifact_refs: List[str] = Field(default_factory=list)


class IngestResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    submission_id: str
    parsed: ParsedPayload
    patch_preview: Optional[str] = None
    verifier_violations: List[Dict[str, Any]] = []
    agent_prompt: Optional[str] = None
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    guideline_version: Optional[str] = None


class ApplyPatchResponse(BaseModel):
    ok: bool
    rubric_path: str
    applied_at: datetime
    already_applied: bool = False
