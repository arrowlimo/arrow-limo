"""
Import employee data from QuickBooks Journal CSV to general_ledger
Matches by date, account, and amount, then populates employee field
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
    
    # Filter to records with Employee data
    df_employees = df_clean[df_clean['Employee'].notna()].copy()
    print(f"Total rows in CSV: {len(df_clean)}")
    print(f"Rows with Employee data: {len(df_employees)}")
    
    # Show employee breakdown
    print("\nTop 20 employees by transaction count:")
    employee_counts = df_employees['Employee'].value_counts()
    for emp, count in employee_counts.head(20).items():
        print(f"  {emp}: {count}")
    
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
    updated_employee = 0
    already_has_employee = 0
    no_match = 0
    
    print("\n" + "=" * 120)
    print("Processing employee records with enhanced matching...")
    print("=" * 120)
    
    for idx, row in df_employees.iterrows():
        employee = row.get('Employee')
        if pd.isna(employee):
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
            SELECT id, date, account_name, account, debit, credit, name, employee
            FROM general_ledger
            WHERE date = %s 
            AND (account_name ILIKE %s OR account ILIKE %s)
            AND (debit = %s OR credit = %s)
            AND (employee IS NULL OR employee = '' OR employee = 'nan')
            LIMIT 1
        """, (trans_date, account, account, amount, amount))
        
        result = cur.fetchone()
        
        if result:
            matched += 1
            gl_id, gl_date, gl_account_name, gl_account, gl_debit, gl_credit, gl_name, gl_employee = result
            gl_amount = gl_debit if gl_debit else gl_credit
            
            # Update employee field
            cur.execute("""
                UPDATE general_ledger 
                SET employee = %s
                WHERE id = %s
            """, (employee, gl_id))
            
            updated_employee += 1
            account_used = gl_account_name if gl_account_name else gl_account
            
            if updated_employee <= 50 or updated_employee % 100 == 0:  # Print first 50, then every 100th
                print(f"Updated GL ID {gl_id}: {gl_date} | {account_used:40s} | ${gl_amount:12} | Employee: {employee}")
        else:
            # Check if employee already exists
            cur.execute("""
                SELECT id FROM general_ledger
                WHERE date = %s 
                AND (account_name ILIKE %s OR account ILIKE %s)
                AND (debit = %s OR credit = %s)
                AND employee IS NOT NULL AND employee != '' AND employee != 'nan'
                LIMIT 1
            """, (trans_date, account, account, amount, amount))
            
            if cur.fetchone():
                already_has_employee += 1
            else:
                no_match += 1
    
    # Commit changes
    conn.commit()
    
    print("\n" + "=" * 120)
    print("SUMMARY")
    print("=" * 120)
    print(f"Records matched: {matched}")
    print(f"Employee field updated: {updated_employee}")
    print(f"Records already had employee: {already_has_employee}")
    print(f"No match found: {no_match}")
    
    # Check employee data coverage
    cur.execute("""
        SELECT COUNT(*) 
        FROM general_ledger 
        WHERE employee IS NOT NULL AND employee != '' AND employee != 'nan'
    """)
    total_with_employee = cur.fetchone()[0]
    
    cur.execute("""
        SELECT COUNT(*) 
        FROM general_ledger 
        WHERE employee IS NOT NULL AND employee != '' AND employee != 'nan'
        AND EXTRACT(YEAR FROM date) = 2025
    """)
    with_employee_2025 = cur.fetchone()[0]
    
    print(f"\nTotal records with employee data: {total_with_employee:,}")
    print(f"  - In 2025: {with_employee_2025:,}")
    
    # Show top employees in database
    print("\nTop 15 employees by transaction count in database:")
    cur.execute("""
        SELECT employee, COUNT(*) as count
        FROM general_ledger
        WHERE employee IS NOT NULL AND employee != '' AND employee != 'nan'
        GROUP BY employee
        ORDER BY count DESC
        LIMIT 15
    """)
    for emp, count in cur.fetchall():
        print(f"  {emp}: {count:,}")
    
    print(f"\nUpdate complete!")
    
    conn.close()

if __name__ == "__main__":
    main()
