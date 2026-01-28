"""
Copy name field to account_name field where account_name is NULL
"""
import psycopg2

def main():
    # Connect to database
    conn = psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )
    cur = conn.cursor()
    
    # First, check how many records need updating
    cur.execute("""
        SELECT COUNT(*) 
        FROM general_ledger 
        WHERE account_name IS NULL 
        AND name IS NOT NULL 
        AND name != '' 
        AND name != 'nan'
    """)
    count = cur.fetchone()[0]
    print(f"Records with NULL account_name but valid name: {count}")
    
    # Show some examples before updating
    cur.execute("""
        SELECT id, date, account_name, name, account, debit, credit
        FROM general_ledger 
        WHERE account_name IS NULL 
        AND name IS NOT NULL 
        AND name != '' 
        AND name != 'nan'
        ORDER BY date DESC
        LIMIT 10
    """)
    
    print("\nSample records before update:")
    print("=" * 120)
    for row in cur.fetchall():
        gl_id, date, acct_name, name, account, debit, credit = row
        amount = debit if debit else credit
        print(f"ID {gl_id}: {date} | account_name={acct_name} | name={name} | account={account} | ${amount}")
    
    # Perform the update
    print("\n" + "=" * 120)
    print("Updating records...")
    cur.execute("""
        UPDATE general_ledger 
        SET account_name = name
        WHERE account_name IS NULL 
        AND name IS NOT NULL 
        AND name != '' 
        AND name != 'nan'
    """)
    
    updated_count = cur.rowcount
    conn.commit()
    
    print(f"✓ Updated {updated_count} records")
    
    # Verify the update
    cur.execute("""
        SELECT COUNT(*) 
        FROM general_ledger 
        WHERE account_name IS NULL
    """)
    remaining = cur.fetchone()[0]
    
    print(f"\nRecords still with NULL account_name: {remaining}")
    
    # Show updated records
    cur.execute("""
        SELECT id, date, account_name, name, debit, credit
        FROM general_ledger 
        WHERE account_name = name
        AND account_name IS NOT NULL
        ORDER BY date DESC
        LIMIT 10
    """)
    
    print("\nSample records after update (account_name now populated):")
    print("=" * 120)
    for row in cur.fetchall():
        gl_id, date, acct_name, name, debit, credit = row
        amount = debit if debit else credit
        print(f"ID {gl_id}: {date} | account_name={acct_name} | name={name} | ${amount}")
    
    conn.close()
    print("\n" + "=" * 120)
    print("Update complete!")

if __name__ == "__main__":
    main()
