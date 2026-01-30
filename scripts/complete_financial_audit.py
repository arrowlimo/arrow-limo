"""
Complete Financial Data Audit
Checks for anomalies, duplications, missing monthly lease payments, and data integrity.
"""

import psycopg2
from datetime import datetime, timedelta
from collections import defaultdict
import calendar

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def print_section(title):
    print(f'\n{"=" * 100}')
    print(f'{title}')
    print("=" * 100)

def audit_receipts():
    """Audit receipts for anomalies."""
    print_section('📋 RECEIPTS AUDIT')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 1. Check for unusual amounts
    cur.execute("""
        SELECT COUNT(*) as count, 
               SUM(CASE WHEN gross_amount > 10000 THEN 1 ELSE 0 END) as over_10k,
               SUM(CASE WHEN gross_amount > 50000 THEN 1 ELSE 0 END) as over_50k,
               SUM(CASE WHEN gross_amount < 0 THEN 1 ELSE 0 END) as negative,
               SUM(CASE WHEN gross_amount = 0 THEN 1 ELSE 0 END) as zero_amount
        FROM receipts
    """)
    count, over_10k, over_50k, negative, zero_amount = cur.fetchone()
    
    print(f'\n   Total receipts: {count:,}')
    print(f'   Over $10,000: {over_10k:,} ({(over_10k/count*100):.2f}%)')
    print(f'   Over $50,000: {over_50k:,} ({(over_50k/count*100):.2f}%)')
    print(f'   Negative amounts: {negative:,}')
    print(f'   Zero amounts: {zero_amount:,}')
    
    # 2. Missing vendor names
    cur.execute("""
        SELECT COUNT(*) as missing_vendor,
               SUM(gross_amount) as total_amount
        FROM receipts
        WHERE vendor_name IS NULL OR vendor_name = ''
    """)
    missing_vendor, vendor_amount = cur.fetchone()
    if missing_vendor > 0:
        print(f'\n   ⚠️  Missing vendor names: {missing_vendor:,} receipts (${vendor_amount:,.2f})')
    
    # 3. Future-dated receipts
    cur.execute("""
        SELECT COUNT(*) as future_count,
               MIN(receipt_date) as earliest_future
        FROM receipts
        WHERE receipt_date > CURRENT_DATE
    """)
    future_count, earliest_future = cur.fetchone()
    if future_count > 0:
        print(f'\n   ⚠️  Future-dated receipts: {future_count:,} (earliest: {earliest_future})')
    
    # 4. Check GST calculation accuracy
    cur.execute("""
        SELECT COUNT(*) as incorrect_gst
        FROM receipts
        WHERE gst_amount IS NOT NULL 
        AND gross_amount IS NOT NULL
        AND ABS(gst_amount - (gross_amount * 0.05 / 1.05)) > 0.02
    """)
    incorrect_gst = cur.fetchone()[0]
    if incorrect_gst > 0:
        print(f'\n   ⚠️  Incorrect GST calculations: {incorrect_gst:,}')
    
    # 5. Top 10 largest receipts
    cur.execute("""
        SELECT receipt_date, vendor_name, gross_amount, category
        FROM receipts
        ORDER BY gross_amount DESC
        LIMIT 10
    """)
    print(f'\n   Top 10 largest receipts:')
    for row in cur.fetchall():
        vendor = (row[1][:40] if row[1] else 'None').ljust(40)
        category = row[3] if row[3] else 'None'
        print(f'     {row[0]} | {vendor} | ${row[2]:>12,.2f} | {category}')
    
    cur.close()
    conn.close()

