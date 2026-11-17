import sqlite3
import hashlib
import json

path = "backend/frameops.db"
conn = sqlite3.connect(path)
cur = conn.cursor()

cur.execute("SELECT version_num FROM alembic_version")
version = cur.fetchall()
print(f"Restored version: {version}")

cur.execute("PRAGMA integrity_check")
integrity = cur.fetchall()
print(f"PRAGMA integrity_check: {integrity}")

cur.execute("PRAGMA foreign_key_check")
fk_check = cur.fetchall()
print(f"PRAGMA foreign_key_check: {fk_check}")

cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
print(f"Tables ({len(tables)}): {tables}")

row_counts = {}
for table in tables:
    cur.execute(f'SELECT COUNT(*) FROM "{table}"')
    row_counts[table] = cur.fetchone()[0]

print(f"Row counts: {row_counts}")

conn.close()

with open(path, "rb") as f:
    h = hashlib.sha256(f.read()).hexdigest()
print(f"SHA256: {h}")

with open("backend/scripts/m1_backup_meta.json", "r") as f:
    orig = json.load(f)

print(f"Matches original backup SHA256: {h == orig['sha256']}")
print(f"Matches original version: {version == orig['alembic_version']}")
print(f"Matches original row counts: {row_counts == orig['row_counts']}")
