#!/usr/bin/env python3
"""
LMS Database Incremental Update
===============================

Updates the PostgreSQL database with only the changed records from the latest LMS backup.
Compares current database state with L:\limo\backups\lms.mdb to identify:
- New records added since last update
- Modified records with different values
- Deleted records (marked as inactive)

Usage:
    python scripts/update_from_latest_lms.py --dry-run    # Preview changes
    python scripts/update_from_latest_lms.py --apply      # Apply changes
"""

import pyodbc
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
from dotenv import load_dotenv
import argparse

load_dotenv()

# Database connections
LMS_PATH = r'L:\limo\backups\lms.mdb'
PG_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'database': os.getenv('DB_NAME', 'almsdata'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '')
}

class LMSIncrementalUpdater:
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.changes_found = {
            'new_records': {},
            'modified_records': {},
            'deleted_records': {},
            'flagged_records': {},
            'summary': {}
        }
        
    def connect_lms(self):
        """Connect to LMS Access database"""
        conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
        return pyodbc.connect(conn_str)
        
    def connect_postgres(self):
        """Connect to PostgreSQL database"""
        return psycopg2.connect(**PG_CONFIG)
        
    def get_last_update_timestamp(self):
        """Get the timestamp of the last LMS update"""
        try:
            with self.connect_postgres() as pg_conn:
                with pg_conn.cursor() as cur:
                    cur.execute("""
                        SELECT MAX(last_updated) as last_update
                        FROM lms_update_log 
                        WHERE update_status = 'completed'
                    """)
                    result = cur.fetchone()
                    return result[0] if result and result[0] else datetime(2020, 1, 1)
        except:
            # If no update log exists, assume we need full sync
            return datetime(2020, 1, 1)
    
    def check_reserve_changes(self):
        """Check for changes in Reserve table"""
        print("🔍 Checking Reserve table changes...")
        
        last_update = self.get_last_update_timestamp()
        
        with self.connect_lms() as lms_conn:
            lms_cur = lms_conn.cursor()
            
            # Get all reserves from LMS
            lms_cur.execute("""
                SELECT Reserve_No, Account_No, PU_Date, Rate, Balance, Deposit, 
                       Pymt_Type, Vehicle, Name, LastUpdated
                FROM Reserve
                ORDER BY Reserve_No
            """)
            
            lms_reserves = {}
            for row in lms_cur.fetchall():
                reserve_no = row[0]
                lms_reserves[reserve_no] = {
                    'reserve_number': row[0],
                    'account_number': row[1],
                    'pickup_date': row[2],
                    'rate': float(row[3]) if row[3] else 0.0,
                    'balance': float(row[4]) if row[4] else 0.0,
                    'deposit': float(row[5]) if row[5] else 0.0,
                    'payment_type': row[6],
                    'vehicle': row[7],
                    'client_name': row[8],
                    'last_updated': row[9]
                }
        
        # Get existing reserves from PostgreSQL with client information
        with self.connect_postgres() as pg_conn:
            with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT c.reserve_number, c.account_number, c.charter_date, c.rate, 
                           c.balance, c.deposit, c.vehicle, c.client_id, cl.company_name, c.updated_at
                    FROM charters c
                    LEFT JOIN clients cl ON c.client_id = cl.client_id
                    WHERE c.reserve_number IS NOT NULL
                """)
                
                pg_reserves = {row['reserve_number']: dict(row) for row in cur.fetchall()}
        
        # Compare and find changes
        new_reserves = []
        modified_reserves = []
        
        for reserve_no, lms_data in lms_reserves.items():
            if reserve_no not in pg_reserves:
                # New record
                new_reserves.append(lms_data)
            else:
                # Check if modified
                pg_data = pg_reserves[reserve_no]
                if self.is_record_modified(lms_data, pg_data, ['rate', 'balance', 'deposit']):
                    modified_reserves.append({
                        'reserve_number': reserve_no,
                        'lms_data': lms_data,
                        'pg_data': pg_data
                    })
        
        # Check for deleted records (in PG but not in LMS) - FLAG ONLY, DON'T DELETE
        flagged_reserves = []
        for reserve_no in pg_reserves:
            if reserve_no not in lms_reserves:
                flagged_reserves.append({
                    'reserve_number': reserve_no,
                    'data': pg_reserves[reserve_no],
                    'reason': 'not_in_lms_backup'
                })
        
        self.changes_found['new_records']['reserves'] = new_reserves
        self.changes_found['modified_records']['reserves'] = modified_reserves
        self.changes_found['flagged_records']['reserves'] = flagged_reserves
        
        print(f"   📊 Found: {len(new_reserves)} new, {len(modified_reserves)} modified, {len(flagged_reserves)} flagged for review")
    
    def check_payment_changes(self):
        """Check for changes in Payment table"""
        print("🔍 Checking Payment table changes...")
        
        with self.connect_lms() as lms_conn:
            lms_cur = lms_conn.cursor()
            
            # Get all payments from LMS
            lms_cur.execute("""
                SELECT PaymentID, Account_No, Reserve_No, Amount, [Key], 
                       LastUpdated, LastUpdatedBy
                FROM Payment
                ORDER BY PaymentID
            """)
            
            lms_payments = {}
            for row in lms_cur.fetchall():
                payment_id = row[0]
                lms_payments[payment_id] = {
                    'lms_payment_id': row[0],
                    'account_number': row[1],
                    'reserve_number': row[2],
                    'amount': float(row[3]) if row[3] else 0.0,
                    'payment_key': row[4],
                    'payment_date': row[5],
                    'last_updated_by': row[6]
                }
        
        # Get existing payments from PostgreSQL
        with self.connect_postgres() as pg_conn:
            with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT payment_key, account_number, reserve_number, amount, 
                           payment_date, last_updated_by
                    FROM payments 
                    WHERE payment_key IS NOT NULL
                """)
                
                # Index by payment_key instead of payment_id for matching
                pg_payments = {}
                for row in cur.fetchall():
                    if row['payment_key']:
                        pg_payments[row['payment_key']] = dict(row)
        
        # Compare payments by payment_key
        new_payments = []
        modified_payments = []
        
        for lms_id, lms_data in lms_payments.items():
            payment_key = lms_data['payment_key']
            if payment_key and payment_key not in pg_payments:
                # New payment record
                new_payments.append(lms_data)
            elif payment_key and payment_key in pg_payments:
                # Check if modified
                pg_data = pg_payments[payment_key]
                lms_amount = float(lms_data['amount'])
                pg_amount = float(pg_data['amount'])
                if abs(lms_amount - pg_amount) > 0.01:  # Amount changed
                    modified_payments.append({
                        'payment_key': payment_key,
                        'lms_data': lms_data,
                        'pg_data': pg_data
                    })
        
        self.changes_found['new_records']['payments'] = new_payments
        self.changes_found['modified_records']['payments'] = modified_payments
        
        print(f"   📊 Found: {len(new_payments)} new, {len(modified_payments)} modified payments")
    
    def check_deposit_changes(self):
        """Check for changes in Deposit table"""
        print("🔍 Checking Deposit table changes...")
        
        with self.connect_lms() as lms_conn:
            lms_cur = lms_conn.cursor()
            
            # Get all deposits from LMS
            lms_cur.execute("""
                SELECT [Key], [Number], [Total], [Date], [Type], [Transact]
                FROM Deposit
                ORDER BY [Key]
            """)
            
            lms_deposits = {}
            for row in lms_cur.fetchall():
                deposit_key = row[0]
                lms_deposits[deposit_key] = {
                    'deposit_key': row[0],
                    'deposit_number': row[1],
                    'total_amount': float(row[2]) if row[2] else 0.0,
                    'deposit_date': row[3],
                    'deposit_type': row[4],
                    'transaction_type': row[5]
                }
        
        # Check if we have a deposits table in PostgreSQL
        with self.connect_postgres() as pg_conn:
            with pg_conn.cursor() as cur:
                try:
                    cur.execute("""
                        SELECT COUNT(*) FROM information_schema.tables 
                        WHERE table_name = 'deposits'
                    """)
                    table_exists = cur.fetchone()[0] > 0
                    
                    if table_exists:
                        cur.execute("""
                            SELECT deposit_key, deposit_number, total_amount, 
                                   deposit_date, deposit_type
                            FROM deposits
                        """)
                        pg_deposits = {row[0]: row for row in cur.fetchall()}
                    else:
                        pg_deposits = {}
                        
                except:
                    pg_deposits = {}
        
        # All LMS deposits are new if no deposits table exists
        new_deposits = list(lms_deposits.values()) if not pg_deposits else []
        
        # If deposits table exists, find actual new deposits
        if pg_deposits:
            new_deposits = [data for key, data in lms_deposits.items() if key not in pg_deposits]
        
        self.changes_found['new_records']['deposits'] = new_deposits
        
        print(f"   📊 Found: {len(new_deposits)} new deposits")
    
    def is_record_modified(self, lms_data, pg_data, compare_fields):
        """Compare specific fields between LMS and PostgreSQL records"""
        for field in compare_fields:
            lms_value = lms_data.get(field)
            pg_value = pg_data.get(field)
            
            # Handle numeric comparisons with tolerance
            if isinstance(lms_value, (int, float)) and isinstance(pg_value, (int, float)):
                if abs(lms_value - pg_value) > 0.01:
                    return True
            elif lms_value != pg_value:
                return True
        
        return False
    
    def get_or_create_client(self, pg_conn, account_number, company_name):
        """Get existing client_id or create new client"""
        with pg_conn.cursor() as cur:
            # First try to find existing client by account_number or company_name
            cur.execute("""
                SELECT client_id FROM clients 
                WHERE account_number = %s OR company_name = %s
                LIMIT 1
            """, (account_number, company_name))
            
            result = cur.fetchone()
            if result:
                return result[0]
            
            # Create new client
            cur.execute("""
                INSERT INTO clients (account_number, company_name, client_name, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING client_id
            """, (account_number, company_name, company_name, datetime.now(), datetime.now()))
            
            return cur.fetchone()[0]

    def apply_changes(self):
        """Apply the identified changes to PostgreSQL database"""
        if self.dry_run:
            print("🔍 DRY RUN MODE - No changes will be applied")
            return
        
        print("📝 Applying changes to PostgreSQL database...")
        
        with self.connect_postgres() as pg_conn:
            with pg_conn.cursor() as cur:
                
                # Apply new reserves
                new_reserves = self.changes_found['new_records'].get('reserves', [])
                for reserve in new_reserves:
                    # Get or create client
                    client_id = self.get_or_create_client(
                        pg_conn, 
                        reserve['account_number'], 
                        reserve['client_name']
                    )
                    
                    cur.execute("""
                        INSERT INTO charters (reserve_number, account_number, charter_date, 
                                            rate, balance, deposit, vehicle, client_id, 
                                            created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        reserve['reserve_number'], reserve['account_number'], 
                        reserve['pickup_date'], reserve['rate'], reserve['balance'],
                        reserve['deposit'], reserve['vehicle'], client_id,
                        datetime.now(), datetime.now()
                    ))
                
                # Apply modified reserves
                modified_reserves = self.changes_found['modified_records'].get('reserves', [])
                for mod in modified_reserves:
                    lms_data = mod['lms_data']
                    cur.execute("""
                        UPDATE charters 
                        SET rate = %s, balance = %s, deposit = %s, updated_at = %s
                        WHERE reserve_number = %s
                    """, (
                        lms_data['rate'], lms_data['balance'], lms_data['deposit'],
                        datetime.now(), mod['reserve_number']
                    ))
                
                # Apply new payments
                new_payments = self.changes_found['new_records'].get('payments', [])
                for payment in new_payments:
                    cur.execute("""
                        INSERT INTO payments (account_number, reserve_number, amount, 
                                            payment_key, payment_date, last_updated_by,
                                            created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        payment['account_number'], payment['reserve_number'],
                        payment['amount'], payment['payment_key'], payment['payment_date'],
                        payment['last_updated_by'], datetime.now(), datetime.now()
                    ))
                
                # Create deposits table if it doesn't exist and insert deposits
                new_deposits = self.changes_found['new_records'].get('deposits', [])
                if new_deposits:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS deposits (
                            deposit_id SERIAL PRIMARY KEY,
                            deposit_key VARCHAR(50),
                            deposit_number INTEGER,
                            total_amount DECIMAL(12,2),
                            deposit_date DATE,
                            deposit_type VARCHAR(50),
                            transaction_type VARCHAR(10),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    for deposit in new_deposits:
                        cur.execute("""
                            INSERT INTO deposits (deposit_key, deposit_number, total_amount,
                                                deposit_date, deposit_type, transaction_type)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (
                            deposit['deposit_key'], deposit['deposit_number'],
                            deposit['total_amount'], deposit['deposit_date'],
                            deposit['deposit_type'], deposit['transaction_type']
                        ))
                
                # Log this update
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS lms_update_log (
                        update_id SERIAL PRIMARY KEY,
                        update_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        lms_source_path VARCHAR(500),
                        records_added INTEGER,
                        records_modified INTEGER,
                        update_status VARCHAR(20)
                    )
                """)
                
                total_added = (len(new_reserves) + len(new_payments) + len(new_deposits))
                total_modified = len(modified_reserves)
                
                cur.execute("""
                    INSERT INTO lms_update_log (lms_source_path, records_added, 
                                              records_modified, update_status)
                    VALUES (%s, %s, %s, %s)
                """, (LMS_PATH, total_added, total_modified, 'completed'))
                
                pg_conn.commit()
        
        print("[OK] Changes applied successfully!")
    
    def print_summary(self):
        """Print summary of changes found"""
        print("\n📊 CHANGE SUMMARY")
        print("=" * 50)
        
        for table, records in self.changes_found['new_records'].items():
            if records:
                print(f"📈 New {table}: {len(records)}")
                if table == 'reserves':
                    for r in records[:3]:  # Show first 3
                        print(f"   • Reserve {r['reserve_number']}: {r['client_name']} - ${r['rate']}")
                    if len(records) > 3:
                        print(f"   ... and {len(records) - 3} more")
        
        for table, records in self.changes_found['modified_records'].items():
            if records:
                print(f"📝 Modified {table}: {len(records)}")
                if table == 'reserves':
                    for r in records[:3]:
                        lms_data = r['lms_data']
                        print(f"   • Reserve {r['reserve_number']}: Rate ${lms_data['rate']}, Balance ${lms_data['balance']}")
                    if len(records) > 3:
                        print(f"   ... and {len(records) - 3} more")
        
        for table, records in self.changes_found['deleted_records'].items():
            if records:
                print(f"🗑️  Deleted {table}: {len(records)}")
        
        # Show flagged records
        flagged_records = self.changes_found.get('flagged_records', {})
        for table, records in flagged_records.items():
            if records:
                print(f"🚩 Flagged {table} (not in LMS): {len(records)}")
                for r in records[:5]:  # Show first 5
                    data = r['data']
                    print(f"   • Reserve {r['reserve_number']}: {data.get('company_name', 'Unknown')} - Account {data.get('account_number')}")
                if len(records) > 5:
                    print(f"   ... and {len(records) - 5} more")

def main():
    parser = argparse.ArgumentParser(description='Update database from latest LMS backup')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    parser.add_argument('--apply', action='store_true', help='Apply changes to database')
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.apply:
        print("Please specify either --dry-run or --apply")
        return
    
    print("🚗 LMS DATABASE INCREMENTAL UPDATER")
    print("=" * 50)
    print(f"📂 LMS Source: {LMS_PATH}")
    print(f"🗄️  Target: PostgreSQL {PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['database']}")
    print(f"🔍 Mode: {'DRY RUN' if args.dry_run else 'APPLY CHANGES'}")
    print()
    
    # Check if LMS file exists
    if not os.path.exists(LMS_PATH):
        print(f"[FAIL] LMS file not found: {LMS_PATH}")
        return
    
    updater = LMSIncrementalUpdater(dry_run=args.dry_run)
    
    try:
        # Check for changes
        updater.check_reserve_changes()
        updater.check_payment_changes()
        updater.check_deposit_changes()
        
        # Print summary
        updater.print_summary()
        
        # Apply changes if not dry run
        if not args.dry_run:
            updater.apply_changes()
        
        print("\n[OK] Update completed successfully!")
        
    except Exception as e:
        print(f"[FAIL] Update failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()