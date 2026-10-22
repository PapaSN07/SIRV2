"""Count ITD PosteInterruption rows matching migrated interruptions."""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import pyodbc

REPO = Path(__file__).resolve().parents[2]
os.environ.setdefault("SIR_PROFILE", "senelec")

db_url = ""
for line in (REPO / ".env.senelec").read_text(encoding="utf-8").splitlines():
    if line.strip().startswith("DATABASE_URL="):
        db_url = line.split("=", 1)[1].strip()
        break

parsed = urlparse(db_url.replace("mssql+aioodbc://", "mssql://", 1))
user = unquote(parsed.username or "")
password = unquote(parsed.password or "")
host = parsed.hostname
port = parsed.port or 1433
driver = parse_qs(parsed.query).get("driver", ["ODBC Driver 17 for SQL Server"])[0].replace("+", " ")

ITD_DB = os.environ.get("ITD_DATABASE", "IndicateursTransportDistribution")
conn_str = (
    f"DRIVER={{{driver}}};SERVER={host},{port};DATABASE={ITD_DB};"
    f"UID={user};PWD={password};TrustServerCertificate=yes;"
)

id_map = json.loads((REPO / "scripts/migration/id_maps/interruptions.json").read_text(encoding="utf-8"))
legacy_ids = [int(k) for k in id_map.keys() if str(k).isdigit()][:500]
ids_sql = ",".join(str(i) for i in legacy_ids)

cn = pyodbc.connect(conn_str, timeout=30)
cur = cn.cursor()
cur.execute(f"SELECT COUNT(*) FROM dbo.PosteInterruption WHERE NInterruption IN ({ids_sql})")
print("sample 500 legacy ids -> rows:", cur.fetchone()[0])

# count with clients > 0 on sample
cur.execute(
    f"SELECT COUNT(*) FROM dbo.PosteInterruption WHERE NInterruption IN ({ids_sql}) "
    "AND nombreclientposteEstime > 0"
)
print("with clients > 0:", cur.fetchone()[0])
cn.close()
