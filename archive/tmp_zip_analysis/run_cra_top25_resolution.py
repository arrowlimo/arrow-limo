import csv
import os
from collections import Counter
from pathlib import Path

import psycopg2

base = Path(r"L:\limo")
checklist_path = base / r"archive\tmp_zip_analysis\cra_group_review_checklist.csv"
out_csv = base / r"archive\tmp_zip_analysis\cra_top25_resolution.csv"
out_summary = base / r"archive\tmp_zip_analysis\cra_top25_resolution_summary.txt"

def load_dotenv(path: Path):
    env = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def row_text(row):
    return " ".join("" if v is None else str(v) for v in row).lower()

with checklist_path.open("r", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
rows.sort(key=lambda r: int(r.get("priority_rank") or 10**9))
top25 = rows[:25]

env = {}
env.update(load_dotenv(base / ".env"))
env.update(load_dotenv(base / ".env.local"))

host = "localhost"
port = 5432
dbname = "almsdata"
users = [env.get("DB_USER"), "postgres"]
passwords = [env.get("DB_PASSWORD"), os.environ.get("PGPASSWORD"), "ArrowLimousine"]

conn = None
last_err = None
for u in [x for x in users if x]:
    for p in [x for x in passwords if x]:
        try:
            conn = psycopg2.connect(host=host, port=port, dbname=dbname, user=u, password=p)
            break
        except Exception as e:
            last_err = e
    if conn:
        break
if conn is None:
    raise last_err

conn.set_session(readonly=True, autocommit=False)
cur = conn.cursor()

results = []
for item in top25:
    pr = item.get("priority_rank", "")
    txn_id = (item.get("txn_id") or "").strip()
    dt = (item.get("date") or "").strip()
    desc = (item.get("description") or "").strip()
    p1 = item.get("sql_probe_1", "")
    p2 = item.get("sql_probe_2", "")

    cur.execute(p1)
    ledger_rows = cur.fetchall()
    cur.execute(p2)
    banking_rows = cur.fetchall()

    txn_l = txn_id.lower(); date_l = dt.lower(); desc_l = desc.lower()
    ledger_clear = False; banking_clear = False; ledger_weak = False; banking_weak = False

    for r in ledger_rows:
        t = row_text(r)
        has_txn = txn_l and txn_l in t
        has_date = date_l and date_l in t
        has_desc = desc_l and desc_l in t
        if has_txn: ledger_clear = True
        elif has_date or has_desc: ledger_weak = True

    for r in banking_rows:
        t = row_text(r)
        has_txn = txn_l and txn_l in t
        has_date = date_l and date_l in t
        has_desc = desc_l and desc_l in t
        if has_txn: banking_clear = True
        elif has_date or has_desc: banking_weak = True

    if ledger_clear: status = "RESOLVED_LEDGER"
    elif banking_clear: status = "RESOLVED_BANKING"
    elif ledger_weak or banking_weak: status = "PARTIAL"
    else: status = "UNRESOLVED"

    evidence = f"ledger_rows={len(ledger_rows)}; banking_rows={len(banking_rows)}; ledger_clear={'yes' if ledger_clear else 'no'}; banking_clear={'yes' if banking_clear else 'no'}"

    results.append({"priority_rank": pr, "txn_id": txn_id, "date": dt, "description": desc, "status": status, "evidence": evidence})

conn.rollback(); cur.close(); conn.close()

with out_csv.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["priority_rank","txn_id","date","description","status","evidence"])
    w.writeheader(); w.writerows(results)

counts = Counter(r["status"] for r in results)
unresolved = [r["txn_id"] for r in results if r["status"] == "UNRESOLVED"]
summary = "\n".join([
    "CRA Top-25 Resolution Summary",
    f"Total items: {len(results)}",
    f"RESOLVED_LEDGER: {counts.get('RESOLVED_LEDGER', 0)}",
    f"RESOLVED_BANKING: {counts.get('RESOLVED_BANKING', 0)}",
    f"PARTIAL: {counts.get('PARTIAL', 0)}",
    f"UNRESOLVED: {counts.get('UNRESOLVED', 0)}",
    "UNRESOLVED txn_ids: " + (", ".join(unresolved) if unresolved else "(none)"),
]) + "\n"
out_summary.write_text(summary, encoding="utf-8")

print("DONE")
