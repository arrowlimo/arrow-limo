"""
Comprehensive duplicate detection across all tables.
Identifies duplicates from multiple import sources (LMS, QuickBooks, Banking, Excel, CSV, etc.)
"""
import psycopg2
import hashlib
from collections import defaultdict
import os

os.environ['DB_HOST'] = 'localhost'
os.environ['DB_NAME'] = 'almsdata'
os.environ['DB_USER'] = 'postgres'
os.environ['DB_PASSWORD'] = '***REMOVED***'

def generate_hash(*args):
    """Generate deterministic hash from multiple fields."""
    key = "|".join(str(a) for a in args)
    return hashlib.sha256(key.encode('utf-8')).hexdigest()

def check_receipts_duplicates(cur):
    """Check receipts table for duplicates."""
    print("=" * 80)
    print("1. RECEIPTS TABLE - Duplicate Detection")
    print("=" * 80)
    print()
    
    # Check by date + vendor + amount (most common duplicate pattern)
    cur.execute("""
        SELECT 
            receipt_date,
            vendor_name,
            gross_amount,
            COUNT(*) as count,
            array_agg(receipt_id ORDER BY receipt_id) as ids,
            array_agg(created_from_banking ORDER BY receipt_id) as auto_flags,
            array_agg(COALESCE(description, 'N/A') ORDER BY receipt_id) as descriptions
        FROM receipts
        GROUP BY receipt_date, vendor_name, gross_amount
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, gross_amount DESC
    """)
    
    duplicates = cur.fetchall()
    
    if duplicates:
        total_dupes = sum(row[3] - 1 for row in duplicates)
        dupe_amount = sum((row[3] - 1) * row[2] for row in duplicates)
        
        print(f"Found {len(duplicates)} duplicate groups ({total_dupes} duplicate records)")
        print(f"Duplicate amount: ${dupe_amount:,.2f}")
        print()
        
        print("Top 10 duplicate groups:")
        print("-" * 80)
        for i, (date, vendor, amount, count, ids, auto_flags, descs) in enumerate(duplicates[:10], 1):
            print(f"\n{i}. {date} | {vendor[:40]} | ${amount:,.2f} ({count} copies)")
            for j, (receipt_id, auto, desc) in enumerate(zip(ids, auto_flags, descs), 1):
                auto_str = "[AUTO]" if auto else "[MANUAL]"
                print(f"   ID {receipt_id:6} {auto_str:8} | {desc[:50]}")
        
        if len(duplicates) > 10:
            print(f"\n... and {len(duplicates) - 10} more duplicate groups")
    else:
        print("✅ No duplicates found in receipts table")
    
    print()
    return len(duplicates) if duplicates else 0

def check_payments_duplicates(cur):
    """Check payments table for duplicates."""
    print("=" * 80)
    print("2. PAYMENTS TABLE - Duplicate Detection")
    print("=" * 80)
    print()
    
    # Check by reserve_number + amount + payment_date
    cur.execute("""
        SELECT 
            reserve_number,
            amount,
            payment_date,
            COUNT(*) as count,
            array_agg(payment_id ORDER BY payment_id) as ids,
            array_agg(COALESCE(payment_key, 'N/A') ORDER BY payment_id) as keys,
            array_agg(COALESCE(payment_method, 'N/A') ORDER BY payment_id) as methods
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number, amount, payment_date
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, amount DESC
    """)
    
    duplicates = cur.fetchall()
    
    if duplicates:
        total_dupes = sum(row[3] - 1 for row in duplicates)
        dupe_amount = sum((row[3] - 1) * row[1] for row in duplicates)
        
        print(f"Found {len(duplicates)} duplicate groups ({total_dupes} duplicate records)")
        print(f"Duplicate amount: ${dupe_amount:,.2f}")
        print()
        
        print("Top 10 duplicate groups:")
        print("-" * 80)
        for i, (rsv, amount, date, count, ids, keys, methods) in enumerate(duplicates[:10], 1):
            print(f"\n{i}. Rsv {rsv} | {date} | ${amount:,.2f} ({count} copies)")
            for j, (payment_id, key, method) in enumerate(zip(ids, keys, methods), 1):
                print(f"   ID {payment_id:6} | Key: {key[:20]:<20} | Method: {method}")
        
        if len(duplicates) > 10:
            print(f"\n... and {len(duplicates) - 10} more duplicate groups")
    else:
        print("✅ No duplicates found in payments table")
    
    print()
    return len(duplicates) if duplicates else 0

