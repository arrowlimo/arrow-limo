#!/usr/bin/env python3
"""
Compare Scotia_Bank_2012_Full_Report.csv against banking_transactions table.
Verify all transactions are present and amounts match.
"""

import psycopg2
import csv
from datetime import datetime
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def parse_amount(amount_str):
    """Parse amount string to Decimal."""
    if not amount_str or amount_str.strip() == '':
        return Decimal('0.00')
    # Remove commas and convert
    clean = amount_str.replace(',', '').strip()
    return Decimal(clean)

def main():
    csv_file = r'l:\limo\reports\Scotia_Bank_2012_Full_Report.csv'
    
    print("=" * 80)
    print("SCOTIA BANK 2012 FULL REPORT vs DATABASE VERIFICATION")
    print("=" * 80)
    
    # Read CSV file
    csv_transactions = []
    with open(csv_file, 'r', encoding='utf-8-sig') as f:  # utf-8-sig strips BOM
        reader = csv.DictReader(f)
        for row in reader:
            csv_transactions.append({
                'transaction_id': row['Transaction ID'],
                'date': datetime.strptime(row['Date'], '%Y-%m-%d').date(),
                'account': row['Account Number'],
                'description': row['Description'],
                'debit': parse_amount(row['Debit Amount']),
                'credit': parse_amount(row['Credit Amount']),
                'balance': parse_amount(row['Running Balance']),
                'created_at': row['Created At']
            })
    
    print(f"\nCSV FILE SUMMARY:")
    print(f"  Total rows in CSV: {len(csv_transactions):,}")
    print(f"  Account number: {csv_transactions[0]['account'] if csv_transactions else 'N/A'}")
    print(f"  Date range: {csv_transactions[0]['date']} to {csv_transactions[-1]['date']}")
    
    total_csv_debits = sum(t['debit'] for t in csv_transactions)
    total_csv_credits = sum(t['credit'] for t in csv_transactions)
    print(f"  Total debits: ${total_csv_debits:,.2f}")
    print(f"  Total credits: ${total_csv_credits:,.2f}")
    print(f"  Net: ${(total_csv_credits - total_csv_debits):,.2f}")
    
    # Get database records
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            account_number,
            description,
            COALESCE(debit_amount, 0) as debit,
            COALESCE(credit_amount, 0) as credit,
            balance
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND transaction_date >= '2012-01-01'
        AND transaction_date < '2013-01-01'
        ORDER BY transaction_date, transaction_id
    """)
    
    db_transactions = []
    for row in cur.fetchall():
        db_transactions.append({
            'transaction_id': row[0],
            'date': row[1],
            'account': row[2],
            'description': row[3],
            'debit': Decimal(str(row[4])),
            'credit': Decimal(str(row[5])),
            'balance': Decimal(str(row[6])) if row[6] is not None else Decimal('0.00')
        })
    
    print(f"\nDATABASE SUMMARY:")
    print(f"  Total rows in DB: {len(db_transactions):,}")
    if db_transactions:
        print(f"  Date range: {db_transactions[0]['date']} to {db_transactions[-1]['date']}")
        total_db_debits = sum(t['debit'] for t in db_transactions)
        total_db_credits = sum(t['credit'] for t in db_transactions)
        print(f"  Total debits: ${total_db_debits:,.2f}")
        print(f"  Total credits: ${total_db_credits:,.2f}")
        print(f"  Net: ${(total_db_credits - total_db_debits):,.2f}")
    
    # Compare counts
    print(f"\nCOMPARISON:")
    if len(csv_transactions) == len(db_transactions):
        print(f"  ✓ Row count matches: {len(csv_transactions):,}")
    else:
        print(f"  ✗ Row count MISMATCH:")
        print(f"    CSV: {len(csv_transactions):,}")
        print(f"    DB:  {len(db_transactions):,}")
        print(f"    Difference: {abs(len(csv_transactions) - len(db_transactions)):,}")
    
    # Compare totals
    debit_diff = abs(total_csv_debits - total_db_debits)
    credit_diff = abs(total_csv_credits - total_db_credits)
    
    if debit_diff < Decimal('0.01'):
        print(f"  ✓ Debit totals match: ${total_csv_debits:,.2f}")
    else:
        print(f"  ✗ Debit totals MISMATCH:")
        print(f"    CSV: ${total_csv_debits:,.2f}")
        print(f"    DB:  ${total_db_debits:,.2f}")
        print(f"    Difference: ${debit_diff:,.2f}")
    
    if credit_diff < Decimal('0.01'):
        print(f"  ✓ Credit totals match: ${total_csv_credits:,.2f}")
    else:
        print(f"  ✗ Credit totals MISMATCH:")
        print(f"    CSV: ${total_csv_credits:,.2f}")
        print(f"    DB:  ${total_db_credits:,.2f}")
        print(f"    Difference: ${credit_diff:,.2f}")
    
    # Find missing/extra transactions
    csv_by_date_desc = {}
    for t in csv_transactions:
        key = (t['date'], t['description'][:50], t['debit'], t['credit'])
        if key not in csv_by_date_desc:
            csv_by_date_desc[key] = []
        csv_by_date_desc[key].append(t)
    
    db_by_date_desc = {}
    for t in db_transactions:
        key = (t['date'], t['description'][:50], t['debit'], t['credit'])
        if key not in db_by_date_desc:
            db_by_date_desc[key] = []
        db_by_date_desc[key].append(t)
    
    # Find transactions in CSV but not in DB
    missing_in_db = []
    for key, csv_txns in csv_by_date_desc.items():
        db_txns = db_by_date_desc.get(key, [])
        if len(csv_txns) > len(db_txns):
            missing_count = len(csv_txns) - len(db_txns)
            for i in range(missing_count):
                missing_in_db.append(csv_txns[i])
    
    # Find transactions in DB but not in CSV
    extra_in_db = []
    for key, db_txns in db_by_date_desc.items():
        csv_txns = csv_by_date_desc.get(key, [])
        if len(db_txns) > len(csv_txns):
            extra_count = len(db_txns) - len(csv_txns)
            for i in range(extra_count):
                extra_in_db.append(db_txns[i])
    
    if missing_in_db:
        print(f"\n⚠ MISSING IN DATABASE ({len(missing_in_db)} transactions):")
        for t in missing_in_db[:10]:  # Show first 10
            print(f"  {t['date']} | {t['description'][:40]} | D:${t['debit']:,.2f} C:${t['credit']:,.2f}")
        if len(missing_in_db) > 10:
            print(f"  ... and {len(missing_in_db) - 10} more")
    
    if extra_in_db:
        print(f"\n⚠ EXTRA IN DATABASE ({len(extra_in_db)} transactions):")
        for t in extra_in_db[:10]:  # Show first 10
            print(f"  {t['date']} | {t['description'][:40]} | D:${t['debit']:,.2f} C:${t['credit']:,.2f}")
        if len(extra_in_db) > 10:
            print(f"  ... and {len(extra_in_db) - 10} more")
    
    if not missing_in_db and not extra_in_db:
        print(f"\n✓ ALL TRANSACTIONS MATCH!")
        print(f"  CSV and database are in perfect sync.")
    
    # Monthly breakdown comparison
    print(f"\nMONTHLY BREAKDOWN:")
    print(f"  Month      CSV Rows  DB Rows   Match")
    print(f"  ------     --------  -------   -----")
    
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    for month_num in range(1, 13):
        csv_count = sum(1 for t in csv_transactions if t['date'].month == month_num)
        db_count = sum(1 for t in db_transactions if t['date'].month == month_num)
        match = "✓" if csv_count == db_count else "✗"
        print(f"  {months[month_num-1]:3} 2012   {csv_count:8,}  {db_count:7,}   {match}")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    main()
