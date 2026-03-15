import psycopg2
from decimal import Decimal

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost')
cur = conn.cursor()

print("="*80)
print("PERRON VENTURES - ACTUAL CHARTER STATUS")
print("="*80)

cur.execute("""
    SELECT 
        c.reserve_number,
        c.charter_date,
        c.total_amount_due,
        COALESCE(SUM(cp.amount), 0) as total_paid
    FROM charters c
    LEFT JOIN charter_payments cp ON cp.charter_id::integer = c.charter_id
    WHERE c.client_display_name ILIKE '%Perron Ventures%'
    AND c.charter_date BETWEEN '2012-01-01' AND '2012-12-31'
    GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due
    ORDER BY c.charter_date
""")

charters = cur.fetchall()

fully_paid = 0
unpaid = 0
overpaid = 0
total_due = Decimal('0')
total_paid = Decimal('0')

print(f"\n{'Reserve':<12} {'Date':<12} {'Due':<15} {'Paid':<15} {'Balance':<15} Status")
print("-" * 85)

for reserve, charter_date, due, paid in charters[:15]:
    due = due or Decimal('0')
    paid = paid or Decimal('0')
    balance = due - paid
    total_due += due
    total_paid += paid
    
    if abs(balance) < 0.01:
        status = "✅ PAID"
        fully_paid += 1
    elif balance > 0.01:
        status = "⚠️  UNPAID"
        unpaid += 1
    else:
        status = "🔴 OVER"
        overpaid += 1
    
    print(f"{reserve:<12} {str(charter_date):<12} ${due:>12,.2f} ${paid:>12,.2f} ${balance:>12,.2f} {status}")

if len(charters) > 15:
    print(f"... and {len(charters) - 15} more charters")

print("\n" + "="*80)
print(f"SUMMARY: {len(charters)} total charters")
print(f"  ✅ Fully Paid: {fully_paid}")
print(f"  ⚠️  Unpaid: {unpaid}")
print(f"  🔴 Overpaid: {overpaid}")
print(f"\n  Total Due: ${total_due:,.2f}")
print(f"  Total Paid: ${total_paid:,.2f}")
print(f"  Balance: ${total_due - total_paid:,.2f}")
print("="*80)

conn.close()
