#!/usr/bin/env python3
"""
Analyze LMS customer export (customerlistbasic.xls) and compare to almsdata.clients.
"""
import os
import sys
import pandas as pd
import psycopg2
from difflib import SequenceMatcher


def get_conn():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        dbname=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
    )


def normalize_name(name):
    """Normalize customer name for comparison."""
    if pd.isna(name) or not name:
        return ''
    return str(name).upper().strip()


def fuzzy_match(s1, s2, threshold=0.85):
    """Return True if strings match above threshold."""
    return SequenceMatcher(None, s1, s2).ratio() >= threshold


def main():
    # Read LMS export - header is at row 15
    print("Reading LMS customer export...")
    df = pd.read_excel('L:\\limo\\data\\customerlistbasic.xls', header=15)
    
    # Clean up - remove rows that are all NaN
    df = df.dropna(how='all')
    
    # Display available columns
    print(f"\nColumns found: {list(df.columns)}")
    print(f"Total rows (after dropping empty): {len(df)}")
    
    # The columns should be: Account, Bill To, Customer Name, City/State/Zip, Home Phone, Work Phone, Fax Phone, Email, Account Type, Salesperson, Source/Referral
    # But they appear as: Account, NaN, Bill To, NaN, Customer Name, etc. (alternating data/NaN)
    # Let's extract just the non-NaN columns
    
    # Take every other column starting from 0 (Account, Bill To, Customer Name, etc.)
    data_cols = [col for i, col in enumerate(df.columns) if i % 2 == 0]
    df_clean = df[data_cols].copy()
    
    print(f"\nCleaned columns: {list(df_clean.columns)}")
    print(f"\nFirst 10 rows:")
    print(df_clean.head(10).to_string())
    
    # Rename columns for clarity
    if len(df_clean.columns) >= 6:
        df_clean.columns = [
            'account_number', 'bill_to', 'customer_name', 'city_state_zip',
            'home_phone', 'work_phone', 'fax_phone', 'email',
            'account_type', 'salesperson', 'source_referral', 'extra'
        ][:len(df_clean.columns)]
    
    # Remove any header repetitions and empty rows
    df_clean = df_clean[df_clean['account_number'] != 'Account']
    df_clean = df_clean[df_clean['account_number'].notna()]
    df_clean['account_number'] = df_clean['account_number'].astype(str).str.strip()
    
    print(f"\nLMS customers after cleanup: {len(df_clean)}")
    print(f"\nSample data:")
    print(df_clean.head(20).to_string())
    
    # Get almsdata clients
    print("\n" + "="*80)
    print("Comparing to almsdata.clients...")
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT client_id, account_number, client_name, company_name, email, primary_phone
        FROM clients
        ORDER BY client_id
    """)
    db_clients = cur.fetchall()
    print(f"Database clients: {len(db_clients)}")
    
    # Build lookup maps
    lms_by_account = {}
    for _, row in df_clean.iterrows():
        acc = str(row['account_number']).strip()
        if acc and acc != 'nan':
            lms_by_account[acc] = {
                'name': normalize_name(row.get('customer_name', '')),
                'email': str(row.get('email', '')).strip() if pd.notna(row.get('email')) else '',
                'phone': str(row.get('work_phone', '')).strip() if pd.notna(row.get('work_phone')) else '',
            }
    
    db_by_account = {}
    for cid, acc, cname, company, email, phone in db_clients:
        acc_str = str(acc).strip() if acc else ''
        if acc_str:
            db_by_account[acc_str] = {
                'client_id': cid,
                'name': normalize_name(cname or company),
                'email': email or '',
                'phone': phone or '',
            }
    
    # Compare
    print("\n" + "="*80)
    print("COMPARISON RESULTS:")
    print("="*80)
    
    # 1. LMS accounts NOT in database
    missing_in_db = []
    for acc, data in lms_by_account.items():
        if acc not in db_by_account:
            missing_in_db.append((acc, data['name']))
    
    print(f"\n1. LMS accounts NOT in database: {len(missing_in_db)}")
    if missing_in_db:
        print("\nFirst 20 missing accounts:")
        for acc, name in missing_in_db[:20]:
            print(f"  {acc}: {name}")
    
    # 2. DB accounts NOT in LMS
    missing_in_lms = []
    for acc, data in db_by_account.items():
        if acc not in lms_by_account:
            missing_in_lms.append((acc, data['name'], data['client_id']))
    
    print(f"\n2. Database accounts NOT in LMS: {len(missing_in_lms)}")
    if missing_in_lms:
        print("\nFirst 20 DB-only accounts:")
        for acc, name, cid in missing_in_lms[:20]:
            print(f"  {acc}: {name} (client_id={cid})")
    
    # 3. Name mismatches (same account, different name)
    name_mismatches = []
    for acc in set(lms_by_account.keys()) & set(db_by_account.keys()):
        lms_name = lms_by_account[acc]['name']
        db_name = db_by_account[acc]['name']
        if lms_name and db_name and not fuzzy_match(lms_name, db_name, 0.90):
            name_mismatches.append((acc, lms_name, db_name))
    
    print(f"\n3. Name mismatches (same account): {len(name_mismatches)}")
    if name_mismatches:
        print("\nFirst 20 mismatches:")
        for acc, lms_n, db_n in name_mismatches[:20]:
            print(f"  {acc}:")
            print(f"    LMS: {lms_n}")
            print(f"    DB:  {db_n}")
    
    # 4. Perfect matches
    perfect = []
    for acc in set(lms_by_account.keys()) & set(db_by_account.keys()):
        lms_name = lms_by_account[acc]['name']
        db_name = db_by_account[acc]['name']
        if lms_name and db_name and fuzzy_match(lms_name, db_name, 0.90):
            perfect.append(acc)
    
    print(f"\n4. Perfect/near-perfect matches: {len(perfect)}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY:")
    print("="*80)
    print(f"LMS customers:           {len(lms_by_account)}")
    print(f"DB clients:              {len(db_by_account)}")
    print(f"Missing in DB:           {len(missing_in_db)}")
    print(f"Missing in LMS:          {len(missing_in_lms)}")
    print(f"Name mismatches:         {len(name_mismatches)}")
    print(f"Perfect matches:         {len(perfect)}")
    
    # Check the "suspect" clients mentioned
    print("\n" + "="*80)
    print("CHECKING SUSPECT CLIENTS:")
    print("="*80)
    suspect_accounts = ['07469', '07475']
    for acc in suspect_accounts:
        in_lms = acc in lms_by_account
        in_db = acc in db_by_account
        print(f"\nAccount {acc}:")
        print(f"  In LMS: {in_lms}")
        if in_lms:
            print(f"    Name: {lms_by_account[acc]['name']}")
        print(f"  In DB: {in_db}")
        if in_db:
            print(f"    Name: {db_by_account[acc]['name']}")
            print(f"    client_id: {db_by_account[acc]['client_id']}")
    
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