def check_banking_duplicates(cur):
    """Check banking_transactions table for duplicates."""
    print("=" * 80)
    print("3. BANKING_TRANSACTIONS TABLE - Duplicate Detection")
    print("=" * 80)
    print()
    
    # Check by account + date + description + amount
    cur.execute("""
        SELECT 
            account_number,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            COUNT(*) as count,
            array_agg(transaction_id ORDER BY transaction_id) as ids
        FROM banking_transactions
        GROUP BY account_number, transaction_date, description, debit_amount, credit_amount
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, COALESCE(debit_amount, credit_amount) DESC
    """)
    
    duplicates = cur.fetchall()
    
    if duplicates:
        total_dupes = sum(row[5] - 1 for row in duplicates)
        
        print(f"Found {len(duplicates)} duplicate groups ({total_dupes} duplicate records)")
        print()
        
        print("Top 10 duplicate groups:")
        print("-" * 80)
        for i, (acct, date, desc, debit, credit, count, ids) in enumerate(duplicates[:10], 1):
            amount = debit if debit else credit
            type_str = "DR" if debit else "CR"
            print(f"\n{i}. {date} | {acct} | {type_str} ${amount:,.2f} ({count} copies)")
            print(f"   Description: {desc[:60]}")
            print(f"   Transaction IDs: {ids[:5]}{'...' if len(ids) > 5 else ''}")
        
        if len(duplicates) > 10:
            print(f"\n... and {len(duplicates) - 10} more duplicate groups")
    else:
        print("✅ No duplicates found in banking_transactions table")
    
    print()
    return len(duplicates) if duplicates else 0

def check_charter_charges_duplicates(cur):
    """Check charter_charges table for duplicates."""
    print("=" * 80)
    print("4. CHARTER_CHARGES TABLE - Duplicate Detection")
    print("=" * 80)
    print()
    
    # Check by charter_id + description + amount
    cur.execute("""
        SELECT 
            charter_id,
            description,
            amount,
            COUNT(*) as count,
            array_agg(charge_id ORDER BY charge_id) as ids
        FROM charter_charges
        GROUP BY charter_id, description, amount
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, amount DESC
    """)
    
    duplicates = cur.fetchall()
    
    if duplicates:
        total_dupes = sum(row[3] - 1 for row in duplicates)
        dupe_amount = sum((row[3] - 1) * row[2] for row in duplicates)
        
        print(f"Found {len(duplicates)} duplicate groups ({total_dupes} duplicate records)")
        print(f"Duplicate amount: ${dupe_amount:,.2f}")
        print()
        
        print("Top 10 duplicate groups:")
        print("-" * 80)
        for i, (charter_id, desc, amount, count, ids) in enumerate(duplicates[:10], 1):
            print(f"\n{i}. Charter {charter_id} | ${amount:,.2f} ({count} copies)")
            print(f"   Description: {desc[:60]}")
            print(f"   Charge IDs: {ids}")
        
        if len(duplicates) > 10:
            print(f"\n... and {len(duplicates) - 10} more duplicate groups")
    else:
        print("✅ No duplicates found in charter_charges table")
    
    print()
    return len(duplicates) if duplicates else 0

def check_journal_duplicates(cur):
    """Check journal/unified_general_ledger for duplicates."""
    print("=" * 80)
    print("5. JOURNAL TABLE - Duplicate Detection")
    print("=" * 80)
    print()
    
    # Check if journal table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'journal'
        )
    """)
    
    if not cur.fetchone()[0]:
        print("⚠️  journal table does not exist")
        print()
        return 0
    
    # Get actual column names first
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'journal' 
        ORDER BY ordinal_position
    """)
    columns = [row[0] for row in cur.fetchall()]
    
    # Journal table uses mixed-case column names with spaces
    # Check by date + account + description + amount
    cur.execute("""
        SELECT 
            "Date",
            "Account",
            "Memo/Description",
            "Debit",
            "Credit",
            COUNT(*) as count,
            array_agg(journal_id ORDER BY journal_id) as ids
        FROM journal
        GROUP BY "Date", "Account", "Memo/Description", "Debit", "Credit"
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, COALESCE("Debit", "Credit") DESC
    """)
    
    duplicates = cur.fetchall()
    
    if duplicates:
        total_dupes = sum(row[5] - 1 for row in duplicates)
        
        print(f"Found {len(duplicates)} duplicate groups ({total_dupes} duplicate records)")
        print()
        
        print("Top 10 duplicate groups:")
        print("-" * 80)
        for i, (date, acct, memo, debit, credit, count, ids) in enumerate(duplicates[:10], 1):
            amount = debit if debit else credit
            type_str = "DR" if debit else "CR"
            print(f"\n{i}. {date} | {acct} | {type_str} ${amount:,.2f} ({count} copies)")
            print(f"   Memo: {(memo or 'N/A')[:60]}")
            print(f"   IDs: {ids[:5]}{'...' if len(ids) > 5 else ''}")
        
        if len(duplicates) > 10:
            print(f"\n... and {len(duplicates) - 10} more duplicate groups")
    else:
        print("✅ No duplicates found in journal table")
    
    print()
    return len(duplicates) if duplicates else 0

