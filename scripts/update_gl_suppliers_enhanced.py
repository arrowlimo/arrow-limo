"""
Enhanced matching script for QB Journal to general_ledger
Uses flexible matching:
1. Match by date + account (both account_name and account fields) + amount
2. Fill supplier field where missing
"""
import psycopg2
import pandas as pd
from datetime import datetime
from decimal import Decimal

def parse_date(date_str):
    """Parse date in DD/MM/YYYY format"""
    if pd.isna(date_str):
        return None
    try:
        return datetime.strptime(str(date_str), '%d/%m/%Y').date()
    except:
        return None

def parse_amount(amount_str):
    """Parse amount removing commas"""
    if pd.isna(amount_str):
        return None
    try:
        clean_str = str(amount_str).replace(',', '')
        return Decimal(clean_str)
    except:
        return None

def main():
    # Read the QB Journal CSV
    csv_path = r"L:\limo\quickbooks\Arrow Limousine backup 2025_Journal.csv"
    print("Reading QuickBooks Journal CSV...")
    df = pd.read_csv(csv_path, skiprows=4, low_memory=False)
    df = df[df[df.columns[0]] != '1']  # Remove transaction separator rows
    df_clean = df[df.iloc[:, 1].notna()]  # Keep only rows with dates
    
    print(f"Total rows in CSV: {len(df_clean)}")
    print(f"Rows with Supplier data: {df_clean['Supplier'].notna().sum()}")
    
    # Connect to database
    conn = psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )
    cur = conn.cursor()
    
    # Statistics
    matched = 0
    updated_supplier = 0
    already_has_supplier = 0
    no_match = 0
    
    print("\nProcessing records with enhanced matching...")
    print("=" * 100)
    
    for idx, row in df_clean.iterrows():
        supplier = row.get('Supplier')
        if pd.isna(supplier):
            continue
            
        trans_date = parse_date(row.get('Transaction date'))
        if not trans_date:
            continue
            
        account = str(row.get('Account full name', '')).strip()
        debit = parse_amount(row.get('Debit'))
        credit = parse_amount(row.get('Credit'))
        amount = debit if debit else credit
        
        if not amount or not account:
            continue
        
        # Try matching with BOTH account_name and account fields
        cur.execute("""
            SELECT id, date, account_name, account, debit, credit, name, supplier
            FROM general_ledger
            WHERE date = %s 
            AND (account_name ILIKE %s OR account ILIKE %s)
            AND (debit = %s OR credit = %s)
            AND (supplier IS NULL OR supplier = '' OR supplier = 'nan')
            LIMIT 1
        """, (trans_date, account, account, amount, amount))
        
        result = cur.fetchone()
        
        if result:
            matched += 1
            gl_id, gl_date, gl_account_name, gl_account, gl_debit, gl_credit, gl_name, gl_supplier = result
            gl_amount = gl_debit if gl_debit else gl_credit
            
            # Update supplier field
            cur.execute("""
                UPDATE general_ledger 
                SET supplier = %s
                WHERE id = %s
            """, (supplier, gl_id))
            
            updated_supplier += 1
            account_used = gl_account_name if gl_account_name else gl_account
            print(f"Updated GL ID {gl_id}: {gl_date} | {account_used:30s} | ${gl_amount:12} | Supplier: {supplier}")
        else:
            # Check if supplier already exists
            cur.execute("""
                SELECT id FROM general_ledger
                WHERE date = %s 
                AND (account_name ILIKE %s OR account ILIKE %s)
                AND (debit = %s OR credit = %s)
                AND supplier IS NOT NULL AND supplier != '' AND supplier != 'nan'
                LIMIT 1
            """, (trans_date, account, account, amount, amount))
            
            if cur.fetchone():
                already_has_supplier += 1
            else:
                no_match += 1
    
    # Commit changes
    conn.commit()
    
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"Records matched: {matched}")
    print(f"Supplier field updated: {updated_supplier}")
    print(f"Records already had supplier: {already_has_supplier}")
    print(f"No match found: {no_match}")
    print(f"\nUpdate complete!")
    
    conn.close()

if __name__ == "__main__":
    main()
