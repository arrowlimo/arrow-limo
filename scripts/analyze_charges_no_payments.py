#!/usr/bin/env python
"""
Report charters that have charges but no payments applied.
Criteria:
  A) charter_charges sum(amount) > 0 OR charters.total_amount_due > 0
  B) No rows in charter_payments for that reserve_number
  C) charters.paid_amount IS NULL OR = 0
Outputs:
  - Summary counts
  - Year breakdown
  - Top 50 largest outstanding amounts
  - CSV export: reports/charters_with_charges_no_payments.csv
"""
import psycopg2, csv, os, argparse
from decimal import Decimal
from collections import defaultdict

parser = argparse.ArgumentParser(description='Report charters that have charges but no payments applied.')
parser.add_argument('--include-cancelled', action='store_true',
                    help='Include cancelled charters in the output (default excludes them).')
parser.add_argument('--csv', default='reports/charters_with_charges_no_payments.csv',
                    help='Output CSV path.')
parser.add_argument('--include-refunded', action='store_true',
                    help='Include charters that appear refunded/discounted (notes or GST-only pattern).')
args = parser.parse_args()

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*100)
print('Charters with CHARGES but NO PAYMENTS')
print('='*100)

# Build a temp set of sums from charter_charges
cur.execute("""
    WITH charge_sum AS (
        SELECT reserve_number, ROUND(SUM(amount)::numeric,2) AS charges
        FROM charter_charges
        GROUP BY reserve_number
    ), candidate AS (
        SELECT c.reserve_number,
               c.charter_date,
               c.account_number,
               c.status,
               c.cancelled,
               c.total_amount_due,
               COALESCE(cs.charges,0) AS charge_sum,
               COALESCE(c.paid_amount,0) AS paid_amount,
               COALESCE(c.balance, (COALESCE(c.total_amount_due, cs.charges) - COALESCE(c.paid_amount,0))) AS balance
        FROM charters c
        LEFT JOIN charge_sum cs ON cs.reserve_number = c.reserve_number
        WHERE (COALESCE(cs.charges,0) > 0 OR COALESCE(c.total_amount_due,0) > 0)
          AND COALESCE(c.paid_amount,0) = 0
          AND NOT EXISTS (
                SELECT 1 FROM charter_payments cp WHERE cp.charter_id = c.reserve_number
          )
    )
    SELECT * FROM candidate
    ORDER BY balance DESC NULLS LAST
""")
rows = cur.fetchall()

if not rows:
    print('No charters meet criteria.')
    cur.close(); conn.close(); exit(0)

original_len = len(rows)

# Exclude cancelled unless explicitly included
if rows and not args.include_cancelled:
    filtered = []
    for r in rows:
        _, _, _, status, cancelled, *_ = r
        status_str = (status or '').lower()
        if cancelled or status_str.startswith('cancel'):
            continue
        filtered.append(r)
    excluded = original_len - len(filtered)
    rows = filtered
    print(f"Excluded cancelled: {excluded} (use --include-cancelled to include)")

refund_excluded = 0
if rows and not args.include_refunded:
    filtered2 = []
    # Keyword set for discount/refund/comp scenarios
    KW = {
        'refund','refunded','discount','disc','comp','complimentary','comped',
        'no charge','no-charge','waive','waived','waiver','write off','write-off','writeoff',
        'promo','promotion','free','courtesy','credit','rebate','void','voided','cancelled charge','cancelling charges'
    }
    for r in rows:
        reserve_number, charter_date, account_number, status, cancelled, total_amount_due, charge_sum, paid_amount, balance = r
        # Heuristics: exclude if notes indicate refund/discount OR charge components are strictly base+gst where gst < total*0.07
        # Fetch charge components lazily for heuristic (only GST/base fee patterns)
        cur2 = conn.cursor()
        cur2.execute("SELECT description, amount FROM charter_charges WHERE reserve_number=%s", (reserve_number,))
        charge_rows = cur2.fetchall()
        cur2.close()
        descs = ' '.join((d or '').lower() for d, _ in charge_rows)
        # Pattern flags
        refunded_flag = any(k in descs for k in KW)
        # Also inspect charter notes for signals
        if not refunded_flag:
            cur3 = conn.cursor()
            cur3.execute("SELECT COALESCE(notes,'') || ' ' || COALESCE(booking_notes,'') || ' ' || COALESCE(client_notes,'') FROM charters WHERE reserve_number=%s", (reserve_number,))
            notes_blob = (cur3.fetchone() or [''])[0].lower()
            cur3.close()
            if any(k in notes_blob for k in KW):
                refunded_flag = True
        # Recognize full charge already split into fee + fuel + gst only (normal) -> keep
        # If there is a negative amount row (true refund component), exclude
        has_negative = any(a < 0 for _, a in charge_rows)
        if refunded_flag or has_negative:
            refund_excluded += 1
            continue
        filtered2.append(r)
    rows = filtered2
    if refund_excluded:
        print(f"Excluded refunded/discounted: {refund_excluded} (use --include-refunded to include)")

print(f"Total charters with charges and no payments: {len(rows):,}")

# Year breakdown
year_counts = defaultdict(int)
for r in rows:
    _, charter_date, *_ = r
    if charter_date:
        year_counts[charter_date.year] += 1
    else:
        year_counts['(no date)'] += 1

print('\nBy Year:')
for y in sorted(year_counts, key=lambda k: (9999 if k=='(no date)' else k), reverse=True):
    print(f"  {y}: {year_counts[y]}")

# Top 50 largest outstanding
print('\nTop 50 largest outstanding (balance descending):')
for r in rows[:50]:
    reserve_number, charter_date, account_number, status, cancelled, total_amount_due, charge_sum, paid_amount, balance = r
    charges_source = total_amount_due if (total_amount_due and total_amount_due>0) else charge_sum
    print(f"  {reserve_number} date={charter_date} acct={account_number} status={status} cancelled={cancelled} charges={charges_source} balance={balance}")

# Aggregate total outstanding
total_outstanding = sum((r[8] or 0) for r in rows)
print(f"\nAggregate outstanding (sum(balance)): {Decimal(total_outstanding):,.2f}")

# Export CSV
os.makedirs('reports', exist_ok=True)
outfile = args.csv
with open(outfile, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['Reserve Number','Charter Date','Account Number','Status','Cancelled','Total Amount Due','Charge Sum','Paid Amount','Balance'])
    for r in rows:
        w.writerow(r)
print(f"\nCSV exported: {outfile}")

cur.close(); conn.close()
print('\nDone.')
