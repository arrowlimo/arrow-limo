#!/usr/bin/env python
"""Create year-based accounting views for all major tables.
This creates a separate view for each year (2011-2026) for:
- receipts_YYYY
- banking_transactions_YYYY
- general_ledger_YYYY
- payments_YYYY
- charters_YYYY
Plus summary views for year-over-year analysis.
"""
import psycopg2
import os

DB_HOST=os.environ.get("DB_HOST","localhost")
DB_NAME=os.environ.get("DB_NAME","almsdata")
DB_USER=os.environ.get("DB_USER","postgres")
DB_PASSWORD=os.environ.get("DB_PASSWORD","***REMOVED***")

conn=psycopg2.connect(host=DB_HOST,database=DB_NAME,user=DB_USER,password=DB_PASSWORD)
cur=conn.cursor()

print("\n"+"="*100)
print("CREATING YEAR-BASED ACCOUNTING VIEWS")
print("="*100)
print()

# Define year range (2011-2026 based on data analysis)
years = range(2011, 2027)

# Track created views
created_views = []

# 1. RECEIPTS YEAR VIEWS
print("1. Creating receipts_YYYY views...")
print("-" * 100)
for year in years:
    view_name = f"receipts_{year}"
    cur.execute(f"DROP VIEW IF EXISTS {view_name} CASCADE")
    cur.execute(f"""
        CREATE VIEW {view_name} AS
        SELECT *
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = {year}
    """)
    created_views.append(view_name)
    print(f"  ✅ {view_name}")

# 2. BANKING_TRANSACTIONS YEAR VIEWS
print("\n2. Creating banking_transactions_YYYY views...")
print("-" * 100)
for year in years:
    view_name = f"banking_transactions_{year}"
    cur.execute(f"DROP VIEW IF EXISTS {view_name} CASCADE")
    cur.execute(f"""
        CREATE VIEW {view_name} AS
        SELECT *
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = {year}
    """)
    created_views.append(view_name)
    print(f"  ✅ {view_name}")

# 3. GENERAL_LEDGER YEAR VIEWS
print("\n3. Creating general_ledger_YYYY views...")
print("-" * 100)
for year in years:
    view_name = f"general_ledger_{year}"
    cur.execute(f"DROP VIEW IF EXISTS {view_name} CASCADE")
    cur.execute(f"""
        CREATE VIEW {view_name} AS
        SELECT *
        FROM general_ledger
        WHERE EXTRACT(YEAR FROM date) = {year}
    """)
    created_views.append(view_name)
    print(f"  ✅ {view_name}")

# 4. PAYMENTS YEAR VIEWS
print("\n4. Creating payments_YYYY views...")
print("-" * 100)
for year in years:
    view_name = f"payments_{year}"
    cur.execute(f"DROP VIEW IF EXISTS {view_name} CASCADE")
    cur.execute(f"""
        CREATE VIEW {view_name} AS
        SELECT *
        FROM payments
        WHERE EXTRACT(YEAR FROM payment_date) = {year}
    """)
    created_views.append(view_name)
    print(f"  ✅ {view_name}")

# 5. CHARTERS YEAR VIEWS
print("\n5. Creating charters_YYYY views...")
print("-" * 100)
for year in years:
    view_name = f"charters_{year}"
    cur.execute(f"DROP VIEW IF EXISTS {view_name} CASCADE")
    cur.execute(f"""
        CREATE VIEW {view_name} AS
        SELECT *
        FROM charters
        WHERE EXTRACT(YEAR FROM charter_date) = {year}
    """)
    created_views.append(view_name)
    print(f"  ✅ {view_name}")

# 6. YEAR SUMMARY VIEW (aggregated stats per year)
print("\n6. Creating accounting_year_summary view...")
print("-" * 100)
cur.execute("DROP VIEW IF EXISTS accounting_year_summary CASCADE")
cur.execute("""
    CREATE VIEW accounting_year_summary AS
    WITH year_receipts AS (
        SELECT EXTRACT(YEAR FROM receipt_date)::int as yr,
               COUNT(*) as cnt, SUM(gross_amount) as total,
               COUNT(DISTINCT gl_account_code) as gl_codes,
               COUNT(CASE WHEN gl_account_code IS NULL THEN 1 END) as uncategorized
        FROM receipts WHERE receipt_date IS NOT NULL
        GROUP BY yr
    ),
    year_banking AS (
        SELECT EXTRACT(YEAR FROM transaction_date)::int as yr,
               COUNT(*) as cnt, SUM(COALESCE(debit_amount,0)) as debits,
               SUM(COALESCE(credit_amount,0)) as credits
        FROM banking_transactions WHERE transaction_date IS NOT NULL
        GROUP BY yr
    ),
    year_charters AS (
        SELECT EXTRACT(YEAR FROM charter_date)::int as yr,
               COUNT(*) as cnt, SUM(total_amount_due) as revenue,
               SUM(paid_amount) as paid
        FROM charters WHERE charter_date IS NOT NULL
        GROUP BY yr
    ),
    year_payments AS (
        SELECT EXTRACT(YEAR FROM payment_date)::int as yr,
               COUNT(*) as cnt, SUM(amount) as total
        FROM payments WHERE payment_date IS NOT NULL
        GROUP BY yr
    )
    SELECT 
        COALESCE(r.yr, b.yr, c.yr, p.yr) as fiscal_year,
        COALESCE(r.cnt,0) as receipt_count,
        COALESCE(r.total,0) as total_receipts,
        COALESCE(r.gl_codes,0) as unique_gl_codes,
        COALESCE(r.uncategorized,0) as uncategorized_receipts,
        COALESCE(b.cnt,0) as banking_transaction_count,
        COALESCE(b.debits,0) as total_debits,
        COALESCE(b.credits,0) as total_credits,
        COALESCE(c.cnt,0) as charter_count,
        COALESCE(c.revenue,0) as total_charter_revenue,
        COALESCE(c.paid,0) as total_charter_paid,
        COALESCE(p.cnt,0) as payment_count,
        COALESCE(p.total,0) as total_payments
    FROM year_receipts r
    FULL OUTER JOIN year_banking b ON r.yr = b.yr
    FULL OUTER JOIN year_charters c ON COALESCE(r.yr, b.yr) = c.yr
    FULL OUTER JOIN year_payments p ON COALESCE(r.yr, b.yr, c.yr) = p.yr
    ORDER BY fiscal_year
""")
created_views.append("accounting_year_summary")
print(f"  ✅ accounting_year_summary")

