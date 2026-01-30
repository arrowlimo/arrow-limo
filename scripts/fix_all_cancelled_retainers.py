import argparse
import psycopg2
from decimal import Decimal
from datetime import datetime

# Process multiple cancelled charters with non-refundable retainers held for future use.
# Charters: 014215, 016530, 017101
# For each:
#   1. Convert retainer amount (from LMS deposit or paid amount) to credit ledger
#   2. Delete all existing payment rows
#   3. Zero charter paid_amount and balance
#   4. Backup payments before deletion

CHARTERS = [
    {'reserve_number': '014215', 'retainer': Decimal('500.00'), 'client': 'Katerynych, Katerina'},
    {'reserve_number': '016530', 'retainer': Decimal('468.00'), 'client': 'Kumar Pranesh'},
    {'reserve_number': '017101', 'retainer': Decimal('500.00'), 'client': 'Leyenhorst Stephanie'},
    {'reserve_number': '015911', 'retainer': Decimal('500.00'), 'client': 'Smawley Meghann'},
    {'reserve_number': '017860', 'retainer': Decimal('75.00'), 'client': 'Dietrich, Konrad'},
    {'reserve_number': '016922', 'retainer': Decimal('500.00'), 'client': 'Chinook Enviromental Ltd.'},
    {'reserve_number': '016213', 'retainer': Decimal('500.00'), 'client': 'Garrett Scott'},
    {'reserve_number': '018481', 'retainer': Decimal('500.00'), 'client': 'Ellingson, Mary'},
    {'reserve_number': '014411', 'retainer': Decimal('205.00'), 'client': 'Loucks, Amber'},
]

def get_conn():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def fetch_charter(cur, reserve_number):
    cur.execute("""
        SELECT charter_id, total_amount_due, paid_amount, balance, cancelled
        FROM charters WHERE reserve_number = %s
    """, (reserve_number,))
    row = cur.fetchone()
    if not row:
        return None
    return {
        'charter_id': row[0],
        'total_amount_due': Decimal(str(row[1])) if row[1] is not None else Decimal('0'),
        'paid_amount': Decimal(str(row[2])) if row[2] is not None else Decimal('0'),
        'balance': Decimal(str(row[3])) if row[3] is not None else Decimal('0'),
        'cancelled': bool(row[4])
    }

def fetch_payments(cur, reserve_number):
    cur.execute("""
        SELECT payment_id, amount, payment_date
        FROM payments WHERE reserve_number = %s ORDER BY payment_date, payment_id
    """, (reserve_number,))
    rows = cur.fetchall()
    return [{'payment_id': r[0], 'amount': Decimal(str(r[1])) if r[1] else Decimal('0'), 'payment_date': r[2]} for r in rows]

def backup_payments(cur, reserve_number, payment_ids):
    if not payment_ids:
        return None
    backup_table = f"payments_backup_{reserve_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    id_list = ','.join(str(i) for i in payment_ids)
    cur.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM payments WHERE payment_id IN ({id_list})")
    return backup_table

def create_credit(cur, reserve_number, charter_id, amount):
    cur.execute("""
        INSERT INTO charter_credit_ledger (
            reserve_number, charter_id, credit_amount, credit_remaining, credit_reason, notes, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, NOW()) RETURNING id
    """, (reserve_number, charter_id, amount, amount, 'CANCELLED_DEPOSIT',
          f'Cancelled charter non-refundable retainer held for future use'))
    return cur.fetchone()[0]

def delete_payments(cur, payment_ids):
    if not payment_ids:
        return 0
    cur.execute("DELETE FROM payments WHERE payment_id = ANY(%s)", (payment_ids,))
    return cur.rowcount

def update_charter(cur, charter_id):
    cur.execute("""
        UPDATE charters
        SET paid_amount = 0.00, balance = 0.00, cancelled = TRUE, updated_at = NOW()
        WHERE charter_id = %s
    """, (charter_id,))

def process_charter(cur, charter_def, dry_run):
    reserve_number = charter_def['reserve_number']
    retainer = charter_def['retainer']
    client = charter_def['client']
    
    print(f"\n--- Processing {reserve_number} ({client}) ---")
    charter = fetch_charter(cur, reserve_number)
    if not charter:
        print(f"Charter {reserve_number} not found; skipping.")
        return
    
    payments = fetch_payments(cur, reserve_number)
    total_paid = sum(p['amount'] for p in payments)
    print(f"Payments: {len(payments)}  Total paid: {total_paid}  Retainer target: {retainer}")
    print(f"Charter cancelled: {charter['cancelled']}")
    
    if not payments:
        print("No payments to process.")
        return
    
    payment_ids = [p['payment_id'] for p in payments]
    
    if dry_run:
        print(f"DRY-RUN: Would create credit {retainer}, delete {len(payment_ids)} payments, zero charter.")
        return
    
    # Backup
    backup_table = backup_payments(cur, reserve_number, payment_ids)
    print(f"Backup: {backup_table}")
    
    # Create credit
    credit_id = create_credit(cur, reserve_number, charter['charter_id'], retainer)
    print(f"Credit ledger entry created: id={credit_id}, amount={retainer}")
    
    # Delete payments
    deleted = delete_payments(cur, payment_ids)
    print(f"Deleted {deleted} payments.")
    
    # Zero charter
    update_charter(cur, charter['charter_id'])
    print(f"Charter financials zeroed (paid=0, balance=0).")

def main():
    parser = argparse.ArgumentParser(description='Process all cancelled charters with non-refundable retainers.')
    parser.add_argument('--write', action='store_true', help='Apply changes; otherwise dry-run.')
    args = parser.parse_args()
    
    conn = get_conn()
    conn.autocommit = False
    try:
        cur = conn.cursor()
        for charter_def in CHARTERS:
            process_charter(cur, charter_def, dry_run=not args.write)
        
        if args.write:
            conn.commit()
            print("\n=== All changes committed ===")
        else:
            conn.rollback()
            print("\n=== DRY-RUN complete (no changes applied) ===")
    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    main()
