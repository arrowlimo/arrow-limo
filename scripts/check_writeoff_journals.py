"""
Check if journal entries exist for 2012 write-offs.
"""
import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

# Write-off reserve numbers
writeoff_reserves = [
    '002359', '002947', '002994', '003261', '003406', '003429', '003897', '003959',
    '004035', '004125', '004138', '004173', '004200', '004211', '004251', '004273',
    '004279', '004301', '004315', '004322', '004326', '004343', '004483', '004502',
    '004522', '004564', '004572', '004584', '004596', '004626', '004647', '004697',
    '004713', '004872', '004932', '004941', '004947', '004963', '004981', '004982',
    '004997', '005020', '005026', '005034', '005042', '005069', '005138', '005159',
    '005162', '005217', '005280', '005359', '005428', '005527', '005535', '005672'
]

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print('=' * 100)
    print('CHECKING FOR WRITE-OFF JOURNAL ENTRIES')
    print('=' * 100)
    
    # Check for write-off entries in 2012
    cur.execute("""
                SELECT COUNT(*) 
                FROM journal 
                WHERE "Memo/Description" ILIKE '%write%off%' 
                    AND "Date" ILIKE '2012%'
    """)
    count_2012 = cur.fetchone()[0]
    print(f'\nWrite-off journal entries in 2012: {count_2012}')
    
    # Check for any write-off entries
    cur.execute("""
    SELECT COUNT(*) 
    FROM journal 
    WHERE "Memo/Description" ILIKE '%write%off%'
    """)
    count_all = cur.fetchone()[0]
    print(f'Total write-off journal entries (all years): {count_all}')
    
    # Sample write-off entries
    print(f'\n' + '=' * 100)
    print('SAMPLE WRITE-OFF JOURNAL ENTRIES:')
    print('=' * 100)
    cur.execute("""
    SELECT "Date", "Memo/Description", "Debit", "Credit", "Account"
    FROM journal 
    WHERE "Memo/Description" ILIKE '%write%off%' 
    ORDER BY "Date" 
    LIMIT 20
    """)
    results = cur.fetchall()
    
    if results:
        for r in results:
            print(f"{r[0]} | {r[4] or 'N/A'} | {r[1][:60]}")
            print(f"  Debit: ${r[2] or 0:.2f} | Credit: ${r[3] or 0:.2f}")
    else:
        print("  [FAIL] No write-off journal entries found in database")
    
    # Check for specific reserve numbers in journal
    print(f'\n' + '=' * 100)
    print('CHECKING SPECIFIC RESERVE NUMBERS IN JOURNAL:')
    print('=' * 100)
    
    found_reserves = []
    for reserve in writeoff_reserves[:10]:  # Check first 10
        cur.execute("""
            SELECT "Date", "Memo/Description", "Debit", "Credit"
            FROM journal 
            WHERE "Memo/Description" ILIKE %s
            ORDER BY "Date"
        """, (f'%{reserve}%',))
        
        results = cur.fetchall()
        if results:
            found_reserves.append(reserve)
            print(f'\n✓ Reserve {reserve}:')
            for r in results:
                print(f'  {r[0]} | {r[1][:50]} | Dr: ${r[2] or 0:.2f} Cr: ${r[3] or 0:.2f}')
    
    print(f'\nReserves with journal entries: {len(found_reserves)} out of 10 checked')
    
    # Check unified_general_ledger
    print(f'\n' + '=' * 100)
    print('CHECKING UNIFIED GENERAL LEDGER:')
    print('=' * 100)
    
    cur.execute("""
        SELECT COUNT(*) 
        FROM unified_general_ledger 
        WHERE description ILIKE '%write%off%' 
          AND EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    ugl_count = cur.fetchone()[0]
    print(f'Write-off entries in unified_general_ledger (2012): {ugl_count}')
    
    # Sample UGL entries
    cur.execute("""
        SELECT transaction_date, account_name, description, debit_amount, credit_amount
        FROM unified_general_ledger 
        WHERE description ILIKE '%write%off%' 
          AND EXTRACT(YEAR FROM transaction_date) = 2012
        ORDER BY transaction_date 
        LIMIT 10
    """)
    results = cur.fetchall()
    
    if results:
        print('\nSample entries:')
        for r in results:
            print(f"  {r[0]} | {r[1]} | {r[2][:40]}")
            print(f"    Debit: ${r[3] or 0:.2f} | Credit: ${r[4] or 0:.2f}")
    
    # Summary
    print(f'\n' + '=' * 100)
    print('SUMMARY:')
    print('=' * 100)
    print(f'Total write-offs to check: 56')
    print(f'Journal entries found (2012): {count_2012}')
    print(f'UGL entries found (2012): {ugl_count}')
    
    if count_2012 == 0 and ugl_count == 0:
        print('\n[FAIL] NO JOURNAL ENTRIES FOUND FOR 2012 WRITE-OFFS')
        print('   Recommendation: Create journal entries to properly record write-offs')
    elif count_2012 < 56:
        print(f'\n[WARN] INCOMPLETE: Only {count_2012} entries found (expected 56)')
        print('   Recommendation: Review and add missing entries')
    else:
        print('\n✓ Journal entries appear to exist for write-offs')
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
