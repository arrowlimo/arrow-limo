#!/usr/bin/env python3
"""
Create journal entry to update GL 2020 (Notes Payable - David) with
recurring payment reimbursements from 2014-2025.
"""
import os, psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***'),
)
cur = conn.cursor()

print("\n" + "="*70)
print("CREATING JOURNAL ENTRY FOR DAVID REIMBURSEMENT")
print("="*70 + "\n")

# Get David-paid totals by vendor
cur.execute("""
    SELECT 
        CASE 
            WHEN vendor_name ILIKE 'godaddy%' THEN 'GoDaddy'
            WHEN vendor_name ILIKE 'wix%' THEN 'Wix'
            WHEN vendor_name ILIKE 'ionos%' THEN 'IONOS'
        END as vendor,
        COUNT(*) as count,
        SUM(gross_amount) as amount,
        MIN(receipt_date) as earliest,
        MAX(receipt_date) as latest
    FROM receipts
    WHERE description ILIKE '%David paid%'
    AND (vendor_name ILIKE 'godaddy%' OR vendor_name ILIKE 'wix%' OR vendor_name ILIKE 'ionos%')
    GROUP BY vendor
    ORDER BY vendor
""")

vendors = cur.fetchall()
total_amount = sum(v[2] for v in vendors)

print("David-Paid Breakdown:")
print("-"*70)
for vendor, count, amount, earliest, latest in vendors:
    print(f"{vendor:<10}: {count:>3} receipts × ${amount:>9,.2f}  ({earliest} to {latest})")
print("-"*70)
print(f"TOTAL: ${total_amount:,.2f}\n")

# Create journal entry description
description = f"Web hosting & domain services 2014-2025 (GoDaddy, Wix, IONOS) - David reimbursement"

# Transaction date (today)
txn_date = datetime.now().date()

print("Creating journal entries...")
print("-"*70)

# Debit GL 5450 (Marketing/Web Services) - increase expense
# Note: journal table uses capitalized column names (Date, Account, Debit, Credit, etc.)
# Don't insert journal_id - let it auto-generate if it has a sequence
cur.execute("""
    SELECT COALESCE(MAX(journal_id), 0) + 1 FROM journal
""")
next_id = cur.fetchone()[0]

cur.execute("""
    INSERT INTO journal (
        journal_id, "Date", "Account", "Name", "Memo/Description", "Debit", "Credit"
    ) VALUES (
        %s, %s, '5450', 'Marketing - Web Services', %s, %s, NULL
    )
""", (next_id, txn_date, description, total_amount))

print(f"✅ DR GL 5450 Marketing - Web Services: ${total_amount:,.2f} (journal id: {next_id})")

# Credit GL 2020 (Notes Payable - David) - increase liability
next_id += 1
cur.execute("""
    INSERT INTO journal (
        journal_id, "Date", "Account", "Name", "Memo/Description", "Debit", "Credit"
    ) VALUES (
        %s, %s, '2020', 'Notes Payable - David', %s, NULL, %s
    )
""", (next_id, txn_date, description, total_amount))

print(f"✅ CR GL 2020 Notes Payable - David: ${total_amount:,.2f} (journal id: {next_id})")

# Also add to unified_general_ledger
cur.execute("""
    INSERT INTO unified_general_ledger (
        transaction_date, account_code, account_name, description,
        debit_amount, credit_amount, source_system, source_transaction_id
    ) VALUES 
    (%s, '5450', 'Marketing - Web Services', %s, %s, NULL, 'manual_adjustment', 'david_reimburse_hosting_2014_2025'),
    (%s, '2020', 'Notes Payable - David', %s, NULL, %s, 'manual_adjustment', 'david_reimburse_hosting_2014_2025')
""", (txn_date, description, total_amount, txn_date, description, total_amount))

print(f"✅ Entries added to unified_general_ledger")

conn.commit()

# Verify GL 2020 balance
cur.execute("""
    SELECT 
        COALESCE(SUM("Credit"), 0) - COALESCE(SUM("Debit"), 0) as balance
    FROM journal
    WHERE "Account" = '2020'
""")
gl_2020_balance = cur.fetchone()[0]

print("\n" + "="*70)
print(f"✅ JOURNAL ENTRY CREATED SUCCESSFULLY")
print(f"   Date: {txn_date}")
print(f"   Amount: ${total_amount:,.2f}")
print(f"   GL 2020 Current Balance: ${gl_2020_balance:,.2f}")
print("="*70 + "\n")

cur.close()
conn.close()
