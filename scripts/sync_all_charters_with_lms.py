"""
Sync ALL charter paid_amount values with LMS Deposit field (source of truth).
Remove any PostgreSQL payments that exceed what LMS shows.
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
    parser = argparse.ArgumentParser(description='Sync charter paid_amount with LMS')
    parser.add_argument('--write', action='store_true', help='Actually update charters')
    parser.add_argument('--limit', type=int, help='Limit number of charters to process')
    args = parser.parse_args()
    
    pg_conn = get_pg_connection()
    pg_cur = pg_conn.cursor()
    
    lms_conn = get_lms_connection()
    lms_cur = lms_conn.cursor()
    
    try:
        print("=" * 80)
        print("SYNC CHARTER PAID_AMOUNT WITH LMS DEPOSIT")
        print("=" * 80)
        
        # Get all LMS reserves with their deposit amounts
        print(f"\n📊 Loading LMS deposit data...")
        lms_cur.execute("SELECT Reserve_No, Est_Charge, Deposit, Balance FROM Reserve")
        lms_data = {row[0]: (float(row[1] or 0), float(row[2] or 0), float(row[3] or 0)) 
                    for row in lms_cur.fetchall()}
        
        print(f"   ✓ Loaded {len(lms_data):,} LMS reserves")
        
        # Get PostgreSQL charters
        query = """
            SELECT reserve_number, total_amount_due, paid_amount, balance
            FROM charters
            WHERE reserve_number IS NOT NULL
        """
        if args.limit:
            query += f" ORDER BY balance ASC LIMIT {args.limit}"
        
        pg_cur.execute(query)
        pg_charters = pg_cur.fetchall()
        
        print(f"\n📊 Checking {len(pg_charters):,} PostgreSQL charters...")
        
        mismatches = []
        not_in_lms = []
        
        for charter in pg_charters:
            reserve, pg_total, pg_paid, pg_balance = charter
            
            if reserve in lms_data:
                lms_total, lms_deposit, lms_balance = lms_data[reserve]
                
                paid_diff = float(pg_paid) - lms_deposit
                
                if abs(paid_diff) > 0.01:  # More than 1 cent difference
                    mismatches.append({
                        'reserve': reserve,
                        'pg_total': float(pg_total),
                        'pg_paid': float(pg_paid),
                        'pg_balance': float(pg_balance),
                        'lms_total': lms_total,
                        'lms_deposit': lms_deposit,
                        'lms_balance': lms_balance,
                        'paid_diff': paid_diff
                    })
            else:
                not_in_lms.append(reserve)
        
        print(f"\n📊 ANALYSIS:")
        print(f"   Matches: {len(pg_charters) - len(mismatches) - len(not_in_lms):,}")
        print(f"   Mismatches: {len(mismatches):,}")
        print(f"   Not in LMS: {len(not_in_lms):,}")
        
        if mismatches:
            total_excess = sum(m['paid_diff'] for m in mismatches)
            overpaid = [m for m in mismatches if m['paid_diff'] > 0]
            underpaid = [m for m in mismatches if m['paid_diff'] < 0]
            
            print(f"\n   Overpaid (PG > LMS): {len(overpaid):,} charters, ${sum(m['paid_diff'] for m in overpaid):,.2f} excess")
            print(f"   Underpaid (PG < LMS): {len(underpaid):,} charters, ${abs(sum(m['paid_diff'] for m in underpaid)):,.2f} missing")
            print(f"   Net difference: ${total_excess:,.2f}")
            
            print(f"\n📋 TOP 20 OVERPAID (PG has more than LMS):")
            print(f"   {'Reserve':<10} {'PG Paid':>12} {'LMS Deposit':>12} {'Difference':>12}")
            print("   " + "-" * 50)
            for m in sorted(overpaid, key=lambda x: x['paid_diff'], reverse=True)[:20]:
                print(f"   {m['reserve']:<10} ${m['pg_paid']:>10,.2f} ${m['lms_deposit']:>10,.2f} ${m['paid_diff']:>10,.2f}")
        
        if not args.write:
            print(f"\n[WARN]  DRY RUN - No changes made. Use --write to apply.")
            return
        
        # Create backup
        backup_table = f"charters_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"\n📦 Creating backup: {backup_table}")
        
        reserve_list = [m['reserve'] for m in mismatches]
        pg_cur.execute(f"""
            CREATE TABLE {backup_table} AS
            SELECT * FROM charters
            WHERE reserve_number = ANY(%s)
        """, (reserve_list,))
        
        backup_count = pg_cur.rowcount
        print(f"   ✓ Backed up {backup_count:,} charters")
        
        # Update charters to match LMS
        print(f"\n🔄 Syncing {len(mismatches):,} charters with LMS...")
        
        updated_count = 0
        for m in mismatches:
            pg_cur.execute("""
                UPDATE charters
                SET paid_amount = %s,
                    balance = total_amount_due - %s
                WHERE reserve_number = %s
            """, (m['lms_deposit'], m['lms_deposit'], m['reserve']))
            updated_count += 1
            
            if updated_count % 100 == 0:
                print(f"   ... {updated_count:,} updated")
        
        pg_conn.commit()
        
        print(f"\n{'='*80}")
        print("[OK] SYNC COMPLETE")
        print("=" * 80)
        print(f"\nUpdated {updated_count:,} charters to match LMS Deposit field")
        print(f"Backup: {backup_table}")
        
        # Show final stats
        pg_cur.execute("""
            SELECT COUNT(*), SUM(balance)
            FROM charters
            WHERE balance < 0
        """)
        overpaid_count, overpaid_total = pg_cur.fetchone()
        
        print(f"\nRemaining overpaid charters: {overpaid_count:,} (${abs(overpaid_total or 0):,.2f})")
        
    except Exception as e:
        pg_conn.rollback()
        print(f"\n[FAIL] Error: {e}")
        raise
    finally:
        lms_cur.close()
        lms_conn.close()
        pg_cur.close()
        pg_conn.close()

if __name__ == '__main__':
    main()
