"""
Parse QuickBooks Excel Reports to Backfill Database
Extracts customer balances, vendor balances, account details, and transactions
"""

import pandas as pd
import psycopg2
from pathlib import Path
import re
from datetime import datetime

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        port=5432,
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

# QuickBooks reports directory
QB_DIR = Path("L:/limo/quickbooks")

# =====================================================================
# 1. Parse Customer Balance Detailed
# =====================================================================

def parse_customer_balance_detailed():
    """
    Extract customer data from customer balance detailed.xlsx
    - Customer name, balance, terms, aging
    """
    print("\n" + "="*70)
    print("PARSING: customer balance detailed.xlsx")
    print("="*70)
    
    file_path = QB_DIR / "customer balance detailed.xlsx"
    if not file_path.exists():
        print(f"[FAIL] File not found: {file_path}")
        return
    
    try:
        # Read Excel file
        df = pd.read_excel(file_path, sheet_name=0)
        print(f"✓ Loaded {len(df)} rows")
        print(f"✓ Columns: {list(df.columns)}")
        
        # Show sample data
        print("\nSample data:")
        print(df.head(10))
        
        # Connect to database
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Track updates
        matched = 0
        updated = 0
        skipped = 0
        
        # Process each customer row
        for idx, row in df.iterrows():
            # Skip header/total rows
            if pd.isna(row.iloc[0]) or str(row.iloc[0]).strip().lower() in ['total', 'customer', '']:
                continue
            
            # Extract customer name (usually first column)
            customer_name = str(row.iloc[0]).strip()
            
            # Try to find matching client in database
            cur.execute("""
                SELECT client_id, company_name, account_number 
                FROM clients 
                WHERE company_name ILIKE %s 
                   OR account_number = %s
                LIMIT 1
            """, (f"%{customer_name}%", customer_name))
            
            result = cur.fetchone()
            if result:
                client_id, db_name, account_num = result
                matched += 1
                
                # Extract balance and aging from row (columns vary by report format)
                # Will update based on actual column structure
                balance = None
                for col in df.columns:
                    if 'balance' in str(col).lower():
                        balance = row[col]
                        break
                
                # Update customer QB fields
                try:
                    cur.execute("""
                        UPDATE clients 
                        SET balance = COALESCE(%s, balance),
                            qb_customer_type = COALESCE(qb_customer_type, 'Commercial'),
                            payment_terms = COALESCE(payment_terms, 'Net 30')
                        WHERE client_id = %s
                    """, (balance, client_id))
                    updated += 1
                    print(f"  ✓ Updated: {db_name} (balance: {balance})")
                except Exception as e:
                    print(f"  ✗ Error updating {db_name}: {e}")
                    skipped += 1
            else:
                skipped += 1
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"\n[+] Customer Balance Processing Complete:")
        print(f"  Matched: {matched}")
        print(f"  Updated: {updated}")
        print(f"  Skipped: {skipped}")
        
    except Exception as e:
        print(f"[FAIL] Error parsing customer balance: {e}")
        import traceback
        traceback.print_exc()

# =====================================================================
# 2. Parse Vendor Balance Detailed
# =====================================================================

def parse_vendor_balance_detailed():
    """
    Extract vendor data from vendor balanced detailed.xlsx
    - Vendor name, balance, terms, 1099 status
    """
    print("\n" + "="*70)
    print("PARSING: vendor balanced detailed.xlsx")
    print("="*70)
    
    file_path = QB_DIR / "vendor balanced detailed.xlsx"
    if not file_path.exists():
        print(f"[FAIL] File not found: {file_path}")
        return
    
    try:
        # Read Excel file
        df = pd.read_excel(file_path, sheet_name=0)
        print(f"✓ Loaded {len(df)} rows")
        print(f"✓ Columns: {list(df.columns)}")
        
        # Show sample data
        print("\nSample data:")
        print(df.head(10))
        
        # Connect to database
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Track updates
        matched = 0
        updated = 0
        skipped = 0
        
        # Process each vendor row
        for idx, row in df.iterrows():
            # Skip header/total rows
            if pd.isna(row.iloc[0]) or str(row.iloc[0]).strip().lower() in ['total', 'vendor', '']:
                continue
            
            # Extract vendor name
            vendor_name = str(row.iloc[0]).strip()
            
            # Try to find matching vendor in database
            cur.execute("""
                SELECT vendor_id, vendor_name, company_name 
                FROM vendors 
                WHERE vendor_name ILIKE %s 
                   OR company_name ILIKE %s
                LIMIT 1
            """, (f"%{vendor_name}%", f"%{vendor_name}%"))
            
            result = cur.fetchone()
            if result:
                vendor_id, db_vendor_name, company_name = result
                matched += 1
                
                # Extract balance
                balance = None
                for col in df.columns:
                    if 'balance' in str(col).lower():
                        balance = row[col]
                        break
                
                # Update vendor QB fields
                try:
                    cur.execute("""
                        UPDATE vendors 
                        SET payment_terms = COALESCE(payment_terms, 'Net 30'),
                            qb_vendor_type = COALESCE(qb_vendor_type, 'Supplier')
                        WHERE vendor_id = %s
                    """, (vendor_id,))
                    updated += 1
                    print(f"  ✓ Updated: {db_vendor_name or company_name}")
                except Exception as e:
                    print(f"  ✗ Error updating {db_vendor_name}: {e}")
                    skipped += 1
            else:
                skipped += 1
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"\n[+] Vendor Balance Processing Complete:")
        print(f"  Matched: {matched}")
        print(f"  Updated: {updated}")
        print(f"  Skipped: {skipped}")
        
    except Exception as e:
        print(f"[FAIL] Error parsing vendor balance: {e}")
        import traceback
        traceback.print_exc()

