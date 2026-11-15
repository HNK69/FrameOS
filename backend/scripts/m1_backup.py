"""Milestone 1 Pre-Migration Backup Script.

Creates a verified timestamped backup of backend/frameops.db using the native
sqlite3.Connection.backup API, records SHA256, table row counts, PRAGMA checks,
and writes comprehensive metadata to backend/scripts/m1_backup_meta.json.
"""

import datetime
import hashlib
import json
import os
import sqlite3
import sys

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if not os.path.isdir(base_dir):
    base_dir = os.path.abspath("backend")

src_path = os.path.abspath(os.path.join(base_dir, "frameops.db"))
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup_filename = f"frameops.db.backup_{timestamp}"
backup_path = os.path.abspath(os.path.join(base_dir, backup_filename))

print(f"=== M1 PRE-MIGRATION DATABASE BACKUP ===")
print(f"Source DB:    {src_path}")
print(f"Backup Dest:  {backup_path}")

if not os.path.exists(src_path):
    print(f"ERROR: Source database not found at {src_path}", file=sys.stderr)
    sys.exit(1)

# Compute source SHA256
src_hasher = hashlib.sha256()
with open(src_path, "rb") as f:
    while chunk := f.read(65536):
        src_hasher.update(chunk)
source_sha256 = src_hasher.hexdigest()

# 1. Native atomic SQLite backup
src_conn = sqlite3.connect(src_path)
dst_conn = sqlite3.connect(backup_path)
with dst_conn:
    src_conn.backup(dst_conn)
dst_conn.close()
src_conn.close()

# 2. File size and SHA256 checksum of backup
file_size = os.path.getsize(backup_path)
hasher = hashlib.sha256()
with open(backup_path, "rb") as f:
    while chunk := f.read(65536):
        hasher.update(chunk)
backup_sha256 = hasher.hexdigest()

print(f"[PASS] Backup created successfully.")
print(f"Source SHA256: {source_sha256}")
print(f"Backup Size:   {file_size} bytes")
print(f"Backup SHA256: {backup_sha256}")

# 3. Post-backup integrity and schema checks on the backup snapshot
check_conn = sqlite3.connect(backup_path)
cur = check_conn.cursor()

cur.execute("PRAGMA integrity_check")
integrity = cur.fetchall()
print(f"PRAGMA integrity_check: {integrity}")
assert integrity == [("ok",)], f"Integrity check failed on backup: {integrity}"

cur.execute("PRAGMA foreign_key_check")
fk_check = cur.fetchall()
print(f"PRAGMA foreign_key_check: {fk_check}")
assert fk_check == [], f"Foreign key check failed on backup: {fk_check}"

cur.execute("SELECT version_num FROM alembic_version")
version = cur.fetchall()
print(f"alembic_version: {version}")

cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
print(f"Total tables: {len(tables)}")

row_counts = {}
for table in tables:
    cur.execute(f'SELECT COUNT(*) FROM "{table}"')
    count = cur.fetchone()[0]
    row_counts[table] = count
    print(f"  {table:28}: {count}")

check_conn.close()

# 4. Save metadata JSON
metadata = {
    "source_path": src_path,
    "source_sha256": source_sha256,
    "backup_path": backup_path,
    "backup_filename": backup_filename,
    "backup_sha256": backup_sha256,
    "timestamp": timestamp,
    "file_size": file_size,
    "sha256": backup_sha256,
    "integrity_check": integrity,
    "foreign_key_check": fk_check,
    "alembic_version": version,
    "row_counts": row_counts,
}

meta_path = os.path.join(base_dir, "scripts", "m1_backup_meta.json")
with open(meta_path, "w") as f:
    json.dump(metadata, f, indent=2)

print(f"\nBackup metadata written to {meta_path}")
print("PRE-MIGRATION BACKUP COMPLETED AND VERIFIED 100%!")
