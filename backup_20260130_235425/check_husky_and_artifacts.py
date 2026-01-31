"""
Check Husky transactions - gas station shouldn't have cheques!
Likely QuickBooks import artifacts with Cheque #dd and X
"""
import psycopg2
import os

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password=os.getenv('DB_PASSWORD')
)
cur = conn.cursor()

print("=== ALL HUSKY TRANSACTIONS ===\n")

cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        vendor_extracted,
        debit_amount,
        credit_amount
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND (description ILIKE '%husky%' OR vendor_extracted ILIKE '%husky%')
    ORDER BY transaction_date DESC
""")

results = cur.fetchall()
print(f"Total Husky transactions: {len(results)}\n")

for r in results:
    debit = r[4] if r[4] is not None else 0.0
    credit = r[5] if r[5] is not None else 0.0
    print(f"TX {r[0]} | {r[1]} | Debit: ${debit:>10.2f} | Credit: ${credit:>10.2f}")
    print(f"  Description: {r[2]}")
    print(f"  Vendor: {r[3]}")
    print()

# Check for QuickBooks import patterns
print("\n=== CHECKING FOR QB IMPORT ARTIFACTS ===\n")

cur.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE description LIKE '%Cheque #dd%' OR description LIKE '%Cheque #DD%') as cheque_dd,
        COUNT(*) FILTER (WHERE description LIKE '% X' OR description LIKE '% X %') as ending_x,
        COUNT(*) FILTER (WHERE description LIKE '%[QB:%') as qb_prefix,
        COUNT(*) as total
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND (description ILIKE '%husky%' OR vendor_extracted ILIKE '%husky%')
""")

artifacts = cur.fetchone()
print(f"Husky transactions with artifacts:")
print(f"  - 'Cheque #dd': {artifacts[0]}")
print(f"  - Ending with 'X': {artifacts[1]}")
print(f"  - '[QB:' prefix: {artifacts[2]}")
print(f"  - Total Husky: {artifacts[3]}")

# Look for similar patterns across all vendors
print("\n\n=== CHECKING ALL TRANSACTIONS FOR REMAINING ARTIFACTS ===\n")

cur.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE description LIKE '%Cheque #dd%' OR description LIKE '%Cheque #DD%') as cheque_dd,
        COUNT(*) FILTER (WHERE description LIKE '% X') as ending_x,
        COUNT(*) as total
    FROM banking_transactions
    WHERE account_number = '0228362'
""")

all_artifacts = cur.fetchone()
print(f"ALL CIBC transactions:")
print(f"  - Total transactions: {all_artifacts[2]:,}")
print(f"  - With 'Cheque #dd': {all_artifacts[0]} (SHOULD BE 0)")
print(f"  - Ending with ' X': {all_artifacts[1]} (SHOULD BE 0)")

if all_artifacts[0] > 0 or all_artifacts[1] > 0:
    print("\n⚠️ WARNING: Artifacts still present! Cleanup may not have completed.")
    
    # Show examples
    print("\n=== SAMPLE REMAINING ARTIFACTS ===\n")
    cur.execute("""
        SELECT transaction_id, description, vendor_extracted
        FROM banking_transactions
        WHERE account_number = '0228362'
        AND (description LIKE '%Cheque #dd%' OR description LIKE '%Cheque #DD%' OR description LIKE '% X')
        LIMIT 10
    """)
    
    samples = cur.fetchall()
    for s in samples:
        print(f"TX {s[0]}: {s[1][:70]}")
        print(f"  Vendor: {s[2]}")
        print()

cur.close()
conn.close()
