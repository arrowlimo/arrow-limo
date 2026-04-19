import os
import re
import pandas as pd
import numpy as np
import psycopg2

excel_path = r"E:\new shit\working files\docs\2012-2013 excel\2012 Reconcile Cash Receipts.xlsx"
report_path = r"L:\limo\reports\excel_vs_alms_cash_receipts_2012_2013_20260417.csv"
os.makedirs(os.path.dirname(report_path), exist_ok=True)

amount_keywords = ["amount", "total", "debit", "credit", "payment", "receipt", "cash"]
primary_priority = ["receipt", "payment", "cash", "amount", "total", "debit", "credit"]

def normalize(col):
    return re.sub(r"\s+", " ", str(col).strip().lower())

def is_amount_col(name):
    n = normalize(name)
    return any(k in n for k in amount_keywords)

def score_primary(name):
    n = normalize(name)
    for i, k in enumerate(primary_priority):
        if k in n:
            return i
    return 999

def to_numeric_series(s):
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce")
    cleaned = s.astype(str).str.replace(r"[,$() ]", "", regex=True).str.replace(r"^-$", "", regex=True)
    cleaned = cleaned.str.replace("(", "-", regex=False).str.replace(")", "", regex=False)
    return pd.to_numeric(cleaned, errors="coerce")

def date_like_col(name, series):
    n = normalize(name)
    if "date" in n:
        return True
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if series.dropna().empty:
        return False
    sample = series.dropna().astype(str).head(100)
    parsed = pd.to_datetime(sample, errors="coerce", infer_datetime_format=True)
    ratio = parsed.notna().mean() if len(parsed) else 0
    return ratio >= 0.6

wb = pd.read_excel(excel_path, sheet_name=None)

sheet_metrics = []
overall_primary_sum = 0.0
overall_all_amount_sum = 0.0

for sheet, df in wb.items():
    row_count = len(df)
    col_names = list(df.columns)

    amount_cols = []
    amount_col_sums = {}
    for c in col_names:
        if is_amount_col(c):
            ns = to_numeric_series(df[c])
            if ns.notna().sum() > 0:
                amount_cols.append(c)
                amount_col_sums[c] = float(ns.sum(skipna=True))

    date_cols = [c for c in col_names if date_like_col(c, df[c])]

    primary_col = None
    primary_sum = 0.0
    if amount_cols:
        sorted_cols = sorted(
            amount_cols,
            key=lambda c: (
                score_primary(c),
                -to_numeric_series(df[c]).notna().sum(),
                c.lower(),
            ),
        )
        primary_col = sorted_cols[0]
        primary_sum = float(to_numeric_series(df[primary_col]).sum(skipna=True))

    all_amount_sum = float(sum(amount_col_sums.values()))
    overall_primary_sum += primary_sum
    overall_all_amount_sum += all_amount_sum

    sheet_metrics.append({
        "sheet": sheet,
        "rows": row_count,
        "date_columns": "; ".join(map(str, date_cols)) if date_cols else "",
        "amount_columns": "; ".join(map(str, amount_cols)) if amount_cols else "",
        "primary_amount_column": str(primary_col) if primary_col is not None else "",
        "primary_amount_sum": primary_sum,
        "all_detected_amount_sum": all_amount_sum,
    })

# Postgres totals
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
)

