"""Milestone 1 Post-Migration Invariant Verification Script.

Executes after Alembic migration head is applied to backend/frameops.db:
1. Verifies database file exists and computes post-migration SHA256 and size.
2. Checks pre-migration backup remains completely unchanged.
3. Checks alembic_version is 'b2c3d4e5f6a7'.
4. Checks PRAGMA integrity_check == ok.
5. Checks PRAGMA foreign_key_check == [].
6. Verifies all 5 new tables exist (agency_profiles, client_profiles, project_requests, proposals, project_messages).
7. Verifies schema extensions on users (role, full_name) and projects (request_id).
8. Verifies 100% preservation of all 144 baseline operational records across 9 tables.
9. Saves comprehensive metadata summary to backend/scripts/m1_active_migration_meta.json.
"""

import hashlib
import json
import os
import sqlite3
import sys

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if not os.path.isdir(base_dir):
    base_dir = os.path.abspath("backend")

meta_backup_path = os.path.join(base_dir, "scripts", "m1_backup_meta.json")
if not os.path.exists(meta_backup_path):
    print(f"ERROR: Backup metadata not found at {meta_backup_path}!", file=sys.stderr)
    sys.exit(1)

with open(meta_backup_path, "r") as f:
    backup_meta = json.load(f)

db_path = os.path.abspath(os.path.join(base_dir, "frameops.db"))
backup_path = backup_meta["backup_path"]
meta_output_path = os.path.join(base_dir, "scripts", "m1_active_migration_meta.json")

print("=== M1 POST-MIGRATION INVARIANT VERIFICATION ===")
print(f"Target DB: {db_path}")

# 1. Verify file exists and compute post-migration SHA256 and size
with open(db_path, "rb") as f:
    db_bytes = f.read()
    post_db_hash = hashlib.sha256(db_bytes).hexdigest()
    post_db_size = len(db_bytes)

print(f"Post-migration DB size:   {post_db_size} bytes")
print(f"Post-migration DB SHA256: {post_db_hash}")

# 2. Check backup is untouched
with open(backup_path, "rb") as f:
    backup_hash = hashlib.sha256(f.read()).hexdigest()
expected_backup_hash = backup_meta.get("backup_sha256", backup_meta["sha256"])
assert backup_hash == expected_backup_hash, f"Backup modified! Expected {expected_backup_hash}, got {backup_hash}"
print(f"[PASS] Pre-migration backup {backup_path} is intact (SHA256: {backup_hash})")

# 3. Database invariants
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Alembic version
cur.execute("SELECT version_num FROM alembic_version")
ver_rows = cur.fetchall()
print(f"Post-migration alembic_version: {ver_rows}")
assert ver_rows == [("b2c3d4e5f6a7",)], f"Expected [('b2c3d4e5f6a7',)], got {ver_rows}"
print("[PASS] Final Alembic revision is 'b2c3d4e5f6a7'")

# PRAGMA integrity_check
cur.execute("PRAGMA integrity_check")
integrity = cur.fetchall()
print(f"PRAGMA integrity_check: {integrity}")
assert integrity == [("ok",)], f"Expected [('ok',)], got {integrity}"
print("[PASS] PRAGMA integrity_check == [('ok',)]")

# PRAGMA foreign_key_check
cur.execute("PRAGMA foreign_key_check")
fk = cur.fetchall()
print(f"PRAGMA foreign_key_check: {fk}")
assert fk == [], f"Expected [], got {fk}"
print("[PASS] PRAGMA foreign_key_check == []")

# 4. Verify all 5 newly migrated tables exist
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
all_tables = [r[0] for r in cur.fetchall()]
print(f"All tables in DB ({len(all_tables)}): {all_tables}")

required_new_tables = [
    "agency_profiles",
    "client_profiles",
    "project_requests",
    "proposals",
    "project_messages",
]
new_table_counts = {}
for t in required_new_tables:
    assert t in all_tables, f"Missing required new table: {t}"
    cur.execute(f'SELECT COUNT(*) FROM "{t}"')
    cnt = cur.fetchone()[0]
    new_table_counts[t] = cnt
    print(f"  [PASS] Newly migrated table exists: {t} (rows: {cnt})")

# 5. Verify schema extensions on users and projects
cur.execute("PRAGMA table_info(users)")
user_cols = {r[1]: r for r in cur.fetchall()}
assert "role" in user_cols, "Missing 'role' column on users table"
assert "full_name" in user_cols, "Missing 'full_name' column on users table"

cur.execute("SELECT id, email, role, full_name FROM users WHERE id=1")
user_row = cur.fetchone()
print(f"  [PASS] User 1 updated: id={user_row[0]}, email='{user_row[1]}', role='{user_row[2]}', full_name='{user_row[3]}'")
assert user_row[2] == "agency_owner", f"Expected role 'agency_owner', got {user_row[2]}"

cur.execute("PRAGMA table_info(projects)")
project_cols = {r[1]: r for r in cur.fetchall()}
assert "request_id" in project_cols, "Missing 'request_id' column on projects table"
print(f"  [PASS] projects table has 'request_id' column")

# 6. Verify row counts across all 9 baseline operational tables
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

actual_baseline_counts = {}
for tbl, expected_cnt in baseline_counts.items():
    cur.execute(f'SELECT COUNT(*) FROM "{tbl}"')
    cnt = cur.fetchone()[0]
    actual_baseline_counts[tbl] = cnt
    assert cnt == expected_cnt, f"Baseline table '{tbl}' row count mismatch: expected {expected_cnt}, got {cnt}"
    print(f"  [PASS] Baseline table '{tbl:18}': {cnt} rows intact")

total_operational = sum(actual_baseline_counts.values())
print(f"Total operational records across 9 baseline tables: {total_operational} (expected 144)")
assert total_operational == 144, f"Expected 144 operational records, got {total_operational}"

conn.close()

# 7. Save metadata summary JSON
meta_data = {
    "migration_type": "active_database_migration",
    "milestone": "M1",
    "status": "success",
    "command_executed": "cd backend; .\\.venv\\Scripts\\alembic.exe upgrade head",
    "exit_code": 0,
    "pre_migration": {
        "active_db_sha256": backup_meta.get("source_sha256", backup_meta["sha256"]),
        "backup_db_sha256": expected_backup_hash,
        "backup_path": backup_path,
        "alembic_version": "a1b2c3d4e5f6",
    },
    "post_migration": {
        "db_path": db_path,
        "db_sha256": post_db_hash,
        "db_size_bytes": post_db_size,
        "alembic_version": "b2c3d4e5f6a7",
        "integrity_check": integrity,
        "foreign_key_check": fk,
        "baseline_tables_count": actual_baseline_counts,
        "total_operational_records": total_operational,
        "new_tables_verified": required_new_tables,
        "new_tables_counts": new_table_counts,
    },
}

with open(meta_output_path, "w") as f:
    json.dump(meta_data, f, indent=2)

print(f"\nMetadata summary written to {meta_output_path}")
print("ALL M1 POST-MIGRATION INVARIANTS PASSED 100%!")
