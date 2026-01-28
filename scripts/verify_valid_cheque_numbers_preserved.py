"""
Verify that legitimate cheque transactions with valid cheque numbers and vendor names
were properly preserved during cleanup
"""
import psycopg2
import os
import re

# Connect to database
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD')
)
cur = conn.cursor()

print("=== Verification: Valid Cheque Numbers Preserved ===\n")

# Pattern 1: Cheque with actual number (e.g., "Cheque #123", "Cheque 456")
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        vendor_extracted,
        debit_amount
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND description ~* 'cheque\\s*#?\\d+'
    ORDER BY transaction_date DESC
    LIMIT 20
""")
numbered_cheques = cur.fetchall()

print(f"Cheques with actual numbers found: {len(numbered_cheques)}")
print("\nSample of preserved cheque transactions:")
print("-" * 100)
for row in numbered_cheques[:10]:
    amount = row[4] if row[4] is not None else 0.0
    print(f"TX {row[0]} | {row[1]} | ${amount:>10.2f} | {row[2][:50]:<50} | Vendor: {row[3] or 'N/A'}")

# Pattern 2: All cheque transactions to see full pattern
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN vendor_extracted IS NOT NULL AND vendor_extracted != '' THEN 1 END) as with_vendor,
        COUNT(CASE WHEN description ~* 'cheque\\s*#?\\d+' THEN 1 END) as with_number,
        COUNT(CASE WHEN description ~ '^Cheque\\s+[A-Za-z]' THEN 1 END) as name_only
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND description ILIKE 'Cheque%'
""")
summary = cur.fetchone()

print(f"\n\n=== Cheque Transaction Summary ===")
print(f"Total cheque transactions: {summary[0]}")
print(f"  - With vendor extracted: {summary[1]} ({summary[1]/summary[0]*100:.1f}%)")
print(f"  - With cheque numbers: {summary[2]} ({summary[2]/summary[0]*100:.1f}%)")
print(f"  - Name/vendor only (no #): {summary[3]} ({summary[3]/summary[0]*100:.1f}%)")

# Pattern 3: Check specific examples with vendor names
cur.execute("""
    SELECT 
        transaction_id,
        description,
        vendor_extracted,
        debit_amount
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND description ILIKE 'Cheque%'
    AND vendor_extracted IS NOT NULL
    ORDER BY debit_amount DESC
    LIMIT 15
""")
vendor_examples = cur.fetchall()

print(f"\n\n=== Top 15 Cheques by Amount (with vendor names) ===")
print("-" * 100)
for row in vendor_examples:
    amount = row[3] if row[3] is not None else 0.0
    print(f"TX {row[0]} | ${amount:>10.2f} | {row[1][:60]:<60} | Vendor: {row[2]}")

# Pattern 4: Check for specific vendor patterns (Heffner, Fibrenew, etc.)
cur.execute("""
    SELECT 
        vendor_extracted,
        COUNT(*) as count,
        SUM(debit_amount) as total_amount
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND description ILIKE 'Cheque%'
    AND vendor_extracted IS NOT NULL
    GROUP BY vendor_extracted
    HAVING COUNT(*) >= 3
    ORDER BY COUNT(*) DESC
    LIMIT 10
""")
vendor_groups = cur.fetchall()

print(f"\n\n=== Most Common Cheque Vendors ===")
print("-" * 70)
for row in vendor_groups:
    print(f"{row[0]:<40} | Count: {row[1]:>4} | Total: ${row[2]:>12,.2f}")

# Pattern 5: Verify no data loss - check specific high-value examples
print(f"\n\n=== Sample High-Value Cheques (Verification) ===")
print("-" * 100)

test_cases = [
    ("Fibrenew", "Cheque #276 Fibrenew"),
    ("Heffner", "Cheque #222 Heffner"),
    ("Paul", "Cheque #Tsf Paul Richard"),
]

for vendor_keyword, expected_pattern in test_cases:
    cur.execute("""
        SELECT transaction_id, description, vendor_extracted, debit_amount
        FROM banking_transactions
        WHERE account_number = '0228362'
        AND description ILIKE %s
        LIMIT 3
    """, (f"%{vendor_keyword}%",))
    
    results = cur.fetchall()
    if results:
        print(f"\n✓ {vendor_keyword} cheques preserved:")
        for row in results:
            amount = row[3] if row[3] is not None else 0.0
            print(f"  TX {row[0]} | ${amount:>10.2f} | {row[1][:60]} | Vendor: {row[2] or 'N/A'}")
    else:
        print(f"\n✗ WARNING: No {vendor_keyword} cheques found!")

cur.close()
conn.close()

print("\n\n=== VERIFICATION COMPLETE ===")
print("✓ Valid cheque numbers and vendor names should be preserved above")
print("✓ Check that high-value transactions (Heffner, Fibrenew, etc.) are intact")
print("✓ Vendor extraction should be populated for most cheque transactions")
