"""
Phase 4A: Create charters balance view and validate calculations.
Non-destructive: creates view without dropping balance column yet.
"""
import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 100)
print("PHASE 4A: CREATE CHARTERS BALANCE VIEW & VALIDATE")
print("=" * 100)

# Step 1: Create the view
print("\n[1] CREATE VIEW v_charter_balances")
print("-" * 100)

create_view_sql = """
CREATE OR REPLACE VIEW v_charter_balances AS
SELECT 
    c.charter_id,
    c.reserve_number,
    c.account_number,
    c.charter_date,
    c.total_amount_due,
    COALESCE(SUM(p.amount), 0) AS paid_amount,
    c.total_amount_due - COALESCE(SUM(p.amount), 0) AS calculated_balance,
    c.balance AS stored_balance,
    c.status,
    c.notes,
    c.created_at,
    c.updated_at
FROM charters c
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
GROUP BY c.charter_id, c.reserve_number, c.account_number, c.charter_date, 
         c.total_amount_due, c.balance, c.status, c.notes, c.created_at, c.updated_at
ORDER BY c.charter_id;
"""

try:
    cur.execute(create_view_sql)
    conn.commit()
    print("✅ View created: v_charter_balances")
except Exception as e:
    conn.rollback()
    print(f"❌ Error creating view: {e}")
    cur.close()
    conn.close()
    exit(1)

# Step 2: Validate calculations
print("\n[2] VALIDATE CALCULATED BALANCE vs STORED BALANCE")
print("-" * 100)

cur.execute("""
    SELECT 
        COUNT(*) as total_charters,
        SUM(CASE WHEN calculated_balance = stored_balance THEN 1 ELSE 0 END) as matches,
        SUM(CASE WHEN calculated_balance <> stored_balance THEN 1 ELSE 0 END) as mismatches,
        SUM(CASE WHEN calculated_balance IS NULL OR stored_balance IS NULL THEN 1 ELSE 0 END) as nulls
    FROM v_charter_balances
""")

total, matches, mismatches, nulls = cur.fetchone()

print(f"Total charters: {total:,}")
print(f"Matches: {matches:,} ({100*matches/total:.1f}%)")
print(f"Mismatches: {mismatches:,} ({100*mismatches/total:.1f}%)")
print(f"NULL issues: {nulls:,}")

if mismatches > 0:
    print("\n⚠️  MISMATCHES DETECTED - Showing top 20:")
    cur.execute("""
        SELECT 
            charter_id, reserve_number, total_amount_due, 
            paid_amount, calculated_balance, stored_balance,
            (stored_balance - calculated_balance) AS difference
        FROM v_charter_balances
        WHERE calculated_balance <> stored_balance
        ORDER BY ABS(stored_balance - calculated_balance) DESC
        LIMIT 20
    """)
    
    for charter_id, reserve, due, paid, calc, stored, diff in cur.fetchall():
        print(f"  Charter {charter_id} (Reserve {reserve}): Due=${due:.2f}, Paid=${paid:.2f}")
        print(f"    Calc=${calc:.2f} vs Stored=${stored:.2f} [diff: ${diff:.2f}]")
else:
    print("\n✅ All balances match!")

# Step 3: Test dependent queries
print("\n[3] TEST DEPENDENT QUERIES")
print("-" * 100)

# Test: Get unpaid charters
cur.execute("""
    SELECT COUNT(*) FROM v_charter_balances 
    WHERE calculated_balance > 0.01
""")
unpaid = cur.fetchone()[0]
print(f"✅ Unpaid charters: {unpaid:,}")

# Test: Get paid charters
cur.execute("""
    SELECT COUNT(*) FROM v_charter_balances 
    WHERE calculated_balance <= 0.01
""")
paid = cur.fetchone()[0]
print(f"✅ Paid charters: {paid:,}")

# Test: Total outstanding
cur.execute("""
    SELECT SUM(calculated_balance) 
    FROM v_charter_balances 
    WHERE calculated_balance > 0.01
""")
total_outstanding = cur.fetchone()[0] or 0
print(f"✅ Total outstanding: ${total_outstanding:,.2f}")

# Test: Charters by status
cur.execute("""
    SELECT status, COUNT(*) as count, SUM(calculated_balance) as balance
    FROM v_charter_balances
    GROUP BY status
    ORDER BY balance DESC NULLS LAST
    LIMIT 10
""")

print(f"\n✅ Balance by status:")
for status, count, balance in cur.fetchall():
    balance_str = f"${balance:,.2f}" if balance else "NULL"
    print(f"  {str(status):<20} {count:>6,} charters   {balance_str:>15}")

# Step 4: Create sample report using view
print("\n[4] SAMPLE REPORT - TOP 10 OUTSTANDING CHARTERS")
print("-" * 100)

cur.execute("""
    SELECT 
        charter_id, reserve_number, charter_date, 
        total_amount_due, paid_amount, calculated_balance
    FROM v_charter_balances
    WHERE calculated_balance > 0.01
    ORDER BY calculated_balance DESC
    LIMIT 10
""")

print(f"{'Charter ID':<12} {'Reserve':<10} {'Date':<12} {'Total Due':<15} {'Paid':<15} {'Balance':<15}")
print("-" * 80)
for charter_id, reserve, date, due, paid, balance in cur.fetchall():
    print(f"{charter_id:<12} {reserve:<10} {str(date):<12} ${due:>13.2f} ${paid:>13.2f} ${balance:>13.2f}")

# Step 5: Summary
print("\n" + "=" * 100)
print("PHASE 4A COMPLETE")
print("=" * 100)

print(f"""
✅ VIEW CREATED: v_charter_balances

📊 VALIDATION RESULTS:
  - Total charters: {total:,}
  - Matches: {matches:,} ({100*matches/total:.1f}%)
  - Mismatches: {mismatches:,}
  - NULLs: {nulls:,}

📈 KEY METRICS:
  - Unpaid charters: {unpaid:,}
  - Paid charters: {paid:,}
  - Total outstanding: ${total_outstanding:,.2f}

✅ DEPENDENT QUERIES TESTED:
  - Unpaid charters query
  - Paid charters query
  - Balance by status grouping
  - Top outstanding charters report

📋 NEXT STEPS (Phase 4B):
  1. Update all dependent queries to use v_charter_balances
  2. Test reports and dashboards
  3. Verify no performance degradation
  
🚀 PHASE 4C (after validation):
  1. Back up charters table
  2. Drop charters.balance column
  3. Re-test all queries
  4. Monitor performance

💾 SPACE SAVINGS (after Phase 4C):
  - 1 column × 18,679 rows × 8 bytes = ~150 KB
""")

cur.close()
conn.close()
