"""Deterministic Offline In-Memory Mock for Hindsight Multi-Tenant Memory API.

Provides stateful, in-memory client preference storage with strict bank_id tenant isolation,
supporting retain, recall, reflect, retain_and_verify, ensure_bank, and delete_bank operations.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.services.groq import ServiceUnavailable


class MockHindsightService:
    """In-memory multi-tenant memory bank mock for Hindsight API.

    Guarantees strict tenant isolation by scoping all memories directly to bank_id.
    """

    def __init__(self) -> None:
        self._banks: dict[str, list[dict[str, Any]]] = {}
        self.is_configured: bool = True
        self.should_fail: bool = False
        self.failure_message: str = "Hindsight cluster unavailable"
        self.recorded_calls: list[dict[str, Any]] = []

    def reset(self) -> None:
        """Clear memory banks and reset error simulation triggers."""
        self._banks.clear()
        self.is_configured = True
        self.should_fail = False
        self.failure_message = "Hindsight cluster unavailable"
        self.recorded_calls.clear()

    def configured(self) -> bool:
        """Check whether the memory service is configured."""
        return self.is_configured

    def seed_memory(
        self,
        bank_id: str,
        content: str,
        context: str = "seed",
        tags: list[str] | None = None,
        document_id: str = "seed-doc",
    ) -> dict[str, Any]:
        """Test helper to pre-seed client memories into a specific tenant bank."""
        mem_id = f"mem-seed-{uuid4().hex[:8]}"
        record = {
            "id": mem_id,
            "document_id": document_id,
            "text": content,
            "context": context,
            "tags": tags or ["frameops", "seed"],
            "created_at": datetime.now(UTC).isoformat(),
            "scores": {"final": 0.98, "semantic": 0.95, "keyword": 1.0},
        }
        self._banks.setdefault(bank_id, []).append(record)
        return record

    async def call_memory(self, method: str, bank_id: str, operation: str, payload: dict) -> dict:
        """Dispatch simulated Hindsight HTTP operations with tenant isolation."""
        self.recorded_calls.append({
            "method": method,
            "bank_id": bank_id,
            "operation": operation,
            "payload": payload,
        })
        if self.should_fail:
            raise ServiceUnavailable(f"Hindsight {operation} failed: {self.failure_message}")

        if operation == "retain":
            items = payload.get("items", [])
            results = []
            for item in items:
                mem_id = f"mem-{uuid4().hex[:10]}"
                doc_id = item.get("document_id") or f"doc-{uuid4().hex[:8]}"
                rec = {
                    "id": mem_id,
                    "document_id": doc_id,
                    "text": item.get("content", ""),
                    "context": item.get("context", ""),
                    "tags": item.get("tags", []),
                    "created_at": datetime.now(UTC).isoformat(),
                    "scores": {"final": 0.92, "semantic": 0.88, "keyword": 0.95},
                }
                self._banks.setdefault(bank_id, []).append(rec)
                results.append(rec)
            return {"results": results, "status": "stored"}

        elif operation == "recall":
            query = payload.get("query", "").lower()
            limit = payload.get("limit", 8)
            records = self._banks.get(bank_id, [])

            # Relevance filtering by keyword overlap within the tenant bank
            query_tokens = set(re.findall(r"[a-z0-9]+", query))
            stop_words = {"this", "that", "with", "from", "have", "will", "would", "could", "should", "please", "the", "and"}
            query_words = {w for w in query_tokens if len(w) > 2 and w not in stop_words}

            matches = []
            for r in records:
                text_lower = r["text"].lower()
                text_tokens = set(re.findall(r"[a-z0-9]+", text_lower))
                overlap = len(query_words & text_tokens)
                if overlap > 0 or not query_words:
                    matches.append(r)

            return {"results": matches[:limit]}

        elif operation == "list":
            return {"results": self._banks.get(bank_id, [])}

        elif operation == "delete_bank":
            self._banks.pop(bank_id, None)
            return {"status": "deleted"}

        elif operation in ("config", "reflect"):
            return {"status": "ok", "bank_id": bank_id}

        return {}

    async def retain(self, bank_id: str, content: str, context: str, tags: list[str], document_id: str) -> dict:
        """Store client memory in isolated bank."""
        return await self.call_memory("POST", bank_id, "retain", {
            "items": [{"content": content, "context": context, "tags": tags, "document_id": document_id}],
        })

    async def recall(self, bank_id: str, query: str) -> dict:
        """Retrieve relevant client memories from isolated bank."""
        return await self.call_memory("POST", bank_id, "recall", {"query": query, "limit": 8})

    async def retain_and_verify(
        self, bank_id: str, content: str, context: str, tags: list[str], document_id: str
    ) -> tuple[dict, bool]:
        """Synchronously retain and verify memory existence without polling delays."""
        result = await self.retain(bank_id, content, context, tags, document_id)
        records = self._banks.get(bank_id, [])
        verified = any(r.get("document_id") == document_id for r in records)
        return result, verified

    async def reflect(self, bank_id: str, query: str) -> dict:
        """Synthesize high-level patterns across retained memories."""
        return await self.call_memory("POST", bank_id, "reflect", {"query": query})

    async def ensure_bank(self, bank_id: str) -> dict:
        """Ensure tenant memory bank exists."""
        self._banks.setdefault(bank_id, [])
        return {"status": "ensured", "bank_id": bank_id}

    async def delete_bank(self, bank_id: str) -> dict:
        """Delete tenant memory bank."""
        return await self.call_memory("DELETE", bank_id, "delete_bank", {})
