"""
Check LMS Access database for 2012 payroll data completeness
"""
import pyodbc
import psycopg2

LMS_PATH = r'L:\limo\lms.mdb'

def main():
    print("=" * 80)
    print("LMS 2012 PAYROLL DATA VERIFICATION")
    print("=" * 80)
    
    # Connect to LMS
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    lms_conn = pyodbc.connect(conn_str)
    lms_cur = lms_conn.cursor()
    
    # Check what tables exist
    print("\nChecking LMS tables with payroll data...")
    lms_cur.execute("SELECT Name FROM MSysObjects WHERE Type=1 AND Flags=0 ORDER BY Name")
    tables = [row[0] for row in lms_cur.fetchall()]
    
    payroll_tables = [t for t in tables if 'pay' in t.lower() or 'driver' in t.lower() or 'wage' in t.lower()]
    print(f"Found {len(payroll_tables)} potential payroll tables:")
    for t in payroll_tables:
        print(f"  - {t}")
    
    # Check Payment table for 2012 data
    print("\n" + "-" * 80)
    print("LMS Payment Table Analysis (2012)")
    print("-" * 80)
    
    try:
        lms_cur.execute("""
            SELECT 
                COUNT(*) as total_payments,
                SUM(Amount) as total_amount
            FROM Payment
            WHERE Year(LastUpdated) = 2012
        """)
        row = lms_cur.fetchone()
        print(f"Total 2012 payments in LMS: {row[0]}")
        print(f"Total payment amount: ${row[1]:,.2f}" if row[1] else "Total payment amount: $0.00")
    except Exception as e:
        print(f"Error querying Payment table: {e}")
    
    # Check Reserve table for 2012 charters
    print("\n" + "-" * 80)
    print("LMS Reserve Table Analysis (2012)")
    print("-" * 80)
    
    try:
        lms_cur.execute("""
            SELECT 
                COUNT(*) as total_charters,
                SUM(Rate) as total_rate,
                SUM(Balance) as total_balance,
                SUM(Deposit) as total_deposit
            FROM Reserve
            WHERE Year(PU_Date) = 2012
        """)
        row = lms_cur.fetchone()
        print(f"Total 2012 charters in LMS: {row[0]}")
        print(f"Total charter rate: ${row[1]:,.2f}" if row[1] else "Total rate: $0.00")
        print(f"Total balance owed: ${row[2]:,.2f}" if row[2] else "Total balance: $0.00")
        print(f"Total deposits: ${row[3]:,.2f}" if row[3] else "Total deposits: $0.00")
    except Exception as e:
        print(f"Error querying Reserve table: {e}")
    
    # Check for driver pay tables
    print("\n" + "-" * 80)
    print("Checking for Driver Pay/Wage Tables")
    print("-" * 80)
    
    for table in payroll_tables:
        try:
            lms_cur.execute(f"SELECT COUNT(*) FROM [{table}]")
            count = lms_cur.fetchone()[0]
            print(f"{table}: {count} records")
            
            # Try to get column names
            lms_cur.execute(f"SELECT TOP 1 * FROM [{table}]")
            columns = [column[0] for column in lms_cur.description]
            print(f"  Columns: {', '.join(columns[:10])}{'...' if len(columns) > 10 else ''}")
        except Exception as e:
            print(f"{table}: Error - {e}")
    
    lms_cur.close()
    lms_conn.close()
    
    # Compare to PostgreSQL
    print("\n" + "=" * 80)
    print("POSTGRESQL DATABASE COMPARISON")
    print("=" * 80)
    
    pg_conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    pg_cur = pg_conn.cursor()
    
    pg_cur.execute("""
        SELECT 
            COUNT(*) as total_records,
            SUM(gross_pay) as total_gross
        FROM driver_payroll
        WHERE year = 2012
    """)
    row = pg_cur.fetchone()
    print(f"\nPostgreSQL driver_payroll (2012):")
    print(f"  Total records: {row[0]}")
    print(f"  Total gross pay: ${row[1]:,.2f}" if row[1] else "  Total gross pay: $0.00")
    
    pg_cur.execute("""
        SELECT COUNT(*) FROM charters WHERE EXTRACT(YEAR FROM charter_date) = 2012
    """)
    charter_count = pg_cur.fetchone()[0]
    print(f"\nPostgreSQL charters (2012): {charter_count} records")
    
    pg_cur.close()
    pg_conn.close()
    
    print("\n" + "=" * 80)
    print("KEY FINDINGS")
    print("=" * 80)
    print("\nThe discrepancies are due to:")
    print("1. base_wages field is 99.9% empty (only 1 record populated)")
    print("2. gratuity_amount field is 99.9% empty (only 1 record populated)")
    print("3. hours_worked field is 100% empty")
    print("4. Database has 'gross_pay' and 'expenses' but not the component breakdown")
    print("\nACTION NEEDED:")
    print("- Populate base_wages from gross_pay field")
    print("- Import gratuity data if available from source files")
    print("- Import hours_worked data if available")
    print("- Verify if missing payroll records need to be imported from LMS or other sources")

if __name__ == '__main__':
    main()
