#!/usr/bin/env python3
"""
Monthly reconciliation (2012): CIBC + Scotia statements vs QB vs Database
- Loads monthly JSONs for CIBC statements, Scotia statements, and Scotia QB reconciliation
- Sums deposits (credits) and withdrawals (debits) per month and compares to DB
- Outputs TXT and JSON summary with PASS/FAIL per month (±$1 tolerance)

Inputs (if present):
  - L:\\limo\\staging\\2012_comparison\\cibc_statement_monthly_2012.json
  - L:\\limo\\staging\\2012_comparison\\scotia_statement_monthly_2012.json
  - L:\\limo\\staging\\2012_comparison\\scotia_qb_monthly_2012.json

Outputs:
  - L:\\limo\\staging\\2012_comparison\\monthly_reconciliation_all_accounts_2012.json
  - L:\\limo\\staging\\2012_comparison\\monthly_reconciliation_all_accounts_2012.txt
"""
from __future__ import annotations
from pathlib import Path
import json
import os
from decimal import Decimal
from typing import Dict, Tuple
import psycopg2

ROOT = Path(r"L:\\limo\\staging\\2012_comparison")
CIBC_STATEMENTS = ROOT / "cibc_statement_monthly_2012.json"
SCOTIA_STATEMENTS = ROOT / "scotia_statement_monthly_2012.json"
SCOTIA_QB = ROOT / "scotia_qb_monthly_2012.json"
OUT_JSON = ROOT / "monthly_reconciliation_all_accounts_2012.json"
OUT_TXT = ROOT / "monthly_reconciliation_all_accounts_2012.txt"

YEAR = 2012
TOL = Decimal('1.00')


def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def to_d(d) -> Decimal:
    if d is None:
        return Decimal('0')
    return Decimal(str(d))


def summarize_statements(cibc, scotia) -> Dict[str, Tuple[Decimal, Decimal]]:
    """Return dict month -> (deposits, withdrawals). Missing months default to 0."""
    res: Dict[str, Tuple[Decimal, Decimal]] = {f"{YEAR}-{m:02d}": (Decimal('0'), Decimal('0')) for m in range(1, 13)}
    if cibc:
        for m in cibc:
            mk = m.get('month_key')
            if mk and mk.startswith(str(YEAR)):
                dep = to_d(m.get('deposits'))
                wdr = to_d(m.get('withdrawals'))
                cd, cw = res.get(mk, (Decimal('0'), Decimal('0')))
                res[mk] = (cd + dep, cw + wdr)
    if scotia:
        for m in scotia:
            mk = m.get('month_key')
            if mk and mk.startswith(str(YEAR)):
                dep = to_d(m.get('deposits'))
                wdr = to_d(m.get('withdrawals'))
                cd, cw = res.get(mk, (Decimal('0'), Decimal('0')))
                res[mk] = (cd + dep, cw + wdr)
    return res


def summarize_qb(scotia_qb) -> Dict[str, Tuple[Decimal, Decimal]]:
    """Return dict month -> (deposits, payments) from QB. Only Scotia QB currently available."""
    res: Dict[str, Tuple[Decimal, Decimal]] = {}
    if not scotia_qb:
        return res
    for m in scotia_qb:
        mk = m.get('month_key')
        if mk and mk.startswith(str(YEAR)):
            dep = to_d(m.get('cleared_deposits')) if 'cleared_deposits' in m else to_d(m.get('deposits'))
            pay = to_d(m.get('cleared_payments')) if 'cleared_payments' in m else to_d(m.get('payments'))
            res[mk] = (dep, pay)
    return res


def get_db_connection():
    host = os.environ.get('DB_HOST', 'localhost')
    dbname = os.environ.get('DB_NAME', 'almsdata')
    user = os.environ.get('DB_USER', 'postgres')
    password = os.environ.get('DB_PASSWORD', '***REDACTED***')
    return psycopg2.connect(host=host, dbname=dbname, user=user, password=password)


