"""Milestone 1 Migration Rehearsal Script.

Safely tests the M1 Alembic migration on an isolated copy (backend/frameops_rehearse.db)
before touching the active database.
Verifies PRAGMA integrity_check, PRAGMA foreign_key_check, preservation of all 144
baseline records across 9 tables, creation of 5 new tables, schema modifications on
users and projects, and guarantees active backend/frameops.db remains 100% untouched.
"""

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if not os.path.isdir(base_dir):
    base_dir = os.path.abspath("backend")

meta_backup_path = os.path.join(base_dir, "scripts", "m1_backup_meta.json")
if not os.path.exists(meta_backup_path):
    print(f"ERROR: Backup metadata not found at {meta_backup_path}. Run m1_backup.py first!", file=sys.stderr)
    sys.exit(1)

with open(meta_backup_path, "r") as f:
    backup_meta = json.load(f)

backup_path = backup_meta["backup_path"]
rehearse_path = os.path.join(base_dir, "frameops_rehearse.db")
active_path = os.path.join(base_dir, "frameops.db")

print("=== M1 MIGRATION REHEARSAL WORKFLOW ===")
print(f"Base Directory:   {base_dir}")
print(f"Source Backup:    {backup_path}")
print(f"Rehearsal Target: {rehearse_path}")
print(f"Active DB:        {active_path}")

# 1. Fresh copy from backup to frameops_rehearse.db
shutil.copy2(backup_path, rehearse_path)
print(f"[PASS] Copied {backup_path} -> {rehearse_path}")

# 2. Record pre-migration counts and checks from rehearsal copy
pre_conn = sqlite3.connect(rehearse_path)
pre_cur = pre_conn.cursor()

pre_cur.execute("PRAGMA integrity_check")
pre_integrity = pre_cur.fetchall()
assert pre_integrity == [("ok",)], f"Pre-migration rehearsal integrity failed: {pre_integrity}"

pre_cur.execute("PRAGMA foreign_key_check")
pre_fk = pre_cur.fetchall()
assert pre_fk == [], f"Pre-migration rehearsal foreign key check failed: {pre_fk}"

pre_cur.execute("SELECT version_num FROM alembic_version")
pre_version_rows = pre_cur.fetchall()
pre_version = pre_version_rows[0][0]
print(f"Rehearsal pre-migration alembic_version: {pre_version}")
assert pre_version == "a1b2c3d4e5f6", f"Expected pre-migration version a1b2c3d4e5f6, got {pre_version}"

baseline_tables = [
    "users", "workspaces", "memberships", "clients",
    "projects", "transcripts", "processing_runs", "extracted_items", "memory_operations"
]
pre_counts = {}
for t in baseline_tables:
    pre_cur.execute(f'SELECT COUNT(*) FROM "{t}"')
    pre_counts[t] = pre_cur.fetchone()[0]

total_baseline_pre = sum(pre_counts.values())
print(f"Rehearsal pre-migration baseline counts: {pre_counts}")
print(f"Total baseline records across 9 tables: {total_baseline_pre}")

pre_conn.close()

# 3. Run alembic upgrade head targeting frameops_rehearse.db via subprocess
alembic_bin = os.path.join(base_dir, ".venv", "Scripts", "alembic.exe")
if not os.path.exists(alembic_bin):
    alembic_bin = "alembic"

env = os.environ.copy()
env["DATABASE_URL"] = "sqlite:///./frameops_rehearse.db"

print(f"\nRunning alembic upgrade head with DATABASE_URL={env['DATABASE_URL']}...")
cmd = [alembic_bin, "upgrade", "head"]
proc = subprocess.run(cmd, cwd=base_dir, env=env, capture_output=True, text=True)
print("STDOUT:\n", proc.stdout)
if proc.stderr:
    print("STDERR:\n", proc.stderr)
print(f"Exit code: {proc.returncode}")
assert proc.returncode == 0, f"Alembic upgrade failed with code {proc.returncode}"

# 4. Post-migration assertions on frameops_rehearse.db
conn = sqlite3.connect(rehearse_path)
cur = conn.cursor()

