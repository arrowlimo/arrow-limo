"""
Import Scotia Bank consolidated CSV into banking_transactions table.

This script:
1. Creates backup of existing banking_transactions for Scotia account
2. Updates 30 matched transactions with cleaner vendor names from CSV
3. Imports 2,023 missing transactions from consolidated CSV
4. Maps CSV columns to database schema with proper debit/credit split

Usage:
    python import_scotia_consolidated_to_banking.py --dry-run  # Preview changes
    python import_scotia_consolidated_to_banking.py --write    # Apply changes

Created: November 24, 2025
"""

import os
import csv
import psycopg2
import hashlib
import argparse
from datetime import datetime
from decimal import Decimal

# Database connection parameters
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

SCOTIA_ACCOUNT = '903990106011'

def create_backup(conn, cur):
    """Create timestamped backup of Scotia banking transactions."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'banking_transactions_scotia_backup_{timestamp}'
    
    print(f"\nCreating backup: {backup_table}")
    
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM banking_transactions
        WHERE account_number = %s
    """, (SCOTIA_ACCOUNT,))
    
    cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
    count = cur.fetchone()[0]
    
    print(f"   Backed up: {count} Scotia transactions")
    
    return backup_table

def generate_source_hash(date, description, amount):
    """Generate deterministic hash for transaction identification."""
    hash_input = f"{date}|{description}|{amount:.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def load_existing_transactions(cur):
    """Load existing Scotia transactions from database."""
    print("\nLoading existing database transactions...")
    
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            balance
        FROM banking_transactions
        WHERE account_number = %s
        ORDER BY transaction_date, transaction_id
    """, (SCOTIA_ACCOUNT,))
    
    existing = {}
    for row in cur.fetchall():
        txn_id = row[0]
        date = row[1]
        description = row[2] or ''
        debit = row[3] or Decimal('0')
        credit = row[4] or Decimal('0')
        balance = row[5] or Decimal('0')
        
        # Create lookup key
        amount = -debit if debit > 0 else credit
        key = f"{date}|{amount}"
        
        if key not in existing:
            existing[key] = []
        
        existing[key].append({
            'id': txn_id,
            'description': description,
            'debit': debit,
            'credit': credit,
            'balance': balance
        })
    
    print(f"   Loaded: {len(existing)} unique date+amount pairs")
    
    return existing

def load_consolidated_csv():
    """Load consolidated CSV with all Scotia transactions."""
    csv_path = r'L:\limo\data\scotia_consolidated_all_years.csv'
    
    print(f"\nLoading consolidated CSV: {csv_path}")
    
    transactions = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = datetime.strptime(row['date'], '%Y-%m-%d').date()
            amount = Decimal(row['amount'])
            
            transactions.append({
                'date': date,
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

def update_matched_transactions(cur, existing, csv_txns, dry_run=True):
    """Update the 30 matched transactions with cleaner vendor names from CSV."""
    print("\n" + "=" * 80)
    print("STEP 1: UPDATE MATCHED TRANSACTIONS WITH CLEANER VENDOR NAMES")
    print("=" * 80)
    
    updates = []
    
    # Build CSV lookup by date+amount
    csv_by_key = {}
    for txn in csv_txns:
        key = f"{txn['date']}|{txn['amount']}"
        if key not in csv_by_key:
            csv_by_key[key] = []
        csv_by_key[key].append(txn)
    
    # Find matches
    for key, csv_list in csv_by_key.items():
        if key in existing:
            db_list = existing[key]
            
            # Match first CSV to first DB (simple pairing)
            for csv_txn in csv_list:
                for db_txn in db_list:
                    # Check if vendor name is cleaner in CSV
                    csv_vendor = csv_txn['vendor']
                    db_desc = db_txn['description']
                    
                    # CSV has cleaner names if it doesn't have transaction type prefixes
                    if not any(prefix in db_desc.upper() for prefix in ['POINT OF SALE', 'CHQ', 'CHEQUE', 'DEBIT MEMO']):
                        continue  # DB already has clean name
                    
                    updates.append({
                        'transaction_id': db_txn['id'],
                        'old_description': db_desc,
                        'new_description': csv_vendor,
                        'date': csv_txn['date'],
                        'amount': csv_txn['amount']
                    })
                    
                    break  # Only match once
                break  # Move to next key
    
    print(f"\nFound {len(updates)} transactions to update with cleaner vendor names")
    
    if updates and not dry_run:
        print("\nApplying updates...")
        for i, update in enumerate(updates, 1):
            cur.execute("""
                UPDATE banking_transactions
                SET description = %s
                WHERE transaction_id = %s
            """, (update['new_description'], update['transaction_id']))
            
            if i <= 10:  # Show first 10
                print(f"   {i}. {update['date']} | ${update['amount']:>10.2f}")
                print(f"      Old: {update['old_description'][:60]}")
                print(f"      New: {update['new_description'][:60]}")
    
    elif updates:
        print("\nDRY RUN - Would update:")
        for i, update in enumerate(updates[:10], 1):
            print(f"   {i}. {update['date']} | ${update['amount']:>10.2f}")
            print(f"      Old: {update['old_description'][:60]}")
            print(f"      New: {update['new_description'][:60]}")
        
        if len(updates) > 10:
            print(f"   ... and {len(updates) - 10} more")
    
    return len(updates)

def import_missing_transactions(cur, existing, csv_txns, dry_run=True):
    """Import missing transactions from CSV into banking_transactions."""
    print("\n" + "=" * 80)
    print("STEP 2: IMPORT MISSING TRANSACTIONS")
    print("=" * 80)
    
    # Build existing lookup
    existing_keys = set()
    for key in existing.keys():
        existing_keys.add(key)
    
    # Find missing
    missing = []
    for txn in csv_txns:
        key = f"{txn['date']}|{txn['amount']}"
        if key not in existing_keys:
            missing.append(txn)
    
    print(f"\nFound {len(missing)} transactions to import")
    
    # Year breakdown
    from collections import defaultdict
    by_year = defaultdict(lambda: {'count': 0, 'debits': Decimal('0'), 'credits': Decimal('0')})
    
    for txn in missing:
        year = txn['date'].year
        by_year[year]['count'] += 1
        if txn['amount'] < 0:
            by_year[year]['debits'] += abs(txn['amount'])
        else:
            by_year[year]['credits'] += txn['amount']
    
    print("\nMissing by year:")
    for year in sorted(by_year.keys()):
        stats = by_year[year]
        print(f"   {year}: {stats['count']:4d} transactions, "
              f"Debits: ${stats['debits']:>12,.2f}, Credits: ${stats['credits']:>12,.2f}")
    
    if missing and not dry_run:
        print("\nImporting transactions...")
        imported = 0
        
        for txn in missing:
            # Split amount into debit/credit
            if txn['amount'] < 0:
                debit = abs(txn['amount'])
                credit = Decimal('0')
            else:
                debit = Decimal('0')
                credit = txn['amount']
            
            # Generate source hash
            source_hash = generate_source_hash(txn['date'], txn['vendor'], txn['amount'])
            
            # Insert (without ON CONFLICT since source_hash doesn't have unique constraint)
            cur.execute("""
                INSERT INTO banking_transactions (
                    account_number,
                    transaction_date,
                    description,
                    debit_amount,
                    credit_amount,
                    balance,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """, (
                SCOTIA_ACCOUNT,
                txn['date'],
                txn['vendor'],
                debit,
                credit,
                txn['balance']
            ))
            
            if cur.rowcount > 0:
                imported += 1
        
        print(f"\nImported: {imported} new transactions")
        
        return imported
    
    elif missing:
        print("\nDRY RUN - Would import:")
        for i, txn in enumerate(missing[:20], 1):
            print(f"   {i}. {txn['date']} | {txn['vendor'][:50]} | ${txn['amount']:>10.2f}")
        
        if len(missing) > 20:
            print(f"   ... and {len(missing) - 20} more")
    
    return 0

def verify_import(cur):
    """Verify the import completed successfully."""
    print("\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            MIN(transaction_date) as first_date,
            MAX(transaction_date) as last_date,
            SUM(debit_amount) as total_debits,
            SUM(credit_amount) as total_credits
        FROM banking_transactions
        WHERE account_number = %s
    """, (SCOTIA_ACCOUNT,))
    
    row = cur.fetchone()
    print(f"\nScotia Bank Account {SCOTIA_ACCOUNT}:")
    print(f"   Total transactions: {row[0]}")
    print(f"   Date range: {row[1]} to {row[2]}")
    print(f"   Total debits: ${row[3]:,.2f}")
    print(f"   Total credits: ${row[4]:,.2f}")
    
    # Compare to CSV
    print(f"\nExpected from CSV: 2,053 transactions")
    print(f"   Difference: {row[0] - 2053} transactions")
    
    if row[0] >= 2053:
        print("\n✅ SUCCESS: All consolidated transactions imported")
    else:
        print(f"\n⚠️ WARNING: Missing {2053 - row[0]} transactions")

