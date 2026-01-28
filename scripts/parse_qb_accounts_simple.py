"""
Simple QB Account Listing Parser - No Unicode
"""

import pandas as pd
import psycopg2
from pathlib import Path
import re

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        port=5432,
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )

# Parse old account listing
file_path = Path("L:/limo/quickbooks/old account listing.xlsx")

print("="*70)
print("Parsing: old account listing.xlsx")
print("="*70)

# Read Excel file
df = pd.read_excel(file_path, sheet_name=0)
print(f"Loaded {len(df)} rows")
print(f"Columns: {list(df.columns)}")

# Connect to database
conn = get_db_connection()
cur = conn.cursor()

# Track updates
matched = 0
updated = 0
skipped = 0

# Process each account row
for idx, row in df.iterrows():
    # Skip empty rows
    if pd.isna(row.get('Account', row.iloc[1] if len(row) > 1 else None)):
        continue
    
    # Extract account info from 'Account' column (format: "1000 · Account Name")
    account_str = str(row.get('Account', row.iloc[1])).strip()
    
    # Parse account number and name
    match = re.match(r'^(\d+)\s*[·•]\s*(.+)$', account_str)
    if not match:
        skipped += 1
        continue
    
    account_num = match.group(1)
    account_name = match.group(2).strip()
    
    # Extract additional QB data from columns
    account_type = row.get('Type', None)
    balance = row.get('Balance Total', None)
    description = row.get('Description', None)
    qb_account_num = row.get('Accnt. #', None)
    tax_line = row.get('Tax Line', None)
    
    # Try to find matching account in database
    cur.execute("""
        SELECT account_id, account_number, account_name, account_type 
        FROM chart_of_accounts 
        WHERE account_number = %s
        LIMIT 1
    """, (account_num,))
    
    result = cur.fetchone()
    if result:
        account_id, db_num, db_name, db_type = result
        matched += 1
        
        # Update account QB fields
        try:
            update_fields = []
            update_values = []
            
            if balance and pd.notna(balance) and balance != 0:
                update_fields.append("opening_balance = %s")
                update_values.append(float(balance))
            
            if description and pd.notna(description):
                update_fields.append("qb_description = %s")
                update_values.append(str(description))
            
            if account_type and pd.notna(account_type) and not db_type:
                update_fields.append("account_type = %s")
                update_values.append(str(account_type))
            
            if tax_line and pd.notna(tax_line) and str(tax_line) != '<Unassigned>':
                # Extract numeric tax line if possible
                tax_match = re.search(r'(\d+)', str(tax_line))
                if tax_match:
                    update_fields.append("qb_tax_line_id = %s")
                    update_values.append(int(tax_match.group(1)))
            
            if update_fields:
                update_values.append(account_id)
                sql = f"UPDATE chart_of_accounts SET {', '.join(update_fields)} WHERE account_id = %s"
                cur.execute(sql, update_values)
                updated += 1
                print(f"  [+] Updated: {db_num} - {db_name} (balance: {balance})")
        except Exception as e:
            print(f"  [!] Error updating {db_name}: {e}")
            skipped += 1
    else:
        skipped += 1
        print(f"  [?] No match for: {account_num} - {account_name}")

conn.commit()
cur.close()
conn.close()

print(f"\n{'='*70}")
print(f"[+] Account Listing Processing Complete")
print(f"{'='*70}")
print(f"  Matched: {matched}")
print(f"  Updated: {updated}")
print(f"  Skipped: {skipped}")
