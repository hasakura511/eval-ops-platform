from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class TaskType(str, Enum):
    RANK = "rank"
    LABEL = "label"
    EXTRACT = "extract"
    VERIFY = "verify"
    COMPARE = "compare"
    REPRODUCE = "reproduce"


class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    VERIFIED = "verified"
    REJECTED = "rejected"
    COMPLETED = "completed"


class ArtifactType(str, Enum):
    OBSERVATION_LEDGER = "observation_ledger"
    EVIDENCE_PACK = "evidence_pack"
    DECISION = "decision"
    STRUCTURED_OUTPUT = "structured_output"
    DIFF = "diff"
    TRACE = "trace"
    SCREENSHOT = "screenshot"


# Rubric Schemas
class RubricDimension(BaseModel):
    name: str
    description: str
    scale: List[Any]  # e.g., [1, 2, 3, 4, 5] or ["poor", "fair", "good"]
    examples: Optional[List[str]] = None


class RubricCreate(BaseModel):
    workspace_id: str
    name: str
    dimensions: List[RubricDimension]
    scoring_rules: Dict[str, Any]
    disallowed_language: List[str] = Field(default_factory=list)
    policy: Dict[str, Any] = Field(default_factory=dict)


class RubricResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    version: int
    dimensions: List[Dict[str, Any]]
    scoring_rules: Dict[str, Any]
    disallowed_language: List[str]
    policy: Dict[str, Any]
    created_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True


# Workflow Schemas
class WorkflowStep(BaseModel):
    step_id: str
    type: str  # "capture", "extract", "verify", "rate"
    requires: List[str] = Field(default_factory=list)  # artifact_ids or step_ids
    produces: ArtifactType
    verifiers: List[str] = Field(default_factory=list)  # verifier names


class WorkflowCreate(BaseModel):
    workspace_id: str
    name: str
    description: Optional[str] = None
    steps: List[WorkflowStep]
    retry_policy: Dict[str, Any] = Field(default_factory=dict)
    escalation_rules: Dict[str, Any] = Field(default_factory=dict)
    compiled_from: Optional[str] = None


class WorkflowResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: Optional[str]
    steps: List[Dict[str, Any]]
    retry_policy: Dict[str, Any]
    escalation_rules: Dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Task Schemas
class TaskCreate(BaseModel):
    workflow_id: str
    rubric_id: str
    task_type: TaskType
    inputs: Dict[str, Any]
    instructions: str
    required_artifacts: List[ArtifactType]


class TaskResponse(BaseModel):
    id: str
    workflow_id: str
    rubric_id: str
    task_type: TaskType
    status: TaskStatus
    inputs: Dict[str, Any]
    instructions: str
    required_artifacts: List[str]
    assigned_to: Optional[str]
    assigned_at: Optional[datetime]
    created_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# Artifact Schemas
class ArtifactCreate(BaseModel):
    task_id: str
    artifact_type: ArtifactType
    storage_path: Optional[str] = None
    content_hash: Optional[str] = None
    size_bytes: Optional[int] = None
    artifact_metadata: Dict[str, Any] = Field(default_factory=dict)
    data: Optional[Dict[str, Any]] = None


class ArtifactResponse(BaseModel):
    id: str
    task_id: str
    artifact_type: ArtifactType
    storage_path: Optional[str]
    content_hash: Optional[str]
    artifact_metadata: Dict[str, Any]
    data: Optional[Dict[str, Any]]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Execution Schemas
class TaskExecutionCreate(BaseModel):
    task_id: str
    executor_id: str
    executor_type: str  # "human" or "model"


class TaskExecutionSubmit(BaseModel):
    decision: Dict[str, Any]  # {rating, rationale, confidence}
    trace: Optional[Dict[str, Any]] = None


class TaskExecutionResponse(BaseModel):
    id: str
    task_id: str
    executor_id: str
    executor_type: str
    started_at: datetime
    completed_at: Optional[datetime]
    decision: Optional[Dict[str, Any]]
    trace: Optional[Dict[str, Any]]
    
    class Config:
        from_attributes = True


# Verification Schemas
class VerificationResultResponse(BaseModel):
    id: str
    execution_id: str
    artifact_id: Optional[str]
    verifier_name: str
    passed: bool
    rule: Dict[str, Any]
    violations: List[Dict[str, Any]]
    evidence: Dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Adjudication Schemas
class AdjudicationCreate(BaseModel):
    task_id: str
    executions_compared: List[str]
    winner_id: str
    reason_tags: List[str]
    notes: Optional[str] = None
    adjudicator_id: str


class AdjudicationResponse(BaseModel):
    id: str
    task_id: str
    executions_compared: List[str]
    winner_id: str
    reason_tags: List[str]
    notes: Optional[str]
    adjudicator_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# Workflow Compiler Schemas
class CompileWorkflowRequest(BaseModel):
    workspace_id: str
    guideline_text: str
    workflow_name: str
    task_type: TaskType


class CompileWorkflowResponse(BaseModel):
    workflow: WorkflowResponse
    compiler_notes: Dict[str, Any]
