"""
Update confirmed check matches and investigate remaining gaps
- Check #108: TX 80227 (SHAWN COLLIN) - CONFIRMED
- Check #117: TX 77696 (CHQ 114 $841.00) - CONFIRMED
- Check #22: Investigate WITH THIS RING
- Check #93: Investigate WORD OF LIFE donation
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
        print("UPDATE CONFIRMED CHECKS AND INVESTIGATE REMAINING")
        print("=" * 80)
        
        # Step 1: Update confirmed matches
        print("\n" + "=" * 80)
        print("STEP 1: Update Confirmed Matches")
        print("=" * 80)
        
        confirmed_updates = [
            (108, 80227, '2014-06-03', 'SHAWN COLLIN (misspelled as CALLIN in register)'),
            (117, 77696, '2013-01-03', 'CHQ 114 - $841.00 (close to $841.11)'),
        ]
        
        # First check if cheque_register table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'cheque_register'
            )
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            print("⚠️  cheque_register table doesn't exist yet")
            print("   Will be created by main import script")
            print("   Skipping updates for now\n")
        else:
            for cheque_num, tx_id, date_str, note in confirmed_updates:
                print(f"\nCheck #{cheque_num}: TX {tx_id} ({note})")
                
                # Check if cheque_register record exists (cast to VARCHAR)
                cur.execute("SELECT id FROM cheque_register WHERE cheque_number::text = %s", (str(cheque_num),))
                exists = cur.fetchone()
                
                if exists:
                    cur.execute("""
                        UPDATE cheque_register
                        SET banking_transaction_id = %s,
                            cheque_date = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE cheque_number::text = %s
                    """, (tx_id, date_str, str(cheque_num)))
                    print(f"  ✓ Updated cheque_register: TX {tx_id}, date {date_str}")
                else:
                    print(f"  ⚠️  Cheque #{cheque_num} not in register yet - will be added by main import")
        
        conn.commit()
        print(f"\n✓ Confirmed matches ready for import")
        
        # Step 2: Deep investigation of Check #22
        print("\n" + "=" * 80)
        print("STEP 2: Investigate Check #22 - WITH THIS RING $682.50")
        print("=" * 80)
        
        print("\nFound earlier: Cheque #213 'With This Ring Brida' $1,050 (Feb 2012)")
        print("But register shows Check #22 as $682.50")
        print("\n⚠️  AMOUNT MISMATCH - Possible explanations:")
        print("  1. Check #22 was NSF/VOID and amount changed")
        print("  2. Handwriting error: $682.50 vs actual amount")
        print("  3. Different check entirely (not #22)")
        
        # Search for $682.50 in Scotia around Sept 2012 (when other L-9 checks cleared)
        print("\nSearching Scotia for $682.50 around Sept 2012:")
        cur.execute("""
            SELECT 
                transaction_id,
                transaction_date,
                description,
                debit_amount
            FROM banking_transactions
            WHERE account_number = '903990106011'
            AND debit_amount = 682.50
            ORDER BY transaction_date
        """)
        
        exact_matches = cur.fetchall()
        if exact_matches:
            print(f"  Found {len(exact_matches)} exact $682.50 matches:")
            for tx_id, date, desc, amount in exact_matches:
                print(f"  TX {tx_id:6} | {date} | ${amount:>10,.2f} | {desc}")
        else:
            print("  ✗ No exact $682.50 matches in Scotia")
        
        # Search CIBC for $682.50 around 2012
        print("\nSearching CIBC for $682.50 around 2012:")
        cur.execute("""
            SELECT 
                transaction_id,
                transaction_date,
                description,
                debit_amount
            FROM banking_transactions
            WHERE account_number = '0228362'
            AND debit_amount = 682.50
            AND transaction_date BETWEEN '2012-01-01' AND '2013-12-31'
            ORDER BY transaction_date
        """)
        
        cibc_matches = cur.fetchall()
        if cibc_matches:
            print(f"  Found {len(cibc_matches)} exact $682.50 matches in CIBC:")
            for tx_id, date, desc, amount in cibc_matches:
                print(f"  TX {tx_id:6} | {date} | ${amount:>10,.2f} | {desc}")
        else:
            print("  ✗ No $682.50 matches in CIBC 2012")
        
        # Step 3: Deep investigation of Check #93
        print("\n" + "=" * 80)
        print("STEP 3: Investigate Check #93 - WORD OF LIFE $200 DONATION")
        print("=" * 80)
        
        print("\nCheck #93 marked as DONATION - must be in banking (not cash)")
        print("Searching for $200 transactions with donation/church/charity keywords:")
        
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
                OR description ILIKE '%WORD%'
                OR description ILIKE '%LIFE%'
                OR vendor_extracted ILIKE '%DONATION%'
                OR vendor_extracted ILIKE '%CHURCH%'
                OR vendor_extracted ILIKE '%WORD%'
            )
            AND debit_amount BETWEEN 180 AND 220
            AND transaction_date BETWEEN '2012-01-01' AND '2013-12-31'
            ORDER BY transaction_date
        """)
        
        donation_matches = cur.fetchall()
        if donation_matches:
            print(f"  Found {len(donation_matches)} potential donation matches:")
            for tx_id, acct, date, desc, amount, vendor in donation_matches:
                print(f"  TX {tx_id:6} | {acct} | {date} | ${amount:>8,.2f} | {desc[:50]}")
        else:
            print("  ✗ No donation-related transactions found")
        
        # Search for exact $200 in Scotia around Nov-Dec 2012
        print("\nSearching for $200 in Scotia around Nov-Dec 2012 (when check would have cleared):")
        cur.execute("""
            SELECT 
                transaction_id,
                transaction_date,
                description,
                debit_amount,
                vendor_extracted
            FROM banking_transactions
            WHERE account_number = '903990106011'
            AND debit_amount = 200.00
            AND transaction_date BETWEEN '2012-11-01' AND '2012-12-31'
            ORDER BY transaction_date
        """)
        
        nov_dec_200 = cur.fetchall()
        if nov_dec_200:
            print(f"  Found {len(nov_dec_200)} $200 transactions in Nov-Dec 2012:")
            for tx_id, date, desc, amount, vendor in nov_dec_200:
                print(f"  TX {tx_id:6} | {date} | ${amount:>8,.2f} | {desc}")
                print(f"         Vendor: {vendor if vendor else 'N/A'}")
        else:
            print("  ✗ No $200 transactions in Nov-Dec 2012")
        
        # Final recommendations
        print("\n" + "=" * 80)
        print("RECOMMENDATIONS")
        print("=" * 80)
        
        print("\n✅ COMPLETED UPDATES:")
        print("  Check #108: TX 80227 - SHAWN COLLIN (CALLIN misspelled)")
        print("  Check #117: TX 77696 - CHQ 114 $841.00")
        
        print("\n⚠️  NEEDS MANUAL REVIEW:")
        print("\n  Check #22: WITH THIS RING $682.50")
        if exact_matches:
            print(f"    → Review TX {exact_matches[0][0]} ({exact_matches[0][1]}) as possible match")
        else:
            print("    → Amount may be wrong in register")
            print("    → Check if it's actually $1,050 (Cheque #213)")
            print("    → Or check was VOID/NSF and amount changed")
        
        print("\n  Check #93: WORD OF LIFE $200 DONATION")
        if nov_dec_200:
            print("    → Review these $200 transactions from Nov-Dec 2012:")
            for tx_id, date, desc, amount, vendor in nov_dec_200[:3]:
                print(f"      TX {tx_id} ({date}): {desc[:50]}")
        else:
            print("    → Check may have been VOID")
            print("    → Or cleared in different month")
            print("    → Search QB journal for donation entry")
        
        print("\n" + "=" * 80)
        print("NEXT STEPS:")
        print("=" * 80)
        print("1. Verify Check #22 actual amount (is it $682.50 or $1,050?)")
        print("2. Search QB journal for 'Word of Life' donation")
        print("3. Check if #93 was VOID (marked in register)")
        print("4. Run main Scotia import script with all data")
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
