"""Find potential refunds for cancelled charters with outstanding balances or payment anomalies.

Detection logic:
1. Identify cancelled charters with balance > 0.01 (these appear still owing).
2. For each cancelled charter gather all payments by reserve_number.
3. Classify payments:
   - Positive amounts: original payments/deposits.
   - Negative amounts: potential refunds / reversals.
   - Keyword matches in notes/status/payment_method: 'refund', 'reversal', 'chargeback'.
4. Also scan global payment rows that look like refunds (negative or refund keywords) whose reserve_number is NULL but whose notes contain the cancelled charter reserve number.
5. Produce CSV + console report summarizing: reserve_number, charter_date, client_name, total_due, paid_amount, recorded_balance, sum_positive, sum_negative, net_payments (positives + negatives), refund_candidates (count), refund_gap (expected refund vs detected), earliest_refund_date.

Assumptions:
- Refunds are stored as negative amounts OR annotated with keywords.
- Use reserve_number business key.

Output:
- Console summary grouped by status: (A) Cancelled with potential refund found, (B) Cancelled with NO refund indicators, (C) Refund indicators but charter balance not updated.
- CSV stored under reports/find_cancelled_charter_refunds_YYYYMMDD_HHMMSS.csv
"""
import psycopg2
import csv
from datetime import datetime
from collections import defaultdict

KEYWORDS = ["refund", "reversal", "chargeback", "return", "write-off", "write off"]

def get_conn():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

def fetch_cancelled_charters(cur):
    cur.execute("""
        SELECT c.reserve_number, c.charter_date, cl.client_name, c.total_amount_due,
               c.paid_amount, c.balance, c.notes
        FROM charters c
        LEFT JOIN clients cl ON cl.client_id = c.client_id
        WHERE c.cancelled = TRUE AND c.balance > 0.01
        ORDER BY c.charter_date ASC NULLS FIRST
    """)
    rows = cur.fetchall()
    return rows

def fetch_payments_for_reserves(cur, reserves):
    # Fetch payments tied directly to these reserve numbers
    cur.execute("""
        SELECT reserve_number, payment_id, amount, payment_date, payment_method, status, notes
        FROM payments
        WHERE reserve_number = ANY(%s)
        ORDER BY payment_date ASC NULLS LAST, payment_id ASC
    """, (reserves,))
    return cur.fetchall()

def fetch_global_refunds(cur):
    # Refund-looking payments with NULL reserve_number (might reference in notes)
    cur.execute("""
        SELECT payment_id, amount, payment_date, payment_method, status, notes
        FROM payments
        WHERE (reserve_number IS NULL OR reserve_number = '') AND (
              amount < 0 OR
              LOWER(COALESCE(status,'')) LIKE '%refund%' OR
              LOWER(COALESCE(notes,'')) LIKE '%refund%' OR
              LOWER(COALESCE(payment_method,'')) LIKE '%refund%' OR
              LOWER(COALESCE(notes,'')) LIKE '%reversal%' OR
              LOWER(COALESCE(status,'')) LIKE '%reversal%'
        )
    """)
    return cur.fetchall()

def classify_payment(row):
    reserve_number, payment_id, amount, payment_date, payment_method, status, notes = row
    amt_type = 'positive' if (amount or 0) > 0 else ('negative' if (amount or 0) < 0 else 'zero')
    text_blob = ' '.join([str(x or '') for x in (payment_method, status, notes)]).lower()
    keyword_hit = any(kw in text_blob for kw in KEYWORDS)
    is_refund_candidate = amt_type == 'negative' or keyword_hit
    return {
        'reserve_number': reserve_number,
        'payment_id': payment_id,
        'amount': amount or 0,
        'payment_date': payment_date,
        'payment_method': payment_method,
        'status': status,
        'notes': notes,
        'amt_type': amt_type,
        'keyword_hit': keyword_hit,
        'refund_candidate': is_refund_candidate,
    }


