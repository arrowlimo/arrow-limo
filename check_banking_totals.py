import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("\n" + "=" * 100)
print("BANKING TRANSACTIONS - FULL BREAKDOWN")
print("=" * 100)

# Total banking transactions
cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(COALESCE(credit_amount, 0)) as total_credits,
        SUM(COALESCE(debit_amount, 0)) as total_debits
    FROM banking_transactions
""")
total, credits, debits = cur.fetchone()
print(f"\nALL BANKING TRANSACTIONS:")
print(f"  Total count:    {total:8d}")
print(f"  Total credits:  ${credits if credits else 0:15,.2f} (money IN)")
print(f"  Total debits:   ${debits if debits else 0:15,.2f} (money OUT)")
print(f"  Net:            ${(credits if credits else 0) - (debits if debits else 0):15,.2f}")

# Unmatched only
cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(COALESCE(credit_amount, 0)) as total_credits,
        SUM(COALESCE(debit_amount, 0)) as total_debits
    FROM banking_transactions
    WHERE reconciled_payment_id IS NULL
    AND reconciled_receipt_id IS NULL
""")
total, credits, debits = cur.fetchone()
print(f"\nUNMATCHED BANKING TRANSACTIONS:")
print(f"  Total count:    {total:8d}")
print(f"  Total credits:  ${credits if credits else 0:15,.2f} (money IN)")
print(f"  Total debits:   ${debits if debits else 0:15,.2f} (money OUT)")
print(f"  Combined:       ${(credits if credits else 0) + (debits if debits else 0):15,.2f}")

# E-transfers only (unmatched)
cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(COALESCE(credit_amount, 0)) as total_credits
    FROM banking_transactions
    WHERE reconciled_payment_id IS NULL
    AND reconciled_receipt_id IS NULL
    AND description ILIKE '%E-TRANSFER%'
    AND credit_amount IS NOT NULL
""")
total, credits = cur.fetchone()
print(f"\nUNMATCHED E-TRANSFERS ONLY (credits/incoming):")
print(f"  Total count:    {total:8d}")
print(f"  Total amount:   ${credits if credits else 0:15,.2f}")

# What we've linked so far
cur.execute("""
    SELECT 
        COUNT(*) as to_payments,
        SUM(COALESCE(credit_amount, 0)) as payment_credits
    FROM banking_transactions
    WHERE reconciled_payment_id IS NOT NULL
""")
pay_cnt, pay_amt = cur.fetchone()

cur.execute("""
    SELECT 
        COUNT(*) as to_receipts,
        SUM(COALESCE(debit_amount, 0)) as receipt_debits
    FROM banking_transactions
    WHERE reconciled_receipt_id IS NOT NULL
""")
rec_cnt, rec_amt = cur.fetchone()

print(f"\nALREADY LINKED:")
print(f"  To payments:    {pay_cnt:8d} | ${pay_amt if pay_amt else 0:15,.2f}")
print(f"  To receipts:    {rec_cnt:8d} | ${rec_amt if rec_amt else 0:15,.2f}")

print("\n" + "=" * 100 + "\n")

cur.close()
conn.close()
