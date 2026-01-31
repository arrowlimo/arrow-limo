"""
Analyze gaps in cheque register and search QuickBooks data for missing information
- Identify checks without TX IDs
- Search QB journal/GL for matching check numbers
- Search banking_transactions for check references
- Report what's found and what's still missing
"""

import os
import psycopg2
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

# Gaps from user's data
GAPS = {
    10: {'amount': 0.00, 'payee': 'NOT ISSUED', 'reason': 'Not issued'},
    22: {'amount': 682.50, 'payee': 'WITH THIS RING', 'reason': 'No TX ID'},
    25: {'amount': 1475.25, 'payee': 'HEFFNER AUTO', 'reason': 'No date/TX ID'},
    26: {'amount': 1475.25, 'payee': 'HEFFNER AUTO', 'reason': 'No date/TX ID'},
    27: {'amount': 1475.25, 'payee': 'HEFFNER AUTO', 'reason': 'No date/TX ID'},
    28: {'amount': 1475.25, 'payee': 'HEFFNER AUTO', 'reason': 'No date/TX ID'},
    33: {'amount': 2525.25, 'payee': 'HEFFNER AUTO', 'reason': 'No date/TX ID'},
    41: {'amount': 3993.79, 'payee': 'REVENUE CANADA', 'reason': 'No date/TX ID'},
    87: {'amount': 1500.00, 'payee': 'JEANNIE SHILLINGTON', 'reason': 'No date/TX ID'},
    92: {'amount': 613.00, 'payee': 'TREDD MAYFAIR', 'reason': 'VOID'},
    93: {'amount': 200.00, 'payee': 'WORD OF LIFE', 'reason': 'DONATION - No TX ID'},
    94: {'amount': 1885.65, 'payee': 'JACK CARTER', 'reason': 'Duplicate of #95?'},
    108: {'amount': 564.92, 'payee': 'SHAWN CALLIN', 'reason': 'No date/TX ID'},
    117: {'amount': 841.11, 'payee': 'MIKE RICHARD', 'reason': 'No date/TX ID'},
}

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    try:
        print("=" * 80)
        print("CHEQUE REGISTER GAP ANALYSIS")
        print("=" * 80)
        
        print(f"\nIdentified gaps: {len(GAPS)} checks without banking TX IDs")
        print("\nGap Summary:")
        total_gap_amount = sum(g['amount'] for g in GAPS.values())
        print(f"  Total amount in gaps: ${total_gap_amount:,.2f}")
        
        # Check what QB tables exist
        print("\n" + "=" * 80)
        print("STEP 1: Check available QuickBooks tables")
        print("=" * 80)
        
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND (table_name LIKE '%qb%' OR table_name LIKE '%quickbooks%' 
                 OR table_name = 'journal' OR table_name = 'unified_general_ledger')
            ORDER BY table_name
        """)
        qb_tables = [row[0] for row in cur.fetchall()]
        
        print(f"Found {len(qb_tables)} QB-related tables:")
        for table in qb_tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"  - {table}: {count:,} rows")
        
        # Search banking_transactions for check references
        print("\n" + "=" * 80)
        print("STEP 2: Search banking_transactions for check references")
        print("=" * 80)
        
        found_in_banking = {}
        for cheque_num, info in GAPS.items():
            # Search for check number in description
            cur.execute("""
                SELECT 
                    transaction_id,
                    account_number,
                    transaction_date,
                    description,
                    debit_amount,
                    credit_amount,
                    vendor_extracted
                FROM banking_transactions
                WHERE (
                    description ILIKE %s 
                    OR description ILIKE %s
                    OR description ILIKE %s
                )
                AND account_number IN ('903990106011', '0228362')
                ORDER BY transaction_date
            """, (f'%CHQ {cheque_num}%', f'%CHEQUE {cheque_num}%', f'%CHECK {cheque_num}%'))
            
            matches = cur.fetchall()
            if matches:
                found_in_banking[cheque_num] = matches
        
        print(f"\nFound {len(found_in_banking)} checks in banking_transactions:")
        for cheque_num, matches in found_in_banking.items():
            print(f"\n  Cheque #{cheque_num}: {GAPS[cheque_num]['payee']} (${GAPS[cheque_num]['amount']:,.2f})")
            for tx_id, acct, date, desc, debit, credit, vendor in matches:
                amount = debit if debit else credit
                print(f"    TX {tx_id} | {date} | {acct} | ${amount:,.2f} | {desc[:60]}")
        
        # Search journal for check numbers
        print("\n" + "=" * 80)
        print("STEP 3: Search journal table for check references")
        print("=" * 80)
        
        if 'journal' in qb_tables:
            found_in_journal = {}
            for cheque_num, info in GAPS.items():
                cur.execute("""
                    SELECT 
                        id,
                        transaction_date,
                        description,
                        debit_amount,
                        credit_amount,
                        account_name,
                        source_system
                    FROM journal
                    WHERE (
                        description ILIKE %s 
                        OR description ILIKE %s
                        OR description ILIKE %s
                    )
                    ORDER BY transaction_date
                """, (f'%CHQ {cheque_num}%', f'%CHEQUE {cheque_num}%', f'%CHECK {cheque_num}%'))
                
                matches = cur.fetchall()
                if matches:
                    found_in_journal[cheque_num] = matches
            
            print(f"\nFound {len(found_in_journal)} checks in journal:")
            for cheque_num, matches in found_in_journal.items():
                print(f"\n  Cheque #{cheque_num}: {GAPS[cheque_num]['payee']} (${GAPS[cheque_num]['amount']:,.2f})")
                for j_id, date, desc, debit, credit, account, source in matches:
                    amount = debit if debit else credit
                    print(f"    ID {j_id} | {date} | {account} | ${amount:,.2f} | {desc[:50]}")
        
        # Search unified_general_ledger
        print("\n" + "=" * 80)
        print("STEP 4: Search unified_general_ledger for check references")
        print("=" * 80)
        
        if 'unified_general_ledger' in qb_tables:
            found_in_gl = {}
            for cheque_num, info in GAPS.items():
                cur.execute("""
                    SELECT 
                        id,
                        transaction_date,
                        description,
                        debit_amount,
                        credit_amount,
                        account_name,
                        source_system
                    FROM unified_general_ledger
                    WHERE (
                        description ILIKE %s 
                        OR description ILIKE %s
                        OR description ILIKE %s
                    )
                    ORDER BY transaction_date
                """, (f'%CHQ {cheque_num}%', f'%CHEQUE {cheque_num}%', f'%CHECK {cheque_num}%'))
                
                matches = cur.fetchall()
                if matches:
                    found_in_gl[cheque_num] = matches
            
            print(f"\nFound {len(found_in_gl)} checks in unified_general_ledger:")
            for cheque_num, matches in found_in_gl.items():
                print(f"\n  Cheque #{cheque_num}: {GAPS[cheque_num]['payee']} (${GAPS[cheque_num]['amount']:,.2f})")
                for gl_id, date, desc, debit, credit, account, source in matches:
                    amount = debit if debit else credit
                    print(f"    ID {gl_id} | {date} | {account} | ${amount:,.2f} | {desc[:50]}")
        
        # Search by amount and payee (fuzzy matching)
        print("\n" + "=" * 80)
        print("STEP 5: Search by amount + payee (fuzzy matching)")
        print("=" * 80)
        
        amount_matches = {}
        for cheque_num, info in GAPS.items():
            if info['amount'] == 0:
                continue
            
            amount = info['amount']
            payee_words = info['payee'].split()[:2]  # First 2 words
            
            # Search banking
            cur.execute("""
                SELECT 
                    transaction_id,
                    transaction_date,
                    description,
                    debit_amount,
                    vendor_extracted
                FROM banking_transactions
                WHERE debit_amount BETWEEN %s AND %s
                AND account_number IN ('903990106011', '0228362')
                AND transaction_date >= '2012-01-01' AND transaction_date <= '2013-12-31'
                ORDER BY ABS(debit_amount - %s)
                LIMIT 5
            """, (amount - 0.50, amount + 0.50, amount))
            
            banking_matches = cur.fetchall()
            
            if banking_matches:
                # Filter by payee name match
                relevant = []
                for tx_id, date, desc, debit, vendor in banking_matches:
                    desc_upper = desc.upper() if desc else ''
                    vendor_upper = vendor.upper() if vendor else ''
                    if any(word.upper() in desc_upper or word.upper() in vendor_upper for word in payee_words):
                        relevant.append((tx_id, date, desc, debit, vendor))
                
                if relevant:
                    amount_matches[cheque_num] = relevant
        
        print(f"\nFound {len(amount_matches)} checks by amount+payee matching:")
        for cheque_num, matches in amount_matches.items():
            print(f"\n  Cheque #{cheque_num}: {GAPS[cheque_num]['payee']} (${GAPS[cheque_num]['amount']:,.2f})")
            for tx_id, date, desc, debit, vendor in matches:
                print(f"    TX {tx_id} | {date} | ${debit:,.2f} | {desc[:50]}")
        
        # Final summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        
        found_checks = set(found_in_banking.keys()) | set(amount_matches.keys())
        still_missing = set(GAPS.keys()) - found_checks
        
        print(f"\nTotal gaps identified: {len(GAPS)}")
        print(f"Found in banking/QB data: {len(found_checks)}")
        print(f"Still missing: {len(still_missing)}")
        
        if still_missing:
            print("\nStill missing TX IDs:")
            missing_amount = 0
            for cheque_num in sorted(still_missing):
                info = GAPS[cheque_num]
                print(f"  Cheque #{cheque_num}: {info['payee']:30} ${info['amount']:>10,.2f} ({info['reason']})")
                missing_amount += info['amount']
            print(f"\nTotal missing amount: ${missing_amount:,.2f}")
        
        if found_checks:
            print("\n" + "=" * 80)
            print("RECOMMENDED ACTION: Update cheque register with found TX IDs")
            print("=" * 80)
            print("\nCreate update script with:")
            for cheque_num in sorted(found_checks):
                if cheque_num in found_in_banking:
                    tx_id = found_in_banking[cheque_num][0][0]
                    date = found_in_banking[cheque_num][0][2]
                    print(f"  UPDATE cheque_register SET banking_transaction_id = {tx_id}, cheque_date = '{date}' WHERE cheque_number = {cheque_num};")
                elif cheque_num in amount_matches:
                    tx_id = amount_matches[cheque_num][0][0]
                    date = amount_matches[cheque_num][0][1]
                    print(f"  -- VERIFY: UPDATE cheque_register SET banking_transaction_id = {tx_id}, cheque_date = '{date}' WHERE cheque_number = {cheque_num};")
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
