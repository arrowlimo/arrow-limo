"""
Migrate legacy 'expense' column values to standardized 'gross_amount'.

RULES:
1. If gross_amount = 0 and expense > 0: Copy expense → gross_amount (withdrawals)
2. If gross_amount > 0 and expense < 0: Keep gross_amount (revenue, expense was negative)
3. If both are same value: No action needed
4. If differ significantly: Flag for manual review
"""

import psycopg2
import os
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    print("="*80)
    print("MIGRATE LEGACY EXPENSE COLUMN TO GROSS_AMOUNT")
    print("="*80)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Case 1: gross_amount = 0, expense > 0 (withdrawals with missing gross)
    print("\nCase 1: gross_amount = 0, expense > 0 (withdrawals)")
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, expense
        FROM receipts
        WHERE gross_amount = 0 
        AND expense > 0
        ORDER BY expense DESC
        LIMIT 10
    """)
    
    case1_examples = cur.fetchall()
    cur.execute("""
        SELECT COUNT(*), SUM(expense)
        FROM receipts
        WHERE gross_amount = 0 AND expense > 0
    """)
    case1_stats = cur.fetchone()
    
    print(f"Found {case1_stats[0]:,} receipts | Total: ${case1_stats[1]:,.2f}")
    print("Examples:")
    for row in case1_examples:
        print(f"  ID {row[0]}: {row[1]} | {row[2]} | gross=${row[3]:.2f} | expense=${row[4]:.2f}")
    
    # Case 2: gross_amount > 0, expense < 0 (revenue with negative expense)
    print("\n" + "="*80)
    print("Case 2: gross_amount > 0, expense < 0 (revenue)")
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, expense
        FROM receipts
        WHERE gross_amount > 0 
        AND expense < 0
        ORDER BY gross_amount DESC
        LIMIT 10
    """)
    
    case2_examples = cur.fetchall()
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount), SUM(expense)
        FROM receipts
        WHERE gross_amount > 0 AND expense < 0
    """)
    case2_stats = cur.fetchone()
    
    print(f"Found {case2_stats[0]:,} receipts | Gross: ${case2_stats[1]:,.2f} | Expense: ${case2_stats[2]:,.2f}")
    print("Examples (these are correct - gross_amount should stay positive):")
    for row in case2_examples:
        print(f"  ID {row[0]}: {row[1]} | {row[2]} | gross=${row[3]:.2f} | expense=${row[4]:.2f}")
    
    # Case 3: Both positive but different (unusual)
    print("\n" + "="*80)
    print("Case 3: Both positive but different (needs review)")
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, expense, 
               ABS(gross_amount - expense) as diff
        FROM receipts
        WHERE gross_amount > 0 
        AND expense > 0
        AND ABS(gross_amount - expense) > 0.01
        ORDER BY ABS(gross_amount - expense) DESC
        LIMIT 10
    """)
    
    case3_examples = cur.fetchall()
    cur.execute("""
        SELECT COUNT(*)
        FROM receipts
        WHERE gross_amount > 0 AND expense > 0 
        AND ABS(gross_amount - expense) > 0.01
    """)
    case3_count = cur.fetchone()[0]
    
    print(f"Found {case3_count:,} receipts with conflicting values")
    if case3_count > 0:
        print("Examples:")
        for row in case3_examples:
            print(f"  ID {row[0]}: {row[1]} | {row[2]} | gross=${row[3]:.2f} | expense=${row[4]:.2f} | diff=${row[5]:.2f}")
    
    # Recommendation
    print("\n" + "="*80)
    print("RECOMMENDED MIGRATION")
    print("="*80)
    
    print(f"\n✅ Case 1: Update {case1_stats[0]:,} receipts (copy expense → gross_amount)")
    print(f"✅ Case 2: Keep {case2_stats[0]:,} receipts as-is (revenue entries correct)")
    print(f"⚠️  Case 3: Flag {case3_count:,} receipts for manual review")
    
    response = input("\nProceed with Case 1 migration (copy expense → gross_amount for withdrawals)? (yes/no): ")
    if response.lower() != 'yes':
        print("Aborted")
        return
    
    # Create backup
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'receipts_backup_expense_migration_{timestamp}'
    
    print(f"\nCreating backup: {backup_table}")
    cur.execute(f"""
        CREATE TABLE {backup_table} AS 
        SELECT * FROM receipts 
        WHERE gross_amount = 0 AND expense > 0
    """)
    
    cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
    backup_count = cur.fetchone()[0]
    print(f"✅ Backup created: {backup_count} rows")
    
    # Perform migration
    print("\nMigrating Case 1 receipts...")
    cur.execute("""
        UPDATE receipts
        SET gross_amount = expense,
            gst_amount = ROUND((expense * 0.05 / 1.05)::numeric, 2),
            net_amount = ROUND((expense - (expense * 0.05 / 1.05))::numeric, 2)
        WHERE gross_amount = 0 
        AND expense > 0
    """)
    
    updated_count = cur.rowcount
    print(f"✅ Updated {updated_count:,} receipts")
    
    conn.commit()
    
    # Verify
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)
    
    cur.execute("""
        SELECT COUNT(*)
        FROM receipts
        WHERE gross_amount = 0 AND expense > 0
    """)
    
    remaining = cur.fetchone()[0]
    print(f"Receipts with gross=0, expense>0: {remaining:,} (should be 0)")
    
    if remaining == 0:
        print("✅ Migration complete!")
    else:
        print(f"⚠️  WARNING: {remaining} receipts still need migration")
    
    print(f"\nBackup table: {backup_table}")
    print(f"To rollback: UPDATE receipts SET gross_amount = {backup_table}.gross_amount, gst_amount = {backup_table}.gst_amount FROM {backup_table} WHERE receipts.receipt_id = {backup_table}.receipt_id;")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
