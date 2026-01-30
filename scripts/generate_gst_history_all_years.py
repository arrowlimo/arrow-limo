"""
Generate consolidated GST/HST history for ALL available years.

Data sources (in order of preference):
- unified_general_ledger: Use GST/HST account lines → credits ~ GST collected, debits ~ ITCs
- charter_gst_details_2010_2012 (if present): authoritative GST collected for 2010–2012
- receipts: Sum receipts.gst_amount as ITCs fallback
- banking_transactions: Heuristic CRA GST remittances from description/category

Output: exports/cra/GST_HISTORY_ALL_YEARS.md

Notes:
- This script is defensive: it introspects schema and gracefully degrades when a table/column is missing.
- Uses the "GST included" model for receipts only (ITCs already present as gst_amount).
- For CRA payments, matches common descriptors (Receiver General, CRA, GST, etc.), nets credits (reversals) against debits.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional, Tuple, List

import psycopg2


BASE = Path('l:/limo/exports/cra')
BASE.mkdir(parents=True, exist_ok=True)


def get_db_connection():
    host = os.getenv('DB_HOST', 'localhost')
    dbname = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REDACTED***')
    return psycopg2.connect(host=host, dbname=dbname, user=user, password=password)


def table_exists(cur, table: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
          SELECT 1 FROM information_schema.tables
          WHERE table_schema='public' AND table_name=%s
        )
        """,
        (table,)
    )
    return bool(cur.fetchone()[0])


