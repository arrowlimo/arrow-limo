#!/usr/bin/env python3
"""
Check if missing $513K in deposits exist in other tables
Compares 2012 totals across: payments, receipts, charter_charges, unified_general_ledger
"""
import psycopg2
import os

DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

conn = psycopg2.connect(**DSN)
cur = conn.cursor()

print("=" * 80)
print("SEARCHING FOR MISSING $513K IN DEPOSITS (2012)")
print("=" * 80)
print()
print("QuickBooks shows: $833,621.56 in deposits")
print("Database banking_transactions: $319,689.47 in credits")
print("Missing: $513,932.09")
print()
print("=" * 80)
print()

# Check payments table
print("📊 Checking PAYMENTS table...")
try:
    cur.execute("""
        SELECT 
            COUNT(*) as tx_count,
            COALESCE(SUM(amount), 0) as total_amount,
            MIN(payment_date) as first_date,
            MAX(payment_date) as last_date
        FROM payments
        WHERE EXTRACT(YEAR FROM payment_date) = 2012
    """)
    row = cur.fetchone()
    if row:
        count, total, first_date, last_date = row
        print(f"   Transactions: {int(count):,}")
        print(f"   Total Amount: ${float(total):,.2f}")
        print(f"   Date Range:   {first_date} to {last_date}")
        print()
        
        # Get payment method breakdown
        cur.execute("""
            SELECT 
                COALESCE(payment_method, 'UNKNOWN') as method,
                COUNT(*) as count,
                COALESCE(SUM(amount), 0) as total
            FROM payments
            WHERE EXTRACT(YEAR FROM payment_date) = 2012
            GROUP BY payment_method
            ORDER BY total DESC
        """)
        print("   By Payment Method:")
        for method_row in cur.fetchall():
            method, count, total = method_row
            print(f"     {method}: {int(count):,} payments, ${float(total):,.2f}")
        print()
except Exception as e:
    print(f"   [FAIL] Error: {e}\n")

# Check receipts table
print("📊 Checking RECEIPTS table...")
try:
    # First check what columns exist
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'receipts' AND column_name IN ('amount', 'gross_amount', 'net_amount')
    """)
    amount_cols = [row[0] for row in cur.fetchall()]
    amount_col = amount_cols[0] if amount_cols else 'gross_amount'
    
    cur.execute(f"""
        SELECT 
            COUNT(*) as tx_count,
            COALESCE(SUM({amount_col}), 0) as total_amount,
            MIN(receipt_date) as first_date,
            MAX(receipt_date) as last_date
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
    """)
    row = cur.fetchone()
    if row:
        count, total, first_date, last_date = row
        print(f"   Transactions: {int(count):,} (using column: {amount_col})")
        print(f"   Total Expenses: ${float(total):,.2f}")
        print(f"   Date Range:   {first_date} to {last_date}")
        conn.rollback()  # Roll back failed transaction
        print()
except Exception as e:
    print(f"   [FAIL] Error: {e}\n")

# Check charter_charges table
print("📊 Checking CHARTER_CHARGES table...")
try:
    conn.rollback()  # Clear any previous error state
    cur.execute("""
        SELECT 
            COUNT(*) as tx_count,
            COALESCE(SUM(amount), 0) as total_amount
        FROM charter_charges cc
        JOIN charters c ON cc.charter_id = c.charter_id
        WHERE EXTRACT(YEAR FROM c.charter_date) = 2012
    """)
    row = cur.fetchone()
    if row:
        count, total = row
        print(f"   Transactions: {int(count):,}")
        print(f"   Total Amount: ${float(total):,.2f}")
        print()
except Exception as e:
    print(f"   [FAIL] Error: {e}\n")

# Check unified_general_ledger for credits (revenue/deposits)
print("📊 Checking UNIFIED_GENERAL_LEDGER (Credits = Revenue/Deposits)...")
try:
    conn.rollback()  # Clear any previous error state
    cur.execute("""
        SELECT 
            COUNT(*) as tx_count,
            COALESCE(SUM(credit_amount), 0) as total_credits,
            COALESCE(SUM(debit_amount), 0) as total_debits
        FROM unified_general_ledger
        WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    row = cur.fetchone()
    if row:
        count, credits, debits = row
        print(f"   Transactions: {int(count):,}")
        print(f"   Total Credits (Revenue): ${float(credits):,.2f}")
        print(f"   Total Debits (Expenses): ${float(debits):,.2f}")
        print()
        
        # Get account breakdown for credits
        cur.execute("""
            SELECT 
                COALESCE(account_name, account_code::text, 'UNKNOWN') as account,
                COUNT(*) as count,
                COALESCE(SUM(credit_amount), 0) as total
            FROM unified_general_ledger
            WHERE EXTRACT(YEAR FROM transaction_date) = 2012
              AND credit_amount > 0
            GROUP BY account_name, account_code
            ORDER BY total DESC
            LIMIT 10
        """)
        print("   Top 10 Credit Accounts (Revenue Sources):")
        for acc_row in cur.fetchall():
            account, count, total = acc_row
            print(f"     {account}: {int(count):,} entries, ${float(total):,.2f}")
        print()
