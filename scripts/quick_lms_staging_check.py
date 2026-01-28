"""Quick LMS staging analysis - basic counts only."""
import os, psycopg2

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REMOVED***')
)
cur = conn.cursor()

print("LMS STAGING TABLES - QUICK ANALYSIS")
print("=" * 60)

# Customers
cur.execute("SELECT COUNT(*) FROM lms_staging_customer")
cust_staging = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM clients")
cust_prod = cur.fetchone()[0]

print(f"Customers: {cust_staging:,} staging | {cust_prod:,} production")

# Payments  
cur.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM lms_staging_payment")
pmt_staging, pmt_staging_total = cur.fetchone()

cur.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM payments")
pmt_prod, pmt_prod_total = cur.fetchone()

print(f"Payments: {pmt_staging:,} staging (${pmt_staging_total:,.2f}) | {pmt_prod:,} production (${pmt_prod_total:,.2f})")

# Reserves
cur.execute("SELECT COUNT(*) FROM lms_staging_reserve")
res_staging = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM charters")
res_prod = cur.fetchone()[0]

print(f"Reserves: {res_staging:,} staging | {res_prod:,} production (charters)")

print("\n" + "=" * 60)
print(f"COMPARISON:")
if cust_staging < cust_prod and pmt_staging < pmt_prod and res_staging < res_prod:
    print("✓ Production has MORE data than staging")
    print("  Likely: Staging is old snapshot, production is current")
    print("  Recommendation: ARCHIVE staging tables")
elif cust_staging > cust_prod or pmt_staging > pmt_prod or res_staging > res_prod:
    print("⚠ Staging has MORE data than production!")
    print("  Requires detailed duplicate analysis")
else:
    print("~ Similar counts - need detailed matching analysis")

cur.close()
conn.close()
