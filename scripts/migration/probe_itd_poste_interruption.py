"""Probe schema PosteInterruption on IndicateursTransportDistribution."""
from __future__ import annotations

import os
import re
from urllib.parse import parse_qs, unquote, urlparse

import pyodbc

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("SIR_PROFILE", "senelec")

# Load .env.senelec manually
env_path = os.path.join(REPO, ".env.senelec")
db_url = ""
for line in open(env_path, encoding="utf-8"):
    if line.strip().startswith("DATABASE_URL="):
        db_url = line.split("=", 1)[1].strip()
        break

if not db_url:
    raise SystemExit("DATABASE_URL not found in .env.senelec")

parsed = urlparse(db_url.replace("mssql+aioodbc://", "mssql://", 1))
user = unquote(parsed.username or "")
password = unquote(parsed.password or "")
host = parsed.hostname
port = parsed.port or 1433
qs = parse_qs(parsed.query)
driver = qs.get("driver", ["ODBC Driver 17 for SQL Server"])[0].replace("+", " ")

ITD_DB = os.environ.get("ITD_DATABASE", "IndicateursTransportDistribution")

conn_str = (
    f"DRIVER={{{driver}}};"
    f"SERVER={host},{port};"
    f"DATABASE={ITD_DB};"
    f"UID={user};PWD={password};"
    "TrustServerCertificate=yes;"
)

print(f"Connecting to {host}/{ITD_DB} ...")
cn = pyodbc.connect(conn_str, timeout=15)
cur = cn.cursor()

# Find table name (PosteInterruption vs Poste Interruption)
cur.execute(
    "SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
    "WHERE TABLE_NAME = 'PosteInterruption'"
)
tables = cur.fetchall()
print("Tables:", tables)

if not tables:
    raise SystemExit("No PosteInterruption table found")

schema, table = tables[0]
full = f"{schema}.{table}"
print(f"\nColumns for {full}:")
cur.execute(
    "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
    "WHERE TABLE_SCHEMA=? AND TABLE_NAME=? ORDER BY ORDINAL_POSITION",
    schema,
    table,
)
for row in cur.fetchall():
    print(f"  {row[0]} ({row[1]})")

cur.execute(f"SELECT COUNT(*) FROM {full}")
print(f"\nRow count: {cur.fetchone()[0]}")

cur.execute(f"SELECT TOP 3 * FROM {full}")
cols = [d[0] for d in cur.description]
print("Sample columns:", cols)
for row in cur.fetchall():
    print(dict(zip(cols, row, strict=True)))

cn.close()
