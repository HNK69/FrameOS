import asyncio
import os
import sys

import pytest

from app.config import settings
from app.services import openclaw


def run_selector_loop(coroutine):
    # Mirrors the Windows loop configuration that cannot create subprocess transports.
    loop = asyncio.SelectorEventLoop()
    try:
        return loop.run_until_complete(coroutine)
    finally:
        loop.close()


def test_gateway_settings_are_forwarded_to_cli_environment(monkeypatch):
    monkeypatch.setattr(settings, "openclaw_gateway_url", "wss://gateway.example.test")
    monkeypatch.setattr(settings, "openclaw_auth_token", "isolated-test-token")

    env = openclaw._gateway_environment()

    assert env["OPENCLAW_GATEWAY_URL"] == "wss://gateway.example.test"
    assert env["OPENCLAW_GATEWAY_TOKEN"] == "isolated-test-token"


def test_windows_npm_shim_resolves_to_direct_node_entrypoint(tmp_path, monkeypatch):
    npm_prefix = tmp_path / "npm-prefix"
    shim_dir = npm_prefix / "node_modules" / ".bin"
    package_dir = npm_prefix / "node_modules" / "openclaw"
    shim_dir.mkdir(parents=True)
    package_dir.mkdir(parents=True)
    shim = shim_dir / "openclaw.cmd"
    entrypoint = package_dir / "openclaw.mjs"
    node = tmp_path / "node.exe"
    shim.write_text("@echo off\n", encoding="utf-8")
    entrypoint.write_text("", encoding="utf-8")
    monkeypatch.setattr(settings, "openclaw_node_bin", str(node))

    command = openclaw._cli_command(str(shim), ["agent", "--message", "a & b"])

    assert command == [str(node), str(entrypoint), "agent", "--message", "a & b"]


def test_windows_cli_path_runs_off_loop_and_captures_output(monkeypatch):
    monkeypatch.setattr(openclaw, "_uses_windows_threaded_subprocess", lambda: True)
    env = os.environ.copy()
    env["FRAMEOPS_TEST_GATEWAY_TOKEN"] = "isolated-test-token"
    code = (
        "import os,sys,time; time.sleep(.15); "
        "print(os.environ['FRAMEOPS_TEST_GATEWAY_TOKEN']); "
        "print('child diagnostic', file=sys.stderr)"
    )

    async def exercise():
        task = asyncio.create_task(
            openclaw._execute_cli([sys.executable, "-c", code], env, timeout=3)
        )
        await asyncio.sleep(0.03)
        assert not task.done(), "waiting for the child must not block the Uvicorn event loop"
        return await task

    result = run_selector_loop(exercise())
    assert result.returncode == 0
    assert result.stdout.decode().strip() == "isolated-test-token"
    assert result.stderr.decode().strip() == "child diagnostic"


def test_windows_cli_path_enforces_process_timeout(monkeypatch):
    monkeypatch.setattr(openclaw, "_uses_windows_threaded_subprocess", lambda: True)
    code = "import time; time.sleep(2)"

    with pytest.raises(TimeoutError, match="timed out"):
        run_selector_loop(openclaw._execute_cli([sys.executable, "-c", code], os.environ.copy(), timeout=0.1))


def test_synthesis_memory_evidence_keeps_provenance_and_drops_retrieval_payload():
    compact = openclaw._memory_evidence({"results": [{
        "text": "Client prefers understated music.",
        "context": "editor interpretation; unconfirmed",
        "document_id": "source-document",
        "tags": ["editor_interpretation", "unconfirmed"],
        "scores": {"final": 0.84, "semantic": 0.74, "keyword": 0.9},
        "entities": ["client", "music"],
    }]})

    assert compact == [{
        "evidence": "Client prefers understated music.",
        "provenance": "editor interpretation; unconfirmed",
        "source": "source-document",
        "confirmation_and_tags": ["editor_interpretation", "unconfirmed"],
        "confidence": 0.84,
    }]
