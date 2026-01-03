import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, JSON, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

from app.models.database import Base


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    raw_text = Column(Text, nullable=False)
    parsed_json = Column(JSON)
    artifact_refs = Column(postgresql.ARRAY(postgresql.UUID(as_uuid=True)))
    patch_preview = Column(Text)
    patch_data = Column(JSON)
    patch_applied = Column(Boolean, default=False)
    patch_applied_at = Column(DateTime(timezone=True))
    verifier_results = Column(JSON)