# =====================================================================
# 3. Parse Old Account Listing
# =====================================================================

def parse_old_account_listing():
    """
    Extract chart of accounts data from old account listing.xlsx
    - Account number, name, type, opening balance
    """
    print("\n" + "="*70)
    print("PARSING: old account listing.xlsx")
    print("="*70)
    
    file_path = QB_DIR / "old account listing.xlsx"
    if not file_path.exists():
        print(f"[FAIL] File not found: {file_path}")
        return
    
    try:
        # Read Excel file
        df = pd.read_excel(file_path, sheet_name=0)
        print(f"✓ Loaded {len(df)} rows")
        print(f"✓ Columns: {list(df.columns)}")
        
        # Show sample data
        print("\nSample data:")
        print(df.head(15))
        
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
            if match:
                account_num = match.group(1)
                account_name = match.group(2).strip()
            else:
                # No match - skip
                skipped += 1
                continue
            
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
                        update_fields.append("qb_tax_line_id = %s")
                        # Extract numeric tax line if possible
                        tax_match = re.search(r'(\d+)', str(tax_line))
                        if tax_match:
                            update_values.append(int(tax_match.group(1)))
                    
                    if update_fields:
                        update_values.append(account_id)
                        sql = f"UPDATE chart_of_accounts SET {', '.join(update_fields)} WHERE account_id = %s"
                        cur.execute(sql, update_values)
                        updated += 1
                        print(f"  [+] Updated: {db_num} · {db_name} (balance: {balance})")
                except Exception as e:
                    print(f"  ✗ Error updating {db_name}: {e}")
                    skipped += 1
            else:
                skipped += 1
                print(f"  [?] No match for: {account_num} · {account_name}")
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"\n[+] Account Listing Processing Complete:")
        print(f"  Matched: {matched}")
        print(f"  Updated: {updated}")
        print(f"  Skipped: {skipped}")
        
    except Exception as e:
        print(f"[FAIL] Error parsing account listing: {e}")
        import traceback
        traceback.print_exc()

# =====================================================================
# 4. Analyze and Report on All QB Files
# =====================================================================

def scan_qb_files():
    """
    Scan all QB Excel files and report structure
    """
    print("\n" + "="*70)
    print("SCANNING: QuickBooks Report Files")
    print("="*70)
    
    excel_files = list(QB_DIR.glob("*.xlsx")) + list(QB_DIR.glob("*.xls"))
    excel_files = [f for f in excel_files if not f.name.startswith('~$')]
    
    print(f"\nFound {len(excel_files)} Excel files:\n")
    
    for file_path in sorted(excel_files):
        print(f"\n[*] {file_path.name}")
        try:
            # Read first few rows
            df = pd.read_excel(file_path, sheet_name=0, nrows=5)
            print(f"   Columns ({len(df.columns)}): {', '.join([str(c)[:30] for c in df.columns[:5]])}")
            print(f"   Rows: {len(pd.read_excel(file_path, sheet_name=0))}")
        except Exception as e:
            print(f"   [!] Error reading: {e}")

# =====================================================================
# Main Execution
# =====================================================================

if __name__ == "__main__":
    print("="*70)
    print("QuickBooks Report Parser")
    print("="*70)
    print("This script will parse QB Excel reports and update the database")
    print("with customer balances, vendor info, and account details.")
    print("="*70)
    
    # Scan all files first to understand structure
    scan_qb_files()
    
    print("\n" + "="*70)
    print("PARSING REPORTS")
    print("="*70)
    
    # Parse each report type
    parse_customer_balance_detailed()
    parse_vendor_balance_detailed()
    parse_old_account_listing()
    
    print("\n" + "="*70)
    print("[+] PARSING COMPLETE")
    print("="*70)
