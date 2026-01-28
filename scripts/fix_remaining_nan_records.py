"""
Fix remaining 88 records with name='nan' - mostly bank-related
"""
import psycopg2

def main():
    conn = psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )
    cur = conn.cursor()
    
    print("=" * 120)
    print("FIXING REMAINING RECORDS WITH name='nan'")
    print("=" * 120)
    
    # Check what transaction types they are
    print("\nRemaining records by transaction_type:")
    cur.execute("""
        SELECT transaction_type, COUNT(*) as count
        FROM general_ledger 
        WHERE name = 'nan'
        GROUP BY transaction_type
        ORDER BY count DESC
    """)
    for trans_type, count in cur.fetchall():
        print(f"  {trans_type}: {count}")
    
    # Look at some samples
    print("\nSample remaining records:")
    print("=" * 120)
    cur.execute("""
        SELECT id, date, account, transaction_type, memo_description, debit, credit
        FROM general_ledger 
        WHERE name = 'nan'
        ORDER BY date DESC
        LIMIT 15
    """)
    for row in cur.fetchall():
        gl_id, date, account, trans_type, memo, debit, credit = row
        amount = debit if debit else credit
        memo_short = memo[:70] if memo else ''
        print(f"ID {gl_id}: {date} | {account:40s} | {trans_type:15s} | ${amount:10} | {memo_short}")
    
    # Fix Scotia Bank Main - likely bank service charges or transfers
    print("\n" + "=" * 120)
    print("Updating Scotia Bank Main records...")
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Bank Transaction',
            account_name = 'Bank Transaction'
        WHERE name = 'nan'
        AND account = '1010 Scotia Bank Main'
    """)
    scotia_count = cur.rowcount
    print(f"   Updated {scotia_count} Scotia Bank records")
    
    # Fix CIBC checking account
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Bank Transaction',
            account_name = 'Bank Transaction'
        WHERE name = 'nan'
        AND account = '0228362 CIBC checking account'
    """)
    cibc_count = cur.rowcount
    print(f"   Updated {cibc_count} CIBC checking account records")
    
    # Fix CIBC Business Deposit
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Bank Transaction',
            account_name = 'Bank Transaction'
        WHERE name = 'nan'
        AND account = '3648117 CIBC Business Deposit account'
    """)
    cibc_biz_count = cur.rowcount
    print(f"   Updated {cibc_biz_count} CIBC Business Deposit records")
    
    # Fix Charter Client purchases
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Charter Client Purchase',
            account_name = 'Charter Client Purchase'
        WHERE name = 'nan'
        AND account = 'Charter Client purchases'
    """)
    charter_count = cur.rowcount
    print(f"   Updated {charter_count} Charter Client purchase records")
    
    # Fix Credit Card accounts
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Credit Card Transaction',
            account_name = 'Credit Card Transaction'
        WHERE name = 'nan'
        AND (account LIKE '%Mastercard%' OR account LIKE '%Visa%' OR account LIKE '%MC%')
    """)
    cc_count = cur.rowcount
    print(f"   Updated {cc_count} Credit Card records")
    
    # Fix Bank Charges
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Bank Charges',
            account_name = 'Bank Charges'
        WHERE name = 'nan'
        AND (account LIKE '%Bank Charges%' OR account LIKE '%Credit Card Charges%')
    """)
    charges_count = cur.rowcount
    print(f"   Updated {charges_count} Bank/CC Charges records")
    
    # Commit
    conn.commit()
    
    # Final check
    cur.execute("""
        SELECT COUNT(*) 
        FROM general_ledger 
        WHERE name = 'nan'
    """)
    remaining = cur.fetchone()[0]
    
    print("\n" + "=" * 120)
    print("FINAL RESULTS")
    print("=" * 120)
    print(f"Records updated in this pass: {scotia_count + cibc_count + cibc_biz_count + charter_count + cc_count + charges_count}")
    print(f"Records still with name='nan': {remaining}")
    
    if remaining > 0:
        print("\nRemaining records:")
        cur.execute("""
            SELECT id, date, account, transaction_type, memo_description, debit, credit
            FROM general_ledger 
            WHERE name = 'nan'
            ORDER BY date DESC
        """)
        for row in cur.fetchall():
            gl_id, date, account, trans_type, memo, debit, credit = row
            amount = debit if debit else credit
            memo_short = memo[:50] if memo else ''
            print(f"ID {gl_id}: {date} | {account:35s} | {trans_type:12s} | ${amount:10} | {memo_short}")
    
    conn.close()
    print("\n" + "=" * 120)
    print("Complete!")

if __name__ == "__main__":
    main()
