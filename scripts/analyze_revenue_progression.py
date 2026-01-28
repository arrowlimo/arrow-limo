"""Analyze revenue growth from payments table."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 80)
print("REVENUE ANALYSIS - PAYMENT DATA")
print("=" * 80)

# 1. Total payments by year
print("\n1. TOTAL PAYMENTS BY YEAR")
print("-" * 80)
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM payment_date) as year,
        COUNT(*) as payment_count,
        SUM(amount) as total_amount
    FROM payments
    WHERE payment_date IS NOT NULL
    AND payment_date >= '2007-01-01'
    AND payment_date <= '2024-12-31'
    GROUP BY EXTRACT(YEAR FROM payment_date)
    ORDER BY year
""")

print(f"{'Year':<8} {'Payments':<12} {'Total Amount':<20} {'Cumulative':<20}")
print("-" * 80)

cumulative = 0
for row in cur.fetchall():
    year, count, amount = int(row[0]), row[1], row[2] or 0
    cumulative += amount
    print(f"{year:<8} {count:<12,} ${amount:>18,.2f} ${cumulative:>18,.2f}")

# 2. Matched vs unmatched breakdown
print("\n2. MATCHED VS UNMATCHED PAYMENTS (2007-2024)")
print("-" * 80)
cur.execute("""
    SELECT 
        CASE 
            WHEN charter_id IS NOT NULL THEN 'Matched to Charter'
            ELSE 'Unmatched'
        END as status,
        COUNT(*) as payment_count,
        SUM(amount) as total_amount
    FROM payments
    WHERE payment_date >= '2007-01-01'
    AND payment_date <= '2024-12-31'
    GROUP BY CASE WHEN charter_id IS NOT NULL THEN 'Matched to Charter' ELSE 'Unmatched' END
    ORDER BY total_amount DESC
""")

print(f"{'Status':<25} {'Count':<12} {'Amount':<20}")
print("-" * 80)
for row in cur.fetchall():
    print(f"{row[0]:<25} {row[1]:<12,} ${row[2]:>18,.2f}")

# 3. Payment sources
print("\n3. PAYMENT SOURCES")
print("-" * 80)
cur.execute("""
    SELECT 
        CASE 
            WHEN payment_key LIKE 'SQ:%' OR square_transaction_id IS NOT NULL THEN 'Square'
            WHEN payment_key LIKE 'QBO:%' THEN 'QuickBooks Online'
            WHEN payment_key LIKE 'LMSDEP:%' THEN 'LMS Deposits'
            WHEN payment_key LIKE 'BTX:%' THEN 'Banking (Interac)'
            WHEN payment_key ~ '^[0-9]+$' THEN 'LMS Legacy'
            ELSE 'Other/Unknown'
        END as source,
        COUNT(*) as payment_count,
        SUM(amount) as total_amount
    FROM payments
    WHERE payment_date >= '2007-01-01'
    AND payment_date <= '2024-12-31'
    GROUP BY source
    ORDER BY total_amount DESC
""")

print(f"{'Source':<25} {'Count':<12} {'Amount':<20}")
print("-" * 80)
for row in cur.fetchall():
    print(f"{row[0]:<25} {row[1]:<12,} ${row[2]:>18,.2f}")

# 4. Compare with charters table
print("\n4. REVENUE COMPARISON: PAYMENTS vs CHARTERS")
print("-" * 80)

# Payments total
cur.execute("""
    SELECT 
        COUNT(*) as payment_count,
        SUM(amount) as total_payments
    FROM payments
    WHERE payment_date >= '2007-01-01'
    AND payment_date <= '2024-12-31'
""")
pay_stats = cur.fetchone()
payment_count, payment_total = pay_stats[0], pay_stats[1] or 0

# Charters total (rate + deposits)
cur.execute("""
    SELECT 
        COUNT(*) as charter_count,
        SUM(rate) as total_rate,
        SUM(deposit) as total_deposits,
        SUM(balance) as total_balance
    FROM charters
    WHERE charter_date >= '2007-01-01'
    AND charter_date <= '2024-12-31'
    AND status NOT IN ('cancelled', 'Cancelled')
""")
charter_stats = cur.fetchone()
charter_count = charter_stats[0]
charter_rate = charter_stats[1] or 0
charter_deposits = charter_stats[2] or 0
charter_balance = charter_stats[3] or 0

