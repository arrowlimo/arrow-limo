import os, psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REDACTED***')
)
cur = conn.cursor()

print("=" * 80)
print("QB_TRANSACTIONS_STAGING ANALYSIS - 983K Rows")
print("=" * 80)

# 1. Basic stats
print("\n1. BASIC STATISTICS")
print("-" * 80)
cur.execute("""
    SELECT 
        COUNT(*) as total_rows,
        COUNT(DISTINCT txn_date) as unique_dates,
        MIN(txn_date) as earliest_date,
        MAX(txn_date) as latest_date,
        SUM(amount) FILTER (WHERE amount > 0) as total_positive,
        SUM(amount) FILTER (WHERE amount < 0) as total_negative,
        SUM(amount) as net_total
    FROM qb_transactions_staging
""")

total, dates, min_date, max_date, positive, negative, net = cur.fetchone()
print(f"Total rows: {total:,}")
print(f"Unique dates: {dates:,}")
print(f"Date range: {min_date} to {max_date}")
print(f"Total positive amounts: ${positive or 0:,.2f}")
print(f"Total negative amounts: ${negative or 0:,.2f}")
print(f"Net total: ${net or 0:,.2f}")

# 2. Check columns
print("\n2. TABLE STRUCTURE")
print("-" * 80)
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'qb_transactions_staging'
    ORDER BY ordinal_position
""")

cols = cur.fetchall()
print(f"Columns ({len(cols)}):")
for col, dtype in cols:
    print(f"  {col:<30} {dtype}")

# 3. Check for duplicates in existing tables
print("\n3. COMPARISON WITH EXISTING TABLES")
print("-" * 80)

# Check journal table (case-sensitive column name)
cur.execute('SELECT COUNT(*), MIN("Date"), MAX("Date") FROM journal')
j_count, j_min, j_max = cur.fetchone()
print(f"\njournal table:")
print(f"  Rows: {j_count:,}")
print(f"  Date range: {j_min} to {j_max}")

# Check unified_general_ledger
cur.execute("SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date) FROM unified_general_ledger")
ugl_count, ugl_min, ugl_max = cur.fetchone()
print(f"\nunified_general_ledger table:")
print(f"  Rows: {ugl_count:,}")
print(f"  Date range: {ugl_min} to {ugl_max}")

# 4. Date overlap analysis
print("\n4. DATE OVERLAP ANALYSIS")
print("-" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as staging_in_journal_range,
        COUNT(*) FILTER (WHERE txn_date < %s) as before_journal,
        COUNT(*) FILTER (WHERE txn_date > %s) as after_journal
    FROM qb_transactions_staging
""", (j_min, j_max))

in_range, before, after = cur.fetchone()
print(f"Staging transactions in journal date range ({j_min} to {j_max}):")
print(f"  In range: {in_range:,} ({in_range/total*100:.1f}%)")
print(f"  Before journal start: {before:,}")
print(f"  After journal end: {after:,}")

# 5. Sample transactions
print("\n5. SAMPLE TRANSACTIONS")
print("-" * 80)
cur.execute("""
    SELECT id, txn_date, entry_name, description, amount, source_zip
    FROM qb_transactions_staging
    ORDER BY txn_date DESC
    LIMIT 10
""")

print("Recent 10 transactions:")
for row in cur.fetchall():
    tid, date, entry, desc, amt, source = row
    print(f"  {date} | {entry or 'N/A':<30} | ${amt or 0:>10,.2f} | {source or 'N/A'}")
    if desc:
        print(f"    Desc: {desc[:70]}")

# 6. Entry name distribution  
print("\n6. ENTRY NAME DISTRIBUTION (Source files)")
print("-" * 80)
cur.execute("""
    SELECT entry_name, COUNT(*) as cnt, SUM(amount) as total_amt
    FROM qb_transactions_staging
    GROUP BY entry_name
    ORDER BY cnt DESC
    LIMIT 15
""")

print(f"{'Entry Name':<50} {'Count':>10} {'Total':>15}")
print("-" * 80)
for entry, cnt, amt in cur.fetchall():
    print(f"{(entry or 'NULL'):<50} {cnt:>10,} ${amt or 0:>13,.2f}")

# 7. Source ZIP distribution
print("\n7. SOURCE ZIP FILES")
print("-" * 80)
cur.execute("""
    SELECT source_zip, COUNT(*) as cnt
    FROM qb_transactions_staging
    WHERE source_zip IS NOT NULL
    GROUP BY source_zip
    ORDER BY cnt DESC
    LIMIT 20
""")

for source, cnt in cur.fetchall():
    print(f"  {source:<70} {cnt:>8,} txns")

# 8. Year-over-year breakdown
print("\n8. YEARLY BREAKDOWN")
print("-" * 80)
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM txn_date) as year,
        COUNT(*) as txns,
        SUM(amount) FILTER (WHERE amount > 0) as positive,
        SUM(amount) FILTER (WHERE amount < 0) as negative
    FROM qb_transactions_staging
    WHERE txn_date IS NOT NULL
    GROUP BY year
    ORDER BY year
""")

print(f"{'Year':<6} {'Transactions':>12} {'Positive':>15} {'Negative':>15}")
print("-" * 55)
for year, cnt, pos, neg in cur.fetchall():
    print(f"{int(year) if year else 'NULL':<6} {cnt:>12,} ${pos or 0:>13,.2f} ${neg or 0:>13,.2f}")

print("\n" + "=" * 80)
print("RECOMMENDATIONS")
print("=" * 80)
print("""
Based on analysis:

1. Date Range Check:
   - Compare staging date range vs journal/unified_general_ledger
   - Identify if staging has NEW data or is duplicate

2. Duplicate Detection:
   - Check if transactions already exist in journal
   - Compare transaction amounts, dates, accounts

3. Promotion Strategy Options:
   A. If NEW data → Promote to unified_general_ledger
   B. If DUPLICATE → Archive and mark as processed
   C. If MIXED → Selective promotion of new records only

4. Next Steps:
   - Run duplicate detection query
   - Determine promotion vs archive
   - Create migration script if promoting
""")

cur.close()
conn.close()
