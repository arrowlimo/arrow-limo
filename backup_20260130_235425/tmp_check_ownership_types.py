import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=ArrowLimousine')
cur = conn.cursor()
cur.execute("""
    SELECT unnest(enum_range(NULL::asset_ownership_type))
""")
print("Valid asset_ownership_type values:")
for row in cur.fetchall():
    print(f"  - {row[0]}")