def main():
    parser = argparse.ArgumentParser(description='Import Scotia consolidated CSV to banking_transactions')
    parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
    args = parser.parse_args()
    
    dry_run = not args.write
    
    print("=" * 80)
    print("SCOTIA CONSOLIDATED CSV IMPORT")
    print("=" * 80)
    
    if dry_run:
        print("\n🔍 DRY RUN MODE - No changes will be made")
        print("   Use --write to apply changes")
    else:
        print("\n✍️  WRITE MODE - Changes will be applied")
    
    # Connect to database
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    try:
        # Create backup
        if not dry_run:
            backup_table = create_backup(conn, cur)
            conn.commit()
        
        # Load data
        existing = load_existing_transactions(cur)
        csv_txns = load_consolidated_csv()
        
        # Step 1: Update matched transactions
        updated = update_matched_transactions(cur, existing, csv_txns, dry_run)
        
        # Step 2: Import missing transactions
        imported = import_missing_transactions(cur, existing, csv_txns, dry_run)
        
        # Commit changes
        if not dry_run:
            conn.commit()
            print("\n✅ Changes committed to database")
            
            # Verify
            verify_import(cur)
        else:
            print("\n🔍 DRY RUN - No changes made")
            print(f"\nSummary:")
            print(f"   Would update: {updated} transactions")
            
            # Count missing
            missing_count = 0
            for txn in csv_txns:
                key = f"{txn['date']}|{txn['amount']}"
                if key not in existing:
                    missing_count += 1
            
            print(f"   Would import: {missing_count} transactions")
    
    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERROR: {e}")
        raise
    
    finally:
        cur.close()
        conn.close()
    
    print("\n" + "=" * 80)
    print("Import complete.")
    print("=" * 80)

if __name__ == '__main__':
    main()
