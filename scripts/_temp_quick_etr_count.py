#!/usr/bin/env python3
"""Count ETR payments missing reserve or banking"""
import psycopg2
c = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = c.cursor()

cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN reserve_number IS NULL THEN 1 END) as no_reserve,
        COUNT(CASE WHEN banking_transaction_id IS NULL THEN 1 END) as no_banking,
        SUM(amount) as total_amount
    FROM payments
    WHERE payment_key LIKE 'ETR:%'
""")
total, no_res, no_bank, amt = cur.fetchone()
print(f"\n📊 ETR: payments (payment_key LIKE 'ETR:%'):")
print(f"   Total: {total:,} (${amt:,.2f})")
print(f"   Missing reserve_number: {no_res:,} ({no_res/total*100:.1f}%)")
print(f"   Missing banking_transaction_id: {no_bank:,} ({no_bank/total*100:.1f}%)")
print(f"   MATCHED: {total-no_bank:,} ({(total-no_bank)/total*100:.1f}%)")

cur.close()
c.close()
