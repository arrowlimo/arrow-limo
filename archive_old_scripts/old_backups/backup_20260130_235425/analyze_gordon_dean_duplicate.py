"""
Analyze the Gordon, Dean duplicate payment issue (Charter 004420).
LMS shows $220.50 paid, PostgreSQL shows $441.00 paid ($220.50 overpaid).
Then check for similar duplicate patterns across all charters.
"""
import psycopg2

def analyze_gordon_dean():
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("GORDON, DEAN DUPLICATE ANALYSIS - Charter 004420")
    print("=" * 80)
    
    # Get charter details
    cur.execute("""
        SELECT charter_id, reserve_number, account_number, charter_date,
               total_amount_due, paid_amount, balance
        FROM charters
        WHERE reserve_number = '004420'
    """)
    
    charter = cur.fetchone()
    if charter:
        print(f"\nCharter Details:")
        print(f"  Charter ID: {charter[0]}")
        print(f"  Reserve Number: {charter[1]}")
        print(f"  Account Number: {charter[2]}")
        print(f"  Date: {charter[3]}")
        print(f"  Total Due: ${charter[4]:,.2f}")
        print(f"  Paid Amount: ${charter[5]:,.2f}")
        print(f"  Balance: ${charter[6]:,.2f}")
        print(f"\n  [WARN] OVERPAID by ${abs(charter[6]):,.2f}")
    
    # Get all payments for this charter
    cur.execute("""
        SELECT payment_id, reserve_number, account_number, amount, 
               payment_date, payment_method, payment_key, 
               created_at, notes
        FROM payments
        WHERE reserve_number = '004420'
        ORDER BY payment_date, created_at
    """)
    
    payments = cur.fetchall()
    print(f"\n\nPayments for Charter 004420 ({len(payments)} records):")
    print("-" * 80)
    
    total_paid = 0
    for p in payments:
        print(f"\nPayment ID: {p[0]}")
        print(f"  Amount: ${p[3]:,.2f}")
        print(f"  Date: {p[4]}")
        print(f"  Method: {p[5]}")
        print(f"  Key: {p[6]}")
        print(f"  Created: {p[7]}")
        if p[8]:
            print(f"  Notes: {p[8]}")
        total_paid += p[3]
    
    print(f"\n  TOTAL PAYMENTS: ${total_paid:,.2f}")
    print(f"  LMS shows: $220.50 (1 payment)")
    print(f"  PostgreSQL shows: ${total_paid:,.2f} ({len(payments)} payments)")
    print(f"  Duplicate amount: ${float(total_paid) - 220.50:,.2f}")
    
    # Identify potential duplicates
    if len(payments) > 1:
        print(f"\n\n🔍 Duplicate Detection:")
        print("-" * 80)
        
        # Group by amount and date
        amount_groups = {}
        for p in payments:
            key = (p[3], p[4])  # (amount, date)
            if key not in amount_groups:
                amount_groups[key] = []
            amount_groups[key].append(p)
        
        for (amount, date), group in amount_groups.items():
            if len(group) > 1:
                print(f"\n[WARN] {len(group)} payments with same amount ${amount:,.2f} on {date}:")
                for p in group:
                    print(f"    Payment ID: {p[0]}, Key: {p[6]}, Created: {p[7]}")
    
    print("\n\n" + "=" * 80)
    print("CHECKING FOR SIMILAR OVERPAYMENT PATTERNS ACROSS ALL CHARTERS")
    print("=" * 80)
    
    # Find all charters with exactly double payments
    cur.execute("""
        WITH payment_totals AS (
            SELECT 
                c.charter_id,
                c.reserve_number,
                c.account_number,
                c.total_amount_due,
                c.paid_amount,
                c.balance,
                COALESCE(SUM(p.amount), 0) as actual_paid_sum,
                COUNT(p.payment_id) as payment_count
            FROM charters c
            LEFT JOIN payments p ON p.reserve_number = c.reserve_number
            WHERE c.total_amount_due > 0
            GROUP BY c.charter_id, c.reserve_number, c.account_number, 
                     c.total_amount_due, c.paid_amount, c.balance
        )
        SELECT 
            charter_id,
            reserve_number,
            account_number,
            total_amount_due,
            paid_amount,
            actual_paid_sum,
            balance,
            payment_count,
            ROUND((paid_amount / NULLIF(total_amount_due, 0))::numeric, 2) as payment_ratio
        FROM payment_totals
        WHERE paid_amount > total_amount_due * 1.1  -- More than 10% overpaid
        AND payment_count > 1  -- Multiple payments
        ORDER BY (paid_amount - total_amount_due) DESC
        LIMIT 50
    """)
    
    overpaid = cur.fetchall()
    
    if overpaid:
        print(f"\n✓ Found {len(overpaid)} charters overpaid by >10%:")
        print("\nTop overpayment cases:")
        print("-" * 80)
        
        for row in overpaid:
            overpaid_amount = row[4] - row[3]
            print(f"\nReserve: {row[1]}, Account: {row[2]}")
            print(f"  Total Due: ${row[3]:,.2f}")
            print(f"  Paid Amount: ${row[4]:,.2f}")
            print(f"  Balance: ${row[6]:,.2f}")
            print(f"  Payment Count: {row[7]}")
            print(f"  Payment Ratio: {row[8]}x")
            print(f"  [WARN] OVERPAID by ${overpaid_amount:,.2f}")
    else:
        print("\n✓ No other significant overpayment cases found")
    
    # Check for exact 2x duplicates (paid exactly double)
    print("\n\n" + "=" * 80)
    print("CHECKING FOR EXACT 2X DUPLICATE PATTERNS")
    print("=" * 80)
    
    cur.execute("""
        WITH payment_totals AS (
            SELECT 
                c.charter_id,
                c.reserve_number,
                c.account_number,
                c.total_amount_due,
                c.paid_amount,
                c.balance,
                COUNT(p.payment_id) as payment_count
            FROM charters c
            LEFT JOIN payments p ON p.reserve_number = c.reserve_number
            WHERE c.total_amount_due > 0
            GROUP BY c.charter_id, c.reserve_number, c.account_number, 
                     c.total_amount_due, c.paid_amount, c.balance
        )
        SELECT 
            charter_id,
            reserve_number,
            account_number,
            total_amount_due,
            paid_amount,
            balance,
            payment_count,
            ROUND((paid_amount / NULLIF(total_amount_due, 0))::numeric, 2) as ratio
        FROM payment_totals
        WHERE ABS(paid_amount - (total_amount_due * 2)) < 1.0  -- Paid exactly 2x (within $1)
        AND payment_count >= 2
        ORDER BY total_amount_due DESC
    """)
    
    exact_doubles = cur.fetchall()
    
    if exact_doubles:
        print(f"\n[WARN] Found {len(exact_doubles)} charters with EXACT 2X payment (likely duplicates):")
        print("-" * 80)
        
        for row in exact_doubles:
            print(f"\nReserve: {row[1]}, Account: {row[2]}")
            print(f"  Total Due: ${row[3]:,.2f}")
            print(f"  Paid Amount: ${row[4]:,.2f} (exactly {row[7]}x)")
            print(f"  Balance: ${row[5]:,.2f}")
            print(f"  Payment Count: {row[6]}")
            
            # Get payment details for this charter
            cur.execute("""
                SELECT payment_id, amount, payment_date, payment_key, 
                       created_at, payment_method
                FROM payments
                WHERE reserve_number = %s
                ORDER BY payment_date, created_at
            """, (row[1],))
            
            pmts = cur.fetchall()
            print(f"  Payments:")
            for p in pmts:
                print(f"    ID {p[0]}: ${p[1]:,.2f} on {p[2]} (Key: {p[3]}, Created: {p[4]})")
    else:
        print("\n✓ No exact 2x duplicate patterns found")
    
    # Summary statistics
    print("\n\n" + "=" * 80)
    print("OVERPAYMENT SUMMARY STATISTICS")
    print("=" * 80)
    
    cur.execute("""
        WITH payment_totals AS (
            SELECT 
                c.charter_id,
                c.reserve_number,
                c.total_amount_due,
                c.paid_amount,
                c.balance
            FROM charters c
            WHERE c.total_amount_due > 0
        )
        SELECT 
            COUNT(*) as total_charters,
            SUM(CASE WHEN paid_amount > total_amount_due THEN 1 ELSE 0 END) as overpaid_count,
            SUM(CASE WHEN paid_amount > total_amount_due * 1.5 THEN 1 ELSE 0 END) as overpaid_50pct,
            SUM(CASE WHEN paid_amount > total_amount_due * 1.9 AND paid_amount < total_amount_due * 2.1 THEN 1 ELSE 0 END) as approx_double,
            SUM(CASE WHEN balance < 0 THEN ABS(balance) ELSE 0 END) as total_overpayment_amount
        FROM payment_totals
    """)
    
    stats = cur.fetchone()
    if stats:
        print(f"\nTotal charters with amount_due > 0: {stats[0]:,}")
        print(f"Overpaid charters: {stats[1]:,} ({stats[1]/stats[0]*100:.1f}%)")
        print(f"Overpaid by >50%: {stats[2]:,} ({stats[2]/stats[0]*100:.1f}%)")
        print(f"Approximately doubled (1.9x-2.1x): {stats[3]:,}")
        print(f"Total overpayment amount: ${stats[4]:,.2f}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    analyze_gordon_dean()
