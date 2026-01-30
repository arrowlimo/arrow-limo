"""
Parse and import February 2012 manual verification data.
Similar to January process - validates opening/closing balances.
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
print("FEBRUARY 2012 MANUAL VERIFICATION IMPORT")
print("=" * 80)

# Expected boundaries
EXPECTED_OPENING = -49.17  # Jan 31 closing
EXPECTED_CLOSING = 1014.49  # Feb 29 closing

# Parse manual verification file
manual_txns = []

try:
    with open('l:/limo/reports/2012_cibc_complete_running_balance_verification.md', encoding='utf-8') as f:
        content = f.read()
        
        # Extract February section
        if '## February 2012' in content:
            feb_section = content.split('## February 2012')[1]
            if '## March 2012' in feb_section:
                feb_section = feb_section.split('## March 2012')[0]
            elif '##' in feb_section:
                feb_section = feb_section.split('##')[0]
            
            # Parse table rows
            lines = feb_section.split('\n')
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
                                if 'Feb' in date_str:
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
                        except (ValueError, IndexError):
                            continue
            
            if manual_txns:
                print(f"[OK] Parsed {len(manual_txns)} verified February transactions")
                
                # Verify boundaries
                first = manual_txns[0]
                last = manual_txns[-1]
                
                print(f"\nFirst transaction: {first['date']} - Balance ${first['balance']:,.2f}")
                print(f"Last transaction: {last['date']} - Balance ${last['balance']:,.2f}")
                
                opening_match = abs(first['balance'] - EXPECTED_OPENING) < 0.01
                closing_match = abs(last['balance'] - EXPECTED_CLOSING) < 0.01
                
                print(f"\nOpening balance: {'[OK] MATCH' if opening_match else f'[WARN] Expected ${EXPECTED_OPENING:.2f}'}")
                print(f"Closing balance: {'[OK] MATCH' if closing_match else f'[WARN] Expected ${EXPECTED_CLOSING:.2f}'}")
                
                # Generate hashes
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
                    WHERE transaction_date >= '2012-02-01' AND transaction_date <= '2012-02-29'
                    ORDER BY transaction_date, transaction_id
                """)
                
                db_txns = []
                for date, desc, debit, credit, balance, txn_id in cur.fetchall():
                    db_txns.append({
                        'id': txn_id,
                        'date': str(date),
                        'description': desc or '',
                        'debit': float(debit or 0),
                        'credit': float(credit or 0),
                        'balance': float(balance or 0)
                    })
                
                print(f"\n[OK] Loaded {len(db_txns)} existing database transactions")
                
                # Find what needs updating
                to_update = []
                for manual_txn in manual_txns:
                    # Find matching DB transaction by date and amount
                    for db_txn in db_txns:
                        if (db_txn['date'] == manual_txn['date'] and
                            abs((db_txn['debit'] or 0) - (manual_txn['debit'] or 0)) < 0.01 and
                            abs((db_txn['credit'] or 0) - (manual_txn['credit'] or 0)) < 0.01):
                            # Check if balance needs update
                            if abs(db_txn['balance'] - manual_txn['balance']) > 0.01:
                                to_update.append({
                                    'id': db_txn['id'],
                                    'date': manual_txn['date'],
                                    'description': manual_txn['description'],
                                    'old_balance': db_txn['balance'],
                                    'new_balance': manual_txn['balance']
                                })
                            break
                
                print(f"\n{'='*80}")
                print("CHANGES REQUIRED")
                print("=" * 80)
                print(f"\nTransactions needing balance updates: {len(to_update)}")
                
                if to_update:
                    print(f"\n{'Date':<12} {'Old Balance':>12} {'New Balance':>12} {'Description':<40}")
                    print("-" * 80)
                    for upd in to_update[:20]:
                        print(f"{upd['date']:<12} ${upd['old_balance']:>10,.2f} ${upd['new_balance']:>10,.2f} {upd['description'][:39]}")
                    if len(to_update) > 20:
                        print(f"... and {len(to_update) - 20} more")
                
                print("\nTo apply changes, run with: --write")
                
                # Apply if --write flag
                import sys
                if '--write' in sys.argv:
                    print("\n" + "=" * 80)
                    print("APPLYING CHANGES")
                    print("=" * 80)
                    
                    # Create backup
                    backup_name = f"banking_transactions_feb2012_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    print(f"\nCreating backup: {backup_name}")
                    cur.execute(f"""
                        CREATE TABLE {backup_name} AS 
                        SELECT * FROM banking_transactions 
                        WHERE transaction_date >= '2012-02-01' AND transaction_date <= '2012-02-29'
                    """)
                    conn.commit()
                    print(f"[OK] Backed up {len(db_txns)} transactions")
                    
                    # Update balances
                    if to_update:
                        print(f"\nUpdating {len(to_update)} transaction balances...")
                        for upd in to_update:
                            cur.execute("""
                                UPDATE banking_transactions
                                SET balance = %s
                                WHERE transaction_id = %s
                            """, (upd['new_balance'], upd['id']))
                        conn.commit()
                        print(f"[OK] Updated {len(to_update)} balances")
                    
                    # Verify
                    cur.execute("""
                        SELECT transaction_date, balance
                        FROM banking_transactions
                        WHERE transaction_date = '2012-02-29'
                        ORDER BY transaction_id DESC
                        LIMIT 1
                    """)
                    final = cur.fetchone()
                    
                    print("\n" + "=" * 80)
                    print("VERIFICATION")
                    print("=" * 80)
                    print(f"Feb 29 closing balance: ${final[1]:,.2f}")
                    print(f"Expected: ${EXPECTED_CLOSING:,.2f}")
                    print(f"Status: {'[OK] MATCH' if abs(float(final[1]) - EXPECTED_CLOSING) < 0.01 else '[WARN] MISMATCH'}")
            else:
                print("\n[WARN] No February 2012 manual verification data found")
                print("Add February section to: l:/limo/reports/2012_cibc_complete_running_balance_verification.md")
        else:
            print("\n[WARN] No February 2012 section found in verification file")
            print("Expected section starting with: ## February 2012")
            
except FileNotFoundError:
    print("\n[FAIL] Verification file not found")
    print("Expected: l:/limo/reports/2012_cibc_complete_running_balance_verification.md")

cur.close()
conn.close()