# 7. GL ACCOUNT SUMMARY BY YEAR
print("\n7. Creating gl_account_year_summary view...")
print("-" * 100)
cur.execute("DROP VIEW IF EXISTS gl_account_year_summary CASCADE")
cur.execute("""
    CREATE VIEW gl_account_year_summary AS
    SELECT 
        EXTRACT(YEAR FROM receipt_date)::int as fiscal_year,
        gl_account_code,
        COUNT(*) as transaction_count,
        SUM(gross_amount) as total_amount,
        MIN(receipt_date) as first_transaction,
        MAX(receipt_date) as last_transaction,
        COUNT(DISTINCT vendor_name) as unique_vendors
    FROM receipts
    WHERE receipt_date IS NOT NULL AND gl_account_code IS NOT NULL
    GROUP BY EXTRACT(YEAR FROM receipt_date), gl_account_code
    ORDER BY fiscal_year, gl_account_code
""")
created_views.append("gl_account_year_summary")
print(f"  ✅ gl_account_year_summary")

# 8. VENDOR SPENDING BY YEAR
print("\n8. Creating vendor_year_summary view...")
print("-" * 100)
cur.execute("DROP VIEW IF EXISTS vendor_year_summary CASCADE")
cur.execute("""
    CREATE VIEW vendor_year_summary AS
    SELECT 
        EXTRACT(YEAR FROM receipt_date)::int as fiscal_year,
        vendor_name,
        COUNT(*) as transaction_count,
        SUM(gross_amount) as total_spent,
        MIN(receipt_date) as first_purchase,
        MAX(receipt_date) as last_purchase,
        COUNT(DISTINCT gl_account_code) as gl_codes_used
    FROM receipts
    WHERE receipt_date IS NOT NULL AND vendor_name IS NOT NULL
    GROUP BY EXTRACT(YEAR FROM receipt_date), vendor_name
    HAVING SUM(gross_amount) > 0
    ORDER BY fiscal_year, total_spent DESC
""")
created_views.append("vendor_year_summary")
print(f"  ✅ vendor_year_summary")

conn.commit()

# Report summary
print("\n" + "="*100)
print("YEAR-BASED ACCOUNTING SYSTEM CREATED")
print("="*100)
print(f"\n✅ Created {len(created_views)} views:")
print()
print("YEAR-SPECIFIC VIEWS (per table):")
print(f"  - receipts_2011 through receipts_2026 ({len([v for v in created_views if v.startswith('receipts_')])} views)")
print(f"  - banking_transactions_2011 through banking_transactions_2026 ({len([v for v in created_views if v.startswith('banking_transactions_')])} views)")
print(f"  - general_ledger_2011 through general_ledger_2026 ({len([v for v in created_views if v.startswith('general_ledger_')])} views)")
print(f"  - payments_2011 through payments_2026 ({len([v for v in created_views if v.startswith('payments_')])} views)")
print(f"  - charters_2011 through charters_2026 ({len([v for v in created_views if v.startswith('charters_')])} views)")
print()
print("SUMMARY/ANALYSIS VIEWS:")
print("  - accounting_year_summary (aggregate stats per year)")
print("  - gl_account_year_summary (GL account breakdown by year)")
print("  - vendor_year_summary (vendor spending by year)")
print()

# Show sample usage
print("USAGE EXAMPLES:")
print("-" * 100)
print("-- Get all 2024 receipts:")
print("SELECT * FROM receipts_2024;")
print()
print("-- Export 2024 banking transactions to CSV:")
print("\\copy (SELECT * FROM banking_transactions_2024) TO 'banking_2024.csv' CSV HEADER;")
print()
print("-- View yearly summary:")
print("SELECT * FROM accounting_year_summary ORDER BY fiscal_year;")
print()
print("-- Top vendors in 2024:")
print("SELECT * FROM vendor_year_summary WHERE fiscal_year=2024 ORDER BY total_spent DESC LIMIT 20;")
print()
print("-- GL account breakdown for 2024:")
print("SELECT * FROM gl_account_year_summary WHERE fiscal_year=2024 ORDER BY total_amount DESC;")
print()

# Verify row counts for a sample year (2024)
print("\n" + "="*100)
print("VERIFICATION: 2024 DATA COUNTS")
print("="*100)
cur.execute("SELECT COUNT(*) FROM receipts_2024")
r_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM banking_transactions_2024")
b_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM general_ledger_2024")
gl_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM payments_2024")
p_count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM charters_2024")
c_count = cur.fetchone()[0]

print(f"receipts_2024:              {r_count:>8,} rows")
print(f"banking_transactions_2024:  {b_count:>8,} rows")
print(f"general_ledger_2024:        {gl_count:>8,} rows")
print(f"payments_2024:              {p_count:>8,} rows")
print(f"charters_2024:              {c_count:>8,} rows")
print()

cur.close()
conn.close()

print("✅ Year-based accounting system ready for use!")
