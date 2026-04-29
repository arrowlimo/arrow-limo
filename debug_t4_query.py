#!/usr/bin/env python3
import psycopg2
import os

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'ArrowLimousine')
DB_PORT = int(os.getenv('DB_PORT', '5432'))

conn = psycopg2.connect(
    host=DB_HOST, dbname=DB_NAME, user=DB_USER,
    password=DB_PASSWORD, port=DB_PORT
)
cur = conn.cursor()

print("Testing T4 query...")
cur.execute("""
    SELECT t4_id, tax_year, box_14_employment_income, box_16_cpp_contributions,
           box_18_ei_premiums, box_22_income_tax, box_44_union_dues, box_24_ei_insurable_earnings,
           box_29_exempt_ei_ei_insurable, notes
    FROM employee_t4_records
    WHERE employee_id = 10 AND tax_year = 2012;
""")

row = cur.fetchone()
print(f"Row returned: {row}")
print(f"Number of columns: {len(row) if row else 'None'}")

if row:
    print(f"\nUnpacking:")
    (t4_id, tax_year, box14, box16, box18, box22, box44,
     box24, box29, notes) = row
    print(f"t4_id={t4_id}")
    print(f"tax_year={tax_year}")
    print(f"box14={box14}")
    print(f"box16={box16}")
    print(f"box18={box18}")
    print(f"box22={box22}")
    print(f"box44={box44}")
    print(f"box24={box24}")
    print(f"box29={box29}")
    print(f"notes={notes}")

cur.close()
conn.close()
