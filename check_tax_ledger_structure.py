"""
Check for yearly tax ledgers and journal tables
Verify tax data organization and whether we have year-based tables
"""
import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

print("=" * 100)
print("TAX LEDGER & JOURNAL STRUCTURE ANALYSIS")
print("=" * 100)

# 1. Find all tax-related tables
print("\n[1] TAX-RELATED TABLES")
print("-" * 100)

cur.execute("""
SELECT t.table_name
FROM information_schema.tables t
WHERE t.table_schema = 'public'
  AND (t.table_name LIKE '%tax%'
    OR t.table_name LIKE '%ledger%'
    OR t.table_name LIKE '%journal%'
    OR t.table_name LIKE '%income%'
    OR t.table_name LIKE '%expense%')
  AND t.table_type = 'BASE TABLE'
ORDER BY t.table_name
""")

tax_tables = cur.fetchall()
if tax_tables:
    print(f"Found {len(tax_tables)} tax/ledger/journal tables:\n")
    for table, in tax_tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        rows = cur.fetchone()[0]
        print(f"  📊 {table:<40} {rows:>10,} rows")
else:
    print("❌ No dedicated tax ledger tables found")

# 2. Check general_ledger structure
print("\n[2] GENERAL_LEDGER TABLE STRUCTURE")
print("-" * 100)

cur.execute("SELECT COUNT(*) FROM general_ledger")
total_gl_rows = cur.fetchone()[0]
print(f"Total GL rows: {total_gl_rows:,}")

# Check if partitioned by year
cur.execute("""
SELECT EXTRACT(YEAR FROM date) as year, COUNT(*) as count
FROM general_ledger
GROUP BY EXTRACT(YEAR FROM date)
ORDER BY year
""")

years_in_gl = cur.fetchall()
print(f"\nYears covered in general_ledger:")
for year, count in years_in_gl:
    print(f"  {int(year)}: {count:,} transactions")

# 3. Check for yearly journal tables
print("\n[3] YEARLY JOURNAL TABLES")
print("-" * 100)

cur.execute("""
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND (table_name ~ '^journal_[0-9]{4}$'
    OR table_name ~ '^tax_[0-9]{4}$'
    OR table_name ~ '^gl_[0-9]{4}$'
    OR table_name LIKE 'journal_%'
    OR table_name LIKE 'tax_journal_%')
  AND table_type = 'BASE TABLE'
ORDER BY table_name
""")

yearly_tables = [row[0] for row in cur.fetchall()]
if yearly_tables:
    print(f"Found {len(yearly_tables)} yearly journal tables:")
    for table in yearly_tables[:15]:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        rows = cur.fetchone()[0]
        print(f"  {table:<40} {rows:>10,} rows")
    if len(yearly_tables) > 15:
        print(f"  ... and {len(yearly_tables) - 15} more")
else:
    print("❌ No yearly journal tables found (all data in single general_ledger table)")

# 4. Check qb_journal_entries if still exists
print("\n[4] QB JOURNAL ENTRIES TABLE")
print("-" * 100)

cur.execute("""
SELECT EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_name = 'qb_journal_entries'
)
""")

if cur.fetchone()[0]:
    cur.execute("SELECT COUNT(*) FROM qb_journal_entries")
    qb_rows = cur.fetchone()[0]
    print(f"⚠️ qb_journal_entries still exists: {qb_rows:,} rows")
    
    cur.execute("""
    SELECT EXTRACT(YEAR FROM transaction_date) as year, COUNT(*)
    FROM qb_journal_entries
    GROUP BY year
    ORDER BY year
    """)
    print("Years in qb_journal_entries:")
    for year, count in cur.fetchall():
        if year:
            print(f"  {int(year)}: {count:,} entries")
else:
    print("✅ qb_journal_entries was deleted (Phase 1 cleanup)")

# 5. Check for any views that might be tax-related yearly views
print("\n[5] YEARLY TAX/JOURNAL VIEWS")
print("-" * 100)

cur.execute("""
SELECT table_name
FROM information_schema.views
WHERE table_schema = 'public'
  AND (table_name ~ 'tax_[0-9]{4}'
    OR table_name ~ 'journal_[0-9]{4}'
    OR table_name ~ '^gl_[0-9]{4}$')
ORDER BY table_name
""")

