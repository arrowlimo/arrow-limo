"""
Check specifically for QuickBooks Online (QBO) imports vs LMS imports.
Determine if 2013-2015 have QBO data or only LMS data.
"""
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor(cursor_factory=RealDictCursor)

print("="*80)
print("DISTINGUISHING QBO vs LMS IMPORTS (2012-2015)")
print("="*80)

# Check patterns year by year
for year in [2012, 2013, 2014, 2015]:
    print(f"\n{year}:")
    print("-" * 60)
    
    # QBO specific
    cur.execute("""
        SELECT COUNT(*) as count, SUM(amount) as total
        FROM payments
        WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
        AND (notes ILIKE '%%QBO%%' OR notes ILIKE '%%QuickBooks Online%%')
    """, (year,))
    qbo = cur.fetchone()
    print(f"  QBO imports: {qbo['count']} (${qbo['total'] or 0:,.2f})")
    
    # LMS specific
    cur.execute("""
        SELECT COUNT(*) as count, SUM(amount) as total
        FROM payments
        WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
        AND notes ILIKE '%%Imported from LMS%%'
    """, (year,))
    lms = cur.fetchone()
    print(f"  LMS imports: {lms['count']} (${lms['total'] or 0:,.2f})")
    
    # Generic "Import" (not LMS, not QBO)
    cur.execute("""
        SELECT COUNT(*) as count, SUM(amount) as total
        FROM payments
        WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
        AND notes ILIKE '%%Import%%'
        AND notes NOT ILIKE '%%LMS%%'
        AND notes NOT ILIKE '%%QBO%%'
        AND notes NOT ILIKE '%%QuickBooks%%'
    """, (year,))
    generic = cur.fetchone()
    print(f"  Other imports: {generic['count']} (${generic['total'] or 0:,.2f})")
    
    # Sample notes if QBO exists
    if qbo['count'] > 0:
        cur.execute("""
            SELECT payment_id, payment_date, amount, payment_method,
                   SUBSTRING(notes, 1, 120) as note_sample
            FROM payments
            WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = %s
            AND (notes ILIKE '%%QBO%%' OR notes ILIKE '%%QuickBooks Online%%')
            LIMIT 5
        """, (year,))
        print(f"\n  Sample QBO notes:")
        for row in cur.fetchall():
            print(f"    {row['payment_id']}: ${row['amount']:.2f} - {row['note_sample']}")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) as year,
        COUNT(*) as qbo_count,
        SUM(amount) as qbo_total
    FROM payments
    WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) BETWEEN 2012 AND 2015
    AND (notes ILIKE '%%QBO%%' OR notes ILIKE '%%QuickBooks Online%%')
    GROUP BY EXTRACT(YEAR FROM CAST(payment_date AS timestamp))
    ORDER BY year
""")

qbo_years = cur.fetchall()

if qbo_years:
    print("\nQBO imports found in:")
    for row in qbo_years:
        print(f"  {int(row['year'])}: {row['qbo_count']} payments (${row['qbo_total']:,.2f})")
else:
    print("\nNo QBO imports found in 2012-2015")
    print("All 'Import' payments appear to be LMS imports")

print("\nRECOMMENDATION:")
if not qbo_years or (len(qbo_years) == 1 and qbo_years[0]['year'] == 2012):
    print("  QBO imports only exist in 2012 (already audited)")
    print("  2013-2015 use LMS imports which don't need QBO-specific audit")
    print("  → No further QBO audit needed for 2013-2015")
else:
    print("  QBO imports found in multiple years - continue with audit")

cur.close()
conn.close()
