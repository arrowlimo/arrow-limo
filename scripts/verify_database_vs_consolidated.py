"""
Verify database banking_transactions against consolidated Scotia CSV.

This script:
1. Loads consolidated CSV (2,053 unique transactions)
2. Loads database Scotia transactions (791 transactions)
3. Compares using date+vendor+amount matching
4. Reports what's missing, what matches, and what's extra in database

Created: November 24, 2025
"""

import os
import csv
import psycopg2
from datetime import datetime
from decimal import Decimal
from collections import defaultdict

# Database connection parameters
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

def load_consolidated_csv():
    """Load consolidated CSV file."""
    csv_path = r'L:\limo\data\scotia_consolidated_all_years.csv'
    transactions = []
    
    print(f"Loading consolidated CSV: {csv_path}")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            txn_date = datetime.strptime(row['date'], '%Y-%m-%d').date()
            amount = Decimal(row['amount'])
            
            transactions.append({
                'date': txn_date,
                'vendor': row['vendor'].strip(),
                'amount': amount,
                'type': row['type'],
                'num': row['num'],
                'cleared': row['cleared'],
                'balance': Decimal(row['balance']),
                'source_files': row['source_files'],
                'appears_in_count': int(row['appears_in_count'])
            })
    
    print(f"   Loaded: {len(transactions)} consolidated transactions")
    return transactions

