"""Import correct 2012 CIBC 1615 data and verify balances match PDF statement."""

import psycopg2
import hashlib
from datetime import date

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def generate_hash(date_str, description, amount):
    """Generate deterministic hash for transaction."""
    hash_input = f"{date_str}|{description}|{amount:.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

# 2012 January transactions from PDF
transactions_2012_jan = [
    # (date, description, debit, credit, balance)
    ('2012-01-01', 'Opening balance', 0, 0, 7177.34),
    ('2012-01-03', 'PURCHASE CENTEX PETROLEU', 63.50, 0, 7113.84),
    ('2012-01-03', 'PURCHASE MR.SUDS INC.', 4.80, 0, 7109.04),
    ('2012-01-03', 'PURCHASE REAL CDN. WHOLE', 37.16, 0, 7071.88),
    ('2012-01-03', 'PURCHASE RUN\'N ON EMPTY', 114.00, 0, 6957.88),
    ('2012-01-03', 'ABM WITHDRAWAL 2C0Q', 500.00, 0, 6457.88),
    ('2012-01-03', 'DEPOSIT', 0, 756.26, 7214.14),
    ('2012-01-03', 'WITHDRAWAL', 140.00, 0, 7074.14),
    ('2012-01-03', 'TRANSFER TO: 00339/02-28362', 2200.00, 0, 4874.14),
    ('2012-01-03', 'PURCHASE BED BATH & BEYO', 78.70, 0, 4795.44),
    # Jan 31 closing entries
    ('2012-01-31', 'Balance forward', 0, 0, 74.83),
    ('2012-01-31', 'DEBIT MEMO 4017775 VISA', 82.50, 0, -7.67),
    ('2012-01-31', 'E-TRANSFER NWK FEE', 1.50, 0, -9.17),
    ('2012-01-31', 'ACCOUNT FEE', 35.00, 0, -44.17),
    ('2012-01-31', 'OVERDRAFT S/C', 5.00, 0, -49.17),
    ('2012-01-31', 'Closing balance', 0, 0, -49.17),
]

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("CIBC 1615 - IMPORT CORRECT 2012 DATA (Opening $7,177.34 → Closing -$49.17)")
    print("=" * 100)
    
    # Check current state
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number = '1615'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    existing = cur.fetchone()[0]
    
    print(f"\nCurrent 2012 records: {existing}")
    
    if existing > 0:
        print(f"⚠️  {existing} records already exist for 2012")
        response = input("Delete and re-import? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            cur.close()
            conn.close()
            return
        
        cur.execute("""
            DELETE FROM banking_transactions
            WHERE account_number = '1615'
            AND EXTRACT(YEAR FROM transaction_date) = 2012
        """)
        print(f"Deleted {cur.rowcount} existing 2012 records")
    
    # Load existing hashes to prevent duplicates
    cur.execute("SELECT source_hash FROM banking_transactions WHERE source_hash IS NOT NULL")
    existing_hashes = {row[0] for row in cur.fetchall()}
    
    # Import transactions
    imported = 0
    skipped = 0
    
    print(f"\nImporting {len(transactions_2012_jan)} January 2012 transactions...")
    
    for txn_date, desc, debit, credit, balance in transactions_2012_jan:
        amount = debit if debit > 0 else credit
        source_hash = generate_hash(txn_date, desc, amount if amount > 0 else balance)
        
        if source_hash in existing_hashes:
            skipped += 1
            continue
        
        cur.execute("""
            INSERT INTO banking_transactions (
                account_number,
                transaction_date,
                description,
                debit_amount,
                credit_amount,
                balance,
                source_hash,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, ('1615', txn_date, desc, debit if debit > 0 else None, 
              credit if credit > 0 else None, balance, source_hash))
        
        imported += 1
        existing_hashes.add(source_hash)
    
    conn.commit()
    
    print(f"\n✅ Imported: {imported} transactions")
    print(f"⏭️  Skipped: {skipped} duplicates")
    
    # Verify balances
    print("\nVerifying balances:")
    cur.execute("""
        SELECT transaction_date, balance
        FROM banking_transactions
        WHERE account_number = '1615'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        ORDER BY transaction_date ASC
        LIMIT 1
    """)
    opening = cur.fetchone()
    
    cur.execute("""
        SELECT transaction_date, balance
        FROM banking_transactions
        WHERE account_number = '1615'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        ORDER BY transaction_date DESC
        LIMIT 1
    """)
    closing = cur.fetchone()
    
    if opening and closing:
        print(f"  Opening (Jan 1): ${opening[1]:.2f} (expected $7,177.34)")
        print(f"  Closing (Jan 31): ${closing[1]:.2f} (expected -$49.17)")
        
        if abs(opening[1] - 7177.34) < 0.01 and abs(closing[1] - (-49.17)) < 0.01:
            print("  ✅ BALANCES MATCH PDF!")
        else:
            print("  ❌ BALANCES DO NOT MATCH - CHECK DATA")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 100)
    print("IMPORT COMPLETE - Now run verify script to check 2012→2013 linkage")
    print("=" * 100)

if __name__ == '__main__':
    main()
