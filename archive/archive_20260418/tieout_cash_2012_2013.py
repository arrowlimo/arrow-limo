import os
import pandas as pd
from collections import defaultdict, deque
import psycopg2

excel_path = r"E:\new shit\working files\docs\2012-2013 excel\2012 Reconcile Cash Receipts.xlsx"
sheet_name = "Recon.GST"
reports_dir = r"L:\limo\reports"
os.makedirs(reports_dir, exist_ok=True)

out_receipts = os.path.join(reports_dir, "tieout_excel_vs_receipts_cash_2012_2013_20260417.csv")
out_charter = os.path.join(reports_dir, "tieout_excel_vs_charter_payments_cash_2012_2013_20260417.csv")
out_summary = os.path.join(reports_dir, "tieout_excel_vs_alms_cash_summary_20260417.csv")

start_date = pd.to_datetime("2012-01-01").date()
end_date = pd.to_datetime("2013-12-31").date()


def parse_date_series(s: pd.Series) -> pd.Series:
    d1 = pd.to_datetime(s, errors="coerce")

    num = pd.to_numeric(s, errors="coerce")
    def _excel_to_dt(v):
        if pd.isna(v):
            return pd.NaT
        if abs(v) > 100000:
            return pd.NaT
        try:
            return pd.Timestamp("1899-12-30") + pd.to_timedelta(float(v), unit="D")
        except Exception:
            return pd.NaT

    d2 = num.map(_excel_to_dt)

    plausible1 = d1.between("2010-01-01", "2015-12-31", inclusive="both").sum()
    plausible2 = d2.between("2010-01-01", "2015-12-31", inclusive="both").sum()
    out = d2 if plausible2 > plausible1 else d1
    return out.dt.date


# ---------- Excel ----------
df_raw = pd.read_excel(excel_path, sheet_name=sheet_name)

norm_map = {c: str(c).strip().lower() for c in df_raw.columns}
amount_col = None
for c, lc in norm_map.items():
    if lc == "cash receipts - total":
        amount_col = c
        break
if amount_col is None:
    candidates = []
    for c in df_raw.columns:
        vals = pd.to_numeric(df_raw[c], errors="coerce")
        nn = vals.notna().sum()
        if nn == 0:
            continue
        name = str(c).lower()
        score = nn / max(len(df_raw), 1)
        for kw in ["cash", "receipt", "total", "amount", "payment"]:
            if kw in name:
                score += 1.0
        score += float(vals.abs().sum() > 0)
        candidates.append((score, c))
    if not candidates:
        raise RuntimeError("Amount column not found")
    amount_col = sorted(candidates, reverse=True)[0][1]

date_col = None
best_score = -1
for c in df_raw.columns:
    parsed = parse_date_series(df_raw[c])
    ratio = parsed.notna().mean()
    name_bonus = 0.2 if "date" in str(c).lower() else 0
    score = ratio + name_bonus
    if score > best_score:
        best_score = score
        date_col = c

if date_col is None:
    raise RuntimeError("Date column not found")

excel = df_raw.copy()
excel["excel_row_number"] = excel.index + 2
excel["excel_date"] = parse_date_series(excel[date_col])
excel["excel_amount"] = pd.to_numeric(excel[amount_col], errors="coerce").round(2)
excel = excel[(excel["excel_date"].notna()) & (excel["excel_amount"].notna()) & (excel["excel_amount"] != 0)][["excel_row_number", "excel_date", "excel_amount"]].reset_index(drop=True)

excel_row_count = int(len(excel))
excel_total = round(float(excel["excel_amount"].sum()), 2) if excel_row_count else 0.0

