"""
Executions API router.

Handles task execution, submission, and verification.
This is where the "no simulated verification" enforcement happens.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid
from datetime import datetime

from app.core.database import get_db
from app.models.database import TaskExecution, Task, Artifact, VerificationResult, TaskStatus, Workflow
from app.schemas.schemas import (
    TaskExecutionCreate, 
    TaskExecutionSubmit,
    TaskExecutionResponse
)
from app.services.verifier_engine import verify_execution

router = APIRouter()


@router.post("/", response_model=TaskExecutionResponse)
def create_execution(
    execution_data: TaskExecutionCreate,
    db: Session = Depends(get_db)
):
    """
    Start a task execution.
    
    Creates an execution record when a user/model begins working on a task.
    """
    # Verify task exists
    task = db.query(Task).filter(Task.id == execution_data.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    execution = TaskExecution(
        id=str(uuid.uuid4()),
        task_id=execution_data.task_id,
        executor_id=execution_data.executor_id,
        executor_type=execution_data.executor_type
    )
    
    db.add(execution)
    db.commit()
    db.refresh(execution)
    
    return execution


@router.post("/{execution_id}/submit", response_model=TaskExecutionResponse)
def submit_execution(
    execution_id: str,
    submission: TaskExecutionSubmit,
    db: Session = Depends(get_db)
):
    """
    Submit a task execution.
    
    This is THE critical endpoint - it runs all verifiers and only
    accepts the submission if all verifiers pass.
    """
    # Get execution
    execution = db.query(TaskExecution).filter(TaskExecution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    if execution.completed_at:
        raise HTTPException(status_code=400, detail="Execution already submitted")
    
    # Get task and workflow
    task = db.query(Task).filter(Task.id == execution.task_id).first()
    workflow = db.query(Workflow).filter(Workflow.id == task.workflow_id).first()
    
    # Get all artifacts for this task
    artifacts = db.query(Artifact).filter(Artifact.task_id == task.id).all()
    artifacts_dict = [
        {
            'id': a.id,
            'artifact_type': a.artifact_type.value,
            'storage_path': a.storage_path,
            'content_hash': a.content_hash,
            'data': a.data,
            'artifact_metadata': a.artifact_metadata
        }
        for a in artifacts
    ]
    
    # Extract verifiers from workflow steps
    verifier_names = []
    for step in workflow.steps:
        verifier_names.extend(step.get('verifiers', []))
    
    # Remove duplicates
    verifier_names = list(set(verifier_names))
    
    # Run verification
    verification_result = verify_execution(
        execution_id=execution_id,
        artifacts=artifacts_dict,
        execution={'decision': submission.decision, 'trace': submission.trace},
        verifier_names=verifier_names
    )
    
    # Store verification results
    for result in verification_result['results']:
        for violation in result['violations']:
            verification = VerificationResult(
                id=str(uuid.uuid4()),
                execution_id=execution_id,
                verifier_name=result['verifier'],
                passed=result['passed'],
                rule={'verifier': result['verifier']},
                violations=[violation],
                evidence={}
            )
            db.add(verification)
    
    # Update execution
    execution.decision = submission.decision
    execution.trace = submission.trace
    execution.completed_at = datetime.utcnow()
    
    # Update task status based on verification
    if verification_result['all_passed']:
        task.status = TaskStatus.VERIFIED
    else:
        task.status = TaskStatus.REJECTED
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Verification failed",
                "verification_results": verification_result
            }
        )
    
    db.commit()
    db.refresh(execution)
    
    return execution


@router.get("/{execution_id}", response_model=TaskExecutionResponse)
def get_execution(
    execution_id: str,
    db: Session = Depends(get_db)
):
    """Get an execution by ID."""
    execution = db.query(TaskExecution).filter(TaskExecution.id == execution_id).first()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return execution


@router.get("/task/{task_id}", response_model=List[TaskExecutionResponse])
def list_task_executions(
    task_id: str,
    db: Session = Depends(get_db)
):
    """List all executions for a task."""
    executions = db.query(TaskExecution).filter(TaskExecution.task_id == task_id).all()
    return executions


@router.delete("/{execution_id}")
def delete_execution(
    execution_id: str,
    db: Session = Depends(get_db)
):
    """Delete an execution."""
    execution = db.query(TaskExecution).filter(TaskExecution.id == execution_id).first()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    db.delete(execution)
    db.commit()
    
    return {"status": "deleted", "execution_id": execution_id}
