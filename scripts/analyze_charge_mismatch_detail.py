"""
Analyze the charge mismatches to understand what's happening.
Many charters have total_amount_due but no charter_charges records.
"""
import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def analyze():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("ANALYZING CHARGE MISMATCHES")
    print("=" * 100)
    
    # Charters with total_amount_due but no charges
    cur.execute("""
        SELECT COUNT(*), SUM(c.total_amount_due)
        FROM charters c
        WHERE c.total_amount_due > 0
          AND NOT EXISTS (
              SELECT 1 FROM charter_charges cc 
              WHERE cc.charter_id = c.charter_id
          )
    """)
    
    no_charges_count, no_charges_total = cur.fetchone()
    print(f"\n1. Charters with total_amount_due but NO charge records:")
    print(f"   Count: {no_charges_count}")
    print(f"   Total: ${no_charges_total or 0:,.2f}")
    
    # Charters with charges but mismatched totals
    cur.execute("""
        WITH charge_sums AS (
            SELECT 
                charter_id,
                SUM(amount) as actual_charges
            FROM charter_charges
            GROUP BY charter_id
        )
        SELECT COUNT(*), SUM(ABS(c.total_amount_due - cs.actual_charges))
        FROM charters c
        INNER JOIN charge_sums cs ON c.charter_id = cs.charter_id
        WHERE ABS(c.total_amount_due - cs.actual_charges) > 0.01
          AND cs.actual_charges > 0
    """)
    
    has_charges_count, has_charges_diff = cur.fetchone()
    print(f"\n2. Charters WITH charges but mismatched total_amount_due:")
    print(f"   Count: {has_charges_count}")
    print(f"   Total difference: ${has_charges_diff or 0:,.2f}")
    
    # Check if these are quotes or cancelled
    cur.execute("""
        SELECT 
            c.booking_status,
            COUNT(*),
            SUM(c.total_amount_due)
        FROM charters c
        WHERE c.total_amount_due > 0
          AND NOT EXISTS (
              SELECT 1 FROM charter_charges cc 
              WHERE cc.charter_id = c.charter_id
          )
        GROUP BY c.booking_status
        ORDER BY COUNT(*) DESC
    """)
    
    print(f"\n3. Booking status of charters with no charges:")
    for row in cur.fetchall():
        status, count, total = row
        print(f"   {status or 'NULL'}: {count} charters, ${total or 0:,.2f}")
    
    # Check cancelled status
    cur.execute("""
        SELECT 
            c.cancelled,
            COUNT(*),
            SUM(c.total_amount_due)
        FROM charters c
        WHERE c.total_amount_due > 0
          AND NOT EXISTS (
              SELECT 1 FROM charter_charges cc 
              WHERE cc.charter_id = c.charter_id
          )
        GROUP BY c.cancelled
    """)
    
    print(f"\n4. Cancelled status of charters with no charges:")
    for row in cur.fetchall():
        cancelled, count, total = row
        print(f"   {'Cancelled' if cancelled else 'Not Cancelled'}: {count} charters, ${total or 0:,.2f}")
    
    # Sample some with actual mismatches (not zero charges)
    cur.execute("""
        WITH charge_sums AS (
            SELECT 
                charter_id,
                SUM(amount) as actual_charges
            FROM charter_charges
            GROUP BY charter_id
        )
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.total_amount_due,
            cs.actual_charges,
            c.booking_status,
            c.cancelled,
            (SELECT json_agg(json_build_object(
                'description', cc.description,
                'amount', cc.amount,
                'charge_type', cc.charge_type
            ))
            FROM charter_charges cc 
            WHERE cc.charter_id = c.charter_id) as charges
        FROM charters c
        INNER JOIN charge_sums cs ON c.charter_id = cs.charter_id
        WHERE ABS(c.total_amount_due - cs.actual_charges) > 0.01
          AND cs.actual_charges > 0
        ORDER BY ABS(c.total_amount_due - cs.actual_charges) DESC
        LIMIT 10
    """)
    
    print(f"\n5. Sample charters with charge mismatches (actual charges exist):")
    for row in cur.fetchall():
        charter_id, reserve, date, total_due, actual, status, cancelled, charges = row
        print(f"\n   Reserve {reserve}:")
        print(f"     Date: {date}")
        print(f"     Total due: ${total_due:,.2f}")
        print(f"     Actual charges: ${actual:,.2f}")
        print(f"     Difference: ${abs(total_due - actual):,.2f}")
        print(f"     Status: {status}, Cancelled: {cancelled}")
        if charges:
            print(f"     Charges: {charges}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    analyze()