# ---------- DB ----------
conn = psycopg2.connect(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")

receipts_sql = """
SELECT receipt_id, receipt_date::date AS receipt_date, round(gross_amount::numeric,2) AS amount,
       payment_method, vendor_name, description
FROM receipts
WHERE receipt_date::date BETWEEN %s AND %s
  AND payment_method ILIKE '%%cash%%'
"""
receipts = pd.read_sql_query(receipts_sql, conn, params=[start_date, end_date])
if len(receipts):
    receipts["receipt_date"] = pd.to_datetime(receipts["receipt_date"]).dt.date
    receipts["amount"] = pd.to_numeric(receipts["amount"], errors="coerce").round(2)

cp_cols = pd.read_sql_query("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='charter_payments'", conn)["column_name"].tolist()
opt_cols = [c for c in ["reserve_number", "payment_id"] if c in cp_cols]
opt_sql = (", " + ", ".join(opt_cols)) if opt_cols else ""

charter_sql = f"""
SELECT id, payment_date::date AS payment_date, round(amount::numeric,2) AS amount, payment_method{opt_sql}
FROM charter_payments
WHERE payment_date::date BETWEEN %s AND %s
  AND payment_method ILIKE '%%cash%%'
"""
charter = pd.read_sql_query(charter_sql, conn, params=[start_date, end_date])
if len(charter):
    charter["payment_date"] = pd.to_datetime(charter["payment_date"]).dt.date
    charter["amount"] = pd.to_numeric(charter["amount"], errors="coerce").round(2)

conn.close()


def tieout(excel_df, source_df, source_name, source_id_col, source_date_col):
    ex = excel_df.copy().reset_index(drop=True)
    src = source_df.copy().reset_index(drop=True)

    ex["matched"] = False
    ex["match_type"] = "unmatched"
    ex["matched_source"] = source_name
    ex["matched_id"] = pd.NA
    ex["matched_date"] = pd.NaT
    ex["matched_amount"] = pd.NA

    src["matched"] = False

    ex_map = defaultdict(deque)
    src_map = defaultdict(deque)
    for i, r in ex.iterrows():
        ex_map[(r["excel_date"], float(r["excel_amount"]))].append(i)
    for j, r in src.iterrows():
        src_map[(r[source_date_col], float(r["amount"]))].append(j)

    for k in set(ex_map).intersection(src_map):
        while ex_map[k] and src_map[k]:
            i = ex_map[k].popleft()
            j = src_map[k].popleft()
            ex.at[i, "matched"] = True
            ex.at[i, "match_type"] = "exact"
            ex.at[i, "matched_id"] = src.at[j, source_id_col]
            ex.at[i, "matched_date"] = src.at[j, source_date_col]
            ex.at[i, "matched_amount"] = src.at[j, "amount"]
            src.at[j, "matched"] = True

    rem_ex = [i for i in ex.index if not ex.at[i, "matched"]]
    rem_src = [j for j in src.index if not src.at[j, "matched"]]

    amt_to_src = defaultdict(list)
    for j in rem_src:
        amt_to_src[float(src.at[j, "amount"])].append(j)

    for i in sorted(rem_ex, key=lambda x: ex.at[x, "excel_date"]):
        amt = float(ex.at[i, "excel_amount"])
        d = ex.at[i, "excel_date"]
        candidates = []
        for j in amt_to_src.get(amt, []):
            if src.at[j, "matched"]:
                continue
            sd = src.at[j, source_date_col]
            diff = abs((sd - d).days)
            if diff <= 3:
                candidates.append((diff, sd, j))
        if candidates:
            candidates.sort()
            j = candidates[0][2]
            ex.at[i, "matched"] = True
            ex.at[i, "match_type"] = "window"
            ex.at[i, "matched_id"] = src.at[j, source_id_col]
            ex.at[i, "matched_date"] = src.at[j, source_date_col]
            ex.at[i, "matched_amount"] = src.at[j, "amount"]
            src.at[j, "matched"] = True

    exact_mask = ex["match_type"].eq("exact")
    window_mask = ex["match_type"].eq("window")
    unmatched_mask = ex["match_type"].eq("unmatched")

    stats = {
        "source": source_name,
        "matched_exact_count": int(exact_mask.sum()),
        "matched_exact_sum": round(float(ex.loc[exact_mask, "excel_amount"].sum()), 2) if exact_mask.any() else 0.0,
        "matched_window_count": int(window_mask.sum()),
        "matched_window_sum": round(float(ex.loc[window_mask, "excel_amount"].sum()), 2) if window_mask.any() else 0.0,
        "unmatched_excel_count": int(unmatched_mask.sum()),
        "unmatched_excel_sum": round(float(ex.loc[unmatched_mask, "excel_amount"].sum()), 2) if unmatched_mask.any() else 0.0,
        "unmatched_source_count": int((~src["matched"]).sum()),
        "unmatched_source_sum": round(float(src.loc[~src["matched"], "amount"].sum()), 2) if len(src) else 0.0,
    }

    return ex, stats


rec_tie, rec_stats = tieout(excel, receipts, "receipts", "receipt_id", "receipt_date")
char_tie, char_stats = tieout(excel, charter, "charter_payments", "id", "payment_date")

rec_tie.to_csv(out_receipts, index=False)
char_tie.to_csv(out_charter, index=False)

summary = pd.DataFrame([
    {"source": "excel", "metric": "row_count", "value": excel_row_count},
    {"source": "excel", "metric": "total_amount", "value": excel_total},
    *[{"source": "receipts", "metric": k, "value": v} for k, v in rec_stats.items() if k != "source"],
    *[{"source": "charter_payments", "metric": k, "value": v} for k, v in char_stats.items() if k != "source"],
])
summary.to_csv(out_summary, index=False)

print(f"Excel row count: {excel_row_count}; total: {excel_total:.2f}")
print(
    f"receipts matched exact count/sum: {rec_stats['matched_exact_count']}/{rec_stats['matched_exact_sum']:.2f}; "
    f"matched window count/sum: {rec_stats['matched_window_count']}/{rec_stats['matched_window_sum']:.2f}; "
    f"unmatched excel count/sum: {rec_stats['unmatched_excel_count']}/{rec_stats['unmatched_excel_sum']:.2f}; "
    f"unmatched receipts count/sum: {rec_stats['unmatched_source_count']}/{rec_stats['unmatched_source_sum']:.2f}"
)
print(
    f"charter_payments matched exact count/sum: {char_stats['matched_exact_count']}/{char_stats['matched_exact_sum']:.2f}; "
    f"matched window count/sum: {char_stats['matched_window_count']}/{char_stats['matched_window_sum']:.2f}; "
    f"unmatched excel count/sum: {char_stats['unmatched_excel_count']}/{char_stats['unmatched_excel_sum']:.2f}; "
    f"unmatched charter_payments count/sum: {char_stats['unmatched_source_count']}/{char_stats['unmatched_source_sum']:.2f}"
)
print(out_receipts)
print(out_charter)
print(out_summary)
