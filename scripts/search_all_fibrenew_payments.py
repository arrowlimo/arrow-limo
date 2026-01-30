"""
Search for ALL possible Fibrenew-related payments in banking_transactions
using various pattern variations
"""
import psycopg2

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

# Multiple search patterns to catch variations
patterns = [
    '%fibrenew%',
    '%fibre new%',
    '%fib re new%',
    '%fibre-new%',
    '%fiber new%',
    '%fiber-new%',
    '%fibernew%',
    # Possible payment descriptions
    '%office rent%',
    '%rent payment%',
    # Account/vendor numbers if any
]

with psycopg2.connect(**DB) as cn:
    with cn.cursor() as cur:
        # First, get the currently matched payments
        cur.execute("""
            SELECT transaction_id, transaction_date, description, debit_amount
            FROM banking_transactions
            WHERE debit_amount IS NOT NULL
              AND (
                LOWER(description) LIKE %s
                OR LOWER(description) LIKE %s
                OR LOWER(description) LIKE %s
              )
            ORDER BY transaction_date
        """, ('%fibrenew%', '%fibre new%', '%fib re new%'))
        
        current_matches = cur.fetchall()
        current_ids = {row[0] for row in current_matches}
        
        print(f"\nCURRENTLY MATCHED FIBRENEW PAYMENTS: {len(current_matches)}")
        print("="*100)
        print(f"{'ID':<10} {'Date':<12} {'Amount':>12} {'Description':<60}")
        print("-"*100)
        for row in current_matches[:10]:
            print(f"{row[0]:<10} {row[1]!s:<12} ${row[3]:>10,.2f} {row[2][:60]}")
        if len(current_matches) > 10:
            print(f"... and {len(current_matches) - 10} more")
        
        # Now search for broader patterns that might include office rent payments
        print(f"\n\nSEARCHING FOR POTENTIAL ADDITIONAL MATCHES:")
        print("="*100)
        
        # Look for debits around typical rent amounts
        cur.execute("""
            SELECT transaction_id, transaction_date, description, debit_amount
            FROM banking_transactions
            WHERE debit_amount IS NOT NULL
              AND (
                -- Rent-like amounts
                (debit_amount BETWEEN 600 AND 750)
                OR (debit_amount BETWEEN 250 AND 350)  -- utilities range
                OR (debit_amount BETWEEN 2500 AND 3000)  -- large payments
              )
              AND transaction_date >= '2019-01-01'
              AND LOWER(description) NOT LIKE '%fibrenew%'
              AND LOWER(description) NOT LIKE '%fibre new%'
            ORDER BY transaction_date, debit_amount DESC
        """)
        
        potential = cur.fetchall()
        
        # Filter for anything that looks like office/rent related
        office_keywords = ['office', 'rent', 'lease', 'property', 'commercial', 'space']
        
        print(f"\nPOTENTIAL OFFICE/RENT PAYMENTS (not currently matched):")
        print(f"{'ID':<10} {'Date':<12} {'Amount':>12} {'Description':<60}")
        print("-"*100)
        
        found_potential = 0
        for row in potential[:50]:  # Check first 50
            desc_lower = (row[2] or '').lower()
            
            if any(kw in desc_lower for kw in office_keywords):
                print(f"{row[0]:<10} {row[1]!s:<12} ${row[3]:>10,.2f} {(row[2] or '')[:60]}")
                found_potential += 1
        
        if found_potential == 0:
            print("  (no obvious office/rent payments found)")
        
        # Check for recurring payment patterns
        print(f"\n\nCHECKING RECURRING DEBITS (same amount, multiple times):")
        print("="*100)
        cur.execute("""
            SELECT debit_amount, COUNT(*) as count, 
                   MIN(transaction_date) as first_date,
                   MAX(transaction_date) as last_date,
                   STRING_AGG(DISTINCT SUBSTRING(description, 1, 50), ' | ' ORDER BY SUBSTRING(description, 1, 50)) as sample_descriptions
            FROM banking_transactions
            WHERE debit_amount IS NOT NULL
              AND transaction_date >= '2019-01-01'
              AND LOWER(description) NOT LIKE '%fibrenew%'
              AND LOWER(description) NOT LIKE '%fibre new%'
            GROUP BY debit_amount
            HAVING COUNT(*) >= 5  -- recurring amounts
               AND debit_amount BETWEEN 200 AND 3000
            ORDER BY COUNT(*) DESC
            LIMIT 20
        """)
        
        print(f"{'Amount':>12} {'Count':>8} {'First Date':<12} {'Last Date':<12} {'Sample Descriptions':<50}")
        print("-"*100)
        for row in cur.fetchall():
            print(f"${row[0]:>10,.2f} {row[1]:>8} {row[2]!s:<12} {row[3]!s:<12} {(row[4] or '')[:50]}")

