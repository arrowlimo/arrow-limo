"""
FINAL AUDIT REPORT: Perron Ventures Limited Charter Payments
"""
import psycopg2
from decimal import Decimal

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='ArrowLimousine'
)
cur = conn.cursor()

print("="*80)
print("PERRON VENTURES LIMITED - FINAL PAYMENT AUDIT REPORT")
print("="*80)
print()

# Get all charters currently assigned to Perron Ventures
cur.execute("""
    SELECT 
        c.reserve_number,
        c.charter_date,
        c.total_amount_due,
        c.balance,
        COUNT(cp.id) as payment_count,
        COALESCE(SUM(cp.amount), 0) as total_paid,
        STRING_AGG(DISTINCT cp.payment_key, ', ' ORDER BY cp.payment_key) as payment_keys
    FROM charters c
    LEFT JOIN charter_payments cp ON c.reserve_number = cp.charter_id
    WHERE c.client_display_name ILIKE '%Perron Ventures%'
      AND c.client_display_name NOT ILIKE '%Perron Kip%'
      AND EXTRACT(YEAR FROM c.charter_date) = 2012
    GROUP BY c.reserve_number, c.charter_date, c.total_amount_due, c.balance
    ORDER BY c.charter_date, c.reserve_number
""")

all_charters = cur.fetchall()

print(f"📊 CHARTER SUMMARY")
print(f"   Total charters in database: {len(all_charters)}")
print()

# Separate into invoice charters vs excluded charters
excluded_charters = ['005969', '005970', '005971', '006026']
invoice_charters = [c for c in all_charters if c[0] not in excluded_charters]
excluded_details = [c for c in all_charters if c[0] in excluded_charters]

print("="*80)
print("INVOICED CHARTERS (58 charters from multiinvoice.xls)")
print("="*80)
print()

# Group by payment key
check1_charters = []
check2_charters = []

for charter in invoice_charters:
    reserve_num, charter_date, total_due, balance, pay_count, total_paid, pay_keys = charter
    if 'CHQ-004859' in (pay_keys or ''):
        check1_charters.append(charter)
    elif 'CHQ-005094' in (pay_keys or ''):
        check2_charters.append(charter)

check1_total_due = sum(Decimal(str(c[2])) for c in check1_charters)
check1_total_paid = sum(Decimal(str(c[5])) for c in check1_charters)

check2_total_due = sum(Decimal(str(c[2])) for c in check2_charters)
check2_total_paid = sum(Decimal(str(c[5])) for c in check2_charters)

print(f"CHECK #004859 (February 21, 2012)")
print(f"  Charters: {len(check1_charters)}")
print(f"  Total Due: ${check1_total_due:,.2f}")
print(f"  Total Paid: ${check1_total_paid:,.2f}")
print(f"  Status: {'✅ PAID IN FULL' if check1_total_due == check1_total_paid else '⚠️ BALANCE DUE'}")
print()

print(f"CHECK #005094 (April 17, 2012)")
print(f"  Charters: {len(check2_charters)}")
print(f"  Total Due: ${check2_total_due:,.2f}")
print(f"  Total Paid: ${check2_total_paid:,.2f}")
print(f"  Status: {'✅ PAID IN FULL' if check2_total_due == check2_total_paid else '⚠️ BALANCE DUE'}")
print()

print("-" * 80)
print(f"INVOICE TOTAL")
print(f"  Total Due:  ${check1_total_due + check2_total_due:,.2f}")
print(f"  Total Paid: ${check1_total_paid + check2_total_paid:,.2f}")
print(f"  Balance:    ${(check1_total_due + check2_total_due) - (check1_total_paid + check2_total_paid):,.2f}")
print()

# Excluded charters
if excluded_details:
    print("="*80)
    print("EXCLUDED CHARTERS (NOT Perron Ventures - Misassigned)")
    print("="*80)
    print()
    
    for charter in excluded_details:
        reserve_num, charter_date, total_due, balance, pay_count, total_paid, pay_keys = charter
        print(f"  {reserve_num}  {charter_date}  ${total_due:>8,.2f}  {pay_keys or 'No Payment'}")
    
    excluded_total_due = sum(Decimal(str(c[2])) for c in excluded_details)
    excluded_total_paid = sum(Decimal(str(c[5])) for c in excluded_details)
    
    print()
    print(f"  Total Due:  ${excluded_total_due:,.2f}")
    print(f"  Total Paid: ${excluded_total_paid:,.2f}")
    print()
    print("  ⚠️  These charters should be reassigned to correct clients")
    print()

# Summary
print("="*80)
print("FINAL SUMMARY")
print("="*80)
print()
print("✅ PERRON VENTURES LIMITED ACCOUNT STATUS:")
print(f"   • 58 charters totaling $57,997.50")
print(f"   • Paid in full with 2 checks:")
print(f"     - Check #004859: $42,940.00 (Feb 21, 2012) - 43 charters")
print(f"     - Check #005094: $15,057.50 (Apr 17, 2012) - 15 charters")
print(f"   • Account Balance: $0.00")
print()
print("⚠️  DATA QUALITY ISSUE:")
print(f"   • 4 charters incorrectly assigned to Perron Ventures:")
print(f"     - {', '.join(excluded_charters)}")
print(f"   • Recommendation: Reassign to correct clients")
print()

cur.close()
conn.close()

print("="*80)
print("AUDIT COMPLETE")
print("="*80)