# Assertion 1: PRAGMA integrity_check == [('ok',)]
cur.execute("PRAGMA integrity_check")
integrity = cur.fetchall()
print(f"\nRehearsal post-migration PRAGMA integrity_check: {integrity}")
assert integrity == [("ok",)], f"Integrity check failed: {integrity}"

# Assertion 2: PRAGMA foreign_key_check == []
cur.execute("PRAGMA foreign_key_check")
fk = cur.fetchall()
print(f"Rehearsal post-migration PRAGMA foreign_key_check: {fk}")
assert fk == [], f"Foreign key check failed: {fk}"

# Assertion 3: New tables exist:
# agency_profiles, client_profiles, project_requests, proposals, project_messages
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
all_tables = [r[0] for r in cur.fetchall()]
print(f"Total tables after migration ({len(all_tables)}): {all_tables}")

required_new_tables = [
    "agency_profiles",
    "client_profiles",
    "project_requests",
    "proposals",
    "project_messages",
]
for nt in required_new_tables:
    assert nt in all_tables, f"Missing required new table: {nt}"
    cur.execute(f'SELECT COUNT(*) FROM "{nt}"')
    cnt = cur.fetchone()[0]
    print(f"  [PASS] Table exists: {nt} (count={cnt})")

# Assertion 4: Existing table schema extensions
cur.execute("PRAGMA table_info(users)")
user_cols = {r[1]: r for r in cur.fetchall()}
assert "role" in user_cols, "Missing 'role' column on users table"
assert "full_name" in user_cols, "Missing 'full_name' column on users table"
print(f"  [PASS] users table schema extended with role and full_name")

cur.execute("PRAGMA table_info(projects)")
project_cols = {r[1]: r for r in cur.fetchall()}
assert "request_id" in project_cols, "Missing 'request_id' column on projects table"
print(f"  [PASS] projects table schema extended with request_id")

# Assertion 5: Table row counts in baseline tables match pre-migration counts exactly
post_counts = {}
for t in baseline_tables:
    cur.execute(f'SELECT COUNT(*) FROM "{t}"')
    post_counts[t] = cur.fetchone()[0]
    assert post_counts[t] == pre_counts[t], f"Row count mismatch for {t}: pre={pre_counts[t]}, post={post_counts[t]}"
    print(f"  [PASS] Preserved baseline row count {t:18}: {post_counts[t]}")

total_baseline_post = sum(post_counts.values())
assert total_baseline_post == total_baseline_pre, "Total baseline records changed during rehearsal!"
print(f"  [PASS] Total baseline records preserved: {total_baseline_post}")

# Assertion 6: Target Alembic revision reached
cur.execute("SELECT version_num FROM alembic_version")
post_version = cur.fetchone()[0]
print(f"Rehearsal post-migration alembic_version: {post_version}")
assert post_version == "b2c3d4e5f6a7", f"Expected version b2c3d4e5f6a7, got {post_version}"

conn.close()

# 5. Confirm active frameops.db is untouched and matches pre-rehearsal source hash
with open(active_path, "rb") as f:
    active_hash = hashlib.sha256(f.read()).hexdigest()

expected_active_hash = backup_meta.get("source_sha256", backup_meta["sha256"])
print(f"\nActive frameops.db SHA256: {active_hash}")
print(f"Expected active DB SHA256: {expected_active_hash}")
assert active_hash == expected_active_hash, "Active frameops.db has been modified during rehearsal!"
print("[PASS] Active backend/frameops.db remains completely untouched and pristine!")

# 6. Record rehearsal verification results
rehearsal_meta = {
    "rehearsal_db_path": rehearse_path,
    "pre_migration_version": pre_version,
    "post_migration_version": post_version,
    "integrity_check": integrity,
    "foreign_key_check": fk,
    "required_new_tables": required_new_tables,
    "baseline_table_counts": post_counts,
    "total_baseline_records": total_baseline_post,
    "active_db_pristine": True,
    "active_db_sha256": active_hash,
}
rehearsal_meta_path = os.path.join(base_dir, "scripts", "m1_rehearsal_meta.json")
with open(rehearsal_meta_path, "w") as f:
    json.dump(rehearsal_meta, f, indent=2)

print(f"\nRehearsal metadata written to {rehearsal_meta_path}")
print("ALL M1 REHEARSAL ASSERTIONS PASSED 100%!")
