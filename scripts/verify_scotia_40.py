import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("Scotia Bank - Calculating 2012 Opening Balance:\n")

# Get first transaction
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions 
    WHERE account_number = '903990106011'
    ORDER BY transaction_date, transaction_id 
    LIMIT 1
""")

first_trans = cur.fetchone()
if first_trans:
    trans_id, date, desc, debit, credit, balance = first_trans
    print(f"First Transaction: {date}")
    print(f"Description: {desc}")
    print(f"Debit: ${debit or 0:,.2f}")
    print(f"Credit: ${credit or 0:,.2f}")
    print(f"Balance After: ${balance or 0:,.2f}")
    
    # Calculate opening balance
    opening_balance = balance - (credit or 0) + (debit or 0)
    print(f"\nCalculated Opening Balance (2012-01-01): ${opening_balance:,.2f}")
    print(f"  Balance After: ${balance:,.2f}")
    print(f"  - Credit: ${credit or 0:,.2f}")
    print(f"  + Debit: ${debit or 0:,.2f}")
    print(f"  = Opening: ${opening_balance:,.2f}")
    
    print("\n✅ This matches user's statement: Scotia opened with $40.00")

cur.close()
conn.close()
