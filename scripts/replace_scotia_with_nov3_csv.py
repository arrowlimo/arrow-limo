#!/usr/bin/env python3
"""
Replace Scotia Bank 2012 database data with authoritative Nov 3 CSV report.
The CSV has 786 transactions with proper balances.
The database has 791 rows from Nov 6 with incorrect totals.
"""

import psycopg2
import csv
from datetime import datetime
from decimal import Decimal
import hashlib

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def generate_hash(date, description, amount):
    """Generate deterministic hash for deduplication."""
    hash_input = f"{date}|{description}|{amount:.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

def parse_amount(amount_str):
    """Parse amount string to Decimal."""
    if not amount_str or amount_str.strip() == '':
        return Decimal('0.00')
    clean = amount_str.replace(',', '').strip()
    return Decimal(clean)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Replace Scotia Bank 2012 data with Nov 3 CSV')
    parser.add_argument('--write', action='store_true', help='Actually apply changes (default is dry-run)')
    parser.add_argument('--backup', action='store_true', help='Create backup table before deletion')
    args = parser.parse_args()
    
    csv_file = r'l:\limo\reports\Scotia_Bank_2012_Full_Report.csv'
    
    print("=" * 80)
    print("SCOTIA BANK 2012 - REPLACE DATABASE WITH NOV 3 CSV")
    print("=" * 80)
    
    # Read CSV file
    csv_transactions = []
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = datetime.strptime(row['Date'], '%Y-%m-%d').date()
            debit = parse_amount(row['Debit Amount'])
            credit = parse_amount(row['Credit Amount'])
            balance = parse_amount(row['Running Balance'])
            description = row['Description'].strip()
            
            csv_transactions.append({
                'date': date,
                'account': row['Account Number'],
                'description': description,
                'debit': debit,
                'credit': credit,
                'balance': balance,
                'source_hash': generate_hash(date, description, debit + credit)
            })
    
    print(f"\nCSV FILE:")
    print(f"  Transactions: {len(csv_transactions):,}")
    print(f"  Date range: {csv_transactions[0]['date']} to {csv_transactions[-1]['date']}")
    total_debits = sum(t['debit'] for t in csv_transactions)
    total_credits = sum(t['credit'] for t in csv_transactions)
    print(f"  Total debits: ${total_debits:,.2f}")
    print(f"  Total credits: ${total_credits:,.2f}")
    print(f"  Net: ${(total_credits - total_debits):,.2f}")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check current database
    cur.execute("""
        SELECT COUNT(*), 
               SUM(COALESCE(debit_amount, 0)), 
               SUM(COALESCE(credit_amount, 0))
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND transaction_date >= '2012-01-01' AND transaction_date < '2013-01-01'
    """)
    
    db_count, db_debits, db_credits = cur.fetchone()
    
    print(f"\nCURRENT DATABASE:")
    print(f"  Transactions: {db_count:,}")
    print(f"  Total debits: ${float(db_debits):,.2f}")
    print(f"  Total credits: ${float(db_credits):,.2f}")
    print(f"  Net: ${(float(db_credits) - float(db_debits)):,.2f}")
    
    if args.write:
        print(f"\n{'=' * 80}")
        print("APPLYING CHANGES...")
        print("=" * 80)
        
        # Create backup if requested
        if args.backup:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_table = f'scotia_2012_backup_{timestamp}'
            
            print(f"\nCreating backup table: {backup_table}")
            cur.execute(f"""
                CREATE TABLE {backup_table} AS
                SELECT * FROM banking_transactions
                WHERE account_number = '903990106011'
                AND transaction_date >= '2012-01-01' AND transaction_date < '2013-01-01'
            """)
            conn.commit()
            print(f"  ✓ Backed up {db_count:,} rows to {backup_table}")
        
        # Delete existing Scotia 2012 data
        print(f"\nDeleting existing Scotia 2012 transactions...")
        cur.execute("""
            DELETE FROM banking_transactions
            WHERE account_number = '903990106011'
            AND transaction_date >= '2012-01-01' AND transaction_date < '2013-01-01'
        """)
        deleted_count = cur.rowcount
        print(f"  ✓ Deleted {deleted_count:,} rows")
        
        # Insert CSV data
        print(f"\nInserting {len(csv_transactions):,} transactions from CSV...")
        inserted = 0
        for t in csv_transactions:
            cur.execute("""
                INSERT INTO banking_transactions (
                    transaction_date, account_number, description,
                    debit_amount, credit_amount, balance, source_hash, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (
                t['date'], t['account'], t['description'],
                t['debit'], t['credit'], t['balance'], t['source_hash']
            ))
            inserted += 1
            
            if inserted % 100 == 0:
                print(f"  Inserted {inserted}/{len(csv_transactions)}...")
        
        conn.commit()
        print(f"  ✓ Inserted {inserted:,} rows")
        
        # Verify new data
        cur.execute("""
            SELECT COUNT(*), 
                   SUM(COALESCE(debit_amount, 0)), 
                   SUM(COALESCE(credit_amount, 0))
            FROM banking_transactions
            WHERE account_number = '903990106011'
            AND transaction_date >= '2012-01-01' AND transaction_date < '2013-01-01'
        """)
        
        new_count, new_debits, new_credits = cur.fetchone()
        
        print(f"\nNEW DATABASE STATE:")
        print(f"  Transactions: {new_count:,}")
        print(f"  Total debits: ${float(new_debits):,.2f}")
        print(f"  Total credits: ${float(new_credits):,.2f}")
        print(f"  Net: ${(float(new_credits) - float(new_debits)):,.2f}")
        
        # Verify match
        if new_count == len(csv_transactions):
            print(f"\n✓ SUCCESS: Row counts match!")
        else:
            print(f"\n✗ WARNING: Row count mismatch!")
            print(f"  Expected: {len(csv_transactions):,}")
            print(f"  Got: {new_count:,}")
        
        debit_diff = abs(total_debits - Decimal(str(new_debits)))
        credit_diff = abs(total_credits - Decimal(str(new_credits)))
        
        if debit_diff < Decimal('0.01') and credit_diff < Decimal('0.01'):
            print(f"✓ SUCCESS: Amounts match!")
        else:
            print(f"✗ WARNING: Amount mismatch!")
            print(f"  Debit diff: ${debit_diff:,.2f}")
            print(f"  Credit diff: ${credit_diff:,.2f}")
        
    else:
        print(f"\n{'=' * 80}")
        print("DRY-RUN MODE - No changes made")
        print("=" * 80)
        print(f"\nTo apply changes, run with --write flag:")
        print(f"  python {__file__} --write --backup")
        print(f"\nThis will:")
        print(f"  1. Create backup table (if --backup flag used)")
        print(f"  2. Delete {db_count:,} existing Scotia 2012 transactions")
        print(f"  3. Insert {len(csv_transactions):,} transactions from Nov 3 CSV")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    main()
