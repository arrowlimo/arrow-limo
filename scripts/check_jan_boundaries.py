"""
Check January 2012 opening and closing boundaries against manual verification.
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("=" * 80)
print("JANUARY 2012 BOUNDARY VERIFICATION")
print("=" * 80)

# Parse manual verification to get boundaries
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
                    
                    # Parse amount and balance
                    if amount_str and balance_str and current_date:
                        try:
                            amount = float(amount_str)
                            balance = float(balance_str)
                            
                            manual_txns.append({
                                'date': current_date,
                                'description': description,
                                'type': txn_type,
                                'amount': amount,
                                'balance': balance
                            })
                        except ValueError:
                            pass
                except (ValueError, IndexError):
                    continue

print(f"\nManual verification contains: {len(manual_txns)} transactions")

# Get first and last from manual
if manual_txns:
    first_manual = manual_txns[0]
    last_manual = manual_txns[-1]
    
    print("\n" + "=" * 80)
    print("MANUAL VERIFICATION BOUNDARIES")
    print("=" * 80)
    print(f"\nFirst transaction:")
    print(f"  Date: {first_manual['date']}")
    print(f"  Description: {first_manual['description']}")
    print(f"  Balance: ${first_manual['balance']:,.2f}")
    
    print(f"\nLast transaction:")
    print(f"  Date: {last_manual['date']}")
    print(f"  Description: {last_manual['description']}")
    print(f"  Balance: ${last_manual['balance']:,.2f}")

# Get database boundaries
cur.execute("""
    SELECT transaction_date, description, balance
    FROM banking_transactions
    WHERE transaction_date >= '2012-01-01' AND transaction_date <= '2012-01-31'
    ORDER BY transaction_date, transaction_id
    LIMIT 1
""")

db_first = cur.fetchone()

cur.execute("""
    SELECT transaction_date, description, balance
    FROM banking_transactions
    WHERE transaction_date >= '2012-01-01' AND transaction_date <= '2012-01-31'
    ORDER BY transaction_date DESC, transaction_id DESC
    LIMIT 1
""")

db_last = cur.fetchone()

print("\n" + "=" * 80)
print("DATABASE BOUNDARIES")
print("=" * 80)
print(f"\nFirst transaction:")
print(f"  Date: {db_first[0]}")
print(f"  Description: {db_first[1]}")
print(f"  Balance: ${db_first[2]:,.2f}")

print(f"\nLast transaction:")
print(f"  Date: {db_last[0]}")
print(f"  Description: {db_last[1]}")
print(f"  Balance: ${db_last[2]:,.2f}")

# Comparison
print("\n" + "=" * 80)
print("COMPARISON")
print("=" * 80)

opening_match = abs(float(db_first[2]) - first_manual['balance']) < 0.01
closing_match = abs(float(db_last[2]) - last_manual['balance']) < 0.01

print(f"\nOpening Balance:")
print(f"  Manual: ${first_manual['balance']:,.2f}")
print(f"  Database: ${db_first[2]:,.2f}")
if opening_match:
    print(f"  Status: [OK] MATCH")
else:
    delta = abs(float(db_first[2]) - first_manual['balance'])
    print(f"  Status: [WARN] MISMATCH (Δ ${delta:.2f})")

print(f"\nClosing Balance:")
print(f"  Manual: ${last_manual['balance']:,.2f}")
print(f"  Database: ${db_last[2]:,.2f}")
if closing_match:
    print(f"  Status: [OK] MATCH")
else:
    delta = abs(float(db_last[2]) - last_manual['balance'])
    print(f"  Status: [WARN] MISMATCH (Δ ${delta:.2f})")

# Count verification
cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions
    WHERE transaction_date >= '2012-01-01' AND transaction_date <= '2012-01-31'
""")
db_count = cur.fetchone()[0]

print(f"\nTransaction Count:")
print(f"  Manual: {len(manual_txns)} transactions")
print(f"  Database: {db_count} transactions")
print(f"  Difference: {db_count - len(manual_txns)} transactions")

# Check if all manual transactions exist in database
print("\n" + "=" * 80)
print("RECORD-BY-RECORD VALIDATION")
print("=" * 80)

missing_in_db = []
for idx, manual_txn in enumerate(manual_txns):
    cur.execute("""
        SELECT transaction_id, balance
        FROM banking_transactions
        WHERE transaction_date = %s
        AND ABS(COALESCE(balance, 0) - %s) < 0.01
        LIMIT 1
    """, (manual_txn['date'], manual_txn['balance']))
    
    match = cur.fetchone()
    if not match:
        missing_in_db.append((idx + 1, manual_txn))

if missing_in_db:
    print(f"\n[WARN] Found {len(missing_in_db)} manual transactions NOT in database:")
    print(f"\n{'Row#':<6} {'Date':<12} {'Balance':>12} {'Description':<40}")
    print("-" * 80)
    for row_num, txn in missing_in_db[:10]:
        print(f"{row_num:<6} {txn['date']:<12} ${txn['balance']:>10,.2f} {txn['description'][:39]}")
    if len(missing_in_db) > 10:
        print(f"... and {len(missing_in_db) - 10} more")
else:
    print("\n[OK] ALL manual verification transactions found in database")

# Summary
print("\n" + "=" * 80)
print("VALIDATION SUMMARY")
print("=" * 80)
print(f"\n{'Check':<40} {'Status':<20}")
print("-" * 60)
print(f"{'Opening balance matches':<40} {'[OK] PASS' if opening_match else '[FAIL] FAIL'}")
print(f"{'Closing balance matches':<40} {'[OK] PASS' if closing_match else '[FAIL] FAIL'}")
print(f"{'All manual records in database':<40} {'[OK] PASS' if not missing_in_db else f'[FAIL] FAIL ({len(missing_in_db)} missing)'}")

if opening_match and closing_match and not missing_in_db:
    print("\n" + "🎉 " * 20)
    print("[OK] JANUARY 2012 DATABASE CORRECTION: COMPLETE AND VERIFIED")
    print("🎉 " * 20)
else:
    print("\n[WARN] Some validation checks failed - review discrepancies above")

cur.close()
conn.close()
