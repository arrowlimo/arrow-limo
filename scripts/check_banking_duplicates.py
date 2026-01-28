"""
Check for duplicate banking transactions (Husky and all vendors)
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

print("=== HUSKY DUPLICATE ANALYSIS ===\n")

# Check Husky duplicates
cur.execute("""
    SELECT 
        transaction_date,
        description,
        debit_amount,
        COUNT(*) as count,
        ARRAY_AGG(transaction_id ORDER BY transaction_id) as ids
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND (description ILIKE '%husky%' OR vendor_extracted ILIKE '%husky%')
    GROUP BY transaction_date, description, debit_amount
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC, debit_amount DESC
""")

husky_dups = cur.fetchall()
print(f"Husky duplicate groups: {len(husky_dups)}\n")

if husky_dups:
    for d in husky_dups:
        print(f"Date: {d[0]} | Amount: ${d[2]:,.2f} | Count: {d[3]} duplicates")
        print(f"Description: {d[1]}")
        print(f"Transaction IDs: {d[4]}")
        print()
else:
    print("✓ No Husky duplicates found\n")

# Check the specific suspicious entries (TX 60359, 60360 - both $83.82 on same date)
print("\n=== CHECKING SUSPICIOUS SAME-DAY ENTRIES ===\n")

cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        vendor_extracted,
        debit_amount,
        credit_amount
    FROM banking_transactions
    WHERE transaction_id IN (60359, 60360)
    ORDER BY transaction_id
""")

suspicious = cur.fetchall()
for s in suspicious:
    print(f"TX {s[0]} | {s[1]} | Debit: ${s[4] or 0:,.2f}")
    print(f"  Description: {s[2]}")
    print(f"  Vendor: {s[3]}")
    print()

# Also check TX 60206 and 60207 (both $113.53 on 2012-05-05)
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        vendor_extracted,
        debit_amount
    FROM banking_transactions
    WHERE transaction_id IN (60206, 60207)
    ORDER BY transaction_id
""")

more_suspicious = cur.fetchall()
if more_suspicious:
    print("\n=== MORE SUSPICIOUS ENTRIES (TX 60206, 60207) ===\n")
    for s in more_suspicious:
        print(f"TX {s[0]} | {s[1]} | Debit: ${s[4] or 0:,.2f}")
        print(f"  Description: {s[2]}")
        print(f"  Vendor: {s[3]}")
        print()

# Global duplicate check across ALL vendors
print("\n=== ALL CIBC DUPLICATES (Same Date + Description + Amount) ===\n")

cur.execute("""
    SELECT 
        COUNT(*) as duplicate_groups,
        SUM(count - 1) as extra_duplicates
    FROM (
        SELECT COUNT(*) as count
        FROM banking_transactions
        WHERE account_number = '0228362'
        GROUP BY transaction_date, description, debit_amount, credit_amount
        HAVING COUNT(*) > 1
    ) subq
""")

all_dups = cur.fetchone()
print(f"Total duplicate groups: {all_dups[0] or 0}")
print(f"Extra duplicate transactions: {all_dups[1] or 0}")

if all_dups[0] and all_dups[0] > 0:
    print("\n⚠️ WARNING: Duplicates found in banking transactions!")
    
    # Show top duplicates
    cur.execute("""
        SELECT 
            transaction_date,
            description,
            debit_amount,
            COUNT(*) as count,
            ARRAY_AGG(transaction_id ORDER BY transaction_id) as ids
        FROM banking_transactions
        WHERE account_number = '0228362'
        GROUP BY transaction_date, description, debit_amount
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, debit_amount DESC
        LIMIT 15
    """)
    
    top_dups = cur.fetchall()
    print("\n=== TOP 15 DUPLICATE GROUPS ===\n")
    for d in top_dups:
        amount = d[2] if d[2] is not None else 0.0
        print(f"Date: {d[0]} | Amount: ${amount:,.2f} | Count: {d[3]}")
        print(f"Description: {d[1][:70]}")
        print(f"IDs: {d[4]}")
        print()
else:
    print("\n✓ No duplicates found!")

cur.close()
conn.close()