def audit_payments():
    """Audit payments for anomalies."""
    print_section('💳 PAYMENTS AUDIT')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 1. Overall stats
    cur.execute("""
        SELECT COUNT(*) as count,
               SUM(amount) as total,
               SUM(CASE WHEN amount > 10000 THEN 1 ELSE 0 END) as over_10k,
               SUM(CASE WHEN amount < 0 THEN 1 ELSE 0 END) as negative,
               SUM(CASE WHEN reserve_number IS NULL THEN 1 ELSE 0 END) as no_reserve
        FROM payments
    """)
    count, total, over_10k, negative, no_reserve = cur.fetchone()
    
    print(f'\n   Total payments: {count:,}')
    print(f'   Total amount: ${total:,.2f}')
    print(f'   Over $10,000: {over_10k:,} ({(over_10k/count*100):.2f}%)')
    print(f'   Negative amounts: {negative:,}')
    print(f'   Missing reserve_number: {no_reserve:,} ({(no_reserve/count*100):.2f}%)')
    
    # 2. Unmatched to charters
    cur.execute("""
        SELECT COUNT(*) as unmatched,
               SUM(amount) as unmatched_amount
        FROM payments p
        WHERE reserve_number IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM charters c 
            WHERE c.reserve_number = p.reserve_number
        )
    """)
    unmatched, unmatched_amt = cur.fetchone()
    if unmatched > 0:
        print(f'\n   ⚠️  Payments not matched to charters: {unmatched:,} (${unmatched_amt:,.2f})')
    
    # 3. Duplicate payment keys
    cur.execute("""
        SELECT payment_key, COUNT(*) as cnt, SUM(amount) as total
        FROM payments
        WHERE payment_key IS NOT NULL
        GROUP BY payment_key
        HAVING COUNT(*) > 10
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """)
    print(f'\n   Payment keys with >10 entries (batch payments):')
    for row in cur.fetchall():
        print(f'     {row[0][:50]:50} | {row[1]:5} payments | ${row[2]:>12,.2f}')
    
    # 4. Payment methods
    cur.execute("""
        SELECT payment_method, COUNT(*) as count, SUM(amount) as total
        FROM payments
        WHERE payment_method IS NOT NULL
        GROUP BY payment_method
        ORDER BY SUM(amount) DESC
    """)
    print(f'\n   Payment methods:')
    for row in cur.fetchall():
        method = (row[0][:30] if row[0] else 'None').ljust(30)
        print(f'     {method} | {row[1]:6,} payments | ${row[2]:>15,.2f}')
    
    cur.close()
    conn.close()

def audit_charters():
    """Audit charters for balance and payment issues."""
    print_section('🚗 CHARTERS AUDIT')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 1. Overall stats
    cur.execute("""
        SELECT COUNT(*) as count,
               SUM(total_amount_due) as total_due,
               SUM(paid_amount) as total_paid,
               SUM(balance) as total_balance,
               SUM(CASE WHEN balance < -100 THEN 1 ELSE 0 END) as overpaid,
               SUM(CASE WHEN balance > 100 AND NOT cancelled THEN 1 ELSE 0 END) as outstanding
        FROM charters
    """)
    count, total_due, total_paid, total_balance, overpaid, outstanding = cur.fetchone()
    
    print(f'\n   Total charters: {count:,}')
    print(f'   Total amount due: ${total_due:,.2f}')
    print(f'   Total paid: ${total_paid:,.2f}')
    print(f'   Total balance: ${total_balance:,.2f}')
    print(f'   Overpaid (>$100): {overpaid:,}')
    print(f'   Outstanding (>$100): {outstanding:,}')
    
    # 2. Balance integrity check
    cur.execute("""
        SELECT COUNT(*) as incorrect_balance
        FROM charters
        WHERE ABS(balance - (total_amount_due - paid_amount)) > 0.01
    """)
    incorrect = cur.fetchone()[0]
    if incorrect > 0:
        print(f'\n   ⚠️  Incorrect balance calculations: {incorrect:,}')
    
    # 3. Charters with payments but no charges
    cur.execute("""
        SELECT c.reserve_number, c.charter_date, c.paid_amount, c.total_amount_due
        FROM charters c
        WHERE c.paid_amount > 0
        AND c.total_amount_due = 0
        ORDER BY c.paid_amount DESC
        LIMIT 10
    """)
    no_charges = cur.fetchall()
    if no_charges:
        print(f'\n   ⚠️  Charters with payments but no charges: {len(no_charges)}')
        print(f'     Top 10:')
        for row in no_charges:
            print(f'       {row[0]} | {row[1]} | Paid: ${row[2]:,.2f} | Due: ${row[3]:,.2f}')
    
    # 4. Top overpayments
    cur.execute("""
         SELECT c.reserve_number, c.charter_date, cl.client_name, 
             c.total_amount_due, c.paid_amount, c.balance
         FROM charters c
         LEFT JOIN clients cl ON c.client_id = cl.client_id
         WHERE c.balance < -100
         ORDER BY c.balance
        LIMIT 10
    """)
    print(f'\n   Top 10 overpayments:')
    for row in cur.fetchall():
        client = (row[2][:30] if row[2] else 'None').ljust(30)
        print(f'     {row[0]} | {row[1]} | {client} | Due: ${row[3]:>8,.2f} | Paid: ${row[4]:>8,.2f} | Balance: ${row[5]:>8,.2f}')
    
    # 5. Top outstanding balances
    cur.execute("""
         SELECT c.reserve_number, c.charter_date, cl.client_name,
             c.total_amount_due, c.paid_amount, c.balance
         FROM charters c
         LEFT JOIN clients cl ON c.client_id = cl.client_id
         WHERE c.balance > 100
         AND c.cancelled = FALSE
         ORDER BY c.balance DESC
        LIMIT 10
    """)
    print(f'\n   Top 10 outstanding balances:')
    for row in cur.fetchall():
        client = (row[2][:30] if row[2] else 'None').ljust(30)
        print(f'     {row[0]} | {row[1]} | {client} | Due: ${row[3]:>8,.2f} | Paid: ${row[4]:>8,.2f} | Balance: ${row[5]:>8,.2f}')
    
    cur.close()
    conn.close()

