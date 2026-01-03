"""
Artifacts API router.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.core.database import get_db
from app.core.config import settings
from app.models.database import Artifact
from app.schemas.schemas import ArtifactCreate, ArtifactResponse
from app.services.artifact_store import get_artifact_store

router = APIRouter()

# Initialize artifact store
artifact_store = get_artifact_store(
    storage_type=settings.STORAGE_TYPE,
    storage_path=settings.STORAGE_PATH,
    bucket_name=settings.S3_BUCKET_NAME,
    endpoint_url=settings.S3_ENDPOINT_URL
)


@router.post("/upload")
async def upload_artifact(
    task_id: str,
    artifact_type: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload an artifact file.
    
    This is the core "evidence gate" - artifacts must be uploaded
    before task submission is allowed.
    """
    artifact_id = str(uuid.uuid4())
    
    # Read file content
    content = await file.read()
    
    # Store in artifact store
    storage_result = artifact_store.store_artifact(
        artifact_id=artifact_id,
        content=content,
        metadata={
            'filename': file.filename,
            'content_type': file.content_type,
            'task_id': task_id
        }
    )
    
    # Create database record
    artifact = Artifact(
        id=artifact_id,
        task_id=task_id,
        artifact_type=artifact_type,
        storage_path=storage_result['storage_path'],
        content_hash=storage_result['content_hash'],
        size_bytes=storage_result['size_bytes'],
        artifact_metadata=storage_result['metadata']
    )
    
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    
    return artifact


@router.post("/", response_model=ArtifactResponse)
def create_artifact(
    artifact_data: ArtifactCreate,
    db: Session = Depends(get_db)
):
    """Create an artifact record (for structured/JSON artifacts)."""
    artifact = Artifact(
        id=str(uuid.uuid4()),
        task_id=artifact_data.task_id,
        artifact_type=artifact_data.artifact_type,
        storage_path=artifact_data.storage_path,
        content_hash=artifact_data.content_hash,
        size_bytes=artifact_data.size_bytes,
        artifact_metadata=artifact_data.artifact_metadata,
        data=artifact_data.data
    )
    
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    
    return artifact


@router.get("/{artifact_id}", response_model=ArtifactResponse)
def get_artifact(
    artifact_id: str,
    db: Session = Depends(get_db)
):
    """Get artifact metadata."""
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    return artifact


@router.get("/{artifact_id}/download")
def download_artifact(
    artifact_id: str,
    db: Session = Depends(get_db)
):
    """Download artifact content."""
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    # Retrieve from store
    content = artifact_store.retrieve_artifact(artifact.storage_path)
    
    if content is None:
        raise HTTPException(status_code=404, detail="Artifact content not found in storage")
    
    from fastapi.responses import Response
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={artifact_id}"
        }
    )


@router.get("/task/{task_id}", response_model=List[ArtifactResponse])
def list_task_artifacts(
    task_id: str,
    db: Session = Depends(get_db)
):
    """List all artifacts for a task."""
    artifacts = db.query(Artifact).filter(Artifact.task_id == task_id).all()
    return artifacts


@router.delete("/{artifact_id}")
def delete_artifact(
    artifact_id: str,
    db: Session = Depends(get_db)
):
    """Delete an artifact."""
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    # Delete from storage
    artifact_store.delete_artifact(artifact.storage_path)
    
    # Delete from database
    db.delete(artifact)
    db.commit()
    
    return {"status": "deleted", "artifact_id": artifact_id}
