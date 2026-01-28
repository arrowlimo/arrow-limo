#!/usr/bin/env python
"""
Assign account_number = 1615 to cheques 215 & 216 in cheque_register.
These cheques are already correctly linked in banking_transactions to account 1615,
but the cheque_register has NULL account_number.
"""

import psycopg2
import os
import json
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def backup_cheques():
    """Backup affected cheques before update."""
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT id, cheque_number, account_number, cheque_date, payee, amount, status
            FROM cheque_register
            WHERE cheque_number IN ('215', '216')
            ORDER BY cheque_number
        """)
        rows = cur.fetchall()
        
        backup_data = []
        for row in rows:
            backup_data.append({
                "id": row[0],
                "cheque_number": row[1],
                "account_number": row[2],
                "cheque_date": str(row[3]),
                "payee": row[4],
                "amount": str(row[5]),
                "status": row[6]
            })
        
        backup_file = f"cheque_215_216_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2)
        
        print(f"✅ Backup created: {backup_file}")
        print(f"   {len(backup_data)} cheques backed up")
        
        for item in backup_data:
            print(f"   Cheque #{item['cheque_number']} | {item['cheque_date']} | {item['payee']} | ${item['amount']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def assign_account():
    """Assign account_number = 1615 to cheques 215 & 216."""
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE cheque_register
            SET account_number = '1615'
            WHERE cheque_number IN ('215', '216')
            AND account_number IS NULL
        """)
        
        updated = cur.rowcount
        conn.commit()
        
        print(f"\n✅ Updated {updated} cheques to account_number = 1615")
        
        # Verify
        cur.execute("""
            SELECT id, cheque_number, account_number, cheque_date, payee, amount, status
            FROM cheque_register
            WHERE cheque_number IN ('215', '216')
            ORDER BY cheque_number
        """)
        rows = cur.fetchall()
        
        print(f"\n📋 Verification (after update):")
        for row in rows:
            print(f"   Cheque #{row[1]} | Account {row[2]} | {row[3]} | {row[4]} | ${row[5]} | Status: {row[6]}")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Update failed: {e}")
        return False
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    print("=" * 100)
    print("ASSIGN ACCOUNT_NUMBER = 1615 TO CHEQUES 215 & 216")
    print("=" * 100)
    
    if backup_cheques():
        assign_account()
    else:
        print("Aborting due to backup failure.")
