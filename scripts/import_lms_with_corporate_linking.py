"""
Import LMS customers and create corporate parent-child account structure.

Handles multi-user accounts like 01007 (Kevin Dushane from customer table, 
Brenda from CustAdmin table) by creating a parent account and linking users.
"""
import os
import sys
import pyodbc
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "***REMOVED***")

ACCESS_DB_PATH = r'L:\limo\database_backups\lms2026.mdb'

def import_and_link_customers(dry_run=True):
    """Import LMS customers and create corporate parent-child structure."""
    
    # Connect to Access
    print("="*80)
    print("IMPORTING LMS CUSTOMERS AND CREATING CORPORATE STRUCTURE")
    print("="*80)
    print(f"Database: {ACCESS_DB_PATH}\n")
    
    conn_str = r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=' + ACCESS_DB_PATH + ';'
    
    try:
        access_conn = pyodbc.connect(conn_str)
        print("✅ Connected to Access database\n")
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    access_cur = access_conn.cursor()
    pg_conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    pg_cur = pg_conn.cursor()
    
    try:
        # Step 1: Read LMS customer data
        print("1. Reading LMS customer data...")
        
        # From customer table
        access_cur.execute("SELECT Account_No, Bill_To, Attention FROM customer ORDER BY Account_No;")
        customer_rows = access_cur.fetchall()
        print(f"   ✅ Customer table: {len(customer_rows):,} records")
        
        # From CustAdmin table
        try:
            access_cur.execute("SELECT Account_No, Name FROM CustAdmin ORDER BY Account_No;")
            custadmin_rows = access_cur.fetchall()
            print(f"   ✅ CustAdmin table: {len(custadmin_rows):,} records\n")
        except:
            custadmin_rows = []
            print(f"   ⚠️  CustAdmin table: unable to read\n")
        
        # Step 2: Find multi-user accounts
        print("2. Identifying multi-user accounts...")
        
        # Group by account number
        account_data = {}
        for row in customer_rows:
            acct, bill_to, attention = row
            name = bill_to if bill_to and str(bill_to).strip() else attention
            if acct and name:
                if acct not in account_data:
                    account_data[acct] = {'customer': [], 'custadmin': []}
                account_data[acct]['customer'].append(name)
        
        for row in custadmin_rows:
            acct, name = row
            if acct and name:
                if acct not in account_data:
                    account_data[acct] = {'customer': [], 'custadmin': []}
                account_data[acct]['custadmin'].append(name)
        
        # Find multi-user accounts
        multi_user_accounts = {
            acct: data for acct, data in account_data.items()
            if len(data['customer']) + len(data['custadmin']) > 1
        }
        
        print(f"   ✅ Found {len(multi_user_accounts):,} multi-user accounts")
        print(f"   ℹ️  Sample accounts:")
        for i, (acct, data) in enumerate(list(multi_user_accounts.items())[:5]):
            users = data['customer'] + data['custadmin']
            print(f"      {acct}: {', '.join(users[:2])}{'...' if len(users) > 2 else ''} ({len(users)} users)")
        
        if dry_run:
            print(f"\n{'='*80}")
            print(f"DRY RUN - Would create:")
            print(f"  - {len(multi_user_accounts):,} parent accounts")
            print(f"  - Update child accounts with parent_client_id")
            print(f"Use --write to apply changes")
            print(f"{'='*80}\n")
            return
        
        # Step 3: Update clients with LMS data
        print(f"\n3. Updating clients table with LMS names...\n")
        
        updated_unknown = 0
        updated_blank = 0
        
        # For each account, find Unknown Clients
        for acct, data in account_data.items():
            all_names = data['customer'] + data['custadmin']
            if not all_names:
                continue
            
            # Find Unknown Clients with this account number
            pg_cur.execute("""
                SELECT client_id FROM clients
                WHERE account_number = %s
                AND (company_name = 'Unknown Client' OR company_name IS NULL OR company_name = '')
                LIMIT 1;
            """, (acct,))
            
            result = pg_cur.fetchone()
            if result:
                unknown_id = result[0]
                # Use first name as company (e.g., "Dushane Household" or just the account)
                primary_name = all_names[0] if all_names else acct
                
                pg_cur.execute("""
                    UPDATE clients SET company_name = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE client_id = %s;
                """, (primary_name, unknown_id))
                
                if pg_cur.rowcount > 0:
                    updated_unknown += 1
        
        pg_conn.commit()
        print(f"   ✅ Updated {updated_unknown:,} Unknown Client records\n")
        
        # Step 4: Create corporate structure
        print("4. Creating corporate parent-child structure...\n")
        
        parents_created = 0
        children_linked = 0
        
        for acct, data in multi_user_accounts.items():
            all_names = data['customer'] + data['custadmin']
            if len(all_names) < 2:
                continue
            
            # Find all clients with this account number
            pg_cur.execute("""
                SELECT client_id, company_name FROM clients
                WHERE account_number = %s
                ORDER BY client_id;
            """, (acct,))
            
            clients = pg_cur.fetchall()
            if not clients:
                continue
            
            # First client becomes parent
            parent_id = clients[0][0]
            parent_name = clients[0][1]
            
            pg_cur.execute("""
                UPDATE clients
                SET account_type = 'corporate_parent', parent_client_id = NULL
                WHERE client_id = %s;
            """, (parent_id,))
            
            if pg_cur.rowcount > 0:
                parents_created += 1
            
            # Remaining clients become children
            for i in range(1, len(clients)):
                child_id = clients[i][0]
                pg_cur.execute("""
                    UPDATE clients
                    SET account_type = 'corporate_child', parent_client_id = %s
                    WHERE client_id = %s;
                """, (parent_id, child_id))
                
                if pg_cur.rowcount > 0:
                    children_linked += 1
        
        pg_conn.commit()
        
        print(f"   ✅ Created {parents_created:,} parent accounts")
        print(f"   ✅ Linked {children_linked:,} child accounts to parents\n")
        
        print("="*80)
        print("✅ COMPLETED")
        print("="*80)
        print(f"  - Updated {updated_unknown:,} Unknown Clients with LMS names")
        print(f"  - Created {parents_created:,} corporate parent accounts")
        print(f"  - Linked {children_linked:,} child contacts to parents\n")
        
    finally:
        access_cur.close()
        access_conn.close()
        pg_cur.close()
        pg_conn.close()

def main():
    dry_run = '--write' not in sys.argv
    import_and_link_customers(dry_run)

if __name__ == "__main__":
    main()
