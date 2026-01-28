#!/usr/bin/env python3
"""
Analyze Banking Records - Categorization and Missing Entries
Check if all banking fees, transfers, withdrawals, and recurring expenses are properly logged
"""
import psycopg2
from collections import defaultdict

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 100)
print("BANKING RECORDS ANALYSIS - CATEGORIZATION REVIEW")
print("=" * 100)

# 1. Get all banking transactions with their categorization
print("\n" + "=" * 100)
print("1. BANKING TRANSACTION OVERVIEW")
print("=" * 100)

cur.execute("""
    SELECT 
        COUNT(*) as total_transactions,
        COUNT(DISTINCT EXTRACT(YEAR FROM transaction_date)) as years_covered,
        MIN(transaction_date) as earliest_date,
        MAX(transaction_date) as latest_date,
        SUM(CASE WHEN debit_amount > 0 THEN 1 ELSE 0 END) as debit_count,
        SUM(CASE WHEN credit_amount > 0 THEN 1 ELSE 0 END) as credit_count,
        SUM(debit_amount) as total_debits,
        SUM(credit_amount) as total_credits
    FROM banking_transactions
""")
row = cur.fetchone()
print(f"  Total transactions: {row[0]:,}")
print(f"  Years covered: {int(row[1])}")
print(f"  Date range: {row[2]} to {row[3]}")
print(f"  Debit transactions: {row[4]:,} (${row[6]:,.2f})")
print(f"  Credit transactions: {row[5]:,} (${row[7]:,.2f})")

# 2. Banking Fees Analysis
print("\n" + "=" * 100)
print("2. BANKING FEES - Are they all logged?")
print("=" * 100)

cur.execute("""
    SELECT 
        description,
        COUNT(*) as count,
        SUM(debit_amount) as total_amount,
        MIN(transaction_date) as first_occurrence,
        MAX(transaction_date) as last_occurrence
    FROM banking_transactions
    WHERE description ILIKE '%fee%'
       OR description ILIKE '%service charge%'
       OR description ILIKE '%bank charge%'
       OR description ILIKE '%monthly fee%'
       OR description ILIKE '%transaction fee%'
       OR description ILIKE '%NSF%'
       OR description ILIKE '%overdraft%'
    GROUP BY description
    ORDER BY total_amount DESC
""")
fees = cur.fetchall()

if fees:
    print(f"\n  Found {len(fees)} types of banking fees:")
    total_fees = 0
    for desc, count, amount, first, last in fees:
        print(f"\n    {desc[:60]}")
        print(f"      Occurrences: {count:,} times")
        print(f"      Total: ${amount or 0:,.2f}")
        print(f"      Period: {first} to {last}")
        total_fees += amount or 0
    print(f"\n  TOTAL BANKING FEES: ${total_fees:,.2f}")
else:
    print("  WARNING: No banking fees found in descriptions!")

# Check if fees are in general_ledger
cur.execute("""
    SELECT 
        account_name,
        COUNT(*) as entries,
        SUM(debit) as total_amount
    FROM general_ledger
    WHERE account_name ILIKE '%bank%fee%'
       OR account_name ILIKE '%bank%charge%'
       OR account_name ILIKE '%service charge%'
    GROUP BY account_name
    ORDER BY total_amount DESC
""")
gl_fees = cur.fetchall()

if gl_fees:
    print(f"\n  Banking fees in General Ledger:")
    for account, count, amount in gl_fees:
        print(f"    {account}: {count} entries, ${amount or 0:,.2f}")
else:
    print("\n  WARNING: No banking fees found in General Ledger!")

# 3. Bank Transfers Analysis
print("\n" + "=" * 100)
print("3. BANK TRANSFERS - One account to another")
print("=" * 100)

cur.execute("""
    SELECT 
        description,
        COUNT(*) as count,
        SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as total_debits,
        SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END) as total_credits
    FROM banking_transactions
    WHERE description ILIKE '%transfer%'
       OR description ILIKE '%e-transfer%'
       OR description ILIKE '%interac%'
    GROUP BY description
    ORDER BY count DESC
    LIMIT 20
""")
transfers = cur.fetchall()