except Exception as e:
    print(f"   [FAIL] Error: {e}\n")

# Check charters table for total revenue
print("📊 Checking CHARTERS table (Revenue Recognition)...")
try:
    conn.rollback()  # Clear any previous error state
    cur.execute("""
        SELECT 
            COUNT(*) as charter_count,
            COALESCE(SUM(rate), 0) as total_rate,
            COALESCE(SUM(balance), 0) as total_balance,
            COALESCE(SUM(deposit), 0) as total_deposits,
            COALESCE(SUM(paid_amount), 0) as total_paid
        FROM charters
        WHERE EXTRACT(YEAR FROM charter_date) = 2012
    """)
    row = cur.fetchone()
    if row:
        count, rate, balance, deposit, paid = row
        print(f"   Charters: {int(count):,}")
        print(f"   Total Rate (Contracted): ${float(rate):,.2f}")
        print(f"   Total Balance Due: ${float(balance):,.2f}")
        print(f"   Total Deposits: ${float(deposit):,.2f}")
        print(f"   Total Paid Amount: ${float(paid):,.2f}")
        print()
except Exception as e:
    print(f"   [FAIL] Error: {e}\n")

# SUMMARY
print("=" * 80)
print("SUMMARY ANALYSIS")
print("=" * 80)
print()

# Calculate what we found
conn.rollback()  # Clear any transaction errors before summary
cur.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE EXTRACT(YEAR FROM payment_date) = 2012")
payments_total = float(cur.fetchone()[0])

cur.execute("SELECT COALESCE(SUM(credit_amount), 0) FROM unified_general_ledger WHERE EXTRACT(YEAR FROM transaction_date) = 2012")
gl_credits = float(cur.fetchone()[0])

cur.execute("SELECT COALESCE(SUM(credit_amount), 0) FROM banking_transactions WHERE EXTRACT(YEAR FROM transaction_date) = 2012")
banking_credits = float(cur.fetchone()[0])

print("Potential Sources for Missing $513K:")
print()
print(f"1. Payments Table:           ${payments_total:,.2f}")
print(f"2. General Ledger (Credits): ${gl_credits:,.2f}")
print(f"3. Banking Transactions:     ${banking_credits:,.2f}")
print()

if payments_total > banking_credits:
    diff = payments_total - banking_credits
    print(f"💡 INSIGHT: Payments table has ${diff:,.2f} MORE than banking!")
    print(f"   This suggests customer payments were recorded in 'payments' table")
    print(f"   but corresponding bank deposits may not have been imported.")
    print()

if gl_credits > banking_credits:
    diff = gl_credits - banking_credits
    print(f"💡 INSIGHT: General Ledger credits ${diff:,.2f} MORE than banking!")
    print(f"   This suggests GL has revenue entries that aren't in banking table.")
    print()

print("=" * 80)
print("RECOMMENDATION:")
print("=" * 80)
print()
print("The missing $513K in deposits is likely in one of these scenarios:")
print()
print("A) PAYMENTS table contains customer payments that should match deposits")
print("   → Need to reconcile payments to banking deposits by date/amount")
print()
print("B) GENERAL LEDGER has deposit entries from QuickBooks")
print("   → Need to extract GL deposit transactions and compare to QB reconciliation")
print()
print("C) Banking import was incomplete and transactions need to be re-imported")
print("   → Need to locate original 2012 CIBC files and re-import")
print()
print("Next step: Parse QuickBooks 1,040 transaction details and match against")
print("           payments table and general ledger to determine source.")
print()

cur.close()
conn.close()