def db_monthly_sums() -> Dict[str, Tuple[Decimal, Decimal]]:
    q = """
        SELECT to_char(transaction_date, 'YYYY-MM') AS ym,
               COALESCE(SUM(credit_amount), 0) AS credits,
               COALESCE(SUM(debit_amount), 0) AS debits
        FROM banking_transactions
        WHERE transaction_date >= %s AND transaction_date < %s
        GROUP BY 1
    """
    res: Dict[str, Tuple[Decimal, Decimal]] = {f"{YEAR}-{m:02d}": (Decimal('0'), Decimal('0')) for m in range(1, 13)}
    start = f"{YEAR}-01-01"
    end = f"{YEAR+1}-01-01"
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(q, (start, end))
        for ym, credits, debits in cur.fetchall():
            res[ym] = (Decimal(str(credits)), Decimal(str(debits)))
        cur.close(); conn.close()
    except Exception as e:
        print(f"WARN: DB query failed: {e}")
    return res


def main():
    cibc = load_json(CIBC_STATEMENTS)
    scotia = load_json(SCOTIA_STATEMENTS)
    scotia_qb = load_json(SCOTIA_QB)

    stmts = summarize_statements(cibc, scotia)
    qb = summarize_qb(scotia_qb)
    db = db_monthly_sums()

    months = [f"{YEAR}-{m:02d}" for m in range(1, 13)]
    rows = []
    totals = {
        'stmts_dep': Decimal('0'), 'stmts_wdr': Decimal('0'),
        'qb_dep': Decimal('0'), 'qb_pay': Decimal('0'),
        'db_cr': Decimal('0'), 'db_db': Decimal('0'),
    }

    for mk in months:
        s_dep, s_wdr = stmts.get(mk, (Decimal('0'), Decimal('0')))
        q_dep, q_pay = qb.get(mk, (Decimal('0'), Decimal('0')))
        d_cr, d_db = db.get(mk, (Decimal('0'), Decimal('0')))

        pass_dep = (abs((s_dep) - d_cr) <= TOL)
        pass_wdr = (abs((s_wdr) - d_db) <= TOL)

        rows.append({
            'month': mk,
            'statements': {'deposits': float(s_dep), 'withdrawals': float(s_wdr)},
            'qb': {'deposits': float(q_dep), 'payments': float(q_pay)},
            'db': {'credits': float(d_cr), 'debits': float(d_db)},
            'pass_deposits_vs_db': pass_dep,
            'pass_withdrawals_vs_db': pass_wdr,
            'delta_deposits': float(s_dep - d_cr),
            'delta_withdrawals': float(s_wdr - d_db),
        })

        totals['stmts_dep'] += s_dep
        totals['stmts_wdr'] += s_wdr
        totals['qb_dep'] += q_dep
        totals['qb_pay'] += q_pay
        totals['db_cr'] += d_cr
        totals['db_db'] += d_db

    # Write JSON
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as jf:
        json.dump({'year': YEAR, 'months': rows, 'totals': {k: float(v) for k, v in totals.items()}}, jf, indent=2)

    # Write TXT
    lines = []
    lines.append(f"MONTHLY RECONCILIATION (All Accounts) {YEAR}")
    lines.append('=' * 80)
    lines.append('')
    for r in rows:
        mk = r['month']
        s = r['statements']; q = r['qb']; d = r['db']
        lines.append(f"{mk}")
        lines.append(f"  Statements:  Deposits ${s['deposits']:,.2f} | Withdrawals ${s['withdrawals']:,.2f}")
        lines.append(f"  QB (Scotia): Deposits ${q['deposits']:,.2f} | Payments ${q['payments']:,.2f}")
        lines.append(f"  DB:          Credits  ${d['credits']:,.2f} | Debits     ${d['debits']:,.2f}")
        lines.append(f"  PASS Deposits vs DB: {r['pass_deposits_vs_db']} (Δ ${r['delta_deposits']:,.2f})")
        lines.append(f"  PASS Withdrawals vs DB: {r['pass_withdrawals_vs_db']} (Δ ${r['delta_withdrawals']:,.2f})")
        lines.append('')
    lines.append('-' * 80)
    lines.append(f"TOTALS (Statements): Deposits ${totals['stmts_dep']:,.2f} | Withdrawals ${totals['stmts_wdr']:,.2f}")
    lines.append(f"TOTALS (QB Scotia): Deposits ${totals['qb_dep']:,.2f} | Payments ${totals['qb_pay']:,.2f}")
    lines.append(f"TOTALS (DB):        Credits  ${totals['db_cr']:,.2f} | Debits     ${totals['db_db']:,.2f}")

    with open(OUT_TXT, 'w', encoding='utf-8') as tf:
        tf.write('\n'.join(lines))

    print(f"Saved combined monthly reconciliation: {OUT_TXT}")


if __name__ == '__main__':
    main()
