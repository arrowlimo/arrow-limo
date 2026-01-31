import psycopg2

VENDOR_PATTERNS = [
    '%mcdonald%',
    '%wendy%',
    '%tim hortons%',
    '%tim horton%',
    '%tim hortin%',
    '%sushi%',
    '%susi%',
    '%ciniplex%',
    '%cineplex%',
]

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

like_clauses = ["LOWER(vendor_name) LIKE %s" for _ in VENDOR_PATTERNS]
vendor_cond = "(" + " OR ".join(like_clauses) + ")"

cur.execute(f"""
    SELECT vendor_name, gl_account_code, gl_account_name, category, COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE {vendor_cond}
    GROUP BY vendor_name, gl_account_code, gl_account_name, category
    ORDER BY SUM(gross_amount) DESC
""", VENDOR_PATTERNS)

print("Personal-food candidate receipts (fast food / coffee / sushi / cineplex):")
print(f"{'Vendor':<40} {'GL':<8} {'GL Name':<35} {'Category':<25} {'Count':>6} {'Amount':>12}")
print('-'*140)

total_count = 0
total_amount = 0
for r in cur.fetchall():
    total_count += r[4]
    total_amount += r[5] or 0
    print(f"{r[0][:39]:<40} {str(r[1] or 'NULL'):<8} {str(r[2] or '')[:34]:<35} {str(r[3] or '')[:24]:<25} {r[4]:>6} ${r[5]:>11,.2f}")

print('-'*140)
print(f"Total: {total_count} receipts, ${total_amount:,.2f}")

# Show distinct vendors
print("\nDistinct vendor names:")
cur.execute(f"""
    SELECT vendor_name, COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE {vendor_cond}
    GROUP BY vendor_name
    ORDER BY SUM(gross_amount) DESC
""", VENDOR_PATTERNS)
for r in cur.fetchall():
    print(f"  {r[0]:<40} {r[1]:>5} receipts, ${r[2]:>11,.2f}")

cur.close()
conn.close()
