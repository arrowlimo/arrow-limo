"""
Check LMS database for information that could help match unmatched payments.

Compare:
1. Unmatched payments in PostgreSQL with reserve numbers in notes
2. LMS Reserve table for matching reserve numbers
3. LMS Payment table for payment_key matches
4. LMS Deposit table for deposit number matches
"""

import psycopg2
import pyodbc
import os

def get_db_connection():
    """Get PostgreSQL database connection."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def get_lms_connection():
    """Get LMS Access database connection."""
    LMS_PATH = r'L:\limo\backups\lms.mdb'
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)

def analyze_lms_matches():
    """Analyze LMS data to help match unmatched PostgreSQL payments."""
    
    pg_conn = get_db_connection()
    pg_cur = pg_conn.cursor()
    
    print("=" * 120)
    print("LMS DATABASE ANALYSIS FOR UNMATCHED PAYMENTS")
    print("=" * 120)
    print()
    
    # Get unmatched payments with various identifiers
    print("Fetching unmatched payments from PostgreSQL (2007-2024)...")
    pg_cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            amount,
            payment_key,
            account_number,
            reserve_number,
            notes,
            payment_method
        FROM payments
        WHERE charter_id IS NULL
          AND payment_date >= '2007-01-01'
          AND payment_date < '2025-01-01'
        ORDER BY payment_date DESC
        LIMIT 500
    """)
    
    unmatched = pg_cur.fetchall()
    print(f"Fetched {len(unmatched)} unmatched payments (showing first 500)")
    print()
    
    # Categorize by what info we have
    with_payment_key = []
    with_reserve_number = []
    with_account_number = []
    with_reserve_in_notes = []
    with_deposit_in_notes = []
    minimal_info = []
    
    for row in unmatched:
        pid, pdate, amount, pkey, account, reserve, notes, method = row
        
        if pkey:
            with_payment_key.append(row)
        if reserve:
            with_reserve_number.append(row)
        if account:
            with_account_number.append(row)
        if notes and 'reserve' in notes.lower():
            with_reserve_in_notes.append(row)
        if notes and 'deposit' in notes.lower():
            with_deposit_in_notes.append(row)
        if not (pkey or reserve or account or notes):
            minimal_info.append(row)
    
    print("Categorization by available identifiers:")
    print(f"  With payment_key:           {len(with_payment_key)}")
    print(f"  With reserve_number:        {len(with_reserve_number)}")
    print(f"  With account_number:        {len(with_account_number)}")
    print(f"  With 'reserve' in notes:    {len(with_reserve_in_notes)}")
    print(f"  With 'deposit' in notes:    {len(with_deposit_in_notes)}")
    print(f"  Minimal info:               {len(minimal_info)}")
    print()
    
    # Connect to LMS
    try:
        print("Connecting to LMS database...")
        lms_conn = get_lms_connection()
        lms_cur = lms_conn.cursor()
        print("[OK] Connected to LMS")
        print()
        
        # Check LMS Reserve table for reserve numbers we have
        if with_reserve_number:
            print("=" * 120)
            print(f"CHECKING LMS RESERVE TABLE FOR {len(with_reserve_number[:100])} RESERVE NUMBERS")
            print("=" * 120)
            
            matches_found = 0
            deleted_found = 0
            
            for row in with_reserve_number[:100]:  # Check first 100
                pid, pdate, amount, pkey, account, reserve, notes, method = row
                
                # Query LMS for this reserve number
                lms_cur.execute("""
                    SELECT Reserve_No, Account_No, PU_Date, Rate, Balance, Name, Pymt_Type
                    FROM Reserve
                    WHERE Reserve_No = ?
                """, (reserve,))
                
                lms_result = lms_cur.fetchone()
                
                if lms_result:
                    matches_found += 1
                    if matches_found <= 10:  # Show first 10
                        lms_reserve, lms_account, lms_date, lms_rate, lms_balance, lms_name, lms_pymt = lms_result
                        print(f"[OK] Payment {pid}: Reserve {reserve}")
                        print(f"   PostgreSQL: ${amount:.2f} on {pdate}, Account {account if account else 'NULL'}")
                        print(f"   LMS:        ${lms_rate:.2f} on {lms_date}, Account {lms_account}, Balance ${lms_balance:.2f}")
                        print(f"   Client:     {lms_name}")
                        print()
                else:
                    deleted_found += 1
            
            print(f"\nResults: {matches_found} found in LMS, {deleted_found} NOT in LMS (deleted/cancelled)")
            print()
        
        # Check LMS Payment table for payment_keys
        if with_payment_key:
            print("=" * 120)
            print(f"CHECKING LMS PAYMENT TABLE FOR {len(with_payment_key[:100])} PAYMENT KEYS")
            print("=" * 120)
            
            matches_found = 0
            
            for row in with_payment_key[:100]:  # Check first 100
                pid, pdate, amount, pkey, account, reserve, notes, method = row
                
                # Query LMS for this payment key
                lms_cur.execute("""
                    SELECT PaymentID, Account_No, Reserve_No, Amount, [Key], LastUpdated
                    FROM Payment
                    WHERE [Key] = ?
                """, (pkey,))
                
                lms_results = lms_cur.fetchall()
                
                if lms_results:
                    matches_found += 1
                    if matches_found <= 10:  # Show first 10
                        print(f"[OK] Payment Key {pkey} - PostgreSQL Payment {pid}")
                        print(f"   Found {len(lms_results)} LMS payment(s):")
                        for lms_row in lms_results[:5]:
                            lms_pid, lms_account, lms_reserve, lms_amount, lms_key, lms_date = lms_row
                            print(f"     LMS Payment {lms_pid}: Reserve {lms_reserve if lms_reserve else 'NULL'}, "
                                  f"Account {lms_account if lms_account else 'NULL'}, ${lms_amount:.2f} on {lms_date}")
                        print()
            
            print(f"\nResults: {matches_found} payment_keys found in LMS")
            print()
        
        # Check LMS Deposit table for deposit numbers in notes
        if with_deposit_in_notes:
            print("=" * 120)
            print(f"CHECKING LMS DEPOSIT TABLE FOR DEPOSIT NUMBERS IN NOTES")
            print("=" * 120)
            
            import re
            deposit_pattern = re.compile(r'deposit[:\s]+(\d{7})', re.IGNORECASE)
            
            matches_found = 0
            
            for row in with_deposit_in_notes[:50]:  # Check first 50
                pid, pdate, amount, pkey, account, reserve, notes, method = row
                
                # Extract deposit number from notes
                match = deposit_pattern.search(notes)
                if match:
                    deposit_num = match.group(1)
                    
                    # Query LMS Deposit table
                    lms_cur.execute("""
                        SELECT [Key], [Number], [Total], [Date], [Type], [Transact]
                        FROM Deposit
                        WHERE [Number] = ?
                    """, (deposit_num,))
                    
                    lms_result = lms_cur.fetchone()
                    
                    if lms_result:
                        matches_found += 1
                        if matches_found <= 10:
                            lms_key, lms_num, lms_total, lms_date, lms_type, lms_transact = lms_result
                            print(f"[OK] Deposit {deposit_num} - PostgreSQL Payment {pid}")
                            print(f"   PostgreSQL: ${amount:.2f} on {pdate}")
                            print(f"   LMS:        ${lms_total:.2f} on {lms_date}, Type {lms_type}, Transact {lms_transact}")
                            print(f"   Notes:      {notes[:80]}...")
                            print()
            
            print(f"\nResults: {matches_found} deposit numbers found in LMS")
            print()
        
        # Get LMS Reserve records without matching PostgreSQL charters
        print("=" * 120)
        print("LMS RESERVES NOT IN POSTGRESQL CHARTERS")
        print("=" * 120)
        
        lms_cur.execute("""
            SELECT Reserve_No, Account_No, PU_Date, Rate, Balance, Name, Pymt_Type
            FROM Reserve
            WHERE PU_Date >= #2007-01-01#
              AND PU_Date < #2025-01-01#
            ORDER BY PU_Date DESC
        """)
        
        lms_reserves = lms_cur.fetchall()
        print(f"Total LMS reserves (2007-2024): {len(lms_reserves)}")
        
        # Check which LMS reserves are in PostgreSQL
        missing_in_pg = []
        for lms_row in lms_reserves[:500]:  # Check first 500
            lms_reserve = lms_row[0]
            
            pg_cur.execute("""
                SELECT charter_id FROM charters WHERE reserve_number = %s
            """, (lms_reserve,))
            
            if not pg_cur.fetchone():
                missing_in_pg.append(lms_row)
        
        print(f"LMS reserves NOT in PostgreSQL charters (first 500 checked): {len(missing_in_pg)}")
        
        if missing_in_pg:
            print("\nSample missing reserves:")
            for lms_row in missing_in_pg[:10]:
                lms_reserve, lms_account, lms_date, lms_rate, lms_balance, lms_name, lms_pymt = lms_row
                print(f"  Reserve {lms_reserve}: ${lms_rate:.2f}, Balance ${lms_balance:.2f}, "
                      f"Date {lms_date}, Account {lms_account}, Client {lms_name}")
        
        lms_cur.close()
        lms_conn.close()
        
    except Exception as e:
        print(f"[FAIL] Error connecting to LMS: {e}")
        print("Cannot perform LMS comparison")
    
    # Summary
    print("\n" + "=" * 120)
    print("SUMMARY & RECOMMENDATIONS")
    print("=" * 120)
    print()
    
    print(f"Unmatched payments analyzed: {len(unmatched)}")
    print()
    print("Potential matching strategies:")
    print(f"  1. Reserve number lookup:   {len(with_reserve_number)} payments have reserve_number")
    print(f"  2. Payment key lookup:      {len(with_payment_key)} payments have payment_key")
    print(f"  3. Account number + date:   {len(with_account_number)} payments have account_number")
    print(f"  4. Notes parsing:           {len(with_reserve_in_notes)} have reserve in notes")
    print(f"  5. Deposit numbers:         {len(with_deposit_in_notes)} have deposit in notes")
    print()
    print("Next steps:")
    print("  - Create script to match by reserve_number from notes")
    print("  - Match payment_key to LMS Payment → Reserve_No")
    print("  - Import missing LMS reserves as charters")
    print("  - Match by account + date + amount tolerance")
    
    pg_cur.close()
    pg_conn.close()

if __name__ == '__main__':
    analyze_lms_matches()
