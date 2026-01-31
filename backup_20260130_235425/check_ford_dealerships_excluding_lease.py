import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("WOODRIDGE FORD receipts (vehicle lease - should NOT be GL 5100):")
cur.execute("""
    SELECT receipt_date, gross_amount, gl_account_code, gl_account_name, category
    FROM receipts
    WHERE vendor_name = 'WOODRIDGE FORD'
    ORDER BY receipt_date DESC
    LIMIT 10
""")
for r in cur.fetchall():
    print(f"  {r[0]} - ${r[1]:>10,.2f} - GL {r[2] or 'NULL':>6} - {r[3] or ''} - {r[4] or ''}")

print(f"\nTotal WOODRIDGE FORD: {cur.execute('SELECT COUNT(*), SUM(gross_amount) FROM receipts WHERE vendor_name = %s', ('WOODRIDGE FORD',)) or cur.fetchone()}")
cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts WHERE vendor_name = %s", ('WOODRIDGE FORD',))
count, total = cur.fetchone()
print(f"Total WOODRIDGE FORD: {count} receipts, ${total:,.2f}")

print("\n" + "="*80)
print("\nActual Ford dealerships for GL 5100 (maintenance & repair):")
print("\nMGM FORD variants:")
cur.execute("""
    SELECT vendor_name, COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name LIKE 'MGM FORD%'
    GROUP BY vendor_name
""")
for r in cur.fetchall():
    print(f"  {r[0]:<40} {r[1]:>3} receipts, ${r[2]:>10,.2f}")

print("\nCAM CLARK FORD:")
cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts WHERE vendor_name = 'CAM CLARK FORD'")
count, total = cur.fetchone()
print(f"  {'CAM CLARK FORD':<40} {count:>3} receipts, ${total:>10,.2f}")

print("\nLACOMBE FORD:")
cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts WHERE vendor_name = 'LACOMBE FORD'")
count, total = cur.fetchone()
print(f"  {'LACOMBE FORD':<40} {count:>3} receipts, ${total:>10,.2f}")

# Total for actual dealerships
cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE (vendor_name LIKE 'MGM FORD%' OR vendor_name = 'CAM CLARK FORD' OR vendor_name = 'LACOMBE FORD')
      AND (gl_account_code != '5100' OR gl_account_code IS NULL)
""")
count, total = cur.fetchone()
print(f"\n{'Total needing GL 5100 update:':<40} {count:>3} receipts, ${total or 0:>10,.2f}")

cur.close()
conn.close()
