import csv
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import psycopg2

ZIP_PATH = r"L:\CRAauditexport__2002-01-01_2025-12-31__20251019T204151.zip"
OUT_DIR = Path(r"L:\limo\archive\tmp_zip_analysis")
SUMMARY_PATH = OUT_DIR / "cra_group_recon_summary.txt"
MISSING_PATH = OUT_DIR / "cra_group_missing_candidates.csv"
YEARLY_PATH = OUT_DIR / "cra_group_yearly_recon.csv"

DB = dict(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")

STOP = {"the","and","for","with","from","this","that","bank","card","transfer","payment","journal","entry","memo","doc","num","txn","type","accounts","payable"}

def clean_text(v):
    return " ".join((v or "").strip().split())

def norm_id(v):
    s = clean_text(v)
    if not s:
        return None
    s2 = s.strip('"\'')
    if re.fullmatch(r"[-+]?\d+\.0+", s2):
        s2 = s2.split(".")[0]
    return s2

def parse_date(v):
    s = clean_text(v)
    if not s:
        return None
    s = s.replace("Z","")
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s[:19], fmt).date().isoformat()
        except Exception:
            pass
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", s)
    if m:
        return m.group(1)
    return None

def parse_amount(v):
    s = clean_text(v)
    if not s:
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    s = s.replace(",", "").replace("$", "")
    try:
        val = float(s)
        if neg:
            val = -val
        return val
    except Exception:
        return None

def tokenize(*parts):
    txt = " ".join(clean_text(p).lower() for p in parts if p)
    tokens = re.findall(r"[a-z0-9]+", txt)
    return {t for t in tokens if len(t) >= 3 and t not in STOP}

def find_transactions_xml(zf):
    for name in zf.namelist():
        lname = name.lower()
        if lname.endswith("transactions.xml") or "transactions.xml" in lname:
            return name
    raise FileNotFoundError("Transactions.xml not found in zip")

OUT_DIR.mkdir(parents=True, exist_ok=True)

groups = {}
with zipfile.ZipFile(ZIP_PATH) as zf:
    xml_name = find_transactions_xml(zf)
    root = ET.fromstring(zf.read(xml_name))
    rows = root.findall('.//DataRow')

for idx, row in enumerate(rows):
    rec = {c.tag.lower(): clean_text(c.text) for c in list(row)}
    txn = norm_id(rec.get("txn_id"))
    tx_date = parse_date(rec.get("tx_date"))
    create_date = parse_date(rec.get("create_date"))
    use_date = tx_date or create_date
    seq = clean_text(rec.get("sequence")) or None

    if txn:
        key = ("txn", txn)
    elif seq or use_date:
        key = ("seqdate", seq or "", use_date or "")
    else:
        key = ("row", idx)

    if key not in groups:
        groups[key] = {"rows": [], "txn_id": txn, "sequence": seq}
    groups[key]["rows"].append(rec)
    if txn and not groups[key].get("txn_id"):
        groups[key]["txn_id"] = txn