def get_columns(cur, table: str) -> Dict[str, str]:
    cur.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name=%s
        ORDER BY ordinal_position
        """,
        (table,)
    )
    return {r[0]: r[1] for r in cur.fetchall()}


def detect_year_bounds(cur) -> Tuple[int, int]:
    """Pick the broadest min/max years from preferred tables."""
    candidates: List[Tuple[Optional[int], Optional[int]]] = []
    # unified_general_ledger
    if table_exists(cur, 'unified_general_ledger'):
        cur.execute("SELECT MIN(EXTRACT(YEAR FROM transaction_date))::int, MAX(EXTRACT(YEAR FROM transaction_date))::int FROM unified_general_ledger")
        candidates.append(cur.fetchone())
    # receipts
    if table_exists(cur, 'receipts'):
        cols = get_columns(cur, 'receipts')
        date_col = 'receipt_date' if 'receipt_date' in cols else ('created_at' if 'created_at' in cols else None)
        if date_col:
            cur.execute(f"SELECT MIN(EXTRACT(YEAR FROM {date_col}))::int, MAX(EXTRACT(YEAR FROM {date_col}))::int FROM receipts")
            candidates.append(cur.fetchone())
    # journal (optional)
    if table_exists(cur, 'journal'):
        cols = get_columns(cur, 'journal')
        date_col = 'transaction_date' if 'transaction_date' in cols else ('created_at' if 'created_at' in cols else None)
        if date_col:
            cur.execute(f"SELECT MIN(EXTRACT(YEAR FROM {date_col}))::int, MAX(EXTRACT(YEAR FROM {date_col}))::int FROM journal")
            candidates.append(cur.fetchone())

    # Fallback range if nothing found
    years = [y for pair in candidates for y in pair if y is not None]
    if not years:
        # Default to operational span from docs
        return (2007, 2026)
    return (min(years), max(years))


def summarize_gst_from_ugl(cur, year: int) -> Tuple[float, float]:
    """Return (gst_credits_collected, gst_debits_itc) for the year using UGL."""
    if not table_exists(cur, 'unified_general_ledger'):
        return (0.0, 0.0)
    # Heuristic filters for GST/HST account rows
    cur.execute(
        """
        SELECT 
          COALESCE(SUM(credit_amount), 0) AS credits,
          COALESCE(SUM(debit_amount), 0)  AS debits
        FROM unified_general_ledger
        WHERE EXTRACT(YEAR FROM transaction_date) = %s
          AND (
                LOWER(account_name) LIKE '%%gst%%'
             OR LOWER(account_name) LIKE '%%hst%%'
             OR LOWER(description) LIKE '%%gst%%'
             OR LOWER(description) LIKE '%%hst%%'
          )
        """,
        (year,)
    )
    credits, debits = cur.fetchone()
    return (float(credits or 0.0), float(debits or 0.0))


def summarize_itc_from_receipts(cur, year: int) -> float:
    if not table_exists(cur, 'receipts'):
        return 0.0
    cols = get_columns(cur, 'receipts')
    date_col = 'receipt_date' if 'receipt_date' in cols else ('created_at' if 'created_at' in cols else None)
    if not date_col:
        return 0.0
    # Only include taxable receipts when flag present; otherwise include all
    is_tax_filter = " AND is_taxable = true" if 'is_taxable' in cols else ""
    gst_col = 'gst_amount' if 'gst_amount' in cols else None
    if not gst_col:
        return 0.0
    cur.execute(
        f"""
        SELECT COALESCE(SUM({gst_col}), 0)
        FROM receipts
        WHERE EXTRACT(YEAR FROM {date_col}) = %s
        {is_tax_filter}
        """,
        (year,)
    )
    val = cur.fetchone()[0]
    return float(val or 0.0)


def summarize_cra_payments_from_banking(cur, year: int) -> float:
    if not table_exists(cur, 'banking_transactions'):
        return 0.0
    cols = get_columns(cur, 'banking_transactions')
    date_col = 'transaction_date' if 'transaction_date' in cols else None
    if not date_col:
        return 0.0
    # Prefer description; fallback to vendor_name/category if present
    text_expr = []
    for c in ('description', 'vendor_name', 'category'):
        if c in cols:
            text_expr.append(f"COALESCE(LOWER({c}), '')")
    if not text_expr:
        return 0.0
    txt = " || ' ' || ".join(text_expr)
    # Heuristic keywords for CRA GST remittances
    patterns = [
        'receiver general', 'cra', 'gst', 'rc', 'canada revenue', 'govt of canada', 'government of canada'
    ]
    like_clause = " OR ".join([f"({txt} LIKE '%%{p}%%')" for p in patterns])
    cur.execute(
        f"""
        SELECT COALESCE(SUM(debit_amount), 0) - COALESCE(SUM(credit_amount), 0) AS net_outflow
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM {date_col}) = %s
          AND ({like_clause})
        """,
        (year,)
    )
    val = cur.fetchone()[0]
    return float(val or 0.0)


def summarize_charter_details_2010_2012(cur, year: int) -> Optional[float]:
    if not table_exists(cur, 'charter_gst_details_2010_2012'):
        return None
    cur.execute(
        """
        WITH base AS (
          SELECT COALESCE(EXTRACT(YEAR FROM d.reserve_date), EXTRACT(YEAR FROM c.charter_date))::int AS year,
                 d.gst_amount
          FROM charter_gst_details_2010_2012 d
          LEFT JOIN charters c ON c.reserve_number = d.reserve_number
        )
        SELECT COALESCE(SUM(gst_amount), 0)
        FROM base WHERE year = %s
        """,
        (year,)
    )
    val = cur.fetchone()[0]
    return float(val or 0.0)


def main():
    conn = get_db_connection(); cur = conn.cursor()
    min_year, max_year = detect_year_bounds(cur)

    summary: Dict[int, Dict[str, float]] = {}
    for y in range(min_year, max_year + 1):
        s = {'gst_collected': 0.0, 'gst_itc': 0.0, 'cra_payments': 0.0}

        # 1) Prefer UGL signals
        credits, debits = summarize_gst_from_ugl(cur, y)
        if credits or debits:
            s['gst_collected'] = float(credits)
            s['gst_itc'] = float(debits)

        # 2) 2010–2012 special source for collected
        if 2010 <= y <= 2012:
            d = summarize_charter_details_2010_2012(cur, y)
            if d is not None and d > 0:
                # Use the higher signal to avoid under-reporting; UGL may under-capture by mapping
                s['gst_collected'] = max(s['gst_collected'], float(d))

        # 3) ITC fallback from receipts when UGL debits missing
        if s['gst_itc'] == 0.0:
            s['gst_itc'] = summarize_itc_from_receipts(cur, y)

        # 4) CRA payments from banking
        s['cra_payments'] = summarize_cra_payments_from_banking(cur, y)

        summary[y] = s

    # Write report
    out = BASE / 'GST_HISTORY_ALL_YEARS.md'
    total_collect = total_itc = total_pay = 0.0
    with out.open('w', encoding='utf-8') as f:
        f.write('# GST/HST History - All Years\n\n')
        f.write(f'Source priority: unified_general_ledger → 2010–2012 charter details → receipts (ITC) → banking (CRA payments).\n\n')
        for y in range(min_year, max_year + 1):
            s = summary.get(y, {'gst_collected':0.0,'gst_itc':0.0,'cra_payments':0.0})
            net = s['gst_collected'] - s['gst_itc']
            f.write(f"## {y}\n")
            f.write(f"- GST/HST Collected (credits): ${s['gst_collected']:,.2f}\n")
            f.write(f"- ITCs (debits): ${s['gst_itc']:,.2f}\n")
            f.write(f"- Net GST/HST: ${net:,.2f}\n")
            f.write(f"- CRA Payments (banking): ${s['cra_payments']:,.2f}\n\n")
            total_collect += s['gst_collected']
            total_itc += s['gst_itc']
            total_pay += s['cra_payments']
        f.write('---\n')
        f.write('**TOTAL (All Years)**\n\n')
        f.write(f"- GST/HST Collected (credits): ${total_collect:,.2f}\n")
        f.write(f"- ITCs (debits): ${total_itc:,.2f}\n")
        f.write(f"- Net GST/HST: ${total_collect - total_itc:,.2f}\n")
        f.write(f"- CRA Payments (banking): ${total_pay:,.2f}\n")

    cur.close(); conn.close()
    print(f"[OK] Wrote consolidated report: {out}")


if __name__ == '__main__':
    main()