def load_database_transactions():
    """Load Scotia Bank transactions from database."""
    print("\nLoading database transactions...")
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Get all Scotia transactions (not just 2012)
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            balance,
            account_number
        FROM banking_transactions
        WHERE account_number = '903990106011'
        ORDER BY transaction_date, transaction_id
    """)
    
    transactions = []
    for row in cur.fetchall():
        txn_id = row[0]
        txn_date = row[1]
        description = row[2] or ''
        debit = row[3] or Decimal('0')
        credit = row[4] or Decimal('0')
        balance = row[5] or Decimal('0')
        account = row[6]
        
        # Calculate amount (negative for debits, positive for credits)
        if debit > 0:
            amount = -debit
        else:
            amount = credit
        
        transactions.append({
            'id': txn_id,
            'date': txn_date,
            'description': description,
            'amount': amount,
            'debit': debit,
            'credit': credit,
            'balance': balance
        })
    
    cur.close()
    conn.close()
    
    print(f"   Loaded: {len(transactions)} database transactions")
    return transactions

def normalize_vendor(vendor):
    """Normalize vendor name for comparison."""
    import re
    
    # Strip and uppercase
    normalized = vendor.strip().upper()
    
    # Remove common transaction type prefixes
    prefixes_to_remove = [
        r'^POINT OF SALE PURCHASE\s+',      # "POINT OF SALE PURCHASE"
        r'^CHEQUE\s+#?\s*\d*\s*',           # "Cheque #dd", "Cheque #123", "Cheque"
        r'^CHQ\s+\d+\s+\d+',                # "CHQ 9 3700138410" - cheque number patterns
        r'^CHQ\s+\d+\s*',                   # "CHQ 96", "CHQ 105"
        r'^BILL PMT\s+-\s*',                # "Bill Pmt - "
        r'^BILL PM!\s+-\s*',                # "Bill Pm! - "
        r'^DEPOSIT\s+-\s*',                 # "Deposit - "
        r'^CHEQUE\s+',                      # "Cheque "
        r'^DEBIT MEMO\s+',                  # "DEBIT MEMO"
    ]
    
    for prefix_pattern in prefixes_to_remove:
        normalized = re.sub(prefix_pattern, '', normalized, flags=re.IGNORECASE)
    
    # Remove location/branch suffixes (city names, provinces, country codes)
    # Examples: "RED DEER AB", "RED DEER ABCA", "RED DEER ABCD"
    # Also remove "RED DEER" appearing before location codes
    normalized = re.sub(r'\s+RED\s+DEER\s+AB[A-Z]*$', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\s+RED\s+DEER$', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\s+CALGARY\s+AB[A-Z]*$', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\s+EDMONTON\s+AB[A-Z]*$', '', normalized, flags=re.IGNORECASE)
    
    # Remove common location descriptors and gas station suffixes
    normalized = re.sub(r'\(C-STOR[^)]*\)?', '', normalized, flags=re.IGNORECASE)  # Handle missing closing paren
    normalized = re.sub(r'\([^)]*BRANCH[^)]*\)', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\s+DEERPARK', '', normalized, flags=re.IGNORECASE)  # Not just at end
    normalized = re.sub(r'\s+GAS\s+BAR', '', normalized, flags=re.IGNORECASE)  # Not just at end
    
    # Remove store codes and numbers (more aggressive)
    normalized = re.sub(r'\s+ST\d+#\s*\d+[A-Z]*', '', normalized, flags=re.IGNORECASE)  # ST107# 67H
    normalized = re.sub(r'\s+#\d+', '', normalized)  # Any # followed by digits
    normalized = re.sub(r'\s+\d+\s*-\s*LB\s+\d+TH\s+ST\.?', ' LIQUOR BARN', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'^\d+\s*-\s*', '', normalized)  # Remove leading store numbers like "604 - "
    
    # Gas station specific normalizations
    normalized = re.sub(r'CENDALE\s+SHELL', 'SHELL', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'SHELL\s+CANADA\s+PRODU.*', 'SHELL', normalized, flags=re.IGNORECASE)
    
    # Restaurant name normalizations
    normalized = re.sub(r'PHILLIS\s+RESTAURANTS?', 'PHILS', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"PHIL'?S\s+RESTAURANT", 'PHILS', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'ROYAL\s+RESTAUR', 'PATTYS FAMILY', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"PATTY'?S\s+FAMILY", 'PATTYS FAMILY', normalized, flags=re.IGNORECASE)
    
    # Tim Hortons variations
    normalized = re.sub(r'LEASES\s+ST\s+STATION.*', 'TIM HORTONS', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'TIM\s+HORTONS?', 'TIM HORTONS', normalized, flags=re.IGNORECASE)
    
    # Fix possessive forms
    normalized = re.sub(r"'S'S", "'S", normalized)  # Fix double possessive
    normalized = re.sub(r"'S\s*$", "", normalized)  # Remove trailing possessive
    
    # Normalize common vendor name variations
    vendor_mappings = {
        r'TH\s+STREET\s+LIQUOR': 'LIQUOR BARN',  # "67TH" became "TH" after removing "67"
        r'67TH\s+STREET\s+LIQUOR': 'LIQUOR BARN',
        r'LIQUOR BARN': 'LIQUOR BARN',
        r'LB\s+67TH': 'LIQUOR BARN',
        r'CENTEX': 'CENTEX',
        r'PLAZA LIQUOR TOWN': 'PLAZA LIQUOR STORE',
        r'WHOLESALE CL': 'REAL CANADIAN SUPERSTORE',
        r"GEORGE'?S PIZZA": 'GEORGIOS PIZZA',
        r'GEORGIOS PIZZA': 'GEORGIOS PIZZA',
        r'BEST BUY': 'BEST BUY',
        r'CANADIAN\s+TIRE': 'CANADIAN TIRE',
        r'SOBEY': 'SOBEYS',
        r'SHELL': 'SHELL',
    }
    
    for pattern, replacement in vendor_mappings.items():
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    
    # Remove trailing ellipsis and dots
    normalized = re.sub(r'\s*\.+\s*$', '', normalized)
    
    # Collapse multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized

def create_transaction_key(date, vendor, amount):
    """Create unique key for transaction matching."""
    normalized_vendor = normalize_vendor(vendor)
    return f"{date}|{normalized_vendor}|{amount}"

def fuzzy_match_vendor(vendor1, vendor2, threshold=0.8):
    """
    Check if two vendor names are similar using fuzzy matching.
    Returns similarity ratio (0.0 to 1.0).
    """
    from difflib import SequenceMatcher
    
    # Normalize both
    v1 = normalize_vendor(vendor1)
    v2 = normalize_vendor(vendor2)
    
    # Exact match after normalization
    if v1 == v2:
        return 1.0
    
    # Calculate similarity ratio
    ratio = SequenceMatcher(None, v1, v2).ratio()
    
    return ratio if ratio >= threshold else 0.0

def compare_transactions(csv_txns, db_txns):
    """Compare CSV and database transactions."""
    print("\n" + "=" * 80)
    print("COMPARISON ANALYSIS")
    print("=" * 80)
    
    # Build lookup dictionaries
    csv_by_date_amount = defaultdict(list)
    db_by_date_amount = defaultdict(list)
    
    for txn in csv_txns:
        csv_by_date_amount[f"{txn['date']}|{txn['amount']}"].append(txn)
    
    for txn in db_txns:
        db_by_date_amount[f"{txn['date']}|{txn['amount']}"].append(txn)
    
    # Find matches
    exact_matches = []
    fuzzy_matches = []
    csv_not_in_db = []
    db_not_in_csv = []
    
    # First, count all date+amount matches regardless of vendor
    print("\n1. Counting exact date+amount matches (regardless of vendor)...")
    date_amt_match_count = 0
    for date_amt_key in csv_by_date_amount.keys():
        if date_amt_key in db_by_date_amount:
            # Count the minimum of CSV and DB transactions for this date+amount
            csv_count = len(csv_by_date_amount[date_amt_key])
            db_count = len(db_by_date_amount[date_amt_key])
            date_amt_match_count += min(csv_count, db_count)
    
    print(f"   Date+Amount matches: {date_amt_match_count} potential pairs")
    
    print("\n2. Analyzing date+amount matches with fuzzy vendor matching...")
    
    matched_csv = set()
    matched_db = set()
    
    for date_amt_key, csv_txn_list in csv_by_date_amount.items():
        if date_amt_key in db_by_date_amount:
            db_txn_list = db_by_date_amount[date_amt_key]
            
            # Try to match each CSV transaction to a DB transaction
            for csv_txn in csv_txn_list:
                best_match = None
                best_ratio = 0.0
                
                for db_txn in db_txn_list:
                    db_id = id(db_txn)
                    if db_id in matched_db:
                        continue  # Already matched
                    
                    ratio = fuzzy_match_vendor(csv_txn['vendor'], db_txn['description'])
                    
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_match = db_txn
                
                if best_match and best_ratio >= 0.6:  # Lower threshold for date+amount matches
                    csv_id = id(csv_txn)
                    db_id = id(best_match)
                    
                    matched_csv.add(csv_id)
                    matched_db.add(db_id)
                    
                    if best_ratio >= 0.9:
                        exact_matches.append({
                            'csv': csv_txn,
                            'db': best_match,
                            'similarity': best_ratio
                        })
                    else:
                        fuzzy_matches.append({
                            'csv': csv_txn,
                            'db': best_match,
                            'similarity': best_ratio
                        })
    
    print(f"   Exact/near-exact matches (similarity >= 90%): {len(exact_matches)}")
    print(f"   Fuzzy matches (similarity 60-89%): {len(fuzzy_matches)}")
    
    # Find CSV transactions not in database
    print("\n3. Finding CSV transactions missing from database...")
    for csv_txn in csv_txns:
        if id(csv_txn) not in matched_csv:
            csv_not_in_db.append(csv_txn)
    
    print(f"   CSV transactions NOT in database: {len(csv_not_in_db)}")
    
    # Find database transactions not in CSV
    print("\n4. Finding database transactions not in CSV...")
    for db_txn in db_txns:
        if id(db_txn) not in matched_db:
            db_not_in_csv.append(db_txn)
    
    print(f"   Database transactions NOT in CSV: {len(db_not_in_csv)}")
    
    # Summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    csv_total = len(csv_txns)
    db_total = len(db_txns)
    
    total_matches = len(exact_matches) + len(fuzzy_matches)
    
    print(f"\nConsolidated CSV:  {csv_total} transactions")
    print(f"Database:          {db_total} transactions")
    print(f"\nDate+Amount matches: {date_amt_match_count} pairs (regardless of vendor)")
    print(f"\nVendor-matched:    {total_matches} ({total_matches/csv_total*100:.1f}% of CSV)")
    print(f"  - Exact/near:    {len(exact_matches)} (>= 90% similarity)")
    print(f"  - Fuzzy:         {len(fuzzy_matches)} (60-89% similarity)")
    print(f"\nMissing from DB:   {len(csv_not_in_db)} transactions")
    print(f"Extra in DB:       {len(db_not_in_csv)} transactions")
    
    # Year breakdown for missing transactions
    print("\n" + "-" * 80)
    print("MISSING FROM DATABASE - BY YEAR")
    print("-" * 80)
    
    missing_by_year = defaultdict(lambda: {'count': 0, 'debits': Decimal('0'), 'credits': Decimal('0')})
    for txn in csv_not_in_db:
        year = txn['date'].year
        missing_by_year[year]['count'] += 1
        if txn['amount'] < 0:
            missing_by_year[year]['debits'] += abs(txn['amount'])
        else:
            missing_by_year[year]['credits'] += txn['amount']
    
    for year in sorted(missing_by_year.keys()):
        stats = missing_by_year[year]
        print(f"   {year}: {stats['count']:4d} transactions, "
              f"Debits: ${stats['debits']:>12,.2f}, Credits: ${stats['credits']:>12,.2f}")
    
    # Show sample of missing transactions
    print("\n" + "-" * 80)
    print("SAMPLE MISSING TRANSACTIONS (first 20)")
    print("-" * 80)
    
    for i, txn in enumerate(csv_not_in_db[:20], 1):
        print(f"{i:2d}. {txn['date']} | {txn['vendor'][:40]:40s} | ${txn['amount']:>10.2f}")
    
    # Show sample of extra database transactions
    if db_not_in_csv:
        print("\n" + "-" * 80)
        print("SAMPLE EXTRA DATABASE TRANSACTIONS (first 20)")
        print("-" * 80)
        
        for i, txn in enumerate(db_not_in_csv[:20], 1):
            print(f"{i:2d}. {txn['date']} | {txn['description'][:40]:40s} | ${txn['amount']:>10.2f}")
    
    # Show sample of fuzzy matches
    if fuzzy_matches:
        print("\n" + "-" * 80)
        print("SAMPLE FUZZY MATCHES (first 20)")
        print("-" * 80)
        
        for i, match in enumerate(fuzzy_matches[:20], 1):
            csv_txn = match['csv']
            db_txn = match['db']
            similarity = match['similarity']
            print(f"{i:2d}. {csv_txn['date']} | ${csv_txn['amount']:>10.2f} | Similarity: {similarity:.1%}")
            print(f"    CSV: {csv_txn['vendor'][:60]}")
            print(f"    DB:  {db_txn['description'][:60]}")
            print()
    
    # Show ALL vendor mismatches (date+amount match, vendor doesn't)
    print("\n" + "=" * 80)
    print("ALL VENDOR MISMATCHES (Date+Amount match, vendor differs)")
    print("=" * 80)
    
    vendor_mismatches = []
    
    for date_amt_key, csv_txn_list in csv_by_date_amount.items():
        if date_amt_key in db_by_date_amount:
            db_txn_list = db_by_date_amount[date_amt_key]
            
            for csv_txn in csv_txn_list:
                for db_txn in db_txn_list:
                    # Check if they're not already matched
                    csv_id = id(csv_txn)
                    db_id = id(db_txn)
                    
                    if csv_id not in matched_csv and db_id not in matched_db:
                        vendor_mismatches.append({
                            'date': csv_txn['date'],
                            'amount': csv_txn['amount'],
                            'csv_vendor': csv_txn['vendor'],
                            'db_vendor': db_txn['description'],
                            'csv_normalized': normalize_vendor(csv_txn['vendor']),
                            'db_normalized': normalize_vendor(db_txn['description'])
                        })
    
    if vendor_mismatches:
        print(f"\nFound {len(vendor_mismatches)} date+amount pairs with vendor mismatches:\n")
        
        # Categorize mismatches
        cheque_payments = []
        wrong_vendors = []
        normalization_issues = []
        
        for mismatch in vendor_mismatches:
            db_vendor = mismatch['db_vendor'].upper()
            csv_vendor = mismatch['csv_vendor']
            
            # Extract cheque number if present
            import re
            cheque_match = re.search(r'CHQ\s+(\d+)(?:\s+(\d+))?', db_vendor, re.IGNORECASE)
            
            if cheque_match:
                cheque_num = cheque_match.group(1)
                cheque_account = cheque_match.group(2) if cheque_match.group(2) else None
                mismatch['cheque_number'] = cheque_num
                mismatch['cheque_account'] = cheque_account
                mismatch['payee_name'] = csv_vendor
                cheque_payments.append(mismatch)
            elif 'CANADIAN TIRE' in db_vendor and 'SOBEY' in csv_vendor.upper():
                mismatch['note'] = 'Accepted as: Sobeys/Canadian Tire Gas Bar'
                normalization_issues.append(mismatch)
            elif 'TIM HORTON' in csv_vendor.upper() and 'LEASES' in db_vendor:
                mismatch['note'] = 'Accepted as: Tim Hortons/Leases St Station'
                normalization_issues.append(mismatch)
            elif 'PATTY' in csv_vendor.upper() and 'RESTAUR' in db_vendor:
                mismatch['note'] = 'Accepted as: Pattys Family/Red Deer Royal Restaurant'
                normalization_issues.append(mismatch)
            else:
                mismatch['note'] = 'Minor normalization differences'
                normalization_issues.append(mismatch)
        
        # Print cheque payments with detailed information
        if cheque_payments:
            print("=" * 80)
            print("CHEQUE PAYMENTS - Need Cheque Register Mapping")
            print("=" * 80)
            print("Format: Cheque #[number] → Payee Name")
            print()
            
            for i, mismatch in enumerate(cheque_payments, 1):
                cheque_info = f"Cheque #{mismatch['cheque_number']}"
                if mismatch['cheque_account']:
                    cheque_info += f" (Account: {mismatch['cheque_account']})"
                
                print(f"{i:2d}. {mismatch['date']} | ${mismatch['amount']:>10.2f}")
                print(f"    {cheque_info} → {mismatch['payee_name']}")
                print()
        
        # Print wrong vendors
        if wrong_vendors:
            print("=" * 80)
            print("DIFFERENT VENDORS - Possible Data Errors")
            print("=" * 80)
            
            for i, mismatch in enumerate(wrong_vendors, 1):
                print(f"{i:2d}. {mismatch['date']} | ${mismatch['amount']:>10.2f}")
                print(f"    CSV: {mismatch['csv_vendor']}")
                print(f"    DB:  {mismatch['db_vendor'][:70]}")
                print(f"    Note: {mismatch['note']}")
                print()
        
        # Print normalization issues
        if normalization_issues:
            print("=" * 80)
            print("NORMALIZATION ISSUES - Minor Differences")
            print("=" * 80)
            
            for i, mismatch in enumerate(normalization_issues, 1):
                print(f"{i:2d}. {mismatch['date']} | ${mismatch['amount']:>10.2f}")
                print(f"    CSV: {mismatch['csv_vendor']}")
                print(f"    DB:  {mismatch['db_vendor'][:70]}")
                print(f"    CSV Normalized: {mismatch['csv_normalized'][:60]}")
                print(f"    DB  Normalized: {mismatch['db_normalized'][:60]}")
                print()
    else:
        print("\nNo unmatched vendor mismatches found (all date+amount pairs either matched or unique).")
    
    print("=" * 80)
    
    return {
        'exact_matches': exact_matches,
        'fuzzy_matches': fuzzy_matches,
        'csv_not_in_db': csv_not_in_db,
        'db_not_in_csv': db_not_in_csv
    }

def main():
    print("=" * 80)
    print("DATABASE VS CONSOLIDATED CSV VERIFICATION")
    print("=" * 80)
    
    # Load data
    csv_transactions = load_consolidated_csv()
    db_transactions = load_database_transactions()
    
    # Compare
    results = compare_transactions(csv_transactions, db_transactions)
    
    print("\nVerification complete.")

if __name__ == '__main__':
    main()
