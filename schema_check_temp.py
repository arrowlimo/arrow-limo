import psycopg2

conn = psycopg2.connect(
    host='localhost', port='5432', database='almsdata',
    user='postgres', password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 60)
print("CHARTERS COLUMNS (first 20):")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='charters' ORDER BY ordinal_position LIMIT 20")
for col in cur.fetchall():
    print(f"  - {col[0]}")

print("\n" + "=" * 60)
print("RECEIPTS COLUMNS - KEY ONES:")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='receipts' ORDER BY ordinal_position")
all_cols = [c[0] for c in cur.fetchall()]
keywords = ['category', 'expense_account', 'account', 'vendor', 'description', 'amount', 'gross', 'gst']
for col in all_cols[:15]:
    print(f"  - {col}")
print("  ... (first 15 shown)")
found_key = False
for col in all_cols:
    if any(kw in col.lower() for kw in keywords) and col not in all_cols[:15]:
        if not found_key:
            print("\nKeyword matches:")
            found_key = True
        print(f"  - {col}")

cur.close()
conn.close()
print("\n" + "=" * 60)
