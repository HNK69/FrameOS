"""Tier 1 Feature 4 Tests: Agency Discovery Catalog & Search.

Coverage:
16. test_tier1_f4_discovery_list_published_agencies: Public catalog returns only agencies with is_published=True.
17. test_tier1_f4_discovery_search_by_name: Search query filters agencies by studio/workspace name.
18. test_tier1_f4_discovery_filter_by_specialization: Discovery filter matches agencies having specified specialization.
19. test_tier1_f4_discovery_filter_by_service: Discovery filter matches agencies providing specified service.
20. test_tier1_f4_discovery_get_single_agency_details: Public profile route returns full AgencyDiscoveryItem for published agency.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import AgencyProfile, Workspace
from app.schemas import AgencyDiscoveryItem
from . import progressive_check


def test_tier1_f4_discovery_list_published_agencies(agency_setup, foreign_agency_setup, isolated_db):
    """F4-1: Public discovery endpoint lists published agencies with real data."""
    def _fallback():
        with isolated_db() as db:
            published_profiles = db.scalars(
                select(AgencyProfile).where(AgencyProfile.is_published == True)
            ).all()
            assert len(published_profiles) >= 1
            for p in published_profiles:
                assert p.is_published is True

    with TestClient(app) as client:
        resp = client.get("/api/discovery/agencies")
        progressive_check(app, resp, "/api/discovery/agencies", _fallback)

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        for item in data:
            assert item.get("is_published", True) is True
            assert "workspace_id" in item
            assert "name" in item


def test_tier1_f4_discovery_search_by_name(agency_setup, isolated_db):
    """F4-2: Discovery search query filters agencies by workspace name."""
    def _fallback():
        with isolated_db() as db:
            ws = db.scalar(select(Workspace).where(Workspace.name.ilike("%Acme%")))
            assert ws is not None
            assert ws.id == agency_setup["workspace_id"]

    with TestClient(app) as client:
        resp = client.get("/api/discovery/agencies?query=Acme")
        progressive_check(app, resp, "/api/discovery/agencies", _fallback)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert any(item["workspace_id"] == agency_setup["workspace_id"] for item in data)


def test_tier1_f4_discovery_filter_by_specialization(agency_setup, isolated_db):
    """F4-3: Filter discovery catalog by agency specialization."""
    def _fallback():
        with isolated_db() as db:
            profile = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == agency_setup["workspace_id"]))
            assert profile is not None
            assert "cinematic" in profile.specializations_list or "commercial" in profile.specializations_list

    with TestClient(app) as client:
        resp = client.get("/api/discovery/agencies?specialization=commercial")
        progressive_check(app, resp, "/api/discovery/agencies", _fallback)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        for item in data:
            assert "commercial" in item.get("specializations", [])


def test_tier1_f4_discovery_filter_by_service(agency_setup, isolated_db):
    """F4-4: Filter discovery catalog by agency service offering."""
    def _fallback():
        with isolated_db() as db:
            profile = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == agency_setup["workspace_id"]))
            assert profile is not None
            assert "editing" in profile.services_list

    with TestClient(app) as client:
        resp = client.get("/api/discovery/agencies?service=editing")
        progressive_check(app, resp, "/api/discovery/agencies", _fallback)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        for item in data:
            assert "editing" in item.get("services", [])


def test_tier1_f4_discovery_get_single_agency_details(agency_setup, isolated_db):
    """F4-5: Public endpoint returns full agency profile details for a published agency."""
    ws_id = agency_setup["workspace_id"]

    def _fallback():
        with isolated_db() as db:
            profile = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == ws_id))
            assert profile is not None
            ws = db.get(Workspace, ws_id)
            item = AgencyDiscoveryItem(
                workspace_id=profile.workspace_id,
                name=ws.name if ws else "Acme Production Studio",
                tagline=profile.tagline,
                description=profile.description,
                specializations=profile.specializations_list,
                services=profile.services_list,
                portfolio=profile.portfolio_list,
                contact_email=profile.contact_email,
                website=profile.website,
                published_at=profile.published_at,
            )
            assert item.workspace_id == ws_id

    with TestClient(app) as client:
        resp = client.get(f"/api/discovery/agencies/{ws_id}")
        progressive_check(app, resp, f"/api/discovery/agencies/{ws_id}", _fallback)

        assert resp.status_code == 200
        data = resp.json()
        assert data["workspace_id"] == ws_id
        assert data["name"] == "Acme Production Studio"
        assert "contact_email" in data
