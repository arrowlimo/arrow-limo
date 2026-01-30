#!/usr/bin/env python3
"""Quick check for driver 69 payroll"""
import os, psycopg2

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REDACTED***')
)
cur = conn.cursor()

print("\nDriver 69 payroll (gross $1700-$1900) for December 2012:")
cur.execute("""
    SELECT id, driver_id, pay_date, gross_pay, cpp, ei, tax, net_pay, 
           reserve_number, source
    FROM driver_payroll 
    WHERE driver_id = '69' 
      AND gross_pay BETWEEN 1700 AND 1900
      AND pay_date >= '2012-12-01' AND pay_date < '2013-01-01'
    ORDER BY pay_date DESC
""")

rows = cur.fetchall()
if rows:
    for r in rows:
        print(f"\nID: {r[0]}")
        print(f"Date: {r[2]}")
        print(f"Gross: ${r[3]:.2f}")
        print(f"CPP: ${r[4]:.2f}")
        print(f"EI: ${r[5]:.2f}")
        print(f"Tax: ${r[6]:.2f}")
        print(f"Net: ${r[7]:.2f if r[7] else 0:.2f}")
        print(f"Reserve: {r[8]}")
        print(f"Source: {r[9]}")
        
        # Compare
        match_gross = abs(r[3] - 1814.11) < 0.01
        match_cpp = abs(r[4] - 69.98) < 0.01
        match_ei = abs(r[5] - 31.21) < 0.01
        match_tax = abs(r[6] - 108.07) < 0.01
        
        if match_gross and match_cpp and match_ei and match_tax:
            print("✓ EXACT MATCH to pay stub!")
else:
    print("No entries found")

# Try broader search
print("\n\nAll driver 69 payroll in December 2012:")
cur.execute("""
    SELECT id, pay_date, gross_pay, cpp, ei, tax
    FROM driver_payroll 
    WHERE driver_id = '69'
      AND pay_date >= '2012-12-01' AND pay_date < '2013-01-01'
    ORDER BY gross_pay DESC
""")

for r in cur.fetchall():
    print(f"ID: {r[0]}, Date: {r[1]}, Gross: ${r[2]:.2f}, CPP: ${r[3]:.2f}, EI: ${r[4]:.2f}, Tax: ${r[5]:.2f}")

cur.close()
conn.close()
