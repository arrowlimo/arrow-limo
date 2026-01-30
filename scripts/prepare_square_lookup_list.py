"""Prepare a lookup list of Square transaction/payment IDs for cancelled charters.

Generates CSV & console table with:
- reserve_number
- charter_date
- client_name
- total_due, paid_amount, balance
- square_transaction_ids (distinct list)
- square_payment_ids (distinct list)
- count_positive, count_refund

Only includes cancelled charters (cancelled = TRUE) that have any Square linkage.
If none exist, reports accordingly.
"""
import psycopg2
import csv
from datetime import datetime

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

def get_conn():
    return psycopg2.connect(**DB)

QUERY = """
SELECT c.reserve_number, c.charter_date, cl.client_name,
       c.total_amount_due, c.paid_amount, c.balance,
       p.payment_id, p.amount, p.payment_date,
       p.square_transaction_id, p.square_payment_id,
       COALESCE(p.square_status,'') AS square_status, COALESCE(p.notes,'') AS notes
FROM charters c
JOIN payments p ON p.reserve_number = c.reserve_number
LEFT JOIN clients cl ON cl.client_id = c.client_id
WHERE c.cancelled = TRUE
  AND (p.square_transaction_id IS NOT NULL OR p.square_payment_id IS NOT NULL)
ORDER BY c.charter_date ASC NULLS FIRST, p.payment_date ASC NULLS LAST, p.payment_id ASC
"""

REFUND_KEYWORDS = ["refund", "refunded", "reversal", "chargeback", "cancelled", "canceled"]


def classify(amount, status, notes):
    txt = (status + " " + notes).lower()
    if amount < 0:
        return 'refund'
    for kw in REFUND_KEYWORDS:
        if kw in txt:
            return 'refund'
    return 'positive'


def main():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(QUERY)
    rows = cur.fetchall()

    if not rows:
        print("No cancelled charters have Square transaction references in the database.")
        return

    data = {}
    for (reserve, cdate, client, total_due, paid, bal, payment_id, amount, pdate,
         sq_txn, sq_pid, sq_status, notes) in rows:
        entry = data.setdefault(reserve, {
            'reserve_number': reserve,
            'charter_date': cdate,
            'client_name': client or 'Unknown',
            'total_due': float(total_due or 0),
            'paid_amount': float(paid or 0),
            'balance': float(bal or 0),
            'square_txn_ids': set(),
            'square_payment_ids': set(),
            'positive_count': 0,
            'refund_count': 0,
        })
        if sq_txn:
            entry['square_txn_ids'].add(sq_txn)
        if sq_pid:
            entry['square_payment_ids'].add(sq_pid)
        cls = classify(float(amount or 0), sq_status, notes)
        if cls == 'refund':
            entry['refund_count'] += 1
        else:
            if (amount or 0) > 0:
                entry['positive_count'] += 1

    # Prepare CSV
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = f'L:/limo/reports/square_lookup_cancelled_{ts}.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow([
            'Reserve','Charter Date','Client','Total Due','Paid Amount','Balance',
            'Square Transaction IDs','Square Payment IDs','Positive Count','Refund Count'
        ])
        for e in sorted(data.values(), key=lambda x: (x['charter_date'] or datetime.min)):
            w.writerow([
                e['reserve_number'],
                e['charter_date'].strftime('%Y-%m-%d') if e['charter_date'] else '',
                e['client_name'],
                f"{e['total_due']:.2f}",
                f"{e['paid_amount']:.2f}",
                f"{e['balance']:.2f}",
                ';'.join(sorted(e['square_txn_ids'])) or '',
                ';'.join(sorted(e['square_payment_ids'])) or '',
                e['positive_count'],
                e['refund_count']
            ])

    # Console table
    print('='*110)
    print('Square Lookup List (Cancelled Charters)')
    print('='*110)
    print(f'Export: {csv_path}')
    print()
    header = f"{'Reserve':<8} {'Date':<10} {'Client':<20} {'Paid':>9} {'Bal':>9} {'TxnIDs':<36} {'PmtIDs':<36} {'Pos':>3} {'Ref':>3}"
    print(header)
    print('-'*110)
    for e in sorted(data.values(), key=lambda x: (x['charter_date'] or datetime.min)):
        txn_ids = ','.join(list(e['square_txn_ids'])[:2])  # shorten in console
        pmt_ids = ','.join(list(e['square_payment_ids'])[:2])
        print(f"{e['reserve_number']:<8} {e['charter_date'].strftime('%Y-%m-%d') if e['charter_date'] else '':<10} "
              f"{e['client_name'][:20]:<20} {e['paid_amount']:>9.2f} {e['balance']:>9.2f} "
              f"{txn_ids:<36} {pmt_ids:<36} {e['positive_count']:>3} {e['refund_count']:>3}")
    print('-'*110)
    print(f"Total cancelled w/ Square refs: {len(data)}")
    print()
    print('Instructions for manual Square lookup:')
    print('  1. Log into Square Dashboard → Transactions or Sales.')
    print('  2. Use the search box and paste a transaction ID (column Square Transaction IDs).')
    print('  3. If transaction IDs are blank, the charter has no direct Square linkage recorded.')
    print('  4. For refunds: filter by date range around the charter_date and search by amount (positive or refunded).')
    print('  5. Cross-check that any refund equals a prior captured sale; Square will only refund captured amounts.')
    print()
    print('API approach (optional): set SQUARE_ACCESS_TOKEN env var and use Square Payments API to fetch by payment_id.')
    print('Example endpoint: GET https://connect.squareup.com/v2/payments/{payment_id}')
    print('='*110)

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
