"""
Parse January 2012 manual verification and import missing/corrected transactions.
"""
import psycopg2
from datetime import datetime
import hashlib

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("=" * 80)
print("PARSING JANUARY 2012 MANUAL VERIFICATION")
print("=" * 80)

# Parse manual verification file
manual_txns = []

with open('l:/limo/reports/2012_cibc_complete_running_balance_verification.md', encoding='utf-8') as f:
    content = f.read()
    
    # Extract January section only
    jan_section = content.split('## February 2012')[0] if '## February 2012' in content else content
    jan_section = jan_section.split('## January 2012')[1] if '## January 2012' in jan_section else jan_section
    
    # Parse table rows
    lines = jan_section.split('\n')
    current_date = None
    
    for line in lines:
        if '|' in line and ('[OK]' in line or '[WARN]' in line):
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 7:
                try:
                    date_str = parts[1]
                    description = parts[2]
                    txn_type = parts[3]
                    amount_str = parts[4].replace('$', '').replace(',', '').replace('-', '').strip()
                    balance_str = parts[6].replace('$', '').replace(',', '').strip()
                    
                    # Parse date
                    if date_str and date_str != 'Date' and date_str != '---':
                        if 'Jan' in date_str:
                            day = date_str.replace('Jan ', '').strip()
                            if day.isdigit():
                                current_date = f"2012-01-{int(day):02d}"
                        elif 'Feb' in date_str:
                            day = date_str.replace('Feb ', '').strip()
                            if day.isdigit():
                                current_date = f"2012-02-{int(day):02d}"
                    
                    # Parse amount and balance
                    if amount_str and balance_str and current_date and txn_type in ['W', 'D']:
                        amount = float(amount_str)
                        balance = float(balance_str)
                        
                        debit = amount if txn_type == 'W' else None
                        credit = amount if txn_type == 'D' else None
                        
                        manual_txns.append({
                            'date': current_date,
                            'description': description,
                            'debit': debit,
                            'credit': credit,
                            'balance': balance
                        })
                except (ValueError, IndexError) as e:
                    continue

print(f"[OK] Parsed {len(manual_txns)} verified transactions")

# Generate hash for each transaction for duplicate detection
for txn in manual_txns:
    hash_str = f"{txn['date']}|{txn['description']}|{txn['debit'] or 0}|{txn['credit'] or 0}|{txn['balance']}"
    txn['hash'] = hashlib.sha256(hash_str.encode()).hexdigest()[:16]

# Get existing database transactions
cur.execute("""
    SELECT 
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance,
        transaction_id
    FROM banking_transactions
    WHERE transaction_date >= '2012-01-01' AND transaction_date <= '2012-01-31'
    ORDER BY transaction_date, transaction_id
""")

db_txns = []
for date, desc, debit, credit, balance, txn_id in cur.fetchall():
    hash_str = f"{date}|{desc or ''}|{debit or 0}|{credit or 0}|{balance or 0}"
    db_txns.append({
        'id': txn_id,
        'date': str(date),
        'description': desc or '',
        'debit': float(debit or 0),
        'credit': float(credit or 0),
        'balance': float(balance or 0),
        'hash': hashlib.sha256(hash_str.encode()).hexdigest()[:16]
    })

print(f"[OK] Loaded {len(db_txns)} existing database transactions")

# Find transactions to insert (in manual but not in DB)
to_insert = []
db_hashes = {t['hash'] for t in db_txns}

for manual_txn in manual_txns:
    if manual_txn['hash'] not in db_hashes:
        # Also check by date + amount (in case description differs slightly)
        found = False
        for db_txn in db_txns:
            if (db_txn['date'] == manual_txn['date'] and 
                abs((db_txn['debit'] or 0) - (manual_txn['debit'] or 0)) < 0.01 and
                abs((db_txn['credit'] or 0) - (manual_txn['credit'] or 0)) < 0.01 and
                abs(db_txn['balance'] - manual_txn['balance']) < 0.01):
                found = True
                break
        
        if not found:
            to_insert.append(manual_txn)

