"""client_portal_schema

Revision ID: a1b2c3d4e5f6
Revises: 05cc8ac7f846
Create Date: 2026-11-14 16:32:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '05cc8ac7f846'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'client_portal_access',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('access_token', sa.String(length=128), nullable=False),
        sa.Column('passcode', sa.String(length=64), nullable=False),
        sa.Column('client_email', sa.String(length=320), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('client_id')
    )
    op.create_index(op.f('ix_client_portal_access_access_token'), 'client_portal_access', ['access_token'], unique=True)
    op.create_index(op.f('ix_client_portal_access_client_id'), 'client_portal_access', ['client_id'], unique=False)
    op.create_index(op.f('ix_client_portal_access_passcode'), 'client_portal_access', ['passcode'], unique=False)
    op.create_index(op.f('ix_client_portal_access_workspace_id'), 'client_portal_access', ['workspace_id'], unique=False)

    op.create_table(
        'review_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('version_label', sa.String(length=32), nullable=False),
        sa.Column('video_asset_id', sa.Integer(), nullable=True),
        sa.Column('video_url', sa.String(length=500), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('change_summary', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['video_asset_id'], ['assets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_review_versions_client_id'), 'review_versions', ['client_id'], unique=False)
    op.create_index(op.f('ix_review_versions_project_id'), 'review_versions', ['project_id'], unique=False)
    op.create_index(op.f('ix_review_versions_workspace_id'), 'review_versions', ['workspace_id'], unique=False)

    op.create_table(
        'video_comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('review_version_id', sa.Integer(), nullable=True),
        sa.Column('timestamp_seconds', sa.Float(), nullable=False),
        sa.Column('timecode', sa.String(length=16), nullable=False),
        sa.Column('author_name', sa.String(length=120), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['review_version_id'], ['review_versions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_video_comments_client_id'), 'video_comments', ['client_id'], unique=False)
    op.create_index(op.f('ix_video_comments_project_id'), 'video_comments', ['project_id'], unique=False)
    op.create_index(op.f('ix_video_comments_workspace_id'), 'video_comments', ['workspace_id'], unique=False)

    op.create_table(
        'client_feedback_submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('review_version_id', sa.Integer(), nullable=True),
        sa.Column('feedback_type', sa.String(length=32), nullable=False),
        sa.Column('author_name', sa.String(length=160), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('structured_data', sa.Text(), nullable=False),
        sa.Column('audio_asset_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('review_decision', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['audio_asset_id'], ['assets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['review_version_id'], ['review_versions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_client_feedback_submissions_client_id'), 'client_feedback_submissions', ['client_id'], unique=False)
    op.create_index(op.f('ix_client_feedback_submissions_project_id'), 'client_feedback_submissions', ['project_id'], unique=False)
    op.create_index(op.f('ix_client_feedback_submissions_workspace_id'), 'client_feedback_submissions', ['workspace_id'], unique=False)


def downgrade() -> None:
    op.drop_table('client_feedback_submissions')
    op.drop_table('video_comments')
    op.drop_table('review_versions')
    op.drop_table('client_portal_access')
