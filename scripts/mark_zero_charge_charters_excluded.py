#!/usr/bin/env python3
"""
Mark charters with $0 charges as excluded (no payment expected).
This will clean up the charters-without-payments list.
"""

import psycopg2
import argparse

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

def main():
    parser = argparse.ArgumentParser(description='Mark zero-charge charters as excluded')
    parser.add_argument('--apply', action='store_true', help='Actually apply the changes (default is dry-run)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("MARK ZERO-CHARGE CHARTERS AS EXCLUDED")
    print("=" * 100)
    print()
    
    if args.apply:
        print("🔧 APPLY MODE - Will update database")
    else:
        print("👀 DRY-RUN MODE - No changes will be made")
        print("   Run with --apply to actually update the database")
    
    print()
    
    # First, check if we need to add a column for exclusion tracking
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'charters' 
        AND column_name = 'payment_excluded'
    """)
    
    if not cur.fetchone():
        print("Adding 'payment_excluded' column to charters table...")
        if args.apply:
            cur.execute("""
                ALTER TABLE charters 
                ADD COLUMN payment_excluded BOOLEAN DEFAULT FALSE
            """)
            cur.execute("""
                COMMENT ON COLUMN charters.payment_excluded IS 
                'True if charter should be excluded from payment matching (e.g., $0 charges, cancelled with no payment expected)'
            """)
            conn.commit()
            print("[OK] Column added")
        else:
            print("   (Would add column in apply mode)")
        print()
    
    # Find charters with no payments and $0 charges
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            COALESCE(cc.total_charges, 0) as total_charges,
            c.cancelled,
            c.status
        FROM charters c
        LEFT JOIN (
            SELECT charter_id, SUM(COALESCE(amount, 0)) as total_charges
            FROM charter_charges
            GROUP BY charter_id
        ) cc ON c.charter_id = cc.charter_id
        WHERE NOT EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.charter_id = c.charter_id
        )
        AND EXTRACT(YEAR FROM c.charter_date) BETWEEN 2007 AND 2024
        AND COALESCE(cc.total_charges, 0) = 0
        ORDER BY c.charter_date
    """)
    
    zero_charge_charters = cur.fetchall()
    
    print(f"Found {len(zero_charge_charters):,} charters with $0 charges and no payments")
    print()
    
    # Breakdown by year
    year_counts = {}
    for row in zero_charge_charters:
        charter_id, reserve_num, charter_date, charges, cancelled, status = row
        if charter_date:
            year = charter_date.year
            year_counts[year] = year_counts.get(year, 0) + 1
    
    print("Breakdown by year:")
    print(f"{'Year':<8} {'Count':<10}")
    print("-" * 20)
    for year in sorted(year_counts.keys()):
        count = year_counts[year]
        print(f"{year:<8} {count:<10,}")
    
    print()
    print(f"{'Charter ID':<12} {'Reserve':<10} {'Date':<12} {'Charges':<12} {'Status':<15}")
    print("-" * 70)
    
    for row in zero_charge_charters[:20]:
        charter_id, reserve_num, charter_date, charges, cancelled, status = row
        date_str = charter_date.strftime('%Y-%m-%d') if charter_date else 'N/A'
        status_str = 'CANCELLED' if cancelled else (status or 'Unknown')
        print(f"{charter_id:<12} {reserve_num:<10} {date_str:<12} ${float(charges):<11.2f} {status_str:<15}")
    
    if len(zero_charge_charters) > 20:
        print(f"... and {len(zero_charge_charters) - 20:,} more")
    
    print()
    
    if args.apply:
        print("=" * 100)
        print("APPLYING EXCLUSION MARKS...")
        print("=" * 100)
        print()
        
        charter_ids = [row[0] for row in zero_charge_charters]
        
        # Update in batches
        batch_size = 1000
        updated_count = 0
        
        for i in range(0, len(charter_ids), batch_size):
            batch = charter_ids[i:i + batch_size]
            cur.execute("""
                UPDATE charters 
                SET payment_excluded = TRUE 
                WHERE charter_id = ANY(%s)
            """, (batch,))
            updated_count += len(batch)
            
            if updated_count % 1000 == 0 or updated_count == len(charter_ids):
                print(f"  Marked {updated_count:,} charters as payment_excluded...")
        
        conn.commit()
        
        print()
        print(f"[OK] Successfully marked {updated_count:,} charters as excluded")
        print()
        
        # Verify
        cur.execute("""
            SELECT COUNT(*)
            FROM charters
            WHERE payment_excluded = TRUE
        """)
        
        total_excluded = cur.fetchone()[0]
        
        print("=" * 100)
        print("VERIFICATION:")
        print("=" * 100)
        print()
        print(f"Total charters marked as payment_excluded: {total_excluded:,}")
        print()
        print("These charters will now be excluded from 'charters without payments' reports.")
        
    else:
        print("=" * 100)
        print("DRY-RUN COMPLETE")
        print("=" * 100)
        print()
        print(f"Would mark {len(zero_charge_charters):,} charters as payment_excluded")
        print()
        print("To apply these changes, run:")
        print(f"  python {__file__} --apply")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