# Find transactions to update (in DB but balance/amount wrong)
to_update = []
for db_txn in db_txns:
    for manual_txn in manual_txns:
        if (db_txn['date'] == manual_txn['date'] and 
            db_txn['description'].strip() == manual_txn['description'].strip()):
            # Check if amounts or balance differ
            if (abs((db_txn['debit'] or 0) - (manual_txn['debit'] or 0)) > 0.01 or
                abs((db_txn['credit'] or 0) - (manual_txn['credit'] or 0)) > 0.01 or
                abs(db_txn['balance'] - manual_txn['balance']) > 0.01):
                to_update.append({
                    'id': db_txn['id'],
                    'manual': manual_txn,
                    'db': db_txn
                })

print("\n" + "=" * 80)
print("CHANGES REQUIRED")
print("=" * 80)
print(f"\nTransactions to INSERT: {len(to_insert)}")
print(f"Transactions to UPDATE: {len(to_update)}")

if to_insert:
    print(f"\n{'Date':<12} {'Type':<6} {'Amount':>12} {'Balance':>12} {'Description':<40}")
    print("-" * 80)
    for txn in to_insert[:10]:
        txn_type = 'W' if txn['debit'] else 'D'
        amount = txn['debit'] or txn['credit']
        print(f"{txn['date']:<12} {txn_type:<6} ${amount:>10,.2f} ${txn['balance']:>10,.2f} {txn['description'][:39]}")
    if len(to_insert) > 10:
        print(f"... and {len(to_insert) - 10} more")

if to_update:
    print(f"\n{'Date':<12} {'Description':<30} {'Field':<10} {'DB Value':>12} {'Should Be':>12}")
    print("-" * 80)
    for item in to_update[:10]:
        print(f"{item['db']['date']:<12} {item['db']['description'][:29]:<30} "
              f"{'balance':<10} ${item['db']['balance']:>10,.2f} ${item['manual']['balance']:>10,.2f}")
    if len(to_update) > 10:
        print(f"... and {len(to_update) - 10} more")

print("\n" + "=" * 80)
print("READY TO APPLY? (DRY RUN)")
print("=" * 80)
print("\nThis script will:")
print(f"1. Create backup: banking_transactions_jan2012_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
print(f"2. INSERT {len(to_insert)} new transactions from manual verification")
print(f"3. UPDATE {len(to_update)} existing transactions with corrected values")
print(f"4. Verify final count matches manual verification ({len(manual_txns)} transactions)")
print("\nTo apply changes, run with: --write")

# Check if --write flag
import sys
if '--write' in sys.argv:
    print("\n" + "=" * 80)
    print("APPLYING CHANGES")
    print("=" * 80)
    
    # Create backup
    backup_name = f"banking_transactions_jan2012_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"\nCreating backup: {backup_name}")
    cur.execute(f"""
        CREATE TABLE {backup_name} AS 
        SELECT * FROM banking_transactions 
        WHERE transaction_date >= '2012-01-01' AND transaction_date <= '2012-01-31'
    """)
    conn.commit()
    print(f"[OK] Backed up {len(db_txns)} transactions")
    
    # Insert new transactions
    if to_insert:
        print(f"\nInserting {len(to_insert)} new transactions...")
        for txn in to_insert:
            cur.execute("""
                INSERT INTO banking_transactions 
                (transaction_date, description, debit_amount, credit_amount, balance, account_number)
                VALUES (%s, %s, %s, %s, %s, '0228362')
            """, (txn['date'], txn['description'], txn['debit'], txn['credit'], txn['balance']))
        conn.commit()
        print(f"[OK] Inserted {len(to_insert)} transactions")
    
    # Update existing transactions
    if to_update:
        print(f"\nUpdating {len(to_update)} transactions...")
        for item in to_update:
            cur.execute("""
                UPDATE banking_transactions
                SET debit_amount = %s, credit_amount = %s, balance = %s
                WHERE transaction_id = %s
            """, (item['manual']['debit'], item['manual']['credit'], 
                  item['manual']['balance'], item['id']))
        conn.commit()
        print(f"[OK] Updated {len(to_update)} transactions")
    
    # Verify
    cur.execute("""
        SELECT COUNT(*) 
        FROM banking_transactions
        WHERE transaction_date >= '2012-01-01' AND transaction_date <= '2012-01-31'
    """)
    final_count = cur.fetchone()[0]
    
    print("\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    print(f"Manual verification: {len(manual_txns)} transactions")
    print(f"Database after update: {final_count} transactions")
    print(f"Status: {'[OK] MATCH' if final_count == len(manual_txns) else '[WARN] COUNT MISMATCH'}")

cur.close()
conn.close()
