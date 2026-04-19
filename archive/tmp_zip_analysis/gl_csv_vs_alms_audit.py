import csv
import pathlib
import re
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation

import psycopg2

BASE = pathlib.Path(r"L:\limo")
OUT_DIR = BASE / "archive" / "tmp_zip_analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CSV_FILES = [
    BASE / "Copy of General_ledger2.csv",
    BASE / "Copy of General_ledger.csv",
]

SUMMARY_PATH = OUT_DIR / "gl_csv_vs_alms_audit_summary.txt"
ROW_RESULTS_PATH = OUT_DIR / "gl_csv_vs_alms_row_results.csv"
MISSING_PATH = OUT_DIR / "gl_csv_vs_alms_missing_only.csv"
MISMATCH_PATH = OUT_DIR / "gl_csv_vs_alms_mismatch_only.csv"
KEY_STATS_PATH = OUT_DIR / "gl_csv_vs_alms_key_stats.csv"


def load_env(path: pathlib.Path):
    data = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def parse_date(value: str):
    s = (value or "").strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def parse_amount(value: str):
    s = (value or "").strip()
    if not s:
        return None
    s = s.replace(",", "").replace("$", "").replace(" ", "")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def normalize_key(value: str):
    s = (value or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def tokenize(text: str):
    s = (text or "").lower()
    return set(re.findall(r"[a-z0-9]+", s))


def jaccard(a, b):
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    uni = len(a | b)
    return inter / uni if uni else 0.0


def parse_account(raw: str):
    s = (raw or "").strip()
    if not s:
        return (None, None, None)
    m = re.match(r"^([A-Za-z0-9\-\.]+)\s+(.*)$", s)
    if m:
        code = m.group(1).strip()
        name = m.group(2).strip() or None
        norm = code.lower()
        return (code, name, norm)
    return (None, s, s.lower())


def norm_decimal(d: Decimal):
    if d is None:
        return None
    return d.quantize(Decimal("0.01"))


def row_amount_abs(row):
    n = row.get("csv_net")
    if n is None:
        d = row.get("csv_debit") or Decimal("0")
        c = row.get("csv_credit") or Decimal("0")
        n = d - c
    return abs(n)

# Load ALMS GL rows (read-only)
env = load_env(BASE / ".env")
conn = psycopg2.connect(
    host=env.get("DB_HOST", "localhost"),
    port=int(env.get("DB_PORT", "5432")),
    dbname=env.get("DB_NAME", "almsdata"),
    user=env.get("DB_USER", "postgres"),
    password=env.get("DB_PASSWORD", ""),
)
cur = conn.cursor()
cur.execute(
    """
    SELECT id, transaction_date, account_code, account_name, description,
           debit_amount, credit_amount, source_transaction_id, transaction_number
    FROM public.unified_general_ledger
    """
)
alms_rows = []
for r in cur.fetchall():
    debit = norm_decimal(r[5]) if r[5] is not None else None
    credit = norm_decimal(r[6]) if r[6] is not None else None
    net = None
    if debit is not None or credit is not None:
        net = norm_decimal((debit or Decimal("0")) - (credit or Decimal("0")))
    account_norm = (r[2].strip().lower() if r[2] else (r[3].strip().lower() if r[3] else None))
    alms_rows.append({
        "id": r[0],
        "date": r[1],
        "account_code": r[2],
        "account_name": r[3],
        "account_norm": account_norm,
        "description": r[4] or "",
        "desc_tokens": tokenize(r[4] or ""),
        "debit": debit,
        "credit": credit,
        "net": net,
        "source_transaction_id": r[7],
        "transaction_number": r[8],
    })
cur.close()
conn.close()

idx_key = defaultdict(list)
idx_date_account = defaultdict(list)
idx_t3 = defaultdict(list)
for ar in alms_rows:
    for k in (ar.get("source_transaction_id"), ar.get("transaction_number")):
        nk = normalize_key(k)
        if nk:
            idx_key[nk].append(ar)
    if ar["date"] and ar["account_norm"]:
        da = (ar["date"], ar["account_norm"])
        idx_date_account[da].append(ar)
        if ar["net"] is not None:
            idx_t3[(ar["date"], ar["account_norm"], ar["net"])].append(ar)

all_results = []
schema_notes = []
key_stats = []

for csv_path in CSV_FILES:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)

    amount_candidates = [h for h in headers if any(x in h.lower() for x in ("debit", "credit", "amount", "balance"))]
    date_vals = []
    parsed_rows = []

    for i, raw in enumerate(rows, start=2):
        d = parse_date(raw.get("Date", ""))
        debit = norm_decimal(parse_amount(raw.get("Debit", "")))
        credit = norm_decimal(parse_amount(raw.get("Credit", "")))
        net = None
        if debit is not None or credit is not None:
            net = norm_decimal((debit or Decimal("0")) - (credit or Decimal("0")))

        account_raw = raw.get("Account", "")
        account_code, account_name, account_norm = parse_account(account_raw)
        if not account_norm:
            fallback = (raw.get("Name", "") or "").strip()
            account_norm = fallback.lower() if fallback else None

        desc_parts = [raw.get("Memo/Description", ""), raw.get("Name", ""), raw.get("Transaction Type", "")]
        desc = " | ".join([p.strip() for p in desc_parts if (p or "").strip()])

        rec = {
            "file": csv_path.name,
            "line_number": i,
            "raw_date": raw.get("Date", ""),
            "date": d,
            "account_raw": account_raw,
            "account_code": account_code,
            "account_name": account_name,
            "account_norm": account_norm,
            "description": desc,
            "desc_tokens": tokenize(desc),
            "csv_key_raw": raw.get("#", ""),
            "csv_key_norm": normalize_key(raw.get("#", "")),
            "csv_debit": debit,
            "csv_credit": credit,
            "csv_net": net,
            "transaction_type": (raw.get("Transaction Type", "") or "").strip(),
            "name": (raw.get("Name", "") or "").strip(),
            "memo": (raw.get("Memo/Description", "") or "").strip(),
        }
        if d:
            date_vals.append(d)
        if d and account_norm and (debit is not None or credit is not None or net is not None):
            parsed_rows.append(rec)

    schema_notes.append({
        "file": csv_path.name,
        "headers": headers,
        "raw_rows": len(rows),
        "comparable_rows": len(parsed_rows),
        "date_min": min(date_vals).isoformat() if date_vals else "n/a",
        "date_max": max(date_vals).isoformat() if date_vals else "n/a",
        "amount_columns": amount_candidates,
    })

    # compare rows
    class_counts = Counter()
    t1_hits = t2_hits = t3_hits = 0
    for rec in parsed_rows:
        cls = None
        tier = None
        reason = ""
        matched = None

        # T1
        if rec["csv_key_norm"]:
            cands = idx_key.get(rec["csv_key_norm"], [])
            if cands:
                best = None
                for c in cands:
                    score = 0
                    if rec["date"] and c["date"] == rec["date"]:
                        score += 3
                    if rec["account_norm"] and c["account_norm"] == rec["account_norm"]:
                        score += 3
                    if rec["csv_net"] is not None and c["net"] == rec["csv_net"]:
                        score += 2
                    sim = jaccard(rec["desc_tokens"], c["desc_tokens"])
                    if sim >= 0.5:
                        score += 1
                    if best is None or score > best[0]:
                        best = (score, c, sim)
                if best and best[0] >= 5:
                    cls = "PRESENT_STRONG"
                    tier = "T1"
                    reason = f"key match with corroborating fields (score={best[0]})"
                    matched = best[1]
                    t1_hits += 1
                else:
                    cls = "MISMATCH_IN_ALMS"
                    tier = "T1"
                    reason = "key exists in ALMS but supporting fields differ"
                    matched = best[1] if best else cands[0]

        # T2
        if cls is None:
            cands = idx_date_account.get((rec["date"], rec["account_norm"]), []) if rec["date"] and rec["account_norm"] else []
            t2 = []
            for c in cands:
                amount_ok = False
                if rec["csv_debit"] is not None and rec["csv_credit"] is not None and c["debit"] is not None and c["credit"] is not None:
                    amount_ok = (rec["csv_debit"] == c["debit"] and rec["csv_credit"] == c["credit"])
                if not amount_ok and rec["csv_net"] is not None and c["net"] is not None:
                    amount_ok = (rec["csv_net"] == c["net"])
                if amount_ok:
                    sim = jaccard(rec["desc_tokens"], c["desc_tokens"])
                    t2.append((sim, c))
            if t2:
                t2.sort(key=lambda x: x[0], reverse=True)
                sim, c = t2[0]
                if sim >= 0.5 or (not rec["desc_tokens"] and not c["desc_tokens"]):
                    cls = "PRESENT_STRONG"
                    tier = "T2"
                    reason = f"date/account/amount exact; description similarity={sim:.2f}"
                    matched = c
                    t2_hits += 1
                else:
                    cls = "MISMATCH_IN_ALMS"
                    tier = "T2"
                    reason = f"date/account/amount matched but description differs (sim={sim:.2f})"
                    matched = c

        # T3
        if cls is None:
            cands = idx_t3.get((rec["date"], rec["account_norm"], rec["csv_net"]), []) if rec["date"] and rec["account_norm"] and rec["csv_net"] is not None else []
            if cands:
                cls = "PRESENT_WEAK"
                tier = "T3"
                reason = "date/account/net amount match"
                matched = cands[0]
                t3_hits += 1

        # mismatch/missing fallback
        if cls is None:
            da_cands = idx_date_account.get((rec["date"], rec["account_norm"]), []) if rec["date"] and rec["account_norm"] else []
            if da_cands:
                cls = "MISMATCH_IN_ALMS"
                tier = "FALLBACK"
                reason = "date+account exists in ALMS but amount/key not matched"
                matched = da_cands[0]
            else:
                cls = "MISSING_IN_ALMS"
                tier = "FALLBACK"
                reason = "no candidate found by key/date/account/amount"

        class_counts[cls] += 1
        out = {
            **rec,
            "classification": cls,
            "match_tier": tier,
            "reason": reason,
            "alms_id": matched["id"] if matched else "",
            "alms_date": matched["date"].isoformat() if matched and matched["date"] else "",
            "alms_account_code": matched["account_code"] if matched else "",
            "alms_account_name": matched["account_name"] if matched else "",
            "alms_description": matched["description"] if matched else "",
            "alms_debit": matched["debit"] if matched else "",
            "alms_credit": matched["credit"] if matched else "",
            "alms_net": matched["net"] if matched else "",
        }
        all_results.append(out)

    key_stats.extend([
        {"file": csv_path.name, "metric": "raw_rows", "value": len(rows)},
        {"file": csv_path.name, "metric": "comparable_rows", "value": len(parsed_rows)},
        {"file": csv_path.name, "metric": "t1_strong_hits", "value": t1_hits},
        {"file": csv_path.name, "metric": "t2_strong_hits", "value": t2_hits},
        {"file": csv_path.name, "metric": "t3_weak_hits", "value": t3_hits},
    ] + [{"file": csv_path.name, "metric": f"class_{k}", "value": v} for k, v in sorted(class_counts.items())])

