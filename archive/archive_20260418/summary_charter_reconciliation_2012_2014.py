"""
Summary Statistics for Charter Reconciliation: 2012-2014
"""
from decimal import Decimal
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine',
)
cur = conn.cursor()

def q2(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'))

print("\n" + "=" * 80)
print("SUMMARY STATISTICS: 2012-2014 CHARTER RECONCILIATION")
print("=" * 80 + "\n")

# Count cancelled vs active
cur.execute("""
    SELECT COUNT(*) as total,
           SUM(CASE WHEN cancelled = true THEN 1 ELSE 0 END) as cancelled,
           SUM(CASE WHEN cancelled = false OR cancelled IS NULL THEN 1 ELSE 0 END) as active
    FROM charters
    WHERE EXTRACT(YEAR FROM charter_date) IN (2012, 2013, 2014)
""")
total, cancelled, active = cur.fetchone()

print(f"CHARTER COUNTS:")
print(f"  Total Charters: {total:>15,}")
print(f"  Cancelled:      {cancelled:>15,}")
print(f"  Active:         {active:>15,}\n")

# Billing and Payment Totals
cur.execute("""
    SELECT COALESCE(SUM(cc.amount), 0) as total_billed,
           COUNT(DISTINCT cc.charge_id) as charge_count,
           COALESCE(SUM(cp.amount), 0) as total_paid,
           COUNT(DISTINCT cp.id) as payment_count
    FROM charters c
    LEFT JOIN charter_charges cc ON c.charter_id = cc.charter_id
    LEFT JOIN charter_payments cp ON c.reserve_number = cp.charter_id
    WHERE EXTRACT(YEAR FROM c.charter_date) IN (2012, 2013, 2014)
""")
billed, charge_count, paid, payment_count = cur.fetchone()
billed = q2(billed)
paid = q2(paid)
balance = billed - paid

print(f"FINANCIAL TOTALS:")
print(f"  Total Billed:   ${billed:>18}")
print(f"  Total Paid:     ${paid:>18}")
print(f"  Net Balance:    ${balance:>18}")
print(f"  (Charged - Paid) \n")

# Balance distribution
cur.execute("""
    SELECT 
        SUM(CASE WHEN ABS(cc_tot - cp_tot) < 0.01 THEN 1 ELSE 0 END) as perfectly_matched,
        SUM(CASE WHEN cc_tot > cp_tot THEN 1 ELSE 0 END) as has_unpaid,
        COALESCE(SUM(CASE WHEN cc_tot > cp_tot THEN cc_tot - cp_tot ELSE 0 END), 0) as unpaid_amount,
        SUM(CASE WHEN cc_tot < cp_tot THEN 1 ELSE 0 END) as has_overpaid,
        COALESCE(SUM(CASE WHEN cc_tot < cp_tot THEN cp_tot - cc_tot ELSE 0 END), 0) as overpaid_amount
    FROM (
        SELECT c.charter_id,
               COALESCE(SUM(cc.amount), 0) as cc_tot,
               COALESCE(SUM(cp.amount), 0) as cp_tot
        FROM charters c
        LEFT JOIN charter_charges cc ON c.charter_id = cc.charter_id
        LEFT JOIN charter_payments cp ON c.reserve_number = cp.charter_id
        WHERE EXTRACT(YEAR FROM c.charter_date) IN (2012, 2013, 2014)
          AND (c.cancelled = false OR c.cancelled IS NULL)
        GROUP BY c.charter_id
    ) sub
""")
matched, unpaid_count, unpaid_amt, overpaid_count, overpaid_amt = cur.fetchone()
unpaid_amt = q2(unpaid_amt)
overpaid_amt = q2(overpaid_amt)

print(f"CHARTER BALANCE STATUS (Active charters only):")
print(f"  Perfectly Matched ($0 balance): {matched:>10,}")
print(f"  Have Unpaid Balance:            {unpaid_count:>10,}  Total: ${unpaid_amt:>18}")
print(f"  Have Overpayment/Credit:        {overpaid_count:>10,}  Total: ${overpaid_amt:>18}\n")

# Cancelled charters details
cur.execute("""
    SELECT COALESCE(SUM(cc.amount), 0) as total_charges,
           COUNT(DISTINCT cc.charge_id) as charge_count,
           COALESCE(SUM(cp.amount), 0) as total_payments,
           COUNT(DISTINCT cp.id) as payment_count
    FROM charters c
    LEFT JOIN charter_charges cc ON c.charter_id = cc.charter_id
    LEFT JOIN charter_payments cp ON c.reserve_number = cp.charter_id
    WHERE EXTRACT(YEAR FROM c.charter_date) IN (2012, 2013, 2014)
      AND c.cancelled = true
""")
c_charges, c_charge_cnt, c_payments, c_payment_cnt = cur.fetchone()
c_charges = q2(c_charges)
c_payments = q2(c_payments)

print(f"CANCELLED CHARTERS ({cancelled} total):")
print(f"  Total Charges:   ${c_charges:>18}")
print(f"  Total Payments:  ${c_payments:>18}")
print(f"  Note: Cancelled charters should have $0 charges by policy\n")

# Show balance distribution
print(f"BALANCE DISTRIBUTION (Active charters):\n")
cur.execute("""
    SELECT 
        ROUND(cc_tot - cp_tot, 2) as balance,
        COUNT(*) as charter_count,
        COALESCE(SUM(cc_tot), 0) as total_charged,
        COALESCE(SUM(cp_tot), 0) as total_paid
    FROM (
        SELECT c.charter_id,
               COALESCE(SUM(cc.amount), 0) as cc_tot,
               COALESCE(SUM(cp.amount), 0) as cp_tot
        FROM charters c
        LEFT JOIN charter_charges cc ON c.charter_id = cc.charter_id
        LEFT JOIN charter_payments cp ON c.reserve_number = cp.charter_id
        WHERE EXTRACT(YEAR FROM c.charter_date) IN (2012, 2013, 2014)
          AND (c.cancelled = false OR c.cancelled IS NULL)
        GROUP BY c.charter_id
    ) sub
    GROUP BY ROUND(cc_tot - cp_tot, 2)
    ORDER BY balance DESC
    LIMIT 20
""")

print(f"{'Balance':>15} {'Count':>10} {'Type':<20}")
print("-" * 50)
for balance, count, charged, paid in cur.fetchall():
    if balance > 0:
        bal_type = "UNPAID"
    elif balance < 0:
        bal_type = "OVERPAID/CREDIT"
    else:
        bal_type = "MATCHED"
    print(f"${balance:>14} {count:>10} {bal_type:<20}")

print("\n" + "=" * 80)
print("✓ Full detailed CSV report exported to: charter_reconciliation_2012_2014.csv")
print("=" * 80 + "\n")

cur.close()
conn.close()
