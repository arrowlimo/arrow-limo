"""
Analyze unmatched records between QB Journal CSV and general_ledger
to identify patterns and improve matching logic.
"""
import psycopg2
import pandas as pd
from datetime import datetime, timedelta
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
    
    # Filter to records with Supplier data
    df_suppliers = df_clean[df_clean['Supplier'].notna()].copy()
    print(f"Total CSV rows with Supplier: {len(df_suppliers)}")
    
    # Connect to database
    conn = psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )
    cur = conn.cursor()
    
    # Analyze unmatched patterns
    unmatched_samples = []
    unmatched_by_year = {}
    unmatched_by_account = {}
    
    print("\nAnalyzing matching patterns...")
    print("=" * 100)
    
    for idx, row in df_suppliers.iterrows():
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
        
        # Try exact match
        cur.execute("""
            SELECT id, date, account_name, debit, credit, name, supplier
            FROM general_ledger
            WHERE date = %s 
            AND account_name ILIKE %s
            AND (debit = %s OR credit = %s)
            LIMIT 1
        """, (trans_date, account, amount, amount))
        
        result = cur.fetchone()
        
        if not result:
            # Track unmatched record
            year = trans_date.year
            unmatched_by_year[year] = unmatched_by_year.get(year, 0) + 1
            unmatched_by_account[account] = unmatched_by_account.get(account, 0) + 1
            
            if len(unmatched_samples) < 20:
                # Try fuzzy date match (±3 days)
                cur.execute("""
                    SELECT id, date, account_name, debit, credit, name, supplier
                    FROM general_ledger
                    WHERE date BETWEEN %s AND %s
                    AND account_name ILIKE %s
                    AND (debit = %s OR credit = %s)
                    LIMIT 3
                """, (trans_date - timedelta(days=3), trans_date + timedelta(days=3), 
                      account, amount, amount))
                
                nearby_matches = cur.fetchall()
                
                unmatched_samples.append({
                    'csv_date': trans_date,
                    'csv_account': account,
                    'csv_amount': amount,
                    'csv_supplier': supplier,
                    'nearby_matches': len(nearby_matches),
                    'nearby_details': nearby_matches[:2] if nearby_matches else []
                })
    
    # Print analysis
    print("\n" + "=" * 100)
    print("UNMATCHED RECORDS ANALYSIS")
    print("=" * 100)
    
    print(f"\nUnmatched records by year:")
    for year in sorted(unmatched_by_year.keys()):
        print(f"  {year}: {unmatched_by_year[year]} records")
    
    print(f"\nTop 20 accounts with unmatched records:")
    sorted_accounts = sorted(unmatched_by_account.items(), key=lambda x: x[1], reverse=True)
    for account, count in sorted_accounts[:20]:
        print(f"  {account}: {count} records")
    
    print(f"\n\nSample unmatched records (first 20):")
    print("=" * 100)
    for i, sample in enumerate(unmatched_samples, 1):
        print(f"\n{i}. CSV Record:")
        print(f"   Date: {sample['csv_date']}")
        print(f"   Account: {sample['csv_account']}")
        print(f"   Amount: ${sample['csv_amount']}")
        print(f"   Supplier: {sample['csv_supplier']}")
        print(f"   Nearby matches (±3 days): {sample['nearby_matches']}")
        if sample['nearby_details']:
            for match in sample['nearby_details']:
                gl_id, gl_date, gl_account, gl_debit, gl_credit, gl_name, gl_supplier = match
                gl_amount = gl_debit if gl_debit else gl_credit
                print(f"     → GL {gl_id}: {gl_date} | {gl_account} | ${gl_amount} | Name: {gl_name}")
    
    # Check missing names in GL by account
    print("\n" + "=" * 100)
    print("MISSING NAMES IN GENERAL_LEDGER BY ACCOUNT")
    print("=" * 100)
    
    cur.execute("""
        SELECT account_name, COUNT(*) as missing_count
        FROM general_ledger
        WHERE (name IS NULL OR name = '' OR name = 'nan')
        AND EXTRACT(YEAR FROM date) = 2025
        GROUP BY account_name
        ORDER BY missing_count DESC
        LIMIT 20
    """)
    
    print("\nTop 20 accounts with missing names in 2025:")
    for account, count in cur.fetchall():
        print(f"  {account}: {count} missing names")
    
    conn.close()
    print("\n" + "=" * 100)
    print("Analysis complete!")

if __name__ == "__main__":
    main()