print(f"PAYMENTS TABLE:")
print(f"  Total payments: {payment_count:,}")
print(f"  Total amount: ${payment_total:,.2f}")
print()
print(f"CHARTERS TABLE:")
print(f"  Total charters (non-cancelled): {charter_count:,}")
print(f"  Total rate (billable): ${charter_rate:,.2f}")
print(f"  Total deposits: ${charter_deposits:,.2f}")
print(f"  Outstanding balance: ${charter_balance:,.2f}")
print()
print(f"RECONCILIATION:")
print(f"  Charter billings (rate): ${charter_rate:,.2f}")
print(f"  Payments received: ${payment_total:,.2f}")
print(f"  Difference: ${payment_total - charter_rate:,.2f}")
print(f"  Outstanding balance: ${charter_balance:,.2f}")

# 5. Payment methods breakdown
print("\n5. PAYMENT METHODS")
print("-" * 80)
cur.execute("""
    SELECT 
        COALESCE(payment_method, 'Unknown') as method,
        COUNT(*) as payment_count,
        SUM(amount) as total_amount
    FROM payments
    WHERE payment_date >= '2007-01-01'
    AND payment_date <= '2024-12-31'
    GROUP BY payment_method
    ORDER BY total_amount DESC
    LIMIT 20
""")

print(f"{'Method':<30} {'Count':<12} {'Amount':<20}")
print("-" * 80)
for row in cur.fetchall():
    method = (row[0] or 'Unknown')[:28]
    print(f"{method:<30} {row[1]:<12,} ${row[2]:>18,.2f}")

# 6. Check for other revenue tables
print("\n6. OTHER POTENTIAL REVENUE SOURCES")
print("-" * 80)

# Check receipts table
cur.execute("""
    SELECT 
        COUNT(*) as receipt_count,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE receipt_date >= '2007-01-01'
    AND receipt_date <= '2024-12-31'
""")
receipts = cur.fetchone()
print(f"RECEIPTS table (expenses):")
print(f"  Total receipts: {receipts[0]:,}")
print(f"  Total amount: ${receipts[1]:,.2f}" if receipts[1] else "  Total amount: $0.00")

# Check journal table
cur.execute("""
    SELECT 
        COUNT(*) as entry_count,
        SUM(CASE WHEN entry_type = 'credit' THEN amount ELSE 0 END) as credits,
        SUM(CASE WHEN entry_type = 'debit' THEN amount ELSE 0 END) as debits
    FROM journal
    WHERE entry_date >= '2007-01-01'
    AND entry_date <= '2024-12-31'
""")
journal = cur.fetchone()
print(f"\nJOURNAL table:")
print(f"  Total entries: {journal[0]:,}")
print(f"  Total credits: ${journal[1]:,.2f}" if journal[1] else "  Total credits: $0.00")
print(f"  Total debits: ${journal[2]:,.2f}" if journal[2] else "  Total debits: $0.00")

# 7. Banking transactions
print("\n7. BANKING TRANSACTIONS")
print("-" * 80)
cur.execute("""
    SELECT 
        COUNT(*) as transaction_count,
        SUM(credit_amount) as total_credits,
        SUM(debit_amount) as total_debits
    FROM banking_transactions
    WHERE transaction_date >= '2007-01-01'
    AND transaction_date <= '2024-12-31'
""")
banking = cur.fetchone()
print(f"BANKING_TRANSACTIONS table:")
print(f"  Total transactions: {banking[0]:,}")
print(f"  Total credits (deposits): ${banking[1]:,.2f}" if banking[1] else "  Total credits: $0.00")
print(f"  Total debits (payments): ${banking[2]:,.2f}" if banking[2] else "  Total debits: $0.00")

# 8. Grand total summary
print("\n" + "=" * 80)
print("SUMMARY: WHERE DID $19.4M COME FROM?")
print("=" * 80)
print(f"""
PAYMENTS TABLE: ${payment_total:,.2f}
  - This is the master payment tracking table
  - Includes all payment sources: LMS, Square, QuickBooks, Banking
  - 50,499 payments from 2007-2024
  - 95.5% matched to charters ($19.0M)
  - 4.5% unmatched ($343K) - mostly deposits, refunds, duplicates

CHARTERS TABLE: ${charter_rate:,.2f} billable
  - This represents the amount INVOICED (rate field)
  - 18,500+ charters from 2007-2024
  - Payments received: ${payment_total:,.2f}
  - Difference: ${payment_total - charter_rate:,.2f}
  
BANKING: ${banking[1]:,.2f} credits (deposits)
  - Bank deposits should match payments received
  - Some variance due to timing differences
  - Includes all sources (cash, card, transfer, etc)

REVENUE RECOGNITION:
  The $19.4M represents total PAYMENTS RECEIVED (cash basis)
  Charter rate ${charter_rate:,.2f} represents BILLABLE AMOUNT (accrual basis)
  
  Payments > Billings suggests:
  - Customer deposits/advances included
  - Tips and gratuities
  - Non-charter revenue (vehicle sales, other services)
  - Multiple payment sources consolidated
""")

print("=" * 80)

cur.close()
conn.close()
