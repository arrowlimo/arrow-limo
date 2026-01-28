#!/usr/bin/env python3
"""
Fix reserves 014617 and 014618 - both are promo/trade of services, not cancelled.
"""

import psycopg2
import pyodbc
import sys

# Connect to PostgreSQL
pg_conn = psycopg2.connect(
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***',
    host='localhost'
)
pg_cur = pg_conn.cursor()

# Connect to LMS
LMS_PATH = r'L:\limo\backups\lms.mdb'
lms_conn = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')
lms_cur = lms_conn.cursor()

reserves = ['014617', '014618']

print("=" * 120)
print("PROMO/TRADE OF SERVICES - RESERVES 014617 & 014618")
print("=" * 120)
print()

for reserve_no in reserves:
    print(f"\n{'=' * 120}")
    print(f"RESERVE {reserve_no}")
    print('=' * 120)
    
    # Check LMS
    lms_cur.execute("""
        SELECT Reserve_No, Name, PU_Date, Est_Charge, Balance, Deposit, Cancelled, Status, Pymt_Type
        FROM Reserve
        WHERE Reserve_No = ?
    """, (reserve_no,))
    lms_row = lms_cur.fetchone()
    
    if lms_row:
        print(f"\nLMS DATA:")
        print(f"  Reserve: {lms_row.Reserve_No}")
        print(f"  Name: {lms_row.Name}")
        print(f"  Date: {lms_row.PU_Date}")
        print(f"  Est_Charge: ${lms_row.Est_Charge}")
        print(f"  Balance: ${lms_row.Balance}")
        print(f"  Deposit: ${lms_row.Deposit}")
        print(f"  Cancelled: {lms_row.Cancelled}")
        print(f"  Status: {lms_row.Status}")
        print(f"  Payment Type: {lms_row.Pymt_Type}")
        
        lms_cancelled = lms_row.Cancelled if lms_row.Cancelled is not None else False
        lms_pymt_type = lms_row.Pymt_Type or ''
    else:
        print(f"\n⚠️  Reserve {reserve_no} NOT FOUND in LMS")
        lms_cancelled = None
        lms_pymt_type = ''
    
    # Check PostgreSQL
    pg_cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            cl.client_name,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            c.cancelled,
            c.status
        FROM charters c
        LEFT JOIN clients cl ON cl.client_id = c.client_id
        WHERE c.reserve_number = %s
    """, (reserve_no,))
    pg_row = pg_cur.fetchone()
    
    if pg_row:
        charter_id, reserve, charter_date, client, total, paid, balance, cancelled, status = pg_row
        
        print(f"\nPOSTGRESQL DATA:")
        print(f"  Charter ID: {charter_id}")
        print(f"  Client: {client}")
        print(f"  Date: {charter_date}")
        print(f"  Total Due: ${total}")
        print(f"  Paid: ${paid}")
        print(f"  Balance: ${balance}")
        print(f"  Cancelled: {cancelled}")
        print(f"  Status: {status}")
        
        # Check payments
        pg_cur.execute("""
            SELECT payment_id, amount, payment_date, payment_method, notes
            FROM payments
            WHERE reserve_number = %s
            ORDER BY payment_date
        """, (reserve_no,))
        payments = pg_cur.fetchall()
        
        if payments:
            print(f"\n  PAYMENTS ({len(payments)}):")
            for pid, amt, pdate, method, notes in payments:
                print(f"    {pdate}: ${amt:,.2f} via {method or 'unknown'} - {notes or 'no notes'}")
        else:
            print(f"\n  NO PAYMENTS FOUND")
        
        print(f"\nANALYSIS:")
        if lms_pymt_type and 'trade' in lms_pymt_type.lower():
            print(f"  ℹ️  LMS Payment Type: '{lms_pymt_type}' (PROMO/TRADE)")
        if cancelled:
            print(f"  ⚠️  Currently marked CANCELLED in PostgreSQL")
        if total == 0.01 and paid == 0.01 and balance == 0:
            print(f"  ✓ Already paid via trade")
        elif total == 0.01 and paid == 0 and balance == 0.01:
            print(f"  ⚠️  Needs trade_of_services payment to clear $0.01 balance")
    else:
        print(f"\n⚠️  Reserve {reserve_no} NOT FOUND in PostgreSQL")

print()
print("=" * 120)
print("APPLY FIX? Run with --apply flag")
print("=" * 120)

if '--apply' in sys.argv:
    print()
    print("APPLYING FIXES...")
    print()
    
    # Create backup
    pg_cur.execute(f"""
        CREATE TABLE IF NOT EXISTS charters_promo_backup_20251123 AS
        SELECT * FROM charters 
        WHERE reserve_number IN ('014617', '014618')
    """)
    print("✓ Backup created: charters_promo_backup_20251123")
    
    for reserve_no in reserves:
        print(f"\nProcessing {reserve_no}...")
        
        # Get current state
        pg_cur.execute("""
            SELECT charter_id, total_amount_due, paid_amount, balance, cancelled
            FROM charters
            WHERE reserve_number = %s
        """, (reserve_no,))
        charter = pg_cur.fetchone()
        
        if not charter:
            print(f"  ⚠️  Skipped - not found")
            continue
        
        charter_id, total, paid, balance, cancelled = charter
        
        # Uncancel if needed
        if cancelled:
            pg_cur.execute("""
                UPDATE charters
                SET cancelled = FALSE,
                    status = 'closed'
                WHERE reserve_number = %s
            """, (reserve_no,))
            print(f"  ✓ Uncancelled (set cancelled=FALSE, status='closed')")
        
        # Add payment if balance is unpaid
        if total == 0.01 and balance == 0.01:
            # Check if trade payment already exists
            pg_cur.execute("""
                SELECT COUNT(*) FROM payments
                WHERE reserve_number = %s
                AND payment_method = 'trade_of_services'
            """, (reserve_no,))
            has_trade = pg_cur.fetchone()[0] > 0
            
            if not has_trade:
                pg_cur.execute("""
                    INSERT INTO payments (
                        reserve_number,
                        amount,
                        payment_date,
                        payment_method,
                        notes,
                        created_at
                    ) VALUES (
                        %s,
                        0.01,
                        CURRENT_DATE,
                        'trade_of_services',
                        'Promo/trade of services - correction',
                        NOW()
                    )
                """, (reserve_no,))
                print(f"  ✓ Added trade_of_services payment for $0.01")
                
                # Update balance
                pg_cur.execute("""
                    UPDATE charters
                    SET paid_amount = 0.01,
                        balance = 0.00
                    WHERE reserve_number = %s
                """, (reserve_no,))
                print(f"  ✓ Updated paid_amount=$0.01, balance=$0.00")
            else:
                print(f"  ℹ️  Trade payment already exists")
        elif paid == 0.01 and balance == 0:
            print(f"  ✓ Already paid and balanced")
    
    pg_conn.commit()
    
    print()
    print("=" * 120)
    print("✅ SUCCESS! Reserves 014617 & 014618 fixed:")
    print("   - Uncancelled (if needed)")
    print("   - Trade of services payments recorded (if needed)")
    print("   - Balances cleared to $0.00")
    print()
    print("Rollback: DROP TABLE charters_promo_backup_20251123;")
    print("=" * 120)

pg_cur.close()
pg_conn.close()
lms_cur.close()
lms_conn.close()
