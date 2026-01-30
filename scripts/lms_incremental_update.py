#!/usr/bin/env python3
"""
LMS INCREMENTAL UPDATE FROM BACKUP DATABASE
===========================================

Connects to LMS database in backup folder and performs incremental updates
to almsdata with any changes since the last synchronization.
"""

import os
import pyodbc
import psycopg2
from datetime import datetime, timedelta
import pandas as pd

# Database connections
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '***REDACTED***')

# LMS Database path - check common backup locations
LMS_PATHS = [
    r'L:\limo\lms.mdb',
    r'L:\limo\backups\lms.mdb', 
    r'L:\limo\backup\lms.mdb', 
    r'L:\limo\lms backup\lms.mdb',
    r'L:\limo\database\lms.mdb',
    r'L:\limo\data\lms.mdb'
]

def find_lms_database():
    """Find the LMS database file in backup folders."""
    print("🔍 SEARCHING FOR LMS DATABASE")
    print("-" * 30)
    
    for path in LMS_PATHS:
        if os.path.exists(path):
            print(f"   [OK] Found LMS database: {path}")
            return path
        else:
            print(f"   [FAIL] Not found: {path}")
    
    # Check if user can provide path
    custom_path = input("\n   Enter LMS database path (or press Enter to skip): ").strip()
    if custom_path and os.path.exists(custom_path):
        return custom_path
    
    return None

def get_pg_connection():
    """Get PostgreSQL connection."""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def get_lms_connection(lms_path):
    """Get LMS Access database connection."""
    # Try 64-bit driver first, then fall back to 32-bit
    drivers = [
        'Microsoft Access Driver (*.mdb, *.accdb)',  # 64-bit
        'Microsoft Access Driver (*.mdb)'            # Legacy
    ]
    
    for driver in drivers:
        try:
            conn_str = f'DRIVER={{{driver}}};DBQ={lms_path};'
            return pyodbc.connect(conn_str)
        except pyodbc.Error as e:
            print(f"   [WARN]  Driver '{driver}' failed: {str(e)}")
            continue
    
    raise Exception("No compatible Access driver found. Please install Microsoft Access Database Engine.")

