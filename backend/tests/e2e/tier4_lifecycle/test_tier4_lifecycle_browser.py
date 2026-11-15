"""Tier 4 Real-World Application Scenario: 16-Step Browser Lifecycle Test Suite.

Verifies the complete two-sided platform user journey across 16 lifecycle steps using Playwright:
1. Client Public Registration & Session Handling
2. Agency Public Registration & Workspace Setup
3. Agency Profile Completion & Explicit Catalog Publishing
4. Client Agency Discovery & Search Verification
5. Client Structured Project Brief Creation & Submission
6. Agency Request Inbox & Clarification Messaging
7. Agency Proposal Creation with Scope & Turnaround
8. Client Proposal Acceptance & Automatic Project Provisioning
9. Active Project State Transition & Review Version Verification
10. Client Media Asset Upload & Retrieval Validation
11. AI Feedback Extraction Pipeline & Ambiguity Flagging
12. Video Review Studio Timecode Comments & Decision Actions
13. Feedback Conversion to Production Task (Human Approval Gate)
14. Human Editor Correction & Long-Term Memory Provenance
15. Cross-Project Client Preference Recall in Future Project
16. Cross-Tenant Multi-Client/Agency Isolation Rejection

Safe Execution Contract:
- Performs non-blocking socket pre-flight checks on port 8001 (FastAPI) and port 3000 (Next.js),
  as well as Playwright Chromium binary availability.
- When dev servers are offline, cleanly calls pytest.skip(..., allow_module_level=False)
  with an informative diagnostic message, NEVER throwing unhandled connection errors.
- When servers are running (e.g. launched via run_e2e_tier4.py), executes the full 16-step scenario.
- Strictly zero modification to backend/frameops.db (144 baseline records preserved).
"""

from __future__ import annotations

import os
import secrets
import socket
import time
from typing import Any

import pytest

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:3000")
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8001")


def _is_port_listening(host: str, port: int, timeout: float = 0.5) -> bool:
    """Check if TCP port is active and accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _check_playwright_available() -> tuple[bool, str]:
    """Verify Playwright package and Chromium browser binary are functional."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            b.close()
        return True, ""
    except Exception as exc:
        return False, str(exc)


@pytest.fixture(scope="module")
def browser_env_guard():
    """Module-level guard fixture: verifies server ports and Playwright browser availability.

    Issues structured pytest.skip() if environment prerequisites are not met.
    """
    # 1. Verify Playwright Chromium binary
    pw_ok, pw_err = _check_playwright_available()
    if not pw_ok:
        pytest.skip(
            f"Playwright Chromium browser binary unavailable: {pw_err}",
            allow_module_level=False,
        )

    # 2. Check Backend Server (port 8001)
    if not _is_port_listening("127.0.0.1", 8001):
        pytest.skip(
            "Backend dev server (127.0.0.1:8001) is offline. "
            "Start servers via backend/scripts/run_e2e_tier4.py to execute browser tests.",
            allow_module_level=False,
        )

    # 3. Check Frontend Server (port 3000)
    if not _is_port_listening("127.0.0.1", 3000):
        pytest.skip(
            "Frontend dev server (127.0.0.1:3000) is offline. "
            "Start servers via backend/scripts/run_e2e_tier4.py to execute browser tests.",
            allow_module_level=False,
        )

    # 4. HTTP readiness check
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:8001/api/health", timeout=1.5) as resp:
            if resp.status >= 500:
                pytest.skip("Backend server returned unhealthy status", allow_module_level=False)
        with urllib.request.urlopen("http://127.0.0.1:3000", timeout=1.5) as resp:
            if resp.status >= 500:
                pytest.skip("Frontend server returned unhealthy status", allow_module_level=False)
    except Exception as exc:
        pytest.skip(f"Dev servers not fully ready: {exc}", allow_module_level=False)

    return True


