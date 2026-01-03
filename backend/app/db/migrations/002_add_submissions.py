"""Add submissions table for ingestion pipeline

Revision ID: 002
Revises: 001
Create Date: 2024-01-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
    op.create_table(
        "submissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("parsed_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("artifact_refs", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column("patch_preview", sa.Text(), nullable=True),
        sa.Column("patch_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("patch_applied", sa.Boolean(), server_default=sa.text("false"), nullable=True),
        sa.Column("patch_applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verifier_results", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )


def downgrade():
    op.drop_table("submissions")
