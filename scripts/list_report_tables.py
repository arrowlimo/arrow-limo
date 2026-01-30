import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)
cur = conn.cursor()

print("=" * 80)
print("EXISTING DATABASE TABLES")
print("=" * 80)
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema='public' AND table_type='BASE TABLE' 
    ORDER BY table_name
""")
tables = [r[0] for r in cur.fetchall()]
for t in tables:
    print(f"  • {t}")

print(f"\nTotal tables: {len(tables)}")

print("\n" + "=" * 80)
print("EXISTING DATABASE VIEWS")
print("=" * 80)
cur.execute("""
    SELECT table_name 
    FROM information_schema.views 
    WHERE table_schema='public' 
    ORDER BY table_name
""")
views = [r[0] for r in cur.fetchall()]
for v in views:
    print(f"  • {v}")

print(f"\nTotal views: {len(views)}")

# Check for report-relevant tables
print("\n" + "=" * 80)
print("FINANCIAL REPORTING TABLES/VIEWS")
print("=" * 80)

report_keywords = [
    'loan', 'fuel', 'maintenance', 'insurance', 'depreciation',
    'receivable', 'payable', 'aging', 'balance', 'income',
    'profit', 'loss', 'asset', 'liability', 'equity'
]

print("\nTables:")
for t in tables:
    if any(kw in t.lower() for kw in report_keywords):
        print(f"  ✓ {t}")

print("\nViews:")
for v in views:
    if any(kw in v.lower() for kw in report_keywords):
        print(f"  ✓ {v}")

conn.close()
