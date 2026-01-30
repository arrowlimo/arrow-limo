"""
Remove Square and Auto-matched payments that are likely duplicates.
Keep only LMS-imported and Other payment sources.
"""

import psycopg2
import os
import argparse
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    parser = argparse.ArgumentParser(description='Remove Square and Auto-matched payments')
    parser.add_argument('--write', action='store_true', help='Actually delete payments')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        print("=" * 80)
        print("REMOVE SQUARE AND AUTO-MATCHED PAYMENTS")
        print("=" * 80)
        
        # Find Square payments
        cur.execute("""
            SELECT payment_id, reserve_number, amount, payment_date, notes
            FROM payments
            WHERE notes LIKE '%[Square]%'
            ORDER BY payment_date DESC
        """)
        square_payments = cur.fetchall()
        square_total = sum(p[2] for p in square_payments)
        
        print(f"\n📊 SQUARE PAYMENTS: {len(square_payments)} payments totaling ${square_total:,.2f}")
        
        if square_payments:
            print(f"\n   Sample (first 10):")
            print(f"   {'ID':<10} {'Reserve':<10} {'Amount':>12} {'Date':<12} Notes")
            print("   " + "-" * 80)
            for p in square_payments[:10]:
                notes_short = (p[4] or '')[:40]
                print(f"   {p[0]:<10} {p[1] or 'NULL':<10} ${p[2]:>10,.2f} {str(p[3]):<12} {notes_short}")
        
        # Find Auto-matched payments
        cur.execute("""
            SELECT payment_id, reserve_number, amount, payment_date, notes
            FROM payments
            WHERE notes LIKE '%AUTO-MATCHED%'
            ORDER BY payment_date DESC
        """)
        auto_payments = cur.fetchall()
        auto_total = sum(p[2] for p in auto_payments)
        
        print(f"\n📊 AUTO-MATCHED PAYMENTS: {len(auto_payments)} payments totaling ${auto_total:,.2f}")
        
        if auto_payments:
            print(f"\n   Sample (first 10):")
            print(f"   {'ID':<10} {'Reserve':<10} {'Amount':>12} {'Date':<12} Notes")
            print("   " + "-" * 80)
            for p in auto_payments[:10]:
                notes_short = (p[4] or '')[:40]
                print(f"   {p[0]:<10} {p[1] or 'NULL':<10} ${p[2]:>10,.2f} {str(p[3]):<12} {notes_short}")
        
        total_to_remove = len(square_payments) + len(auto_payments)
        amount_to_remove = square_total + auto_total
        
        print(f"\n{'='*80}")
        print(f"TOTAL TO REMOVE: {total_to_remove:,} payments totaling ${amount_to_remove:,.2f}")
        print("=" * 80)
        
        if not args.write:
            print(f"\n[WARN]  DRY RUN - No changes made. Use --write to apply.")
            return
        
        # Create backup
        backup_table = f"payments_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"\n📦 Creating backup: {backup_table}")
        
        cur.execute(f"""
            CREATE TABLE {backup_table} AS
            SELECT * FROM payments
            WHERE notes LIKE '%[Square]%' OR notes LIKE '%AUTO-MATCHED%'
        """)
        
        backup_count = cur.rowcount
        print(f"   ✓ Backed up {backup_count:,} payments")
        
        # Delete foreign key references first
        print(f"\n🔗 Removing foreign key references...")
        
        # Delete income_ledger entries
        cur.execute("""
            DELETE FROM income_ledger
            WHERE payment_id IN (
                SELECT payment_id FROM payments
                WHERE notes LIKE '%[Square]%' OR notes LIKE '%AUTO-MATCHED%'
            )
        """)
        income_deleted = cur.rowcount
        print(f"   ✓ Deleted {income_deleted:,} income_ledger entries")
        
        # Delete banking_payment_links entries
        cur.execute("""
            DELETE FROM banking_payment_links
            WHERE payment_id IN (
                SELECT payment_id FROM payments
                WHERE notes LIKE '%[Square]%' OR notes LIKE '%AUTO-MATCHED%'
            )
        """)
        banking_deleted = cur.rowcount
        print(f"   ✓ Deleted {banking_deleted:,} banking_payment_links entries")
        
        # Get affected charters before deletion
        cur.execute("""
            SELECT DISTINCT reserve_number
            FROM payments
            WHERE (notes LIKE '%[Square]%' OR notes LIKE '%AUTO-MATCHED%')
              AND reserve_number IS NOT NULL
        """)
        affected_reserves = [row[0] for row in cur.fetchall()]
        
        print(f"\n🗑️  Deleting payments...")
        
        # Delete Square payments
        cur.execute("DELETE FROM payments WHERE notes LIKE '%[Square]%'")
        square_deleted = cur.rowcount
        print(f"   ✓ Deleted {square_deleted:,} Square payments")
        
        # Delete Auto-matched payments
        cur.execute("DELETE FROM payments WHERE notes LIKE '%AUTO-MATCHED%'")
        auto_deleted = cur.rowcount
        print(f"   ✓ Deleted {auto_deleted:,} Auto-matched payments")
        
        # Recalculate affected charters
        print(f"\n🔄 Recalculating {len(affected_reserves):,} affected charters...")
        
        cur.execute("""
            WITH payment_sums AS (
                SELECT 
                    reserve_number,
                    ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as actual_paid
                FROM payments
                WHERE reserve_number = ANY(%s)
                GROUP BY reserve_number
            )
            UPDATE charters c
            SET paid_amount = COALESCE(ps.actual_paid, 0),
                balance = c.total_amount_due - COALESCE(ps.actual_paid, 0)
            FROM payment_sums ps
            WHERE c.reserve_number = ps.reserve_number
        """, (affected_reserves,))
        
        updated_count = cur.rowcount
        print(f"   ✓ Updated {updated_count:,} charters")
        
        # Also handle charters that now have zero payments
        cur.execute("""
            UPDATE charters c
            SET paid_amount = 0,
                balance = c.total_amount_due
            WHERE c.reserve_number = ANY(%s)
              AND NOT EXISTS (
                  SELECT 1 FROM payments p 
                  WHERE p.reserve_number = c.reserve_number
              )
        """, (affected_reserves,))
        
        zero_payment_count = cur.rowcount
        if zero_payment_count > 0:
            print(f"   ✓ Reset {zero_payment_count:,} charters to zero payments")
        
        conn.commit()
        
        print(f"\n{'='*80}")
        print("[OK] REMOVAL COMPLETE")
        print("=" * 80)
        print(f"\nDeleted:")
        print(f"  - {square_deleted:,} Square payments (${square_total:,.2f})")
        print(f"  - {auto_deleted:,} Auto-matched payments (${auto_total:,.2f})")
        print(f"  - {income_deleted:,} income_ledger entries")
        print(f"  - {banking_deleted:,} banking_payment_links entries")
        print(f"\nRecalculated:")
        print(f"  - {updated_count:,} charters with remaining payments")
        print(f"  - {zero_payment_count:,} charters now have zero payments")
        print(f"\nBackup: {backup_table}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n[FAIL] Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