def audit_vehicle_leases():
    """Audit vehicle lease payments for missing monthly payments."""
    print_section('🚙 VEHICLE LEASE PAYMENTS AUDIT')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 1. Identify lease payment vendors
    cur.execute("""
        SELECT vendor_name, 
               COUNT(*) as payment_count,
               MIN(receipt_date) as first_payment,
               MAX(receipt_date) as last_payment,
               AVG(gross_amount) as avg_amount,
               SUM(gross_amount) as total_paid
        FROM receipts
        WHERE (vendor_name LIKE '%HEFFNER%' 
           OR vendor_name LIKE '%CMB%'
           OR vendor_name LIKE '%LEASE%'
           OR vendor_name LIKE '%FINANCING%'
           OR vendor_name LIKE '%ACE TRUCK%'
           OR category = 'equipment_lease')
        AND gross_amount > 1000
        GROUP BY vendor_name
        ORDER BY SUM(gross_amount) DESC
    """)
    
    lease_vendors = cur.fetchall()
    print(f'\n   Lease payment vendors: {len(lease_vendors)}')
    print(f'\n   Vendor                                          | Count | First      | Last       | Avg Amount  | Total Paid')
    print(f'   {"-" * 115}')
    
    for row in lease_vendors:
        vendor = (row[0][:45] if row[0] else 'None').ljust(45)
        print(f'   {vendor} | {row[1]:5} | {row[2]} | {row[3]} | ${row[4]:>9,.2f} | ${row[5]:>12,.2f}')
    
    # 2. Check for missing monthly payments for each vendor
    print(f'\n   Checking for missing monthly payments...')
    
    for vendor_name, count, first_date, last_date, avg_amt, total in lease_vendors:
        if count < 3:  # Skip if less than 3 payments
            continue
            
        # Get all payment dates for this vendor
        cur.execute("""
            SELECT receipt_date, gross_amount
            FROM receipts
            WHERE vendor_name = %s
            ORDER BY receipt_date
        """, (vendor_name,))
        
        payments = cur.fetchall()
        
        # Check for gaps > 45 days (allowing some flexibility for monthly payments)
        missing_periods = []
        for i in range(len(payments) - 1):
            date1 = payments[i][0]
            date2 = payments[i+1][0]
            gap = (date2 - date1).days
            
            if gap > 45:
                expected_payments = gap // 30  # Rough estimate
                if expected_payments > 1:
                    missing_periods.append({
                        'start': date1,
                        'end': date2,
                        'gap_days': gap,
                        'expected_missing': expected_payments - 1
                    })
        
        if missing_periods:
            vendor_short = vendor_name[:60]
            print(f'\n   ⚠️  {vendor_short}')
            print(f'       Total payments: {count}, First: {first_date}, Last: {last_date}')
            print(f'       Missing payment periods:')
            for period in missing_periods:
                print(f'         {period["start"]} → {period["end"]} ({period["gap_days"]} days, ~{period["expected_missing"]} missing)')
    
    cur.close()
    conn.close()

