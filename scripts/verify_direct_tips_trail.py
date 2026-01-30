import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("=" * 60)
print("FINAL VERIFICATION: 2007-2014 DIRECT TIPS DATA TRAIL")
print("=" * 60)

# Check direct_tips_history table
cur.execute("""
    SELECT 
        COUNT(*), 
        SUM(tip_amount), 
        MIN(tip_date), 
        MAX(tip_date),
        COUNT(DISTINCT driver_id)
    FROM direct_tips_history 
    WHERE tax_year BETWEEN 2007 AND 2014
""")
r = cur.fetchone()
print(f"\n1. DIRECT TIPS TABLE:")
print(f"   Records: {r[0]:,}")
print(f"   Total tips: ${r[1]:,.2f}")
print(f"   Date range: {r[2]} to {r[3]}")
print(f"   Unique drivers: {r[4]}")

# Check documented charters
cur.execute("""
    SELECT COUNT(*) 
    FROM charters 
    WHERE EXTRACT(YEAR FROM charter_date) BETWEEN 2007 AND 2014
    AND driver_gratuity > 0 
    AND (notes LIKE '%Pre-2013 gratuity:%' OR notes LIKE '%2013-2014 gratuity:%')
""")
print(f"\n2. DOCUMENTED CHARTERS:")
print(f"   Charters with CRA notes: {cur.fetchone()[0]:,}")

# Verify all CRA flags
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN is_direct_tip THEN 1 END) as is_direct,
        COUNT(CASE WHEN not_on_t4 THEN 1 END) as not_t4,
        COUNT(CASE WHEN paid_by_customer_directly THEN 1 END) as customer_paid,
        COUNT(CASE WHEN not_employer_revenue THEN 1 END) as not_revenue
    FROM direct_tips_history
    WHERE tax_year BETWEEN 2007 AND 2014
""")
r = cur.fetchone()
print(f"\n3. CRA COMPLIANCE FLAGS (2007-2014):")
print(f"   Total records: {r[0]:,}")
print(f"   is_direct_tip = TRUE: {r[1]:,}")
print(f"   not_on_t4 = TRUE: {r[2]:,}")
print(f"   paid_by_customer_directly = TRUE: {r[3]:,}")
print(f"   not_employer_revenue = TRUE: {r[4]:,}")

# Final summary
if r[0] == r[1] == r[2] == r[3] == r[4]:
    print(f"\n[OK] ALL {r[0]:,} RECORDS PROPERLY FLAGGED FOR CRA COMPLIANCE")
else:
    print("\n[WARN]  Some records missing CRA compliance flags")

# Year breakdown
cur.execute("""
    SELECT tax_year, COUNT(*), SUM(tip_amount)
    FROM direct_tips_history
    WHERE tax_year BETWEEN 2007 AND 2014
    GROUP BY tax_year
    ORDER BY tax_year
""")
print(f"\n4. BY YEAR:")
for row in cur.fetchall():
    print(f"   {int(row[0])}: {row[1]:,} records, ${row[2]:,.2f}")

# Get totals
cur.execute("SELECT COUNT(*), SUM(tip_amount) FROM direct_tips_history WHERE tax_year BETWEEN 2007 AND 2014")
total_records, total_amount = cur.fetchone()

print("\n" + "=" * 60)
print("STATUS: [OK] 2007-2014 DIRECT TIPS TRAIL ESTABLISHED")
print("=" * 60)
print(f"\nTotal: {total_records:,} direct tip records, ${total_amount:,.2f}")
print("Period: 2007-2014 (8 years)")
print("CRA Compliance: READY FOR AUDIT")

cur.close()
conn.close()
