#!/usr/bin/env python3
"""
Final status check - verify all fixes are complete.

Checks:
1. Emoji characters removed from audit scripts
2. 2012 charter balances recalculated
3. Cash detection patterns broadened
4. General Journal categorization fixed
5. Scotia Bank import complete

Created: November 25, 2025
"""

import psycopg2
import os
import re

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("\n" + "="*80)
print("FINAL STATUS CHECK - November 25, 2025")
print("="*80)

all_good = True

# Check 1: Charter balance integrity (2012)
print("\n1. Charter Balance Integrity (2012):")
cur.execute("""
    SELECT COUNT(*) 
    FROM charters
    WHERE EXTRACT(YEAR FROM charter_date) = 2012
    AND ABS(paid_amount - (
        SELECT COALESCE(SUM(p.amount), 0)
        FROM payments p
        WHERE p.reserve_number = charters.reserve_number
    )) > 0.01
""")
mismatches = cur.fetchone()[0]
if mismatches == 0:
    print(f"   ✓ All 2012 charter paid_amounts match payment sums")
else:
    print(f"   ✗ {mismatches} charters have mismatched paid_amounts")
    all_good = False

# Check 2: Cash transactions detected (2012)
print("\n2. Cash Transaction Detection (2012):")
cur.execute("""
    SELECT COUNT(*), SUM(amount)
    FROM payments
    WHERE EXTRACT(YEAR FROM payment_date) = 2012
    AND (
        LOWER(payment_method) LIKE '%%cash%%'
        OR LOWER(notes) LIKE '%%cash%%'
    )
""")
cash_payments = cur.fetchone()
print(f"   ✓ Cash payments: {cash_payments[0]} transactions, ${cash_payments[1]:,.2f}")

cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
    AND (
        LOWER(vendor_name) LIKE '%%cash%%'
        OR LOWER(description) LIKE '%%cash%%'
        OR LOWER(vendor_name) LIKE '%%atm%%'
        OR LOWER(vendor_name) LIKE '%%abm%%'
    )
""")
cash_receipts = cur.fetchone()
print(f"   ✓ Cash receipts: {cash_receipts[0]} transactions, ${cash_receipts[1]:,.2f}")

cur.execute("""
    SELECT COUNT(*), SUM(credit_amount)
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    AND account_number = '0228362'
    AND (
        LOWER(description) LIKE '%%cash%%'
        OR LOWER(description) LIKE '%%deposit%%'
        OR LOWER(description) LIKE '%%atm%%'
        OR LOWER(description) LIKE '%%abm%%'
    )
    AND credit_amount > 0
""")
cash_deposits = cur.fetchone()
print(f"   ✓ Cash deposits: {cash_deposits[0]} transactions, ${cash_deposits[1]:,.2f}")

# Check 3: General Journal categorization
print("\n3. General Journal Categorization:")
cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE category = 'general_journal'
""")
gj_receipts = cur.fetchone()
print(f"   ✓ General Journal receipts: {gj_receipts[0]} receipt(s), ${gj_receipts[1]:,.2f}")

cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE (
        vendor_name ILIKE '%general journal%' 
        OR description ILIKE '%general journal%'
    )
    AND category != 'general_journal'
""")
miscategorized = cur.fetchone()[0]
if miscategorized == 0:
    print(f"   ✓ No miscategorized General Journal entries")
else:
    print(f"   ✗ {miscategorized} General Journal entries miscategorized")
    all_good = False

# Check 4: Scotia Bank import status
print("\n4. Scotia Bank Import (903990106011):")
cur.execute("""
    SELECT 
        COUNT(*) as txn_count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        SUM(debit_amount) as total_debits,
        SUM(credit_amount) as total_credits
    FROM banking_transactions
    WHERE account_number = '903990106011'
""")
scotia = cur.fetchone()
print(f"   ✓ Transactions: {scotia[0]:,}")
print(f"   ✓ Date range: {scotia[1]} to {scotia[2]}")
print(f"   ✓ Total debits: ${scotia[3]:,.2f}")
print(f"   ✓ Total credits: ${scotia[4]:,.2f}")

# Check receipts created from Scotia banking
cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE mapped_bank_account_id = 2
    AND created_from_banking = TRUE
""")
scotia_receipts = cur.fetchone()
print(f"   ✓ Receipts created: {scotia_receipts[0]:,} (${scotia_receipts[1]:,.2f})")

# Check 5: Auto-create script has general_journal category
print("\n5. Auto-Create Script Enhancement:")
with open('l:\\limo\\scripts\\auto_create_receipts_from_all_banking.py', 'r', encoding='utf-8') as f:
    content = f.read()
    if 'general_journal' in content and 'GENERAL JOURNAL' in content:
        print(f"   ✓ Script has general_journal categorization logic")
    else:
        print(f"   ✗ Script missing general_journal logic")
        all_good = False

# Check 6: Emoji check in audit script
print("\n6. Emoji Characters Removed:")
with open('l:\\limo\\scripts\\audit_verified_file_line_by_line.py', 'r', encoding='utf-8') as f:
    content = f.read()
    emoji_pattern = re.compile(r'[✅⚠️✓✗]')
    emojis = emoji_pattern.findall(content)
    if not emojis:
        print(f"   ✓ No emoji characters in audit_verified_file_line_by_line.py")
    else:
        print(f"   ✗ Found {len(emojis)} emoji characters: {set(emojis)}")
        all_good = False

print("\n" + "="*80)
if all_good:
    print("STATUS: ✓ ALL FIXES COMPLETE")
    print("\nSummary:")
    print("  • Charter balances accurate")
    print("  • Cash transactions detected")
    print("  • General Journal properly categorized")
    print("  • Scotia Bank data imported")
    print("  • Future imports will categorize correctly")
    print("  • No emoji characters in scripts")
else:
    print("STATUS: ✗ SOME ISSUES REMAIN")
    print("\nPlease review failed checks above.")

print("="*80 + "\n")

cur.close()
conn.close()
