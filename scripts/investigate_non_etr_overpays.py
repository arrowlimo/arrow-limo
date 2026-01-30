"""
Investigate non-ETR overpaid charters: 014140 and 013914.
Goal: Identify suspect duplicate payment linkages not using ETR pattern.
Criteria considered:
 - payment_key reused across many different reserve_numbers
 - payment_date far (>180 days) from charter_date
 - charter_id is NULL (weak linkage) while reserve_number matches
 - amount equals charter total (possible duplicate full payment)
Outputs detailed report and a candidate list for unlink (dry-run only).
"""
import psycopg2, os
from collections import defaultdict

TARGET_RESERVES = ['014140','013914']

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REDACTED***')
    )

def main():
    conn = get_conn(); cur = conn.cursor()
    print('='*80)
    print('NON-ETR OVERPAY INVESTIGATION')
    print('='*80)
    # Preload payment_key usage counts
    cur.execute("""
        SELECT payment_key, COUNT(*) cnt, SUM(amount) total, ARRAY_AGG(DISTINCT reserve_number) as reserves
        FROM payments
        GROUP BY payment_key
        HAVING COUNT(*) > 1
    """)
    key_stats = {r[0]: {'count': r[1], 'total': r[2], 'reserves': r[3]} for r in cur.fetchall() if r[0]}

    for res in TARGET_RESERVES:
        print('-'*80)
        print(f'Charter {res}')
        cur.execute("""SELECT charter_id, charter_date, total_amount_due, paid_amount FROM charters WHERE reserve_number=%s""", (res,))
        charter = cur.fetchone()
        if not charter:
            print('  Charter not found'); continue
        charter_id, charter_date, total_due, charter_paid = charter
        print(f"  Date: {charter_date} | Total Due: {total_due} | Charter Paid Field: {charter_paid}")
        # Payments
        cur.execute("""
            SELECT payment_id, amount, payment_date, payment_key, charter_id
            FROM payments WHERE reserve_number=%s ORDER BY payment_date, payment_id
        """, (res,))
        payments = cur.fetchall()
        actual_sum = sum(p[1] for p in payments)
        print(f"  Linked payments: {len(payments)} | Actual SUM: {actual_sum} | Overpay: {actual_sum - total_due:.2f}")
        candidates = []
        for pid, amt, pdate, pkey, pcharter_id in payments:
            if pkey and pkey.startswith('ETR:'): # skip already handled pattern
                continue
            key_info = key_stats.get(pkey)
            key_reuse = key_info['count'] if key_info else 1
            far_date = abs((pdate - charter_date).days) if (pdate and charter_date) else 0
            full_dup = abs(amt - total_due) < 0.01 and key_reuse > 1
            weak_link = pcharter_id is None
            score = 0
            if key_reuse > 5: score += 2
            if far_date > 180: score += 1
            if weak_link: score += 1
            if full_dup: score += 2
            if score >= 3:
                candidates.append((pid, amt, pdate, pkey, key_reuse, far_date, weak_link, full_dup, score))
        print('  Payments:')
        # Aggregate pattern: repeated identical amounts equal to total_due on sequential dates
        seq_flag = False
        if len(payments) > 3:
            # If >=4 payments all equal to total_due amount (or fixed 500 in these cases)
            repeated_fulls = sum(1 for p in payments if abs(p[1] - payments[0][1]) < 0.01)
            if repeated_fulls == len(payments):
                seq_flag = True
                print('  Pattern: sequential repeated identical full-amount payments detected (likely duplication).')
        for pid, amt, pdate, pkey, pcharter_id in payments:
            reuse = key_stats.get(pkey, {}).get('count',1)
            mark = 'DUP?' if seq_flag else ''
            print(f"    {pid}: ${amt:.2f} date {pdate} key {pkey} reuse={reuse} {mark}")
        if candidates:
            print('  Suspect candidates (score>=3):')
            for c in candidates:
                print(f"    ID {c[0]} amt {c[1]:.2f} date {c[2]} key {c[3]} reuse {c[4]} far {c[5]}d weak={c[6]} fullDup={c[7]} score={c[8]}")
        else:
            print('  No high-score candidates found; requires manual review or broader logic.')
    cur.close(); conn.close()
    print('\nDRY-RUN investigation complete.')

if __name__=='__main__':
    main()
