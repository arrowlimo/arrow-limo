import csv
import psycopg2

# Check the backup CSV for banking_transaction_id data
csv_file = r'L:\limo\backups\critical_backup_20251210_123930\payments_backup_20251210_123930.csv'

print("=== CHECKING BACKUP CSV ===")
with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    
    total = 0
    with_banking = 0
    sample_rows = []
    
    for row in reader:
        total += 1
        if row.get('banking_transaction_id') and row['banking_transaction_id'].strip():
            with_banking += 1
            if len(sample_rows) < 5:
                sample_rows.append({
                    'payment_id': row['payment_id'],
                    'reserve_number': row.get('reserve_number'),
                    'amount': row.get('amount'),
                    'banking_transaction_id': row['banking_transaction_id']
                })
    
    match_pct = (with_banking / total * 100) if total > 0 else 0
    
    print(f"\nBackup from December 10, 2025:")
    print(f"Total payments: {total:,}")
    print(f"With banking_transaction_id: {with_banking:,} ({match_pct:.1f}%)")
    print(f"Without banking: {total - with_banking:,} ({100-match_pct:.1f}%)")
    
    if with_banking > 0:
        print(f"\n✅ BACKUP HAS MATCHING DATA!")
        print("\nSample rows with banking_transaction_id:")
        for row in sample_rows:
            print(f"  Payment {row['payment_id']} (Rsv {row['reserve_number']}, ${row['amount']}) → Banking TX {row['banking_transaction_id']}")
    else:
        print(f"\n❌ Backup does not have banking_transaction_id data")

# Compare to current database
print("\n=== CURRENT DATABASE ===")
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(banking_transaction_id) as with_banking
    FROM payments
""")
current_total, current_with_banking = cur.fetchone()
current_pct = (current_with_banking / current_total * 100) if current_total > 0 else 0

print(f"Total payments: {current_total:,}")
print(f"With banking_transaction_id: {current_with_banking:,} ({current_pct:.1f}%)")

print("\n=== COMPARISON ===")
recoverable = with_banking - current_with_banking
print(f"Backup match rate: {match_pct:.1f}%")
print(f"Current match rate: {current_pct:.1f}%")
print(f"Recoverable matches: {recoverable:,}")

if recoverable > 0:
    print(f"\n🎉 CAN RESTORE {recoverable:,} LOST MATCHES from backup!")
elif match_pct >= 98:
    print(f"\n✅ Backup has 98%+ matching (can restore to that level)")
else:
    print(f"\n⚠️ Backup also has low matching rate ({match_pct:.1f}%)")

conn.close()