if transfers:
    print(f"\n  Found {len(transfers)} types of transfers:")
    for desc, count, debits, credits in transfers:
        print(f"\n    {desc[:70]}")
        print(f"      Occurrences: {count:,}")
        if debits and debits > 0:
            print(f"      Debits (outgoing): ${debits:,.2f}")
        if credits and credits > 0:
            print(f"      Credits (incoming): ${credits:,.2f}")
else:
    print("  No transfers found")

# 4. Cash Withdrawals
print("\n" + "=" * 100)
print("4. CASH WITHDRAWALS - ATM and manual")
print("=" * 100)

cur.execute("""
    SELECT 
        description,
        COUNT(*) as count,
        SUM(debit_amount) as total_amount,
        AVG(debit_amount) as avg_amount
    FROM banking_transactions
    WHERE (description ILIKE '%ATM%'
       OR description ILIKE '%cash%withdraw%'
       OR description ILIKE '%withdrawal%')
      AND debit_amount > 0
    GROUP BY description
    ORDER BY total_amount DESC
""")
withdrawals = cur.fetchall()

if withdrawals:
    print(f"\n  Found {len(withdrawals)} types of cash withdrawals:")
    total_withdrawn = 0
    for desc, count, amount, avg in withdrawals:
        print(f"\n    {desc[:60]}")
        print(f"      Count: {count:,} withdrawals")
        print(f"      Total: ${amount or 0:,.2f}")
        print(f"      Average: ${avg or 0:,.2f}")
        total_withdrawn += amount or 0
    print(f"\n  TOTAL CASH WITHDRAWN: ${total_withdrawn:,.2f}")
else:
    print("  No cash withdrawals found")

# 5. Money Mart / Credit Card Payments
print("\n" + "=" * 100)
print("5. MONEY MART / CREDIT CARD LOAD PAYMENTS")
print("=" * 100)

cur.execute("""
    SELECT 
        description,
        COUNT(*) as count,
        SUM(debit_amount) as total_amount,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date
    FROM banking_transactions
    WHERE description ILIKE '%money%mart%'
       OR description ILIKE '%moneygram%'
       OR description ILIKE '%credit card%payment%'
       OR description ILIKE '%mastercard%'
       OR description ILIKE '%visa%'
    GROUP BY description
    ORDER BY total_amount DESC
""")
cc_payments = cur.fetchall()

if cc_payments:
    print(f"\n  Found {len(cc_payments)} types of credit card payments:")
    for desc, count, amount, first, last in cc_payments:
        print(f"\n    {desc[:70]}")
        print(f"      Payments: {count:,} times")
        print(f"      Total: ${amount or 0:,.2f}")
        print(f"      Period: {first} to {last}")
else:
    print("  WARNING: No Money Mart or credit card payments found!")
    print("  Check if customer checks used for credit card payments are logged")

# 6. Auto Withdrawals - Vehicle Payments (Heffner)
print("\n" + "=" * 100)
print("6. VEHICLE PAYMENTS - Heffner Auto Withdrawals")
print("=" * 100)

cur.execute("""
    SELECT 
        description,
        COUNT(*) as count,
        SUM(debit_amount) as total_amount,
        AVG(debit_amount) as avg_payment,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date
    FROM banking_transactions
    WHERE description ILIKE '%heffner%'
       OR description ILIKE '%vehicle%payment%'
       OR description ILIKE '%car%payment%'
       OR description ILIKE '%auto%loan%'
    GROUP BY description
    ORDER BY count DESC
""")
vehicle_payments = cur.fetchall()

if vehicle_payments:
    print(f"\n  Found {len(vehicle_payments)} types of vehicle payments:")
    for desc, count, amount, avg, first, last in vehicle_payments:
        print(f"\n    {desc[:70]}")
        print(f"      Payments: {count:,} times")
        print(f"      Total: ${amount or 0:,.2f}")
        print(f"      Average: ${avg or 0:,.2f} per payment")
        print(f"      Period: {first} to {last}")
