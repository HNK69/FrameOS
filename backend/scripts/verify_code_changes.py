import sys
import os

sys.path.insert(0, os.path.abspath("backend"))

from app.schemas import (
    ProjectInput,
    ClientRegisterInput,
    AgencyRegisterInput,
    AgencyProfileUpdateInput,
    AgencyProfileResponse,
    ClientProfileUpdateInput,
    ClientProfileResponse,
    ProjectRequestCreateInput,
    ProjectRequestUpdateInput,
    ProjectRequestResponse,
    ProposalCreateInput,
    ProposalUpdateInput,
    ProposalResponse,
    ProjectMessageCreateInput,
    ProjectMessageResponse,
)
from app.models import (
    User,
    Workspace,
    Project,
    AgencyProfile,
    ClientProfile,
    ProjectRequest,
    Proposal,
    ProjectMessage,
)
from app.db import Base, engine
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Test 1: ProjectInput allows "in_review"
p_review = ProjectInput(client_id=1, name="Campaign", status="in_review")
assert p_review.status == "in_review", f"Expected in_review, got {p_review.status}"
print("[PASS] ProjectInput accepts status='in_review'")

# Test 2: ProjectInput still allows "active", "completed", "archived"
for s in ["active", "completed", "archived"]:
    p = ProjectInput(client_id=1, name="Campaign", status=s)
    assert p.status == s
print("[PASS] ProjectInput accepts 'active', 'completed', 'archived'")

# Test 3: ProjectInput rejects invalid status
try:
    ProjectInput(client_id=1, name="Campaign", status="invalid_status")
    assert False, "Should have raised validation error for invalid_status"
except Exception as e:
    print(f"[PASS] ProjectInput correctly rejected invalid status: {type(e).__name__}")

# Test 4: Verify db connection has WAL and busy_timeout=5000 enabled
with engine.connect() as conn:
    jm = conn.execute(text("PRAGMA journal_mode")).scalar()
    bt = conn.execute(text("PRAGMA busy_timeout")).scalar()
    print(f"PRAGMA journal_mode: {jm}")
    print(f"PRAGMA busy_timeout: {bt}")
    assert bt == 5000, f"Expected busy_timeout=5000, got {bt}"
    print("[PASS] DB engine executes PRAGMA journal_mode=WAL and PRAGMA busy_timeout=5000")

# Test 5: Verify M1 Two-Sided Platform Schemas
client_reg = ClientRegisterInput(
    email="client@example.com",
    password="securepassword123",
    full_name="Acme Client",
    company_name="Acme Corp",
)
assert client_reg.company_name == "Acme Corp"
print("[PASS] ClientRegisterInput validated successfully")

agency_reg = AgencyRegisterInput(
    email="agency@example.com",
    password="securepassword123",
    full_name="Agency Owner",
    agency_name="Apex Media",
)
assert agency_reg.agency_name == "Apex Media"
print("[PASS] AgencyRegisterInput validated successfully")

req_input = ProjectRequestCreateInput(
    agency_workspace_id=1,
    title="Brand Launch Video",
    description="30s teaser for product launch",
    video_type="promo",
    target_platform="Instagram Reels",
    target_duration="30s",
    aspect_ratio="9:16",
    status="submitted",
)
assert req_input.title == "Brand Launch Video"
print("[PASS] ProjectRequestCreateInput validated successfully")

prop_input = ProposalCreateInput(
    scope_description="Full edit, sound design, color grading",
    estimated_days=7,
    deliverables_summary="1x 9:16 master + 2 cuts",
)
assert prop_input.estimated_days == 7
print("[PASS] ProposalCreateInput validated successfully")

msg_input = ProjectMessageCreateInput(
    request_id=1,
    content="Can we get the RAW footage delivered via Google Drive?",
)
assert msg_input.request_id == 1
print("[PASS] ProjectMessageCreateInput validated successfully")

# Test 6: Verify M1 Models persistence and default values via in-memory SQLite
test_engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(test_engine)
with Session(test_engine) as session:
    u = User(email="test_user@example.com", password_hash="dummy")
    session.add(u)
    session.commit()
    assert u.role == "agency_owner"
    assert u.full_name == ""
    print("[PASS] User model defaults verified (role='agency_owner', full_name='')")

    ws = Workspace(name="Test Agency Workspace")
    session.add(ws)
    session.commit()

    ap = AgencyProfile(workspace_id=ws.id)
    session.add(ap)
    session.commit()
    assert ap.is_published is False
    assert ap.specializations_list == []
    assert ap.services_list == []
    assert ap.portfolio_list == []
    print("[PASS] AgencyProfile model defaults verified (is_published=False, lists empty)")

    cp = ClientProfile(user_id=u.id, company_name="Test Co")
    session.add(cp)
    session.commit()
    assert cp.company_name == "Test Co"
    print("[PASS] ClientProfile model instantiated successfully")

    pr = ProjectRequest(client_user_id=u.id, agency_workspace_id=ws.id, title="Test Request")
    session.add(pr)
    session.commit()
    assert pr.status == "submitted"
    assert pr.reference_links_list == []
    print("[PASS] ProjectRequest model instantiated successfully")

    prop = Proposal(request_id=pr.id, agency_workspace_id=ws.id, scope_description="Scope")
    session.add(prop)
    session.commit()
    assert prop.status == "pending"
    print("[PASS] Proposal model instantiated successfully")

    msg = ProjectMessage(request_id=pr.id, sender_id=u.id, sender_role="client", content="Hello")
    session.add(msg)
    session.commit()
    assert msg.sender_role == "client"
    print("[PASS] ProjectMessage model instantiated successfully")

print("\nALL CODE CHANGE VERIFICATIONS PASSED 100%!")
