"""Add evaluation context fields to submissions table

Revision ID: 003
Revises: 002
Create Date: 2024-01-15
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("submissions", sa.Column("agent_prompt", sa.Text(), nullable=True))
    op.add_column("submissions", sa.Column("model_name", sa.String(100), nullable=True))
    op.add_column("submissions", sa.Column("model_version", sa.String(50), nullable=True))
    op.add_column("submissions", sa.Column("guideline_version", sa.String(100), nullable=True))


def downgrade():
    op.drop_column("submissions", "guideline_version")
    op.drop_column("submissions", "model_version")
    op.drop_column("submissions", "model_name")
    op.drop_column("submissions", "agent_prompt")
