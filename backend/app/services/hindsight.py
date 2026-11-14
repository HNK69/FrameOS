import asyncio
import math
import re

import httpx

from ..config import settings
from .groq import ServiceUnavailable


def configured() -> bool:
    return bool(settings.hindsight_api_url and settings.hindsight_api_token)


async def call_memory(method: str, bank_id: str, operation: str, payload: dict) -> dict:
    if not configured():
        raise ServiceUnavailable("Hindsight is not configured. Set HINDSIGHT_API_URL and HINDSIGHT_API_TOKEN.")
    path = {
        "retain": f"/v1/default/banks/{bank_id}/memories",
        "recall": f"/v1/default/banks/{bank_id}/memories/recall",
        "reflect": f"/v1/default/banks/{bank_id}/reflect",
        "list": f"/v1/default/banks/{bank_id}/memories",
        "delete_bank": f"/v1/default/banks/{bank_id}",
        "config": f"/v1/default/banks/{bank_id}/config",
    }[operation]
    headers = {"Authorization": f"Bearer {settings.hindsight_api_token}"}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(50, connect=8)) as client:
            response = await client.request(method, settings.hindsight_api_url.rstrip("/") + path,
                                            headers=headers, json=payload)
            response.raise_for_status()
            return response.json() if response.content else {}
    except httpx.HTTPStatusError as exc:
        if operation == "delete_bank" and exc.response.status_code == 404:
            return {"already_deleted": True}
        raise ServiceUnavailable(f"Hindsight {operation} failed with HTTP {exc.response.status_code}.") from exc
    except httpx.HTTPError as exc:
        raise ServiceUnavailable(f"Hindsight {operation} request failed: {type(exc).__name__}.") from exc


async def retain(bank_id: str, content: str, context: str, tags: list[str], document_id: str) -> dict:
    return await call_memory("POST", bank_id, "retain", {
        "items": [{"content": content, "context": context, "tags": tags, "document_id": document_id}],
    })


def _retained_content_matches(content: str, recalled: dict, document_id: str) -> bool:
    """Match Hindsight's distilled fact to its source document, not verbatim text."""
    stop_words = {"this", "that", "with", "from", "have", "will", "would", "could", "should", "please"}
    expected = {word for word in re.findall(r"[a-z0-9]+", content.casefold())
                if len(word) > 3 and word not in stop_words}
    if not expected:
        expected = set(re.findall(r"[a-z0-9]+", content.casefold()))
    records = recalled.get("results", recalled.get("memories", []))
    if not isinstance(records, list):
        return False
    source_records = [record for record in records
                      if isinstance(record, dict) and record.get("document_id") == document_id]
    if not source_records:
        return False
    recalled_text = " ".join(str(record.get("text", "")) for record in source_records).casefold()
    found = set(re.findall(r"[a-z0-9]+", recalled_text))
    overlap = len(expected & found) / len(expected)
    return overlap >= max(0.6, math.ceil(len(expected) * 0.6) / len(expected))


async def retain_and_verify(bank_id: str, content: str, context: str, tags: list[str], document_id: str) -> tuple[dict, bool]:
    """Wait for Hindsight's asynchronous indexing before reporting retention verified."""
    result = await retain(bank_id, content, context, tags, document_id)
    for delay in (1, 2, 3, 5, 5, 5):
        await asyncio.sleep(delay)
        recalled = await recall(bank_id, content)
        if _retained_content_matches(content, recalled, document_id):
            return result, True
    return result, False


async def recall(bank_id: str, query: str) -> dict:
    return await call_memory("POST", bank_id, "recall", {"query": query, "limit": 8})


async def reflect(bank_id: str, query: str) -> dict:
    return await call_memory("POST", bank_id, "reflect", {"query": query})


async def delete_bank(bank_id: str) -> dict:
    return await call_memory("DELETE", bank_id, "delete_bank", {})


async def ensure_bank(bank_id: str) -> dict:
    return await call_memory("PATCH", bank_id, "config", {
        "updates": {
            "reflect_mission": "Identify applicable client creative preferences, preserve conflicting history, and distinguish confirmed decisions from interpretations."
        }
    })
