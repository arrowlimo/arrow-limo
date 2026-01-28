"""
Search for missing Scotia checks in banking records
- Account 0228362 (CIBC) may have relevant data from QB imports
- Check dates != banking clearing dates
- Need exact one-to-one matching
- Check #93 WORD OF LIFE $200 donation must be in banking (not cash)
"""

import os
import psycopg2
from datetime import datetime, timedelta

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

# Missing checks that MUST be in banking
MISSING_CHECKS = {
    22: {'date': None, 'amount': 682.50, 'payee': 'WITH THIS RING', 'desc': 'BRIDAL SHOW @HARVEST CENTRE'},
    41: {'date': None, 'amount': 3993.79, 'payee': 'REVENUE CANADA', 'desc': 'SOURCE DEDUCTIONS'},
    87: {'date': None, 'amount': 1500.00, 'payee': 'JEANNIE SHILLINGTON', 'desc': 'PAYROLL'},
    93: {'date': None, 'amount': 200.00, 'payee': 'WORD OF LIFE', 'desc': 'DONATION'},
    108: {'date': None, 'amount': 564.92, 'payee': 'SHAWN CALLIN', 'desc': 'PAYROLL'},
    117: {'date': None, 'amount': 841.11, 'payee': 'MIKE RICHARD', 'desc': 'PAYROLL'},
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
        print("SEARCH FOR MISSING SCOTIA CHECKS IN BANKING")
        print("=" * 80)
        print("\nKey understanding:")
        print("  - Check dates (issued) != Banking dates (cleared)")
        print("  - ALL checks must be in banking (cannot be cash)")
        print("  - Account 0228362 (CIBC) may have QB-imported data")
        print("  - Scotia account: 903990106011")
        
        # Check both accounts for missing checks
        print("\n" + "=" * 80)
        print("SEARCHING BOTH ACCOUNTS FOR MISSING CHECKS")
        print("=" * 80)
        
        for cheque_num, info in MISSING_CHECKS.items():
            print(f"\n{'=' * 80}")
            print(f"CHECK #{cheque_num}: {info['payee']} - ${info['amount']:,.2f}")
            print(f"Description: {info['desc']}")
            print(f"{'=' * 80}")
            
            # Search by amount (wider range)
            amount = info['amount']
            
            # Search Scotia account
            print(f"\n1. SCOTIA ACCOUNT (903990106011):")
            cur.execute("""
                SELECT 
                    transaction_id,
                    transaction_date,
                    description,
                    debit_amount,
                    credit_amount,
                    vendor_extracted
                FROM banking_transactions
                WHERE account_number = '903990106011'
                AND debit_amount BETWEEN %s AND %s
                ORDER BY ABS(debit_amount - %s), transaction_date
                LIMIT 10
            """, (amount - 10, amount + 10, amount))
            
            scotia_matches = cur.fetchall()
            if scotia_matches:
                print(f"   Found {len(scotia_matches)} potential matches:")
                for tx_id, date, desc, debit, credit, vendor in scotia_matches:
                    print(f"   TX {tx_id:6} | {date} | ${debit:>10,.2f} | {desc[:50]}")
            else:
                print("   ✗ No matches in Scotia account")
            
            # Search CIBC account
            print(f"\n2. CIBC ACCOUNT (0228362):")
            cur.execute("""
                SELECT 
                    transaction_id,
                    transaction_date,
                    description,
                    debit_amount,
                    credit_amount,
                    vendor_extracted
                FROM banking_transactions
                WHERE account_number = '0228362'
                AND debit_amount BETWEEN %s AND %s
                ORDER BY ABS(debit_amount - %s), transaction_date
                LIMIT 10
            """, (amount - 10, amount + 10, amount))
            
            cibc_matches = cur.fetchall()
            if cibc_matches:
                print(f"   Found {len(cibc_matches)} potential matches:")
                for tx_id, date, desc, debit, credit, vendor in cibc_matches:
                    print(f"   TX {tx_id:6} | {date} | ${debit:>10,.2f} | {desc[:50]}")
            else:
                print("   ✗ No matches in CIBC account")
            
            # Search by payee name (fuzzy)
            print(f"\n3. SEARCH BY PAYEE NAME '{info['payee']}':")
            payee_words = info['payee'].split()
            search_terms = ' OR '.join([f"description ILIKE '%{word}%' OR vendor_extracted ILIKE '%{word}%'" for word in payee_words])
            
            cur.execute(f"""
                SELECT 
                    transaction_id,
                    account_number,
                    transaction_date,
                    description,
                    debit_amount,
                    vendor_extracted
                FROM banking_transactions
                WHERE ({search_terms})
                AND debit_amount > 0
                AND transaction_date BETWEEN '2012-01-01' AND '2014-12-31'
                ORDER BY transaction_date
                LIMIT 20
            """)
            
            name_matches = cur.fetchall()
            if name_matches:
                print(f"   Found {len(name_matches)} name matches:")
                for tx_id, acct, date, desc, debit, vendor in name_matches:
                    print(f"   TX {tx_id:6} | {acct} | {date} | ${debit:>10,.2f} | {desc[:40]}")
            else:
                print("   ✗ No name matches found")
            
            # Special search for specific checks
            if cheque_num == 93:  # WORD OF LIFE donation
                print(f"\n4. SPECIAL SEARCH - WORD OF LIFE (donation patterns):")
                cur.execute("""
                    SELECT 
                        transaction_id,
                        account_number,
                        transaction_date,
                        description,
                        debit_amount,
                        vendor_extracted
                    FROM banking_transactions
                    WHERE (
                        description ILIKE '%DONATION%'
                        OR description ILIKE '%CHURCH%'
                        OR description ILIKE '%CHARITY%'
                        OR description ILIKE '%GIFT%'
                    )
                    AND debit_amount BETWEEN 150 AND 250
                    AND transaction_date BETWEEN '2012-01-01' AND '2014-12-31'
                    ORDER BY ABS(debit_amount - 200)
                    LIMIT 10
                """)
                
                donation_matches = cur.fetchall()
                if donation_matches:
                    print(f"   Found {len(donation_matches)} donation-related transactions:")
                    for tx_id, acct, date, desc, debit, vendor in donation_matches:
                        print(f"   TX {tx_id:6} | {acct} | {date} | ${debit:>10,.2f} | {desc[:40]}")
            
            if cheque_num == 41:  # REVENUE CANADA
                print(f"\n4. SPECIAL SEARCH - REVENUE CANADA (tax payments):")
                cur.execute("""
                    SELECT 
                        transaction_id,
                        account_number,
                        transaction_date,
                        description,
                        debit_amount,
                        vendor_extracted
                    FROM banking_transactions
                    WHERE (
                        description ILIKE '%REVENUE CANADA%'
                        OR description ILIKE '%CRA%'
                        OR description ILIKE '%TAX%'
                        OR description ILIKE '%SOURCE DEDUCTION%'
                        OR vendor_extracted ILIKE '%REVENUE CANADA%'
                    )
                    AND debit_amount BETWEEN 3500 AND 4500
                    AND transaction_date BETWEEN '2012-01-01' AND '2014-12-31'
                    ORDER BY ABS(debit_amount - 3993.79)
                    LIMIT 10
                """)
                
                tax_matches = cur.fetchall()
                if tax_matches:
                    print(f"   Found {len(tax_matches)} tax-related transactions:")
                    for tx_id, acct, date, desc, debit, vendor in tax_matches:
                        print(f"   TX {tx_id:6} | {acct} | {date} | ${debit:>10,.2f} | {desc[:40]}")
        
        # Summary of QB-imported data in CIBC account
        print("\n" + "=" * 80)
        print("CIBC ACCOUNT (0228362) QB IMPORT ANALYSIS")
        print("=" * 80)
        
        # Check for duplicates/triplicates in CIBC
        cur.execute("""
            SELECT 
                transaction_date,
                debit_amount,
                description,
                COUNT(*) as occurrence_count,
                ARRAY_AGG(transaction_id) as tx_ids
            FROM banking_transactions
            WHERE account_number = '0228362'
            AND debit_amount > 0
            AND transaction_date BETWEEN '2012-01-01' AND '2014-12-31'
            GROUP BY transaction_date, debit_amount, description
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC, debit_amount DESC
            LIMIT 20
        """)
        
        duplicates = cur.fetchall()
        print(f"\nFound {len(duplicates)} duplicate/triplicate patterns in CIBC:")
        for date, amount, desc, count, tx_ids in duplicates:
            print(f"  {date} | ${amount:>10,.2f} | {count}x | TXs: {tx_ids} | {desc[:40]}")
        
        # Final recommendations
        print("\n" + "=" * 80)
        print("RECOMMENDATIONS")
        print("=" * 80)
        
        print("\n1. ONE-TO-ONE MATCHING STRATEGY:")
        print("   - Review each transaction above")
        print("   - Match by amount (exact or within $5)")
        print("   - Verify payee name in description")
        print("   - Remember: Check date != Banking clear date")
        print("   - ALL checks must have a banking transaction")
        
        print("\n2. UPDATE CHEQUE REGISTER:")
        print("   For each match found, run:")
        print("   UPDATE cheque_register SET")
        print("     banking_transaction_id = [TX_ID],")
        print("     cheque_date = [BANKING_DATE]")
        print("   WHERE cheque_number = [CHECK_NUM];")
        
        print("\n3. NEXT ACTION:")
        print("   Review the matches above and provide:")
        print("   - Which TX ID matches which check number")
        print("   - Any remaining unmatched checks for further investigation")
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
