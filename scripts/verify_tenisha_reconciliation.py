#!/usr/bin/env python3
"""
Verify Tenisha Woodridge e-transfer reconciliation status.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Get the email event with its linked banking transaction
cur.execute("""
    SELECT 
        e.id as email_id,
        e.email_date,
        e.amount as email_amount,
        e.notes,
        e.banking_transaction_id,
        b.transaction_date as bank_date,
        b.debit_amount as bank_debit,
        b.credit_amount as bank_credit,
        b.description as bank_desc
    FROM email_financial_events e
    LEFT JOIN banking_transactions b ON e.banking_transaction_id = b.transaction_id
    WHERE e.notes LIKE '%Tenisha%' OR e.notes LIKE '%Woodridge%'
""")

row = cur.fetchone()
if row:
    email_id, email_date, email_amt, notes, bank_id, bank_date, bank_debit, bank_credit, bank_desc = row
    
    print("TENISHA WOODRIDGE E-TRANSFER RECONCILIATION")
    print("=" * 80)
    print(f"\nEmail Event:")
    print(f"  ID: {email_id}")
    print(f"  Date: {email_date}")
    print(f"  Amount: ${email_amt:.2f}")
    print(f"  Notes: {notes}")
    
    print(f"\nLinked Banking Transaction:")
    print(f"  ID: {bank_id}")
    print(f"  Date: {bank_date}")
    print(f"  Debit: ${bank_debit or 0:.2f}")
    print(f"  Credit: ${bank_credit or 0:.2f}")
    print(f"  Description: {bank_desc[:150] if bank_desc else 'N/A'}")
    
    # Verify match
    if bank_id:
        amount_match = abs((email_amt) - (bank_debit or 0)) < 0.01
        date_match = email_date.date() == bank_date if bank_date else False
        
        print(f"\nReconciliation Status:")
        print(f"  Date match: {'✓' if date_match else '✗'}")
        print(f"  Amount match: {'✓' if amount_match else '✗'}")
        print(f"  Status: {'[OK] RECONCILED' if date_match and amount_match else '⚠ MISMATCH'}")
    else:
        print(f"\n⚠ Not reconciled - no banking transaction linked")
else:
    print("No email event found for Tenisha/Woodridge")

cur.close()
conn.close()
