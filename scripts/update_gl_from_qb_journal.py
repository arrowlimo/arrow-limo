"""
Update general_ledger records with vendor/supplier names from QuickBooks Journal CSV export.
This script matches records by date, account, and amount, then fills in missing name/supplier data.
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
    # Read the QB Journal CSV - updated to use comprehensive backup journal
    csv_path = r"L:\limo\quickbooks\Arrow Limousine backup 2025_Journal.csv"
    print("Reading QuickBooks Journal CSV...")
    df = pd.read_csv(csv_path, skiprows=4)
    df = df[df[df.columns[0]] != '1']  # Remove transaction separator rows
    df_clean = df[df.iloc[:, 1].notna()]  # Keep only rows with dates
    
    print(f"Total rows in CSV: {len(df_clean)}")
    print(f"Rows with Supplier data: {df_clean['Supplier'].notna().sum()}")
    
    # Connect to database
    conn = psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )
    cur = conn.cursor()
    
    # Statistics
    matched = 0
    updated = 0
    already_has_name = 0
    no_match = 0
    
    print("\nProcessing records...")
    print("=" * 100)
    
    for idx, row in df_clean.iterrows():
        supplier = row.get('Supplier')
        if pd.isna(supplier):
            continue
            
        date = parse_date(row.get('Transaction date'))
        if not date:
            continue
            
        account = row.get('Account full name', '')
        debit = parse_amount(row.get('Debit'))
        credit = parse_amount(row.get('Credit'))
        
        # Try to match in general_ledger
        if debit:
            cur.execute("""
                SELECT id, name, account, debit
                FROM general_ledger
                WHERE date = %s
                AND account ILIKE %s
                AND debit = %s
                AND (name IS NULL OR name = 'nan' OR name = '')
                LIMIT 1
            """, (date, f'%{account}%', debit))
        elif credit:
            cur.execute("""
                SELECT id, name, account, credit
                FROM general_ledger
                WHERE date = %s
                AND account ILIKE %s
                AND credit = %s
                AND (name IS NULL OR name = 'nan' OR name = '')
                LIMIT 1
            """, (date, f'%{account}%', credit))
        else:
            continue
        
        result = cur.fetchone()
        
        if result:
            gl_id = result[0]
            current_name = result[1]
            
            # Update the record
            cur.execute("""
                UPDATE general_ledger
                SET name = %s,
                    supplier = %s
                WHERE id = %s
            """, (supplier, supplier, gl_id))
            
            conn.commit()
            updated += 1
            matched += 1
            
            amount_str = f"${debit}" if debit else f"${credit}"
            print(f"Updated GL ID {gl_id}: {date} | {account[:30]:30} | {amount_str:>12} | Supplier: {supplier}")
        else:
            # Check if record exists but already has a name
            if debit:
                cur.execute("""
                    SELECT id, name
                    FROM general_ledger
                    WHERE date = %s
                    AND account ILIKE %s
                    AND debit = %s
                    LIMIT 1
                """, (date, f'%{account}%', debit))
            elif credit:
                cur.execute("""
                    SELECT id, name
                    FROM general_ledger
                    WHERE date = %s
                    AND account ILIKE %s
                    AND credit = %s
                    LIMIT 1
                """, (date, f'%{account}%', credit))
            
            existing = cur.fetchone()
            if existing and existing[1] and existing[1] != 'nan':
                already_has_name += 1
            else:
                no_match += 1
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"Records matched: {matched}")
    print(f"Records updated: {updated}")
    print(f"Records already had name: {already_has_name}")
    print(f"No match found: {no_match}")
    print("\nUpdate complete!")

if __name__ == '__main__':
    main()