def audit_banking():
    """Audit banking transactions."""
    print_section('🏦 BANKING TRANSACTIONS AUDIT')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 1. Overall stats by account
    cur.execute("""
        SELECT account_number,
               COUNT(*) as count,
               SUM(debit_amount) as total_debits,
               SUM(credit_amount) as total_credits,
               MIN(transaction_date) as first_date,
               MAX(transaction_date) as last_date
        FROM banking_transactions
        GROUP BY account_number
        ORDER BY account_number
    """)
    
    print(f'\n   Banking accounts:')
    print(f'   Account      | Transactions | Total Debits      | Total Credits     | First Date | Last Date')
    print(f'   {"-" * 110}')
    
    for row in cur.fetchall():
        acct = (row[0][:12] if row[0] else 'None').ljust(12)
        print(f'   {acct} | {row[1]:>12,} | ${row[2]:>15,.2f} | ${row[3]:>15,.2f} | {row[4]} | {row[5]}')
    
    # 2. Check for unusual gaps in transaction dates
    cur.execute("""
        WITH date_gaps AS (
            SELECT 
                account_number,
                transaction_date,
                LEAD(transaction_date) OVER (PARTITION BY account_number ORDER BY transaction_date) as next_date,
                LEAD(transaction_date) OVER (PARTITION BY account_number ORDER BY transaction_date) - transaction_date as gap_days
            FROM banking_transactions
        )
        SELECT account_number, transaction_date, next_date, gap_days
        FROM date_gaps
        WHERE gap_days > 90
        ORDER BY gap_days DESC
        LIMIT 10
    """)
    
    gaps = cur.fetchall()
    if gaps:
        print(f'\n   ⚠️  Gaps > 90 days in banking data:')
        for row in gaps:
            print(f'     {row[0]} | {row[1]} → {row[2]} ({row[3]} days)')
    
    # 3. Transactions without receipts
    cur.execute("""
        SELECT COUNT(*) as unlinked,
               SUM(debit_amount) as unlinked_debits
        FROM banking_transactions
        WHERE debit_amount > 0
        AND transaction_id NOT IN (
            SELECT banking_transaction_id 
            FROM banking_receipt_matching_ledger
        )
    """)
    unlinked, unlinked_amt = cur.fetchone()
    if unlinked > 0:
        print(f'\n   Banking debits without receipts: {unlinked:,} (${unlinked_amt:,.2f})')
    
    cur.close()
    conn.close()

def audit_payroll():
    """Audit payroll for missing data and anomalies."""
    print_section('👥 PAYROLL AUDIT')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 1. Overall stats
    cur.execute("""
        SELECT COUNT(*) as count,
               SUM(gross_pay) as total_gross,
               SUM(net_pay) as total_net,
               COUNT(DISTINCT employee_id) as unique_employees,
               COUNT(CASE WHEN employee_id IS NULL THEN 1 END) as missing_employee_id
        FROM driver_payroll
        WHERE payroll_class = 'WAGE' OR payroll_class IS NULL
    """)
    count, total_gross, total_net, unique_emp, missing_emp = cur.fetchone()
    
    print(f'\n   Total payroll records: {count:,}')
    print(f'   Total gross pay: ${total_gross:,.2f}')
    print(f'   Total net pay: ${total_net:,.2f}')
    print(f'   Unique employees: {unique_emp:,}')
    print(f'   Missing employee_id: {missing_emp:,} ({(missing_emp/count*100):.2f}%)')
    
    # 2. Check for missing monthly payroll by year
    cur.execute("""
        SELECT year, month, COUNT(*) as entries, SUM(gross_pay) as total
        FROM driver_payroll
        WHERE year >= 2012
        AND (payroll_class = 'WAGE' OR payroll_class IS NULL)
        GROUP BY year, month
        ORDER BY year, month
    """)
    
    payroll_by_month = cur.fetchall()
    
    # Find missing months
    if payroll_by_month:
        print(f'\n   Payroll coverage by year:')
        current_year = None
        year_data = defaultdict(list)
        
        for year, month, entries, total in payroll_by_month:
            if year:
                year_data[year].append(month)
        
        for year in sorted(year_data.keys()):
            months = sorted(year_data[year])
            missing_months = [m for m in range(1, 13) if m not in months]
            
            if missing_months:
                missing_names = [calendar.month_abbr[m] for m in missing_months]
                print(f'     {year}: {len(months):2} months | ⚠️  Missing: {", ".join(missing_names)}')
            else:
                print(f'     {year}: {len(months):2} months | ✓ Complete')
    
    # 3. Negative or zero pay
    cur.execute("""
        SELECT COUNT(*) as negative_gross,
               COUNT(CASE WHEN net_pay <= 0 THEN 1 END) as negative_net
        FROM driver_payroll
        WHERE gross_pay < 0
        OR net_pay <= 0
    """)
    neg_gross, neg_net = cur.fetchone()
    if neg_gross > 0 or neg_net > 0:
        print(f'\n   ⚠️  Negative gross pay: {neg_gross:,}')
        print(f'   ⚠️  Zero/negative net pay: {neg_net:,}')
    
    cur.close()
    conn.close()

