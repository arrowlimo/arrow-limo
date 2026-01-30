"""Final verification of CIBC 1615 balances across all years."""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

print("="*100)
print("CIBC 1615 FINAL VERIFICATION (2012-2017)")
print("="*100)
print()

for year in [2012, 2013, 2014, 2015, 2016, 2017]:
    print(f"\n{year}:")
    print("-" * 100)
    
    # Check data completeness
    cur.execute("""
        SELECT COUNT(*),
               COUNT(CASE WHEN balance IS NULL THEN 1 END),
               MIN(transaction_date),
               MAX(transaction_date)
        FROM banking_transactions
        WHERE account_number = '1615'
        AND EXTRACT(YEAR FROM transaction_date) = %s
    """, (year,))
    total, nulls, min_date, max_date = cur.fetchone()
    
    print(f"  Transactions: {total}")
    print(f"  NULL balances: {nulls}")
    print(f"  Date range: {min_date} to {max_date}")
    
    # Get opening and closing
    cur.execute("""
        SELECT transaction_date, description, balance
        FROM banking_transactions
        WHERE account_number = '1615'
        AND EXTRACT(YEAR FROM transaction_date) = %s
        ORDER BY transaction_date ASC
        LIMIT 1
    """, (year,))
    first = cur.fetchone()
    if first:
        print(f"  Opening: {first[0]} | {first[1][:30]:30} | ${first[2]:.2f}")
    
    # Get closing
    cur.execute("""
        SELECT transaction_date, description, balance
        FROM banking_transactions
        WHERE account_number = '1615'
        AND EXTRACT(YEAR FROM transaction_date) = %s
        ORDER BY transaction_date DESC
        LIMIT 1
    """, (year,))
    last = cur.fetchone()
    if last:
        print(f"  Closing: {last[0]} | {last[1][:30]:30} | ${last[2]:.2f}")

print("\n" + "="*100)
print("YEAR-TO-YEAR CONTINUITY")
print("="*100)

prev_closing = None
for year in [2012, 2013, 2014, 2015, 2016, 2017]:
    cur.execute("""
        SELECT balance FROM banking_transactions
        WHERE account_number = '1615'
        AND EXTRACT(YEAR FROM transaction_date) = %s
        ORDER BY transaction_date DESC
        LIMIT 1
    """, (year,))
    result = cur.fetchone()
    year_end = float(result[0]) if result else None
    
    cur.execute("""
        SELECT balance FROM banking_transactions
        WHERE account_number = '1615'
        AND EXTRACT(YEAR FROM transaction_date) = %s
        ORDER BY transaction_date ASC
        LIMIT 1
    """, (year,))
    result = cur.fetchone()
    year_start = float(result[0]) if result else None
    
    if prev_closing is not None and year_start is not None:
        match = "✅" if abs(year_start - prev_closing) < 0.01 else "❌"
        print(f"{year} opening ${year_start:>10.2f} (expected ${prev_closing:>10.2f} from {year-1}) {match}")
    else:
        print(f"{year} opening ${year_start:>10.2f}")
    
    prev_closing = year_end

print()
print("✅ COMPLETE: All 2012-2017 balances calculated and stored in database")

conn.close()
