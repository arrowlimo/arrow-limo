#!/usr/bin/env python3
"""
Create parent-child client structure in ALMS from LMS data.

First run: Link all multi-contact accounts properly:
- PARENT = Corporation (from Customer table Name field)
- CHILDREN = CustAdmin contacts linked via parent_client_id
- Update charters to link to correct client (parent or child)
"""

import os
import sys
import pyodbc
import psycopg2
from datetime import datetime
from typing import Dict, List, Tuple

LMS_PATH = r"L:\limo\database_backups\lms2026.mdb"
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

class ParentChildLinker:
    def __init__(self):
        self.lms_accounts = {}
        self.alms_conn = None
        self.lms_conn = None
        
    def connect_lms(self):
        """Connect to LMS Access database."""
        access_conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
        self.lms_conn = pyodbc.connect(access_conn_str)
        
    def connect_alms(self):
        """Connect to ALMS PostgreSQL database."""
        self.alms_conn = psycopg2.connect(
            host='localhost',
            dbname='almsdata',
            user='postgres',
            password=DB_PASSWORD
        )
    
    def get_multi_contact_accounts(self) -> List[str]:
        """Get all accounts with multiple CustAdmin contacts."""
        cur = self.lms_conn.cursor()
        cur.execute("""
            SELECT Account_No FROM CustAdmin
            GROUP BY Account_No HAVING COUNT(*) > 1
            ORDER BY Account_No
        """)
        accounts = [row[0] for row in cur.fetchall()]
        return accounts
    
    def get_account_data(self, account_no: str) -> Dict:
        """Get complete account data from LMS."""
        cur = self.lms_conn.cursor()
        
        data = {
            'account_no': account_no,
            'customer': None,
            'custadmins': [],
            'charter_count': 0
        }
        
        # Get Customer (parent company info)
        cur.execute(f"SELECT Name, Line_1, City, State, Zip_Code FROM Customer WHERE Account_No = '{account_no}'")
        cust_row = cur.fetchone()
        if cust_row:
            data['customer'] = {
                'name': cust_row[0],
                'address_line1': cust_row[1],
                'city': cust_row[2],
                'state': cust_row[3],
                'zip_code': cust_row[4]
            }
        
        # Get all CustAdmin contacts
        cur.execute(f"SELECT Name, Work_Phone, EMail FROM CustAdmin WHERE Account_No = '{account_no}' ORDER BY Name")
        for row in cur.fetchall():
            data['custadmins'].append({
                'name': row[0],
                'phone': row[1],
                'email': row[2]
            })
        
        # Count charters
        cur.execute(f"SELECT COUNT(Reserve_No) FROM Reserve WHERE Account_No = '{account_no}'")
        data['charter_count'] = cur.fetchone()[0]
        
        return data
    
    def create_parent_client(self, account_data: Dict) -> int:
        """Create parent client in ALMS (corporation)."""
        cur = self.alms_conn.cursor()
        
        cust = account_data['customer']
        company_name = cust['name'] if cust else f"Account {account_data['account_no']}"
        
        # Check if already exists
        cur.execute("""
            SELECT client_id FROM clients 
            WHERE company_name ILIKE %s AND is_company = true AND parent_client_id IS NULL
            LIMIT 1
        """, (company_name,))
        
        existing = cur.fetchone()
        if existing:
            return existing[0]
        
        # Create new parent client
        cur.execute("""
            INSERT INTO clients 
            (account_number, company_name, is_company, address_line1, city, state, zip_code, created_at)
            VALUES (%s, %s, true, %s, %s, %s, %s, NOW())
            RETURNING client_id
        """, (
            account_data['account_no'],
            company_name,
            cust['address_line1'] if cust else None,
            cust['city'] if cust else None,
            cust['state'] if cust else None,
            cust['zip_code'] if cust else None
        ))
        
        parent_id = cur.fetchone()[0]
        self.alms_conn.commit()
        return parent_id
    
    def create_child_client(self, parent_id: int, contact: Dict, account_no: str) -> int:
        """Create child client in ALMS (contact)."""
        cur = self.alms_conn.cursor()
        
        contact_name = contact['name']
        
        # Check if already exists
        cur.execute("""
            SELECT client_id FROM clients 
            WHERE client_name ILIKE %s AND is_company = false AND parent_client_id = %s
            LIMIT 1
        """, (contact_name, parent_id))
        
        existing = cur.fetchone()
        if existing:
            return existing[0]
        
        # Create new child client (inherits account_number from parent account)
        cur.execute("""
            INSERT INTO clients 
            (account_number, client_name, is_company, parent_client_id, primary_phone, email, created_at)
            VALUES (%s, %s, false, %s, %s, %s, NOW())
            RETURNING client_id
        """, (
            account_no,
            contact_name,
            parent_id,
            contact['phone'],
            contact['email']
        ))
        
        child_id = cur.fetchone()[0]
        self.alms_conn.commit()
        return child_id
    
    def process_account(self, account_no: str, dry_run: bool = True) -> Dict:
        """Process single account: create parent, children, and verify."""
        print(f"\n{'='*100}")
        print(f"PROCESSING ACCOUNT: {account_no}")
        print(f"{'='*100}")
        
        # Get LMS data
        account_data = self.get_account_data(account_no)
        
        print(f"\nLMS Data:")
        print(f"  Company: {account_data['customer']['name'] if account_data['customer'] else '(None)'}")
        print(f"  Contacts: {len(account_data['custadmins'])}")
        print(f"  Charters: {account_data['charter_count']}")
        
        for i, contact in enumerate(account_data['custadmins'], 1):
            print(f"    [{i}] {contact['name']:<40} | {contact['email']}")
        
        if dry_run:
            print("\n[DRY-RUN] Would create:")
            print(f"  - 1 parent client: {account_data['customer']['name']}")
            print(f"  - {len(account_data['custadmins'])} child clients")
            print(f"  - {account_data['charter_count']} charter links")
            return {'status': 'preview', 'account': account_no}
        else:
            print("\n[WRITE] Creating...")
            
            # Create parent
            parent_id = self.create_parent_client(account_data)
            print(f"  ✓ Created parent client: ID {parent_id}")
            
            # Create children
            child_ids = []
            for contact in account_data['custadmins']:
                child_id = self.create_child_client(parent_id, contact, account_no)
                child_ids.append(child_id)
                print(f"  ✓ Created child client: ID {child_id} ({contact['name']})")
            
            return {
                'status': 'created',
                'account': account_no,
                'parent_id': parent_id,
                'child_ids': child_ids
            }
    
    def main(self, dry_run: bool = True):
        """Main process."""
        print("=" * 100)
        print("CREATE PARENT-CHILD CLIENT STRUCTURE FROM LMS")
        print("=" * 100)
        print(f"\nMode: {'DRY-RUN (preview)' if dry_run else 'WRITE (apply changes)'}")
        
        # Connect
        print("\nConnecting to databases...")
        self.connect_lms()
        self.connect_alms()
        print("  ✓ Connected to LMS and ALMS")
        
        # Get multi-contact accounts
        print("\nIdentifying multi-contact accounts...")
        accounts = self.get_multi_contact_accounts()
        print(f"  Found {len(accounts)} accounts with multiple contacts")
        print(f"  Accounts: {', '.join(accounts)}")
        
        # Process each account
        results = []
        for account in accounts:
            result = self.process_account(account, dry_run=dry_run)
            results.append(result)
        
        # Summary
        print(f"\n{'='*100}")
        print("SUMMARY")
        print(f"{'='*100}")
        print(f"Total accounts processed: {len(results)}")
        
        if dry_run:
            print("\nTo apply these changes, run:")
            print("  python create_parent_child_structure.py --write")
        else:
            created = sum(1 for r in results if r['status'] == 'created')
            print(f"Parent clients created: {created}")
            print("\nNext steps:")
            print("  1. Verify parent-child links: SELECT * FROM clients WHERE parent_client_id IS NOT NULL")
            print("  2. Link charters to correct client: python link_charters_to_correct_client.py --write")
        
        # Cleanup
        self.lms_conn.close()
        self.alms_conn.close()

if __name__ == '__main__':
    dry_run = '--write' not in sys.argv
    linker = ParentChildLinker()
    linker.main(dry_run=dry_run)