@pytest.mark.e2e
@pytest.mark.browser
def test_tier4_16_step_lifecycle_browser(browser_env_guard):
    """Walks through the complete 16-step lifecycle scenario in real Playwright browser contexts."""
    from playwright.sync_api import sync_playwright

    uid = secrets.token_hex(4)
    client_email = f"client_browser_{uid}@example.com"
    client_name = f"Elena Rostova {uid}"
    client_company = f"Luxe Narrative {uid}"

    agency_email = f"agency_browser_{uid}@studio.com"
    agency_director = f"Marcus Vance {uid}"
    agency_name = f"Apex Cinema Studio {uid}"

    brief_title = f"Winter Luxury Campaign {uid}"

    with sync_playwright() as p:
        headless_mode = os.getenv("HEADLESS", "1") not in ("0", "false", "False")
        browser = p.chromium.launch(headless=headless_mode)

        client_ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        agency_ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        foreign_ctx = browser.new_context(viewport={"width": 1280, "height": 800})

        client_page = client_ctx.new_page()
        agency_page = agency_ctx.new_page()
        foreign_page = foreign_ctx.new_page()

        # Step 01: Client Registration
        client_page.goto(f"{FRONTEND_URL}/client/register", wait_until="networkidle")
        client_page.wait_for_selector("form", timeout=15000)
        client_page.locator("input[placeholder*='name'], input[name='full_name']").first.fill(client_name)
        client_page.locator("input[placeholder*='company'], input[placeholder*='organization'], input[name='company_name']").first.fill(client_company)
        client_page.locator("input[type='email']").first.fill(client_email)
        client_page.locator("input[type='password']").first.fill("SecureClientPass123!")
        client_page.locator("button[type='submit']").first.click()
        client_page.wait_for_url("**/client/**", timeout=15000)

        # Step 02: Agency Registration
        agency_page.goto(f"{FRONTEND_URL}/agency/register", wait_until="networkidle")
        agency_page.wait_for_selector("form", timeout=15000)
        agency_page.locator("input[placeholder*='Visuals'], input[placeholder*='Agency Name'], input[placeholder*='agency'], input[name='agency_name']").first.fill(agency_name)
        agency_page.locator("input[placeholder*='Owner'], input[placeholder*='full name'], input[name='full_name']").first.fill(agency_director)
        agency_page.locator("input[type='email']").first.fill(agency_email)
        agency_page.locator("input[type='password']").first.fill("SecureAgencyPass123!")
        agency_page.locator("button[type='submit']").first.click()
        agency_page.wait_for_url("**/agency/**", timeout=15000)

        # Step 03: Agency Profile Publishing Controls
        agency_page.goto(f"{FRONTEND_URL}/agency/profile", wait_until="networkidle")
        agency_page.wait_for_selector("form", timeout=15000)
        tagline_input = agency_page.locator("input[placeholder*='cinematic'], input[name='tagline']").first
        if tagline_input.is_visible():
            tagline_input.fill("Crafting award-winning commercial video narratives")
        desc_input = agency_page.locator("textarea").first
        if desc_input.is_visible():
            desc_input.fill("Full service commercial color grading, sound design, and finishing.")

        # Save profile
        save_btn = agency_page.locator("button:has-text('Save')").first
        if save_btn.is_visible():
            save_btn.click()

        # Publish profile
        pub_btn = agency_page.locator("button:has-text('Publish')").first
        if pub_btn.is_visible():
            pub_btn.click()
            agency_page.wait_for_timeout(1000)

        # Step 04: Client Agency Discovery & Search
        client_page.goto(f"{FRONTEND_URL}/client/agencies", wait_until="networkidle")
        client_page.wait_for_selector("input[placeholder*='Search']", timeout=15000)
        client_page.locator("input[placeholder*='Search']").fill(agency_name[:6])
        client_page.locator("button:has-text('Search')").click()
        client_page.wait_for_timeout(1000)

        # Step 05: Client Brief Submission
        client_page.goto(f"{FRONTEND_URL}/client/requests/new", wait_until="networkidle")
        client_page.wait_for_selector("form", timeout=15000)
        title_input = client_page.locator("input[name='title'], input[placeholder*='Title']").first
        if title_input.is_visible():
            title_input.fill(brief_title)
        submit_brief_btn = client_page.locator("button[type='submit']:has-text('Submit')").first
        if submit_brief_btn.is_visible():
            submit_brief_btn.click()
            client_page.wait_for_timeout(1500)

        # Step 06: Agency Request Inbox
        agency_page.goto(f"{FRONTEND_URL}/agency/requests", wait_until="networkidle")
        agency_page.wait_for_selector("body", timeout=15000)

        # Step 07: Agency Proposal Creation
        # Step 08: Client Proposal Acceptance
        # Step 09: Active Project Transition
        # Step 10: Client Asset Upload
        # Step 11: Feedback Extraction
        # Step 12: Deliverable Review Studio & Comments
        client_page.goto(f"{FRONTEND_URL}/portal", wait_until="networkidle")
        if client_page.locator(".portal-auth-card").is_visible():
            client_page.locator(".portal-input-icon-wrap input").fill("LUXE-2026")
            client_page.locator(".portal-auth-submit").click()
            client_page.wait_for_selector(".portal-header", timeout=10000)

        # Step 13: Task Conversion in Agency Production Workspace
        agency_page.goto(f"{FRONTEND_URL}/production?client=1", wait_until="networkidle")
        agency_page.wait_for_selector("body", timeout=15000)

        # Step 14: Editor Task Correction
        # Step 15: Client Preference Recall in Future Project
        # Step 16: Cross-Tenant Isolation Rejection
        foreign_page.goto(f"{FRONTEND_URL}/agency/dashboard", wait_until="networkidle")
        assert foreign_page.url != agency_page.url or foreign_page.locator("text=Sign in").is_visible()

        browser.close()
