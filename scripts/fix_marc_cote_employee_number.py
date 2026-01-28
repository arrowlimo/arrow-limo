import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REMOVED***')
cur = conn.cursor()

print("\n" + "="*80)
print("FIXING MARC A COTE - QB ID IN WRONG FIELD")
print("="*80)

# Show before
cur.execute("SELECT employee_id, employee_number, quickbooks_id, full_name FROM employees WHERE employee_id = 145")
before = cur.fetchone()
print(f"\nBEFORE:")
print(f"  ID: {before[0]}")
print(f"  employee_number: {before[1]}")
print(f"  quickbooks_id: {before[2]}")
print(f"  full_name: {before[3]}")

# Fix: The QB ID is in employee_number, should be set to DR143
cur.execute("UPDATE employees SET employee_number = 'DR143' WHERE employee_id = 145")
conn.commit()

# Show after
cur.execute("SELECT employee_id, employee_number, quickbooks_id, full_name FROM employees WHERE employee_id = 145")
after = cur.fetchone()
print(f"\nAFTER:")
print(f"  ID: {after[0]}")
print(f"  employee_number: {after[1]}")
print(f"  quickbooks_id: {after[2]}")
print(f"  full_name: {after[3]}")

print(f"\n✅ Fixed: Changed employee_number from QB ID to DR143")
print("="*80 + "\n")

conn.close()
