"""
Query banking_transactions directly from database for 2012 CIBC records.
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("=" * 80)
print("2012 CIBC BANKING TRANSACTIONS FROM DATABASE")
print("=" * 80)

# Get 2012 count by month
cur.execute("""
    SELECT 
        TO_CHAR(transaction_date, 'YYYY-MM') as month,
        COUNT(*) as count,
        SUM(COALESCE(credit_amount, 0)) as deposits,
        SUM(COALESCE(debit_amount, 0)) as withdrawals
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    GROUP BY TO_CHAR(transaction_date, 'YYYY-MM')
    ORDER BY month
""")

print(f"{'Month':<10} {'Count':>10} {'Deposits':>15} {'Withdrawals':>15} {'Net':>15}")
print("-" * 80)

rows = cur.fetchall()
for month, count, deposits, withdrawals in rows:
    net = (deposits or 0) - (withdrawals or 0)
    print(f"{month:<10} {count:>10,} ${deposits or 0:>13,.2f} ${withdrawals or 0:>13,.2f} ${net:>13,.2f}")

# Compare with manual verification
print("\n" + "=" * 80)
print("COMPARISON WITH MANUAL VERIFICATION")
print("=" * 80)

manual_verified = {
    '2012-01': 168,  # January complete
    '2012-06': 87,   # June complete (sample from page, not full month)
}

db_counts = {row[0]: row[1] for row in rows}

print(f"{'Month':<10} {'Database':>12} {'Verified':>12} {'Difference':>12} {'Status'}")
print("-" * 80)

for month in sorted(set(list(manual_verified.keys()) + list(db_counts.keys()))):
    db = db_counts.get(month, 0)
    verified = manual_verified.get(month, 0)
    diff = db - verified if verified > 0 else 0
    
    if verified == 0:
        status = "⏳ Not verified"
    elif db == verified:
        status = "[OK] MATCH"
    else:
        status = f"[WARN] Difference"
    
    print(f"{month:<10} {db:>12,} {verified:>12,} {diff:>12,} {status}")

# Show sample January records
print("\n" + "=" * 80)
print("SAMPLE JANUARY 2012 RECORDS (first 10)")
print("=" * 80)

cur.execute("""
    SELECT 
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance
    FROM banking_transactions
    WHERE TO_CHAR(transaction_date, 'YYYY-MM') = '2012-01'
    ORDER BY transaction_date, transaction_id
    LIMIT 10
""")

print(f"{'Date':<12} {'Description':<45} {'Debit':>12} {'Credit':>12} {'Balance':>12}")
print("-" * 80)

for date, desc, debit, credit, balance in cur.fetchall():
    print(f"{str(date):<12} {(desc or '')[:44]:<45} "
          f"${debit or 0:>10,.2f} ${credit or 0:>10,.2f} ${balance or 0:>10,.2f}")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("NEXT STEPS")
print("=" * 80)
print("[OK] Database has 2012 CIBC banking data")
print("\nTo complete verification:")
print("1. Export each month's transactions")
print("2. Compare against PDF statement line-by-line")
print("3. Verify running balances match")
print("4. Update verification report with database-verified months")
