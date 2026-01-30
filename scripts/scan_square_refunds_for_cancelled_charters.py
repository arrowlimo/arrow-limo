"""Scan Square payment data for cancelled charters with outstanding balances.

Focus: Square-specific columns; identify original payments vs refunds.
Rules:
- Square payments identified by square_transaction_id OR square_payment_id NOT NULL.
- Original payment: amount > 0 AND (square_status IS NULL OR NOT LIKE '%refund%'/'%canceled%').
- Refund payment: amount < 0 OR square_status ILIKE '%refund%' OR notes/status contains 'refund'.
- Validate: absolute total refunds <= original positive total (Square hash integrity).
- Flag anomalies: refunds without prior positive payment or refund exceeding original total.

Output:
- Console summary table.
- CSV export with per-charter metrics.

"""
import psycopg2
import csv
from datetime import datetime

KEYWORDS_REFUND = ["refund", "refunded", "reversal", "chargeback", "cancelled", "canceled"]

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

def get_conn():
    return psycopg2.connect(**DB)

def fetch_cancelled_with_balance(cur):
    cur.execute("""
        SELECT c.reserve_number, c.charter_date, cl.client_name, c.total_amount_due,
               c.paid_amount, c.balance
        FROM charters c
        LEFT JOIN clients cl ON cl.client_id = c.client_id
        WHERE c.cancelled = TRUE AND c.balance > 0.01
        ORDER BY c.charter_date ASC NULLS FIRST
    """)
    return cur.fetchall()

def fetch_square_payments(cur, reserves):
    cur.execute("""
        SELECT reserve_number, payment_id, amount, payment_date,
               COALESCE(square_status,''), COALESCE(notes,''),
               square_transaction_id, square_payment_id
        FROM payments
        WHERE reserve_number = ANY(%s)
          AND (square_transaction_id IS NOT NULL OR square_payment_id IS NOT NULL)
        ORDER BY payment_date ASC NULLS LAST, payment_id ASC
    """, (reserves,))
    return cur.fetchall()

def is_refund(amount, status_text, notes_text):
    txt = (status_text + ' ' + notes_text).lower()
    if amount < 0:  # negative amount => refund
        return True
    for kw in KEYWORDS_REFUND:
        if kw in txt:
            return True
    return False


