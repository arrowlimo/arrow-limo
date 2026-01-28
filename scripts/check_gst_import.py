"""Quick check of imported GST data"""
import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute("""
    SELECT reserve_number, reserve_date, gst_taxable, gst_amount, total_amount, source_sheet 
    FROM charter_gst_details_2010_2012 
    ORDER BY reserve_number 
    LIMIT 10
""")

print('Sample imported GST records:')
print(f"{'Reserve':<10} {'Date':<12} {'GST Taxable':<15} {'GST Amount':<12} {'Total':<12} {'Sheet'}")
print('-' * 85)
for r in cur.fetchall():
    print(f"{r[0]:<10} {str(r[1]):<12} ${r[2] or 0:<14,.2f} ${r[3] or 0:<11,.2f} ${r[4] or 0:<11,.2f} {r[5]}")

# Check year distribution
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM reserve_date) as yr,
        source_sheet,
        COUNT(*) 
    FROM charter_gst_details_2010_2012 
    GROUP BY yr, source_sheet
    ORDER BY yr, source_sheet
""")

print('\nRecords by year and sheet:')
for r in cur.fetchall():
    print(f"  {int(r[0]) if r[0] else 'NULL'}: {r[1]} - {r[2]} records")

cur.close()
conn.close()