queries = {
    "alms_receipts_gross_2012_2013": """
        SELECT COALESCE(SUM(gross_amount),0)::numeric
        FROM receipts
        WHERE receipt_date >= DATE '2012-01-01'
          AND receipt_date <= DATE '2013-12-31'
    """,
    "alms_receipts_cash_2012_2013": """
        SELECT COALESCE(SUM(gross_amount),0)::numeric
        FROM receipts
        WHERE receipt_date >= DATE '2012-01-01'
          AND receipt_date <= DATE '2013-12-31'
          AND payment_method ILIKE '%cash%'
    """,
    "alms_charter_payments_2012_2013": """
        SELECT COALESCE(SUM(amount),0)::numeric
        FROM charter_payments
        WHERE payment_date >= DATE '2012-01-01'
          AND payment_date <= DATE '2013-12-31'
    """,
    "alms_charter_payments_cash_2012_2013": """
        SELECT COALESCE(SUM(amount),0)::numeric
        FROM charter_payments
        WHERE payment_date >= DATE '2012-01-01'
          AND payment_date <= DATE '2013-12-31'
          AND (
            payment_method IN ('cash','Cash','CASH')
            OR payment_method ILIKE '%cash%'
          )
    """,
}

alms_totals = {}
with conn:
    with conn.cursor() as cur:
        for k, q in queries.items():
            cur.execute(q)
            val = cur.fetchone()[0]
            alms_totals[k] = float(val) if val is not None else 0.0

conn.close()

print("=== SHEET METRICS ===")
for m in sheet_metrics:
    print(
        f"Sheet: {m['sheet']} | Rows: {m['rows']} | Date cols: {m['date_columns'] or '-'} | "
        f"Amount cols: {m['amount_columns'] or '-'} | Primary: {m['primary_amount_column'] or '-'} | "
        f"Primary sum: {m['primary_amount_sum']:.2f} | All amount sum: {m['all_detected_amount_sum']:.2f}"
    )

print("\n=== WORKBOOK TOTALS ===")
print(f"Workbook primary amount total: {overall_primary_sum:.2f}")
print(f"Workbook all-detected amount total: {overall_all_amount_sum:.2f}")

print("\n=== ALMS COMPARISON (2012-2013) ===")
comparisons = [
    ("ALMS receipts gross", alms_totals["alms_receipts_gross_2012_2013"]),
    ("ALMS receipts cash-only", alms_totals["alms_receipts_cash_2012_2013"]),
    ("ALMS charter_payments", alms_totals["alms_charter_payments_2012_2013"]),
    ("ALMS charter_payments cash-like", alms_totals["alms_charter_payments_cash_2012_2013"]),
]
for label, alms_val in comparisons:
    variance = overall_primary_sum - alms_val
    print(f"{label}: {alms_val:.2f} | Workbook primary total: {overall_primary_sum:.2f} | Variance: {variance:.2f}")

report_rows = []
for m in sheet_metrics:
    row = {"metric": "sheet_metric", **m}
    report_rows.append(row)

report_rows.extend([
    {"metric": "workbook_primary_amount_total", "value": overall_primary_sum},
    {"metric": "workbook_all_detected_amount_total", "value": overall_all_amount_sum},
    {"metric": "alms_receipts_gross_2012_2013", "value": alms_totals["alms_receipts_gross_2012_2013"]},
    {"metric": "alms_receipts_cash_2012_2013", "value": alms_totals["alms_receipts_cash_2012_2013"]},
    {"metric": "alms_charter_payments_2012_2013", "value": alms_totals["alms_charter_payments_2012_2013"]},
    {"metric": "alms_charter_payments_cash_2012_2013", "value": alms_totals["alms_charter_payments_cash_2012_2013"]},
    {"metric": "variance_vs_alms_receipts_gross", "value": overall_primary_sum - alms_totals["alms_receipts_gross_2012_2013"]},
    {"metric": "variance_vs_alms_receipts_cash", "value": overall_primary_sum - alms_totals["alms_receipts_cash_2012_2013"]},
    {"metric": "variance_vs_alms_charter_payments", "value": overall_primary_sum - alms_totals["alms_charter_payments_2012_2013"]},
    {"metric": "variance_vs_alms_charter_payments_cash", "value": overall_primary_sum - alms_totals["alms_charter_payments_cash_2012_2013"]},
])

pd.DataFrame(report_rows).to_csv(report_path, index=False)
print(f"\nReport written: {report_path}")
