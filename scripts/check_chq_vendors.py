import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Count plain "CHQ" entries
cur.execute("SELECT COUNT(*) FROM receipts WHERE vendor_name = 'CHQ'")
plain_chq = cur.fetchone()[0]

# Count "CHQ ###" with check number
cur.execute("SELECT COUNT(*) FROM receipts WHERE vendor_name LIKE 'CHQ %'")
chq_with_num = cur.fetchone()[0]

# Show examples
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description 
    FROM receipts 
    WHERE vendor_name = 'CHQ' 
    ORDER BY receipt_date DESC 
    LIMIT 10
""")
plain_examples = cur.fetchall()

print(f"📊 CHQ Vendor Analysis:")
print(f"  Plain 'CHQ' (missing check number): {plain_chq}")
print(f"  'CHQ ###' (with check number): {chq_with_num}")
print(f"  Total CHQ entries: {plain_chq + chq_with_num}")
print(f"\n❌ Examples of plain 'CHQ' entries (missing check number):")
for row in plain_examples:
    print(f"  ID {row[0]} | {row[1]} | {row[2]} | ${row[3]} | {row[4] or 'No description'}")

conn.close()
