"""Milestone 1 (M1) Model and Schema Unit Tests.

Covers:
- User extension (role, full_name)
- AgencyProfile model & properties (specializations_list, services_list, portfolio_list)
- ClientProfile model & 1:1 user relationship
- ProjectRequest model & status transitions
- Proposal model & request linkage
- ProjectMessage model & polymorphic linking (request / project)
- Project model extension with request_id FK (ondelete='SET NULL')
- Pydantic v2 input/output schemas validation & boundary checks
"""

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import (
    AgencyProfile,
    Client,
    ClientProfile,
    Project,
    ProjectMessage,
    ProjectRequest,
    Proposal,
    User,
    Workspace,
)
from app.schemas import (
    AgencyProfileResponse,
    AgencyProfileUpdateInput,
    AgencyRegisterInput,
    ClientRegisterInput,
    PortfolioItem,
    ProjectMessageCreateInput,
    ProjectRequestCreateInput,
    ProjectRequestResponse,
    ProjectRequestUpdateInput,
    ProposalCreateInput,
)


@pytest.fixture
def db_session():
    """Provides a fresh isolated in-memory SQLite database session for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# =============================================================================
# 1. User Extension Tests
# =============================================================================

def test_user_defaults_and_custom_role(db_session: Session):
    # Default user creation
    user_default = User(email="owner@agency.com", password_hash="hashed_pw")
    db_session.add(user_default)
    db_session.commit()

    assert user_default.id is not None
    assert user_default.role == "agency_owner"
    assert user_default.full_name == ""

    # User with explicit client role and full name
    user_client = User(
        email="client@brand.com",
        password_hash="hashed_pw2",
        full_name="Jane Doe",
        role="client",
    )
    db_session.add(user_client)
    db_session.commit()

    assert user_client.role == "client"
    assert user_client.full_name == "Jane Doe"


def test_user_delete_cascades_to_project_requests(db_session: Session):
    """Verifies that deleting a User with related ProjectRequests cascades cleanly
    without violating NOT NULL constraints on project_requests.client_user_id.
    """
    user = User(email="cascade_client@brand.com", password_hash="hashed_pw", role="client")
    agency_ws = Workspace(name="Cascade Agency")
    db_session.add_all([user, agency_ws])
    db_session.commit()

    req1 = ProjectRequest(
        client_user_id=user.id,
        agency_workspace_id=agency_ws.id,
        title="Request 1",
        status="submitted",
    )
    req2 = ProjectRequest(
        client_user_id=user.id,
        agency_workspace_id=agency_ws.id,
        title="Request 2",
        status="draft",
    )
    db_session.add_all([req1, req2])
    db_session.commit()

    assert len(user.project_requests) == 2
    assert db_session.query(ProjectRequest).filter(ProjectRequest.client_user_id == user.id).count() == 2

    # Deleting user must cascade and delete both requests cleanly
    db_session.delete(user)
    db_session.commit()

    assert db_session.get(User, user.id) is None
    assert db_session.query(ProjectRequest).filter(ProjectRequest.client_user_id == user.id).count() == 0


# =============================================================================
# 2. AgencyProfile Model & Properties Tests
# =============================================================================

def test_agency_profile_defaults_and_json_properties(db_session: Session):
    workspace = Workspace(name="Creative Agency")
    db_session.add(workspace)
    db_session.commit()

    profile = AgencyProfile(
        workspace_id=workspace.id,
        tagline="Top Video Editing Agency",
        description="We craft high-converting YouTube and TikTok videos.",
        specializations=json.dumps(["Short-form", "Commercials"]),
        services=json.dumps(["Full Edit", "Color Grading", "Sound Design"]),
        portfolio=json.dumps([
            {"title": "Demo Reel", "video_url": "https://example.com/demo.mp4", "thumbnail_url": "", "description": "Highlight reel"}
        ]),
        contact_email="hello@creativeagency.com",
        is_published=False,
    )
    db_session.add(profile)
    db_session.commit()

    assert profile.id is not None
    assert profile.workspace_id == workspace.id
    assert profile.is_published is False
    assert profile.published_at is None
    assert profile.specializations_list == ["Short-form", "Commercials"]
    assert profile.services_list == ["Full Edit", "Color Grading", "Sound Design"]
    assert len(profile.portfolio_list) == 1
    assert profile.portfolio_list[0]["title"] == "Demo Reel"

    # Test corrupted JSON fallback
    profile.specializations = "invalid json {"
    assert profile.specializations_list == []


def test_agency_profile_publish_toggle(db_session: Session):
    workspace = Workspace(name="Publish Agency")
    db_session.add(workspace)
    db_session.commit()

    profile = AgencyProfile(workspace_id=workspace.id)
    db_session.add(profile)
    db_session.commit()

    assert not profile.is_published

    now = datetime.now(UTC)
    profile.is_published = True
    profile.published_at = now
    db_session.commit()

    refreshed = db_session.get(AgencyProfile, profile.id)
    assert refreshed.is_published is True
    assert refreshed.published_at is not None


def test_agency_profile_non_list_json_resilience():
    """Verifies that non-list JSON strings (null, numbers, dicts, booleans, strings)
    gracefully evaluate to empty lists for specializations, services, and portfolio,
    and propagate safely through Pydantic schemas without ValidationError.
    """
    non_list_payloads = [
        "null",
        "123",
        "{}",
        "true",
        "false",
        "\"string_literal\"",
        "3.14",
        "invalid json {",
        "",
    ]

    for payload in non_list_payloads:
        profile = AgencyProfile(
            workspace_id=1,
            specializations=payload,
            services=payload,
            portfolio=payload,
        )

        assert profile.specializations_list == [], f"Failed on specializations payload: {payload!r}"
        assert profile.services_list == [], f"Failed on services payload: {payload!r}"
        assert profile.portfolio_list == [], f"Failed on portfolio payload: {payload!r}"

        # Must pass Pydantic AgencyProfileResponse validation cleanly
        response = AgencyProfileResponse(
            id=1,
            workspace_id=1,
            specializations=profile.specializations_list,
            services=profile.services_list,
            portfolio=profile.portfolio_list,
        )
        assert response.specializations == []
        assert response.services == []
        assert response.portfolio == []


# =============================================================================
# 3. ClientProfile Model Tests
# =============================================================================

def test_client_profile_1_to_1_user_relationship(db_session: Session):
    user = User(email="client_user@brand.com", password_hash="hashed_pw", role="client", full_name="John Smith")
    db_session.add(user)
    db_session.commit()

    profile = ClientProfile(
        user_id=user.id,
        company_name="Acme Brand",
        industry="E-commerce",
        brand_guidelines="Minimalist style, brand colors: #FF0000, #FFFFFF",
        website="https://acmebrand.com",
    )
    db_session.add(profile)
    db_session.commit()

    assert profile.id is not None
    assert user.client_profile is not None
    assert user.client_profile.company_name == "Acme Brand"

    # Cascade delete verification
    db_session.delete(user)
    db_session.commit()

    assert db_session.get(ClientProfile, profile.id) is None


# =============================================================================
# 4. ProjectRequest & Proposal Lifecycle Tests
# =============================================================================

def test_project_request_and_proposal_cascade(db_session: Session):
    client_user = User(email="buyer@brand.com", password_hash="pw", role="client")
    agency_ws = Workspace(name="Apex Agency")
    db_session.add_all([client_user, agency_ws])
    db_session.commit()

    request = ProjectRequest(
        client_user_id=client_user.id,
        agency_workspace_id=agency_ws.id,
        title="Spring Rebrand Launch",
        description="Need a 60s teaser for YouTube and 3x 15s cuts for TikTok",
        video_type="promo",
        target_platform="YouTube / TikTok",
        target_duration="60s",
        aspect_ratio="16:9 & 9:16",
        reference_links=json.dumps(["https://vimeo.com/example1", "https://vimeo.com/example2"]),
        budget="$3,000 - $5,000",
        status="submitted",
    )
    db_session.add(request)
    db_session.commit()

    assert request.id is not None
    assert request.reference_links_list == ["https://vimeo.com/example1", "https://vimeo.com/example2"]
    assert request.status == "submitted"

    # Agency submits proposal
    proposal = Proposal(
        request_id=request.id,
        agency_workspace_id=agency_ws.id,
        scope_description="Complete edit, dynamic sound design, kinetic typography",
        estimated_days=10,
        deliverables_summary="1x 60s master + 3x 15s cutdowns",
        status="pending",
    )
    db_session.add(proposal)
    db_session.commit()

    assert proposal.id is not None
    assert len(request.proposals) == 1
    assert request.proposals[0].estimated_days == 10

    # ProjectMessage pre-activation
    msg = ProjectMessage(
        request_id=request.id,
        sender_id=client_user.id,
        sender_role="client",
        content="Uploaded reference moodboard to assets folder.",
    )
    db_session.add(msg)
    db_session.commit()

    assert msg.id is not None
    assert len(request.messages) == 1

    # Deleting request cascades to proposals and messages
    db_session.delete(request)
    db_session.commit()

    assert db_session.get(Proposal, proposal.id) is None
    assert db_session.get(ProjectMessage, msg.id) is None


def test_project_request_non_list_json_resilience():
    """Verifies that non-list JSON strings in ProjectRequest.reference_links
    safely return [] and pass ProjectRequestResponse Pydantic validation.
    """
    non_list_payloads = [
        "null",
        "123",
        "{}",
        "true",
        "false",
        "\"string_literal\"",
        "3.14",
        "invalid json {",
        "",
    ]

    for payload in non_list_payloads:
        request = ProjectRequest(
            client_user_id=1,
            agency_workspace_id=1,
            title="Video Edit Brief",
            reference_links=payload,
            status="submitted",
        )

        assert request.reference_links_list == [], f"Failed on reference_links payload: {payload!r}"

        # Must pass Pydantic ProjectRequestResponse validation cleanly
        response = ProjectRequestResponse(
            id=1,
            client_user_id=1,
            agency_workspace_id=1,
            title=request.title,
            status=request.status,
            reference_links=request.reference_links_list,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert response.reference_links == []


# =============================================================================
# 5. Project Request_ID SET NULL Test
# =============================================================================

def test_project_request_id_foreign_key_ondelete_set_null(db_session: Session):
    client_user = User(email="client_setnull@brand.com", password_hash="pw", role="client")
    agency_ws = Workspace(name="SetNull Agency")
    db_session.add_all([client_user, agency_ws])
    db_session.commit()

    agency_client = Client(workspace_id=agency_ws.id, name="SetNull Client", memory_bank_id="bank_setnull_123")
    db_session.add(agency_client)
    db_session.commit()

    request = ProjectRequest(
        client_user_id=client_user.id,
        agency_workspace_id=agency_ws.id,
        title="Brief to Project Flow",
        status="accepted",
    )
    db_session.add(request)
    db_session.commit()

    project = Project(
        workspace_id=agency_ws.id,
        client_id=agency_client.id,
        name="Production Project from Brief",
        status="active",
        request_id=request.id,
    )
    db_session.add(project)
    db_session.commit()

    assert project.request_id == request.id
    assert project.request.id == request.id

    # Post-activation project message
    proj_msg = ProjectMessage(
        project_id=project.id,
        sender_id=client_user.id,
        sender_role="client",
        content="First cut review comments are in.",
    )
    db_session.add(proj_msg)
    db_session.commit()

    assert proj_msg.project_id == project.id


# =============================================================================
# 6. Pydantic v2 Schema Validation Tests
# =============================================================================

def test_client_register_input_validation():
    # Valid registration
    valid = ClientRegisterInput(
        email="test@brand.com",
        password="strongpassword123",
        full_name="Jane Client",
        company_name="Brand Co",
    )
    assert valid.email == "test@brand.com"
    assert valid.full_name == "Jane Client"

    # Password too short (<8)
    with pytest.raises(ValidationError):
        ClientRegisterInput(
            email="test@brand.com",
            password="short",
            full_name="Jane Client",
        )

    # Empty full name
    with pytest.raises(ValidationError):
        ClientRegisterInput(
            email="test@brand.com",
            password="strongpassword123",
            full_name="",
        )


def test_agency_register_input_validation():
    valid = AgencyRegisterInput(
        email="agency@test.com",
        password="strongpassword123",
        full_name="Owner Person",
        agency_name="Top Agency",
    )
    assert valid.agency_name == "Top Agency"

    # Agency name too short (<2)
    with pytest.raises(ValidationError):
        AgencyRegisterInput(
            email="agency@test.com",
            password="strongpassword123",
            full_name="Owner Person",
            agency_name="A",
        )


def test_project_request_create_input_validation():
    valid = ProjectRequestCreateInput(
        agency_workspace_id=1,
        title="Commercial Video Edit",
        video_type="commercial",
        target_duration="30s",
        status="submitted",
    )
    assert valid.title == "Commercial Video Edit"
    assert valid.status == "submitted"

    # Invalid status pattern (only 'draft' or 'submitted' allowed on create)
    with pytest.raises(ValidationError):
        ProjectRequestCreateInput(
            agency_workspace_id=1,
            title="Commercial Video Edit",
            status="accepted",
        )


def test_project_request_update_input_validation():
    valid = ProjectRequestUpdateInput(
        title="Updated Brief Title",
        status="under_review",
    )
    assert valid.status == "under_review"

    # Invalid status pattern for update
    with pytest.raises(ValidationError):
        ProjectRequestUpdateInput(status="invalid_status_xyz")


def test_proposal_create_input_validation():
    valid = ProposalCreateInput(
        scope_description="Complete high-end edit with sound and color",
        estimated_days=14,
        deliverables_summary="1 master cut, 3 social cutdowns",
    )
    assert valid.estimated_days == 14

    # Estimated days <= 0
    with pytest.raises(ValidationError):
        ProposalCreateInput(
            scope_description="Edit",
            estimated_days=0,
        )

    # Estimated days > 365
    with pytest.raises(ValidationError):
        ProposalCreateInput(
            scope_description="Edit",
            estimated_days=400,
        )


def test_project_message_create_input_validation():
    valid = ProjectMessageCreateInput(
        request_id=1,
        content="Is 4K resolution supported?",
    )
    assert valid.content == "Is 4K resolution supported?"

    # Empty content
    with pytest.raises(ValidationError):
        ProjectMessageCreateInput(
            request_id=1,
            content="",
        )


def test_agency_profile_update_and_response_schemas():
    portfolio = [
        PortfolioItem(
            title="SaaS Promo",
            video_url="https://vimeo.com/12345",
            thumbnail_url="https://vimeo.com/thumb.jpg",
            description="3D product visualization",
        )
    ]
    inp = AgencyProfileUpdateInput(
        tagline="High-impact visuals",
        description="Full-service studio",
        specializations=["3D", "Motion Graphics"],
        services=["Editing", "3D Animation"],
        portfolio=portfolio,
        contact_email="studio@example.com",
    )
    assert len(inp.portfolio) == 1
    assert inp.portfolio[0].title == "SaaS Promo"

    resp = AgencyProfileResponse(
        id=1,
        workspace_id=10,
        workspace_name="Studio X",
        tagline=inp.tagline,
        description=inp.description,
        specializations=inp.specializations,
        services=inp.services,
        portfolio=inp.portfolio,
        contact_email=inp.contact_email,
        is_published=True,
        published_at=datetime.now(UTC),
        is_ready_to_publish=True,
        missing_publish_fields=[],
    )
    assert resp.is_published is True
    assert resp.workspace_name == "Studio X"