def main():
    conn = get_conn()
    cur = conn.cursor()

    cancelled = fetch_cancelled_with_balance(cur)
    if not cancelled:
        print("No cancelled charters with outstanding balances.")
        return
    reserves = [r[0] for r in cancelled]

    square_rows = fetch_square_payments(cur, reserves)

    by_reserve = {}
    for r in cancelled:
        by_reserve[r[0]] = {
            'reserve_number': r[0],
            'charter_date': r[1],
            'client_name': r[2] or 'Unknown',
            'total_due': float(r[3] or 0),
            'paid_amount': float(r[4] or 0),
            'recorded_balance': float(r[5] or 0),
            'square_positive': 0.0,
            'square_refund': 0.0,
            'square_payment_count': 0,
            'square_refund_count': 0,
            'first_square_payment_date': None,
            'first_square_refund_date': None,
            'refund_exceeds_original': False,
            'refund_without_original': False,
            'refund_gap_vs_paid': 0.0,
            'transaction_ids': [],
        }

    for reserve_number, payment_id, amount, payment_date, square_status, notes, sq_txn, sq_pid in square_rows:
        entry = by_reserve.get(reserve_number)
        if not entry:
            continue
        entry['square_payment_count'] += 1
        entry['transaction_ids'].append(sq_txn or sq_pid or str(payment_id))
        # Ensure numeric is float
        amt = float(amount or 0)
        refund = is_refund(amt, square_status, notes)
        if refund:
            entry['square_refund'] += amt
            entry['square_refund_count'] += 1
            if not entry['first_square_refund_date'] and payment_date:
                entry['first_square_refund_date'] = payment_date
        else:
            if amt > 0:
                entry['square_positive'] += amt
                if not entry['first_square_payment_date'] and payment_date:
                    entry['first_square_payment_date'] = payment_date

    # Post-process validations
    for entry in by_reserve.values():
        pos = entry['square_positive']
        ref = entry['square_refund']  # negative if refunds
        # Refund amounts recorded negative; abs(ref) should not exceed pos
        if abs(ref) > pos + 0.01 and pos > 0:  # allow 1 cent tolerance
            entry['refund_exceeds_original'] = True
        if entry['square_refund_count'] > 0 and pos == 0:
            entry['refund_without_original'] = True
        # Gap between paid_amount (system) and square (net of refunds)
        entry['refund_gap_vs_paid'] = entry['paid_amount'] - (pos + ref)

    # Prepare CSV
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = f'L:/limo/reports/square_refunds_cancelled_{ts}.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow([
            'Reserve','Charter Date','Client','Total Due','Paid Amount','Recorded Balance',
            'Square Positive','Square Refund','Square Net','Square Payment Count','Square Refund Count',
            'First Square Payment','First Square Refund','Refund>Original','Refund w/o Original','Refund Gap vs Paid','Square Txn IDs'
        ])
        for e in sorted(by_reserve.values(), key=lambda x: (x['charter_date'] or datetime.min)):
            net = e['square_positive'] + e['square_refund']
            w.writerow([
                e['reserve_number'],
                e['charter_date'].strftime('%Y-%m-%d') if e['charter_date'] else '',
                e['client_name'],
                f"{e['total_due']:.2f}",
                f"{e['paid_amount']:.2f}",
                f"{e['recorded_balance']:.2f}",
                f"{e['square_positive']:.2f}",
                f"{e['square_refund']:.2f}",
                f"{net:.2f}",
                e['square_payment_count'],
                e['square_refund_count'],
                e['first_square_payment_date'].strftime('%Y-%m-%d') if e['first_square_payment_date'] else '',
                e['first_square_refund_date'].strftime('%Y-%m-%d') if e['first_square_refund_date'] else '',
                'YES' if e['refund_exceeds_original'] else '',
                'YES' if e['refund_without_original'] else '',
                f"{e['refund_gap_vs_paid']:.2f}",
                ';'.join(e['transaction_ids'])
            ])

    # Console summary
    print('='*95)
    print('Square Refund Scan for Cancelled Charters')
    print('='*95)
    print(f'Export: {csv_path}')
    print()
    header = (f"{'Reserve':<8} {'Date':<10} {'Client':<20} {'Paid':>9} {'Bal':>9} "
              f"{'Sq+':>9} {'SqRef':>9} {'SqNet':>9} {'PmtCt':>6} {'RefCt':>6} {'Gap':>9} {'Flags':<12}")
    print(header)
    print('-'*95)
    anomalies = 0
    refund_rows = 0
    for e in sorted(by_reserve.values(), key=lambda x: (x['charter_date'] or datetime.min)):
        net = e['square_positive'] + e['square_refund']
        flags = []
        if e['refund_exceeds_original']:
            flags.append('EXCEEDS')
        if e['refund_without_original']:
            flags.append('NOORIG')
        if abs(e['refund_gap_vs_paid']) > 0.01:
            flags.append('GAP')
        if flags:
            anomalies += 1
        if e['square_refund_count'] > 0:
            refund_rows += 1
        print(f"{e['reserve_number']:<8} {e['charter_date'].strftime('%Y-%m-%d') if e['charter_date'] else '':<10} "
              f"{e['client_name'][:20]:<20} {e['paid_amount']:>9.2f} {e['recorded_balance']:>9.2f} "
              f"{e['square_positive']:>9.2f} {e['square_refund']:>9.2f} {net:>9.2f} {e['square_payment_count']:>6} {e['square_refund_count']:>6} "
              f"{e['refund_gap_vs_paid']:>9.2f} {';'.join(flags):<12}")
    print('-'*95)
    print(f"Total cancelled w/ balance: {len(by_reserve)}")
    print(f"Charters with Square refunds: {refund_rows}")
    print(f"Anomaly flagged rows:        {anomalies}")
    print()
    print('Flag meanings:')
    print('  EXCEEDS  - Absolute refund total greater than original Square positive total (should not happen).')
    print('  NOORIG   - Refund detected but no original positive Square payment recorded.')
    print('  GAP      - Paid amount differs from (Square positive + Square refund) beyond tolerance; investigate other payment sources.')

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
