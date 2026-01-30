"""
Verify remaining overpaid charters against LMS source data.
Check if PostgreSQL paid_amount matches LMS Deposit field.
"""

import psycopg2
import pyodbc
import os

def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def get_lms_connection():
    conn_str = (
        r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};'
        r'DBQ=L:\limo\backups\lms.mdb;'
    )
    return pyodbc.connect(conn_str)

def main():
    pg_conn = get_pg_connection()
    pg_cur = pg_conn.cursor()
    
    lms_conn = get_lms_connection()
    lms_cur = lms_conn.cursor()
    
    try:
        print("=" * 80)
        print("VERIFY OVERPAID CHARTERS AGAINST LMS")
        print("=" * 80)
        
        # Get top 20 overpaid charters
        pg_cur.execute("""
            SELECT reserve_number, charter_date, total_amount_due, paid_amount, balance, status
            FROM charters
            WHERE balance < 0
            ORDER BY balance ASC
            LIMIT 20
        """)
        
        overpaid = pg_cur.fetchall()
        
        print(f"\n📊 Checking {len(overpaid)} most overpaid charters against LMS...\n")
        
        mismatches = []
        
        for charter in overpaid:
            reserve, date, total, paid, balance, status = charter
            
            # Query LMS
            lms_cur.execute("""
                SELECT Est_Charge, Deposit, Balance 
                FROM Reserve 
                WHERE Reserve_No = ?
            """, (reserve,))
            
            lms_row = lms_cur.fetchone()
            
            if lms_row:
                lms_total, lms_deposit, lms_balance = lms_row
                lms_total = float(lms_total or 0)
                lms_deposit = float(lms_deposit or 0)
                lms_balance = float(lms_balance or 0)
                
                paid_diff = float(paid) - lms_deposit
                
                if abs(paid_diff) > 0.01:  # More than 1 cent difference
                    mismatches.append({
                        'reserve': reserve,
                        'pg_paid': float(paid),
                        'lms_deposit': lms_deposit,
                        'diff': paid_diff,
                        'pg_balance': float(balance),
                        'lms_balance': lms_balance
                    })
                    
                    print(f"[FAIL] {reserve}: PG paid ${paid:,.2f} vs LMS deposit ${lms_deposit:,.2f} (diff: ${paid_diff:,.2f})")
                else:
                    print(f"✓ {reserve}: PG paid ${paid:,.2f} = LMS deposit ${lms_deposit:,.2f}")
            else:
                print(f"[WARN]  {reserve}: NOT FOUND in LMS")
        
        print(f"\n{'='*80}")
        print(f"SUMMARY")
        print("=" * 80)
        print(f"\nTotal checked: {len(overpaid)}")
        print(f"Mismatches found: {len(mismatches)}")
        
        if mismatches:
            total_excess = sum(m['diff'] for m in mismatches)
            print(f"\nTotal excess paid in PostgreSQL: ${total_excess:,.2f}")
            print(f"\nThese charters have MORE paid in PostgreSQL than LMS shows.")
            print(f"This indicates additional non-LMS payments that should be removed.")
            
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
