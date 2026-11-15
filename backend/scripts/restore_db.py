"""Database Restore Script.

Restores backend/frameops.db from a specified backup (e.g. frameops.db.backup_20261115_092812)
using sqlite3.Connection.backup API, verifying integrity, foreign keys, alembic version,
and baseline row counts post-restoration.
"""

import hashlib
import json
import os
import sqlite3
import sys

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if not os.path.isdir(base_dir):
    base_dir = os.path.abspath("backend")

target_path = os.path.abspath(os.path.join(base_dir, "frameops.db"))
backup_path = sys.argv[1] if len(sys.argv) > 1 else os.path.abspath(os.path.join(base_dir, "frameops.db.backup_20261115_092812"))

print(f"=== DATABASE RESTORE ===")
print(f"Backup Source: {backup_path}")
print(f"Restore Dest:   {target_path}")

if not os.path.exists(backup_path):
    print(f"ERROR: Backup file not found: {backup_path}", file=sys.stderr)
    sys.exit(1)

# Restore via SQLite backup API
backup_conn = sqlite3.connect(backup_path)
target_conn = sqlite3.connect(target_path)
with target_conn:
    backup_conn.backup(target_conn)
target_conn.close()
backup_conn.close()

# Verify integrity and foreign keys on restored DB
conn = sqlite3.connect(target_path)
cur = conn.cursor()

cur.execute("PRAGMA integrity_check")
integrity = cur.fetchall()
print(f"PRAGMA integrity_check: {integrity}")
assert integrity == [("ok",)], f"Integrity check failed: {integrity}"

cur.execute("PRAGMA foreign_key_check")
fk = cur.fetchall()
print(f"PRAGMA foreign_key_check: {fk}")
assert fk == [], f"Foreign key check failed: {fk}"

cur.execute("SELECT version_num FROM alembic_version")
ver = cur.fetchall()
print(f"Alembic version: {ver}")
assert ver == [("a1b2c3d4e5f6",)], f"Expected a1b2c3d4e5f6, got {ver}"

tables = [
    "users", "workspaces", "memberships", "clients",
    "projects", "transcripts", "processing_runs", "extracted_items", "memory_operations"
]
total = 0
counts = {}
for t in tables:
    cur.execute(f'SELECT COUNT(*) FROM "{t}"')
    cnt = cur.fetchone()[0]
    counts[t] = cnt
    total += cnt

print(f"Row counts: {counts}")
print(f"Total operational records: {total} (expected 144)")
assert total == 144, f"Expected exactly 144 operational records, got {total}"

conn.close()

with open(target_path, "rb") as f:
    sha = hashlib.sha256(f.read()).hexdigest()
print(f"Restored DB SHA256: {sha}")
print("[PASS] Database restored successfully!")
