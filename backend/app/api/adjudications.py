"""
Adjudications API router.

Handles comparison and adjudication of multiple executions.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.core.database import get_db
from app.models.database import AdjudicationSession, TaskExecution
from app.schemas.schemas import AdjudicationCreate, AdjudicationResponse

router = APIRouter()


@router.post("/", response_model=AdjudicationResponse)
def create_adjudication(
    adjudication_data: AdjudicationCreate,
    db: Session = Depends(get_db)
):
    """
    Create an adjudication session.
    
    Used when multiple executions need to be compared and a winner selected.
    """
    # Verify executions exist
    for exec_id in adjudication_data.executions_compared:
        execution = db.query(TaskExecution).filter(TaskExecution.id == exec_id).first()
        if not execution:
            raise HTTPException(status_code=404, detail=f"Execution {exec_id} not found")
    
    # Verify winner is in compared list
    if adjudication_data.winner_id not in adjudication_data.executions_compared:
        raise HTTPException(status_code=400, detail="Winner must be one of compared executions")
    
    adjudication = AdjudicationSession(
        id=str(uuid.uuid4()),
        task_id=adjudication_data.task_id,
        executions_compared=adjudication_data.executions_compared,
        winner_id=adjudication_data.winner_id,
        reason_tags=adjudication_data.reason_tags,
        notes=adjudication_data.notes,
        adjudicator_id=adjudication_data.adjudicator_id
    )
    
    db.add(adjudication)
    db.commit()
    db.refresh(adjudication)
    
    return adjudication


@router.get("/{adjudication_id}", response_model=AdjudicationResponse)
def get_adjudication(
    adjudication_id: str,
    db: Session = Depends(get_db)
):
    """Get an adjudication session."""
    adjudication = db.query(AdjudicationSession).filter(
        AdjudicationSession.id == adjudication_id
    ).first()
    
    if not adjudication:
        raise HTTPException(status_code=404, detail="Adjudication not found")
    
    return adjudication


@router.get("/task/{task_id}", response_model=List[AdjudicationResponse])
def list_task_adjudications(
    task_id: str,
    db: Session = Depends(get_db)
):
    """List all adjudications for a task."""
    adjudications = db.query(AdjudicationSession).filter(
        AdjudicationSession.task_id == task_id
    ).all()
    
    return adjudications


@router.get("/analytics/agreement-rate")
def get_agreement_rate(
    task_ids: List[str] = None,
    db: Session = Depends(get_db)
):
    """
    Calculate agreement rate across adjudications.
    
    Useful for measuring rubric clarity and inter-rater reliability.
    """
    query = db.query(AdjudicationSession)
    
    if task_ids:
        query = query.filter(AdjudicationSession.task_id.in_(task_ids))
    
    adjudications = query.all()
    
    if not adjudications:
        return {"agreement_rate": None, "total_adjudications": 0}
    
    # Group by reason tags to identify patterns
    reason_counts = {}
    for adj in adjudications:
        for tag in adj.reason_tags:
            reason_counts[tag] = reason_counts.get(tag, 0) + 1
    
    return {
        "total_adjudications": len(adjudications),
        "reason_distribution": reason_counts,
        "tasks_adjudicated": len(set(adj.task_id for adj in adjudications))
    }
