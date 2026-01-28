"""
Verify charter total_amount_due matches LMS Est_Charge field (source of truth).
Check if PostgreSQL totals match what LMS shows as the actual charter cost.
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
    parser = argparse.ArgumentParser(description='Verify charter totals with LMS')
    parser.add_argument('--write', action='store_true', help='Actually update charters')
    parser.add_argument('--limit', type=int, help='Limit number to check')
    args = parser.parse_args()
    
    pg_conn = get_pg_connection()
    pg_cur = pg_conn.cursor()
    
    lms_conn = get_lms_connection()
    lms_cur = lms_conn.cursor()
    
    try:
        print("=" * 80)
        print("VERIFY CHARTER TOTAL_AMOUNT_DUE WITH LMS EST_CHARGE")
        print("=" * 80)
        
        # Get all LMS reserves with their Est_Charge amounts
        print(f"\n📊 Loading LMS Est_Charge data...")
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
            query += f" LIMIT {args.limit}"
        
        pg_cur.execute(query)
        pg_charters = pg_cur.fetchall()
        
        print(f"\n📊 Checking {len(pg_charters):,} PostgreSQL charters...")
        
        mismatches = []
        not_in_lms = []
        
        for charter in pg_charters:
            reserve, pg_total, pg_paid, pg_balance = charter
            
            if reserve in lms_data:
                lms_est_charge, lms_deposit, lms_balance = lms_data[reserve]
                
                # Handle NULL values
                pg_total = float(pg_total or 0)
                total_diff = pg_total - lms_est_charge
                
                if abs(total_diff) > 0.01:  # More than 1 cent difference
                    mismatches.append({
                        'reserve': reserve,
                        'pg_total': float(pg_total),
                        'pg_paid': float(pg_paid),
                        'pg_balance': float(pg_balance),
                        'lms_est_charge': lms_est_charge,
                        'lms_deposit': lms_deposit,
                        'lms_balance': lms_balance,
                        'total_diff': total_diff
                    })
            else:
                not_in_lms.append(reserve)
        
        print(f"\n📊 ANALYSIS:")
        print(f"   Matches: {len(pg_charters) - len(mismatches) - len(not_in_lms):,}")
        print(f"   Mismatches: {len(mismatches):,}")
        print(f"   Not in LMS: {len(not_in_lms):,}")
        
        if mismatches:
            total_excess = sum(m['total_diff'] for m in mismatches)
            higher = [m for m in mismatches if m['total_diff'] > 0]
            lower = [m for m in mismatches if m['total_diff'] < 0]
            
            print(f"\n   Higher (PG > LMS): {len(higher):,} charters, ${sum(m['total_diff'] for m in higher):,.2f} excess")
            print(f"   Lower (PG < LMS): {len(lower):,} charters, ${abs(sum(m['total_diff'] for m in lower)):,.2f} missing")
            print(f"   Net difference: ${total_excess:,.2f}")
            
            print(f"\n📋 TOP 20 WITH HIGHEST TOTAL_AMOUNT_DUE DIFFERENCES:")
            print(f"   {'Reserve':<10} {'PG Total':>12} {'LMS Est_Charge':>15} {'Difference':>12}")
            print("   " + "-" * 55)
            for m in sorted(mismatches, key=lambda x: abs(x['total_diff']), reverse=True)[:20]:
                print(f"   {m['reserve']:<10} ${m['pg_total']:>10,.2f} ${m['lms_est_charge']:>13,.2f} ${m['total_diff']:>10,.2f}")
            
            # Show balance impact
            print(f"\n📋 BALANCE IMPACT (Top 10):")
            print(f"   {'Reserve':<10} {'PG Balance':>12} {'LMS Balance':>12} {'Difference':>12}")
            print("   " + "-" * 50)
            for m in sorted(mismatches, key=lambda x: abs(x['total_diff']), reverse=True)[:10]:
                print(f"   {m['reserve']:<10} ${m['pg_balance']:>10,.2f} ${m['lms_balance']:>10,.2f} ${m['pg_balance'] - m['lms_balance']:>10,.2f}")
        
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
        print(f"\n🔄 Syncing {len(mismatches):,} charter totals with LMS...")
        
        updated_count = 0
        for m in mismatches:
            pg_cur.execute("""
                UPDATE charters
                SET total_amount_due = %s,
                    balance = %s - paid_amount
                WHERE reserve_number = %s
            """, (m['lms_est_charge'], m['lms_est_charge'], m['reserve']))
            updated_count += 1
            
            if updated_count % 100 == 0:
                print(f"   ... {updated_count:,} updated")
        
        pg_conn.commit()
        
        print(f"\n{'='*80}")
        print("[OK] SYNC COMPLETE")
        print("=" * 80)
        print(f"\nUpdated {updated_count:,} charters to match LMS Est_Charge field")
        print(f"Backup: {backup_table}")
        
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
