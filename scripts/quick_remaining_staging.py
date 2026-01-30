"""Quick analysis of remaining staging tables."""
import os, psycopg2

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REDACTED***')
)
cur = conn.cursor()

print("REMAINING STAGING TABLES - QUICK ANALYSIS")
print("=" * 70)

tables = [
    ('pdf_staging', 879),
    ('staging_receipts_raw', 821),
    ('staging_scotia_2012_verified', 759),
    ('qb_accounts_staging', 298),
    ('staging_banking_pdf_transactions', 269),
]

for table_name, expected_rows in tables:
    print(f"\n{table_name.upper()}")
    print("-" * 70)
    
    # Get schema
    cur.execute(f"""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = '{table_name}'
        ORDER BY ordinal_position
    """)
    
    cols = [r[0] for r in cur.fetchall()]
    print(f"Columns ({len(cols)}): {', '.join(cols[:10])}")
    if len(cols) > 10:
        print(f"  ... and {len(cols)-10} more")
    
    # Get row count and date range
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    actual_rows = cur.fetchone()[0]
    
    print(f"Rows: {actual_rows:,} (expected {expected_rows:,})")
    
    # Try to get date range
    date_cols = [c for c in cols if 'date' in c.lower() or 'created' in c.lower() or 'updated' in c.lower()]
    if date_cols:
        date_col = date_cols[0]
        cur.execute(f"SELECT MIN({date_col}), MAX({date_col}) FROM {table_name} WHERE {date_col} IS NOT NULL")
        result = cur.fetchone()
        if result and result[0]:
            print(f"Date range ({date_col}): {result[0]} to {result[1]}")
    
    # Sample a row
    cur.execute(f"SELECT * FROM {table_name} LIMIT 1")
    if cur.description:
        row = cur.fetchone()
        if row:
            print(f"Sample data preview:")
            for i, col in enumerate(cols[:5]):  # Show first 5 columns
                val = str(row[i])[:50] if row[i] else None
                print(f"  {col}: {val}")

print("\n" + "=" * 70)

cur.close()
conn.close()
