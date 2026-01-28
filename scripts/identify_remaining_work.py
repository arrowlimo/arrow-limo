#!/usr/bin/env python3
"""
Identify remaining reconciliation work that can be done without missing bank statements.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD')
    )


def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("=" * 80)
    print("REMAINING RECONCILIATION WORK (Without Missing Bank Statements)")
    print("=" * 80)

    # 1. Withdrawals to journal entries
    print("\n1. WITHDRAWALS → PETTY CASH JOURNALS")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as count,
            SUM(debit_amount) as total
        FROM banking_transactions
        WHERE debit_amount > 0
          AND (LOWER(description) LIKE '%withdrawal%' OR LOWER(description) LIKE '%atm%')
          AND receipt_id IS NULL
    """)
    withdrawals = cur.fetchone()
    
    print(f"Unlinked withdrawals: {withdrawals['count']:,} (${withdrawals['total']:,.2f})")
    print(f"Action: Create journal entries (Bank → Petty Cash)")
    print(f"Tool: create_withdrawal_transfer_journals.py --write --override-key ALLOW_...")
    print(f"Status: ⏳ Ready to apply")

    # 2. Other expenses not yet categorized
    print("\n2. OTHER EXPENSES (Needs Receipt Creation)")
    print("-" * 80)
    
    cur.execute("""
        WITH categorized AS (
            SELECT 
                CASE 
                    WHEN LOWER(description) LIKE '%pos purchase%' OR LOWER(description) LIKE '%point of sale%' THEN 'POS'
                    WHEN LOWER(description) LIKE '%nsf%' OR LOWER(description) LIKE '%non-sufficient%' THEN 'NSF'
                    WHEN LOWER(description) LIKE '%service charge%' OR LOWER(description) LIKE '%fee%' THEN 'Fee'
                    WHEN LOWER(description) LIKE '%withdrawal%' OR LOWER(description) LIKE '%atm%' THEN 'Withdrawal'
                    WHEN LOWER(description) LIKE '%transfer%' THEN 'Transfer'
                    ELSE 'Other'
                END as category,
                transaction_id,
                description,
                debit_amount,
                receipt_id
            FROM banking_transactions
            WHERE debit_amount > 0
        )
        SELECT COUNT(*) as count, SUM(debit_amount) as total
        FROM categorized
        WHERE category = 'Other' AND receipt_id IS NULL
    """)
    other = cur.fetchone()
    
    print(f"Other expenses unlinked: {other['count']:,} (${other['total']:,.2f})")
    
    # Sample some
    cur.execute("""
        WITH categorized AS (
            SELECT 
                CASE 
                    WHEN LOWER(description) LIKE '%pos purchase%' OR LOWER(description) LIKE '%point of sale%' THEN 'POS'
                    WHEN LOWER(description) LIKE '%nsf%' OR LOWER(description) LIKE '%non-sufficient%' THEN 'NSF'
                    WHEN LOWER(description) LIKE '%service charge%' OR LOWER(description) LIKE '%fee%' THEN 'Fee'
                    WHEN LOWER(description) LIKE '%withdrawal%' OR LOWER(description) LIKE '%atm%' THEN 'Withdrawal'
                    WHEN LOWER(description) LIKE '%transfer%' THEN 'Transfer'
                    ELSE 'Other'
                END as category,
                transaction_id,
                transaction_date,
                description,
                debit_amount,
                receipt_id
            FROM banking_transactions
            WHERE debit_amount > 0
        )
        SELECT transaction_date, description, debit_amount
        FROM categorized
        WHERE category = 'Other' AND receipt_id IS NULL
        ORDER BY debit_amount DESC
        LIMIT 10
    """)
    
    samples = cur.fetchall()
    if samples:
        print(f"\nTop unlinked other expenses:")
        for s in samples:
            print(f"  {s['transaction_date']} | ${s['debit_amount']:8.2f} | {s['description'][:60]}")
    
    print(f"\nAction: Analyze patterns and create receipts or categorize as transfers")
    print(f"Status: ⏳ Needs investigation")

    # 3. Payment-Charter linkage
    print("\n3. PAYMENT → CHARTER LINKAGE")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_payments,
            COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) as linked,
            SUM(amount) as total_amount,
            SUM(CASE WHEN charter_id IS NOT NULL THEN amount END) as linked_amount
        FROM payments
        WHERE amount > 0
    """)
    payment_charter = cur.fetchone()
    
    unlinked_payments = payment_charter['total_payments'] - payment_charter['linked']
    unlinked_amount = payment_charter['total_amount'] - (payment_charter['linked_amount'] or 0)
    
    print(f"Total payments: {payment_charter['total_payments']:,} (${payment_charter['total_amount']:,.2f})")
    print(f"Linked to charters: {payment_charter['linked']:,} (${payment_charter['linked_amount']:,.2f})")
    print(f"Unlinked: {unlinked_payments:,} (${unlinked_amount:,.2f})")
    print(f"\nAction: Match payments to charters by reserve_number/account_number")
    print(f"Status: ⏳ Can be improved")

    # 4. Driver payroll linkage
    print("\n4. DRIVER PAYROLL → EMPLOYEE LINKAGE")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_staging,
            COUNT(CASE WHEN EXISTS (
                                SELECT 1 FROM staging_driver_pay_links l 
                                WHERE l.staging_id = staging_driver_pay.id
            ) THEN 1 END) as linked
        FROM staging_driver_pay
    """)
    staging = cur.fetchone()
    
    unlinked_staging = staging['total_staging'] - staging['linked']
    link_pct = (staging['linked'] / staging['total_staging'] * 100) if staging['total_staging'] > 0 else 0
    
    print(f"Staging payroll records: {staging['total_staging']:,}")
    print(f"Linked to employees: {staging['linked']:,} ({link_pct:.1f}%)")
    print(f"Unlinked: {unlinked_staging:,}")
    print(f"\nAction: Expand name mapping, manual review of ambiguous cases")
    print(f"Status: ⏳ Ongoing improvement")

    # 5. Charter completion/quality
    print("\n5. CHARTER DATA QUALITY")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN client_id IS NULL THEN 1 END) as missing_client,
            COUNT(CASE WHEN rate = 0 OR rate IS NULL THEN 1 END) as missing_rate,
            COUNT(CASE WHEN payment_status IS NULL THEN 1 END) as missing_status,
            COUNT(CASE WHEN assigned_driver_id IS NULL THEN 1 END) as missing_driver
        FROM charters
        WHERE cancelled = false
    """)
    charter_quality = cur.fetchone()
    
    print(f"Total charters: {charter_quality['total']:,}")
    print(f"Missing client_id: {charter_quality['missing_client']:,}")
    print(f"Missing rate: {charter_quality['missing_rate']:,}")
    print(f"Missing payment_status: {charter_quality['missing_status']:,}")
    print(f"Missing driver: {charter_quality['missing_driver']:,}")
    print(f"\nAction: Data cleanup, populate missing fields from LMS if available")
    print(f"Status: ⏳ Data quality improvement")

    # 6. Receipt categorization
    print("\n6. RECEIPT CATEGORIZATION")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN category IS NULL OR category = '' THEN 1 END) as uncategorized,
            COUNT(CASE WHEN vendor_name IS NULL OR vendor_name = '' THEN 1 END) as missing_vendor
        FROM receipts
    """)
    receipt_quality = cur.fetchone()
    
    print(f"Total receipts: {receipt_quality['total']:,}")
    print(f"Uncategorized: {receipt_quality['uncategorized']:,}")
    print(f"Missing vendor: {receipt_quality['missing_vendor']:,}")
    print(f"\nAction: Auto-categorize by vendor patterns, GST verification")
    print(f"Status: ⏳ Enhancement opportunity")

    # 7. Vehicle fuel logs
    print("\n7. VEHICLE FUEL TRACKING")
    print("-" * 80)
    
    # Check if table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'vehicle_fuel_log'
        )
    """)
    
    if cur.fetchone()['exists']:
        cur.execute("""
            SELECT COUNT(*) as total FROM vehicle_fuel_log
        """)
        fuel_count = cur.fetchone()['total']
        
        # Check how many fuel receipts exist
        cur.execute("""
            SELECT COUNT(*) as count
            FROM receipts
            WHERE category LIKE '%fuel%' OR category LIKE '%gas%'
               OR vendor_name LIKE '%Shell%' OR vendor_name LIKE '%Petro%'
               OR vendor_name LIKE '%Esso%' OR vendor_name LIKE '%Fas Gas%'
        """)
        fuel_receipts = cur.fetchone()['count']
        
        print(f"Vehicle fuel log entries: {fuel_count:,}")
        print(f"Fuel receipts: {fuel_receipts:,}")
        print(f"\nAction: Link fuel receipts to vehicle_fuel_log, track mileage")
        print(f"Status: ⏳ Integration opportunity")
    else:
        print(f"Vehicle fuel log table not created")
        print(f"\nAction: Create vehicle_fuel_log table and populate from receipts")
        print(f"Status: ⏳ New feature")

    # 8. Square transaction reconciliation
    print("\n8. SQUARE TRANSACTIONS")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as square_payments,
            SUM(amount) as square_amount
        FROM payments
        WHERE square_transaction_id IS NOT NULL OR payment_method = 'credit_card'
    """)
    square = cur.fetchone()
    
    print(f"Square-related payments: {square['square_payments']:,} (${square['square_amount']:,.2f})")
    print(f"\nAction: Verify Square export completeness, reconcile with banking")
    print(f"Status: ⏳ Verification recommended")

    # Priority summary
    print("\n" + "=" * 80)
    print("PRIORITY RECOMMENDATIONS (Without Bank Statements)")
    print("=" * 80)
    
    print("""
HIGH PRIORITY:
1. [OK] Withdrawal journals (1,894 transactions, $1.5M) - Tool ready
2. [OK] Payment→Charter linking (35,902 unlinked payments) - Improve matching
3. [WARN]  Other expense receipts (1,650 transactions, $1.3M) - Needs investigation

MEDIUM PRIORITY:
4. 📊 Driver payroll expansion (262,000+ staging rows, 99.8% unlinked)
5. 📋 Charter data quality (missing clients, rates, statuses)
6. 🏷️  Receipt categorization (improve vendor/category tagging)

LOW PRIORITY:
7. 🚗 Vehicle fuel tracking integration
8. 💳 Square transaction verification
9. 📈 General ledger reconciliation

BLOCKED (Need Bank Statements):
- Income reconciliation for 2007-2016 (~$14.8M in payments)
- Historical banking analysis
- Complete deposit matching
""")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
