"""
Create corporate parent-child account structure in clients table.

For accounts with multiple users (like 01007 with Kevin Dushane + Brenda),
add parent_client_id field to link child contacts to parent account.

This enables:
- One parent account (e.g., "Dushane Household" or "01007 Corporate")
- Multiple child users linked to parent (Kevin, Brenda, etc.)
- All charters/payments aggregated to parent for billing
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "***REMOVED***")

def add_corporate_structure():
    """Add parent-child corporate account structure to clients table."""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    try:
        print("="*80)
        print("CREATING CORPORATE PARENT-CHILD ACCOUNT STRUCTURE")
        print("="*80)
        
        # Check if parent_client_id already exists
        print("\n1. Checking for parent_client_id column...")
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'clients' 
            AND column_name = 'parent_client_id';
        """)
        
        if cur.fetchone():
            print("   ✅ parent_client_id column already exists\n")
        else:
            print("   ⚠️  parent_client_id column does not exist")
            print("   Creating column...\n")
            cur.execute("""
                ALTER TABLE clients
                ADD COLUMN parent_client_id INTEGER
                REFERENCES clients(client_id) ON DELETE SET NULL;
            """)
            cur.execute("""
                CREATE INDEX idx_clients_parent_id ON clients(parent_client_id);
            """)
            conn.commit()
            print("   ✅ Created parent_client_id column with index\n")
        
        # Add account_type if not exists (for marking parent vs child)
        print("2. Checking for account_type column...")
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'clients' 
            AND column_name = 'account_type';
        """)
        
        if cur.fetchone():
            print("   ✅ account_type column already exists\n")
        else:
            print("   ⚠️  account_type column does not exist")
            print("   Creating column...\n")
            cur.execute("""
                ALTER TABLE clients
                ADD COLUMN account_type VARCHAR(20) DEFAULT 'individual';
            """)
            conn.commit()
            print("   ✅ Created account_type column (values: 'individual', 'corporate_parent', 'corporate_child')\n")
        
        # Show example multi-user accounts
        print("="*80)
        print("EXAMPLE: MULTI-USER ACCOUNT STRUCTURE")
        print("="*80)
        print("""
For Account 01007 (Kevin Dushane + Brenda):

BEFORE:
  ├─ Client ID 1234: "Unknown Client", account_number 01007
  └─ Client ID 1235: "Unknown Client", account_number 01007

AFTER:
  ├─ Client ID 1234: "Dushane Household", account_number 01007
  │   ├─ account_type: 'corporate_parent'
  │   ├─ parent_client_id: NULL
  │   └─ All charters link here
  │
  └─ Client ID 1235: "Kevin Dushane"/"Brenda", account_number 01007
      ├─ account_type: 'corporate_child'
      └─ parent_client_id: 1234 (points to Dushane Household)

BENEFITS:
✅ Single billing account (parent)
✅ Multiple authorized users (children)
✅ All transactions rolled up to parent
✅ Individual contact records maintained
        """)
        
        print("\n" + "="*80)
        print("NEXT STEPS")
        print("="*80)
        print("""
To implement corporate accounts:

1. Identify multi-user accounts:
   - GROUP BY account_number HAVING COUNT(*) > 1
   - These have multiple LMS customer records (from CustAdmin)

2. For each multi-user account:
   - Create ONE parent client with company_name = "{account_number} Corporate"
   - Set account_type = 'corporate_parent'
   - Update individual user records:
     - Set account_type = 'corporate_child'
     - Set parent_client_id = parent's client_id
     - Merge company_name from LMS (Kevin Dushane, Brenda, etc.)

3. Link charters:
   - Create trigger or migration to ensure all charters 
     link to parent_client_id if child account
        """)
        
        print("\n✅ Corporate structure foundation created!\n")
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    add_corporate_structure()