def get_last_sync_timestamp(pg_cur):
    """Get the timestamp of the last LMS synchronization."""
    try:
        # Check if sync tracking table exists
        pg_cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'lms_sync_log'
            )
        """)
        
        table_exists = pg_cur.fetchone()[0]
        
        if not table_exists:
            # Create sync tracking table
            pg_cur.execute("""
                CREATE TABLE lms_sync_log (
                    sync_id SERIAL PRIMARY KEY,
                    sync_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    records_processed INTEGER DEFAULT 0,
                    records_updated INTEGER DEFAULT 0,
                    records_inserted INTEGER DEFAULT 0,
                    sync_type VARCHAR(50) DEFAULT 'incremental',
                    notes TEXT
                )
            """)
            print("   📋 Created LMS sync tracking table")
            return None
        
        # Get last sync timestamp
        pg_cur.execute("""
            SELECT MAX(sync_timestamp) 
            FROM lms_sync_log 
            WHERE sync_type = 'incremental'
        """)
        
        last_sync = pg_cur.fetchone()[0]
        return last_sync
        
    except Exception as e:
        print(f"   [WARN]  Error getting last sync timestamp: {str(e)}")
        return None

def sync_lms_reserves(lms_conn, pg_conn, last_sync):
    """Synchronize LMS Reserve table with PostgreSQL charters."""
    
    print("\n📋 SYNCING LMS RESERVES → POSTGRESQL CHARTERS")
    print("-" * 47)
    
    lms_cur = lms_conn.cursor()
    pg_cur = pg_conn.cursor()
    
    try:
        # Build LMS query based on last sync
        if last_sync:
            # Only get records modified since last sync
            lms_query = """
                SELECT Reserve_No, Account_No, PU_Date, Rate, Balance, Deposit, 
                       Pymt_Type, Vehicle, Name, LastUpdated
                FROM Reserve 
                WHERE LastUpdated > ?
                ORDER BY LastUpdated DESC
            """
            lms_cur.execute(lms_query, last_sync)
            print(f"   🔄 Checking for changes since {last_sync}")
        else:
            # Get all recent records (last 30 days)
            cutoff_date = datetime.now() - timedelta(days=30)
            lms_query = """
                SELECT Reserve_No, Account_No, PU_Date, Rate, Balance, Deposit, 
                       Pymt_Type, Vehicle, Name, LastUpdated
                FROM Reserve 
                WHERE PU_Date > ?
                ORDER BY PU_Date DESC
            """
            lms_cur.execute(lms_query, cutoff_date)
            print(f"   🔄 Getting records from last 30 days")
        
        lms_records = lms_cur.fetchall()
        
        if not lms_records:
            print("   [OK] No new or updated records found")
            return 0, 0
        
        print(f"   📊 Found {len(lms_records):,} records to process")
        
        inserted = 0
        updated = 0
        
        for record in lms_records:
            try:
                reserve_no, account_no, pu_date, rate, balance, deposit, pymt_type, vehicle, name, last_updated = record
                
                # Clean and format data
                reserve_no = str(reserve_no) if reserve_no else None
                account_no = str(account_no) if account_no else None
                rate = float(rate) if rate is not None else 0.0
                balance = float(balance) if balance is not None else 0.0
                deposit = float(deposit) if deposit is not None else 0.0
                
                if not reserve_no or not pu_date:
                    continue
                
                # Check if record exists in PostgreSQL
                pg_cur.execute("""
                    SELECT charter_id, rate, balance, updated_at
                    FROM charters 
                    WHERE reserve_number = %s
                """, (reserve_no,))
                
                existing = pg_cur.fetchone()
                
                if existing:
                    # Update existing record if data differs
                    charter_id, existing_rate, existing_balance, existing_updated = existing
                    
                    if (abs(float(existing_rate or 0) - rate) > 0.01 or 
                        abs(float(existing_balance or 0) - balance) > 0.01):
                        
                        pg_cur.execute("""
                            UPDATE charters 
                            SET rate = %s, balance = %s, deposit = %s, 
                                account_number = %s, updated_at = CURRENT_TIMESTAMP,
                                notes = COALESCE(notes, '') || %s
                            WHERE charter_id = %s
                        """, (
                            rate, balance, deposit, account_no,
                            f" [LMS Sync {datetime.now().strftime('%Y-%m-%d %H:%M')}]",
                            charter_id
                        ))
                        updated += 1
                        
                        if updated <= 5:  # Show first 5 updates
                            print(f"      🔄 Updated {reserve_no}: Rate ${existing_rate} → ${rate}")
                
                else:
                    # Insert new record
                    pg_cur.execute("""
                        INSERT INTO charters (
                            reserve_number, account_number, charter_date, rate, 
                            balance, deposit, notes, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """, (
                        reserve_no, account_no, pu_date, rate, balance, deposit,
                        f"LMS Import: {name or ''} - Vehicle: {vehicle or ''} - Payment: {pymt_type or ''}"
                    ))
                    inserted += 1
                    
                    if inserted <= 5:  # Show first 5 insertions
                        print(f"      [OK] Inserted {reserve_no}: {name or 'Unknown'} - ${rate}")
                
            except Exception as e:
                print(f"      [WARN]  Error processing record {reserve_no}: {str(e)}")
                continue
        
        print(f"   📊 Sync Results: {inserted:,} inserted, {updated:,} updated")
        return inserted, updated
        
    except Exception as e:
        print(f"   [FAIL] Error in reserve sync: {str(e)}")
        return 0, 0

def sync_lms_payments(lms_conn, pg_conn, last_sync):
    """Synchronize LMS Payment table with PostgreSQL payments."""
    
    print("\n💰 SYNCING LMS PAYMENTS → POSTGRESQL PAYMENTS")
    print("-" * 44)
    
    lms_cur = lms_conn.cursor()
    pg_cur = pg_conn.cursor()
    
    try:
        # Get LMS payment records
        if last_sync:
            lms_query = """
                SELECT PaymentID, Account_No, Reserve_No, Amount, [Key], 
                       LastUpdated, LastUpdatedBy
                FROM Payment 
                WHERE LastUpdated > ?
                ORDER BY LastUpdated DESC
            """
            lms_cur.execute(lms_query, last_sync)
        else:
            # Get payments from last 30 days
            cutoff_date = datetime.now() - timedelta(days=30)
            lms_query = """
                SELECT PaymentID, Account_No, Reserve_No, Amount, [Key], 
                       LastUpdated, LastUpdatedBy
                FROM Payment 
                WHERE LastUpdated > ?
                ORDER BY LastUpdated DESC
            """
            lms_cur.execute(lms_query, cutoff_date)
        
        payment_records = lms_cur.fetchall()
        
        if not payment_records:
            print("   [OK] No new payment records found")
            return 0, 0
        
        print(f"   📊 Found {len(payment_records):,} payment records to process")
        
        inserted = 0
        updated = 0
        
        for record in payment_records:
            try:
                payment_id, account_no, reserve_no, amount, key, last_updated, updated_by = record
                
                # Clean data
                account_no = str(account_no) if account_no else None
                reserve_no = str(reserve_no) if reserve_no else None
                amount = float(amount) if amount is not None else 0.0
                key = str(key) if key else None
                
                if amount == 0:
                    continue
                
                # Check if payment exists
                pg_cur.execute("""
                    SELECT payment_id FROM payments 
                    WHERE payment_key = %s OR 
                          (account_number = %s AND reserve_number = %s AND amount = %s)
                """, (key, account_no, reserve_no, amount))
                
                existing_payment = pg_cur.fetchone()
                
                if not existing_payment:
                    # Insert new payment
                    pg_cur.execute("""
                        INSERT INTO payments (
                            account_number, reserve_number, amount, payment_key,
                            payment_date, last_updated_by, created_at, 
                            notes
                        ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
                    """, (
                        account_no, reserve_no, amount, key, 
                        last_updated, updated_by,
                        f"LMS Sync Import - PaymentID: {payment_id}"
                    ))
                    inserted += 1
                    
                    if inserted <= 5:
                        print(f"      [OK] Inserted payment: ${amount} for {reserve_no or account_no}")
                
            except Exception as e:
                print(f"      [WARN]  Error processing payment {payment_id}: {str(e)}")
                continue
        
        print(f"   📊 Payment Sync Results: {inserted:,} inserted, {updated:,} updated")
        return inserted, updated
        
    except Exception as e:
        print(f"   [FAIL] Error in payment sync: {str(e)}")
        return 0, 0

def log_sync_completion(pg_cur, records_processed, records_updated, records_inserted):
    """Log the completion of sync operation."""
    try:
        pg_cur.execute("""
            INSERT INTO lms_sync_log (
                sync_timestamp, records_processed, records_updated, 
                records_inserted, sync_type, notes
            ) VALUES (
                CURRENT_TIMESTAMP, %s, %s, %s, 'incremental',
                'Automated LMS incremental sync'
            )
        """, (records_processed, records_updated, records_inserted))
        
        print(f"   📝 Sync operation logged")
        
    except Exception as e:
        print(f"   [WARN]  Error logging sync: {str(e)}")

def main():
    """Main incremental update process."""
    
    print("🔄 LMS INCREMENTAL UPDATE FROM BACKUP DATABASE")
    print("=" * 50)
    
    # Step 1: Find LMS database
    lms_path = find_lms_database()
    if not lms_path:
        print("\n[FAIL] LMS database not found. Please check backup folders.")
        return
    
    # Step 2: Connect to databases
    print(f"\n🔗 ESTABLISHING DATABASE CONNECTIONS")
    print("-" * 35)
    
    try:
        lms_conn = get_lms_connection(lms_path)
        print("   [OK] Connected to LMS database")
        
        pg_conn = get_pg_connection()
        pg_cur = pg_conn.cursor()
        print("   [OK] Connected to PostgreSQL database")
        
    except Exception as e:
        print(f"   [FAIL] Connection error: {str(e)}")
        return
    
    # Step 3: Get last sync timestamp
    print(f"\n📅 CHECKING LAST SYNC STATUS")
    print("-" * 28)
    
    last_sync = get_last_sync_timestamp(pg_cur)
    if last_sync:
        print(f"   📋 Last sync: {last_sync}")
    else:
        print("   📋 No previous sync found - will sync recent records")
    
    # Step 4: Perform incremental sync
    total_inserted = 0
    total_updated = 0
    total_processed = 0
    
    try:
        # Sync reserves (charters)
        reserve_inserted, reserve_updated = sync_lms_reserves(lms_conn, pg_conn, last_sync)
        total_inserted += reserve_inserted
        total_updated += reserve_updated
        total_processed += reserve_inserted + reserve_updated
        
        # Sync payments
        payment_inserted, payment_updated = sync_lms_payments(lms_conn, pg_conn, last_sync)
        total_inserted += payment_inserted
        total_updated += payment_updated
        total_processed += payment_inserted + payment_updated
        
        # Commit changes
        if total_processed > 0:
            pg_conn.commit()
            print(f"\n[OK] SYNC COMPLETED SUCCESSFULLY")
            print(f"   📊 Total Changes: {total_processed:,}")
            print(f"   [OK] Records Inserted: {total_inserted:,}")
            print(f"   🔄 Records Updated: {total_updated:,}")
            
            # Log sync completion
            log_sync_completion(pg_cur, total_processed, total_updated, total_inserted)
            pg_conn.commit()
        else:
            print(f"\n[OK] NO CHANGES DETECTED")
            print("   📊 Database is up to date")
        
    except Exception as e:
        print(f"\n[FAIL] SYNC ERROR: {str(e)}")
        pg_conn.rollback()
    
    # Step 5: Cleanup
    try:
        pg_cur.close()
        pg_conn.close()
        lms_conn.close()
        print(f"\n🔒 Database connections closed")
        
    except Exception as e:
        print(f"   [WARN]  Cleanup error: {str(e)}")

if __name__ == "__main__":
    # Set database environment variables
    os.environ['DB_HOST'] = 'localhost'
    os.environ['DB_NAME'] = 'almsdata'
    os.environ['DB_USER'] = 'postgres'
    os.environ['DB_PASSWORD'] = '***REDACTED***'
    
    main()