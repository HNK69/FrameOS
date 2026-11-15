"""Deterministic Offline Mock for OpenClaw Synthesis with DaVinci Resolve Workflows.

Generates structured TaskDraft models with compliant DaVinci Resolve instructions,
supporting multi-tenant memory evidence injection and editor workflow verification.
"""

from __future__ import annotations

from typing import Any

from app.schemas import (
    SynthesisResult,
    TaskDraft,
)
from app.services.groq import ServiceUnavailable

VALID_RESOLVE_PAGES = {"Color page", "Fairlight", "Edit page", "Cut page", "Fusion", "Deliver"}


def verify_resolve_workflow(workflow: str) -> dict[str, Any]:
    """Validates that a resolve_workflow string complies with DaVinci Resolve standards."""
    if not workflow or not workflow.strip():
        return {"valid": False, "error": "resolve_workflow cannot be empty"}

    words = workflow.split()
    if len(words) > 20:
        return {"valid": False, "error": f"resolve_workflow exceeds word budget ({len(words)} > 20 words)"}

    has_page = any(page.lower() in workflow.lower() for page in VALID_RESOLVE_PAGES)
    if not has_page:
        return {"valid": False, "error": f"resolve_workflow must reference a DaVinci Resolve page ({VALID_RESOLVE_PAGES})"}

    return {"valid": True, "error": None}


class MockOpenClawService:
    """Offline mock for OpenClaw synthesis producing valid DaVinci Resolve tasks."""

    def __init__(self) -> None:
        self.should_fail: bool = False
        self.failure_message: str = "OpenClaw agent subprocess failed"
        self.recorded_syntheses: list[dict[str, Any]] = []

    def reset(self) -> None:
        """Clear recorded syntheses and reset failure triggers."""
        self.should_fail = False
        self.failure_message = "OpenClaw agent subprocess failed"
        self.recorded_syntheses.clear()

    async def synthesize(
        self,
        *,
        run_id: int,
        attempt_count: int,
        client_name: str,
        project_name: str,
        extraction: dict,
        memories: dict | list,
        assets: list[dict],
    ) -> SynthesisResult:
        """Synthesize actionable DaVinci Resolve production tasks from extractions and memories."""
        self.recorded_syntheses.append({
            "run_id": run_id,
            "attempt_count": attempt_count,
            "client_name": client_name,
            "project_name": project_name,
            "extraction": extraction,
            "memories": memories,
            "assets": assets,
        })

        if self.should_fail:
            raise ServiceUnavailable(self.failure_message)

        tasks: list[TaskDraft] = []
        requests = extraction.get("requests", [])

        # Parse client preference memory evidence
        mem_items = memories if isinstance(memories, list) else memories.get("results", memories.get("memories", []))
        has_client_preference = bool(mem_items and len(mem_items) > 0)
        top_memory = mem_items[0]["text"] if has_client_preference and isinstance(mem_items[0], dict) else ""

        if not requests:
            # Baseline task when no explicit items extracted
            tasks.append(
                TaskDraft(
                    title="Timeline Review and Baseline Alignment",
                    category="editing",
                    instruction="Align timeline cuts with client narrative expectations.",
                    resolve_workflow="Edit page -> Timeline -> Review clip sequence and rhythm",
                    priority="medium",
                    source="current_feedback",
                    evidence="Initial review baseline",
                    confidence=0.88,
                    requires_confirmation=False,
                )
            )

        for req in requests:
            desc = req.get("description", "")
            cat = req.get("category", "editing").lower()
            is_inferred = req.get("classification") == "inferred" or req.get("requires_confirmation", False)

            # Map category to DaVinci Resolve page and workflow
            if "grading" in cat or "color" in desc.lower():
                title = f"Grade: {desc[:35]}"
                workflow = "Color page -> Primaries wheel -> Adjust temperature and offset warmth"
                task_cat = "grading"
            elif "audio" in cat or "music" in desc.lower() or "sound" in desc.lower():
                title = f"Audio: {desc[:35]}"
                workflow = "Fairlight page -> Track EQ & Dynamics -> Balance dialogue and stems"
                task_cat = "audio"
            elif "pacing" in cat or "trim" in desc.lower() or "cut" in desc.lower():
                title = f"Pacing: {desc[:35]}"
                workflow = "Edit page -> Timeline -> Ripple trim head and tail cuts"
                task_cat = "editing"
            elif "graphic" in cat or "logo" in desc.lower() or "title" in desc.lower():
                title = f"Graphics: {desc[:35]}"
                workflow = "Fusion page -> Text+ node -> Apply brand typeface and color"
                task_cat = "graphics"
            else:
                title = f"Task: {desc[:35]}"
                workflow = "Edit page -> Timeline -> Apply client revision"
                task_cat = "editing"

            evidence = req.get("source_quote") or desc
            source = "current_feedback"

            # Enrich with client preference memory if relevant
            if has_client_preference and any(w in top_memory.lower() for w in desc.lower().split() if len(w) > 4):
                evidence = f"Client memory: '{top_memory[:60]}' | Feedback: '{evidence[:60]}'"
                source = "client_memory"

            tasks.append(
                TaskDraft(
                    title=title,
                    category=task_cat,
                    instruction=desc[:120],
                    resolve_workflow=workflow,
                    priority="high" if any(w in desc.lower() for w in ["urgent", "critical", "immediately"]) else "medium",
                    source=source,
                    evidence=evidence[:180],
                    confidence=0.70 if is_inferred else 0.92,
                    requires_confirmation=is_inferred,
                )
            )

        # Inject recalled client preference task if present and not yet represented (Step 15)
        if has_client_preference and not any(t.source == "client_memory" for t in tasks):
            tasks.append(
                TaskDraft(
                    title="Apply Recalled Client Preference",
                    category="brand",
                    instruction=f"Respect client creative preference: {top_memory[:80]}",
                    resolve_workflow="Color page -> Gallery -> Load client-approved grade preset",
                    priority="medium",
                    source="client_memory",
                    evidence=f"Retrieved from client memory bank: {top_memory}",
                    confidence=0.96,
                    requires_confirmation=False,
                )
            )

        return SynthesisResult(tasks=tasks)
