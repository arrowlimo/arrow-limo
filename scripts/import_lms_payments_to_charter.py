#!/usr/bin/env python3
"""
Import LMS payment data to charter_payments
These are the payments that are in LMS but not yet in ALMS charter_payments
"""

import psycopg2
from decimal import Decimal

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

# 24 charters needing payment import from LMS
TARGET_CHARTERS = [
    '019551', '019718', '007346', '006856', '019495', '019216', '019418', '008454',
    '007362', '019268', '008005', '019298', '019423', '007980', '019618', '019657',
    '007358', '019228', '019358', '008427', '019212', '008301', '006190', '007801',
]

try:
    conn = psycopg2.connect(f"host={DB_HOST} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}")
    cur = conn.cursor()
    
    print("="*100)
    print("IMPORT LMS PAYMENT DATA TO CHARTER_PAYMENTS")
    print("="*100)
    
    placeholders = ','.join([f"'{r}'" for r in TARGET_CHARTERS])
    
    # First, check what payment data exists in LMS for these charters
    print("\nAnalyzing LMS payments for 24 target charters...")
    cur.execute(f"""
        SELECT 
            lp.reserve_no,
            COUNT(*) as payment_count,
            SUM(lp.amount) as total_amount,
            MIN(lp.payment_date) as first_date,
            MAX(lp.payment_date) as last_date,
            STRING_AGG(DISTINCT COALESCE(lp.payment_method, 'unknown'), ', ') as methods
        FROM lms2026_payments lp
        WHERE lp.reserve_no IN ({placeholders})
        GROUP BY lp.reserve_no
        ORDER BY total_amount DESC
    """)
    
    lms_summary = cur.fetchall()
    total_lms_amount = Decimal('0.00')
    
    print("\nLMS payments to import:")
    for row in lms_summary:
        reserve_no, count, amount, first_date, last_date, methods = row
        amount = amount or Decimal('0.00')
        total_lms_amount += amount
        print(f"  {reserve_no:10} {count:3} payments | ${amount:12.2f} | {first_date} to {last_date}")
    
    print(f"\nTotal LMS payments to import: ${total_lms_amount:12.2f}")
    
    # Get charter_ids for these reserves (as VARCHAR)
    print("\nMapping reserve numbers to charter IDs...")
    cur.execute(f"""
        SELECT reserve_number, charter_id::VARCHAR
        FROM charters 
        WHERE reserve_number IN ({placeholders})
    """)
    
    charter_mapping = {}
    for reserve_no, charter_id in cur.fetchall():
        charter_mapping[reserve_no] = str(charter_id)  # Ensure it's a string
    
    print(f"Found {len(charter_mapping)} of {len(TARGET_CHARTERS)} charters")
    
    # Now insert LMS payments into charter_payments
    print("\n" + "="*100)
    print("INSERTING LMS PAYMENTS INTO CHARTER_PAYMENTS")
    print("="*100)
    
    insert_count = 0
    skip_count = 0
    
    # Get LMS payment details
    cur.execute(f"""
        SELECT 
            lp.reserve_no,
            lp.amount,
            lp.payment_date,
            COALESCE(lp.payment_method, 'unknown') as payment_method,
            lp.notes,
            lp.payment_id
        FROM lms2026_payments lp
        WHERE lp.reserve_no IN ({placeholders})
        ORDER BY lp.reserve_no, lp.payment_date
    """)
    
    lms_payments = cur.fetchall()
    
    for reserve_no, amount, payment_date, method, notes, payment_id in lms_payments:
        charter_id = charter_mapping.get(reserve_no)
        if not charter_id:
            skip_count += 1
            print(f"  ⚠️  {reserve_no}: No charter_id found, skipping")
            continue
        
        # Check if this payment already exists
        cur.execute("""
            SELECT payment_id FROM charter_payments 
            WHERE charter_id = %s AND amount = %s AND payment_date = %s
            LIMIT 1
        """, (charter_id, amount, payment_date))
        
        if cur.fetchone():
            skip_count += 1
            print(f"  ⏭️  {reserve_no}: Payment ${amount} on {payment_date} already exists, skipping")
            continue
        
        # Insert the payment
        try:
            cur.execute("""
                INSERT INTO charter_payments (
                    charter_id, 
                    amount, 
                    payment_date, 
                    payment_method, 
                    source, 
                    client_name,
                    charter_date,
                    imported_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (
                charter_id, 
                amount, 
                payment_date, 
                method, 
                'lms2026_import',
                reserve_no,
                None  # We don't have charter_date in the LMS payment record
            ))
            insert_count += 1
            print(f"  ✅ {reserve_no}: Inserted ${amount:10.2f} on {payment_date}")
        except Exception as e:
            skip_count += 1
            print(f"  ❌ {reserve_no}: Insert failed - {e}")
    
    # Commit changes
    print("\n" + "="*100)
    print("COMMIT RESULTS")
    print("="*100)
    
    try:
        conn.commit()
        print(f"✅ COMMITTED: {insert_count} payments imported")
        print(f"⏭️  SKIPPED: {skip_count} payments (duplicate or no charter)")
    except Exception as e:
        conn.rollback()
        print(f"❌ ROLLBACK: {e}")
    
    # Verify results
    print("\n" + "="*100)
    print("VERIFICATION: Charter payment totals after import")
    print("="*100)
    
    cur.execute(f"""
        SELECT 
            c.reserve_number,
            c.paid_amount as alms_paid,
            SUM(cp.amount) as imported_payments
        FROM charters c
        LEFT JOIN charter_payments cp ON c.charter_id::VARCHAR = cp.charter_id
        WHERE c.reserve_number IN ({placeholders})
        GROUP BY c.charter_id, c.reserve_number, c.paid_amount
        ORDER BY c.paid_amount DESC
        LIMIT 10
    """)
    
    print("\nFirst 10 charters after import:")
    for reserve_no, alms_paid, imported_total in cur.fetchall():
        imported_total = imported_total or Decimal('0.00')
        status = "✅" if abs((alms_paid or Decimal('0.00')) - imported_total) < Decimal('0.01') else "⚠️"
        print(f"  {status} {reserve_no:10} ALMS: ${alms_paid:12.2f} | Imported: ${imported_total:12.2f}")
    
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
