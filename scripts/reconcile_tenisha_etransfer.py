#!/usr/bin/env python3
"""
Manually reconcile the Tenisha Woodridge e-transfer email event to banking transaction.
"""
import psycopg2
from datetime import date

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Find the email event
cur.execute("""
    SELECT id, email_date, amount, notes, banking_transaction_id
    FROM email_financial_events
    WHERE notes LIKE '%Tenisha%' OR notes LIKE '%Woodridge%'
""")
email_events = cur.fetchall()
print(f"Email events: {len(email_events)}")
for e in email_events:
    print(f"  Event ID {e[0]}: {e[1]} ${e[2]:.2f} banking_id={e[4]}")
    print(f"    {e[3][:150]}")

# Find the banking transaction (2017-04-20, Tenisha Woodridge ford)
cur.execute("""
    SELECT transaction_id, transaction_date, debit_amount, credit_amount, description
    FROM banking_transactions
    WHERE transaction_date = %s
      AND description LIKE '%Tenisha%'
""", (date(2017, 4, 20),))
banking_txns = cur.fetchall()
print(f"\nBanking transactions: {len(banking_txns)}")
for b in banking_txns:
    print(f"  Txn ID {b[0]}: {b[1]} debit ${b[2] or 0:.2f} credit ${b[3] or 0:.2f}")
    print(f"    {b[4][:150]}")

# Match and update
if email_events and banking_txns:
    email_id = email_events[0][0]
    banking_id = banking_txns[0][0]
    
    cur.execute("""
        UPDATE email_financial_events
        SET banking_transaction_id = %s
        WHERE id = %s
    """, (banking_id, email_id))
    conn.commit()
    print(f"\n[OK] Reconciled email event {email_id} to banking transaction {banking_id}")
else:
    print("\n⚠ Could not find both email event and banking transaction for reconciliation")

cur.close()
conn.close()
