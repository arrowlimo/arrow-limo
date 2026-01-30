"""
Import LMS customer data from Access database and create corporate parent-child structure.
This script imports BOTH Customer and CustAdmin records for each account.
"""

import os
import sys
import pyodbc
import psycopg2
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

LMS_PATH = r"L:\limo\database_backups\lms2026.mdb"

def import_lms_customers(dry_run=True):
    """Import LMS customer data and create corporate structure."""
    
    # Read from LMS Access database
    print("📖 Reading LMS Access database...")
    access_conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
    access_conn = pyodbc.connect(access_conn_str)
    access_cur = access_conn.cursor()
    
    # Read Customer table
    access_cur.execute("SELECT Account_No, Bill_To, Attention FROM Customer ORDER BY Account_No")
    customers = {}
    for row in access_cur.fetchall():
        acct, bill_to, attention = row[0], row[1], row[2]
        if acct not in customers:
            customers[acct] = []
        customers[acct].append({
            'type': 'Customer',
            'bill_to': bill_to,
            'attention': attention
        })
    
    # Read CustAdmin table
    access_cur.execute("SELECT Account_No, Name FROM CustAdmin ORDER BY Account_No")
    for row in access_cur.fetchall():
        acct, name = row[0], row[1]
        if acct not in customers:
            customers[acct] = []
        customers[acct].append({
            'type': 'CustAdmin',
            'name': name,
            'attention': None
        })
    
    access_cur.close()
    access_conn.close()
    
    print(f"✅ Read {len(customers)} unique accounts from LMS")
    print(f"   Total records: {sum(len(v) for v in customers.values())}")
    
    # Connect to almsdata
    pg_conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    pg_cur = pg_conn.cursor()
    
    # Summary counters
    inserted_parent = 0
    inserted_child = 0
    updated_parent_flag = 0
    linked_children = 0
    already_existed = 0
    
    # For each account with multiple users
    multi_user_accounts = {k: v for k, v in customers.items() if len(v) > 1}
    
    print(f"\n📊 Multi-user accounts: {len(multi_user_accounts)}")
    
    # Process each account
    for account_no in sorted(multi_user_accounts.keys())[:5]:  # Show first 5 examples
        records = multi_user_accounts[account_no]
        print(f"\n📌 Account {account_no}: {len(records)} users")
        
        # Show all users
        for i, rec in enumerate(records):
            name = rec.get('bill_to') or rec.get('name') or '(Unknown)'
            attention = rec.get('attention') or ''
            source = rec['type']
            print(f"   [{i+1}] {name:30} ({attention:20}) from {source}")
    
    if not dry_run:
        print("\n✍️  Applying changes to database...")
        
        for account_no in sorted(customers.keys()):
            records = customers[account_no]
            
            if len(records) == 1:
                # Single user - mark as individual or skip if already exists
                continue
            
            # Multiple users - need corporate structure
            # First: Check if account already exists in clients
            pg_cur.execute(
                "SELECT client_id, account_type FROM clients WHERE account_number = %s",
                (account_no,)
            )
            existing = pg_cur.fetchone()
            
            if existing:
                client_id, current_type = existing
                
                if current_type == 'individual':
                    # Update first/main record to be corporate_parent
                    pg_cur.execute(
                        "UPDATE clients SET account_type = %s, parent_client_id = NULL WHERE client_id = %s",
                        ('corporate_parent', client_id)
                    )
                    updated_parent_flag += 1
            
            # For additional users, create child client records
            for i, rec in enumerate(records):
                if i == 0:
                    continue  # Skip first - already updated above
                
                name = rec.get('bill_to') or rec.get('name') or f"{account_no} User {i}"
                
                # Check if this user already exists
                pg_cur.execute(
                    "SELECT client_id FROM clients WHERE account_number = %s AND client_name = %s",
                    (account_no, name)
                )
                
                if pg_cur.fetchone():
                    already_existed += 1
                    continue
                
                # Create new child client
                try:
                    pg_cur.execute("""
                        INSERT INTO clients (
                            account_number, company_name, client_name, 
                            account_type, parent_client_id, created_at, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        RETURNING client_id
                    """, (
                        account_no,
                        name,  # company_name = name
                        name,  # client_name = name
                        'corporate_child',
                        existing[0] if existing else None
                    ))
                    
                    child_id = pg_cur.fetchone()[0]
                    inserted_child += 1
                    
                    # Link to parent
                    if existing:
                        linked_children += 1
                
                except psycopg2.IntegrityError as e:
                    pg_conn.rollback()
                    print(f"⚠️  Error creating child for {account_no}: {e}")
        
        pg_conn.commit()
        print(f"\n✅ Import complete:")
        print(f"   Parent accounts flagged: {updated_parent_flag}")
        print(f"   Child accounts created: {inserted_child}")
        print(f"   Children linked to parents: {linked_children}")
    
    else:
        print(f"\n🔍 DRY RUN - Would create:")
        print(f"   ~{len(multi_user_accounts)} parent account flags")
        print(f"   ~{sum(len(v)-1 for v in multi_user_accounts.values())} child account records")
    
    pg_cur.close()
    pg_conn.close()

if __name__ == "__main__":
    dry_run = "--write" not in sys.argv
    
    if dry_run:
        print("🔍 DRY RUN MODE (use --write to apply)")
    else:
        print("✍️  WRITE MODE - Changes will be committed")
    
    import_lms_customers(dry_run=dry_run)
