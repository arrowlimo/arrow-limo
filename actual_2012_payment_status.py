import psycopg2
from decimal import Decimal

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost')
cur = conn.cursor()

print("="*80)
print("PERRON VENTURES 2012 - COMPLETE PAYMENT AUDIT")
print("="*80)

# Get charters with their reserve numbers
cur.execute("""
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.charter_date,
        c.total_amount_due
    FROM charters c
    WHERE c.client_display_name ILIKE '%Perron Ventures%'
    AND c.charter_date BETWEEN '2012-01-01' AND '2012-12-31'
    ORDER BY c.charter_date
""")

charters = cur.fetchall()

print(f"\n📋 2012 CHARTERS: {len(charters)}")
print(f"\n{'Reserve':<12} {'Charter ID':<12} {'Date':<12} {'Due':<15} {'Payments':<40}")
print("-" * 100)

total_due = Decimal('0')
total_paid = Decimal('0')
fully_paid_count = 0
unpaid_count = 0

for charter_id, reserve, charter_date, due in charters:
    due = due or Decimal('0')
    total_due += due
    
    # Get payments matching this reserve number in charter_payments.charter_id
    cur.execute("""
        SELECT payment_date, amount, payment_key
        FROM charter_payments
        WHERE charter_id = %s
        ORDER BY payment_date
    """, (reserve,))
    
    payments = cur.fetchall()
    charter_paid = sum(p[1] for p in payments) if payments else Decimal('0')
    total_paid += charter_paid
    
    balance = due - charter_paid
    
    if abs(balance) < 0.01:
        status = "✅"
        fully_paid_count += 1
    else:
        status = "⚠️"
        unpaid_count += 1
    
    payment_str = ""
    if payments:
        payment_str = f"{len(payments)} pmts = ${charter_paid:,.2f}"
    else:
        payment_str = "NO PAYMENTS"
    
    if unpaid_count <= 15 or payments:  # Show unpaid and those with payments
        print(f"{reserve:<12} {charter_id:<12} {str(charter_date):<12} ${due:>12,.2f} {payment_str:<40} {status}")

print("\n" + "="*80)
print(f"SUMMARY:")
print(f"  Total Charters: {len(charters)}")
print(f"  Total Due: ${total_due:,.2f}")
print(f"  Total Paid: ${total_paid:,.2f}")
print(f"  Outstanding: ${total_due - total_paid:,.2f}")
print(f"  Paid %: {(total_paid / total_due * 100) if total_due > 0 else 0:.1f}%")
print(f"\n  ✅ Fully Paid: {fully_paid_count}")
print(f"  ⚠️  Unpaid: {unpaid_count}")
print("="*80)

conn.close()
