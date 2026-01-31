#!/usr/bin/env python3
"""Review all GL codes for potential consolidation."""
import psycopg2

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost')
cur = conn.cursor()

# Get all GL codes with receipt counts and totals
cur.execute("""
    SELECT 
        c.account_code,
        c.account_name,
        COUNT(r.receipt_id) as cnt,
        COALESCE(SUM(r.gross_amount), 0) as total
    FROM chart_of_accounts c
    LEFT JOIN receipts r ON r.gl_account_code = c.account_code
    WHERE c.account_code IN ('5400', '5410', '5420', '5650', '6000', '6100', '6101', '6900', '1099', '1135', '5450')
    GROUP BY c.account_code, c.account_name
    ORDER BY c.account_code
""")

print("\n" + "=" * 100)
print("BANKING/FEE GL CODES - CONSOLIDATION ANALYSIS")
print("=" * 100)
print(f"{'Code':8} | {'Account Name':50} | {'Receipts':>8} | {'Total Amount':>15}")
print("-" * 100)

rows = cur.fetchall()
for code, name, cnt, total in rows:
    print(f"{code:8} | {name:50} | {cnt:8,} | ${total:>14,.2f}")

print("\n" + "=" * 100)
print("CONSOLIDATION RECOMMENDATIONS:")
print("=" * 100)

# Analyze duplicates
print("\n1. BANK CHARGES GROUP (could consolidate to 6100):")
print("   - 5400 (?)          — Check if bank-related")
print("   - 5410 (Rent)       — MISLABELED! Should be Bank Service Charges")
print("   - 5420 (?)          — Check if bank-related")
print("   - 5650 (Donations)  — Currently misused for Bank Charges")
print("   - 6100              — Bank Charges & Interest (intended)")
print("   - 6101              — Interest & Late Charges (intended)")
print("   RECOMMENDATION: Create proper 6100 & 6101 mapping; fix 5410 (Rent)")

print("\n2. PAYMENT PROCESSING (5450):")
print("   - 5450 (Equipment)  — MISLABELED! Should be Payment Processing Fees")
print("   RECOMMENDATION: Fix the account name or create new GL code")

print("\n3. PREPAID CARDS (1135):")
print("   - 1135 (Prepaid)    — Correct! Asset account for prepaid Visa loads")

print("\n4. INTER-ACCOUNT TRANSFERS (1099):")
print("   - 1099              — Should be created if not exists (clearing account)")

conn.close()
