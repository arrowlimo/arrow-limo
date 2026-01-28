import psycopg2

conn = psycopg2.connect(host='localhost', port='5432', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("=" * 60)
print("SCHEMA VALIDATION FOR PROBLEMATIC COLUMNS")
print("=" * 60)

# Check charters table
print("\nCHARTERS table columns:")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='charters' ORDER BY ordinal_position")
cols = [c[0] for c in cur.fetchall()]
check_cols = ['driver_id', 'customer_id', 'vehicle_id', 'client_id']
for col in check_cols:
    status = "✅ EXISTS" if col in cols else "❌ MISSING"
    print(f"  {col:20} {status}")

# Check employees table
print("\nEMPLOYEES table columns:")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='employees' ORDER BY ordinal_position")
cols = [c[0] for c in cur.fetchall()]
check_cols = ['employee_type', 'is_chauffeur', 'employee_id', 'full_name']
for col in check_cols:
    status = "✅ EXISTS" if col in cols else "❌ MISSING"
    print(f"  {col:20} {status}")

# Check clients/customers table
print("\nCLIENTS table columns:")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='clients' ORDER BY ordinal_position")
cols = [c[0] for c in cur.fetchall()]
check_cols = ['customer_name', 'client_name', 'company_name', 'client_id']
for col in check_cols:
    status = "✅ EXISTS" if col in cols else "❌ MISSING"
    print(f"  {col:20} {status}")

# Check vehicles table
print("\nVEHICLES table columns:")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='vehicles' ORDER BY ordinal_position")
cols = [c[0] for c in cur.fetchall()]
check_cols = ['vehicle_type', 'purchase_date', 'assigned_to', 'vehicle_id']
for col in check_cols:
    status = "✅ EXISTS" if col in cols else "❌ MISSING"
    print(f"  {col:20} {status}")

# Check driver_payroll table
print("\nDRIVER_PAYROLL table columns:")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='driver_payroll' ORDER BY ordinal_position LIMIT 15")
cols = [c[0] for c in cur.fetchall()]
print(f"  Columns (first 15): {', '.join(cols)}")

cur.close()
conn.close()
print("\n" + "=" * 60)
