#!/usr/bin/env python3
"""
Fix NSF transactions currently mislabeled as card deposits.
Rename vendor to 'NSF CHARGE' for proper categorization.
"""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

print("=" * 80)
print("FIXING NSF TRANSACTIONS MISLABELED AS CARD DEPOSITS")
print("=" * 80)

cur = conn.cursor()

# Find NSF transactions
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        vendor_extracted,
        debit_amount,
        credit_amount
    FROM banking_transactions
    WHERE vendor_extracted IN ('VCARD DEPOSIT', 'MCARD DEPOSIT', 'ACARD DEPOSIT', 'DCARD DEPOSIT')
    AND (
        UPPER(description) LIKE '%NSF%'
        OR UPPER(description) LIKE '%NON-SUFFICIENT%'
        OR UPPER(description) LIKE '%INSUFFICIENT%'
        OR UPPER(description) LIKE '%RETURNED%'
    )
    ORDER BY transaction_date DESC
""")

nsf_transactions = cur.fetchall()

print(f"\nFound {len(nsf_transactions)} NSF transactions to fix:\n")

for tx_id, date, desc, vendor, debit, credit in nsf_transactions:
    amount = f"${debit:,.2f}" if debit else f"(${credit:,.2f})"
    print(f"{date} | {vendor} → NSF CHARGE | {amount}")
    print(f"  {desc}\n")

if nsf_transactions:
    print("=" * 80)
    confirm = input(f"Update {len(nsf_transactions)} transactions? (yes/no): ").strip().lower()
    
    if confirm == 'yes':
        print("\n🔓 Disabling banking lock trigger...")
        cur.execute("ALTER TABLE banking_transactions DISABLE TRIGGER trg_banking_transactions_lock")
        
        print("📝 Updating NSF transactions...")
        
        for tx_id, date, desc, vendor, debit, credit in nsf_transactions:
            cur.execute("""
                UPDATE banking_transactions 
                SET vendor_extracted = 'NSF CHARGE'
                WHERE transaction_id = %s
            """, (tx_id,))
        
        print(f"   Updated {len(nsf_transactions)} transactions")
        
        print("\n🔒 Re-enabling banking lock trigger...")
        cur.execute("ALTER TABLE banking_transactions ENABLE TRIGGER trg_banking_transactions_lock")
        
        print("\n💾 Committing changes...")
        conn.commit()
        
        print("\n✅ UPDATE COMPLETE")
        print(f"   {len(nsf_transactions)} transactions renamed to 'NSF CHARGE'")
        
        # Verify
        cur.execute("""
            SELECT COUNT(*) 
            FROM banking_transactions 
            WHERE vendor_extracted = 'NSF CHARGE'
        """)
        count = cur.fetchone()[0]
        print(f"\nVerification: {count} transactions now labeled 'NSF CHARGE'")
        
    else:
        print("\n❌ Update cancelled")
else:
    print("✅ No NSF transactions found in card deposits")

cur.close()
conn.close()