# Write row outputs
row_fields = [
    "file","line_number","classification","match_tier","reason",
    "raw_date","date","account_raw","account_code","account_name","description",
    "csv_key_raw","csv_debit","csv_credit","csv_net",
    "alms_id","alms_date","alms_account_code","alms_account_name","alms_description","alms_debit","alms_credit","alms_net"
]

def fmt(v):
    if isinstance(v, Decimal):
        return f"{v:.2f}"
    return "" if v is None else str(v)

with ROW_RESULTS_PATH.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=row_fields)
    w.writeheader()
    for r in all_results:
        rr = {k: fmt(r.get(k)) for k in row_fields}
        w.writerow(rr)

for target, klass in ((MISSING_PATH, "MISSING_IN_ALMS"), (MISMATCH_PATH, "MISMATCH_IN_ALMS")):
    with target.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=row_fields)
        w.writeheader()
        for r in all_results:
            if r.get("classification") == klass:
                rr = {k: fmt(r.get(k)) for k in row_fields}
                w.writerow(rr)

with KEY_STATS_PATH.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["file", "metric", "value"])
    w.writeheader()
    for r in key_stats:
        w.writerow(r)

# Summary text
combined = Counter(r["classification"] for r in all_results)
per_file = defaultdict(Counter)
for r in all_results:
    per_file[r["file"]][r["classification"]] += 1

