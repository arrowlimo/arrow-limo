import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check fuel receipts with correct GL code
cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code = '5306'")
count_5306 = cur.fetchone()[0]
print(f"✅ Receipts with GL code 5306 (Fuel): {count_5306}")

# Check FAS GAS
cur.execute("SELECT COUNT(*), gl_account_code FROM receipts WHERE vendor_name LIKE '%FAS GAS%' GROUP BY gl_account_code ORDER BY COUNT(*) DESC")
print("\nFAS GAS GL codes:")
for count, gl_code in cur.fetchall()[:10]:
    print(f"  {gl_code or 'NULL'}: {count} receipts")

# Check PETRO CANADA
cur.execute("SELECT COUNT(*), gl_account_code FROM receipts WHERE vendor_name LIKE '%PETRO%CANADA%' GROUP BY gl_account_code ORDER BY COUNT(*) DESC")
print("\nPETRO CANADA GL codes:")
for count, gl_code in cur.fetchall()[:10]:
    print(f"  {gl_code or 'NULL'}: {count} receipts")

# Check SHELL
cur.execute("SELECT COUNT(*), gl_account_code FROM receipts WHERE vendor_name LIKE '%SHELL%' GROUP BY gl_account_code ORDER BY COUNT(*) DESC")
print("\nSHELL GL codes:")
for count, gl_code in cur.fetchall()[:10]:
    print(f"  {gl_code or 'NULL'}: {count} receipts")

cur.close()
conn.close()