def check_employee_payroll_duplicates(cur):
    """Check driver_payroll table for duplicates."""
    print("=" * 80)
    print("6. DRIVER_PAYROLL TABLE - Duplicate Detection")
    print("=" * 80)
    print()
    
    # Check by employee_id + pay_date + gross_pay (excluding adjustments)
    cur.execute("""
        SELECT 
            employee_id,
            pay_date,
            gross_pay,
            COUNT(*) as count,
            array_agg(id ORDER BY id) as ids,
            array_agg(COALESCE(source, 'N/A') ORDER BY id) as sources
        FROM driver_payroll
        WHERE payroll_class IS NULL OR payroll_class != 'ADJUSTMENT'
        GROUP BY employee_id, pay_date, gross_pay
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, gross_pay DESC
    """)
    
    duplicates = cur.fetchall()
    
    if duplicates:
        total_dupes = sum(row[3] - 1 for row in duplicates)
        dupe_amount = sum((row[3] - 1) * (row[2] or 0) for row in duplicates)
        
        print(f"Found {len(duplicates)} duplicate groups ({total_dupes} duplicate records)")
        print(f"Duplicate amount: ${dupe_amount:,.2f}")
        print()
        
        print("Top 10 duplicate groups:")
        print("-" * 80)
        for i, (emp_id, date, gross, count, ids, sources) in enumerate(duplicates[:10], 1):
            print(f"\n{i}. Employee {emp_id or 'NULL'} | {date} | ${gross:,.2f} ({count} copies)")
            for j, (payroll_id, source) in enumerate(zip(ids, sources), 1):
                print(f"   ID {payroll_id:6} | Source: {source}")
        
        if len(duplicates) > 10:
            print(f"\n... and {len(duplicates) - 10} more duplicate groups")
    else:
        print("✅ No duplicates found in driver_payroll table")
    
    print()
    return len(duplicates) if duplicates else 0

def check_rent_ledger_duplicates(cur):
    """Check rent_debt_ledger table for duplicates."""
    print("=" * 80)
    print("7. RENT_DEBT_LEDGER TABLE - Duplicate Detection")
    print("=" * 80)
    print()
    
    # Check by vendor + date + type + amounts
    cur.execute("""
        SELECT 
            vendor_name,
            transaction_date,
            transaction_type,
            charge_amount,
            payment_amount,
            COUNT(*) as count,
            array_agg(id ORDER BY id) as ids
        FROM rent_debt_ledger
        GROUP BY vendor_name, transaction_date, transaction_type, charge_amount, payment_amount
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, COALESCE(charge_amount, payment_amount) DESC
    """)
    
    duplicates = cur.fetchall()
    
    if duplicates:
        total_dupes = sum(row[5] - 1 for row in duplicates)
        
        print(f"Found {len(duplicates)} duplicate groups ({total_dupes} duplicate records)")
        print()
        
        print("Top 10 duplicate groups:")
        print("-" * 80)
        for i, (vendor, date, txn_type, charge, payment, count, ids) in enumerate(duplicates[:10], 1):
            amount = charge if charge else payment
            print(f"\n{i}. {vendor[:40]} | {date} | {txn_type} | ${amount:,.2f} ({count} copies)")
            print(f"   IDs: {ids}")
        
        if len(duplicates) > 10:
            print(f"\n... and {len(duplicates) - 10} more duplicate groups")
    else:
        print("✅ No duplicates found in rent_debt_ledger table")
    
    print()
    return len(duplicates) if duplicates else 0

def main():
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("COMPREHENSIVE DUPLICATE DETECTION ACROSS ALL TABLES")
    print("=" * 80)
    print()
    print("Checking for duplicates from multiple import sources:")
    print("- LMS Access DB imports")
    print("- QuickBooks exports (Excel, CSV, PDF)")
    print("- Banking statements (CIBC, Scotia)")
    print("- Square payments")
    print("- Email parsing")
    print("- Manual entries")
    print()
    
    # Run all checks
    results = {}
    results['receipts'] = check_receipts_duplicates(cur)
    results['payments'] = check_payments_duplicates(cur)
    results['banking'] = check_banking_duplicates(cur)
    results['charter_charges'] = check_charter_charges_duplicates(cur)
    results['journal'] = check_journal_duplicates(cur)
    results['payroll'] = check_employee_payroll_duplicates(cur)
    results['rent_ledger'] = check_rent_ledger_duplicates(cur)
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    
    total_issues = sum(results.values())
    
    for table, count in results.items():
        status = "✅ CLEAN" if count == 0 else f"⚠️  {count} duplicate groups"
        print(f"{table.upper():<20} : {status}")
    
    print()
    
    if total_issues == 0:
        print("🎉 NO DUPLICATES FOUND - All tables are clean!")
    else:
        print(f"⚠️  TOTAL: {total_issues} tables with duplicates")
        print()
        print("NEXT STEPS:")
        print("1. Review duplicate groups above")
        print("2. Create cleanup scripts for each affected table")
        print("3. Use --write flag with backup to remove duplicates")
    
    print("=" * 80)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