ledger = []
with psycopg2.connect(**DB) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id,
                COALESCE(transaction_date::date, created_at::date)::text AS txn_date,
                ABS(COALESCE(debit_amount,0)-COALESCE(credit_amount,0))::numeric(14,2)::text AS amt,
                source_transaction_id,
                description,
                account_name,
                transaction_number,
                entity_name,
                transaction_type
            FROM public.unified_general_ledger
            """
        )
        for r in cur.fetchall():
            amount = float(r[2]) if r[2] is not None else None
            date = r[1]
            ledger.append({
                "id": r[0],
                "date": date,
                "amount": round(abs(amount), 2) if amount is not None else None,
                "source_transaction_id": norm_id(r[3]),
                "tokens": tokenize(r[4], r[5], r[6], r[7], r[8]),
            })

ledger_by_source = defaultdict(list)
ledger_by_date_amount = defaultdict(list)
for l in ledger:
    if l["source_transaction_id"]:
        ledger_by_source[l["source_transaction_id"]].append(l)
    if l["date"] and l["amount"] is not None:
        ledger_by_date_amount[(l["date"], l["amount"])].append(l)

stats = {
    "total_groups": 0,
    "groups_with_usable_date_amount": 0,
    "matched_L1": 0,
    "matched_L2": 0,
    "matched_L3": 0,
    "unmatched_groups": 0,
    "ADD": 0,
    "REVIEW_MAPPING": 0,
}

yearly = defaultdict(lambda: {
    "total_groups": 0,
    "groups_with_usable_date_amount": 0,
    "matched_L1": 0,
    "matched_L2": 0,
    "matched_L3": 0,
    "unmatched_groups": 0,
    "ADD": 0,
    "REVIEW_MAPPING": 0,
})

missing_rows = []

def infer_group(gkey, g):
    rows_local = g["rows"]
    date_val = None
    amounts = []
    for rr in rows_local:
        d = parse_date(rr.get("tx_date")) or parse_date(rr.get("create_date"))
        if d and date_val is None:
            date_val = d
        a = parse_amount(rr.get("amount"))
        if a is not None:
            amounts.append(abs(a))
    amount_val = max(amounts) if amounts else None

    def non_ap(rr):
        an = (rr.get("account_name") or "").lower()
        return "accounts payable" not in an

    preferred = [r for r in rows_local if non_ap(r)] or rows_local
    desc = ""
    for rr in preferred:
        for f in ("memo", "doc_num", "txn_type", "account_name"):
            if clean_text(rr.get(f)):
                desc = clean_text(rr.get(f))
                break
        if desc:
            break

    txn_id = g.get("txn_id")
    seq = g.get("sequence")
    return {
        "group_key": str(gkey),
        "txn_id": txn_id,
        "sequence": seq,
        "date": date_val,
        "amount": round(amount_val, 2) if amount_val is not None else None,
        "desc": desc,
        "tokens": tokenize(desc, seq, txn_id),
        "row_count": len(rows_local),
    }

for gkey, g in groups.items():
    info = infer_group(gkey, g)
    stats["total_groups"] += 1

    year = info["date"][:4] if info["date"] else "UNKNOWN"
    y = yearly[year]
    y["total_groups"] += 1

    usable = info["date"] is not None and info["amount"] is not None
    if usable:
        stats["groups_with_usable_date_amount"] += 1
        y["groups_with_usable_date_amount"] += 1

    match_level = None
    if info["txn_id"] and info["txn_id"] in ledger_by_source:
        match_level = "L1"
    elif usable:
        cands = ledger_by_date_amount.get((info["date"], info["amount"]), [])
        if cands and info["tokens"]:
            overlapped = any(len(info["tokens"] & c["tokens"]) > 0 for c in cands)
            if overlapped:
                match_level = "L2"
        if match_level is None and cands:
            match_level = "L3"

    if match_level:
        stats[f"matched_{match_level}"] += 1
        y[f"matched_{match_level}"] += 1
    else:
        stats["unmatched_groups"] += 1
        y["unmatched_groups"] += 1
        if usable and not info["txn_id"]:
            action = "ADD"
        else:
            action = "REVIEW_MAPPING"
        stats[action] += 1
        y[action] += 1
        missing_rows.append({
            "group_key": info["group_key"],
            "txn_id": info["txn_id"] or "",
            "sequence": info["sequence"] or "",
            "date": info["date"] or "",
            "amount": "" if info["amount"] is None else f"{info['amount']:.2f}",
            "description": info["desc"],
            "row_count": info["row_count"],
            "recommended_action": action,
        })

with SUMMARY_PATH.open("w", encoding="utf-8") as f:
    for k in [
        "total_groups",
        "groups_with_usable_date_amount",
        "matched_L1",
        "matched_L2",
        "matched_L3",
        "unmatched_groups",
        "ADD",
        "REVIEW_MAPPING",
    ]:
        f.write(f"{k}: {stats[k]}\n")

with MISSING_PATH.open("w", newline="", encoding="utf-8") as f:
    cols = ["group_key","txn_id","sequence","date","amount","description","row_count","recommended_action"]
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(missing_rows)

with YEARLY_PATH.open("w", newline="", encoding="utf-8") as f:
    cols = ["year","total_groups","groups_with_usable_date_amount","matched_L1","matched_L2","matched_L3","matched_total","unmatched_groups","ADD","REVIEW_MAPPING"]
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for year in sorted(yearly.keys()):
        row = dict(yearly[year])
        row["year"] = year
        row["matched_total"] = row["matched_L1"] + row["matched_L2"] + row["matched_L3"]
        w.writerow(row)

print("FINAL_NUMBERS")
for k in ["total_groups","groups_with_usable_date_amount","matched_L1","matched_L2","matched_L3","unmatched_groups","ADD","REVIEW_MAPPING"]:
    print(f"{k}={stats[k]}")

for p in [SUMMARY_PATH, MISSING_PATH, YEARLY_PATH]:
    print(f"FILE_HEAD {p}")
    with p.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 5:
                break
            print(line.rstrip("\n"))
