"""
Phase 4: Identify redundant amount columns and consolidation opportunities.
Analyzes amount/price/cost columns to reduce storage duplication.
"""
import os
import psycopg2
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 100)
print("PHASE 4: AMOUNT COLUMN CONSOLIDATION ANALYSIS")
print("=" * 100)

# Find all amount-like columns
cur.execute("""
    SELECT table_name, string_agg(column_name, ', ') as amount_cols,
           count(*) as col_count
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND (column_name LIKE '%amount%'
        OR column_name LIKE '%price%'
        OR column_name LIKE '%cost%'
        OR column_name LIKE '%total%'
        OR column_name LIKE '%fee%'
        OR column_name LIKE '%charge%'
        OR column_name LIKE '%rate%'
        OR column_name LIKE '%sum%')
    GROUP BY table_name
    HAVING count(*) > 1
    ORDER BY col_count DESC, table_name
""")

results = cur.fetchall()

print(f"\nFound {len(results)} tables with multiple amount/price/cost columns\n")

# Key tables for consolidation analysis
key_tables = {
    'receipts': ['gross_amount', 'net_amount', 'gst_amount', 'tax', 'sales_tax'],
    'payments': ['amount', 'deposit_amount'],
    'charters': ['rate', 'total_amount_due', 'balance', 'driver_total', 'driver_paid'],
    'banking_transactions': ['credit_amount', 'debit_amount', 'amount'],
    'general_ledger': ['debit_amount', 'credit_amount', 'amount']
}

print("[1] KEY TABLES - DETAILED ANALYSIS")
print("-" * 100)

consolidation_plan = []

for table in key_tables:
    columns = key_tables[table]
    
    # Check which columns exist
    cur.execute(f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = %s AND column_name = ANY(%s)
        ORDER BY ordinal_position
    """, (table, columns))
    
    existing = cur.fetchall()
    
    if existing:
        print(f"\n📊 {table}:")
        for col_name, dtype in existing:
            cur.execute(f"SELECT COUNT(DISTINCT {col_name}) FROM {table} WHERE {col_name} IS NOT NULL")
            distinct = cur.fetchone()[0]
            print(f"   {col_name:<30} {dtype:<20} ({distinct:,} unique values)")
        
        # Table-specific analysis
        if table == 'receipts':
            # Receipts: gross_amount is typically the source; gst_amount and net_amount are calculated
            cur.execute("""
                SELECT COUNT(*) as total_rows,
                       SUM(CASE WHEN gross_amount IS NOT NULL THEN 1 ELSE 0 END) as gross_filled,
                       SUM(CASE WHEN net_amount IS NOT NULL THEN 1 ELSE 0 END) as net_filled,
                       SUM(CASE WHEN gst_amount IS NOT NULL THEN 1 ELSE 0 END) as gst_filled
                FROM receipts
            """)
            totals, gross, net, gst = cur.fetchone()
            
            print(f"   Strategy: Store only gross_amount; calculate net_amount and gst_amount")
            print(f"             Current: gross={gross}/{totals}, net={net}/{totals}, gst={gst}/{totals}")
            consolidation_plan.append(("receipts", "Drop net_amount, gst_amount; create computed columns"))
        
        elif table == 'payments':
            cur.execute("""
                SELECT COUNT(*) as total_rows,
                       SUM(CASE WHEN amount IS NOT NULL THEN 1 ELSE 0 END) as amount_filled
                FROM payments
            """)
            totals, amt = cur.fetchone()
            print(f"   Strategy: Single amount column already in use")
            print(f"             Current: amount={amt}/{totals}")
        
        elif table == 'charters':
            cur.execute("""
                SELECT COUNT(*) as total_rows,
                       SUM(CASE WHEN total_amount_due IS NOT NULL THEN 1 ELSE 0 END) as due_filled,
                       SUM(CASE WHEN balance IS NOT NULL THEN 1 ELSE 0 END) as balance_filled,
                       SUM(CASE WHEN driver_total IS NOT NULL THEN 1 ELSE 0 END) as driver_total_filled
                FROM charters
            """)
            totals, due, bal, drv = cur.fetchone()
            print(f"   Strategy: total_amount_due is source; balance = due - paid (calculated)")
            print(f"             Current: due={due}/{totals}, balance={bal}/{totals}, driver_total={drv}/{totals}")
            consolidation_plan.append(("charters", "Drop balance column; calculate from total_amount_due and payments"))
        
        elif table == 'banking_transactions':
            cur.execute("""
                SELECT COUNT(*) as total_rows,
                       SUM(CASE WHEN credit_amount IS NOT NULL AND credit_amount <> 0 THEN 1 ELSE 0 END) as credits,
                       SUM(CASE WHEN debit_amount IS NOT NULL AND debit_amount <> 0 THEN 1 ELSE 0 END) as debits
                FROM banking_transactions
            """)
            totals, cred, deb = cur.fetchone()
            print(f"   Strategy: Use debit_amount and credit_amount (already separated by type)")
            print(f"             Current: credits={cred}, debits={deb}")
        
        elif table == 'general_ledger':
            cur.execute("""
                SELECT COUNT(*) as total_rows,
                       SUM(CASE WHEN debit_amount IS NOT NULL AND debit_amount <> 0 THEN 1 ELSE 0 END) as debits,
                       SUM(CASE WHEN credit_amount IS NOT NULL AND credit_amount <> 0 THEN 1 ELSE 0 END) as credits
                FROM general_ledger
            """)
            totals, deb, cred = cur.fetchone()
            print(f"   Strategy: Keep debit_amount and credit_amount (double-entry bookkeeping)")
            print(f"             Current: debits={deb}, credits={cred}")
            consolidation_plan.append(("general_ledger", "Keep as-is (double-entry accounting requirement)"))

print("\n[2] CONSOLIDATION PLAN")
print("-" * 100)

for table, action in consolidation_plan:
    print(f"{table:<35} {action}")

print("\n[3] IMPLEMENTATION ROADMAP")
print("-" * 100)

print("""
PHASE 4A: Create Computed Columns (non-destructive)
  1. charters: CREATE VIEW v_charter_balances AS 
     (SELECT *, (total_amount_due - COALESCE(paid_amount, 0)) AS balance FROM charters)

PHASE 4B: Migrate Data (with validation)
  1. Verify balance column calculation matches existing data
  2. Update dependent queries to use view instead of column
  3. Test all dependent views/reports

PHASE 4C: Clean Up (after all tests pass)
  1. Drop charters.balance column
  2. Update queries to use v_charter_balances view
  3. Measure storage savings

NOTE: Receipts consolidation DEFERRED
  ⚠️  Phase 4 originally proposed consolidating receipts (gross/net/gst)
  ⚠️  DECISION: Keep receipts columns as-is until tax_rates lookup table added
  ⚠️  REASON: Hardcoding 0.05 (AB rate) breaks multi-province/US tax accuracy
  ⚠️  FUTURE: Add tax_rates(province_code, effective_date, rate) table for flexible tax handling

ESTIMATED SAVINGS (Phase 4A only - charters):
  - charters: 1 column × 18,679 rows × 8 bytes = ~150 KB
  
SAFETY MEASURES:
  ✅ Create backup before any column drops
  ✅ Create view before dropping source column
  ✅ Test all dependent views/reports
  ✅ Document column relationships
  ✅ Keep backup tables as reference

NEXT STEP: Run Phase 4A (create view + validate) after user approval.
""")

cur.close()
conn.close()
