#!/usr/bin/env python3
"""Match E-Transfer payments via banking_transactions (not email reserve numbers)"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("\n" + "="*80)
print("E-TRANSFER PAYMENT-BANKING MATCHING STATUS")
print("="*80)

# ETR payment status
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN banking_transaction_id IS NOT NULL THEN 1 END) as has_banking,
        COUNT(CASE WHEN reserve_number IS NOT NULL THEN 1 END) as has_reserve,
        SUM(amount) as total_amount
    FROM payments
    WHERE payment_key LIKE 'ETR:%'
""")

total, has_bank, has_res, amt = cur.fetchone()
print(f"\n📧 ETR Payments (payment_key LIKE 'ETR:%'):")
print(f"   Total: {total:,}")
print(f"   With banking_transaction_id: {has_bank:,} ({has_bank/total*100:.1f}%)")
print(f"   With reserve_number: {has_res:,} ({has_res/total*100:.1f}%)")
print(f"   Total amount: ${amt:,.2f}")

# Check email_financial_events banking matches
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN banking_transaction_id IS NOT NULL THEN 1 END) as has_banking
    FROM email_financial_events
    WHERE event_type = 'etransfer_received'
""")

total_email, email_banking = cur.fetchone()
print(f"\n📨 Email E-Transfer Events (etransfer_received):")
print(f"   Total: {total_email:,}")
print(f"   Matched to banking: {email_banking:,} ({email_banking/total_email*100:.1f}%)")

# Match ETR payments to email events via banking
cur.execute("""
    SELECT 
        COUNT(DISTINCT p.payment_id) as linkable_payments,
        SUM(p.amount) as linkable_amount
    FROM payments p
    INNER JOIN email_financial_events e ON e.banking_transaction_id = p.banking_transaction_id
    WHERE p.payment_key LIKE 'ETR:%'
    AND p.banking_transaction_id IS NOT NULL
    AND e.event_type = 'etransfer_received'
""")

link_payments, link_amt = cur.fetchone()
print(f"\n🔗 ETR Payments Linkable via Banking:")
print(f"   Already linked via banking: {link_payments:,}")
print(f"   Linked amount: ${link_amt:,.2f}" if link_amt else "   Linked amount: $0.00")

# Check for ETR payments in banking NOT in payments
cur.execute("""
    SELECT 
        COUNT(DISTINCT b.transaction_id) as banking_etransfers,
        SUM(b.credit_amount) as banking_amount,
        COUNT(DISTINCT p.payment_id) as matched_payments
    FROM banking_transactions b
    LEFT JOIN payments p ON p.banking_transaction_id = b.transaction_id
    WHERE b.description ILIKE '%e-transfer%'
    OR b.description ILIKE '%etransfer%'
    OR b.description ILIKE '%interac%'
""")

bank_etr, bank_amt, matched_p = cur.fetchone()
print(f"\n🏦 Banking E-Transfer Transactions:")
print(f"   Total banking e-transfers: {bank_etr:,} (${bank_amt:,.2f})")
print(f"   Matched to payments: {matched_p:,} ({matched_p/bank_etr*100:.1f}%)")
print(f"   Unmatched: {bank_etr - matched_p:,}")

# Sample unmatched banking e-transfers
cur.execute("""
    SELECT 
        b.transaction_id,
        b.transaction_date,
        b.credit_amount,
        b.description
    FROM banking_transactions b
    LEFT JOIN payments p ON p.banking_transaction_id = b.transaction_id
    WHERE (b.description ILIKE '%e-transfer%'
           OR b.description ILIKE '%etransfer%'
           OR b.description ILIKE '%interac%')
    AND p.payment_id IS NULL
    AND b.credit_amount > 0
    AND EXTRACT(YEAR FROM b.transaction_date) >= 2025
    ORDER BY b.transaction_date DESC
    LIMIT 10
""")

unmatched = cur.fetchall()
if unmatched:
    print(f"\n📋 Sample Unmatched 2025 Banking E-Transfers:")
    print(f"{'TX ID':<10} {'Date':<12} {'Amount':<12} {'Description':<50}")
    print("-" * 90)
    for tx_id, date, amt, desc in unmatched:
        desc_short = desc[:48] if desc else ''
        print(f"{tx_id:<10} {str(date):<12} ${amt:<11,.2f} {desc_short}")

print(f"\n" + "="*80)
print("CONCLUSION")
print("="*80)
print(f"""
If ETR payments already have banking_transaction_id ({has_bank}/{total}):
  - They are already matched to banking
  - Email events provide additional context (sender, notes)
  - Reserve numbers need to come from LMS sync (not email)

If ETR payments missing banking_transaction_id ({total - has_bank}/{total}):
  - Need to match via amount + date to banking e-transfer transactions
  - Then link to email_financial_events for additional data
""")

cur.close()
conn.close()
