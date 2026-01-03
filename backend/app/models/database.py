from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON, Text, Boolean, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from datetime import datetime

Base = declarative_base()


class TaskType(str, enum.Enum):
    RANK = "rank"
    LABEL = "label"
    EXTRACT = "extract"
    VERIFY = "verify"
    COMPARE = "compare"
    REPRODUCE = "reproduce"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    VERIFIED = "verified"
    REJECTED = "rejected"
    COMPLETED = "completed"


class ArtifactType(str, enum.Enum):
    OBSERVATION_LEDGER = "observation_ledger"
    EVIDENCE_PACK = "evidence_pack"
    DECISION = "decision"
    STRUCTURED_OUTPUT = "structured_output"
    DIFF = "diff"
    TRACE = "trace"
    SCREENSHOT = "screenshot"


class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    workspaces = relationship("Workspace", back_populates="organization")


class Workspace(Base):
    __tablename__ = "workspaces"
    
    id = Column(String, primary_key=True)
    organization_id = Column(String, ForeignKey("organizations.id"))
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    organization = relationship("Organization", back_populates="workspaces")
    rubrics = relationship("Rubric", back_populates="workspace")
    workflows = relationship("Workflow", back_populates="workspace")


class Rubric(Base):
    __tablename__ = "rubrics"
    
    id = Column(String, primary_key=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"))
    name = Column(String, nullable=False)
    version = Column(Integer, default=1)
    dimensions = Column(JSON)  # [{name, description, scale, examples}]
    scoring_rules = Column(JSON)
    disallowed_language = Column(JSON)  # List of banned phrases
    policy = Column(JSON)  # {allowed_tools, privacy_rules, etc.}
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)
    
    workspace = relationship("Workspace", back_populates="rubrics")
    tasks = relationship("Task", back_populates="rubric")


class Workflow(Base):
    __tablename__ = "workflows"
    
    id = Column(String, primary_key=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"))
    name = Column(String, nullable=False)
    description = Column(Text)
    steps = Column(JSON)  # [{step_id, type, requires, produces, verifiers}]
    retry_policy = Column(JSON)
    escalation_rules = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    compiled_from = Column(Text)  # Original guideline doc
    
    workspace = relationship("Workspace", back_populates="workflows")
    tasks = relationship("Task", back_populates="workflow")


class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(String, primary_key=True)
    workflow_id = Column(String, ForeignKey("workflows.id"))
    rubric_id = Column(String, ForeignKey("rubrics.id"))
    task_type = Column(SQLEnum(TaskType))
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)
    
    # Task data
    inputs = Column(JSON)  # {documents, snapshots, tool_outputs}
    instructions = Column(Text, nullable=False)
    required_artifacts = Column(JSON)  # [artifact_type, artifact_type, ...]
    
    # Assignment
    assigned_to = Column(String)  # user_id
    assigned_at = Column(DateTime(timezone=True))
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    
    workflow = relationship("Workflow", back_populates="tasks")
    rubric = relationship("Rubric", back_populates="tasks")
    artifacts = relationship("Artifact", back_populates="task")
    executions = relationship("TaskExecution", back_populates="task")


class Artifact(Base):
    __tablename__ = "artifacts"
    
    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id"))
    artifact_type = Column(SQLEnum(ArtifactType))
    
    # Storage
    storage_path = Column(String)  # S3/object store path
    content_hash = Column(String)
    size_bytes = Column(Integer)
    
    # Metadata
    artifact_metadata = Column(JSON)  # {timestamp, tool_used, etc.}
    data = Column(JSON)  # Structured content (for non-binary artifacts)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    task = relationship("Task", back_populates="artifacts")
    verifications = relationship("VerificationResult", back_populates="artifact")


class TaskExecution(Base):
    __tablename__ = "task_executions"
    
    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id"))
    executor_id = Column(String)  # user_id or model_id
    executor_type = Column(String)  # "human" or "model"
    
    # Execution data
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    
    # Output
    decision = Column(JSON)  # {rating, rationale, confidence}
    trace = Column(JSON)  # Tool calls, timings, errors
    
    task = relationship("Task", back_populates="executions")
    verifications = relationship("VerificationResult", back_populates="execution")


class VerificationResult(Base):
    __tablename__ = "verification_results"
    
    id = Column(String, primary_key=True)
    execution_id = Column(String, ForeignKey("task_executions.id"))
    artifact_id = Column(String, ForeignKey("artifacts.id"), nullable=True)
    
    verifier_name = Column(String, nullable=False)
    passed = Column(Boolean, nullable=False)
    
    # Details
    rule = Column(JSON)  # The verifier rule that was applied
    violations = Column(JSON)  # List of specific failures
    evidence = Column(JSON)  # Supporting data
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    execution = relationship("TaskExecution", back_populates="verifications")
    artifact = relationship("Artifact", back_populates="verifications")


class AdjudicationSession(Base):
    __tablename__ = "adjudication_sessions"
    
    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id"))
    
    executions_compared = Column(JSON)  # [execution_id, execution_id]
    winner_id = Column(String)  # execution_id
    reason_tags = Column(JSON)  # ["clarity", "evidence_quality"]
    notes = Column(Text)
    
    adjudicator_id = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
