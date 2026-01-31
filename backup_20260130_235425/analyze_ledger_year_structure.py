#!/usr/bin/env python
"""Check current ledger/accounting table structures and year distribution."""
import psycopg2
import os

DB_HOST=os.environ.get("DB_HOST","localhost")
DB_NAME=os.environ.get("DB_NAME","almsdata")
DB_USER=os.environ.get("DB_USER","postgres")
DB_PASSWORD=os.environ.get("DB_PASSWORD",os.environ.get("DB_PASSWORD"))

conn=psycopg2.connect(host=DB_HOST,database=DB_NAME,user=DB_USER,password=DB_PASSWORD)
cur=conn.cursor()

print("\n"+"="*100)
print("LEDGER & ACCOUNTING TABLE ANALYSIS")
print("="*100)
print()

# Find all ledger-related tables
cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema='public'
      AND (table_name LIKE '%ledger%' OR table_name LIKE '%journal%' OR table_name LIKE '%gl%')
    ORDER BY table_name
""")
ledger_tables = [row[0] for row in cur.fetchall()]

print("LEDGER/ACCOUNTING TABLES FOUND:")
print("-" * 100)
for tbl in ledger_tables:
    cur.execute(f"SELECT COUNT(*) FROM {tbl}")
    cnt = cur.fetchone()[0]
    print(f"  - {tbl}: {cnt:,} rows")
print()

# Check if any have year-based partitioning
print("\nCHECKING FOR YEAR-BASED STRUCTURES:")
print("-" * 100)

for tbl in ledger_tables:
    # Get columns
    cur.execute(f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name='{tbl}'
        ORDER BY ordinal_position
    """)
    cols = cur.fetchall()
    
    # Check if there's a year column
    has_year = any('year' in col[0].lower() for col in cols)
    
    # Check for date columns
    date_cols = [col[0] for col in cols if 'date' in col[1].lower() or col[1] in ('date', 'timestamp', 'timestamptz')]
    
    print(f"\n{tbl}:")
    print(f"  Columns: {len(cols)}")
    print(f"  Has 'year' column: {has_year}")
    print(f"  Date columns: {date_cols}")
    
    if date_cols and len(date_cols) > 0:
        # Get year distribution from first date column
        date_col = date_cols[0]
        try:
            cur.execute(f"""
                SELECT EXTRACT(YEAR FROM {date_col})::int as yr, COUNT(*), SUM(CASE WHEN amount IS NOT NULL THEN amount ELSE 0 END)
                FROM {tbl}
                WHERE {date_col} IS NOT NULL
                GROUP BY yr
                ORDER BY yr
            """)
            year_dist = cur.fetchall()
            if year_dist:
                print(f"  Year distribution ({date_col}):")
                for yr, cnt, amt in year_dist:
                    print(f"    {yr}: {cnt:,} rows | ${amt:,.2f}")
        except Exception as e:
            conn.rollback()
            # Try without amount
            try:
                cur.execute(f"""
                    SELECT EXTRACT(YEAR FROM {date_col})::int as yr, COUNT(*)
                    FROM {tbl}
                    WHERE {date_col} IS NOT NULL
                    GROUP BY yr
                    ORDER BY yr
                """)
                year_dist = cur.fetchall()
                if year_dist:
                    print(f"  Year distribution ({date_col}):")
                    for yr, cnt in year_dist:
                        print(f"    {yr}: {cnt:,} rows")
            except:
                conn.rollback()

# Check main receipts table year distribution
print("\n\n" + "="*100)
print("RECEIPTS TABLE YEAR DISTRIBUTION")
print("="*100)
cur.execute("""
    SELECT EXTRACT(YEAR FROM receipt_date)::int as yr,
           COUNT(*),
           SUM(gross_amount),
           COUNT(DISTINCT gl_account_code)
    FROM receipts
    WHERE receipt_date IS NOT NULL
    GROUP BY yr
    ORDER BY yr
""")
print("\nYear | Receipts | Total Amount | Unique GL Codes")
print("-" * 100)
for yr, cnt, amt, gl_cnt in cur.fetchall():
    print(f"{yr} | {cnt:>8,} | ${amt:>15,.2f} | {gl_cnt:>3}")

# Check banking_transactions year distribution
print("\n\n" + "="*100)
print("BANKING_TRANSACTIONS TABLE YEAR DISTRIBUTION")
print("="*100)
cur.execute("""
    SELECT EXTRACT(YEAR FROM transaction_date)::int as yr,
           COUNT(*),
           SUM(COALESCE(debit_amount,0) + COALESCE(credit_amount,0))
    FROM banking_transactions
    WHERE transaction_date IS NOT NULL
    GROUP BY yr
    ORDER BY yr
""")
print("\nYear | Transactions | Total Amount")
print("-" * 100)
for yr, cnt, amt in cur.fetchall():
    print(f"{yr} | {cnt:>11,} | ${amt:>15,.2f}")

# Check if we should have year-based partitioning
print("\n\n" + "="*100)
print("RECOMMENDATION: YEAR-BASED ACCOUNTING SEPARATION")
print("="*100)
print("""
Standard accounting practice: Separate books/ledgers per fiscal year

Current structure: Single tables with all years mixed together

PROS of year-based separation:
  ✅ Easier tax filing (isolate one year's transactions)
  ✅ Faster queries (smaller table scans)
  ✅ Clear audit trail (close books at year-end)
  ✅ Simplify period-end reconciliation
  ✅ Better backup/restore (archive old years)

CONS of year-based separation:
  ❌ More complex cross-year reporting
  ❌ Need views/unions for multi-year queries
  ❌ More table maintenance

OPTIONS:
  1. Keep current structure (single tables, filter by year in queries)
     - Simpler, current approach
     - Use views for year-specific reporting
  
  2. Create year-based VIEWS (receipts_2024, receipts_2025, etc.)
     - Best of both worlds
     - Underlying data stays in one table
     - Year-specific views for accounting
  
  3. Create year-based TABLES with partitioning
     - PostgreSQL native partitioning
     - Automatic routing to year partition
     - More complex setup
  
  4. Create separate year-based TABLES manually
     - Most work, least flexible
     - Only if required by accounting software

RECOMMENDATION: Option 2 - Create year-based VIEWS
  - receipts_2024, receipts_2025, etc.
  - banking_transactions_2024, banking_transactions_2025, etc.
  - Easy to export year-specific data for tax/audit
  - Keep single source of truth in main tables
""")

cur.close(); conn.close()
