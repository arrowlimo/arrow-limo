#!/usr/bin/env python3
"""Search for opening/closing balance lines in banking transactions."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*70)
print("SEARCHING FOR OPENING/CLOSING BALANCE LINES")
print("="*70)

# Search for balance-related descriptions
print("\n1. Banking transactions with 'balance' in description:")
cur.execute("""
    SELECT 
        transaction_id,
        account_number,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance,
        source_file
    FROM banking_transactions
    WHERE description ILIKE '%opening balance%'
       OR description ILIKE '%closing balance%'
       OR description ILIKE '%beginning balance%'
       OR description ILIKE '%ending balance%'
       OR description ILIKE '%balance forward%'
       OR description ILIKE '%balance b/f%'
       OR description ILIKE '%balance c/f%'
    ORDER BY transaction_date
""")

results = cur.fetchall()
print(f"   Found {len(results)} balance lines\n")

if results:
    print(f"   {'ID':<10} {'Date':<12} {'Account':<15} {'Debit':>12} {'Credit':>12} {'Description'}")
    print("   " + "-" * 90)
    
    for row in results:
        trans_id, acct, date, desc, debit, credit, balance, source = row
        acct_str = (acct or 'NULL')[:13]
        desc_str = (desc or '')[:40]
        debit_str = f"${debit:,.2f}" if debit else ""
        credit_str = f"${credit:,.2f}" if credit else ""
        print(f"   {trans_id:<10} {date} {acct_str:<15} {debit_str:>12} {credit_str:>12} {desc_str}")

# Search for zero-amount transactions that might be balance lines
print("\n2. Zero-amount transactions (might be balance lines):")
cur.execute("""
    SELECT 
        COUNT(*),
        COUNT(DISTINCT account_number),
        MIN(transaction_date),
        MAX(transaction_date)
    FROM banking_transactions
    WHERE (debit_amount IS NULL OR debit_amount = 0)
      AND (credit_amount IS NULL OR credit_amount = 0)
""")

zero_count, acct_count, min_date, max_date = cur.fetchone()
print(f"   Found {zero_count:,} zero-amount transactions")
print(f"   Across {acct_count} accounts")
if min_date:
    print(f"   Date range: {min_date} to {max_date}")

if zero_count > 0 and zero_count < 100:
    print("\n   Sample zero-amount transactions:")
    cur.execute("""
        SELECT 
            transaction_id,
            account_number,
            transaction_date,
            description
        FROM banking_transactions
        WHERE (debit_amount IS NULL OR debit_amount = 0)
          AND (credit_amount IS NULL OR credit_amount = 0)
        ORDER BY transaction_date DESC
        LIMIT 20
    """)
    
    print(f"\n   {'ID':<10} {'Date':<12} {'Account':<15} {'Description'}")
    print("   " + "-" * 80)
    for row in cur.fetchall():
        trans_id, acct, date, desc = row
        acct_str = (acct or 'NULL')[:13]
        desc_str = (desc or '')[:45]
        print(f"   {trans_id:<10} {date} {acct_str:<15} {desc_str}")

# Check if any receipts were created from balance lines
if results:
    print("\n3. Receipts created from balance lines:")
    balance_trans_ids = [row[0] for row in results]
    
    if balance_trans_ids:
        placeholders = ','.join(['%s'] * len(balance_trans_ids))
        cur.execute(f"""
            SELECT COUNT(*)
            FROM receipts
            WHERE banking_transaction_id IN ({placeholders})
        """, balance_trans_ids)
        
        receipt_count = cur.fetchone()[0]
        print(f"   {receipt_count} receipts created from balance lines")
        
        if receipt_count > 0:
            print("   ⚠️  These should be deleted (balance lines aren't receipts)")

print(f"\n{'='*70}")
print("RECOMMENDATION")
print("="*70)
print("""
Opening/Closing balance lines should be:
  1. REMOVED from banking_transactions (they're not real transactions)
  2. Any receipts created from them should be DELETED
  3. Balance information should be in a separate balances table
  
Balance lines are just informational markers, not actual transactions.
""")

cur.close()
conn.close()
