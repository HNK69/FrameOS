#!/usr/bin/env python3
"""Tier 4 16-Step Lifecycle Scenario Test Runner for FRAMEOPS.

Orchestrates backend (FastAPI on port 8001) and frontend (Next.js on port 3000),
isolates the database while preserving the 144 baseline operational records in frameops.db,
and executes E2E verification suites on Windows with robust process tree management.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import time

# Paths
SCRIPTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPTS_DIR.parent
ROOT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
ACTIVE_DB = BACKEND_DIR / "frameops.db"
TEST_DB = BACKEND_DIR / ".frameops_e2e.db"

# Canonical baseline database hash post-migration
BASELINE_DB_SHA = "c1ad5da27f48ae22e9aacd8f509847da64171ba831f400d7bf19e9882de3724f"


def calculate_sha256(path: Path) -> str:
    """Compute SHA-256 digest of a file."""
    if not path.is_file():
        return ""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check whether a local TCP port is already bound."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def kill_process_tree(pid: int) -> None:
    """Forcefully terminate process and all its children on Windows/POSIX."""
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception as e:
            print(f"[WARN] Failed to taskkill PID {pid}: {e}")
    else:
        try:
            import signal
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception as e:
            print(f"[WARN] Failed to kill PID {pid}: {e}")


def wait_for_health(url: str, timeout: float = 45.0, interval: float = 0.5) -> bool:
    """Poll URL until a response status < 500 is returned or timeout expires."""
    import urllib.error
    import urllib.request

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "FrameOPS-E2E-HealthCheck"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status < 500:
                    return True
        except (urllib.error.URLError, TimeoutError, ConnectionRefusedError, OSError):
            pass
        time.sleep(interval)
    return False


def verify_active_db_invariants(expected_sha: str | None = None) -> None:
    """Assert active DB hash unchanged, PRAGMA checks pass, and 144 baseline records intact."""
    if not ACTIVE_DB.is_file():
        raise FileNotFoundError(f"Active database not found at {ACTIVE_DB}")

    target_sha = expected_sha or BASELINE_DB_SHA
    current_sha = calculate_sha256(ACTIVE_DB)
    if current_sha != target_sha:
        raise RuntimeError(
            f"FATAL INTEGRITY VIOLATION: Active database {ACTIVE_DB} WAS MODIFIED! "
            f"Expected: {target_sha}, Actual: {current_sha}"
        )

    conn = sqlite3.connect(ACTIVE_DB)
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA integrity_check")
        integrity = cur.fetchall()
        if integrity != [("ok",)]:
            raise RuntimeError(f"FATAL: PRAGMA integrity_check failed on active DB: {integrity}")

        cur.execute("PRAGMA foreign_key_check")
        fk = cur.fetchall()
        if fk != []:
            raise RuntimeError(f"FATAL: PRAGMA foreign_key_check failed on active DB: {fk}")

        baseline_counts = {
            "users": 1,
            "workspaces": 1,
            "memberships": 1,
            "clients": 9,
            "projects": 13,
            "transcripts": 16,
            "processing_runs": 16,
            "extracted_items": 56,
            "memory_operations": 31,
        }
        total_records = 0
        for tbl, expected in baseline_counts.items():
            cur.execute(f'SELECT COUNT(*) FROM "{tbl}"')
            actual = cur.fetchone()[0]
            if actual != expected:
                raise RuntimeError(
                    f"FATAL: Record count mismatch in '{tbl}': expected {expected}, got {actual}"
                )
            total_records += actual

        if total_records != 144:
            raise RuntimeError(f"FATAL: Expected 144 total baseline records, found {total_records}")

        print(
            f"Active database integrity verified: SHA-256 untouched ({current_sha[:8]}...) "
            f"and all 144 baseline records preserved."
        )
    finally:
        conn.close()


class E2EServerManager:
    """Context manager for orchestrating backend and frontend test servers."""

    def __init__(
        self,
        backend_port: int = 8001,
        frontend_port: int = 3000,
        api_only: bool = False,
        timeout: float = 45.0,
        cleanup_db: bool = True,
        live_mode: bool = False,
    ) -> None:
        self.backend_port = backend_port
        self.frontend_port = frontend_port
        self.api_only = api_only
        self.timeout = timeout
        self.cleanup_db = cleanup_db
        self.live_mode = live_mode
        self.backend_proc: subprocess.Popen | None = None
        self.frontend_proc: subprocess.Popen | None = None
        self.initial_active_db_sha = ""

    def __enter__(self) -> E2EServerManager:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    def start(self) -> None:
        print("[1/5] Checking ports availability...")
        if is_port_in_use(self.backend_port):
            raise RuntimeError(f"Backend port {self.backend_port} is already in use. Please terminate existing process.")
        if not self.api_only and is_port_in_use(self.frontend_port):
            raise RuntimeError(f"Frontend port {self.frontend_port} is already in use. Please terminate existing process.")

        print("[2/5] Creating isolated clone of active database...")
        if not ACTIVE_DB.is_file():
            raise FileNotFoundError(f"Active database not found at {ACTIVE_DB}")
        self.initial_active_db_sha = calculate_sha256(ACTIVE_DB)

        # Copy database and associated WAL/SHM files
        shutil.copy2(ACTIVE_DB, TEST_DB)
        for ext in ("-wal", "-shm"):
            p = Path(str(ACTIVE_DB) + ext)
            if p.is_file():
                shutil.copy2(p, Path(str(TEST_DB) + ext))

        print(f"      Cloned {ACTIVE_DB.name} -> {TEST_DB.name} (SHA: {self.initial_active_db_sha[:12]}...)")

        # 3. Start Backend
        print(f"[3/5] Starting FastAPI backend on port {self.backend_port}...")
        python_exe = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
        if not python_exe.is_file():
            python_exe = Path(sys.executable)

        backend_env = os.environ.copy()
        backend_env["DATABASE_URL"] = f"sqlite:///{TEST_DB.resolve().as_posix()}"
        backend_env["PORT"] = str(self.backend_port)
        if self.live_mode:
            backend_env["FRAMEOPS_LIVE_SERVICES"] = "1"

        backend_cmd = [
            str(python_exe),
            "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1",
            "--port", str(self.backend_port),
        ]
        self.backend_proc = subprocess.Popen(
            backend_cmd,
            cwd=BACKEND_DIR,
            env=backend_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        health_url = f"http://127.0.0.1:{self.backend_port}/api/health"
        print(f"      Waiting for backend health at {health_url}...")
        if not wait_for_health(health_url, timeout=self.timeout):
            self.stop()
            raise TimeoutError(f"Backend failed to become healthy at {health_url} within {self.timeout}s")
        print("      Backend healthy.")

        # 4. Start Frontend if required
        if not self.api_only:
            print(f"[4/5] Starting Next.js frontend on port {self.frontend_port}...")
            frontend_env = os.environ.copy()
            frontend_env["PORT"] = str(self.frontend_port)
            frontend_env["BACKEND_URL"] = f"http://127.0.0.1:{self.backend_port}"
            frontend_env["NEXT_PUBLIC_API_URL"] = f"http://127.0.0.1:{self.backend_port}"

            npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
            frontend_cmd = [npm_cmd, "run", "dev", "--", "-p", str(self.frontend_port)]

            self.frontend_proc = subprocess.Popen(
                frontend_cmd,
                cwd=FRONTEND_DIR,
                env=frontend_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            frontend_url = f"http://127.0.0.1:{self.frontend_port}"
            print(f"      Waiting for frontend health at {frontend_url}...")
            if not wait_for_health(frontend_url, timeout=self.timeout):
                self.stop()
                raise TimeoutError(f"Frontend failed to become healthy at {frontend_url} within {self.timeout}s")
            print("      Frontend healthy.")
        else:
            print("[4/5] Skipping frontend startup (--api-only flag).")

        print("[5/5] Test servers ready.")

    def stop(self) -> None:
        print("\nStopping test servers...")
        if self.frontend_proc and self.frontend_proc.poll() is None:
            print(f"Killing frontend process PID {self.frontend_proc.pid}...")
            kill_process_tree(self.frontend_proc.pid)
            self.frontend_proc = None

        if self.backend_proc and self.backend_proc.poll() is None:
            print(f"Killing backend process PID {self.backend_proc.pid}...")
            kill_process_tree(self.backend_proc.pid)
            self.backend_proc = None

        # Verify active database was untouched and all invariants hold
        try:
            if self.initial_active_db_sha:
                verify_active_db_invariants(expected_sha=self.initial_active_db_sha)
        finally:
            # Cleanup isolated test database
            if self.cleanup_db:
                for ext in ("", "-wal", "-shm"):
                    p = Path(str(TEST_DB) + ext)
                    if p.is_file():
                        p.unlink(missing_ok=True)
                print("Isolated test database files removed.")


def main() -> int:
    parser = argparse.ArgumentParser(description="FRAMEOPS Tier 4 16-Step Lifecycle Test Runner")
    parser.add_argument("--backend-port", type=int, default=8001, help="Port for FastAPI backend (default: 8001)")
    parser.add_argument("--frontend-port", type=int, default=3000, help="Port for Next.js frontend (default: 3000)")
    parser.add_argument("--api-only", action="store_true", help="Run only API integration suite without frontend")
    parser.add_argument("--browser-only", action="store_true", help="Run only browser Playwright tests")
    parser.add_argument("--live", action="store_true", help="Enable FRAMEOPS_LIVE_SERVICES=1")
    parser.add_argument("--timeout", type=float, default=45.0, help="Server health check timeout in seconds")
    parser.add_argument("--no-cleanup", action="store_true", help="Preserve .frameops_e2e.db for inspection")
    parser.add_argument("--dry-run", action="store_true", help="Verify configuration and exit without running tests")
    args = parser.parse_args()

    if args.dry_run:
        print("Dry run requested. Verifying active database invariants and configuration...")
        verify_active_db_invariants()
        print("Dry run completed. Configuration and active database invariants (SHA-256 and 144 baseline records) are valid.")
        return 0

    python_exe = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    if not python_exe.is_file():
        python_exe = Path(sys.executable)

    pytest_exe = BACKEND_DIR / ".venv" / "Scripts" / "pytest.exe"
    if not pytest_exe.is_file():
        pytest_exe = python_exe.parent / "pytest.exe"

    api_suite = BACKEND_DIR / "tests" / "e2e" / "tier4_lifecycle" / "test_tier4_lifecycle_api.py"
    playwright_script = BACKEND_DIR / "test_playwright_battery.py"
    browser_suite = BACKEND_DIR / "tests" / "e2e" / "tier4_lifecycle" / "test_tier4_lifecycle_browser.py"

    # API-only execution: Runs pytest directly in-process without spinning up background uvicorn/Next.js
    if args.api_only:
        print("=================================================================")
        print(" FRAMEOPS Tier 4 API Lifecycle Test Runner (In-Process)")
        print(f" Live Services: {'Enabled' if args.live else 'Offline Mocks'}")
        print("=================================================================")
        verify_active_db_invariants()

        test_env = os.environ.copy()
        if args.live:
            test_env["FRAMEOPS_LIVE_SERVICES"] = "1"

        print(f"Executing Tier 4 API Lifecycle test suite: {api_suite}...")
        proc = subprocess.run([str(pytest_exe), str(api_suite), "-v"], cwd=BACKEND_DIR, env=test_env)

        # Re-verify active database invariants post test run
        verify_active_db_invariants()
        print(f"API Lifecycle test suite completed with exit code: {proc.returncode}")
        return proc.returncode

    # Server-managed execution (Full Browser & API or Browser-only)
    print("=================================================================")
    print(" FRAMEOPS Tier 4 End-to-End Lifecycle Test Runner")
    print(f" Backend Port:  {args.backend_port}")
    print(f" Frontend Port: {args.frontend_port}")
    print(f" Mode:          {'Browser only' if args.browser_only else 'Full Browser & API'}")
    print(f" Live Services: {'Enabled' if args.live else 'Offline Mocks'}")
    print("=================================================================")

    try:
        with E2EServerManager(
            backend_port=args.backend_port,
            frontend_port=args.frontend_port,
            api_only=False,
            timeout=args.timeout,
            cleanup_db=not args.no_cleanup,
            live_mode=args.live,
        ):
            print("\nExecuting test suites against running servers...")

            # Pass isolated DATABASE_URL and server URLs to test subprocesses
            test_env = os.environ.copy()
            test_env["DATABASE_URL"] = f"sqlite:///{TEST_DB.resolve().as_posix()}"
            test_env["BACKEND_URL"] = f"http://127.0.0.1:{args.backend_port}"
            test_env["FRONTEND_URL"] = f"http://127.0.0.1:{args.frontend_port}"
            if args.live:
                test_env["FRAMEOPS_LIVE_SERVICES"] = "1"

            ret_code = 0

            # 1. Browser-only execution
            if args.browser_only:
                if playwright_script.is_file():
                    print(f"Running Playwright battery: {playwright_script}...")
                    proc = subprocess.run([str(python_exe), str(playwright_script)], cwd=BACKEND_DIR, env=test_env)
                    ret_code = proc.returncode
                if ret_code == 0 and browser_suite.is_file():
                    print(f"Running Browser lifecycle suite: {browser_suite}...")
                    proc_b = subprocess.run([str(pytest_exe), str(browser_suite), "-v"], cwd=BACKEND_DIR, env=test_env)
                    ret_code = proc_b.returncode

            # 2. Default: Both API and Browser suites
            else:
                print(f"Executing Tier 4 API Lifecycle test suite: {api_suite}...")
                proc_api = subprocess.run([str(pytest_exe), str(api_suite), "-v"], cwd=BACKEND_DIR, env=test_env)
                ret_code = proc_api.returncode

                if ret_code == 0 and browser_suite.is_file():
                    print(f"\nRunning Browser lifecycle suite: {browser_suite}...")
                    proc_pw = subprocess.run([str(pytest_exe), str(browser_suite), "-v"], cwd=BACKEND_DIR, env=test_env)
                    ret_code = proc_pw.returncode

            print(f"Test suite execution completed with exit code: {ret_code}")
            return ret_code

    except Exception as exc:
        print(f"[ERROR] Test execution failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
