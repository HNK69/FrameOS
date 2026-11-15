"""Milestone 1 Pre-Flight Active Database Verification Script.

Ensures the active database backend/frameops.db is in a verified, pristine state
prior to executing the active Alembic migration:
1. Verifies database file exists and matches fresh backup source SHA256.
2. Checks alembic_version is 'a1b2c3d4e5f6'.
3. Checks PRAGMA integrity_check == ok.
4. Checks PRAGMA foreign_key_check == [].
5. Verifies all 144 baseline records across the 9 operational tables.
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
    print(f"ERROR: Backup metadata not found at {meta_backup_path}. Run m1_backup.py first!", file=sys.stderr)
    sys.exit(1)

with open(meta_backup_path, "r") as f:
    backup_meta = json.load(f)

db_path = os.path.abspath(os.path.join(base_dir, "frameops.db"))
backup_path = backup_meta["backup_path"]
expected_backup_hash = backup_meta.get("backup_sha256", backup_meta["sha256"])
expected_source_hash = backup_meta.get("source_sha256", backup_meta["sha256"])

print("=== M1 PRE-MIGRATION ACTIVE DB VERIFICATION ===")
print(f"Active DB:    {db_path}")
print(f"Backup DB:    {backup_path}")

# 1. Hashes verification
with open(db_path, "rb") as f:
    db_hash = hashlib.sha256(f.read()).hexdigest()
with open(backup_path, "rb") as f:
    backup_hash = hashlib.sha256(f.read()).hexdigest()

print(f"Active DB SHA256:       {db_hash}")
print(f"Expected source SHA256: {expected_source_hash}")
print(f"Backup DB SHA256:       {backup_hash}")
print(f"Expected backup SHA256: {expected_backup_hash}")

assert db_hash == expected_source_hash, f"Hash mismatch on active DB: expected {expected_source_hash}, got {db_hash}"
assert backup_hash == expected_backup_hash, f"Backup DB hash mismatch: expected {expected_backup_hash}, got {backup_hash}"
print("[PASS] SHA256 matches expected values for both active DB and backup snapshot.")

# 2. Database checks
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Alembic version
cur.execute("SELECT version_num FROM alembic_version")
ver = cur.fetchall()
print(f"Alembic version: {ver}")
assert ver == [("a1b2c3d4e5f6",)], f"Expected [('a1b2c3d4e5f6',)], got {ver}"
print("[PASS] Alembic version is a1b2c3d4e5f6.")

# PRAGMA integrity_check
cur.execute("PRAGMA integrity_check")
integrity = cur.fetchall()
print(f"PRAGMA integrity_check: {integrity}")
assert integrity == [("ok",)], f"Integrity check failed: {integrity}"
print("[PASS] PRAGMA integrity_check == ok.")

# PRAGMA foreign_key_check
cur.execute("PRAGMA foreign_key_check")
fk = cur.fetchall()
print(f"PRAGMA foreign_key_check: {fk}")
assert fk == [], f"Foreign key check failed: {fk}"
print("[PASS] PRAGMA foreign_key_check == [].")

# Baseline tables row counts
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

actual_counts = {}
for tbl, expected_cnt in baseline_counts.items():
    cur.execute(f'SELECT COUNT(*) FROM "{tbl}"')
    cnt = cur.fetchone()[0]
    actual_counts[tbl] = cnt
    assert cnt == expected_cnt, f"Table {tbl} expected {expected_cnt}, got {cnt}"
    print(f"  [PASS] Table '{tbl:18}': {cnt} rows")

total_operational = sum(actual_counts.values())
print(f"Total operational rows (9 tables): {total_operational} (expected 144)")
assert total_operational == 144, f"Expected 144 operational rows, got {total_operational}"

conn.close()
print("\nALL PRE-MIGRATION CHECKS PASSED SUCCESSFULLY — SAFE TO MIGRATE ACTIVE DB!")
