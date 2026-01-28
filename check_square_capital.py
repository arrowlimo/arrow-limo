import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("="*80)
print("SQUARE CAPITAL LOAN DATA")
print("="*80)
print()

# 1. Check square_capital_activity
print("SQUARE_CAPITAL_ACTIVITY (209 rows)")
print("-"*80)

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'square_capital_activity'
    ORDER BY ordinal_position
""")

print("Columns:")
for col in cur.fetchall():
    print(f"  {col[0]:<30} {col[1]}")

cur.execute("SELECT * FROM square_capital_activity ORDER BY id LIMIT 5")
print("\nSample data (first 5 rows):")
for row in cur.fetchall():
    print(f"  {row}")

# Summary
cur.execute("""
    SELECT 
        COUNT(*) as total_transactions,
        SUM(CASE WHEN description ILIKE '%advance%' OR description ILIKE '%loan%' THEN 1 ELSE 0 END) as advances,
        SUM(CASE WHEN description ILIKE '%payment%' THEN 1 ELSE 0 END) as payments,
        SUM(amount) as total_amount,
        MIN(activity_date) as first_date,
        MAX(activity_date) as last_date
    FROM square_capital_activity
""")

summary = cur.fetchone()
print(f"\nSummary:")
print(f"  Total transactions: {summary[0]}")
print(f"  Advances: {summary[1]}")
print(f"  Payments: {summary[2]}")
print(f"  Total amount: ${summary[3]:,.2f}")
print(f"  Date range: {summary[4]} to {summary[5]}")

# 2. Check square_capital_monthly_summary
print("\n" + "="*80)
print("SQUARE_CAPITAL_MONTHLY_SUMMARY (9 rows)")
print("-"*80)

cur.execute("SELECT * FROM square_capital_monthly_summary ORDER BY month")
print(f"\n{'Month':<12} {'Advances':>12} {'Payments':>12} {'Net':>12}")
print("-"*50)

total_advances = 0
total_payments = 0
for row in cur.fetchall():
    print(f"{str(row[0]):<12} ${row[1]:>11.2f} ${row[2]:>11.2f} ${row[3]:>11.2f}")
    total_advances += row[1] or 0
    total_payments += row[2] or 0

print("-"*50)
print(f"{'TOTAL':<12} ${total_advances:>11.2f} ${total_payments:>11.2f} ${total_advances - total_payments:>11.2f}")

# 3. Check if square_loan_payments should reference square_capital_activity
print("\n" + "="*80)
print("SQUARE LOAN STRUCTURE ANALYSIS")
print("="*80)

cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name LIKE 'square_%loan%'
    ORDER BY table_name
""")

print("\nSquare loan tables:")
for table in cur.fetchall():
    cur.execute(f"SELECT COUNT(*) FROM {table[0]}")
    count = cur.fetchone()[0]
    print(f"  {table[0]:<40} {count:>6} rows")

print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)
print("""
The Square loan data IS in the database, but in different tables:
- square_capital_activity (209 transactions) - detailed loan activity
- square_capital_monthly_summary (9 months) - monthly rollups

The square_loan_payments table is EMPTY because it was designed for a 
different structure. The actual loan data is properly stored in 
square_capital_activity.

Should consolidate:
- DROP square_loan_payments (empty, redundant)
- KEEP square_capital_activity (active, contains all loan transactions)
- KEEP square_capital_monthly_summary (summary data)
""")

cur.close()
conn.close()
