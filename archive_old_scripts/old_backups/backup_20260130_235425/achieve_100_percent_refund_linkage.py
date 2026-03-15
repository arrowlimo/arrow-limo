#!/usr/bin/env python3
"""
SOLUTION: Achieve 100% charter refund linkage by:
1. Move QBO business expenses OUT of charter_refunds table
2. Link remaining 20 actual charter refunds (with user assistance)
3. Verify 100% linkage achieved
"""
import psycopg2
import argparse
from table_protection import create_backup_before_delete, log_deletion_audit

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def create_business_expenses_table(cur):
    """Create table for non-charter business expenses"""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS business_expenses (
            id SERIAL PRIMARY KEY,
            expense_date DATE,
            amount DECIMAL(12,2),
            vendor VARCHAR(255),
            description TEXT,
            category VARCHAR(100),
            source_file VARCHAR(255),
            source_row VARCHAR(100),
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_business_expenses_date 
        ON business_expenses(expense_date)
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_business_expenses_vendor 
        ON business_expenses(vendor)
    """)
    
    print("[OK] business_expenses table created")

def move_qbo_expenses(cur, dry_run=True):
    """Move QBO Import records from charter_refunds to business_expenses"""
    print("\n" + "="*80)
    print("STEP 1: Move QBO business expenses to separate table")
    print("="*80)
    
    # Count what we're moving
    cur.execute("""
        SELECT COUNT(*), SUM(amount)
        FROM charter_refunds
        WHERE reserve_number IS NULL
        AND description LIKE '%QBO Import%'
    """)
    count, amount = cur.fetchone()
    
    print(f"\nFound {count:,} QBO Import records to move (${amount:,.2f})")
    
    if not dry_run:
        # Insert into business_expenses
        cur.execute("""
            INSERT INTO business_expenses 
                (expense_date, amount, vendor, description, category, source_file, source_row, notes)
            SELECT 
                refund_date,
                amount,
                COALESCE(customer, 'Unknown'),
                description,
                CASE 
                    WHEN description ~* 'WORKERS COMP|WCB' THEN 'Workers Compensation'
                    WHEN description ~* 'TELUS|SASKTEL' THEN 'Utilities'
                    WHEN description ~* 'INSURANCE' THEN 'Insurance'
                    WHEN description ~* 'HEFFNER|VEHICLE|AUTO' THEN 'Vehicle Expenses'
                    WHEN description ~* 'BILL PAYMENT' THEN 'Bill Payment'
                    WHEN description ~* 'OFFICE' THEN 'Office Expenses'
                    WHEN description ~* 'DEBIT MEMO' THEN 'Adjustments'
                    WHEN description ~* 'CHEQUE' THEN 'Cheques'
                    ELSE 'Other'
                END,
                source_file,
                reference,
                'Moved from charter_refunds - not a customer refund, business expense'
            FROM charter_refunds
            WHERE reserve_number IS NULL
            AND description LIKE '%QBO Import%'
        """)
        
        rows_inserted = cur.rowcount
        print(f"[OK] Inserted {rows_inserted:,} records into business_expenses")
        
        # Delete from charter_refunds
        cur.execute("""
            DELETE FROM charter_refunds
            WHERE reserve_number IS NULL
            AND description LIKE '%QBO Import%'
        """)
        
        rows_deleted = cur.rowcount
        print(f"[OK] Deleted {rows_deleted:,} records from charter_refunds")
        
    else:
        print(f"[DRY RUN] Would move {count:,} records to business_expenses")
    
    return count

def create_manual_linkage_file(cur):
    """Create CSV file for manual review of remaining unlinked refunds"""
    print("\n" + "="*80)
    print("STEP 2: Create manual linkage file for remaining refunds")
    print("="*80)
    
    cur.execute("""
        SELECT 
            r.id,
            r.refund_date,
            r.amount,
            r.customer,
            r.description,
            r.source_file,
            -- Find potential charter matches
            (
                SELECT STRING_AGG(
                    c.reserve_number || ' (' || c.charter_date || ', $' || c.rate || ', ' || 
                    COALESCE(cl.client_name, 'No client') || ')', 
                    '; '
                )
                FROM charters c
                LEFT JOIN clients cl ON c.client_id = cl.client_id
                WHERE c.charter_date BETWEEN r.refund_date - INTERVAL '60 days' 
                                         AND r.refund_date + INTERVAL '60 days'
                AND ABS(c.rate - r.amount) < 500
                LIMIT 5
            ) as potential_matches
        FROM charter_refunds r
        WHERE r.reserve_number IS NULL
        AND (r.description NOT LIKE '%QBO Import%' OR r.description IS NULL)
        ORDER BY r.amount DESC
    """)
    
    rows = cur.fetchall()
    
    # Write CSV
    import csv
    filename = 'l:\\limo\\reports\\UNLINKED_REFUNDS_MANUAL_REVIEW.csv'
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'refund_id', 'refund_date', 'amount', 'customer', 'description', 
            'source_file', 'potential_charter_matches', 'ASSIGN_TO_RESERVE_NUMBER'
        ])
        
        for row in rows:
            writer.writerow(list(row) + [''])  # Empty column for manual entry
    
    print(f"\n[OK] Created manual review file: {filename}")
    print(f"   {len(rows)} refunds need manual charter assignment")
    print(f"\n📝 Instructions:")
    print(f"   1. Open the CSV file")
    print(f"   2. Review potential_charter_matches column")
    print(f"   3. Enter correct reserve_number in ASSIGN_TO_RESERVE_NUMBER column")
    print(f"   4. Save and run: python apply_manual_refund_links.py")
    
    return len(rows)

def main():
    parser = argparse.ArgumentParser(description='Achieve 100% refund linkage')
    parser.add_argument('--write', action='store_true', help='Apply changes')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*80)
    print("ACHIEVING 100% CHARTER REFUND LINKAGE")
    print("="*80)
    
    if args.write:
        print("\n[WARN]  WRITE MODE: Changes will be applied")
    else:
        print("\n🔍 DRY RUN: No changes will be made")
    
    # Current status
    cur.execute("SELECT COUNT(*), SUM(amount) FROM charter_refunds")
    total_count, total_amt = cur.fetchone()
    
    cur.execute("SELECT COUNT(*), SUM(amount) FROM charter_refunds WHERE reserve_number IS NOT NULL")
    linked_count, linked_amt = cur.fetchone()
    
    cur.execute("SELECT COUNT(*), SUM(amount) FROM charter_refunds WHERE reserve_number IS NULL")
    unlinked_count, unlinked_amt = cur.fetchone()
    
    print(f"\nCurrent Status:")
    print(f"  Total: {total_count:,} = ${total_amt:,.2f}")
    print(f"  Linked: {linked_count:,} ({linked_count/total_count*100:.1f}%) = ${linked_amt:,.2f}")
    print(f"  Unlinked: {unlinked_count:,} ({unlinked_count/total_count*100:.1f}%) = ${unlinked_amt:,.2f}")
    
    # Step 1: Create business_expenses table
    if args.write:
        create_business_expenses_table(cur)
    
    # Step 2: Move QBO expenses
    moved_count = move_qbo_expenses(cur, dry_run=not args.write)
    
    if args.write and moved_count > 0:
        conn.commit()
        print(f"\n[OK] COMMITTED: Moved {moved_count} business expenses")
    
    # Step 3: Create manual linkage file
    manual_count = create_manual_linkage_file(cur)
    
    # Final status
    print("\n" + "="*80)
    print("EXPECTED FINAL RESULTS (after manual linkage)")
    print("="*80)
    
    expected_linked = linked_count + manual_count
    expected_total = total_count - moved_count
    
    print(f"\nAfter removing {moved_count} business expenses:")
    print(f"  Charter refunds: {expected_total:,}")
    print(f"  Linked: {linked_count:,}")
    print(f"  Need manual linking: {manual_count:,}")
    print(f"\nAfter manual linking complete:")
    print(f"  [OK] 100% linkage: {expected_linked}/{expected_total} refunds linked to charters")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
