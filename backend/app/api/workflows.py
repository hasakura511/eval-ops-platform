"""
Workflows API router.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.core.database import get_db
from app.models.database import Workflow
from app.schemas.schemas import (
    WorkflowCreate, 
    WorkflowResponse, 
    CompileWorkflowRequest,
    CompileWorkflowResponse
)
from app.services.workflow_compiler import compile_workflow_from_guideline

router = APIRouter()


@router.post("/", response_model=WorkflowResponse)
def create_workflow(
    workflow_data: WorkflowCreate,
    db: Session = Depends(get_db)
):
    """Create a new workflow."""
    workflow = Workflow(
        id=str(uuid.uuid4()),
        workspace_id=workflow_data.workspace_id,
        name=workflow_data.name,
        description=workflow_data.description,
        steps=[step.dict() for step in workflow_data.steps],
        retry_policy=workflow_data.retry_policy,
        escalation_rules=workflow_data.escalation_rules,
        compiled_from=workflow_data.compiled_from
    )
    
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    
    return workflow


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: str,
    db: Session = Depends(get_db)
):
    """Get a workflow by ID."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    return workflow


@router.get("/", response_model=List[WorkflowResponse])
def list_workflows(
    workspace_id: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List workflows, optionally filtered by workspace."""
    query = db.query(Workflow)
    
    if workspace_id:
        query = query.filter(Workflow.workspace_id == workspace_id)
    
    workflows = query.offset(skip).limit(limit).all()
    return workflows


@router.post("/compile", response_model=CompileWorkflowResponse)
def compile_workflow(
    request: CompileWorkflowRequest,
    db: Session = Depends(get_db)
):
    """
    Compile a workflow from evaluation guidelines.
    
    This is the "AI-first" magic: turn natural language guidelines
    into a structured, executable workflow.
    """
    # Compile the workflow
    workflow_data = compile_workflow_from_guideline(
        workspace_id=request.workspace_id,
        guideline_text=request.guideline_text,
        workflow_name=request.workflow_name,
        task_type=request.task_type
    )
    
    # Create workflow in database
    workflow = Workflow(
        id=str(uuid.uuid4()),
        workspace_id=workflow_data['workspace_id'],
        name=workflow_data['name'],
        steps=workflow_data['steps'],
        retry_policy=workflow_data['retry_policy'],
        escalation_rules=workflow_data['escalation_rules'],
        compiled_from=workflow_data['compiled_from']
    )
    
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    
    return CompileWorkflowResponse(
        workflow=workflow,
        compiler_notes={
            'verifier_rules': workflow_data.get('verifier_rules', {}),
            'banned_phrases': workflow_data.get('banned_phrases', [])
        }
    )


@router.delete("/{workflow_id}")
def delete_workflow(
    workflow_id: str,
    db: Session = Depends(get_db)
):
    """Delete a workflow."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    db.delete(workflow)
    db.commit()
    
    return {"status": "deleted", "workflow_id": workflow_id}
