"""Initial migration - create all tables

Revision ID: 001
Revises: 
Create Date: 2024-01-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Organizations
    op.create_table(
        'organizations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Workspaces
    op.create_table(
        'workspaces',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('organization_id', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Rubrics
    op.create_table(
        'rubrics',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=True),
        sa.Column('dimensions', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('scoring_rules', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('disallowed_language', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('policy', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Workflows
    op.create_table(
        'workflows',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('steps', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('retry_policy', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('escalation_rules', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('compiled_from', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Tasks
    op.create_table(
        'tasks',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workflow_id', sa.String(), nullable=True),
        sa.Column('rubric_id', sa.String(), nullable=True),
        sa.Column('task_type', sa.Enum('RANK', 'LABEL', 'EXTRACT', 'VERIFY', 'COMPARE', 'REPRODUCE', name='tasktype'), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'ASSIGNED', 'IN_PROGRESS', 'SUBMITTED', 'VERIFIED', 'REJECTED', 'COMPLETED', name='taskstatus'), nullable=True),
        sa.Column('inputs', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('instructions', sa.Text(), nullable=False),
        sa.Column('required_artifacts', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('assigned_to', sa.String(), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['rubric_id'], ['rubrics.id']),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Artifacts
    op.create_table(
        'artifacts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('task_id', sa.String(), nullable=True),
        sa.Column('artifact_type', sa.Enum('OBSERVATION_LEDGER', 'EVIDENCE_PACK', 'DECISION', 'STRUCTURED_OUTPUT', 'DIFF', 'TRACE', 'SCREENSHOT', name='artifacttype'), nullable=True),
        sa.Column('storage_path', sa.String(), nullable=True),
        sa.Column('content_hash', sa.String(), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('artifact_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Task Executions
    op.create_table(
        'task_executions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('task_id', sa.String(), nullable=True),
        sa.Column('executor_id', sa.String(), nullable=True),
        sa.Column('executor_type', sa.String(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('trace', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Verification Results
    op.create_table(
        'verification_results',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('execution_id', sa.String(), nullable=True),
        sa.Column('artifact_id', sa.String(), nullable=True),
        sa.Column('verifier_name', sa.String(), nullable=False),
        sa.Column('passed', sa.Boolean(), nullable=False),
        sa.Column('rule', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('violations', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('evidence', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['artifact_id'], ['artifacts.id']),
        sa.ForeignKeyConstraint(['execution_id'], ['task_executions.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Adjudication Sessions
    op.create_table(
        'adjudication_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('task_id', sa.String(), nullable=True),
        sa.Column('executions_compared', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('winner_id', sa.String(), nullable=True),
        sa.Column('reason_tags', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('adjudicator_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('adjudication_sessions')
    op.drop_table('verification_results')
    op.drop_table('task_executions')
    op.drop_table('artifacts')
    op.drop_table('tasks')
    op.drop_table('workflows')
    op.drop_table('rubrics')
    op.drop_table('workspaces')
    op.drop_table('organizations')
