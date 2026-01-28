import argparse
import psycopg2
from datetime import datetime

# Link specified banking transaction IDs to a given reserve_number in banking_payment_links.
# Assumes table banking_payment_links with columns:
#   id SERIAL PK
#   transaction_id INTEGER
#   reserve_number VARCHAR
#   link_type VARCHAR
#   notes TEXT
#   created_at TIMESTAMP

DEFAULT_DEPOSIT_TXN = 32977  # $700 credit
DEFAULT_REFUND_TXN = 32890   # $520 debit (choose first occurrence)
POSSIBLE_DUPLICATE_REFUND = 32892  # second $520 debit (not linked by default)

def get_conn():
    return psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')

def ensure_table(cur):
    cur.execute("""
        SELECT 1 FROM information_schema.tables WHERE table_name='banking_payment_links'
    """)
    if not cur.fetchone():
        # Create minimal table if missing (defensive)
        cur.execute("""
            CREATE TABLE banking_payment_links (
                id SERIAL PRIMARY KEY,
                transaction_id INTEGER NOT NULL,
                reserve_number VARCHAR(20) NOT NULL,
                link_type VARCHAR(50) NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

def link_txn(cur, reserve_number, txn_id, link_type, notes, dry_run):
    cur.execute("""SELECT id FROM banking_payment_links WHERE transaction_id=%s AND reserve_number=%s""",
                (txn_id, reserve_number))
    if cur.fetchone():
        print(f"Already linked txn {txn_id} -> {reserve_number}; skipping")
        return
    if dry_run:
        print(f"DRY-RUN: Would link txn {txn_id} -> {reserve_number} ({link_type})")
        return
    cur.execute("""
        INSERT INTO banking_payment_links (transaction_id, reserve_number, link_type, notes, created_at)
        VALUES (%s, %s, %s, %s, NOW()) RETURNING id
    """, (txn_id, reserve_number, link_type, notes))
    new_id = cur.fetchone()[0]
    print(f"Linked txn {txn_id} -> {reserve_number} id={new_id}")

def main():
    ap = argparse.ArgumentParser(description='Link Kelly Debbie banking transactions to a charter reserve_number.')
    ap.add_argument('--reserve', default='016284', help='Target reserve_number to link transactions to')
    ap.add_argument('--include-duplicate-refund', action='store_true', help='Also link second $520 refund (possible duplicate)')
    ap.add_argument('--write', action='store_true', help='Apply changes (otherwise dry-run)')
    args = ap.parse_args()

    conn = get_conn(); conn.autocommit = False
    try:
        cur = conn.cursor()
        ensure_table(cur)
        print(f"Target reserve_number: {args.reserve}")
        link_txn(cur, args.reserve, DEFAULT_DEPOSIT_TXN, 'DEPOSIT', 'Initial $700 e-transfer from Kelly Debbie', not args.write)
        link_txn(cur, args.reserve, DEFAULT_REFUND_TXN, 'REFUND', 'Refund $520 e-transfer to Debbie Kelly', not args.write)
        if args.include_duplicate_refund:
            link_txn(cur, args.reserve, POSSIBLE_DUPLICATE_REFUND, 'REFUND_DUPLICATE', 'Second $520 refund (possible duplicate)', not args.write)
        if args.write:
            conn.commit(); print('Commit complete.')
        else:
            conn.rollback(); print('Rolled back (dry-run).')
    except Exception as e:
        conn.rollback(); print('ERROR:', e); raise
    finally:
        conn.close()

if __name__ == '__main__':
    main()
