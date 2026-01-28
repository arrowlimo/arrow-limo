"""
Match bank transfers from CIBC 8362 to destination accounts (1615 or Scotia)
"""
import psycopg2
from datetime import timedelta

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 120)
print("MATCHING BANK TRANSFERS TO DESTINATION ACCOUNTS")
print("=" * 120)

# Get all bank transfer debits from CIBC 8362
cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        bt.description,
        bt.debit_amount,
        r.receipt_id
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.bank_id = 1
    AND bt.source_file = '2014-2017 CIBC 8362.xlsx'
    AND UPPER(bt.description) LIKE '%BANK TRANSFER%'
    AND bt.debit_amount IS NOT NULL
    ORDER BY bt.transaction_date
""")

debit_transfers = cur.fetchall()

print(f"\n📊 Found {len(debit_transfers)} bank transfer debits (money out from CIBC 8362)\n")

# Try to match to credits in 1615 or Scotia accounts
matches_1615 = []
matches_scotia = []
unmatched = []

for txn_id, txn_date, desc, amount, receipt_id in debit_transfers:
    # Check for matching credit in 1615 (within 3 days)
    cur.execute("""
        SELECT transaction_id, transaction_date, credit_amount
        FROM banking_transactions
        WHERE account_number = '1615'
        AND credit_amount BETWEEN %s - 0.01 AND %s + 0.01
        AND transaction_date BETWEEN %s - INTERVAL '3 days' AND %s + INTERVAL '3 days'
        AND UPPER(description) LIKE '%%TRANSFER%%'
        LIMIT 1
    """, (amount, amount, txn_date, txn_date))
    
    match_1615 = cur.fetchone()
    
    if match_1615:
        matches_1615.append({
            'cibc_txn_id': txn_id,
            'cibc_date': txn_date,
            'amount': amount,
            'dest_txn_id': match_1615[0],
            'dest_date': match_1615[1],
            'receipt_id': receipt_id
        })
        continue
    
    # Check for matching credit in Scotia
    cur.execute("""
        SELECT transaction_id, transaction_date, credit_amount
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND credit_amount BETWEEN %s - 0.01 AND %s + 0.01
        AND transaction_date BETWEEN %s - INTERVAL '3 days' AND %s + INTERVAL '3 days'
        AND UPPER(description) LIKE '%%TRANSFER%%'
        LIMIT 1
    """, (amount, amount, txn_date, txn_date))
    
    match_scotia = cur.fetchone()
    
    if match_scotia:
        matches_scotia.append({
            'cibc_txn_id': txn_id,
            'cibc_date': txn_date,
            'amount': amount,
            'dest_txn_id': match_scotia[0],
            'dest_date': match_scotia[1],
            'receipt_id': receipt_id
        })
    else:
        unmatched.append({
            'cibc_txn_id': txn_id,
            'cibc_date': txn_date,
            'amount': amount,
            'receipt_id': receipt_id
        })

print("=" * 120)
print("MATCHING RESULTS")
print("=" * 120)
print(f"✅ Matched to 1615: {len(matches_1615)}")
print(f"✅ Matched to Scotia: {len(matches_scotia)}")
print(f"❌ Unmatched: {len(unmatched)}")

# Update receipts for matched transfers to 1615
if matches_1615:
    print("\n" + "=" * 120)
    print("UPDATING RECEIPTS - TRANSFERS TO ACCOUNT 1615")
    print("=" * 120)
    
    for match in matches_1615:
        if match['receipt_id']:
            cur.execute("""
                UPDATE receipts
                SET category = 'Inter-Account Transfer',
                    business_personal = 'Transfer',
                    gl_account_code = NULL,
                    vendor_name = 'Transfer to Account 1615'
                WHERE receipt_id = %s
            """, (match['receipt_id'],))
    
    conn.commit()
    print(f"✅ Updated {len(matches_1615)} receipts for transfers to 1615")

# Update receipts for matched transfers to Scotia
if matches_scotia:
    print("\n" + "=" * 120)
    print("UPDATING RECEIPTS - TRANSFERS TO SCOTIA BANK")
    print("=" * 120)
    
    for match in matches_scotia:
        if match['receipt_id']:
            cur.execute("""
                UPDATE receipts
                SET category = 'Inter-Account Transfer',
                    business_personal = 'Transfer',
                    gl_account_code = NULL,
                    vendor_name = 'Transfer to Scotia Bank 903990106011'
                WHERE receipt_id = %s
            """, (match['receipt_id'],))
    
    conn.commit()
    print(f"✅ Updated {len(matches_scotia)} receipts for transfers to Scotia")

# Show unmatched (likely personal accounts or external)
if unmatched:
    print("\n" + "=" * 120)
    print("UNMATCHED TRANSFERS (likely to personal/external accounts)")
    print("=" * 120)
    print(f"\n{'Date':<15} {'Amount':<15} {'Receipt ID':<15}")
    print("-" * 120)
    for match in unmatched[:20]:
        print(f"{str(match['cibc_date']):<15} ${match['amount']:>12,.2f} {match['receipt_id'] or 'None':<15}")
    
    if len(unmatched) > 20:
        print(f"\n... and {len(unmatched) - 20} more")
    
    # Update unmatched as personal transfers
    print("\nUpdating unmatched as personal withdrawals...")
    for match in unmatched:
        if match['receipt_id']:
            cur.execute("""
                UPDATE receipts
                SET category = 'Personal Withdrawal',
                    business_personal = 'Personal',
                    gl_account_code = '5880',
                    vendor_name = 'Bank Transfer - Personal Account'
                WHERE receipt_id = %s
            """, (match['receipt_id'],))
    
    conn.commit()
    print(f"✅ Updated {len(unmatched)} unmatched transfers as personal withdrawals")

cur.close()
conn.close()

print("\n✅ Bank transfer matching complete")
print(f"\nSummary:")
print(f"  - {len(matches_1615)} transfers to Account 1615")
print(f"  - {len(matches_scotia)} transfers to Scotia Bank")
print(f"  - {len(unmatched)} personal/external transfers")
