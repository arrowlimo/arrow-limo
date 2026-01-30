#!/usr/bin/env python3
"""
Import the 42 missing LMS customers (07502-07546) from customerlistbasic.xls
"""
import os
import sys
from datetime import datetime
import pandas as pd
import psycopg2


def get_conn():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        dbname=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REDACTED***'),
    )


def main(write=False):
    # Read LMS export
    print("Reading LMS customer export...")
    df = pd.read_excel('L:\\limo\\data\\customerlistbasic.xls', header=15)
    df = df.dropna(how='all')
    
    # Extract data columns (every other column)
    data_cols = [col for i, col in enumerate(df.columns) if i % 2 == 0]
    df_clean = df[data_cols].copy()
    
    # Rename columns
    if len(df_clean.columns) >= 11:
        df_clean.columns = [
            'account_number', 'bill_to', 'customer_name', 'city_state_zip',
            'home_phone', 'work_phone', 'fax_phone', 'email',
            'account_type', 'salesperson', 'source_referral'
        ] + list(df_clean.columns[11:])
    
    # Clean up
    df_clean = df_clean[df_clean['account_number'] != 'Account']
    df_clean = df_clean[df_clean['account_number'].notna()]
    df_clean['account_number'] = df_clean['account_number'].astype(str).str.strip()
    
    # Get existing DB accounts
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("SELECT account_number FROM clients WHERE account_number IS NOT NULL")
    existing_accounts = {str(row[0]).strip() for row in cur.fetchall()}
    print(f"Existing DB accounts: {len(existing_accounts)}")
    
    # Find missing customers
    missing = []
    for _, row in df_clean.iterrows():
        acc = str(row['account_number']).strip()
        if acc and acc != 'nan' and acc not in existing_accounts:
            missing.append(row)
    
    print(f"\nMissing customers in DB: {len(missing)}")
    
    if not missing:
        print("No missing customers to import!")
        cur.close()
        conn.close()
        return
    
    # Check if any charters/payments reference these accounts
    print("\nChecking for charters/payments referencing missing accounts...")
    missing_accounts = [str(row['account_number']).strip() for row in missing]
    
    cur.execute("""
        SELECT account_number, COUNT(*) as charter_count
        FROM charters
        WHERE account_number = ANY(%s)
        GROUP BY account_number
        ORDER BY charter_count DESC
    """, (missing_accounts,))
    
    charter_refs = cur.fetchall()
    if charter_refs:
        print(f"\nFound {len(charter_refs)} missing accounts with charters:")
        for acc, count in charter_refs[:10]:
            print(f"  {acc}: {count} charters")
    
    cur.execute("""
        SELECT account_number, COUNT(*) as payment_count
        FROM payments
        WHERE account_number = ANY(%s)
        GROUP BY account_number
        ORDER BY payment_count DESC
    """, (missing_accounts,))
    
    payment_refs = cur.fetchall()
    if payment_refs:
        print(f"\nFound {len(payment_refs)} missing accounts with payments:")
        for acc, count in payment_refs[:10]:
            print(f"  {acc}: {count} payments")
    
    # Display customers to import
    print(f"\nCustomers to import ({len(missing)}):")
    for row in missing[:20]:
        name = str(row.get('customer_name', ''))[:40]
        email = str(row.get('email', ''))[:30] if pd.notna(row.get('email')) else ''
        print(f"  {row['account_number']}: {name} {email}")
    
    if len(missing) > 20:
        print(f"  ... and {len(missing) - 20} more")
    
    if not write:
        print("\nDRY-RUN: Use --write to import these customers")
        cur.close()
        conn.close()
        return
    
    # Import customers
    print(f"\nImporting {len(missing)} customers...")
    imported = 0
    errors = []
    
    for row in missing:
        try:
            acc = str(row['account_number']).strip()
            name = str(row.get('customer_name', '')) if pd.notna(row.get('customer_name')) else ''
            email = str(row.get('email', '')) if pd.notna(row.get('email')) else None
            work_phone = str(row.get('work_phone', '')) if pd.notna(row.get('work_phone')) else None
            city_state = str(row.get('city_state_zip', '')) if pd.notna(row.get('city_state_zip')) else None
            
            # Parse city/state/zip if available
            city = None
            state = None
            zip_code = None
            if city_state:
                # Format is typically "Red Deer AB T4N 1C8" or "Red Deer AB"
                parts = city_state.strip().split()
                if len(parts) >= 2:
                    # Find province code (2 letters)
                    for i, part in enumerate(parts):
                        if len(part) == 2 and part.isupper():
                            city = ' '.join(parts[:i]) if i > 0 else None
                            state = part
                            if i + 1 < len(parts):
                                zip_code = ' '.join(parts[i+1:])
                            break
            
            # Get next available client_id
            cur.execute("SELECT COALESCE(MAX(client_id), 0) + 1 FROM clients")
            next_id = cur.fetchone()[0]
            
            cur.execute("""
                INSERT INTO clients (
                    client_id, account_number, client_name, company_name, email, 
                    primary_phone, city, state, zip_code,
                    created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING client_id
            """, (next_id, acc, name or None, name or None, email, work_phone, city, state, zip_code))
            
            client_id = cur.fetchone()[0]
            imported += 1
            
            if imported <= 5:
                print(f"  ✓ Imported {acc}: {name} (client_id={client_id})")
        
        except Exception as e:
            errors.append((acc, str(e)))
            print(f"  ✗ Error importing {acc}: {e}")
    
    if write:
        conn.commit()
        print(f"\n✓ Successfully imported {imported} customers")
        
        if errors:
            print(f"\n✗ Errors: {len(errors)}")
            for acc, err in errors[:5]:
                print(f"  {acc}: {err}")
    else:
        conn.rollback()
    
    cur.close()
    conn.close()


if __name__ == '__main__':
    write = '--write' in sys.argv
    main(write=write)
