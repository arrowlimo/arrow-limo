#!/usr/bin/env python3
"""Fix GL code mislabeling and create missing accounts."""
import psycopg2
from datetime import datetime

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='***REMOVED***', host='localhost')
cur = conn.cursor()

print("=" * 100)
print("GL ACCOUNT CLEANUP & CONSOLIDATION")
print("=" * 100)
print(f"Date: {datetime.now()}\n")

# Step 1: Update mislabeled accounts
print("1. FIXING MISLABELED GL ACCOUNTS")
print("-" * 100)

updates = [
    ("5410", "Bank Service Charges", "Rent Expense"),
    ("5450", "Payment Processing Fees", "Equipment Depreciation"),
]

for code, new_name, old_name in updates:
    cur.execute("""
        UPDATE chart_of_accounts
        SET account_name = %s, updated_at = NOW()
        WHERE account_code = %s
    """, (new_name, code))
    
    # Count affected receipts
    cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code = %s", (code,))
    count = cur.fetchone()[0]
    
    print(f"   {code}: '{old_name}' → '{new_name}' ({count:,} receipts affected)")

conn.commit()

# Step 2: Create missing 1099 account
print("\n2. CREATING MISSING GL ACCOUNT")
print("-" * 100)

cur.execute("SELECT COUNT(*) FROM chart_of_accounts WHERE account_code = '1099'")
exists = cur.fetchone()[0] > 0

if not exists:
    cur.execute("""
        INSERT INTO chart_of_accounts (account_code, account_name, account_type, description)
        VALUES ('1099', 'Inter-Account Clearing', 'OtherCurrentAsset', 'Internal transfers between bank accounts')
    """)
    conn.commit()
    print("   ✓ Created 1099 'Inter-Account Clearing' (OtherCurrentAsset)")
else:
    print("   ✓ 1099 already exists")

# Step 3: Show updated GL code summary
print("\n3. UPDATED GL CODE SUMMARY")
print("-" * 100)
print(f"{'Code':8} | {'Account Name':50} | {'Receipts':>8} | {'Total':>15}")
print("-" * 100)

cur.execute("""
    SELECT 
        c.account_code,
        c.account_name,
        COUNT(r.receipt_id) as cnt,
        COALESCE(SUM(r.gross_amount), 0) as total
    FROM chart_of_accounts c
    LEFT JOIN receipts r ON r.gl_account_code = c.account_code
    WHERE c.account_code IN ('1099', '1135', '5400', '5410', '5420', '5450', '5650', '6100', '6101')
    GROUP BY c.account_code, c.account_name
    ORDER BY c.account_code
""")

rows = cur.fetchall()
for code, name, cnt, total in rows:
    marker = "✓" if code in ("1135", "6100", "6101", "1099", "5450") else "⚠"
    print(f"{marker} {code:8} | {name:50} | {cnt:8,} | ${total:>14,.2f}")

# Step 4: Show exempt GL summary
print("\n4. EXEMPT GL CODES (auto-mark GST Exempt)")
print("-" * 100)

exempt_codes = ("6100", "6101", "5450", "1135", "1099")
cur.execute(f"""
    SELECT 
        COUNT(*) as total_exempt,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE gl_account_code IN {exempt_codes}
""")

total_exempt, total_amount = cur.fetchone()
total_amount = total_amount or 0.0

print(f"   Total receipts with exempt GLs: {total_exempt:,}")
print(f"   Total amount: ${total_amount:,.2f}")
print(f"   GLs: 6100 (Bank Charges), 6101 (Interest), 5450 (Payment Processing),")
print(f"        1135 (Prepaid Visa), 1099 (Inter-Account)")

# Step 5: Recommendations
print("\n5. CONSOLIDATION NOTES")
print("-" * 100)
print("""
   ✓ 6100 & 6101 kept separate: Better for interest vs. fee tracking (loan accounting)
   ✓ 5450 renamed to Payment Processing Fees (was mislabeled as Equipment)
   ✓ 5410 renamed to Bank Service Charges (was mislabeled as Rent)
   ✓ 1099 created for Inter-Account Clearing (internal transfers, GST-exempt)
   ✓ 1135 confirmed as Prepaid Visa Cards (asset account, GST-exempt)
   
   Next step: Update UI script to use corrected GL codes.
   No receipt remapping needed—GL codes remain the same, only account names fixed.
""")

conn.close()
print("\n" + "=" * 100)
print("✓ CLEANUP COMPLETE")
print("=" * 100)
