"""
Correct Check #22 - it's actually a Heffner check $1,475.25 in Aug (not WITH THIS RING $682.50)
Search for Heffner $1,475.25 on Aug 13 or Aug 23, 2012
Then run the main Scotia cheque register import with all corrections
"""

import os
import psycopg2
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

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
        print("CORRECT CHECK #22: ACTUALLY HEFFNER $1,475.25 (NOT WITH THIS RING)")
        print("=" * 80)
        
        # Search for Heffner $1,475.25 in Aug 2012 (Aug 13 or 23)
        print("\nSearching for Heffner checks $1,475.25 in August 2012:")
        
        cur.execute("""
            SELECT 
                transaction_id,
                transaction_date,
                description,
                debit_amount,
                vendor_extracted
            FROM banking_transactions
            WHERE account_number = '903990106011'
            AND debit_amount = 1475.25
            AND (description ILIKE '%HEFFNER%' OR vendor_extracted ILIKE '%HEFFNER%')
            AND transaction_date BETWEEN '2012-08-01' AND '2012-08-31'
            ORDER BY transaction_date
        """)
        
        heffner_matches = cur.fetchall()
        print(f"\nFound {len(heffner_matches)} Heffner checks for $1,475.25 in Aug 2012:")
        for tx_id, date, desc, amount, vendor in heffner_matches:
            print(f"  TX {tx_id:6} | {date} | ${amount:>10,.2f} | {desc[:50]}")
            if 'CHQ' in desc.upper():
                chq_num = desc.upper().split('CHQ')[-1].strip()[:3]
                print(f"           Check number from description: CHQ {chq_num}")
        
        if heffner_matches:
            # Use the first match
            tx_id, date, desc, amount, vendor = heffner_matches[0]
            print(f"\n✓ Using TX {tx_id} ({date}) for Check #22")
            print(f"  Corrected: Check #22 = Heffner $1,475.25 (not WITH THIS RING $682.50)")
        else:
            print("\n⚠️  No Heffner $1,475.25 checks found in Aug 2012")
            print("   Searching broader range...")
            
            cur.execute("""
                SELECT 
                    transaction_id,
                    transaction_date,
                    description,
                    debit_amount
                FROM banking_transactions
                WHERE account_number = '903990106011'
                AND debit_amount = 1475.25
                AND (description ILIKE '%HEFFNER%' OR description ILIKE '%CHQ 22%' OR description ILIKE '%CHQ 23%')
                AND transaction_date BETWEEN '2012-07-01' AND '2012-10-31'
                ORDER BY transaction_date
            """)
            
            broader_matches = cur.fetchall()
            if broader_matches:
                print(f"\n  Found {len(broader_matches)} broader matches:")
                for tx_id, date, desc, amount in broader_matches:
                    print(f"  TX {tx_id:6} | {date} | ${amount:>10,.2f} | {desc[:50]}")
        
        # Summary for Check #93
        print("\n" + "=" * 80)
        print("CHECK #93: WORD OF LIFE DONATION - MARK AS VOID")
        print("=" * 80)
        print("\nNo clear banking match found for check #93 ($200 donation)")
        print("✓ Will mark as VOID in import (no banking_transaction_id)")
        
        # Now show what will be imported
        print("\n" + "=" * 80)
        print("FINAL CHEQUE REGISTER CORRECTIONS")
        print("=" * 80)
        
        corrections = {
            22: "HEFFNER AUTO (L-9) $1,475.25 - TX TBD",
            93: "WORD OF LIFE (VOID - no TX ID)",
            108: "SHAWN COLLIN $564.92 - TX 80227",
            117: "MIKE RICHARD $841.11 - TX 77696",
        }
        
        print("\nCorrected entries:")
        for chq_num, info in sorted(corrections.items()):
            print(f"  Check #{chq_num:3}: {info}")
        
        print("\n" + "=" * 80)
        print("READY TO RUN MAIN IMPORT")
        print("=" * 80)
        print("\nThe import_scotia_cheque_register.py script will:")
        print("  ✓ Import all 117 checks into cheque_register table")
        print("  ✓ Link to banking_transactions via TX IDs")
        print("  ✓ Fill missing dates from banking records")
        print("  ✓ Create receipts for all checks with TX IDs")
        print("  ✓ Assign GL codes based on payee patterns")
        print("  ✓ Mark NSF and VOID checks appropriately")
        print("\nRun: python scripts/import_scotia_cheque_register.py")
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
