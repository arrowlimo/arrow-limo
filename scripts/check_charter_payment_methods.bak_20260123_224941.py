import psycopg2
from decimal import Decimal

DSN = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

STANDARD = {'deposit', 'cash', 'check'}

def fmt_money(x):
    if x is None:
        return '$0.00'
    if isinstance(x, Decimal):
        x = float(x)
    return f"${x:,.2f}"

def main():
    conn = psycopg2.connect(**DSN)
    cur = conn.cursor()

    print('='*80)
    print('CHARTER-LINKED PAYMENTS: METHOD AUDIT')
    print('='*80)

    # Total charter-linked payments
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount),0)
        FROM payments 
        WHERE charter_id IS NOT NULL
    """)
    total_count, total_amount = cur.fetchone()
    print(f"Total charter-linked payments: {total_count:,} | Amount: {fmt_money(total_amount)}")

    # Breakdown by payment_method (lowercased; null -> '(null)')
    cur.execute("""
        SELECT 
            COALESCE(NULLIF(LOWER(TRIM(payment_method)), ''), '(null)') AS method,
            COUNT(*) AS cnt,
            COALESCE(SUM(amount),0) AS total
        FROM payments
        WHERE charter_id IS NOT NULL
        GROUP BY 1
        ORDER BY cnt DESC
    """)
    rows = cur.fetchall()

    print('\nBreakdown by payment_method (charter-linked):')
    print(f"{'method':<20} {'count':>10} {'amount':>18}")
    print('-'*60)
    for m, c, t in rows:
        print(f"{m:<20} {c:>10,} {fmt_money(t):>18}")

    # Standard vs non-standard
    std_count = sum(c for m, c, _ in rows if m in STANDARD)
    std_amount = sum(float(t) if isinstance(t, Decimal) else (t or 0.0) for m, _, t in rows if m in STANDARD)
    nonstd = [(m, c, t) for m, c, t in rows if m not in STANDARD]
    nonstd_count = sum(c for _, c, _ in nonstd)
    nonstd_amount = sum(float(t) if isinstance(t, Decimal) else (t or 0.0) for _, _, t in nonstd)

    print('\nStandard methods (deposit, cash, check):')
    print(f"Payments: {std_count:,} | Amount: {fmt_money(std_amount)}")
    print('Non-standard methods:')
    print(f"Payments: {nonstd_count:,} | Amount: {fmt_money(nonstd_amount)}")

    if nonstd:
        print('\nNon-standard method list:')
        for m, c, t in nonstd:
            print(f"  - {m:<18} {c:>8,} {fmt_money(t):>18}")

    # Payments with null/blank method
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount),0)
        FROM payments
        WHERE charter_id IS NOT NULL
          AND (payment_method IS NULL OR TRIM(payment_method)='')
    """)
    null_cnt, null_amt = cur.fetchone()
    print(f"\nNULL/blank payment_method (charter-linked): {null_cnt:,} | {fmt_money(null_amt)}")

    # Charters without any payments (non-cancelled)
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(c.balance),0)
        FROM charters c
        LEFT JOIN payments p ON p.charter_id = c.charter_id
        WHERE COALESCE(c.status, '') NOT IN ('cancelled','Cancelled')
          AND p.reserve_number IS NULL
    """)
    no_pay_cnt, no_pay_bal = cur.fetchone()
    print(f"\nCharters without any payments (non-cancelled): {no_pay_cnt:,} | Outstanding balance: {fmt_money(no_pay_bal)}")

    cur.close()
    conn.close()

    print('\nDone.')

if __name__ == '__main__':
    main()
