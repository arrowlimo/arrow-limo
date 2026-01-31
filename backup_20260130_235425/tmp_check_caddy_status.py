import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=ArrowLimousine')
cur = conn.cursor()
cur.execute("""
    SELECT asset_id, asset_name, status, ownership_status 
    FROM assets 
    WHERE asset_name LIKE '%2015%' OR asset_name LIKE '%Cadillac%'
""")
print("2015 Caddy status in database:")
for row in cur.fetchall():
    print(f"  Asset ID: {row[0]}, Name: {row[1]}, Status: {row[2]}, Ownership: {row[3]}")
