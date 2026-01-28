#!/usr/bin/env python3
"""Delete duplicate Waste Connections $774 payment records and false credits.

Root cause: August 5, 2025 import created duplicate payment records with NULL keys.
These payments don't exist in LMS and represent false entries.

This script:
  1. Identifies NULL-key payments created 2025-08-05 on Waste Connections reserves
  2. Verifies they're duplicates by checking LMS
  3. Deletes the duplicate payment records
  4. Deletes the corresponding false credit ledger entries

Usage:
  python scripts/delete_waste_774_duplicate_records.py              # Dry-run
  python scripts/delete_waste_774_duplicate_records.py --write      # Execute
"""

import os
import psycopg2
import pyodbc
from datetime import datetime
from argparse import ArgumentParser
from dotenv import load_dotenv

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
LMS_PATH = r"L:\limo\backups\lms.mdb"


def pg_conn():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def lms_conn():
    return pyodbc.connect(f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};")


def main():
    parser = ArgumentParser(description='Delete duplicate Waste Connections $774 payment records')
    parser.add_argument('--write', action='store_true', help='Execute deletions (default is dry-run)')
    args = parser.parse_args()
    
    pg = pg_conn()
    pg_cur = pg.cursor()
    lms = lms_conn()
    lms_cur = lms.cursor()
    
    try:
        # Get all Waste Connections client IDs (there are multiple)
        pg_cur.execute("SELECT client_id, client_name FROM clients WHERE LOWER(client_name) LIKE '%waste connection%'")
        waste_clients = pg_cur.fetchall()
        print(f"Found {len(waste_clients)} Waste Connections clients:")
        for cid, cname in waste_clients:
            print(f"  ID {cid}: {cname}")
        print()
        
        client_ids = [c[0] for c in waste_clients]
        
        deletions = []
        total_duplicate_amount = 0
        
        for client_id in client_ids:
            # Find all $774 reserves for this client
            pg_cur.execute('''
                SELECT DISTINCT reserve_number
                FROM charters
                WHERE client_id = %s
                AND ABS(total_amount_due - 774.00) < 0.01
                ORDER BY reserve_number
            ''', (client_id,))
            
            reserves = [r[0] for r in pg_cur.fetchall()]
            print(f"Client {client_id}: {len(reserves)} $774 reserves")
            
            for reserve in reserves:
                # Check PostgreSQL
                pg_cur.execute('''
                    SELECT COUNT(*), SUM(amount)
                    FROM payments
                    WHERE reserve_number = %s
                    AND ABS(amount - 774.00) < 0.01
                ''', (reserve,))
                pg_row = pg_cur.fetchone()
                pg_count = pg_row[0]
                pg_total = float(pg_row[1]) if pg_row[1] else 0
                
                # Check how many are NULL-key from Aug 5
                pg_cur.execute('''
                    SELECT payment_id, payment_date
                    FROM payments
                    WHERE reserve_number = %s
                    AND ABS(amount - 774.00) < 0.01
                    AND payment_key IS NULL
                    AND DATE(created_at) = DATE('2025-08-05')
                    ORDER BY payment_date
                ''', (reserve,))
                null_key_payments = pg_cur.fetchall()
                null_key_count = len(null_key_payments)
                
                # Check LMS
                lms_cur.execute("SELECT COUNT(*), SUM(Amount) FROM Payment WHERE Reserve_No = ?", (reserve,))
                lms_row = lms_cur.fetchone()
                lms_count = lms_row[0] if lms_row else 0
                lms_total = float(lms_row[1]) if (lms_row and lms_row[1]) else 0
                
                if pg_count > lms_count and null_key_count > 0:
                    excess_count = pg_count - lms_count
                    # Delete the excess NULL-key payments
                    to_delete = null_key_payments[:excess_count]
                    
                    print(f"Reserve {reserve}:")
                    print(f"  PostgreSQL: {pg_count} payments (${pg_total:.2f})")
                    print(f"  LMS:        {lms_count} payments (${lms_total:.2f})")
                    print(f"  NULL-key:   {null_key_count} payments")
                    print(f"  → DELETE:   {len(to_delete)} duplicate payments")
                    for pid, pdate in to_delete:
                        deletions.append({'payment_id': pid, 'reserve': reserve, 'payment_date': pdate, 'client_id': client_id})
                        total_duplicate_amount += 774
                    print()
        
        print("=" * 70)
        print(f"Total duplicate payments to delete: {len(deletions)} (${total_duplicate_amount:,.2f})")
        print()
        
        if not deletions:
            print("No duplicates found to delete")
            return
        
        if args.write:
            # Create backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            payment_ids = [d['payment_id'] for d in deletions]
            
            backup_name = f"payments_backup_waste_duplicate_delete_{timestamp}"
            pg_cur.execute(f"""
                CREATE TABLE {backup_name} AS 
                SELECT * FROM payments 
                WHERE payment_id IN ({','.join(map(str, payment_ids))})
            """)
            print(f"✓ Backup created: {backup_name} ({len(deletions)} rows)")
            
            # Delete payments
            pg_cur.execute(f"DELETE FROM payments WHERE payment_id IN ({','.join(map(str, payment_ids))})")
            print(f"✓ Deleted {len(deletions)} duplicate payment records")
            
            # Delete false credits for Waste Connections UNIFORM_INSTALLMENT
            pg_cur.execute('''
                DELETE FROM charter_credit_ledger
                WHERE client_id IN %s
                AND credit_reason = 'UNIFORM_INSTALLMENT'
            ''', (tuple(client_ids),))
            deleted_credits = pg_cur.rowcount
            print(f"✓ Deleted {deleted_credits} false credit ledger entries for Waste Connections")
            
            pg.commit()
            print()
            print("✓ All changes committed")
            
            # Summary
            pg_cur.execute('''
                SELECT COUNT(*), SUM(amount)
                FROM payments p
                JOIN charters ch ON ch.reserve_number = p.reserve_number
                WHERE ch.client_id IN %s
                AND ABS(p.amount - 774.00) < 0.01
            ''', (tuple(client_ids),))
            r = pg_cur.fetchone()
            print()
            print(f"After cleanup:")
            print(f"  Waste Connections $774 payments: {r[0]} totaling ${r[1]:,.2f}")
        else:
            print("=== DRY-RUN MODE ===")
            print("Would delete:")
            for i, d in enumerate(deletions[:10], 1):
                print(f"  {i}. payment_id={d['payment_id']} reserve={d['reserve']} date={d['payment_date']}")
            if len(deletions) > 10:
                print(f"  ... and {len(deletions) - 10} more")
            print()
            print(f"Would also delete {len(affected_reserves)} UNIFORM_INSTALLMENT credit ledger entries")
            print()
            print("Run with --write to execute")
    
    except Exception as e:
        pg.rollback()
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        pg_cur.close()
        pg.close()
        lms_cur.close()
        lms.close()


if __name__ == '__main__':
    main()