high_risk = [r for r in all_results if r["classification"] in {"MISSING_IN_ALMS", "MISMATCH_IN_ALMS"}]
high_risk.sort(key=lambda x: row_amount_abs(x), reverse=True)

lines = []
lines.append("GL CSV vs ALMS unified_general_ledger audit")
lines.append("")
lines.append("Schema/profile by file:")
for n in schema_notes:
    lines.append(f"- {n['file']}: raw_rows={n['raw_rows']}, comparable_rows={n['comparable_rows']}, date_range={n['date_min']}..{n['date_max']}")
    lines.append(f"  headers={n['headers']}")
    lines.append(f"  amount_columns_detected={n['amount_columns']}")
lines.append("")
lines.append("Per-file class totals:")
for fn, c in per_file.items():
    lines.append(f"- {fn}: PRESENT_STRONG={c['PRESENT_STRONG']}, PRESENT_WEAK={c['PRESENT_WEAK']}, MISSING_IN_ALMS={c['MISSING_IN_ALMS']}, MISMATCH_IN_ALMS={c['MISMATCH_IN_ALMS']}")
lines.append("")
lines.append("Combined class totals:")
lines.append(f"PRESENT_STRONG={combined['PRESENT_STRONG']}")
lines.append(f"PRESENT_WEAK={combined['PRESENT_WEAK']}")
lines.append(f"MISSING_IN_ALMS={combined['MISSING_IN_ALMS']}")
lines.append(f"MISMATCH_IN_ALMS={combined['MISMATCH_IN_ALMS']}")
lines.append("")
lines.append("Top 20 high-amount missing/mismatch rows:")
for r in high_risk[:20]:
    lines.append(
        f"{r['file']} line={r['line_number']} class={r['classification']} date={r['date']} acct={r['account_raw']} net={fmt(r['csv_net'])} debit={fmt(r['csv_debit'])} credit={fmt(r['csv_credit'])} key={r['csv_key_raw']} reason={r['reason']}"
    )

SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

# Console concise totals + first 10 lines of each output file
print("KEY TOTALS")
for fn, c in per_file.items():
    print(f"{fn}: STRONG={c['PRESENT_STRONG']} WEAK={c['PRESENT_WEAK']} MISSING={c['MISSING_IN_ALMS']} MISMATCH={c['MISMATCH_IN_ALMS']}")
print(f"COMBINED: STRONG={combined['PRESENT_STRONG']} WEAK={combined['PRESENT_WEAK']} MISSING={combined['MISSING_IN_ALMS']} MISMATCH={combined['MISMATCH_IN_ALMS']}")

for p in [SUMMARY_PATH, ROW_RESULTS_PATH, MISSING_PATH, MISMATCH_PATH, KEY_STATS_PATH]:
    print(f"\n=== {p.name} (first 10 lines) ===")
    with p.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 10:
                break
            print(line.rstrip("\n"))
