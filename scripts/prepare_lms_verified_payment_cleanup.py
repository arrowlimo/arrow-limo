"""
Prepare cleanup for non-ETR overpaid charters (014140, 013914) while preserving LMS-verified payments.
Retention rules (dry-run):
 1. ALWAYS keep payments having a non-null payment_key (assumed LMS import).
 2. ALSO keep the earliest payment (potential original deposit) even if payment_key is NULL.
 3. Mark all other same-amount repeat payments as candidates for unlink.
Interactive apply mode requires explicit confirmation listing IDs to unlink.
"""
import psycopg2, os, argparse
from datetime import datetime

TARGET_RESERVES = ['014140','013914']

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REMOVED***')
    )

def fetch_payments(cur, reserve):
    cur.execute("""
        SELECT payment_id, amount, payment_date, payment_key, charter_id
        FROM payments
        WHERE reserve_number=%s
        ORDER BY payment_date, payment_id
    """, (reserve,))
    return cur.fetchall()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='Actually unlink candidate duplicate payments')
    ap.add_argument('--unlink-ids', type=str, help='Comma-separated payment_ids to unlink (required with --apply)')
    args = ap.parse_args()

    conn = get_conn(); cur = conn.cursor()
    print('='*90)
    print('LMS VERIFIED PAYMENT CLEANUP (NON-ETR OVERPAYS)')
    print('='*90)
    print(f'Mode: {"APPLY" if args.apply else "DRY-RUN"}')
    print('Retention: keep keyed + earliest; propose unlink others')
    print()

    all_candidates = []
    for res in TARGET_RESERVES:
        print('-'*70)
        print(f'Charter {res}')
        cur.execute("SELECT charter_id, charter_date, total_amount_due, paid_amount FROM charters WHERE reserve_number=%s", (res,))
        ch = cur.fetchone()
        if not ch:
            print('  Charter not found; skipping')
            continue
        charter_id, charter_date, total_due, paid_field = ch
        payments = fetch_payments(cur, res)
        actual_sum = sum(p[1] for p in payments)
        print(f"  Total Due: {total_due:.2f} | paid_field: {paid_field:.2f} | actual_sum: {actual_sum:.2f} | count: {len(payments)}")
        # Identify keyed payments
        keyed = [p for p in payments if p[3]]
        earliest = payments[0] if payments else None
        keep_ids = {p[0] for p in keyed}
        if earliest:
            keep_ids.add(earliest[0])
        print(f"  Keyed payments kept: {[p[0] for p in keyed]} (keys: {[p[3] for p in keyed]})")
        if earliest:
            print(f"  Earliest payment kept: {earliest[0]} on {earliest[2]} amount {earliest[1]:.2f}")
        candidates = [p for p in payments if p[0] not in keep_ids]
        # Group by amount for clarity
        amt_map = {}
        for p in candidates:
            amt_map.setdefault(p[1], []).append(p)
        print('  Candidate duplicates:')
        if candidates:
            for amt, plist in amt_map.items():
                ids = [p[0] for p in plist]
                dates = [p[2] for p in plist]
                print(f"    Amount {amt:.2f} -> IDs {ids} dates {dates}")
        else:
            print('    (none)')
        all_candidates.extend(candidates)

    if not args.apply:
        print('\nDRY-RUN COMPLETE')
        if all_candidates:
            print(f"Total candidate duplicate payments: {len(all_candidates)}")
            print('To apply: re-run with --apply --unlink-ids <comma-separated-payment-ids> (ONLY those you confirm not in LMS).')
        else:
            print('No candidates found to unlink.')
        cur.close(); conn.close(); return

    # APPLY MODE
    if args.apply and not args.unlink_ids:
        print('ERROR: --unlink-ids required with --apply'); cur.close(); conn.close(); return

    unlink_ids = [int(x.strip()) for x in args.unlink_ids.split(',') if x.strip()]
    candidate_ids = {p[0] for p in all_candidates}
    unknown = [pid for pid in unlink_ids if pid not in candidate_ids]
    if unknown:
        print(f"WARNING: Some provided IDs are not in candidate list: {unknown}")
    # Backup
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f"payments_backup_lms_cleanup_{ts}"
    cur.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM payments WHERE payment_id IN ({','.join(map(str, unlink_ids))})")
    cur.execute(f"UPDATE payments SET reserve_number=NULL, charter_id=NULL WHERE payment_id IN ({','.join(map(str, unlink_ids))})")
    affected = cur.rowcount
    # Recalculate affected charters
    for res in TARGET_RESERVES:
        cur.execute("""
            WITH payment_sum AS (
                SELECT reserve_number, SUM(amount) AS total_paid FROM payments WHERE reserve_number=%s GROUP BY reserve_number
            )
            UPDATE charters c SET paid_amount=ps.total_paid, balance=c.total_amount_due-ps.total_paid FROM payment_sum ps WHERE c.reserve_number=ps.reserve_number
        """, (res,))
    conn.commit()
    print(f"\nAPPLY COMPLETE: Unlinked {affected} payments. Backup table: {backup_table}")
    cur.close(); conn.close()

if __name__ == '__main__':
    main()
