import sqlite3
import hashlib
import json
import os
from pathlib import Path

db_path = Path("backend/frameops.db").resolve()
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()

# 1. Alembic version
cur.execute("SELECT version_num FROM alembic_version")
version = cur.fetchall()

# 2. PRAGMA integrity and fk
cur.execute("PRAGMA integrity_check")
integrity = cur.fetchall()
cur.execute("PRAGMA foreign_key_check")
fk = cur.fetchall()

# 3. Table lists
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]

# 4. Baseline tables counts
baseline_tables = ['users', 'workspaces', 'memberships', 'clients', 'projects', 'transcripts', 'processing_runs', 'extracted_items', 'memory_operations']
counts = {}
for t in baseline_tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    counts[t] = cur.fetchone()[0]

# 5. New tables counts
new_tables = ['agency_profiles', 'client_profiles', 'project_requests', 'proposals', 'project_messages']
new_counts = {}
for t in new_tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    new_counts[t] = cur.fetchone()[0]

cur.execute("PRAGMA table_info(projects)")
proj_cols = [c[1] for c in cur.fetchall()]

# 6. User 1 role
cur.execute("SELECT id, email, role, full_name FROM users WHERE id=1")
user_1 = cur.fetchone()

# 7. Checksums of DB and all backups
backups = {}
for p in Path("backend").glob("frameops.db.backup_*"):
    with open(p, "rb") as f:
        backups[p.name] = {
            "size": p.stat().st_size,
            "sha256": hashlib.sha256(f.read()).hexdigest(),
        }

with open(db_path, "rb") as f:
    db_sha = hashlib.sha256(f.read()).hexdigest()

out = {
    "db_path": str(db_path),
    "db_sha256": db_sha,
    "db_size": db_path.stat().st_size,
    "alembic_version": version,
    "integrity_check": integrity,
    "foreign_key_check": fk,
    "all_tables_count": len(tables),
    "all_tables": tables,
    "baseline_records": counts,
    "baseline_total_records": sum(counts.values()),
    "new_tables_records": new_counts,
    "has_request_id_in_projects": "request_id" in proj_cols,
    "user_1": {
        "id": user_1[0],
        "email": user_1[1],
        "role": user_1[2],
        "full_name": user_1[3],
    } if user_1 else None,
    "backups": backups,
}
print(json.dumps(out, indent=2))
