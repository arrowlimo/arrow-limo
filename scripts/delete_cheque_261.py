#!/usr/bin/env python
"""Delete CHQ 261 from cheque_register with backup."""
import psycopg2, os, json
from datetime import datetime

DB_HOST = os.environ.get('DB_HOST','localhost')
DB_NAME = os.environ.get('DB_NAME','almsdata')
DB_USER = os.environ.get('DB_USER','postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD','***REMOVED***')

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    # Backup first
    cur.execute("""
        SELECT id, cheque_number, cheque_date, amount, payee, status, 
               account_number, memo, banking_transaction_id, created_at
        FROM cheque_register
        WHERE cheque_number = '261'
    """)
    rows = cur.fetchall()
    
    backup_data = []
    for r in rows:
        backup_data.append({
            "id": r[0],
            "cheque_number": r[1],
            "cheque_date": str(r[2]),
            "amount": str(r[3]),
            "payee": r[4],
            "status": r[5],
            "account_number": r[6],
            "memo": r[7],
            "banking_transaction_id": r[8],
            "created_at": str(r[9])
        })
    
    backup_file = f"cheque_261_deletion_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(backup_file, 'w') as f:
        json.dump(backup_data, f, indent=2)
    print(f"✅ Backup created: {backup_file}")
    for item in backup_data:
        print(f"   {item}")
    
    # Delete
    cur.execute("DELETE FROM cheque_register WHERE cheque_number = '261'")
    deleted = cur.rowcount
    conn.commit()
    print(f"\n✅ Deleted {deleted} cheque(s)")
    
    # Verify
    cur.execute("SELECT COUNT(*) FROM cheque_register WHERE cheque_number = '261'")
    remaining = cur.fetchone()[0]
    print(f"✅ Verification: {remaining} cheques with number 261 remain (should be 0)")
    
    cur.close(); conn.close()

if __name__ == '__main__':
    print("=" * 100)
    print("DELETE CHQ 261 FROM CHEQUE_REGISTER")
    print("=" * 100)
    main()
