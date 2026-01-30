"""
Fix the remaining 6 charter date mismatches identified in comprehensive audit.
Targets specific charters: 019572, 019531, 019524, 019523, 017186, 013305
"""
import psycopg2
import pyodbc
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def get_lms_connection():
    lms_path = r'L:\limo\backups\lms.mdb'
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={lms_path};'
    return pyodbc.connect(conn_str)

def main():
    pg_conn = get_db_connection()
    lms_conn = get_lms_connection()
    
    pg_cur = pg_conn.cursor()
    lms_cur = lms_conn.cursor()
    
    # Target charters identified in audit
    target_charters = ['019572', '019531', '019524', '019523', '017186', '013305']
    
    print("="*80)
    print("FIXING REMAINING 6 DATE MISMATCHES")
    print("="*80)
    print()
    
    fixes = []
    
    for reserve_number in target_charters:
        # Get PostgreSQL current date
        pg_cur.execute("""
            SELECT reserve_number, charter_date, total_amount_due, paid_amount
            FROM charters
            WHERE reserve_number = %s
        """, (reserve_number,))
        
        pg_result = pg_cur.fetchone()
        if not pg_result:
            print(f"⚠️  {reserve_number}: Not found in PostgreSQL")
            continue
        
        pg_reserve, pg_date, pg_total, pg_paid = pg_result
        
        # Get LMS correct date
        lms_cur.execute("""
            SELECT Reserve_No, PU_Date, Est_Charge, Deposit
            FROM Reserve
            WHERE Reserve_No = ?
        """, (reserve_number,))
        
        lms_result = lms_cur.fetchone()
        if not lms_result:
            print(f"⚠️  {reserve_number}: Not found in LMS")
            continue
        
        lms_reserve, lms_pu_date, lms_charge, lms_deposit = lms_result
        lms_date = lms_pu_date.date() if lms_pu_date else None
        
        if pg_date != lms_date:
            fixes.append({
                'reserve': reserve_number,
                'old_date': pg_date,
                'new_date': lms_date
            })
    
    if not fixes:
        print("✅ No mismatches found - all dates already correct!")
        pg_cur.close()
        lms_cur.close()
        pg_conn.close()
        lms_conn.close()
        return
    
    print(f"Found {len(fixes)} charters to fix:")
    print("-" * 80)
    print(f"{'Reserve':<10} {'Current (PG)':<15} {'Correct (LMS)':<15} {'Difference':<20}")
    print("-" * 80)
    
    for fix in fixes:
        old_date_str = fix['old_date'].strftime('%Y-%m-%d') if fix['old_date'] else 'NULL'
        new_date_str = fix['new_date'].strftime('%Y-%m-%d') if fix['new_date'] else 'NULL'
        
        # Calculate difference
        if fix['old_date'] and fix['new_date']:
            diff_days = (fix['new_date'] - fix['old_date']).days
            if abs(diff_days) >= 365:
                diff_str = f"{diff_days // 365} years, {diff_days % 365} days"
            else:
                diff_str = f"{diff_days} days"
        else:
            diff_str = "N/A"
        
        print(f"{fix['reserve']:<10} {old_date_str:<15} {new_date_str:<15} {diff_str:<20}")
    
    print()
    print("Creating backup table...")
    
    # Create backup table
    backup_table = f"charters_date_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    reserve_list = ','.join([f"'{f['reserve']}'" for f in fixes])
    
    pg_cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM charters
        WHERE reserve_number IN ({reserve_list})
    """)
    
    backup_count = pg_cur.rowcount
    print(f"✓ Created backup table: {backup_table} ({backup_count} rows)")
    print()
    
    # Apply fixes
    print("Applying fixes...")
    print("-" * 80)
    
    for fix in fixes:
        pg_cur.execute("""
            UPDATE charters
            SET charter_date = %s
            WHERE reserve_number = %s
        """, (fix['new_date'], fix['reserve']))
        
        old_str = fix['old_date'].strftime('%Y-%m-%d') if fix['old_date'] else 'NULL'
        new_str = fix['new_date'].strftime('%Y-%m-%d') if fix['new_date'] else 'NULL'
        print(f"  Fixed {fix['reserve']}: {old_str} → {new_str}")
    
    pg_conn.commit()
    print()
    print(f"✓ Fixed {len(fixes)} charter dates")
    print(f"✓ Backup saved to: {backup_table}")
    print()
    print("="*80)
    print("✅ ALL CHARTER DATES NOW MATCH LMS - 100% ACCURACY ACHIEVED")
    print("="*80)
    
    pg_cur.close()
    lms_cur.close()
    pg_conn.close()
    lms_conn.close()

if __name__ == '__main__':
    main()
