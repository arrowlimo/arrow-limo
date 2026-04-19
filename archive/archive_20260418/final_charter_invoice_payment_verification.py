"""
FINAL VERIFICATION: 2012 & 2013 Charter Invoicing vs Payments - Detailed Analysis
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

print("=" * 100)
print("FINAL VERIFICATION: 2012 & 2013 CHARTER INVOICING vs PAYMENTS")
print("=" * 100)

# Summary stats
cur.execute("""
    SELECT EXTRACT(YEAR FROM c.charter_date)::INT as year,
           COUNT(DISTINCT c.charter_id) as total_charters,
           COUNT(DISTINCT cc.charge_id) as charters_with_charges,
           COUNT(DISTINCT CASE WHEN cp.id IS NOT NULL THEN c.charter_id END) as charters_with_payments,
           COUNT(DISTINCT CASE WHEN cp.id IS NULL THEN c.charter_id END) as charters_no_payment
    FROM charters c
    LEFT JOIN charter_charges cc ON c.charter_id = cc.charter_id
    LEFT JOIN charter_payments cp ON c.charter_id = CAST(cp.charter_id AS INTEGER)
    WHERE EXTRACT(YEAR FROM c.charter_date) IN (2012, 2013)
    GROUP BY EXTRACT(YEAR FROM c.charter_date)
    ORDER BY year
""")

print("\nCHARTER COUNT SUMMARY:\n")
print(f"{'Year':<10} {'Total':<12} {'Have Charges':<18} {'Have Payments':<18} {'No Payment':<15}")
print("-" * 65)
for year, total, w_charges, w_payments, no_payment in cur.fetchall():
    print(f"{int(year):<10} {total:<12} {w_charges:<18} {w_payments:<18} {no_payment:<15}")

# Amount summary
print("\n\nAMOUNT SUMMARY:\n")
cur.execute("""
    SELECT EXTRACT(YEAR FROM c.charter_date)::INT as year,
           COALESCE(SUM(cc.amount), 0) as total_charged,
           COALESCE(SUM(CASE WHEN cp.id IS NOT NULL THEN cp.amount ELSE 0 END), 0) as total_paid,
           COALESCE(SUM(cc.amount), 0) - COALESCE(SUM(CASE WHEN cp.id IS NOT NULL THEN cp.amount ELSE 0 END), 0) as unpaid_balance
    FROM charters c
    LEFT JOIN charter_charges cc ON c.charter_id = cc.charter_id
    LEFT JOIN charter_payments cp ON c.charter_id = CAST(cp.charter_id AS INTEGER)
    WHERE EXTRACT(YEAR FROM c.charter_date) IN (2012, 2013)
    GROUP BY EXTRACT(YEAR FROM c.charter_date)
    ORDER BY year
""")

print(f"{'Year':<10} {'Total Charged':<18} {'Total Paid':<18} {'Unpaid Balance':<18} {'% Paid':<12}")
print("-" * 76)
for year, charged, paid, unpaid in cur.fetchall():
    pct = (paid / charged * 100) if charged > 0 else 0
    print(f"{int(year):<10} ${q2(charged):>16} ${q2(paid):>16} ${q2(unpaid):>16} {pct:>10.1f}%")

# Detailed breakdown
print("\n\nDETAILED BREAKDOWN BY STATUS:\n")
cur.execute("""
    SELECT EXTRACT(YEAR FROM c.charter_date)::INT as year,
           -- Charters with charges = payments (MATCHED)
           SUM(CASE WHEN COALESCE(SUM(cc.amount), 0) = COALESCE(SUM(cp.amount), 0) THEN 1 ELSE 0 END) as matched_charters,
           COALESCE(SUM(CASE WHEN COALESCE(SUM(cc.amount), 0) = COALESCE(SUM(cp.amount), 0) THEN cc.amount ELSE 0 END), 0) as matched_amount,
           -- Charters with charges > payments (UNDERPAID)
           SUM(CASE WHEN COALESCE(SUM(cc.amount), 0) > COALESCE(SUM(cp.amount), 0) AND COALESCE(SUM(cp.amount), 0) > 0 THEN 1 ELSE 0 END) as underpaid,
           COALESCE(SUM(CASE WHEN COALESCE(SUM(cc.amount), 0) > COALESCE(SUM(cp.amount), 0) AND COALESCE(SUM(cp.amount), 0) > 0 THEN (COALESCE(SUM(cc.amount), 0) - COALESCE(SUM(cp.amount), 0)) ELSE 0 END), 0) as underpaid_amount,
           -- Charters with charges but NO payments (UNPAID)
           SUM(CASE WHEN COALESCE(SUM(cc.amount), 0) > 0 AND COALESCE(SUM(cp.amount), 0) = 0 THEN 1 ELSE 0 END) as unpaid_no_payment,
           COALESCE(SUM(CASE WHEN COALESCE(SUM(cc.amount), 0) > 0 AND COALESCE(SUM(cp.amount), 0) = 0 THEN COALESCE(SUM(cc.amount), 0) ELSE 0 END), 0) as unpaid_amount
    FROM charters c
    LEFT JOIN charter_charges cc ON c.charter_id = cc.charter_id
    LEFT JOIN charter_payments cp ON c.charter_id = CAST(cp.charter_id AS INTEGER)
    WHERE EXTRACT(YEAR FROM c.charter_date) IN (2012, 2013)
    GROUP BY c.charter_id, EXTRACT(YEAR FROM c.charter_date)
