"""
Check what 2010-2012 data exists in almsdata database
"""
import psycopg2
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def check_charters_2010_2012():
    """Check charter data for 2010-2012"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("CHARTER DATA 2010-2012")
    print("=" * 80)
    
    # Overall stats
    cur.execute("""
        SELECT 
            MIN(charter_date) as earliest, 
            MAX(charter_date) as latest, 
            COUNT(*) as total,
            SUM(COALESCE(rate, 0)) as total_revenue,
            SUM(COALESCE(balance, 0)) as total_balance
        FROM charters 
        WHERE EXTRACT(YEAR FROM charter_date) BETWEEN 2010 AND 2012
    """)
    row = cur.fetchone()
    print(f"\nOverall 2010-2012:")
    print(f"  Records: {row[2]:,}")
    print(f"  Date Range: {row[0]} to {row[1]}")
    print(f"  Total Revenue: ${row[3]:,.2f}" if row[3] else "  Total Revenue: $0.00")
    print(f"  Total Balance: ${row[4]:,.2f}" if row[4] else "  Total Balance: $0.00")
    
    # By year
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM charter_date) as yr, 
            COUNT(*) as count,
            SUM(COALESCE(rate, 0)) as revenue,
            SUM(COALESCE(balance, 0)) as balance
        FROM charters 
        WHERE EXTRACT(YEAR FROM charter_date) BETWEEN 2010 AND 2012 
        GROUP BY EXTRACT(YEAR FROM charter_date)
        ORDER BY yr
    """)
    
    print("\nBy Year:")
    for row in cur.fetchall():
        print(f"  {int(row[0])}: {row[1]:,} charters | Revenue: ${row[2]:,.2f} | Balance: ${row[3]:,.2f}")
    
    cur.close()
    conn.close()

def check_payments_2010_2012():
    """Check payment data for 2010-2012"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "=" * 80)
    print("PAYMENT DATA 2010-2012")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM payment_date) as yr,
            COUNT(*) as count,
            SUM(COALESCE(amount, 0)) as total_amount
        FROM payments
        WHERE EXTRACT(YEAR FROM payment_date) BETWEEN 2010 AND 2012
        GROUP BY EXTRACT(YEAR FROM payment_date)
        ORDER BY yr
    """)
    
    print("\nPayments by Year:")
    rows = cur.fetchall()
    if rows:
        for row in rows:
            print(f"  {int(row[0])}: {row[1]:,} payments | Total: ${row[2]:,.2f}")
    else:
        print("  No payment records found for 2010-2012")
    
    cur.close()
    conn.close()

def check_receipts_2010_2012():
    """Check receipt/expense data for 2010-2012"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "=" * 80)
    print("RECEIPT/EXPENSE DATA 2010-2012")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as yr,
            COUNT(*) as count,
            SUM(COALESCE(gross_amount, 0)) as total_gross,
            SUM(COALESCE(gst_amount, 0)) as total_gst
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2010 AND 2012
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY yr
    """)
    
    print("\nReceipts by Year:")
    rows = cur.fetchall()
    if rows:
        for row in rows:
            print(f"  {int(row[0])}: {row[1]:,} receipts | Gross: ${row[2]:,.2f} | GST: ${row[3]:,.2f}")
    else:
        print("  No receipt records found for 2010-2012")
    
    cur.close()
    conn.close()

def check_reserve_numbers_2010_2012():
    """Check reserve number range for 2010-2012"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "=" * 80)
    print("RESERVE NUMBERS 2010-2012")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM charter_date) as yr,
            MIN(reserve_number) as min_reserve,
            MAX(reserve_number) as max_reserve,
            COUNT(DISTINCT reserve_number) as unique_reserves
        FROM charters
        WHERE EXTRACT(YEAR FROM charter_date) BETWEEN 2010 AND 2012
        GROUP BY EXTRACT(YEAR FROM charter_date)
        ORDER BY yr
    """)
    
    print("\nReserve Number Ranges:")
    rows = cur.fetchall()
    if rows:
        for row in rows:
            print(f"  {int(row[0])}: {row[1]} to {row[2]} ({row[3]:,} unique)")
    else:
        print("  No reserve numbers found for 2010-2012")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    try:
        check_charters_2010_2012()
        check_payments_2010_2012()
        check_receipts_2010_2012()
        check_reserve_numbers_2010_2012()
        
        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
