#!/usr/bin/env python3
"""Remove duplicate Waste Connections $774 payments created by Aug 5, 2025 import.

Investigation shows reserve 013932 has 21 payments in PostgreSQL but only 1 in LMS.
The 20 NULL-key payments created on 2025-08-05 are duplicates and should be removed.

This script:
  1. Identifies NULL-key $774 payments on Waste Connections reserves
  2. Verifies against LMS Payment table
  3. Removes duplicates that don't exist in LMS
  4. Recalculates charter paid_amount and balance
  5. Adjusts credit ledger entries

Usage:
  python scripts/remove_waste_774_duplicates.py              # Dry-run
  python scripts/remove_waste_774_duplicates.py --write      # Execute
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
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def lms_conn():
    return pyodbc.connect(f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};")


def find_waste_client_id(cur):
    cur.execute("SELECT client_id FROM clients WHERE LOWER(client_name) LIKE '%waste connection%' LIMIT 1")
    return cur.fetchone()[0]


def analyze_duplicates():
    pg = pg_conn()
    pg_cur = pg.cursor()
    lms = lms_conn()
    lms_cur = lms.cursor()
    
    client_id = find_waste_client_id(pg_cur)
    
    # Get all Waste Connections $774 reserves with their payment counts
    pg_cur.execute('''
        SELECT 
            ch.reserve_number,
            ch.charter_id,
            ch.charter_date,
            ch.paid_amount,
            COUNT(p.payment_id) as pg_payment_count,
            SUM(CASE WHEN p.payment_key IS NULL AND p.created_at::date = '2025-08-05' THEN 1 ELSE 0 END) as null_key_count
        FROM charters ch
        LEFT JOIN payments p ON p.reserve_number = ch.reserve_number AND ABS(p.amount - 774.00) < 0.01
        WHERE ch.client_id = %s
        AND ABS(ch.total_amount_due - 774.00) < 0.01
        GROUP BY ch.reserve_number, ch.charter_id, ch.charter_date, ch.paid_amount
        HAVING COUNT(p.payment_id) > 1
        ORDER BY COUNT(p.payment_id) DESC
    ''', (client_id,))
    
    multi_payment_reserves = pg_cur.fetchall()
    
    duplicates_to_remove = []
    total_duplicate_amount = 0
    
    print(f"Analyzing {len(multi_payment_reserves)} reserves with multiple $774 payments...")
    print()
    
    for reserve, charter_id, charter_date, pg_paid, pg_count, null_count in multi_payment_reserves:
        # Check LMS
        lms_cur.execute("SELECT COUNT(*), SUM(Amount) FROM Payment WHERE Reserve_No = ?", (reserve,))
        lms_row = lms_cur.fetchone()
        lms_count = lms_row[0] if lms_row else 0
        lms_total = float(lms_row[1]) if (lms_row and lms_row[1]) else 0.0
        
        if pg_count > lms_count:
            excess_count = pg_count - lms_count
            print(f"Reserve {reserve}:")
            print(f"  PostgreSQL: {pg_count} payments (${pg_paid:.2f} paid)")
            print(f"  LMS:        {lms_count} payments (${lms_total:.2f})")
            print(f"  NULL-key:   {null_count} payments from Aug 5, 2025")
            print(f"  ❌ Excess:  {excess_count} duplicate payments (${excess_count * 774:.2f})")
            
            # Get the NULL-key payment IDs
            pg_cur.execute('''
                SELECT payment_id, payment_date
                FROM payments
                WHERE reserve_number = %s
                AND payment_key IS NULL
                AND created_at::date = '2025-08-05'
                AND ABS(amount - 774.00) < 0.01
                ORDER BY payment_date
                LIMIT %s
            ''', (reserve, excess_count))
            
            dup_payments = pg_cur.fetchall()
            for pid, pdate in dup_payments:
                duplicates_to_remove.append({
                    'payment_id': pid,
                    'reserve_number': reserve,
                    'charter_id': charter_id,
                    'payment_date': pdate,
                    'amount': 774.00,
                })
                total_duplicate_amount += 774.00
            
            print()
    
    return duplicates_to_remove, total_duplicate_amount


def remove_duplicates(duplicates, dry_run=True):
    pg = pg_conn()
    pg_cur = pg.cursor()
    
    try:
        if not dry_run:
            # Create backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"payments_backup_waste_774_cleanup_{timestamp}"
            pg_cur.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM payments WHERE payment_id IN ({','.join(str(d['payment_id']) for d in duplicates)})")
            print(f"Backup created: {backup_name} ({len(duplicates)} rows)")
            print()
        
        # Group by charter
        by_charter = {}
        for dup in duplicates:
            charter_id = dup['charter_id']
            if charter_id not in by_charter:
                by_charter[charter_id] = []
            by_charter[charter_id].append(dup)
        
        for charter_id, charter_dups in by_charter.items():
            reserve = charter_dups[0]['reserve_number']
            reduction = len(charter_dups) * 774.00
            
            if not dry_run:
                # Delete duplicate payments
                for dup in charter_dups:
                    pg_cur.execute("DELETE FROM payments WHERE payment_id = %s", (dup['payment_id'],))
                
                # Reduce charter paid_amount
                pg_cur.execute('''
                    UPDATE charters
                    SET paid_amount = paid_amount - %s,
                        balance = balance + %s
                    WHERE charter_id = %s
                ''', (reduction, reduction, charter_id))
                
                # Reduce credit ledger
                pg_cur.execute('''
                    UPDATE charter_credit_ledger
                    SET credit_amount = credit_amount - %s,
                        remaining_balance = remaining_balance - %s
                    WHERE source_charter_id = %s
                ''', (reduction, reduction, charter_id))
        
        if not dry_run:
            pg.commit()
        
        return len(duplicates), sum(d['amount'] for d in duplicates)
    
    finally:
        pg_cur.close()
        pg.close()


def main():
    parser = ArgumentParser(description='Remove duplicate Waste Connections $774 payments')
    parser.add_argument('--write', action='store_true', help='Execute deletions (default is dry-run)')
    args = parser.parse_args()
    
    duplicates, total_amount = analyze_duplicates()
    
    print("=" * 80)
    print(f"Found {len(duplicates)} duplicate payments totaling ${total_amount:,.2f}")
    print()
    
    if duplicates:
        if args.write:
            count, amount = remove_duplicates(duplicates, dry_run=False)
            print(f"✓ Removed {count} duplicate payments (${amount:,.2f})")
            print("✓ Updated charter paid_amount and balance")
            print("✓ Reduced credit ledger entries")
        else:
            print("=== DRY-RUN MODE ===")
            print(f"Would remove {len(duplicates)} payments:")
            for i, dup in enumerate(duplicates[:10], 1):
                print(f"  {i}. payment_id={dup['payment_id']} reserve={dup['reserve_number']} date={dup['payment_date']}")
            if len(duplicates) > 10:
                print(f"  ... and {len(duplicates) - 10} more")
            print()
            print("Run with --write to execute")
    else:
        print("No duplicates found")


if __name__ == '__main__':
    main()
