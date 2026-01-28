#!/usr/bin/env python
"""
Check if all cheques from banking transactions are registered in a cheque tracking table.
Looks for: cheques table, check_register, cheque_book, or similar tracking tables.
"""

import psycopg2
import os
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=== CHEQUE REGISTRATION ANALYSIS ===\n")
    
    # Step 1: Find all cheque-related tables
    print("Step 1: Looking for cheque tracking tables...")
    cur.execute("""
        SELECT table_name, 
               (SELECT COUNT(*) FROM information_schema.columns 
                WHERE table_name = t.table_name) as column_count
        FROM information_schema.tables t
        WHERE table_schema = 'public'
        AND (
            table_name ILIKE '%cheque%' OR
            table_name ILIKE '%check%' OR
            table_name LIKE '%chq%'
        )
        ORDER BY table_name
    """)
    
    cheque_tables = cur.fetchall()
    
    if cheque_tables:
        print(f"Found {len(cheque_tables)} cheque-related table(s):")
        for table, cols in cheque_tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"  📋 {table:30} - {cols:2} columns, {count:6} records")
            
            # Show columns for each table
            cur.execute(f"""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = '{table}'
                ORDER BY ordinal_position
            """)
            columns = cur.fetchall()
            print(f"     Columns: {', '.join([c[0] for c in columns])}")
            print()
    else:
        print("[FAIL] No dedicated cheque tracking tables found\n")
    
    # Step 2: Find all cheque transactions in 2012 CIBC banking
    print("\nStep 2: Finding cheque transactions in 2012 CIBC banking...")
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            account_number
        FROM banking_transactions
        WHERE transaction_date >= '2012-01-01'
        AND transaction_date <= '2012-12-31'
        AND account_number = '0228362'
        AND (
            description ILIKE '%cheque%' OR
            description ILIKE '%check%' OR
            description ILIKE '%chq%' OR
            description ~ 'CHQ\\s*#?\\d+' OR
            description ~ 'CHECK\\s*#?\\d+'
        )
        ORDER BY transaction_date
    """)
    
    cheque_transactions = cur.fetchall()
    print(f"Found {len(cheque_transactions)} cheque transactions in 2012 CIBC\n")
    
    if not cheque_transactions:
        print("[OK] No cheque transactions found in 2012")
        cur.close()
        conn.close()
        return
    
    # Step 3: Display all cheque transactions
    print("="*100)
    print("CHEQUE TRANSACTIONS IN 2012")
    print("="*100)
    
    total_amount = 0
    for txn_id, txn_date, desc, amount, acct in cheque_transactions:
        amount_val = float(amount) if amount else 0.0
        total_amount += amount_val
        print(f"{txn_date} | ${amount_val:10.2f} | {desc[:75]}")
    
    print(f"\nTotal cheque transactions: {len(cheque_transactions)}")
    print(f"Total cheque amount: ${total_amount:,.2f}")
    
    # Step 4: Try to extract cheque numbers from descriptions
    print("\n" + "="*100)
    print("CHEQUE NUMBER EXTRACTION")
    print("="*100)
    
    import re
    cheque_pattern = re.compile(r'(?:CHQ|CHECK|CHEQUE)\s*#?\s*(\d+)', re.IGNORECASE)
    
    extracted = []
    for txn_id, txn_date, desc, amount, acct in cheque_transactions:
        match = cheque_pattern.search(desc)
        cheque_num = match.group(1) if match else "UNKNOWN"
        extracted.append({
            'txn_id': txn_id,
            'date': txn_date,
            'cheque_number': cheque_num,
            'amount': float(amount) if amount else 0.0,
            'description': desc
        })
    
    cheques_with_numbers = [c for c in extracted if c['cheque_number'] != "UNKNOWN"]
    cheques_without_numbers = [c for c in extracted if c['cheque_number'] == "UNKNOWN"]
    
    print(f"\nCheques WITH extracted numbers: {len(cheques_with_numbers)}")
    for chq in cheques_with_numbers:
        print(f"  Cheque #{chq['cheque_number']:6} | {chq['date']} | ${chq['amount']:10.2f} | {chq['description'][:50]}")
    
    print(f"\nCheques WITHOUT identifiable numbers: {len(cheques_without_numbers)}")
    for chq in cheques_without_numbers:
        print(f"  {chq['date']} | ${chq['amount']:10.2f} | {chq['description'][:70]}")
    
    # Step 5: Check if cheques are registered in any tracking table
    if cheque_tables:
        print("\n" + "="*100)
        print("REGISTRATION CHECK")
        print("="*100)
        
        for table, _ in cheque_tables:
            print(f"\nChecking table: {table}")
            
            # Get table structure
            cur.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table}'
            """)
            available_cols = [row[0] for row in cur.fetchall()]
            
            # Try to find date, amount, and cheque number columns
            date_col = None
            amount_col = None
            cheque_num_col = None
            
            for col in available_cols:
                col_lower = col.lower()
                if 'date' in col_lower and not date_col:
                    date_col = col
                if ('amount' in col_lower or 'total' in col_lower) and not amount_col:
                    amount_col = col
                if ('cheque' in col_lower or 'check' in col_lower or 'number' in col_lower) and not cheque_num_col:
                    cheque_num_col = col
            
            if date_col and amount_col:
                # Try to match banking transactions to registered cheques
                cur.execute(f"""
                    SELECT COUNT(*) FROM {table}
                    WHERE {date_col} >= '2012-01-01'
                    AND {date_col} <= '2012-12-31'
                """)
                count_2012 = cur.fetchone()[0]
                print(f"  2012 entries in {table}: {count_2012}")
                
                # Show sample entries
                if count_2012 > 0:
                    cols_to_select = [date_col, amount_col]
                    if cheque_num_col:
                        cols_to_select.append(cheque_num_col)
                    
                    cur.execute(f"""
                        SELECT {', '.join(cols_to_select)}
                        FROM {table}
                        WHERE {date_col} >= '2012-01-01'
                        AND {date_col} <= '2012-12-31'
                        ORDER BY {date_col}
                        LIMIT 10
                    """)
                    samples = cur.fetchall()
                    print(f"  Sample entries:")
                    for sample in samples:
                        print(f"    {sample}")
            else:
                print(f"  [WARN]  Cannot determine date/amount columns in {table}")
    
    # Step 6: Final verdict
    print("\n" + "="*100)
    print("VERDICT")
    print("="*100)
    
    if not cheque_tables:
        print("[FAIL] NO CHEQUE TRACKING TABLE EXISTS")
        print("   Recommendation: Create a 'cheques' or 'check_register' table with:")
        print("     - cheque_number (unique identifier)")
        print("     - cheque_date")
        print("     - payee/vendor_name")
        print("     - amount")
        print("     - memo/description")
        print("     - cleared_date (date cheque cleared bank)")
        print("     - banking_transaction_id (link to banking_transactions)")
        print("     - status (issued, cleared, void, cancelled)")
    else:
        print(f"[OK] Found {len(cheque_tables)} cheque tracking table(s)")
        print(f"[WARN]  {len(cheque_transactions)} cheque transactions in 2012 CIBC")
        print(f"   {len(cheques_with_numbers)} cheques have identifiable numbers")
        print(f"   {len(cheques_without_numbers)} cheques need manual number extraction")
        print("\n   Next steps:")
        print("   1. Compare banking cheque transactions to registered cheques")
        print("   2. Create entries for any unregistered cheques")
        print("   3. Link registered cheques to banking_transaction_id")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
