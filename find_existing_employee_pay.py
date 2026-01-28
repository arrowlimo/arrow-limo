#!/usr/bin/env python3
"""Find existing employee pay and reconciliation tables/records."""
import psycopg2
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("\n" + "=" * 140)
print("FIND EXISTING EMPLOYEE PAY & RECONCILIATION TABLES/RECORDS".center(140))
print("=" * 140)

# Check for tables with employee/pay/reconciliation keywords
print("\n1️⃣ CHECK FOR RELATED TABLES:")
print("-" * 140)

cur.execute('''
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public'
    ORDER BY table_name;
''')

tables = [row[0] for row in cur.fetchall()]

keywords = ['employee', 'pay', 'payroll', 'reconcil', 'reimburse', 'vendor', 'expense']
matching_tables = [t for t in tables if any(kw in t.lower() for kw in keywords)]

if matching_tables:
    print(f"Found {len(matching_tables)} tables:")
    for table in matching_tables:
        cur.execute(f"SELECT COUNT(*) FROM {table};")
        count = cur.fetchone()[0]
        print(f"   - {table} ({count} rows)")
else:
    print("No tables found with employee/pay/reconciliation keywords")

# Check for charters with special reserve_numbers
print("\n2️⃣ CHECK FOR SPECIAL CHARTERS (Employee Pay, Reconciliation):")
print("-" * 140)

cur.execute('''
    SELECT charter_id, reserve_number, client_id, status, 
           total_amount_due, paid_amount
    FROM charters
    WHERE reserve_number ILIKE '%EMP%'
       OR reserve_number ILIKE '%PAY%'
       OR reserve_number ILIKE '%RECONCIL%'
       OR reserve_number ILIKE '%VENDOR%'
       OR reserve_number ILIKE '%INSURANCE%'
       OR reserve_number ILIKE '%HEFFNER%'
    ORDER BY charter_date DESC;
''')

special_charters = cur.fetchall()
if special_charters:
    print(f"Found {len(special_charters)} special charters:")
    for row in special_charters:
        charter_id, reserve, client_id, status, due, paid = row
        print(f"   charter_id={charter_id} | reserve={reserve} | client={client_id} | status={status} | due=${due:.2f} | paid=${paid:.2f}")
else:
    print("No special charters found")

# Check for clients with employee/vendor names
print("\n3️⃣ CHECK FOR SPECIAL CLIENTS (Employee, Vendor):")
print("-" * 140)

cur.execute('''
    SELECT client_id, client_name, company_name
    FROM clients
    WHERE UPPER(client_name) ILIKE '%EMP%'
       OR UPPER(client_name) ILIKE '%PAY%'
       OR UPPER(client_name) ILIKE '%VENDOR%'
       OR UPPER(client_name) ILIKE '%HEFFNER%'
       OR UPPER(client_name) ILIKE '%INSURANCE%'
       OR UPPER(client_name) ILIKE '%RECONCIL%'
       OR UPPER(company_name) ILIKE '%EMP%'
       OR UPPER(company_name) ILIKE '%PAY%'
       OR UPPER(company_name) ILIKE '%VENDOR%'
       OR UPPER(company_name) ILIKE '%HEFFNER%'
       OR UPPER(company_name) ILIKE '%INSURANCE%'
    ORDER BY client_name;
''')

special_clients = cur.fetchall()
if special_clients:
    print(f"Found {len(special_clients)} special clients:")
    for row in special_clients:
        client_id, client_name, company_name = row
        print(f"   client_id={client_id} | name={client_name} | company={company_name}")
else:
    print("No special clients found")

# Check for payments with these reserve_numbers
print("\n4️⃣ CHECK PAYMENTS LINKED TO SPECIAL RESERVES:")
print("-" * 140)

cur.execute('''
    SELECT 
        reserve_number,
        COUNT(*) as count,
        SUM(amount) as total
    FROM payments
    WHERE reserve_number ILIKE '%EMP%'
       OR reserve_number ILIKE '%PAY%'
       OR reserve_number ILIKE '%RECONCIL%'
       OR reserve_number ILIKE '%VENDOR%'
    GROUP BY reserve_number
    ORDER BY SUM(amount) DESC;
''')

special_payments = cur.fetchall()
if special_payments:
    print(f"Found payments linked to special reserves:")
    for row in special_payments:
        reserve, count, total = row
        print(f"   reserve={reserve} | count={count} | total=${total if total else 0:,.2f}")
else:
    print("No payments linked to special reserves")

# List all unique reserve_numbers to see what exists
print("\n5️⃣ ALL UNIQUE RESERVE_NUMBERS (first 30):")
print("-" * 140)

cur.execute('''
    SELECT DISTINCT reserve_number, COUNT(*) as count, SUM(amount) as total
    FROM payments
    GROUP BY reserve_number
    ORDER BY COUNT(*) DESC
    LIMIT 30;
''')

all_reserves = cur.fetchall()
for row in all_reserves:
    reserve, count, total = row
    print(f"   {reserve or 'NULL':<20} | count={count:>6} | total=${total if total else 0:>12,.2f}")

print("\n" + "=" * 140 + "\n")

cur.close()
conn.close()
