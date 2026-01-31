"""
2012 Reconciliation Baseline
- Counts and sums for 2012 across core tables
- Payment↔Charter coverage (by reserve_number)
- Receipts↔Bank links coverage (via bank_id)
- Outputs JSON summary to 2012_complete_analysis.json and prints concise table
"""
import os
import json
from datetime import date
import psycopg2

DB = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'dbname': os.getenv('DB_NAME', 'almsdata'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '***REDACTED***'),
}

YEAR = 2012

SQLS = {
    'charters': '''
        SELECT 
            COUNT(*) AS count,
            COALESCE(SUM(total_amount_due),0) AS total_due,
            COALESCE(SUM(paid_amount),0) AS total_paid,
            COALESCE(SUM(balance),0) AS total_balance
        FROM charters
        WHERE charter_date >= %s AND charter_date < %s
    ''',
    'payments': '''
        SELECT 
            COUNT(*) AS count,
            COALESCE(SUM(amount),0) AS total_amount,
            COUNT(*) FILTER (WHERE reserve_number IS NOT NULL) AS with_reserve,
            COUNT(*) FILTER (WHERE reserve_number IS NULL) AS without_reserve
        FROM payments
        WHERE payment_date >= %s AND payment_date < %s
    ''',
    'payments_by_reserve': '''
        SELECT 
            COUNT(DISTINCT reserve_number) AS distinct_reserves,
            COALESCE(SUM(amount),0) AS total_amount
        FROM payments
        WHERE payment_date >= %s AND payment_date < %s
          AND reserve_number IS NOT NULL
    ''',
    # receipts built dynamically after schema introspection
    'banking': '''
        SELECT 
            COUNT(*) AS count,
            COALESCE(SUM(COALESCE(credit_amount,0) - COALESCE(debit_amount,0)),0) AS net_flow,
            COALESCE(SUM(credit_amount),0) AS credits,
            COALESCE(SUM(debit_amount),0) AS debits
        FROM banking_transactions
        WHERE transaction_date >= %s AND transaction_date < %s
    ''',
    'journal': '''
        SELECT 
            COUNT(*) AS count,
            COALESCE(SUM(debit_amount),0) AS debits,
            COALESCE(SUM(credit_amount),0) AS credits
        FROM unified_general_ledger
        WHERE transaction_date >= %s AND transaction_date < %s
    ''',
    'charter_payment_compare': '''
        WITH pay AS (
            SELECT reserve_number, COALESCE(SUM(amount),0) AS paid
            FROM payments
            WHERE payment_date >= %s AND payment_date < %s
              AND reserve_number IS NOT NULL
            GROUP BY reserve_number
        )
        SELECT 
            COUNT(*) AS reserves_2012,
            COUNT(*) FILTER (WHERE ABS(c.paid_amount - COALESCE(pay.paid,0)) < 0.01) AS paid_match,
            COUNT(*) FILTER (WHERE ABS(c.paid_amount - COALESCE(pay.paid,0)) >= 0.01) AS paid_mismatch,
            COALESCE(SUM((c.paid_amount - COALESCE(pay.paid,0))::numeric),0) AS paid_diff_sum
        FROM charters c
        LEFT JOIN pay ON pay.reserve_number = c.reserve_number
        WHERE c.charter_date >= %s AND c.charter_date < %s
    '''
}


def daterange(year: int):
    return date(year,1,1), date(year+1,1,1)


def run():
    start, end = daterange(YEAR)
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    out = {'year': YEAR}

    def fetch(name, sql):
        cur.execute(sql, (start, end))
        row = cur.fetchone()
        return row

    labels = ['charters','payments','payments_by_reserve','banking','journal']
    for label in labels:
        row = fetch(label, SQLS[label])
        out[label] = tuple(map(lambda x: float(x) if isinstance(x, (int, float)) else (int(x) if isinstance(x, (bool,)) else x), row)) if row else None

    # Receipts: introspect schema to find bank link column if any
    conn2 = psycopg2.connect(**DB)
    cur2 = conn2.cursor()
    cur2.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'receipts'
    """)
    cols = {r[0] for r in cur2.fetchall()}
    link_col = None
    for candidate in ['bank_id','banking_transaction_id','bank_transaction_id','banking_id']:
        if candidate in cols:
            link_col = candidate
            break

    if link_col:
        cur2.execute(f"""
            SELECT 
                COUNT(*) AS count,
                COALESCE(SUM(gross_amount),0) AS gross_total,
                COALESCE(SUM(gst_amount),0) AS gst_total,
                COUNT(*) FILTER (WHERE {link_col} IS NOT NULL) AS linked_bank,
                COUNT(*) FILTER (WHERE {link_col} IS NULL) AS unlinked_bank
            FROM receipts
            WHERE receipt_date >= %s AND receipt_date < %s
        """, (start,end))
        out['receipts'] = cur2.fetchone()
        out['receipts_link_col'] = link_col
    else:
        # Fallback without linkage counts
        cur2.execute("""
            SELECT 
                COUNT(*) AS count,
                COALESCE(SUM(gross_amount),0) AS gross_total,
                COALESCE(SUM(gst_amount),0) AS gst_total
            FROM receipts
            WHERE receipt_date >= %s AND receipt_date < %s
        """, (start,end))
        row = cur2.fetchone()
        out['receipts'] = (row[0], row[1], row[2], None, None)
        out['receipts_link_col'] = None

    cur2.close(); conn2.close()

    # Charter vs payments compare
    cur.execute(SQLS['charter_payment_compare'], (start,end,start,end))
    out['charter_payment_compare'] = cur.fetchone()

    cur.close(); conn.close()

    # Pretty print
    print(f"=== 2012 Reconciliation Baseline ===")
    print(f"Charters: count={int(out['charters'][0])}, total_due=${out['charters'][1]:,.2f}, paid=${out['charters'][2]:,.2f}, balance=${out['charters'][3]:,.2f}")
    print(f"Payments: count={int(out['payments'][0])}, total=${out['payments'][1]:,.2f}, with_reserve={int(out['payments'][2])}, without_reserve={int(out['payments'][3])}")
    print(f"Payments by reserve: reserves={int(out['payments_by_reserve'][0])}, total=${out['payments_by_reserve'][1]:,.2f}")
    rb_link = out.get('receipts_link_col')
    if rb_link:
        print(f"Receipts: count={int(out['receipts'][0])}, gross=${out['receipts'][1]:,.2f}, gst=${out['receipts'][2]:,.2f}, linked_bank({rb_link})={int(out['receipts'][3])}, unlinked_bank={int(out['receipts'][4])}")
    else:
        print(f"Receipts: count={int(out['receipts'][0])}, gross=${out['receipts'][1]:,.2f}, gst=${out['receipts'][2]:,.2f}, linked_bank=N/A, unlinked_bank=N/A")
    print(f"Banking: count={int(out['banking'][0])}, credits=${out['banking'][2]:,.2f}, debits=${out['banking'][3]:,.2f}, net=${out['banking'][1]:,.2f}")
    print(f"UGL: count={int(out['journal'][0])}, debits=${out['journal'][1]:,.2f}, credits=${out['journal'][2]:,.2f}")
    r = out['charter_payment_compare']
    print(f"Charter vs Payments: reserves={int(r[0])}, match={int(r[1])}, mismatch={int(r[2])}, paid_diff_sum=${float(r[3]):,.2f}")

    # Write JSON
    with open('2012_complete_analysis.json','w',encoding='utf-8') as f:
        json.dump(out, f, indent=2, default=str)

if __name__ == '__main__':
    run()
