"""
Bulk fix overpaid charters by unlinking suspect ETR: payments.
Logic per charter:
 - Identify payments with payment_key starting 'ETR:' AND charter_id IS NULL
 - Compute date difference between payment_date and banking transaction_date; if > 90 days mark suspect
 - Also mark suspect if banking description contains expense patterns (PURCHASE, WITHDRAWAL, SERVICE CHARGE, PREAUTHORIZED DEBIT, NSF, FEE, AUTO)
 - Keep non-ETR payments and any ETR payments not suspect (dry-run review first)
Dry-run by default. Use --apply to commit.
"""
import psycopg2, os, argparse, re
from datetime import datetime

EXPENSE_PATTERNS = [
    'PURCHASE','WITHDRAWAL','SERVICE CHARGE','PREAUTHORIZED DEBIT','NSF','FEE','AUTO','PETRO','SOBEYS','SQUARE','HEFFNER'
]

TARGET_RESERVES = [
    '014140','018750','018886','013914','019194','017448','015980','018973','018528','017832'
]

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REMOVED***')
    )

def is_expense(desc: str) -> bool:
    if not desc: return False
    d = desc.upper()
    return any(p in d for p in EXPENSE_PATTERNS)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='Apply changes (unlink suspect payments)')
    args = ap.parse_args()
    conn = get_conn(); cur = conn.cursor()

    print('='*80)
    print('BULK FIX OVERPAID CHARTERS (ETR payment unlink)')
    print('='*80)
    print(f'Target reserves: {", ".join(TARGET_RESERVES)}')
    print('Mode: ' + ('APPLY' if args.apply else 'DRY-RUN'))
    print()

    total_unlink = 0
    for res in TARGET_RESERVES:
        print('-'*80)
        print(f'Charter {res}')
        # Charter info
        cur.execute("""
            SELECT charter_id, total_amount_due, paid_amount FROM charters WHERE reserve_number=%s
        """, (res,))
        charter = cur.fetchone()
        if not charter:
            print('  Charter not found, skipping')
            continue
        charter_id, total_due, charter_paid = charter
        # Payments with banking info
        cur.execute("""
            SELECT p.payment_id, p.amount, p.payment_date, p.payment_key, p.charter_id,
                   bt.transaction_date, bt.description, bt.debit_amount, bt.credit_amount
            FROM payments p
            LEFT JOIN banking_transactions bt ON p.payment_key = 'ETR:' || bt.transaction_id
            WHERE p.reserve_number=%s
            ORDER BY p.payment_date, p.payment_id
        """, (res,))
        payments = cur.fetchall()
        actual_sum = sum(p[1] for p in payments)
        print(f"  Total Due: {total_due} | Charter Paid: {charter_paid} | Actual Sum: {actual_sum}")
        suspect = []
        keep = []
        for p in payments:
            pid, amount, pdate, pkey, pcharter_id, bdate, bdesc, debit, credit = p
            is_etr = pkey and pkey.startswith('ETR:')
            date_diff = (abs((pdate - bdate).days) if (is_etr and pdate and bdate) else 0)
            expense_flag = is_etr and (date_diff > 90 or is_expense(bdesc) or (debit and debit > 0 and (credit is None or credit == 0)))
            if is_etr and expense_flag and pcharter_id is None:
                suspect.append((pid, amount, pkey, date_diff, bdesc))
            else:
                keep.append((pid, amount, pkey))
        print(f"  Payments: {len(payments)} | Keep: {len(keep)} | Suspect unlink: {len(suspect)}")
        overpay = actual_sum - total_due
        print(f"  Overpay: {overpay:.2f}")
        if suspect:
            print('  Suspect payments:')
            for s in suspect:
                print(f"    ID {s[0]} ${s[1]:.2f} key {s[2]} diff {s[3]}d desc={s[4][:80] if s[4] else ''}")
        if args.apply and suspect:
            ids = [str(s[0]) for s in suspect]
            backup = f"payments_backup_{res}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            cur.execute(f"CREATE TABLE {backup} AS SELECT * FROM payments WHERE payment_id IN ({','.join(ids)})")
            cur.execute(f"UPDATE payments SET reserve_number=NULL, charter_id=NULL WHERE payment_id IN ({','.join(ids)})")
            total_unlink += cur.rowcount
            # Recalculate charter
            cur.execute("""
                WITH payment_sum AS (
                    SELECT reserve_number, SUM(amount) AS total_paid FROM payments WHERE reserve_number=%s GROUP BY reserve_number
                )
                UPDATE charters c SET paid_amount=ps.total_paid, balance=c.total_amount_due-ps.total_paid FROM payment_sum ps WHERE c.reserve_number=ps.reserve_number
            """, (res,))
            print(f"  ✓ Unlinked {len(ids)} payments; backup table {backup}")
        else:
            print('  (Dry-run: no changes applied)')
    if args.apply:
        conn.commit(); print(f"\nTOTAL unlinked payments: {total_unlink}")
    else:
        conn.rollback(); print("\nDRY-RUN complete; rerun with --apply to commit.")
    cur.close(); conn.close()

if __name__=='__main__':
    main()
