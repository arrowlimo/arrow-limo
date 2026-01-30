"""
Analyze and fix records with NULL name (not 'nan')
"""
import psycopg2

def main():
    conn = psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )
    cur = conn.cursor()
    
    print("=" * 120)
    print("ANALYZING RECORDS WITH NULL NAME")
    print("=" * 120)
    
    # Check transaction types
    print("\nBy transaction type:")
    cur.execute("""
        SELECT transaction_type, COUNT(*) as count
        FROM general_ledger 
        WHERE name IS NULL
        GROUP BY transaction_type
        ORDER BY count DESC
    """)
    for trans_type, count in cur.fetchall():
        print(f"  {trans_type}: {count}")
    
    # Check accounts
    print("\nBy account (top 15):")
    cur.execute("""
        SELECT account, COUNT(*) as count
        FROM general_ledger 
        WHERE name IS NULL
        GROUP BY account
        ORDER BY count DESC
        LIMIT 15
    """)
    for account, count in cur.fetchall():
        print(f"  {account}: {count}")
    
    # Sample records
    print("\n" + "=" * 120)
    print("Sample records:")
    print("=" * 120)
    cur.execute("""
        SELECT id, date, account, transaction_type, memo_description, debit, credit
        FROM general_ledger 
        WHERE name IS NULL
        ORDER BY date DESC
        LIMIT 20
    """)
    for row in cur.fetchall():
        gl_id, date, account, trans_type, memo, debit, credit = row
        amount = debit if debit else credit
        memo_short = memo[:70] if memo else 'NULL'
        print(f"ID {gl_id}: {date} | {account:40s} | {trans_type:12s} | ${amount:10} | {memo_short}")
    
    print("\n" + "=" * 120)
    print("FIXING NULL NAME RECORDS")
    print("=" * 120)
    
    # Fix by transaction type and account patterns
    
    # 1. Square deposits
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Square Payments',
            account_name = 'Square Payments'
        WHERE name IS NULL
        AND account LIKE '%Square%'
    """)
    square_count = cur.rowcount
    print(f"Updated {square_count} Square records")
    
    # 2. Driver Advances
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Driver Advance',
            account_name = 'Driver Advance'
        WHERE name IS NULL
        AND account LIKE '%Driver Advance%'
    """)
    driver_count = cur.rowcount
    print(f"Updated {driver_count} Driver Advance records")
    
    # 3. Petty Cash
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Petty Cash Transaction',
            account_name = 'Petty Cash Transaction'
        WHERE name IS NULL
        AND account LIKE '%Petty Cash%'
    """)
    petty_count = cur.rowcount
    print(f"Updated {petty_count} Petty Cash records")
    
    # 4. Bank accounts (CIBC, Scotia, etc.)
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Bank Transaction',
            account_name = 'Bank Transaction'
        WHERE name IS NULL
        AND (account LIKE '%CIBC%' OR account LIKE '%Scotia%' OR account LIKE '%Bank%' OR account LIKE '%checking%')
    """)
    bank_count = cur.rowcount
    print(f"Updated {bank_count} Bank account records")
    
    # 5. Income accounts
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Service Income',
            account_name = 'Service Income'
        WHERE name IS NULL
        AND account LIKE '%Income%'
    """)
    income_count = cur.rowcount
    print(f"Updated {income_count} Income records")
    
    # 6. By transaction type for remaining
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Journal Entry',
            account_name = 'Journal Entry'
        WHERE name IS NULL
        AND transaction_type = 'Journal Entry'
    """)
    je_count = cur.rowcount
    print(f"Updated {je_count} Journal Entry records")
    
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Invoice Payment',
            account_name = 'Invoice Payment'
        WHERE name IS NULL
        AND transaction_type = 'Invoice'
    """)
    invoice_count = cur.rowcount
    print(f"Updated {invoice_count} Invoice records")
    
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Payment Received',
            account_name = 'Payment Received'
        WHERE name IS NULL
        AND transaction_type = 'Payment'
    """)
    payment_count = cur.rowcount
    print(f"Updated {payment_count} Payment records")
    
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Credit Transaction',
            account_name = 'Credit Transaction'
        WHERE name IS NULL
        AND transaction_type LIKE '%Credit%'
    """)
    credit_count = cur.rowcount
    print(f"Updated {credit_count} Credit records")
    
    # 7. Catch-all for any remaining
    cur.execute("""
        UPDATE general_ledger
        SET name = 'Unclassified Transaction',
            account_name = 'Unclassified Transaction'
        WHERE name IS NULL
    """)
    unclass_count = cur.rowcount
    print(f"Updated {unclass_count} Unclassified records")
    
    conn.commit()
    
    # Final count
    cur.execute("SELECT COUNT(*) FROM general_ledger WHERE name IS NULL")
    remaining = cur.fetchone()[0]
    
    print("\n" + "=" * 120)
    print("SUMMARY")
    print("=" * 120)
    total_updated = (square_count + driver_count + petty_count + bank_count + 
                     income_count + je_count + invoice_count + payment_count + 
                     credit_count + unclass_count)
    print(f"Total records updated: {total_updated}")
    print(f"Records still with NULL name: {remaining}")
    
    conn.close()

if __name__ == "__main__":
    main()
