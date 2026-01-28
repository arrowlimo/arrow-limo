#!/usr/bin/env python3
"""
Apply charter cancellations: delete charges and zero-balance pre-2025 charters with no payments.

Usage:
  python apply_charter_cancellations.py --dry-run    (default, shows preview)
  python apply_charter_cancellations.py --write       (applies changes)
"""

import sys
import os
import psycopg2
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def get_charters_to_cancel():
    """Get charters prior to 2025 with charges and no payments."""
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    query = """
    SELECT
        c.charter_id,
        c.reserve_number,
        c.charter_date,
        c.status,
        COALESCE(SUM(ch.amount), 0) as total_charges
    FROM charters c
    LEFT JOIN charter_charges ch ON ch.charter_id = c.charter_id
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number
    WHERE c.charter_date < '2025-01-01'
      AND p.reserve_number IS NULL
      AND c.notes NOT ILIKE '%trade%'
      AND c.notes NOT ILIKE '%gift%'
      AND c.notes NOT ILIKE '%promo%'
      AND c.status NOT IN ('Closed', 'closed_paid_verified', 'closed')
    GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.status
    HAVING COALESCE(SUM(ch.amount), 0) > 0
    ORDER BY c.charter_date DESC
    """
    
    cur.execute(query)
    charters = cur.fetchall()
    cur.close()
    conn.close()
    return charters

def apply_cancellations(charters):
    """Delete charges and zero-balance charters."""
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    try:
        total_deleted = 0
        total_charge_rows = 0
        total_amount = 0.0
        
        for charter_id, reserve_number, charter_date, status, charges in charters:
            # Delete all charges for this charter
            cur.execute("DELETE FROM charter_charges WHERE charter_id = %s", (charter_id,))
            deleted = cur.rowcount
            total_deleted += deleted
            total_charge_rows += deleted
            total_amount += float(charges)
            
            # Update charter status to cancelled (if not already)
            if status and status.lower() != 'cancelled':
                cur.execute(
                    "UPDATE charters SET status = %s WHERE charter_id = %s",
                    ('cancelled', charter_id)
                )
        
        conn.commit()
        print(f"\n✅ APPLIED {len(charters)} charter cancellations:")
        print(f"   • Deleted {total_charge_rows} charge records")
        print(f"   • Total charges deleted: ${total_amount:,.2f}")
        print(f"   • Status updated to 'cancelled'")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        return False
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    charters = get_charters_to_cancel()
    
    if not charters:
        print("No charters to cancel.")
        sys.exit(0)
    
    # Check for --write flag
    if "--write" in sys.argv:
        print(f"\n🔴 APPLYING CHANGES to {len(charters)} charters...")
        success = apply_cancellations(charters)
        sys.exit(0 if success else 1)
    else:
        print("DRY-RUN MODE (no changes made)")
        print(f"To apply, run: python apply_charter_cancellations.py --write")
