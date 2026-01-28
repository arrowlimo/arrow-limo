import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REMOVED***",
    host="localhost"
)

cur = conn.cursor()

print("=" * 80)
print("SEARCHING FOR RECEIPT-RELATED TABLES")
print("=" * 80)

# Find all receipt-related tables
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name LIKE '%receipt%'
    ORDER BY table_name
""")

tables = cur.fetchall()
print(f"\nFound {len(tables)} receipt-related tables:")
for table in tables:
    print(f"  - {table[0]}")

# Check for staging tables
print("\n" + "=" * 80)
print("CHECKING RECEIPT STAGING TABLE")
print("=" * 80)

if any('staging' in t[0] for t in tables):
    staging_table = [t[0] for t in tables if 'staging' in t[0]][0]
    print(f"\nFound staging table: {staging_table}")
    
    # Get row count
    cur.execute(f"SELECT COUNT(*) FROM {staging_table}")
    count = cur.fetchone()[0]
    print(f"Row count: {count:,}")
    
    # Get columns
    cur.execute(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = '{staging_table}'
        ORDER BY ordinal_position
    """)
    print(f"\nColumns in {staging_table}:")
    for col in cur.fetchall():
        print(f"  {col[0]:30} {col[1]}")
    
    # Check for card data
    cur.execute(f"""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN card_number IS NOT NULL AND card_number != '' THEN 1 END) as has_card_number,
            COUNT(CASE WHEN card_type IS NOT NULL AND card_type != '' THEN 1 END) as has_card_type,
            COUNT(CASE WHEN pay_method IS NOT NULL AND pay_method != '' THEN 1 END) as has_pay_method
        FROM {staging_table}
    """)
    row = cur.fetchone()
    if row:
        total, card_num, card_type, pay_meth = row
        print(f"\nCard data in {staging_table}:")
        print(f"  Total rows:          {total:6,}")
        print(f"  With card_number:    {card_num:6,} ({100*card_num/total if total > 0 else 0:5.1f}%)")
        print(f"  With card_type:      {card_type:6,} ({100*card_type/total if total > 0 else 0:5.1f}%)")
        print(f"  With pay_method:     {pay_meth:6,} ({100*pay_meth/total if total > 0 else 0:5.1f}%)")
    
    # Sample rows with card data
    cur.execute(f"""
        SELECT 
            id,
            receipt_date,
            vendor_name,
            gross_amount,
            card_number,
            card_type,
            pay_method
        FROM {staging_table}
        WHERE card_number IS NOT NULL AND card_number != ''
        LIMIT 10
    """)
    results = cur.fetchall()
    if results:
        print(f"\nSample rows from {staging_table} with card data:")
        print(f"{'ID':6} {'Date':12} {'Vendor':25} {'Amount':12} {'Card#':6} {'Type':10} {'PayMethod':10}")
        print("-" * 95)
        for row in results:
            rid, date, vendor, amount, card_num, card_type, pay_meth = row
            vendor = (vendor or '')[:24]
            card_type = (card_type or '')[:9]
            pay_meth = (pay_meth or '')[:9]
            print(f"{rid:6} {str(date):12} {vendor:25} ${amount:10,.2f} {card_num:6} {card_type:10} {pay_meth:10}")
else:
    print("\nNo receipt staging table found!")
    print("\nAll receipt-related tables:")
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cur.fetchone()[0]
        print(f"  {table[0]:30} {count:8,} rows")

cur.close()
conn.close()
