#!/usr/bin/env python
import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REMOVED***')
cur = conn.cursor()

print("="*80)
print("LEGACY VIEW ANALYSIS")
print("="*80)

# Check the views' source code
cur.execute("""
    SELECT table_name, view_definition
    FROM information_schema.views
    WHERE table_name IN ('customer_name_resolver', 'client_directory', 'service_preferences')
""")

for view, defn in cur.fetchall():
    print(f"\nVIEW: {view}")
    print("-" * 80)
    print(defn[:600])
    if len(defn) > 600:
        print("... (truncated)")

# Check row counts
print("\n" + "="*80)
print("DATA COUNTS")
print("="*80)

cur.execute("SELECT COUNT(*) FROM customer_name_resolver")
print(f"customer_name_resolver rows: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM customer_name_mapping")
print(f"customer_name_mapping rows: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM lms_customers_enhanced")
print(f"lms_customers_enhanced rows: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM clients")
print(f"clients rows: {cur.fetchone()[0]}")

cur.close()
conn.close()
