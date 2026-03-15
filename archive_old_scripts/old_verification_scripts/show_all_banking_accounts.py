#!/usr/bin/env python3
"""Show all banking accounts in the system."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    user='postgres',
    password='ArrowLimousine',
    dbname='almsdata'
)
cur = conn.cursor()

print("\n" + "="*100)
print("ALL BANKING ACCOUNTS IN SYSTEM")
print("="*100)

# 1. Chart of Accounts - Banking GL Codes
print("\n1. CHART OF ACCOUNTS - BANKING/CASH GL CODES")
print("-"*100)

cur.execute("""
    SELECT 
        account_code,
        account_name,
        account_type,
        bank_account_number,
        is_active,
        (SELECT COUNT(*) FROM receipts WHERE gl_account_code = coa.account_code) as receipt_count,
        (SELECT SUM(gross_amount) FROM receipts WHERE gl_account_code = coa.account_code) as total_amount
    FROM chart_of_accounts coa
    WHERE (
        account_type IN ('Asset', 'Bank', 'Cash')
        OR account_code LIKE '10%'
        OR account_name ILIKE '%bank%'
        OR account_name ILIKE '%cash%'
        OR account_name ILIKE '%checking%'
        OR account_name ILIKE '%savings%'
        OR account_name ILIKE '%cibc%'
        OR account_name ILIKE '%scotia%'
    )
    AND account_code < '2000'  -- Assets only
    ORDER BY account_code
""")

gl_accounts = cur.fetchall()

print(f"{'GL Code':<10} {'Account Name':<40} {'Bank Acct #':<20} {'Active':<8} {'Receipts':<10} {'Total $'}")
print("-"*100)

for code, name, acct_type, bank_num, active, count, amount in gl_accounts:
    name_display = (name or "NO NAME")[:40]
    bank_display = (bank_num or "")[:20]
    active_str = "Yes" if active else "No"
    amount_str = f"${amount:,.2f}" if amount else "$0.00"
    print(f"{code:<10} {name_display:<40} {bank_display:<20} {active_str:<8} {count:<10} {amount_str}")

# 2. Bank Accounts Table
print("\n" + "="*100)
print("2. BANK_ACCOUNTS TABLE (Physical Bank Accounts)")
print("="*100)

cur.execute("""
    SELECT 
        bank_id,
        account_name,
        institution_name,
        account_number,
        account_type,
        is_active
    FROM bank_accounts
    ORDER BY bank_id
""")

bank_accounts = cur.fetchall()

print(f"{'ID':<6} {'Account Name':<35} {'Bank':<30} {'Account #':<20} {'Type':<12} {'Active'}")
print("-"*100)

for bank_id, acct_name, institution, acct_num, acct_type, active in bank_accounts:
    name_display = (acct_name or "")[:35]
    institution_display = (institution or "")[:30]
    num_display = (acct_num or "")[:20]
    type_display = (acct_type or "")[:12]
    active_str = "Yes" if active else "No"
    print(f"{bank_id:<6} {name_display:<35} {institution_display:<30} {num_display:<20} {type_display:<12} {active_str}")

# 3. Banking Transactions Summary by Bank Account
print("\n" + "="*100)
print("3. BANKING TRANSACTIONS BY BANK ACCOUNT")
print("="*100)

cur.execute("""
    SELECT 
        ba.bank_id,
        ba.account_name,
        ba.account_number,
        COUNT(bt.transaction_id) as transaction_count,
        SUM(CASE WHEN bt.debit_amount > 0 THEN bt.debit_amount ELSE 0 END) as total_debits,
        SUM(CASE WHEN bt.credit_amount > 0 THEN bt.credit_amount ELSE 0 END) as total_credits
    FROM bank_accounts ba
    LEFT JOIN banking_transactions bt ON ba.bank_id = bt.bank_id
    GROUP BY ba.bank_id, ba.account_name, ba.account_number
    ORDER BY ba.bank_id
""")

print(f"{'ID':<6} {'Account Name':<30} {'Account #':<20} {'Transactions':<15} {'Total Debits':<15} {'Total Credits'}")
print("-"*100)

for bank_id, acct_name, acct_num, count, debits, credits in cur.fetchall():
    name_display = (acct_name or "")[:30]
    num_display = (acct_num or "")[:20]
    debits_str = f"${debits:,.2f}" if debits else "$0.00"
    credits_str = f"${credits:,.2f}" if credits else "$0.00"
    print(f"{bank_id:<6} {name_display:<30} {num_display:<20} {count:<15} {debits_str:<15} {credits_str}")

# 4. Mapping: Bank Accounts to GL Codes
print("\n" + "="*100)
print("4. BANK ACCOUNT → GL CODE MAPPING")
print("="*100)

print(f"{'Bank Account #':<20} {'Bank Account Name':<35} {'→ GL Code':<12} {'GL Name'}")
print("-"*100)

# Manual mapping based on setup
mappings = [
    ('0228362', 'CIBC Business Checking', '1011', 'CIBC Checking 0228362'),
    ('903990106011', 'Scotia Bank', '1012', 'Scotia Bank 903990106011'),
    ('3648117', 'CIBC Business Deposit', '1013', 'CIBC Merchant Processing 3648117'),
    ('8314462', 'CIBC Vehicle Loans', 'N/A', 'Liability account'),
    ('74-61615', 'CIBC Business Checking (Legacy)', '1011', 'Same as 0228362'),
    ('N/A', 'Petty Cash', '1015', 'Petty Cash'),
    ('N/A', 'Savings Account', '1020', 'Savings Account'),
]

for bank_num, bank_name, gl_code, gl_name in mappings:
    print(f"{bank_num:<20} {bank_name:<35} {gl_code:<12} {gl_name}")

# 5. Missing GL Codes?
print("\n" + "="*100)
print("5. BANK ACCOUNTS WITHOUT GL CODES")
print("="*100)

cur.execute("""
    SELECT 
        ba.account_number,
        ba.account_name,
        ba.institution_name
    FROM bank_accounts ba
    WHERE NOT EXISTS (
        SELECT 1 
        FROM chart_of_accounts coa 
        WHERE coa.bank_account_number = ba.account_number
    )
    AND ba.is_active = TRUE
    AND ba.account_type != 'loan'
""")

missing = cur.fetchall()
if missing:
    print("These bank accounts need GL codes:")
    for acct_num, acct_name, institution in missing:
        print(f"  - {acct_num}: {acct_name} ({institution})")
else:
    print("✓ All active bank accounts have corresponding GL codes")

print("\n" + "="*100)
print("SUMMARY")
print("="*100)
print(f"""
Banking GL Codes in Chart of Accounts: {len([x for x in gl_accounts if x[4]])}  (active)
Physical Bank Accounts: {len(bank_accounts)}
Banking Transactions: {sum([x[3] for x in cur.execute("SELECT ba.bank_id, ba.account_name, ba.account_number, COUNT(bt.transaction_id) FROM bank_accounts ba LEFT JOIN banking_transactions bt ON ba.bank_id = bt.bank_id GROUP BY ba.bank_id, ba.account_name, ba.account_number").fetchall()])} total

Standard Banking GL Structure:
  1010 - Cash & Bank Accounts (general)
  1011 - CIBC Checking 0228362
  1012 - Scotia Bank 903990106011
  1013 - CIBC Merchant Processing 3648117
  1015 - Petty Cash
  1016 - Driver Float Outstanding
  1018 - Undeposited Funds
  1020 - Savings Account
  1135 - Prepaid Visa Cards
""")

conn.close()
