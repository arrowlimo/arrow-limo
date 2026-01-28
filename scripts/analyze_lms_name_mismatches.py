#!/usr/bin/env python3
"""
Generate detailed report of the 26 LMS name mismatches.
Show current DB name, LMS name, and any charters/payments using the account.
"""
import os
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
    # Read LMS export
    print("Reading LMS customer export...")
    df = pd.read_excel('L:\\limo\\data\\customerlistbasic.xls', header=15)
    df = df.dropna(how='all')
    
    # Extract data columns
    data_cols = [col for i, col in enumerate(df.columns) if i % 2 == 0]
    df_clean = df[data_cols].copy()
    
    if len(df_clean.columns) >= 11:
        df_clean.columns = [
            'account_number', 'bill_to', 'customer_name', 'city_state_zip',
            'home_phone', 'work_phone', 'fax_phone', 'email',
            'account_type', 'salesperson', 'source_referral'
        ] + list(df_clean.columns[11:])
    
    df_clean = df_clean[df_clean['account_number'] != 'Account']
    df_clean = df_clean[df_clean['account_number'].notna()]
    df_clean['account_number'] = df_clean['account_number'].astype(str).str.strip()
    
    # Build LMS lookup
    lms_by_account = {}
    for _, row in df_clean.iterrows():
        acc = str(row['account_number']).strip()
        if acc and acc != 'nan':
            lms_by_account[acc] = {
                'name': normalize_name(row.get('customer_name', '')),
                'email': str(row.get('email', '')).strip() if pd.notna(row.get('email')) else '',
            }
    
    # Get DB clients
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT client_id, account_number, client_name, company_name, email
        FROM clients
        WHERE account_number IS NOT NULL
        ORDER BY account_number
    """)
    
    db_clients = cur.fetchall()
    db_by_account = {}
    for cid, acc, cname, company, email in db_clients:
        acc_str = str(acc).strip() if acc else ''
        if acc_str:
            db_by_account[acc_str] = {
                'client_id': cid,
                'name': normalize_name(cname or company),
                'display': cname or company or '',
                'email': email or '',
            }
    
    # Find name mismatches
    mismatches = []
    for acc in set(lms_by_account.keys()) & set(db_by_account.keys()):
        lms_name = lms_by_account[acc]['name']
        db_name = db_by_account[acc]['name']
        if lms_name and db_name and not fuzzy_match(lms_name, db_name, 0.90):
            mismatches.append({
                'account': acc,
                'lms_name': lms_name,
                'db_name': db_name,
                'db_display': db_by_account[acc]['display'],
                'client_id': db_by_account[acc]['client_id'],
                'lms_email': lms_by_account[acc]['email'],
                'db_email': db_by_account[acc]['email'],
            })
    
    print(f"\nFound {len(mismatches)} name mismatches")
    print("="*100)
    
    # Check usage for each mismatch
    for m in mismatches:
        acc = m['account']
        
        # Get charters
        cur.execute("""
            SELECT COUNT(*), 
                   MIN(charter_date) as first_date, 
                   MAX(charter_date) as last_date,
                   SUM(total_amount_due) as total_revenue
            FROM charters
            WHERE account_number = %s
        """, (acc,))
        charter_data = cur.fetchone()
        charter_count = charter_data[0] if charter_data else 0
        
        # Get payments
        cur.execute("""
            SELECT COUNT(*), SUM(amount) as total_paid
            FROM payments
            WHERE account_number = %s
        """, (acc,))
        payment_data = cur.fetchone()
        payment_count = payment_data[0] if payment_data else 0
        
        # Get most recent charter client_display_name
        cur.execute("""
            SELECT client_display_name, charter_date, reserve_number
            FROM charters
            WHERE account_number = %s
            ORDER BY charter_date DESC
            LIMIT 1
        """, (acc,))
        recent = cur.fetchone()
        
        print(f"\nAccount: {acc} (client_id={m['client_id']})")
        print(f"  LMS Name:    {m['lms_name']}")
        print(f"  DB Name:     {m['db_name']}")
        if m['lms_email'] or m['db_email']:
            print(f"  LMS Email:   {m['lms_email']}")
            print(f"  DB Email:    {m['db_email']}")
        print(f"  Charters:    {charter_count}")
        if charter_count > 0:
            print(f"    First:     {charter_data[1]}")
            print(f"    Last:      {charter_data[2]}")
            print(f"    Revenue:   ${charter_data[3]:,.2f}" if charter_data[3] else "    Revenue:   $0.00")
        print(f"  Payments:    {payment_count}")
        if payment_count > 0:
            print(f"    Total:     ${payment_data[1]:,.2f}" if payment_data[1] else "    Total:     $0.00")
        if recent:
            print(f"  Recent Charter: {recent[2]} on {recent[1]} - display_name: '{recent[0] or 'NULL'}'")
    
    # Summary recommendation
    print("\n" + "="*100)
    print("RECOMMENDATIONS:")
    print("="*100)
    print("\n1. LIKELY ACCOUNT REASSIGNMENTS (different business took over account number):")
    reassignments = [m for m in mismatches if not any(word in m['lms_name'] for word in m['db_name'].split())]
    for m in reassignments[:10]:
        print(f"   {m['account']}: {m['db_name']} → {m['lms_name']}")
    
    print(f"\n2. LIKELY NAME CHANGES (same business, different name format):")
    name_changes = [m for m in mismatches if any(word in m['lms_name'] for word in m['db_name'].split())]
    for m in name_changes[:10]:
        print(f"   {m['account']}: {m['db_name']} → {m['lms_name']}")
    
    print(f"\n3. UPDATE RECOMMENDATIONS:")
    print(f"   - Total mismatches: {len(mismatches)}")
    print(f"   - Likely reassignments: {len(reassignments)} (may need new client records)")
    print(f"   - Likely name changes: {len(name_changes)} (safe to update company_name)")
    
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