else:
    print("  WARNING: No Heffner vehicle payments found!")
    print("  Search variations:")
    
    # Try broader search
    cur.execute("""
        SELECT DISTINCT description
        FROM banking_transactions
        WHERE description ILIKE '%hef%'
           OR description ILIKE '%auto%'
        LIMIT 10
    """)
    variations = cur.fetchall()
    if variations:
        print("  Found these variations:")
        for desc, in variations:
            print(f"    - {desc[:80]}")

# 7. Rent Payments
print("\n" + "=" * 100)
print("7. RENT PAYMENTS - Parking/Garage, Fibrenew")
print("=" * 100)

cur.execute("""
    SELECT 
        description,
        COUNT(*) as count,
        SUM(debit_amount) as total_amount,
        AVG(debit_amount) as avg_payment,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date
    FROM banking_transactions
    WHERE description ILIKE '%rent%'
       OR description ILIKE '%fibrenew%'
       OR description ILIKE '%parking%'
       OR description ILIKE '%garage%'
       OR description ILIKE '%lease%'
    GROUP BY description
    ORDER BY count DESC
""")
rent_payments = cur.fetchall()

if rent_payments:
    print(f"\n  Found {len(rent_payments)} types of rent payments:")
    for desc, count, amount, avg, first, last in rent_payments:
        print(f"\n    {desc[:70]}")
        print(f"      Payments: {count:,} times")
        print(f"      Total: ${amount or 0:,.2f}")
        print(f"      Average: ${avg or 0:,.2f} per payment")
        print(f"      Period: {first} to {last}")
else:
    print("  WARNING: No rent payments found!")

# 8. Internet/Phone Services
print("\n" + "=" * 100)
print("8. INTERNET, PHONE & WEB SERVICES")
print("=" * 100)

# Ionos webmail
cur.execute("""
    SELECT 
        'Ionos Webmail' as service,
        COUNT(*) as count,
        SUM(debit_amount) as total_amount,
        AVG(debit_amount) as avg_payment
    FROM banking_transactions
    WHERE description ILIKE '%ionos%'
""")
ionos = cur.fetchone()

# Microsoft
cur.execute("""
    SELECT 
        'Microsoft Software' as service,
        COUNT(*) as count,
        SUM(debit_amount) as total_amount,
        AVG(debit_amount) as avg_payment
    FROM banking_transactions
    WHERE description ILIKE '%microsoft%'
       OR description ILIKE '%office 365%'
       OR description ILIKE '%office365%'
""")
microsoft = cur.fetchone()

# Wix/GoDaddy
cur.execute("""
    SELECT 
        'Wix/GoDaddy' as service,
        COUNT(*) as count,
        SUM(debit_amount) as total_amount,
        AVG(debit_amount) as avg_payment
    FROM banking_transactions
    WHERE description ILIKE '%wix%'
       OR description ILIKE '%godaddy%'
""")
web = cur.fetchone()

# Rogers phone
cur.execute("""
    SELECT 
        'Rogers Phone' as service,
        COUNT(*) as count,
        SUM(debit_amount) as total_amount,
        AVG(debit_amount) as avg_payment
    FROM banking_transactions
    WHERE description ILIKE '%rogers%'
       OR description ILIKE '%telus%'
""")
phone = cur.fetchone()

# Xplorenet
cur.execute("""
    SELECT 
        'Xplorenet Internet' as service,
        COUNT(*) as count,
        SUM(debit_amount) as total_amount,
        AVG(debit_amount) as avg_payment
    FROM banking_transactions
    WHERE description ILIKE '%xplorenet%'
       OR description ILIKE '%xplore%'
""")
xplorenet = cur.fetchone()

services = [ionos, microsoft, web, phone, xplorenet]
found_any = False

