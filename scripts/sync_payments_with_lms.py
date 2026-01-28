"""
Sync PostgreSQL payments with LMS Payment table (source of truth).
Remove payments that don't exist in LMS, keep only LMS-verified payments.
"""

import psycopg2
import pyodbc
import os
import argparse
from datetime import datetime

def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def get_lms_connection():
    conn_str = (
        r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};'
        r'DBQ=L:\limo\backups\lms.mdb;'
    )
    return pyodbc.connect(conn_str)

def main():
    parser = argparse.ArgumentParser(description='Sync payments with LMS')
    parser.add_argument('--write', action='store_true', help='Actually delete non-LMS payments')
    args = parser.parse_args()
    
    pg_conn = get_pg_connection()
    pg_cur = pg_conn.cursor()
    
    lms_conn = get_lms_connection()
    lms_cur = lms_conn.cursor()
    
    try:
        print("=" * 80)
        print("SYNC POSTGRESQL PAYMENTS WITH LMS PAYMENT TABLE")
        print("=" * 80)
        
        # Get all LMS Payment IDs that exist
        lms_cur.execute("SELECT PaymentID FROM Payment")
        lms_payment_ids = set(str(row[0]) for row in lms_cur.fetchall())
        
        print(f"\n📊 LMS has {len(lms_payment_ids):,} payments in Payment table")
        
        # Get PostgreSQL payments that claim to be from LMS
        pg_cur.execute("""
            SELECT payment_id, reserve_number, amount, notes
            FROM payments
            WHERE notes LIKE '%Imported from LMS Payment ID%'
        """)
        
        pg_lms_payments = pg_cur.fetchall()
        print(f"📊 PostgreSQL has {len(pg_lms_payments):,} payments claiming LMS source")
        
        # Check which PostgreSQL payments don't have valid LMS PaymentID
        invalid_payments = []
        for pg_payment in pg_lms_payments:
            payment_id, reserve, amount, notes = pg_payment
            
            # Extract LMS PaymentID from notes
            if 'Imported from LMS Payment ID' in notes:
                try:
                    lms_id = notes.split('Imported from LMS Payment ID')[1].strip().split()[0]
                    if lms_id not in lms_payment_ids:
                        invalid_payments.append((payment_id, reserve, amount, lms_id))
                except:
                    invalid_payments.append((payment_id, reserve, amount, 'PARSE_ERROR'))
        
        print(f"\n[WARN]  Found {len(invalid_payments)} PostgreSQL payments with invalid LMS IDs")
        
        if invalid_payments:
            print(f"\n📋 SAMPLE (first 20):")
            print(f"\n{'PG ID':<10} {'Reserve':<10} {'Amount':>12} LMS ID")
            print("-" * 50)
            for p in invalid_payments[:20]:
                print(f"{p[0]:<10} {p[1]:<10} ${p[2]:>10,.2f} {p[3]}")
        
        # Now find payments that are NOT from LMS (Square, auto-matched, etc)
        pg_cur.execute("""
            SELECT payment_id, reserve_number, amount, payment_method, notes
            FROM payments
            WHERE notes NOT LIKE '%Imported from LMS Payment ID%'
              OR notes IS NULL
        """)
        
        non_lms_payments = pg_cur.fetchall()
        print(f"\n📊 PostgreSQL has {len(non_lms_payments):,} payments NOT from LMS")
        
        # Categorize non-LMS payments
        square_payments = [p for p in non_lms_payments if p[4] and '[Square]' in p[4]]
        auto_matched = [p for p in non_lms_payments if p[4] and 'AUTO-MATCHED' in p[4]]
        other = [p for p in non_lms_payments if p not in square_payments and p not in auto_matched]
        
        print(f"   - Square payments: {len(square_payments):,}")
        print(f"   - Auto-matched: {len(auto_matched):,}")
        print(f"   - Other: {len(other):,}")
        
        # For overpaid charters, check if Square payments exist in LMS
        pg_cur.execute("""
            SELECT DISTINCT c.reserve_number
            FROM charters c
            JOIN payments p ON p.reserve_number = c.reserve_number
            WHERE c.balance < 0
              AND p.notes LIKE '%[Square]%'
        """)
        
        overpaid_with_square = [row[0] for row in pg_cur.fetchall()]
        print(f"\n[WARN]  {len(overpaid_with_square)} overpaid charters have Square payments")
        
        # Check if these Square payments exist in LMS for these charters
        for reserve in overpaid_with_square[:5]:  # Sample first 5
            lms_cur.execute("SELECT COUNT(*), SUM(Amount) FROM Payment WHERE Reserve_No = ?", (reserve,))
            lms_count, lms_sum = lms_cur.fetchone()
            
            pg_cur.execute("SELECT COUNT(*), SUM(amount) FROM payments WHERE reserve_number = %s", (reserve,))
            pg_count, pg_sum = pg_cur.fetchone()
            
            print(f"\n   {reserve}: LMS {lms_count} payments (${lms_sum or 0:,.2f}) vs PG {pg_count} payments (${pg_sum:,.2f})")
        
        print(f"\n{'='*80}")
        print("RECOMMENDATION")
        print("=" * 80)
        print("\nOption 1: Delete ALL non-LMS payments (Square, auto-matched)")
        print("  - Most conservative")
        print("  - Trust only LMS Payment table")
        print(f"  - Would remove {len(non_lms_payments):,} payments")
        
        print("\nOption 2: Delete only Square payments from overpaid charters")
        print("  - More targeted")
        print("  - Keeps other payment sources")
        print(f"  - Would remove ~{len(square_payments)} Square payments")
        
    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        raise
    finally:
        lms_cur.close()
        lms_conn.close()
        pg_cur.close()
        pg_conn.close()

if __name__ == '__main__':
    main()