def main():
    conn = get_conn()
    cur = conn.cursor()

    cancelled = fetch_cancelled_charters(cur)
    if not cancelled:
        print("No cancelled charters with outstanding balances found.")
        return

    reserves = [r[0] for r in cancelled]

    payments = fetch_payments_for_reserves(cur, reserves)
    payments_classified = [classify_payment(p) for p in payments]

    global_refunds = fetch_global_refunds(cur)

    # Map global refunds potentially referencing reserve_number in notes
    global_ref_map = defaultdict(list)
    for pid, amount, payment_date, payment_method, status, notes in global_refunds:
        blob = (notes or '')
        for reserve in reserves:
            if reserve and reserve in blob:
                global_ref_map[reserve].append({
                    'payment_id': pid,
                    'amount': amount,
                    'payment_date': payment_date,
                    'payment_method': payment_method,
                    'status': status,
                    'notes': notes,
                    'source': 'global_refund_note_match'
                })

    # Aggregate
    charter_summary = []
    payment_index = defaultdict(list)
    for p in payments_classified:
        payment_index[p['reserve_number']].append(p)

    for reserve_number, charter_date, client_name, total_due, paid_amount, balance, notes in cancelled:
        pos_total = sum(p['amount'] for p in payment_index[reserve_number] if p['amt_type'] == 'positive')
        neg_total = sum(p['amount'] for p in payment_index[reserve_number] if p['amt_type'] == 'negative')
        refund_candidates = [p for p in payment_index[reserve_number] if p['refund_candidate']]
        global_candidates = global_ref_map.get(reserve_number, [])
        all_candidates_count = len(refund_candidates) + len(global_candidates)
        earliest_refund_date = None
        dates = [p['payment_date'] for p in refund_candidates if p['payment_date']] + [g['payment_date'] for g in global_candidates if g['payment_date']]
        if dates:
            earliest_refund_date = min(dates)

        net_payments = pos_total + neg_total
        expected_refund_gap = paid_amount - net_payments  # If gap > 0 maybe missing refund recording

        charter_summary.append({
            'reserve_number': reserve_number,
            'charter_date': charter_date,
            'client_name': client_name or 'Unknown',
            'total_due': float(total_due or 0),
            'paid_amount': float(paid_amount or 0),
            'recorded_balance': float(balance or 0),
            'sum_positive': float(pos_total),
            'sum_negative': float(neg_total),
            'net_payments': float(net_payments),
            'refund_candidate_count': all_candidates_count,
            'earliest_refund_date': earliest_refund_date,
            'expected_refund_gap': float(expected_refund_gap),
            'notes': notes or '',
            'global_note_matches': len(global_candidates),
        })

    # CSV export
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = f'L:/limo/reports/find_cancelled_charter_refunds_{ts}.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow([
            'Reserve', 'Charter Date', 'Client', 'Total Due', 'Paid Amount', 'Recorded Balance',
            'Sum Positive Payments', 'Sum Negative Payments', 'Net Payments', 'Refund Candidate Count',
            'Global Note Matches', 'Earliest Refund Date', 'Expected Refund Gap', 'Notes'
        ])
        for row in charter_summary:
            w.writerow([
                row['reserve_number'],
                row['charter_date'].strftime('%Y-%m-%d') if row['charter_date'] else '',
                row['client_name'],
                f"{row['total_due']:.2f}",
                f"{row['paid_amount']:.2f}",
                f"{row['recorded_balance']:.2f}",
                f"{row['sum_positive']:.2f}",
                f"{row['sum_negative']:.2f}",
                f"{row['net_payments']:.2f}",
                row['refund_candidate_count'],
                row['global_note_matches'],
                row['earliest_refund_date'].strftime('%Y-%m-%d') if row['earliest_refund_date'] else '',
                f"{row['expected_refund_gap']:.2f}",
                (row['notes'][:120] + '...') if len(row['notes']) > 120 else row['notes']
            ])

    # Console summary
    print("="*90)
    print("Cancelled Charter Refund Analysis")
    print("="*90)
    print(f"Export: {csv_path}")
    print()
    headers = (
        f"{'Reserve':<8} {'Date':<10} {'Client':<22} {'Due':>9} {'Paid':>9} {'Bal':>9} "
        f"{'Pos':>9} {'Neg':>9} {'Net':>9} {'Cand':>4} {'Gap':>9} {'FirstRefund':<10}"
    )
    print(headers)
    print('-'*90)

    with_refund = 0
    no_refund = 0
    gap_refund = 0

    for row in charter_summary:
        gap = row['expected_refund_gap']
        cand = row['refund_candidate_count']
        if cand > 0:
            with_refund += 1
        else:
            no_refund += 1
        if gap > 0.01 and cand == 0:
            gap_refund += 1
        print(f"{row['reserve_number']:<8} {row['charter_date'].strftime('%Y-%m-%d') if row['charter_date'] else '':<10} "
              f"{row['client_name'][:22]:<22} {row['total_due']:>9.2f} {row['paid_amount']:>9.2f} {row['recorded_balance']:>9.2f} "
              f"{row['sum_positive']:>9.2f} {row['sum_negative']:>9.2f} {row['net_payments']:>9.2f} {cand:>4} {gap:>9.2f} "
              f"{row['earliest_refund_date'].strftime('%Y-%m-%d') if row['earliest_refund_date'] else '':<10}")

    print('-'*90)
    print(f"Total cancelled with outstanding balance: {len(charter_summary)}")
    print(f"Charters with refund indicators:         {with_refund}")
    print(f"Charters without refund indicators:      {no_refund}")
    print(f"Potential missing refund recordings:     {gap_refund}")
    print()
    print("Interpretation:")
    print("  - Sum Positive should match paid_amount unless negative (refund) entries exist.")
    print("  - Expected Refund Gap = paid_amount - (positive + negative). If >0 and no candidates, refund may be missing.")
    print("  - Refund Candidate Count includes negative amounts or keyword matches, plus global note matches.")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