for service, count, amount, avg in services:
    if count and count > 0:
        found_any = True
        print(f"\n  {service}:")
        print(f"    Payments: {count:,} times")
        print(f"    Total: ${amount or 0:,.2f}")
        print(f"    Average: ${avg or 0:,.2f} per payment")

if not found_any:
    print("\n  WARNING: No internet/phone/web service payments found!")
    print("  Checking for broader matches...")
    
    cur.execute("""
        SELECT DISTINCT description
        FROM banking_transactions
        WHERE description ILIKE '%internet%'
           OR description ILIKE '%phone%'
           OR description ILIKE '%web%'
           OR description ILIKE '%hosting%'
        LIMIT 15
    """)
    broader = cur.fetchall()
    if broader:
        print("  Found these potential services:")
        for desc, in broader:
            print(f"    - {desc[:80]}")

# 9. Uncategorized/Missing Categories
print("\n" + "=" * 100)
print("9. POTENTIAL MISSING CATEGORIZATIONS")
print("=" * 100)

cur.execute("""
    SELECT 
        description,
        COUNT(*) as count,
        SUM(debit_amount) as total_debit,
        SUM(credit_amount) as total_credit
    FROM banking_transactions
    WHERE description IS NOT NULL
      AND description != ''
      AND (
        -- Common expense patterns that might not be categorized
        description ILIKE '%utilities%'
        OR description ILIKE '%insurance%'
        OR description ILIKE '%fuel%'
        OR description ILIKE '%gas%'
        OR description ILIKE '%maintenance%'
        OR description ILIKE '%repair%'
        OR description ILIKE '%supplies%'
        OR description ILIKE '%equipment%'
      )
    GROUP BY description
    ORDER BY count DESC
    LIMIT 20
""")
uncategorized = cur.fetchall()

if uncategorized:
    print(f"\n  Found {len(uncategorized)} potentially uncategorized expense patterns:")
    for desc, count, debit, credit in uncategorized:
        print(f"\n    {desc[:70]}")
        print(f"      Occurrences: {count:,}")
        if debit and debit > 0:
            print(f"      Debits: ${debit:,.2f}")
        if credit and credit > 0:
            print(f"      Credits: ${credit:,.2f}")

# 10. Summary Statistics
print("\n" + "=" * 100)
print("10. SUMMARY & RECOMMENDATIONS")
print("=" * 100)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date) as year,
        COUNT(*) as transactions,
        SUM(debit_amount) as total_debits,
        SUM(credit_amount) as total_credits
    FROM banking_transactions
    GROUP BY EXTRACT(YEAR FROM transaction_date)
    ORDER BY year DESC
""")
by_year = cur.fetchall()

print("\n  Transactions by Year:")
for year, count, debits, credits in by_year:
    print(f"    {int(year)}: {count:,} transactions (Debits: ${debits or 0:,.2f}, Credits: ${credits or 0:,.2f})")

print("\n  RECOMMENDATIONS:")
print("  " + "-" * 96)

# Count missing categorizations
# Note: Skipping GL linkage check - would need to verify column names in general_ledger
# cur.execute("""
#     SELECT COUNT(*)
#     FROM banking_transactions bt
#     LEFT JOIN general_ledger gl ON bt.transaction_id = gl.reference_number::integer
#     WHERE gl.id IS NULL
# """)
# unlinked = cur.fetchone()[0]
# 
# if unlinked > 0:
#     print(f"  1. Link {unlinked:,} banking transactions to general ledger entries")

if not fees:
    print("  2. Add banking fees to transaction descriptions or general ledger")

if not vehicle_payments:
    print("  3. Verify Heffner vehicle payment tracking")

if not rent_payments:
    print("  4. Add rent payment tracking (parking/garage, Fibrenew)")

if not found_any:
    print("  5. Add internet/phone/web service payment tracking")

print("\n" + "=" * 100)
print("ANALYSIS COMPLETE")
print("=" * 100)

conn.close()
