import psycopg2

conn = psycopg2.connect(
    host='localhost',
    user='postgres',
    password='***REMOVED***',
    database='almsdata'
)
cur = conn.cursor()

# Check if QB export views exist
cur.execute("""
    SELECT table_name FROM information_schema.views 
    WHERE table_schema = 'public' AND table_name LIKE 'qb_export_%'
    ORDER BY table_name
""")

views = cur.fetchall()
cur.close()
conn.close()

if views:
    print(f"✅ QuickBooks Export Views EXIST ({len(views)} views):")
    for view in views:
        print(f"   - {view[0]}")
else:
    print("❌ QuickBooks Export Views NOT FOUND")
    print("\nYou need to run the migration:")
    print("   migrations/create_quickbooks_export_views.sql")
