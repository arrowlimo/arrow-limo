#!/usr/bin/env python3
"""
Monthly Banking Reconciliation (2012)
- Compares CIBC statement monthly totals (from JSON export) to our database banking_transactions
- Reports per-month deposits and withdrawals with variances and PASS/FAIL within tolerance

Safe: Read-only. Outputs report to staging/2012_comparison/monthly_reconciliation_2012.txt
"""
from __future__ import annotations
import os
import json
from pathlib import Path
from decimal import Decimal
import psycopg2

STATEMENT_JSON = Path(r"L:\limo\staging\2012_comparison\cibc_statement_monthly_2012.json")
OUTPUT_TXT = Path(r"L:\limo\staging\2012_comparison\monthly_reconciliation_2012.txt")

YEAR = 2012
TOL = Decimal('1.00')  # $1 tolerance due to OCR/rounding


def get_db_connection():
    host = os.getenv('DB_HOST', 'localhost')
    name = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    # Fallback to documented local dev default if env not set
    password = os.getenv('DB_PASSWORD', '***REMOVED***')
    port = int(os.getenv('DB_PORT', '5432'))
    conn = psycopg2.connect(host=host, dbname=name, user=user, password=password, port=port)
    return conn


def load_statements() -> dict[str, dict]:
    with open(STATEMENT_JSON, 'r', encoding='utf-8') as f:
        items = json.load(f)
    out = {}
    for m in items:
        key = m.get('month_key')
        if not key:
            # try derive from period ending year-month
            key = '2012-00'
        out[key] = {
            'deposits': Decimal(str(m['deposits'])),
            'withdrawals': Decimal(str(m['withdrawals_identity'])),
            'opening': Decimal(str(m['opening'])),
            'closing': Decimal(str(m['closing'])),
            'period': m.get('period', key)
        }
    return out


def load_db_monthly() -> dict[str, dict]:
    sql = """
    SELECT to_char(date_trunc('month', transaction_date), 'YYYY-MM') AS month_key,
           COALESCE(SUM(credit_amount),0) AS deposits,
           COALESCE(SUM(debit_amount),0)  AS withdrawals
    FROM banking_transactions
    WHERE transaction_date >= %s AND transaction_date < %s
    GROUP BY 1
    ORDER BY 1;
    """
    start = f"{YEAR}-01-01"
    end = f"{YEAR+1}-01-01"
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (start, end))
            rows = cur.fetchall()
    finally:
        try:
            conn.close()
        except Exception:
            pass
    out = {}
    for month_key, deposits, withdrawals in rows:
        out[month_key] = {
            'deposits': Decimal(str(deposits or 0)),
            'withdrawals': Decimal(str(withdrawals or 0)),
        }
    return out


def fmt_money(d: Decimal | float) -> str:
    d = Decimal(str(d))
    return f"${d:,.2f}"


def main():
    if not STATEMENT_JSON.exists():
        raise SystemExit(f"Statement JSON not found: {STATEMENT_JSON}")

    stm = load_statements()
    dbm = load_db_monthly()

    # Build ordered month list from statements
    months = sorted(stm.keys())

    lines = []
    lines.append("MONTHLY BANKING RECONCILIATION (2012)")
    lines.append("=" * 80)
    lines.append("")
    header = (
        "Month  | Stmt Deposits | DB Deposits | Δ | PASS | "
        "Stmt Withdrawals | DB Withdrawals | Δ | PASS | Closing"
    )
    lines.append(header)
    lines.append("-" * len(header))

    any_fail = False
    for m in months:
        s = stm[m]
        d = dbm.get(m, {'deposits': Decimal('0'), 'withdrawals': Decimal('0')})
        dep_delta = (d['deposits'] - s['deposits']).quantize(Decimal('0.01'))
        wdr_delta = (d['withdrawals'] - s['withdrawals']).quantize(Decimal('0.01'))
        dep_pass = 'PASS' if dep_delta.copy_abs() <= TOL else 'FAIL'
        wdr_pass = 'PASS' if wdr_delta.copy_abs() <= TOL else 'FAIL'
        if dep_pass == 'FAIL' or wdr_pass == 'FAIL':
            any_fail = True
        lines.append(
            f"{m} | {fmt_money(s['deposits'])} | {fmt_money(d['deposits'])} | {fmt_money(dep_delta)} | {dep_pass} | "
            f"{fmt_money(s['withdrawals'])} | {fmt_money(d['withdrawals'])} | {fmt_money(wdr_delta)} | {wdr_pass} | "
            f"{fmt_money(s['closing'])}"
        )

    lines.append("")
    lines.append("Summary")
    lines.append("-" * 80)
    sum_s_dep = sum((v['deposits'] for v in stm.values()), Decimal('0'))
    sum_s_wdr = sum((v['withdrawals'] for v in stm.values()), Decimal('0'))
    sum_d_dep = sum((v['deposits'] for v in dbm.values() if v), Decimal('0'))
    sum_d_wdr = sum((v['withdrawals'] for v in dbm.values() if v), Decimal('0'))
    lines.append(f"Statement Deposits: {fmt_money(sum_s_dep)}")
    lines.append(f"Database  Deposits: {fmt_money(sum_d_dep)} (Δ {fmt_money((sum_d_dep - sum_s_dep).quantize(Decimal('0.01')))})")
    lines.append(f"Statement Withdrawals: {fmt_money(sum_s_wdr)}")
    lines.append(f"Database  Withdrawals: {fmt_money(sum_d_wdr)} (Δ {fmt_money((sum_d_wdr - sum_s_wdr).quantize(Decimal('0.01')))})")
    lines.append("")
    lines.append(f"Overall result: {'FAIL' if any_fail else 'PASS'} (tolerance ±{fmt_money(TOL)})")

    OUTPUT_TXT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"Saved reconciliation to: {OUTPUT_TXT}")


if __name__ == '__main__':
    main()
