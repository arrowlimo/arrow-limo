"""
Check the two receipt total columns: gross_amount vs expense
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*80)
    print("RECEIPT AMOUNT COLUMNS ANALYSIS")
    print("="*80)
    
    # Get all amount-related columns
    cur.execute("""
        SELECT column_name, data_type, is_nullable 
        FROM information_schema.columns 
        WHERE table_name = 'receipts' 
        AND column_name IN ('gross_amount', 'expense', 'amount', 'total', 'net_amount')
        ORDER BY ordinal_position
    """)
    
    print("\nAmount-related columns in receipts table:")
    for col in cur.fetchall():
        print(f"  {col[0]:20} {col[1]:15} Nullable: {col[2]}")
    
    # Check data distribution
    cur.execute("""
        SELECT 
            COUNT(*) as total_receipts,
            COUNT(*) FILTER (WHERE gross_amount IS NOT NULL) as gross_count,
            COUNT(*) FILTER (WHERE expense IS NOT NULL) as expense_count,
            COUNT(*) FILTER (WHERE gross_amount IS NULL AND expense IS NOT NULL) as only_expense,
            COUNT(*) FILTER (WHERE gross_amount IS NOT NULL AND expense IS NULL) as only_gross,
            COUNT(*) FILTER (WHERE gross_amount IS NOT NULL AND expense IS NOT NULL) as both,
            COUNT(*) FILTER (WHERE gross_amount IS NULL AND expense IS NULL) as neither
        FROM receipts
    """)
    
    stats = cur.fetchone()
    print("\n" + "="*80)
    print("DATA DISTRIBUTION")
    print("="*80)
    print(f"Total receipts: {stats[0]:,}")
    print(f"  gross_amount populated: {stats[1]:,}")
    print(f"  expense populated: {stats[2]:,}")
    print(f"  ONLY expense (no gross): {stats[3]:,}")
    print(f"  ONLY gross (no expense): {stats[4]:,}")
    print(f"  BOTH columns populated: {stats[5]:,}")
    print(f"  NEITHER column populated: {stats[6]:,}")
    
    # Show examples where only expense is populated
    print("\n" + "="*80)
    print("EXAMPLES: Receipts with ONLY expense (no gross_amount)")
    print("="*80)
    
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, expense, gst_amount, source_system
        FROM receipts
        WHERE expense IS NOT NULL AND gross_amount IS NULL
        LIMIT 20
    """)
    
    for row in cur.fetchall():
        print(f"ID {row[0]}: {row[1]} | {row[2]} | expense=${row[3]:.2f} | GST=${row[4] or 0:.2f} | {row[5]}")
    
    # Show examples where both are populated
    print("\n" + "="*80)
    print("EXAMPLES: Receipts with BOTH gross_amount AND expense")
    print("="*80)
    
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, expense, 
               ABS(gross_amount - expense) as difference
        FROM receipts
        WHERE expense IS NOT NULL AND gross_amount IS NOT NULL
        ORDER BY ABS(gross_amount - expense) DESC
        LIMIT 20
    """)
    
    for row in cur.fetchall():
        print(f"ID {row[0]}: {row[1]} | {row[2]} | gross=${row[3]:.2f} | expense=${row[4]:.2f} | diff=${row[5]:.2f}")
    
    # Check where values differ significantly
    cur.execute("""
        SELECT COUNT(*)
        FROM receipts
        WHERE gross_amount IS NOT NULL 
        AND expense IS NOT NULL
        AND ABS(gross_amount - expense) > 0.01
    """)
    
    diff_count = cur.fetchone()[0]
    print(f"\n⚠️  Receipts where gross_amount ≠ expense: {diff_count:,}")
    
    # Recommendation
    print("\n" + "="*80)
    print("RECOMMENDATION")
    print("="*80)
    print("\nThe 'expense' column appears to be a legacy field from old imports.")
    print("The 'gross_amount' column is the current standard (with gst_amount beside it).")
    print(f"\n✅ Should copy expense → gross_amount for {stats[3]:,} receipts that have ONLY expense")
    print(f"⚠️  Should review {diff_count:,} receipts where both exist but differ")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
