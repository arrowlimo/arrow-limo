#!/usr/bin/env python
"""
Create a proper cheque register and register all 2012 CIBC cheques.
Includes: cheque_number, cheque_date, cleared_date, payee, amount, memo, banking_transaction_id, status.
"""

import psycopg2
import os
from datetime import datetime
import re

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def extract_cheque_info(description):
    """Extract cheque number and payee from description"""
    # Pattern: "Cheque 209 000000074B011B (Big 105 Radio - advertising)"
    # Pattern: "CHEQUE 17086706 207"
    
    cheque_pattern = re.compile(r'(?:CHQ|CHECK|CHEQUE)\s+#?\s*(\d+)', re.IGNORECASE)
    match = cheque_pattern.search(description)
    cheque_num = match.group(1) if match else None
    
    # Extract payee from parentheses if present
    payee_pattern = re.compile(r'\(([^)]+)\)')
    payee_match = payee_pattern.search(description)
    payee = payee_match.group(1) if payee_match else None
    
    # If no payee in parentheses, extract from description after cheque number
    if not payee:
        # Try to get text after the cheque number reference string
        after_cheque = re.sub(r'(?:CHQ|CHECK|CHEQUE)\s+#?\s*\d+\s+\d+', '', description, flags=re.IGNORECASE)
        payee = after_cheque.strip() if after_cheque.strip() else None
    
    return cheque_num, payee

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=== CHEQUE REGISTER CREATION ===\n")
    
    # Step 1: Create cheque_register table if it doesn't exist
    print("Step 1: Creating cheque_register table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cheque_register (
            id SERIAL PRIMARY KEY,
            cheque_number VARCHAR(50) NOT NULL,
            cheque_date DATE,
            cleared_date DATE,
            payee VARCHAR(200),
            amount DECIMAL(12,2) NOT NULL,
            memo TEXT,
            banking_transaction_id INTEGER REFERENCES banking_transactions(transaction_id),
            status VARCHAR(50) DEFAULT 'cleared',
            account_number VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(cheque_number, account_number, cleared_date)
        )
    """)
    conn.commit()
    print("[OK] cheque_register table ready\n")
    
    # Step 2: Check existing entries
    cur.execute("SELECT COUNT(*) FROM cheque_register WHERE cleared_date >= '2012-01-01' AND cleared_date <= '2012-12-31'")
    existing_2012 = cur.fetchone()[0]
    print(f"Existing 2012 cheques in register: {existing_2012}\n")
    
    # Step 3: Get all cheque transactions from 2012 CIBC
    print("Step 2: Finding cheque transactions in 2012 CIBC banking...")
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
            description ILIKE '%chq%'
        )
        ORDER BY transaction_date
    """)
    
    cheque_transactions = cur.fetchall()
    print(f"Found {len(cheque_transactions)} cheque transactions\n")
    
    # Step 4: Register each cheque
    print("="*80)
    print("REGISTERING CHEQUES")
    print("="*80)
    
    registered_count = 0
    skipped_count = 0
    error_count = 0
    
    for txn_id, txn_date, desc, amount, acct in cheque_transactions:
        cheque_num, payee = extract_cheque_info(desc)
        
        if not cheque_num:
            print(f"[WARN]  SKIP: Cannot extract cheque number from: {desc[:60]}")
            skipped_count += 1
            continue
        
        # Check if already registered
        cur.execute("""
            SELECT id FROM cheque_register
            WHERE cheque_number = %s
            AND account_number = %s
            AND cleared_date = %s
        """, (cheque_num, acct, txn_date))
        
        if cur.fetchone():
            print(f"  EXISTS: Cheque #{cheque_num:10} | {txn_date} | ${float(amount):10.2f}")
            skipped_count += 1
            continue
        
        # Register the cheque
        try:
            cur.execute("""
                INSERT INTO cheque_register (
                    cheque_number,
                    cheque_date,
                    cleared_date,
                    payee,
                    amount,
                    memo,
                    banking_transaction_id,
                    status,
                    account_number
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                cheque_num,
                txn_date,  # Use cleared date as cheque date (actual issue date unknown)
                txn_date,  # Cleared date
                payee,
                float(amount),
                desc,  # Full description as memo
                txn_id,
                'cleared',
                acct
            ))
            
            cheque_id = cur.fetchone()[0]
            registered_count += 1
            
            payee_display = payee[:30] if payee else "Unknown payee"
            print(f"[OK] #{cheque_num:10} | {txn_date} | ${float(amount):10.2f} | {payee_display}")
            
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            print(f"  DUPLICATE: Cheque #{cheque_num} already exists")
            skipped_count += 1
        except Exception as e:
            conn.rollback()
            print(f"[FAIL] ERROR: Cheque #{cheque_num} - {str(e)[:80]}")
            error_count += 1
    
    # Commit all registrations
    conn.commit()
    
    # Step 5: Verify registrations
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)
    
    cur.execute("""
        SELECT COUNT(*), SUM(amount)
        FROM cheque_register
        WHERE cleared_date >= '2012-01-01'
        AND cleared_date <= '2012-12-31'
        AND account_number = '0228362'
    """)
    
    final_count, final_total = cur.fetchone()
    
    print(f"Total 2012 cheques in register: {final_count}")
    print(f"Total amount: ${float(final_total):,.2f}")
    print(f"\nRegistered this session: {registered_count}")
    print(f"Skipped (already exist or duplicate): {skipped_count}")
    print(f"Errors: {error_count}")
    
    # Show sample registered cheques
    print("\n" + "="*80)
    print("SAMPLE REGISTERED CHEQUES (first 10)")
    print("="*80)
    
    cur.execute("""
        SELECT 
            cheque_number,
            cleared_date,
            amount,
            payee,
            status
        FROM cheque_register
        WHERE cleared_date >= '2012-01-01'
        AND cleared_date <= '2012-12-31'
        AND account_number = '0228362'
        ORDER BY cleared_date
        LIMIT 10
    """)
    
    samples = cur.fetchall()
    for chq_num, chq_date, amt, payee, status in samples:
        payee_display = payee[:40] if payee else "Unknown"
        print(f"#{chq_num:10} | {chq_date} | ${float(amt):10.2f} | {status:8} | {payee_display}")
    
    # Show cheques without payee info
    print("\n" + "="*80)
    print("CHEQUES NEEDING PAYEE INFORMATION")
    print("="*80)
    
    cur.execute("""
        SELECT 
            cheque_number,
            cleared_date,
            amount,
            memo
        FROM cheque_register
        WHERE cleared_date >= '2012-01-01'
        AND cleared_date <= '2012-12-31'
        AND account_number = '0228362'
        AND (payee IS NULL OR payee = '')
        ORDER BY amount DESC
        LIMIT 20
    """)
    
    missing_payee = cur.fetchall()
    if missing_payee:
        print(f"Found {len(missing_payee)} cheques without payee information (showing top 20 by amount):")
        for chq_num, chq_date, amt, memo in missing_payee:
            print(f"  #{chq_num:10} | {chq_date} | ${float(amt):10.2f} | {memo[:50]}")
    else:
        print("[OK] All cheques have payee information")
    
    print("\n" + "="*80)
    print("FINAL STATUS")
    print("="*80)
    
    if registered_count > 0:
        print(f"[OK] SUCCESS: Registered {registered_count} cheques")
    elif skipped_count == len(cheque_transactions):
        print(f"[OK] All {len(cheque_transactions)} cheques already registered")
    else:
        print(f"[WARN]  Partial success: {registered_count} registered, {skipped_count} skipped, {error_count} errors")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
