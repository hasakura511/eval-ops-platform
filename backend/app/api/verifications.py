"""
Verifications API router.

Provides access to verification results and analytics.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.database import VerificationResult
from app.schemas.schemas import VerificationResultResponse

router = APIRouter()


@router.get("/execution/{execution_id}", response_model=List[VerificationResultResponse])
def get_execution_verifications(
    execution_id: str,
    db: Session = Depends(get_db)
):
    """Get all verification results for an execution."""
    verifications = db.query(VerificationResult).filter(
        VerificationResult.execution_id == execution_id
    ).all()
    
    return verifications


@router.get("/{verification_id}", response_model=VerificationResultResponse)
def get_verification(
    verification_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific verification result."""
    verification = db.query(VerificationResult).filter(
        VerificationResult.id == verification_id
    ).first()
    
    if not verification:
        raise HTTPException(status_code=404, detail="Verification not found")
    
    return verification


@router.get("/failed/summary")
def get_failed_verifications_summary(
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get summary of failed verifications.
    
    Useful for identifying common failure patterns and rubric issues.
    """
    failed = db.query(VerificationResult).filter(
        VerificationResult.passed == False
    ).limit(limit).all()
    
    # Group by verifier name
    summary = {}
    for v in failed:
        name = v.verifier_name
        if name not in summary:
            summary[name] = {
                'count': 0,
                'violations': []
            }
        
        summary[name]['count'] += 1
        summary[name]['violations'].extend(v.violations)
    
    return summary
