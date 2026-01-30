"""
Calculate total amount paid to Fibrenew.
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("\n=== Fibrenew Payment Summary ===\n")

# Total all receipts
cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name ILIKE '%fibrenew%'
""")
count, total = cur.fetchone()
print(f"Total receipts: {count}")
print(f"Total paid: ${total:,.2f}\n")

# By year
cur.execute("""
    SELECT EXTRACT(YEAR FROM receipt_date) as year, 
           COUNT(*), 
           SUM(gross_amount)
    FROM receipts
    WHERE vendor_name ILIKE '%fibrenew%'
    GROUP BY EXTRACT(YEAR FROM receipt_date)
    ORDER BY year
""")

print("By Year:")
for row in cur.fetchall():
    print(f"  {int(row[0])}: {int(row[1]):3} receipts | ${row[2]:>12,.2f}")

# Outstanding balance from statement
from decimal import Decimal
outstanding = Decimal('14734.56')
print(f"\n" + "="*50)
print(f"Outstanding balance (per Nov 2025 statement): ${outstanding:,.2f}")
print(f"Total paid + outstanding: ${total + outstanding:,.2f}")

cur.close()
conn.close()
