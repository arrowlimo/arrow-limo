"""
Apply write-offs for uncollectible charter balances.

Strategy:
- Reduce total_amount_due to match paid_amount
- Set balance to $0
- Reduces revenue recognition and GST liability
- Does NOT affect driver gratuity already paid

Targets:
- Pre-2020 charters (5+ years old)
- >90% paid charters (nearly complete)
"""

import psycopg2
import os
from datetime import datetime
from table_protection import protect_deletion, create_backup_before_delete

def get_db_connection():
    """Standard database connection."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def identify_writeoff_candidates(cur):
    """Identify charters for write-off."""
    
    # 2012-2019 charters with balances (preserving 2007-2011)
    cur.execute("""
        SELECT charter_id, reserve_number, charter_date, 
               total_amount_due, paid_amount, balance
        FROM charters
        WHERE cancelled = FALSE
          AND balance > 0
          AND EXTRACT(YEAR FROM charter_date) >= 2012
          AND EXTRACT(YEAR FROM charter_date) < 2020
        ORDER BY charter_date
    """)
    pre_2020 = cur.fetchall()
    
    # >90% paid charters from 2012 onwards
    cur.execute("""
        SELECT charter_id, reserve_number, charter_date,
               total_amount_due, paid_amount, balance
        FROM charters
        WHERE cancelled = FALSE
          AND balance > 0
          AND paid_amount > 0
          AND (paid_amount / NULLIF(total_amount_due, 0)) >= 0.90
          AND EXTRACT(YEAR FROM charter_date) >= 2012
        ORDER BY charter_date
    """)
    ninety_percent = cur.fetchall()
    
    # Combine and deduplicate
    all_candidates = {}
    for row in pre_2020:
        all_candidates[row[0]] = row
    for row in ninety_percent:
        all_candidates[row[0]] = row
    
    return list(all_candidates.values())

def apply_writeoffs(cur, candidates, dry_run=True):
    """Apply write-offs by reducing total_amount_due to match paid_amount."""
    
    if not candidates:
        print("[FAIL] No candidates to write off")
        return
    
    print(f"\n{'DRY RUN - ' if dry_run else ''}Applying write-offs to {len(candidates)} charters...")
    
    total_writeoff = sum(row[5] for row in candidates)  # balance column
    
    for charter_id, reserve_number, charter_date, total_due, paid, balance in candidates:
        adjustment = total_due - paid
        
        if dry_run:
            print(f"  {reserve_number}: ${total_due:,.2f} → ${paid:,.2f} (write off ${adjustment:,.2f})")
        else:
            cur.execute("""
                UPDATE charters
                SET total_amount_due = paid_amount,
                    balance = 0.00,
                    notes = COALESCE(notes || E'\n', '') || 
                            %s
                WHERE charter_id = %s
            """, (
                f"[{datetime.now().strftime('%Y-%m-%d')}] Write-off: Reduced total from ${total_due:.2f} to ${paid:.2f} (uncollectible)",
                charter_id
            ))
    
    print(f"\n{'Would write off' if dry_run else 'Wrote off'}: ${total_writeoff:,.2f} across {len(candidates)} charters")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Apply write-offs for uncollectible balances')
    parser.add_argument('--write', action='store_true', help='Actually apply write-offs (default: dry-run)')
    parser.add_argument('--override-key', help='Override key for backup protection')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        print("=" * 80)
        print("APPLY WRITE-OFFS FOR UNCOLLECTIBLE BALANCES")
        print("=" * 80)
        
        # Get candidates
        candidates = identify_writeoff_candidates(cur)
        
        if not candidates:
            print("✓ No write-off candidates found")
            return
        
        print(f"\n📊 Found {len(candidates)} write-off candidates")
        
        # Show summary by year
        by_year = {}
        for row in candidates:
            year = row[2].year
            if year not in by_year:
                by_year[year] = {'count': 0, 'amount': 0}
            by_year[year]['count'] += 1
            by_year[year]['amount'] += row[5]  # balance
        
        print("\n📅 BY YEAR:")
        for year in sorted(by_year.keys()):
            print(f"   {year}: {by_year[year]['count']:3d} charters, ${by_year[year]['amount']:,.2f} to write off")
        
        if args.write:
            # Create backup
            print("\n📦 Creating backup...")
            backup_name = create_backup_before_delete(
                cur, 
                'charters',
                condition=f"charter_id IN ({','.join(str(r[0]) for r in candidates)})"
            )
            print(f"   ✓ Backup: {backup_name}")
            
            # Apply write-offs
            apply_writeoffs(cur, candidates, dry_run=False)
            
            conn.commit()
            print("\n✓ Write-offs applied successfully")
            
            # Verify
            cur.execute("""
                SELECT COUNT(*), SUM(balance)
                FROM charters
                WHERE cancelled = FALSE AND balance > 0
            """)
            remaining_count, remaining_balance = cur.fetchone()
            print(f"\n📊 REMAINING BALANCES:")
            print(f"   {remaining_count} charters, ${remaining_balance or 0:,.2f} owing")
            
        else:
            print("\n" + "=" * 80)
            print("DRY RUN MODE")
            print("=" * 80)
            apply_writeoffs(cur, candidates, dry_run=True)
            print("\nTo apply write-offs, run with: --write")
        
    except Exception as e:
        conn.rollback()
        print(f"\n[FAIL] Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