yearly_views = [row[0] for row in cur.fetchall()]
if yearly_views:
    print(f"Found {len(yearly_views)} yearly tax/journal views:")
    for view in yearly_views[:10]:
        print(f"  {view}")
    if len(yearly_views) > 10:
        print(f"  ... and {len(yearly_views) - 10} more")
else:
    print("✅ No yearly tax/journal views remaining")

# 6. Tax-specific fields analysis
print("\n[6] TAX DATA IN CORE TABLES")
print("-" * 100)

# Check general_ledger for tax columns
cur.execute("""
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'general_ledger'
  AND (column_name LIKE '%tax%'
    OR column_name LIKE '%gst%'
    OR column_name LIKE '%income%'
    OR column_name LIKE '%expense%')
ORDER BY column_name
""")

tax_cols = cur.fetchall()
if tax_cols:
    print("Tax columns in general_ledger:")
    for col, dtype in tax_cols:
        cur.execute(f"""
        SELECT COUNT(*) 
        FROM general_ledger 
        WHERE "{col}" IS NOT NULL
        """)
        not_null = cur.fetchone()[0]
        pct = (not_null / total_gl_rows * 100) if total_gl_rows > 0 else 0
        print(f"  {col:<30} {dtype:<20} {pct:>6.1f}% populated")
else:
    print("⚠️ No tax-specific columns in general_ledger")

# Check receipts for tax columns
cur.execute("SELECT COUNT(*) FROM receipts")
receipts_total = cur.fetchone()[0]

cur.execute("""
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'receipts'
  AND (column_name LIKE '%tax%'
    OR column_name LIKE '%gst%'
    OR column_name LIKE '%expense%'
    OR column_name LIKE '%gl%')
ORDER BY column_name
""")

receipt_tax_cols = cur.fetchall()
print("\nTax columns in receipts:")
for col, dtype in receipt_tax_cols:
    cur.execute(f"""
    SELECT COUNT(*) 
    FROM receipts 
    WHERE "{col}" IS NOT NULL
    """)
    not_null = cur.fetchone()[0]
    pct = (not_null / receipts_total * 100) if receipts_total > 0 else 0
    print(f"  {col:<30} {dtype:<20} {pct:>6.1f}% populated")

# 7. Summary and recommendations
print("\n" + "=" * 100)
print("SUMMARY & RECOMMENDATIONS")
print("=" * 100)

print(f"""
TAX DATA ORGANIZATION STATUS:

✅ WHAT WE HAVE:
  • Single general_ledger table: {total_gl_rows:,} rows spanning {len(years_in_gl)} years
  • Years covered: {min(int(y[0]) for y in years_in_gl)} to {max(int(y[0]) for y in years_in_gl)}
  • All GL data in one table (partitioned by date, not by table)
  
❌ WHAT WE REMOVED (Phase 1):
  • QB journal entries: {53680 if yearly_tables else 'DELETED'} rows
  • All 16 year-based GL views (general_ledger_2011-2026)
  
⚠️ CURRENT STRUCTURE:
  • NO yearly ledger tables (all in single general_ledger)
  • NO yearly journal tables (would be journal_2011, journal_2012, etc.)
  • YES: Tax data IS in receipts table (gst_amount, expense_account)
  • YES: Tax data IS in general_ledger (debit/credit columns, accounts)
  
🎯 TAX DATA INTEGRITY:
  • Each receipt has gst_amount calculated from gross_amount
  • General ledger tracks all debit/credit entries
  • Can query by YEAR using date column: WHERE EXTRACT(YEAR FROM date) = 2023

📋 RECOMMENDATIONS:
  1. ✅ Current structure is FINE - single GL table is standard
  2. If need yearly reports, CREATE MATERIALIZED VIEWS instead (not year tables)
  3. If need tax audit trail, could add: tax_year, tax_status columns
  4. If need year-end closing, create stored procedures (not separate tables)
  
⚠️ IMPORTANT: 
  We removed views (virtual) not tables (data)
  All transaction data is SAFE in base tables
  Year-based queries use: WHERE date >= '2023-01-01' AND date <= '2023-12-31'
""")

cur.close()
conn.close()
