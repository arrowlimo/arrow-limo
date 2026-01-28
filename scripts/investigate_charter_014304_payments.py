"""Investigate payment records for charter 014304 (Balanski, Kevin).

Expected LMS snapshot (from user screenshot):
- Total charges: 700.00
- Payments: 600.00 (deposit) + 100.00 + 100.00 (American Express) = 800? or exactly 700? Screenshot shows total charges 700, payments 700, balance 0.
  Visible rows: one DEPOSIT 600.00, two RECEIVED 100.00 each.

Goal:
1. List all payments with reserve_number = '014304'.
2. List any payments where notes/status/payment_key contains '014304' but reserve_number differs or is NULL.
3. Summarize totals: positive amounts, negative (refunds), count rows.
4. Identify missing expected payments (two 100.00 payments) if not present.
5. Produce suggested remediation SQL (INSERT ... WHERE NOT EXISTS) or UPDATE linking orphaned payments.

Output: console report + CSV under reports/investigate_charter_014304_YYYYMMDD_HHMMSS.csv
"""
import psycopg2, csv
from datetime import datetime

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
TARGET = '014304'

SEARCH_LIKE_COLUMNS = ['notes','status','payment_key','reference_number']

def get_conn():
    return psycopg2.connect(**DB)

PRIMARY_QUERY = """
SELECT payment_id, reserve_number, charter_id, client_id, amount, payment_method, payment_date,
       payment_key, status, notes, created_at
FROM payments
WHERE reserve_number = %s
ORDER BY payment_date ASC NULLS LAST, payment_id ASC
"""

ORPHAN_QUERY = """
SELECT payment_id, reserve_number, charter_id, client_id, amount, payment_method, payment_date,
       payment_key, status, notes, created_at
FROM payments
WHERE (reserve_number IS NULL OR reserve_number <> %s)
  AND (
    LOWER(COALESCE(notes,'')) LIKE %s OR
    LOWER(COALESCE(status,'')) LIKE %s OR
    LOWER(COALESCE(payment_key,'')) LIKE %s OR
    LOWER(COALESCE(reference_number,'')) LIKE %s
  )
ORDER BY payment_date ASC NULLS LAST, payment_id ASC
"""

def main():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(PRIMARY_QUERY, (TARGET,))
    primary = cur.fetchall()

    like_pattern = f"%{TARGET.lower()}%"
    cur.execute(ORPHAN_QUERY, (TARGET, like_pattern, like_pattern, like_pattern, like_pattern))
    orphan = cur.fetchall()

    # Aggregate primary totals
    pos_total = sum((r[4] or 0) for r in primary if (r[4] or 0) > 0)
    neg_total = sum((r[4] or 0) for r in primary if (r[4] or 0) < 0)

    expected_payments = [600.00, 100.00, 100.00]
    missing = []
    amounts_present = [round((r[4] or 0),2) for r in primary]
    for exp in expected_payments:
        if amounts_present.count(exp) < expected_payments.count(exp):
            # simplistic: if not all expected duplicates appear
            if exp not in amounts_present or amounts_present.count(exp) < expected_payments.count(exp):
                # determine deficit
                deficit = expected_payments.count(exp) - amounts_present.count(exp)
                for _ in range(deficit):
                    missing.append(exp)

    # Prepare CSV
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = f'L:/limo/reports/investigate_charter_014304_{ts}.csv'
    with open(csv_path,'w',newline='',encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Section','payment_id','reserve_number','charter_id','client_id','amount','payment_method','payment_date','payment_key','status','notes','created_at'])
        for r in primary:
            w.writerow(['PRIMARY'] + list(r))
        for r in orphan:
            w.writerow(['ORPHAN_MATCH'] + list(r))
        w.writerow(['SUMMARY','pos_total',pos_total,'neg_total',neg_total,'net',pos_total+neg_total,'missing',';'.join(str(m) for m in missing)])

    print('='*100)
    print(f'Charter Payment Investigation for {TARGET}')
    print('='*100)
    print(f'Export: {csv_path}')
    print(f'Primary payment rows: {len(primary)}  | Orphan textual matches: {len(orphan)}')
    print(f'Positive total: {pos_total:.2f}  Negative total: {neg_total:.2f}  Net: {pos_total+neg_total:.2f}')
    if missing:
        print(f'MISSING expected payments (based on LMS snapshot): {missing}')
    else:
        print('All expected payment amounts present (600 + two 100s).')
    print('\nPRIMARY PAYMENTS:')
    for r in primary:
        pid,res, cid, client_id, amt, method, pdate, pkey, status, notes, created_at = r
        print(f'  ID {pid:<6} amt {amt:>8.2f} date {pdate} method {method or ""} key {pkey or ""} status {status or ""}')
    if orphan:
        print('\nORPHAN TEXT MATCHES (contain 014304 in textual fields but not linked):')
        for r in orphan[:25]:
            pid,res, cid, client_id, amt, method, pdate, pkey, status, notes, created_at = r
            print(f'  ORPHAN ID {pid:<6} amt {amt:>8.2f} date {pdate} reserve={res or "(NULL)"} method {method or ""} key {pkey or ""}')
    # Remediation suggestions
    print('\nRemediation Suggestions:')
    if missing:
        for m in missing:
            print(f"  INSERT suggested: Payment {m:.2f} for reserve {TARGET} if verified in source systems. Use idempotent pattern:")
            print(f"    INSERT INTO payments (reserve_number, amount, payment_date, payment_method, notes)\n"\
                  f"    SELECT '{TARGET}', {m:.2f}, DATE '2019-06-06', 'credit_card', 'Imported from LMS fix'\n"\
                  f"    WHERE NOT EXISTS (SELECT 1 FROM payments WHERE reserve_number='{TARGET}' AND amount={m:.2f} AND payment_date=DATE '2019-06-06');")
    else:
        print('  No insertion required; focus on balance recalculation if charter.balance still shows 100.00.')
        print("  Recalculate charter paid_amount via reserve_number aggregation:")
        print("    WITH payment_sums AS (SELECT reserve_number, SUM(amount) AS s FROM payments GROUP BY reserve_number)\n"\
              "    UPDATE charters c SET paid_amount = ps.s, balance = c.total_amount_due - ps.s FROM payment_sums ps WHERE c.reserve_number = ps.reserve_number AND c.reserve_number='014304';")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
