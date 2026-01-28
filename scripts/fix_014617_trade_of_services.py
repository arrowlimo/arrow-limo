#!/usr/bin/env python3
"""
Fix reserve 014617 - should not be cancelled, was trade of services.
"""

import psycopg2
import pyodbc

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

print("=" * 120)
print("RESERVE 014617 - Trade of Services Investigation")
print("=" * 120)
print()

# Check LMS status
lms_cur.execute("""
    SELECT Reserve_No, Name, PU_Date, Est_Charge, Balance, Deposit, Cancelled, Status
    FROM Reserve
    WHERE Reserve_No = '014617'
""")
lms_row = lms_cur.fetchone()

if lms_row:
    print("LMS DATA:")
    print(f"  Reserve: {lms_row.Reserve_No}")
    print(f"  Name: {lms_row.Name}")
    print(f"  Date: {lms_row.PU_Date}")
    print(f"  Est_Charge: ${lms_row.Est_Charge}")
    print(f"  Balance: ${lms_row.Balance}")
    print(f"  Deposit: ${lms_row.Deposit}")
    print(f"  Cancelled: {lms_row.Cancelled}")
    print(f"  Status: {lms_row.Status}")
    print()
    
    lms_cancelled = lms_row.Cancelled if lms_row.Cancelled is not None else False
    lms_status = lms_row.Status or ''
    
    print(f"LMS shows: Cancelled={lms_cancelled}, Status='{lms_status}'")
else:
    print("⚠️  Reserve 014617 NOT FOUND in LMS")
    lms_cancelled = None
print()

# Check PostgreSQL status
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
    WHERE c.reserve_number = '014617'
""")
pg_row = pg_cur.fetchone()

if pg_row:
    charter_id, reserve, charter_date, client, total, paid, balance, cancelled, status = pg_row
    
    print("POSTGRESQL DATA:")
    print(f"  Charter ID: {charter_id}")
    print(f"  Reserve: {reserve}")
    print(f"  Date: {charter_date}")
    print(f"  Client: {client}")
    print(f"  Total Due: ${total}")
    print(f"  Paid: ${paid}")
    print(f"  Balance: ${balance}")
    print(f"  Cancelled: {cancelled}")
    print(f"  Status: {status}")
    print()
    
    # Check for payments
    pg_cur.execute("""
        SELECT payment_id, amount, payment_date, payment_method, notes
        FROM payments
        WHERE reserve_number = '014617'
        ORDER BY payment_date
    """)
    payments = pg_cur.fetchall()
    
    if payments:
        print(f"PAYMENTS ({len(payments)}):")
        for pid, amt, pdate, method, notes in payments:
            print(f"  {pdate}: ${amt:,.2f} via {method or 'unknown'} - {notes or 'no notes'}")
    else:
        print("NO PAYMENTS FOUND")
    print()
    
    # Analysis
    print("ANALYSIS:")
    if cancelled:
        print("  ⚠️  Currently marked as CANCELLED")
    
    if balance == 0.01 and paid == 0:
        print("  ℹ️  $0.01 balance with $0 paid - no payments recorded")
        print("  ℹ️  This was trade of services - should record payment")
        print()
        print("RECOMMENDED ACTIONS:")
        print("  1. Uncancel the charter (set cancelled=FALSE)")
        print("  2. Add trade_of_services payment for $0.01")
        print("  3. Update balance to $0.00")
else:
    print("⚠️  Reserve 014617 NOT FOUND in PostgreSQL")

print()
print("=" * 120)
print("Apply fix? Run with --apply flag")
print("=" * 120)

import sys
if '--apply' in sys.argv:
    print()
    print("APPLYING FIX...")
    print()
    
    if not pg_row:
        print("❌ Cannot apply fix - charter not found in PostgreSQL")
        sys.exit(1)
    
    # Create backup
    pg_cur.execute("""
        CREATE TABLE IF NOT EXISTS charters_014617_backup_20251123 AS
        SELECT * FROM charters WHERE reserve_number = '014617'
    """)
    print("✓ Backup created: charters_014617_backup_20251123")
    
    # Update cancelled status
    pg_cur.execute("""
        UPDATE charters
        SET cancelled = FALSE,
            status = 'closed'
        WHERE reserve_number = '014617'
    """)
    print("✓ Set cancelled=FALSE, status='closed'")
    
    # Add trade_of_services payment if it doesn't exist
    pg_cur.execute("""
        SELECT COUNT(*) FROM payments 
        WHERE reserve_number = '014617'
        AND payment_method = 'trade_of_services'
    """)
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
                '014617',
                0.01,
                '2022-05-28',
                'trade_of_services',
                'Trade of services - correction from cancelled status',
                NOW()
            )
        """)
        print("✓ Added trade_of_services payment for $0.01")
    
    # Recalculate balance
    pg_cur.execute("""
        UPDATE charters c
        SET paid_amount = 0.01,
            balance = 0.00
        WHERE reserve_number = '014617'
    """)
    print("✓ Updated paid_amount=$0.01, balance=$0.00")
    
    pg_conn.commit()
    
    print()
    print("✅ SUCCESS! Reserve 014617 fixed:")
    print("   - Uncancelled")
    print("   - Trade of services payment recorded")
    print("   - Balance cleared to $0.00")
    print()
    print("Rollback: DROP TABLE charters_014617_backup_20251123;")

pg_cur.close()
pg_conn.close()
lms_cur.close()
lms_conn.close()