def audit_journal():
    """Audit journal entries for duplicates and anomalies."""
    print_section('📒 JOURNAL ENTRIES AUDIT')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check what columns exist in journal table
    try:
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'journal'
            ORDER BY ordinal_position
        """)
        journal_cols = [row[0] for row in cur.fetchall()]
    
        if not journal_cols:
            print(f'\n   ⚠️  Table "journal" does not exist')
            cur.close()
            conn.close()
            return
    
        # Determine which date column to use
        date_col = None
        if 'transaction_date' in journal_cols:
            date_col = 'transaction_date'
        elif 'txn_date' in journal_cols:
            date_col = 'txn_date'
        elif 'date' in journal_cols:
            date_col = 'date'
    
        if not date_col:
            print(f'\n   ⚠️  Journal table exists but has no recognizable date column')
            print(f'   Available columns: {", ".join(journal_cols)}')
            cur.close()
            conn.close()
            return
    except Exception as e:
        print(f'\n   ⚠️  Error checking journal schema: {e}')
        cur.close()
        conn.close()
        return
    cur.execute(f"""
        SELECT COUNT(*) as count,
               SUM(debit_amount) as total_debits,
               SUM(credit_amount) as total_credits,
               MIN({date_col}) as first_date,
               MAX({date_col}) as last_date
        FROM journal
    """)
    count, total_debits, total_credits, first_date, last_date = cur.fetchone()
    
    print(f'\n   Total journal entries: {count:,}')
    print(f'   Total debits: ${total_debits:,.2f}')
    print(f'   Total credits: ${total_credits:,.2f}')
    print(f'   Balance: ${abs(total_debits - total_credits):,.2f}')
    print(f'   Date range: {first_date} to {last_date}')
    
    # 2. Check if debits = credits (should balance)
    if abs(total_debits - total_credits) > 1.00:
        print(f'\n   ⚠️  Journal does not balance! Difference: ${abs(total_debits - total_credits):,.2f}')
    else:
        print(f'\n   ✓ Journal balances correctly')
    
    # 3. Check for duplicate entries
    cur.execute(f"""
        SELECT {date_col}, account_code, debit_amount, credit_amount, 
               COUNT(*) as dup_count
        FROM journal
        GROUP BY {date_col}, account_code, debit_amount, credit_amount
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """)
    
    duplicates = cur.fetchall()
    if duplicates:
        print(f'\n   ⚠️  Potential duplicate journal entries: {len(duplicates)}')
        print(f'     Top 10:')
        for row in duplicates:
            print(f'       {row[0]} | {row[1]} | Debit: ${row[2]:,.2f} | Credit: ${row[3]:,.2f} | Count: {row[4]}')
    
    cur.close()
    conn.close()

def summary_report():
    """Generate summary statistics."""
    print_section('📊 FINANCIAL SUMMARY - ALL TABLES')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get counts for all major tables
    tables = [
        'receipts', 'payments', 'charters', 'banking_transactions',
        'driver_payroll', 'journal', 'clients', 'employees', 'vehicles'
    ]
    
    print(f'\n   Table                        | Records       | Date Range')
    print(f'   {"-" * 80}')
    
    for table in tables:
        try:
            # Try to get date range if table has a date column
            date_col = None
            if table == 'receipts':
                date_col = 'receipt_date'
            elif table == 'payments':
                date_col = 'payment_date'
            elif table == 'charters':
                date_col = 'charter_date'
            elif table == 'banking_transactions':
                date_col = 'transaction_date'
            elif table == 'journal':
                date_col = 'transaction_date'
            
            if date_col:
                cur.execute(f"""
                    SELECT COUNT(*), MIN({date_col}), MAX({date_col})
                    FROM {table}
                """)
                count, min_date, max_date = cur.fetchone()
                date_range = f'{min_date} to {max_date}' if min_date else 'N/A'
            else:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                date_range = 'N/A'
            
            print(f'   {table:28} | {count:>13,} | {date_range}')
        except Exception as e:
            print(f'   {table:28} | Error: {str(e)[:40]}')
    
    cur.close()
    conn.close()

def main():
    print("=" * 100)
    print("COMPREHENSIVE FINANCIAL AUDIT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)
    
    summary_report()
    audit_receipts()
    audit_payments()
    audit_charters()
    audit_vehicle_leases()
    audit_banking()
    audit_payroll()
    audit_journal()
    
    print_section('✅ AUDIT COMPLETE')
    print(f'\n   Report generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'   Review sections marked with ⚠️  for issues requiring attention')
    print()

if __name__ == '__main__':
    main()
