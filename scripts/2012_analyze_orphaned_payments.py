"""
Analyze 2012 payments without reserve_number.
- Count and sum orphaned payments (reserve_number IS NULL)
- Sample by payment method, notes patterns
- Check if they're banking imports, Square, manual entries, etc.
"""
import os
import psycopg2
from datetime import date

DB = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'dbname': os.getenv('DB_NAME', 'almsdata'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '***REDACTED***'),
}

YEAR = 2012

def main():
    s, e = date(YEAR,1,1), date(YEAR+1,1,1)
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    
    # Count/sum orphaned payments
    cur.execute("""
        SELECT 
            COUNT(*) AS count,
            COALESCE(SUM(amount),0) AS total,
            payment_method,
            COUNT(*) FILTER (WHERE notes LIKE '%LMS%') AS from_lms,
            COUNT(*) FILTER (WHERE notes LIKE '%Square%') AS from_square,
            COUNT(*) FILTER (WHERE notes LIKE '%banking%' OR notes LIKE '%bank%') AS from_banking
        FROM payments
        WHERE payment_date >= %s AND payment_date < %s
          AND reserve_number IS NULL
        GROUP BY payment_method
        ORDER BY COUNT(*) DESC
    """, (s, e))
    
    print(f"=== 2012 Payments WITHOUT reserve_number (Orphaned) ===\n")
    print(f"{'Method':<20} {'Count':>8} {'Total':>12} {'LMS':>6} {'Square':>6} {'Banking':>8}")
    print('-'*70)
    
    total_count = 0
    total_amount = 0
    
    rows = cur.fetchall()
    if not rows:
        print("No orphaned payments found!")
        cur.close()
        conn.close()
        return
    
    for row in rows:
        method = row[2] or 'NULL'
        count = row[0]
        amount = row[1]
        lms = row[3] if len(row) > 3 else 0
        square = row[4] if len(row) > 4 else 0
        banking = row[5] if len(row) > 5 else 0
        
        print(f"{method:<20} {count:>8} ${amount:>10,.2f} {lms:>6} {square:>6} {banking:>8}")
        total_count += count
        total_amount += amount
    
    print('-'*70)
    print(f"{'TOTAL':<20} {total_count:>8} ${total_amount:>10,.2f}")
    
    # Sample 25 orphaned payments
    print(f"\n=== Sample 25 Orphaned Payments ===\n")
    cur.execute("""
        SELECT payment_id, payment_date, amount, payment_method, 
               LEFT(COALESCE(notes,''), 80) AS notes_short
        FROM payments
        WHERE payment_date >= %s AND payment_date < %s
          AND reserve_number IS NULL
        ORDER BY amount DESC
        LIMIT 25
    """, (s, e))
    
    print(f"{'ID':<10} {'Date':<12} {'Amount':>10} {'Method':<15} Notes")
    print('-'*100)
    
    for row in cur.fetchall():
        print(f"{row[0]:<10} {row[1]} ${row[2]:>9,.2f} {(row[3] or 'NULL'):<15} {row[4] or ''}")
    
    # Check if any have charter_id but no reserve_number
    cur.execute("""
        SELECT COUNT(*)
        FROM payments
        WHERE payment_date >= %s AND payment_date < %s
          AND reserve_number IS NULL
          AND charter_id IS NOT NULL
    """, (s, e))
    
    with_charter_id = cur.fetchone()[0]
    print(f"\n[WARN]  Payments with charter_id but NO reserve_number: {with_charter_id}")
    if with_charter_id > 0:
        print("   → These should be fixable by copying reserve_number from charters table")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
