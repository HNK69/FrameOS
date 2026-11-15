"""Tier 1 Feature 3 Tests: Agency Profile Publishing Controls.

Coverage:
11. test_tier1_f3_get_agency_profile: Agency owner can retrieve full AgencyProfileResponse.
12. test_tier1_f3_update_agency_profile_fields: Agency owner updates profile fields, reaching ready-to-publish state.
13. test_tier1_f3_publish_agency_profile_success: Explicit publish sets is_published=True and records published_at timestamp.
14. test_tier1_f3_unpublish_agency_profile: Agency owner can unpublish profile, setting is_published=False.
15. test_tier1_f3_portfolio_items_persistence: Portfolio items persist across updates and appear in subsequent profile reads.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
import pytest
from sqlalchemy import select

from app.main import app
from app.models import AgencyProfile
from app.schemas import AgencyProfileResponse, AgencyProfileUpdateInput, PortfolioItem
from . import progressive_check


def test_tier1_f3_get_agency_profile(agency_client, agency_setup, isolated_db):
    """F3-1: Retrieve agency profile schema and publication readiness status."""
    def _fallback():
        with isolated_db() as db:
            profile = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == agency_setup["workspace_id"]))
            assert profile is not None
            resp_model = AgencyProfileResponse(
                id=profile.id,
                workspace_id=profile.workspace_id,
                tagline=profile.tagline,
                description=profile.description,
                specializations=profile.specializations_list,
                services=profile.services_list,
                portfolio=profile.portfolio_list,
                contact_email=profile.contact_email,
                contact_phone=profile.contact_phone,
                website=profile.website,
                is_published=profile.is_published,
                published_at=profile.published_at,
                is_ready_to_publish=True,
                missing_publish_fields=[],
            )
            assert resp_model.workspace_id == agency_setup["workspace_id"]

    resp = agency_client.get("/api/agency/profile")
    progressive_check(app, resp, "/api/agency/profile", _fallback)

    assert resp.status_code == 200
    data = resp.json()
    assert data["workspace_id"] == agency_setup["workspace_id"]
    assert "is_published" in data
    assert "is_ready_to_publish" in data


def test_tier1_f3_update_agency_profile_fields(agency_client, agency_setup, isolated_db):
    """F3-2: Updating agency profile fields updates DB state and computes publication readiness."""
    payload = {
        "tagline": "Cinematic Cuts & Color",
        "description": "High end production boutique specialized in commercial editing.",
        "specializations": ["commercial", "cinematic"],
        "services": ["editing", "color_grading"],
        "contact_email": "hello@acmestudios.com",
        "website": "https://acmestudios.com",
    }

    def _fallback():
        validated = AgencyProfileUpdateInput(**payload)
        assert validated.tagline == "Cinematic Cuts & Color"
        with isolated_db() as db:
            profile = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == agency_setup["workspace_id"]))
            assert profile is not None
            profile.tagline = validated.tagline
            profile.description = validated.description
            profile.specializations = json.dumps(validated.specializations)
            profile.services = json.dumps(validated.services)
            profile.contact_email = validated.contact_email
            profile.website = validated.website
            db.commit()
            refreshed = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == agency_setup["workspace_id"]))
            assert refreshed.tagline == "Cinematic Cuts & Color"
            assert refreshed.specializations_list == ["commercial", "cinematic"]

    resp = agency_client.put("/api/agency/profile", json=payload)
    progressive_check(app, resp, "/api/agency/profile", _fallback)

    assert resp.status_code == 200
    data = resp.json()
    assert data["tagline"] == "Cinematic Cuts & Color"
    assert "commercial" in data["specializations"]
    assert data.get("is_ready_to_publish") is True


def test_tier1_f3_publish_agency_profile_success(agency_client, agency_setup, isolated_db):
    """F3-3: Explicit publish transitions profile to published state with UTC timestamp."""
    def _fallback():
        with isolated_db() as db:
            profile = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == agency_setup["workspace_id"]))
            assert profile is not None
            profile.is_published = True
            profile.published_at = datetime.now(UTC)
            db.commit()
            persisted = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == agency_setup["workspace_id"]))
            assert persisted.is_published is True
            assert persisted.published_at is not None

    resp = agency_client.post("/api/agency/profile/publish")
    progressive_check(app, resp, "/api/agency/profile/publish", _fallback)

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_published"] is True
    assert data["published_at"] is not None


def test_tier1_f3_unpublish_agency_profile(agency_client, agency_setup, isolated_db):
    """F3-4: Unpublishing marks profile as unpublished, removing it from public discovery."""
    def _fallback():
        with isolated_db() as db:
            profile = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == agency_setup["workspace_id"]))
            assert profile is not None
            profile.is_published = False
            db.commit()
            persisted = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == agency_setup["workspace_id"]))
            assert persisted.is_published is False

    resp = agency_client.post("/api/agency/profile/unpublish")
    progressive_check(app, resp, "/api/agency/profile/unpublish", _fallback)

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_published"] is False


def test_tier1_f3_portfolio_items_persistence(agency_client, agency_setup, isolated_db):
    """F3-5: Structured portfolio items are persisted and returned in agency profile."""
    portfolio_payload = [
        {"title": "Nike Air Campaign", "video_url": "https://vimeo.com/123456", "description": "Color pass and sound edit"},
        {"title": "Spotify Spot", "video_url": "https://youtube.com/watch?v=abc", "description": "Fast cuts"},
    ]
    payload = {"portfolio": portfolio_payload}

    def _fallback():
        validated_items = [PortfolioItem(**item) for item in portfolio_payload]
        assert len(validated_items) == 2
        with isolated_db() as db:
            profile = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == agency_setup["workspace_id"]))
            assert profile is not None
            profile.portfolio = json.dumps([item.model_dump() for item in validated_items])
            db.commit()
            refreshed = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == agency_setup["workspace_id"]))
            assert len(refreshed.portfolio_list) == 2
            assert refreshed.portfolio_list[0]["title"] == "Nike Air Campaign"

    resp = agency_client.put("/api/agency/profile", json=payload)
    progressive_check(app, resp, "/api/agency/profile", _fallback)

    assert resp.status_code == 200
    get_resp = agency_client.get("/api/agency/profile")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert len(data.get("portfolio", [])) == 2
    assert data["portfolio"][0]["title"] == "Nike Air Campaign"
