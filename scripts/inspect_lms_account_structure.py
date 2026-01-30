#!/usr/bin/env python3
"""
Query LMS account structure to identify parent-child relationships.
Focus on account 01007 (business + husband/wife example).
"""

import pyodbc
import os

LMS_PATH = r"L:\limo\database_backups\lms2026.mdb"

def query_lms_account(account_no):
    """Query LMS for account structure."""
    access_conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
    access_conn = pyodbc.connect(access_conn_str)
    access_cur = access_conn.cursor()
    
    print("=" * 120)
    print(f"LMS ACCOUNT STRUCTURE: {account_no}")
    print("=" * 120)
    
    # Get Customer table records
    print(f"\nCUSTOMER TABLE (Primary contacts):")
    print("-" * 120)
    
    access_cur.execute(f"""
        SELECT Account_No, Bill_To, Attention, Phone, Fax
        FROM Customer 
        WHERE Account_No = '{account_no}'
        ORDER BY Account_No, Bill_To
    """)
    
    customer_rows = access_cur.fetchall()
    if not customer_rows:
        print(f"  No Customer records found for {account_no}")
    else:
        print(f"  Found {len(customer_rows)} Customer record(s):")
        for i, row in enumerate(customer_rows, 1):
            acct, bill_to, attention, phone, fax = row
            print(f"\n  [{i}] Account: {acct}")
            print(f"      Bill To:  {bill_to}")
            print(f"      Attention: {attention}")
            print(f"      Phone: {phone}")
            print(f"      Fax: {fax}")
    
    # Get CustAdmin table records
    print(f"\n\nCUSTADMIN TABLE (Secondary contacts/admins):")
    print("-" * 120)
    
    access_cur.execute(f"""
        SELECT Account_No, Name, Phone, Email
        FROM CustAdmin
        WHERE Account_No = '{account_no}'
        ORDER BY Account_No, Name
    """)
    
    custadmin_rows = access_cur.fetchall()
    if not custadmin_rows:
        print(f"  No CustAdmin records found for {account_no}")
    else:
        print(f"  Found {len(custadmin_rows)} CustAdmin record(s):")
        for i, row in enumerate(custadmin_rows, 1):
            acct, name, phone, email = row
            print(f"\n  [{i}] Account: {acct}")
            print(f"      Name: {name}")
            print(f"      Phone: {phone}")
            print(f"      Email: {email}")
    
    # Get Reserve records for this account
    print(f"\n\nRESERVE TABLE (Charters for this account):")
    print("-" * 120)
    
    access_cur.execute(f"""
        SELECT Reserve_No, Name, PU_Date, Total
        FROM Reserve
        WHERE Account_No = '{account_no}'
        ORDER BY Reserve_No DESC
    """)
    
    reserve_rows = access_cur.fetchall()
    if not reserve_rows:
        print(f"  No Reserve records found for {account_no}")
    else:
        print(f"  Found {len(reserve_rows)} Reserve record(s) (showing 10 most recent):")
        print(f"\n  {'Reserve':<10} {'Client Name':<40} {'Pickup Date':<12} {'Total':<10}")
        print(f"  {'-'*10} {'-'*40} {'-'*12} {'-'*10}")
        for row in reserve_rows:
            res_no, name, date, total = row
            date_str = date.strftime('%Y-%m-%d') if date else 'N/A'
            print(f"  {res_no:<10} {str(name)[:39]:<40} {date_str:<12} {total:<10.2f}")
    
    # Count total reserves
    access_cur.execute(f"""
        SELECT COUNT(*) FROM Reserve WHERE Account_No = '{account_no}'
    """)
    
    total_reserves = access_cur.fetchone()[0]
    print(f"\n  Total charters under {account_no}: {total_reserves}")
    
    access_conn.close()

def analyze_all_accounts_with_multiple_contacts():
    """Find all accounts with multiple Customer/CustAdmin records (parent-child pattern)."""
    access_conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
    access_conn = pyodbc.connect(access_conn_str)
    access_cur = access_conn.cursor()
    
    print("\n\n" + "=" * 120)
    print("ACCOUNTS WITH MULTIPLE CONTACTS (Parent-Child Pattern)")
    print("=" * 120)
    
    # Get Customer counts by account
    access_cur.execute("""
        SELECT Account_No, COUNT(*) as cnt
        FROM Customer
        GROUP BY Account_No
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
    """)
    
    multi_customer = {row[0]: row[1] for row in access_cur.fetchall()}
    
    # Get CustAdmin counts by account
    access_cur.execute("""
        SELECT Account_No, COUNT(*) as cnt
        FROM CustAdmin
        GROUP BY Account_No
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
    """)
    
    multi_admin = {row[0]: row[1] for row in access_cur.fetchall()}
    
    # Combined: accounts with multiple contacts (either Customer or CustAdmin)
    all_multi = set(multi_customer.keys()) | set(multi_admin.keys())
    
    print(f"\nTotal accounts with multiple contacts: {len(all_multi)}")
    print(f"  - Multiple Customer records: {len(multi_customer)}")
    print(f"  - Multiple CustAdmin records: {len(multi_admin)}")
    
    print("\nTop 15 accounts with most contacts:")
    print(f"{'Account':<10} {'Customers':<12} {'Admins':<12} {'Total':<10}")
    print(f"{'-'*10} {'-'*12} {'-'*12} {'-'*10}")
    
    sorted_accounts = sorted(all_multi, 
                            key=lambda x: (multi_customer.get(x, 0) + multi_admin.get(x, 0)), 
                            reverse=True)
    
    for acct in sorted_accounts[:15]:
        cust_cnt = multi_customer.get(acct, 0)
        admin_cnt = multi_admin.get(acct, 0)
        total = cust_cnt + admin_cnt
        print(f"{acct:<10} {cust_cnt:<12} {admin_cnt:<12} {total:<10}")
    
    access_conn.close()
    return all_multi

if __name__ == '__main__':
    import sys
    
    # First: show all multi-contact accounts
    multi_accounts = analyze_all_accounts_with_multiple_contacts()
    
    # Then: detail for account 01007
    print("\n\n")
    query_lms_account("01007")
    
    # Check if there are other accounts with similar parent-child pattern
    print("\n\n" + "=" * 120)
    print("SAMPLE: A few more accounts with multiple contacts")
    print("=" * 120)
    
    for acct in sorted(list(multi_accounts))[:5]:
        if acct != "01007":  # Skip 01007 since we already showed it
            print(f"\n\nSample Account: {acct}")
            query_lms_account(acct)
            break  # Just show one sample
