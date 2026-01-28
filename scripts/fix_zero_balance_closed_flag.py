"""
Fix charters with $0 balance that are not properly marked as closed.
Set closed = TRUE for all charters with $0 balance.
"""

import psycopg2
import os

def get_db_connection():
    """Create database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*120)
    print("FIX CHARTERS WITH $0 BALANCE - SET CLOSED FLAG")
    print("="*120 + "\n")
    
    # Get counts by status
    cur.execute("""
        SELECT 
            c.status,
            COUNT(*) as count
        FROM charters c
        WHERE c.balance = 0
          AND COALESCE(c.closed, FALSE) = FALSE
          AND COALESCE(c.cancelled, FALSE) = FALSE
          AND c.charter_date < CURRENT_DATE
        GROUP BY c.status
        ORDER BY count DESC
    """)
    
    status_breakdown = cur.fetchall()
    
    print("Current Status Breakdown:")
    print(f"{'Status':<30} {'Count':<10}")
    print("-" * 120)
    
    total_count = 0
    for status, count in status_breakdown:
        print(f"{status or '(NULL)':<30} {count:<10}")
        total_count += count
    
    print("-" * 120)
    print(f"{'TOTAL':<30} {total_count:<10}")
    
    print("\n" + "="*120)
    print("ACTIONS TO PERFORM:")
    print("="*120)
    print("1. Set closed = TRUE for all charters with balance = $0")
    print("2. Set status = 'Closed' for charters with NULL or non-standard status")
    print(f"\nThis will update {total_count} charters")
    print()
    
    response = input(f"Proceed with fixing {total_count} charters? (yes/no): ").strip().lower()
    
    if response != 'yes':
        print("Cancelled - no changes made")
        conn.rollback()
        cur.close()
        conn.close()
        return
    
    print("\nProcessing charters...\n")
    
    # Update charters that already have status = 'Closed'
    cur.execute("""
        UPDATE charters
        SET closed = TRUE,
            updated_at = CURRENT_TIMESTAMP
        WHERE balance = 0
          AND COALESCE(closed, FALSE) = FALSE
          AND COALESCE(cancelled, FALSE) = FALSE
          AND charter_date < CURRENT_DATE
          AND LOWER(status) = 'closed'
    """)
    
    closed_status_count = cur.rowcount
    print(f"✓ Set closed = TRUE for {closed_status_count} charters with status = 'Closed'")
    
    # Update charters that have status = 'Paid in Full'
    cur.execute("""
        UPDATE charters
        SET closed = TRUE,
            updated_at = CURRENT_TIMESTAMP
        WHERE balance = 0
          AND COALESCE(closed, FALSE) = FALSE
          AND COALESCE(cancelled, FALSE) = FALSE
          AND charter_date < CURRENT_DATE
          AND LOWER(status) = 'paid in full'
    """)
    
    paid_full_count = cur.rowcount
    print(f"✓ Set closed = TRUE for {paid_full_count} charters with status = 'Paid in Full'")
    
    # Update charters with NULL or 'UNCLOSED' status
    cur.execute("""
        UPDATE charters
        SET closed = TRUE,
            status = 'Closed',
            updated_at = CURRENT_TIMESTAMP
        WHERE balance = 0
          AND COALESCE(closed, FALSE) = FALSE
          AND COALESCE(cancelled, FALSE) = FALSE
          AND charter_date < CURRENT_DATE
          AND (status IS NULL OR LOWER(status) IN ('unclosed', 'n/a'))
    """)
    
    null_status_count = cur.rowcount
    print(f"✓ Set closed = TRUE and status = 'Closed' for {null_status_count} charters with NULL/UNCLOSED/N/A status")
    
    # Update any remaining charters (other statuses but balance is $0)
    cur.execute("""
        UPDATE charters
        SET closed = TRUE,
            updated_at = CURRENT_TIMESTAMP
        WHERE balance = 0
          AND COALESCE(closed, FALSE) = FALSE
          AND COALESCE(cancelled, FALSE) = FALSE
          AND charter_date < CURRENT_DATE
    """)
    
    remaining_count = cur.rowcount
    if remaining_count > 0:
        print(f"✓ Set closed = TRUE for {remaining_count} remaining charters")
    
    total_updated = closed_status_count + paid_full_count + null_status_count + remaining_count
    
    conn.commit()
    
    # Verify results
    print("\nVerifying results...")
    
    cur.execute("""
        SELECT COUNT(*)
        FROM charters
        WHERE balance = 0
          AND COALESCE(closed, FALSE) = FALSE
          AND COALESCE(cancelled, FALSE) = FALSE
          AND charter_date < CURRENT_DATE
    """)
    
    remaining_unfixed = cur.fetchone()[0]
    
    print("\n" + "="*120)
    print("COMPLETE!")
    print("="*120)
    print(f"\n✓ Updated {total_updated} charters")
    print(f"✓ Remaining charters with $0 balance not closed: {remaining_unfixed}")
    
    if remaining_unfixed == 0:
        print("\n✓ All charters with $0 balance are now properly marked as closed!")
    
    print("\n" + "="*120 + "\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
