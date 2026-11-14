"""client feedback processing and confirmation pipeline

Revision ID: a891c354b0f2
Revises: 05cc8ac7f846
"""
from alembic import op
import sqlalchemy as sa

revision = "a891c354b0f2"
down_revision = "05cc8ac7f846"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("audio_path", sa.String(600), nullable=False, server_default=""),
        sa.Column("audio_filename", sa.String(255), nullable=False, server_default=""),
        sa.Column("audio_content_type", sa.String(120), nullable=False, server_default=""),
        sa.Column("transcript", sa.Text(), nullable=False, server_default=""),
        sa.Column("transcript_provider", sa.String(80), nullable=False, server_default=""),
        sa.Column("transcript_model", sa.String(120), nullable=False, server_default=""),
        sa.Column("transcript_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extracted_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(40), nullable=False, server_default="queued"),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("client_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "idempotency_key", name="uq_client_feedback_workspace_key"),
    )
    for column in ("workspace_id", "client_id", "project_id", "status"):
        op.create_index(f"ix_client_feedback_{column}", "client_feedback", [column])


def downgrade() -> None:
    for column in ("status", "project_id", "client_id", "workspace_id"):
        op.drop_index(f"ix_client_feedback_{column}", table_name="client_feedback")
    op.drop_table("client_feedback")
