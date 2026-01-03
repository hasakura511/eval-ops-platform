"""
Tasks API router.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
from datetime import datetime

from app.core.database import get_db
from app.models.database import Task, TaskStatus
from app.schemas.schemas import TaskCreate, TaskResponse

router = APIRouter()


@router.post("/", response_model=TaskResponse)
def create_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db)
):
    """Create a new task."""
    task = Task(
        id=str(uuid.uuid4()),
        workflow_id=task_data.workflow_id,
        rubric_id=task_data.rubric_id,
        task_type=task_data.task_type,
        status=TaskStatus.PENDING,
        inputs=task_data.inputs,
        instructions=task_data.instructions,
        required_artifacts=[art.value for art in task_data.required_artifacts]
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return task


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """Get a task by ID."""
    task = db.query(Task).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task


@router.get("/", response_model=List[TaskResponse])
def list_tasks(
    workflow_id: Optional[str] = None,
    status: Optional[TaskStatus] = None,
    assigned_to: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List tasks with optional filters."""
    query = db.query(Task)
    
    if workflow_id:
        query = query.filter(Task.workflow_id == workflow_id)
    
    if status:
        query = query.filter(Task.status == status)
    
    if assigned_to:
        query = query.filter(Task.assigned_to == assigned_to)
    
    tasks = query.offset(skip).limit(limit).all()
    return tasks


@router.post("/{task_id}/assign")
def assign_task(
    task_id: str,
    user_id: str,
    db: Session = Depends(get_db)
):
    """Assign a task to a user."""
    task = db.query(Task).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status != TaskStatus.PENDING:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot assign task with status {task.status}"
        )
    
    task.assigned_to = user_id
    task.assigned_at = datetime.utcnow()
    task.status = TaskStatus.ASSIGNED
    
    db.commit()
    db.refresh(task)
    
    return task


@router.post("/{task_id}/start")
def start_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """Mark task as in progress."""
    task = db.query(Task).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status not in [TaskStatus.PENDING, TaskStatus.ASSIGNED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start task with status {task.status}"
        )
    
    task.status = TaskStatus.IN_PROGRESS
    db.commit()
    db.refresh(task)
    
    return task


@router.post("/{task_id}/complete")
def complete_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """Mark task as completed."""
    task = db.query(Task).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.status = TaskStatus.COMPLETED
    task.completed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(task)
    
    return task


@router.delete("/{task_id}")
def delete_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """Delete a task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    db.delete(task)
    db.commit()
    
    return {"status": "deleted", "task_id": task_id}
