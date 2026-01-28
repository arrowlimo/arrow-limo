#!/usr/bin/env python3
"""
Create placeholder charter records for payments with reserve_number but no matching charter.
Uses payment data to populate basic charter fields.

Supports --dry-run (preview) and --apply (execute)
"""
import os
import sys
import psycopg2
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")


def main():
    apply_mode = ('--apply' in sys.argv or '--yes' in sys.argv)
    dry_run = ('--dry-run' in sys.argv)

    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    print("="*80)
    print("CREATE MISSING CHARTERS FROM PAYMENTS")
    print("="*80)

    # Get unique reserve numbers with payments but no charter
    cur.execute("""
        SELECT 
            p.reserve_number,
            MIN(p.payment_date) as first_payment_date,
            SUM(p.amount) as total_paid,
            COUNT(*) as payment_count,
            STRING_AGG(DISTINCT p.payment_method, ', ') as payment_methods,
            MAX(p.square_customer_name) as customer_name
        FROM payments p
        WHERE p.reserve_number IS NOT NULL 
        AND p.reserve_number <> ''
        AND NOT EXISTS (
            SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
        )
        GROUP BY p.reserve_number
        ORDER BY p.reserve_number DESC
    """)
    
    missing_reserves = cur.fetchall()
    print(f"Found {len(missing_reserves)} reserve numbers needing charter creation")
    
    if not missing_reserves:
        print("No missing charters to create.")
        cur.close()
        conn.close()
        return
    
    total_amount = sum(float(row[2]) for row in missing_reserves)
    print(f"Total payment amount: ${total_amount:,.2f}")
    
    print(f"\nReserves to create charters for:")
    for reserve, first_date, paid, count, methods, cust_name in missing_reserves[:20]:
        print(f"  {reserve} | First payment: {first_date} | ${paid:,.2f} ({count} payment(s)) | {cust_name or 'Unknown'}")
    
    if len(missing_reserves) > 20:
        print(f"  ... and {len(missing_reserves)-20} more")
    
    if not apply_mode:
        print(f"\nDry-run: would create {len(missing_reserves)} placeholder charters. Pass --apply to execute.")
        cur.close()
        conn.close()
        return
    
    print("\n" + "="*80)
    print("CREATING PLACEHOLDER CHARTERS")
    print("="*80)
    
    created_count = 0
    for reserve, first_date, paid, count, methods, cust_name in missing_reserves:
        try:
            # Try to find matching client by Square customer name or create unknown client
            client_id = None
            if cust_name:
                cur.execute("""
                    SELECT client_id 
                    FROM clients 
                    WHERE LOWER(COALESCE(client_name, company_name)) LIKE LOWER(%s)
                    LIMIT 1
                """, (f'%{cust_name}%',))
                result = cur.fetchone()
                if result:
                    client_id = result[0]
            
            # Get or create "Unknown Client" placeholder
            if not client_id:
                cur.execute("""
                    SELECT client_id FROM clients 
                    WHERE company_name = 'UNKNOWN CLIENT - NEEDS REVIEW'
                """)
                result = cur.fetchone()
                if result:
                    client_id = result[0]
                else:
                    cur.execute("""
                        INSERT INTO clients (company_name, status, created_at)
                        VALUES ('UNKNOWN CLIENT - NEEDS REVIEW', 'active', NOW())
                        RETURNING client_id
                    """)
                    client_id = cur.fetchone()[0]
            
            # Create placeholder charter
            cur.execute("""
                INSERT INTO charters (
                    reserve_number,
                    client_id,
                    charter_date,
                    total_amount_due,
                    paid_amount,
                    balance,
                    status,
                    is_placeholder,
                    notes,
                    created_at,
                    updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, 
                    'pending', true,
                    'PLACEHOLDER: Created from payment records. Needs review and completion.',
                    NOW(), NOW()
                )
                RETURNING charter_id
            """, (
                reserve,
                client_id,
                first_date,
                paid,  # Assume total_due = amount paid for now
                paid,
                0.0    # Balance = 0 since paid = total_due
            ))
            
            charter_id = cur.fetchone()[0]
            
            # Update payments to link charter_id
            cur.execute("""
                UPDATE payments
                SET charter_id = %s
                WHERE reserve_number = %s
            """, (charter_id, reserve))
            
            created_count += 1
            print(f"✅ Created charter {charter_id} for reserve {reserve} | Client: {client_id} | ${paid:,.2f}")
            
        except Exception as e:
            print(f"❌ Error creating charter for {reserve}: {e}")
            conn.rollback()
            continue
    
    conn.commit()
    print(f"\n✅ Successfully created {created_count} placeholder charters")
    print(f"\nThese charters are marked as is_placeholder=true and need:")
    print("  - Client verification/correction")
    print("  - Charter date/time details")
    print("  - Pickup/dropoff addresses")
    print("  - Vehicle and driver assignment")
    print("  - Service details and notes")
    
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