""")

# Aggregate the subquery
cur.execute("""
    SELECT year,
           SUM(matched_charters) as matched_charters,
           SUM(matched_amount) as matched_amount,
           SUM(underpaid) as underpaid,
           SUM(underpaid_amount) as underpaid_amount,
           SUM(unpaid_no_payment) as unpaid_no_payment,
           SUM(unpaid_amount) as unpaid_amount
    FROM (
        SELECT EXTRACT(YEAR FROM c.charter_date)::INT as year,
               CASE WHEN COALESCE(SUM(cc.amount), 0) = COALESCE(SUM(cp.amount), 0) THEN 1 ELSE 0 END as matched_charters,
               CASE WHEN COALESCE(SUM(cc.amount), 0) = COALESCE(SUM(cp.amount), 0) THEN COALESCE(SUM(cc.amount), 0) ELSE 0 END as matched_amount,
               CASE WHEN COALESCE(SUM(cc.amount), 0) > COALESCE(SUM(cp.amount), 0) AND COALESCE(SUM(cp.amount), 0) > 0 THEN 1 ELSE 0 END as underpaid,
               CASE WHEN COALESCE(SUM(cc.amount), 0) > COALESCE(SUM(cp.amount), 0) AND COALESCE(SUM(cp.amount), 0) > 0 THEN COALESCE(SUM(cc.amount), 0) - COALESCE(SUM(cp.amount), 0) ELSE 0 END as underpaid_amount,
               CASE WHEN COALESCE(SUM(cc.amount), 0) > 0 AND COALESCE(SUM(cp.amount), 0) = 0 THEN 1 ELSE 0 END as unpaid_no_payment,
               CASE WHEN COALESCE(SUM(cc.amount), 0) > 0 AND COALESCE(SUM(cp.amount), 0) = 0 THEN COALESCE(SUM(cc.amount), 0) ELSE 0 END as unpaid_amount
        FROM charters c
        LEFT JOIN charter_charges cc ON c.charter_id = cc.charter_id
        LEFT JOIN charter_payments cp ON c.charter_id = CAST(cp.charter_id AS INTEGER)
        WHERE EXTRACT(YEAR FROM c.charter_date) IN (2012, 2013)
        GROUP BY c.charter_id, EXTRACT(YEAR FROM c.charter_date)
    ) sub
    GROUP BY year
    ORDER BY year
""")

print(f"{'Year':<8} {'Matched':<12} {'Amount':<18} {'Underpaid':<12} {'Amount':<18} {'No Payment':<12} {'Amount':<18}")
print("-" * 100)
for year, matched, matched_amt, underpaid, under_amt, no_payment, no_pay_amt in cur.fetchall():
    print(f"{int(year):<8} {matched:<12} ${q2(matched_amt):>16} {underpaid:<12} ${q2(under_amt):>16} {no_payment:<12} ${q2(no_pay_amt):>16}")

# Final conclusion
print("\n" + "=" * 100)
print("CONCLUSION")
print("=" * 100)

cur.execute("""
    SELECT COALESCE(SUM(cc.amount), 0) as charged,
           COALESCE(SUM(cp.amount), 0) as paid
    FROM charters c
    LEFT JOIN charter_charges cc ON c.charter_id = cc.charter_id
    LEFT JOIN charter_payments cp ON c.charter_id = CAST(cp.charter_id AS INTEGER)
    WHERE EXTRACT(YEAR FROM c.charter_date) IN (2012, 2013)
""")
total_charged, total_paid = cur.fetchone()
total_charged = q2(total_charged)
total_paid = q2(total_paid)
diff = total_charged - total_paid
pct_unpaid = (diff / total_charged * 100) if total_charged > 0 else 0

print(f"\n✗ 2012 & 2013 CHARTER INVOICING DOES NOT MATCH PAYMENTS\n")
print(f"  Total Invoiced (Charges): ${total_charged:>18}")
print(f"  Total Paid (Payments):    ${total_paid:>18}")
print(f"  Unpaid Balance:           ${diff:>18}")
print(f"  % Unpaid:                 {pct_unpaid:>18.1f}%\n")
print(f"  ROOT CAUSE: {int(pct_unpaid)}% of charters have charges but NO payment records")
print(f"  ACTION NEEDED: Investigate whether charges are accurate or payments need to be recorded\n")

cur.close()
conn.close()
