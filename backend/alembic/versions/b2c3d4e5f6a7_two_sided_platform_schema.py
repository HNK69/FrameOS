"""two_sided_platform_schema

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-15 12:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Extend users table with role and full_name
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(
            sa.Column('role', sa.String(length=32), nullable=False, server_default='agency_owner')
        )
        batch_op.add_column(
            sa.Column('full_name', sa.String(length=160), nullable=False, server_default='')
        )
        batch_op.create_index(batch_op.f('ix_users_role'), ['role'], unique=False)

    # 2. Create agency_profiles table
    op.create_table(
        'agency_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('tagline', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('specializations', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('services', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('portfolio', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('contact_email', sa.String(length=320), nullable=False, server_default=''),
        sa.Column('contact_phone', sa.String(length=64), nullable=False, server_default=''),
        sa.Column('website', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('is_published', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', name='uq_agency_profiles_workspace_id')
    )
    op.create_index(op.f('ix_agency_profiles_workspace_id'), 'agency_profiles', ['workspace_id'], unique=True)
    op.create_index(op.f('ix_agency_profiles_is_published'), 'agency_profiles', ['is_published'], unique=False)

    # 3. Create client_profiles table
    op.create_table(
        'client_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=160), nullable=False, server_default=''),
        sa.Column('industry', sa.String(length=120), nullable=False, server_default=''),
        sa.Column('brand_guidelines', sa.Text(), nullable=False, server_default=''),
        sa.Column('website', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_client_profiles_user_id')
    )
    op.create_index(op.f('ix_client_profiles_user_id'), 'client_profiles', ['user_id'], unique=True)

    # 4. Create project_requests table
    op.create_table(
        'project_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_user_id', sa.Integer(), nullable=False),
        sa.Column('agency_workspace_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('video_type', sa.String(length=80), nullable=False, server_default=''),
        sa.Column('target_platform', sa.String(length=80), nullable=False, server_default=''),
        sa.Column('target_duration', sa.String(length=80), nullable=False, server_default=''),
        sa.Column('aspect_ratio', sa.String(length=32), nullable=False, server_default=''),
        sa.Column('editing_requirements', sa.Text(), nullable=False, server_default=''),
        sa.Column('creative_direction', sa.Text(), nullable=False, server_default=''),
        sa.Column('reference_links', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('deliverables_format', sa.String(length=120), nullable=False, server_default=''),
        sa.Column('budget', sa.String(length=80), nullable=False, server_default=''),
        sa.Column('deadline', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='submitted'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.ForeignKeyConstraint(['agency_workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['client_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_project_requests_agency_workspace_id'), 'project_requests', ['agency_workspace_id'], unique=False)
    op.create_index(op.f('ix_project_requests_client_user_id'), 'project_requests', ['client_user_id'], unique=False)
    op.create_index(op.f('ix_project_requests_status'), 'project_requests', ['status'], unique=False)

    # 5. Create proposals table
    op.create_table(
        'proposals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=False),
        sa.Column('agency_workspace_id', sa.Integer(), nullable=False),
        sa.Column('scope_description', sa.Text(), nullable=False, server_default=''),
        sa.Column('estimated_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('estimated_delivery_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deliverables_summary', sa.Text(), nullable=False, server_default=''),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.ForeignKeyConstraint(['agency_workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['request_id'], ['project_requests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_proposals_agency_workspace_id'), 'proposals', ['agency_workspace_id'], unique=False)
    op.create_index(op.f('ix_proposals_request_id'), 'proposals', ['request_id'], unique=False)
    op.create_index(op.f('ix_proposals_status'), 'proposals', ['status'], unique=False)

    # 6. Extend projects table with request_id FK
    with op.batch_alter_table('projects') as batch_op:
        batch_op.add_column(sa.Column('request_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_projects_request_id', 'project_requests', ['request_id'], ['id'], ondelete='SET NULL')
        batch_op.create_index(batch_op.f('ix_projects_request_id'), ['request_id'], unique=False)

    # 7. Create project_messages table
    op.create_table(
        'project_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=True),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('sender_id', sa.Integer(), nullable=False),
        sa.Column('sender_role', sa.String(length=32), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['request_id'], ['project_requests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_project_messages_project_id'), 'project_messages', ['project_id'], unique=False)
    op.create_index(op.f('ix_project_messages_request_id'), 'project_messages', ['request_id'], unique=False)
    op.create_index(op.f('ix_project_messages_sender_id'), 'project_messages', ['sender_id'], unique=False)


def downgrade() -> None:
    # 1. Drop project_messages
    op.drop_index(op.f('ix_project_messages_sender_id'), table_name='project_messages')
    op.drop_index(op.f('ix_project_messages_request_id'), table_name='project_messages')
    op.drop_index(op.f('ix_project_messages_project_id'), table_name='project_messages')
    op.drop_table('project_messages')

    # 2. Remove request_id from projects
    with op.batch_alter_table('projects') as batch_op:
        batch_op.drop_index(batch_op.f('ix_projects_request_id'))
        batch_op.drop_constraint('fk_projects_request_id', type_='foreignkey')
        batch_op.drop_column('request_id')

    # 3. Drop proposals
    op.drop_index(op.f('ix_proposals_status'), table_name='proposals')
    op.drop_index(op.f('ix_proposals_request_id'), table_name='proposals')
    op.drop_index(op.f('ix_proposals_agency_workspace_id'), table_name='proposals')
    op.drop_table('proposals')

    # 4. Drop project_requests
    op.drop_index(op.f('ix_project_requests_status'), table_name='project_requests')
    op.drop_index(op.f('ix_project_requests_client_user_id'), table_name='project_requests')
    op.drop_index(op.f('ix_project_requests_agency_workspace_id'), table_name='project_requests')
    op.drop_table('project_requests')

    # 5. Drop client_profiles
    op.drop_index(op.f('ix_client_profiles_user_id'), table_name='client_profiles')
    op.drop_table('client_profiles')

    # 6. Drop agency_profiles
    op.drop_index(op.f('ix_agency_profiles_is_published'), table_name='agency_profiles')
    op.drop_index(op.f('ix_agency_profiles_workspace_id'), table_name='agency_profiles')
    op.drop_table('agency_profiles')

    # 7. Remove role and full_name from users
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_role'))
        batch_op.drop_column('full_name')
        batch_op.drop_column('role')
