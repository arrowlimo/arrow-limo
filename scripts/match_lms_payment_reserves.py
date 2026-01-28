#!/usr/bin/env python3
"""
Match LMS Payment table (24,587 records with Reserve_No) to PostgreSQL payments.

LMS Payment structure:
- PaymentID: LMS payment identifier  
- Reserve_No: 6-digit charter number
- Account_No: Customer account
- Amount: Payment amount
- Key: Payment key/reference

We need to find matching payments in PostgreSQL and restore reserve_number linkage.
"""

import pyodbc
import psycopg2
from decimal import Decimal

LMS_PATH = r'L:\New folder\lms.mdb'

def normalize_reserve(reserve):
    """Normalize reserve number to 6 digits"""
    if not reserve:
        return None
    reserve = str(reserve).strip()
    if reserve and reserve.isdigit():
        return reserve.zfill(6)
    return None

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', default=True)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    
    if args.write:
        args.dry_run = False
    
    print("="*80)
    print("MATCH LMS PAYMENT RESERVE_NO TO POSTGRESQL")
    print("="*80)
    print(f"\nMode: {'✍️  WRITE' if not args.dry_run else '🔍 DRY RUN'}")
    
    # Connect to LMS
    print(f"\n📂 Connecting to LMS...")
    lms_conn = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')
    lms_cur = lms_conn.cursor()
    
    # Extract LMS payments with reserve numbers
    print(f"📥 Extracting LMS Payment table...")
    lms_cur.execute("""
        SELECT PaymentID, Reserve_No, Account_No, Amount, Key
        FROM Payment
        WHERE Reserve_No IS NOT NULL
    """)
    
    lms_payments = {}
    for row in lms_cur.fetchall():
        payment_id = row[0]
        reserve = normalize_reserve(row[1])
        account = row[2]
        amount = float(row[3]) if row[3] else None
        key = row[4]
        
        if reserve:
            lms_payments[payment_id] = {
                'reserve': reserve,
                'account': account,
                'amount': amount,
                'key': key
            }
    
    lms_cur.close()
    lms_conn.close()
    
    print(f"   Extracted {len(lms_payments):,} LMS payments with Reserve_No")
    
    # Connect to PostgreSQL
    print(f"\n🐘 Connecting to PostgreSQL...")
    pg_conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    pg_cur = pg_conn.cursor()
    
    # Get PostgreSQL payments missing reserve_number
    print(f"📊 Checking PostgreSQL payments...")
    pg_cur.execute("""
        SELECT payment_id, amount, payment_date, payment_key, account_number
        FROM payments
        WHERE reserve_number IS NULL
    """)
    
    pg_missing = {}
    for row in pg_cur.fetchall():
        pg_missing[row[0]] = {
            'amount': float(row[1]) if row[1] else None,
            'date': row[2],
            'key': row[3],
            'account': row[4]
        }
    
    print(f"   PostgreSQL has {len(pg_missing):,} payments missing reserve_number")
    
    # Match by payment_id (direct match if IDs align)
    print(f"\n🔍 Matching LMS → PostgreSQL...")
    
    direct_matches = []
    amount_matches = []
    key_matches = []
    
    for lms_id, lms_data in lms_payments.items():
        # Strategy 1: Direct payment_id match
        if lms_id in pg_missing:
            pg_data = pg_missing[lms_id]
            # Verify amounts match (within $0.01)
            if lms_data['amount'] and pg_data['amount']:
                if abs(lms_data['amount'] - pg_data['amount']) < 0.01:
                    direct_matches.append((lms_id, lms_data['reserve'], 'direct_id'))
                    continue
        
        # Strategy 2: Match by amount + key
        if lms_data['key']:
            for pg_id, pg_data in pg_missing.items():
                if pg_data['key'] == lms_data['key']:
                    if lms_data['amount'] and pg_data['amount']:
                        if abs(lms_data['amount'] - pg_data['amount']) < 0.01:
                            key_matches.append((pg_id, lms_data['reserve'], 'key_match'))
                            break
    
    total_matches = len(direct_matches) + len(key_matches) + len(amount_matches)
    
    print(f"\n📈 Match results:")
    print(f"   Direct ID matches: {len(direct_matches):,}")
    print(f"   Key matches: {len(key_matches):,}")
    print(f"   Amount matches: {len(amount_matches):,}")
    print(f"   Total matches: {total_matches:,}")
    
    # Apply matches
    if total_matches > 0:
        all_matches = direct_matches + key_matches + amount_matches
        
        if args.dry_run:
            print(f"\n📋 Sample matches (first 30):")
            for pg_id, reserve, strategy in all_matches[:30]:
                print(f"   Payment {pg_id} → Reserve {reserve} ({strategy})")
            if len(all_matches) > 30:
                print(f"   ... and {len(all_matches) - 30:,} more")
        else:
            print(f"\n💾 Applying {total_matches:,} matches...")
            update_count = 0
            for pg_id, reserve, strategy in all_matches:
                pg_cur.execute("""
                    UPDATE payments
                    SET reserve_number = %s
                    WHERE payment_id = %s
                """, (reserve, pg_id))
                update_count += 1
                
                if update_count % 100 == 0:
                    print(f"   Updated {update_count:,} payments...")
            
            pg_conn.commit()
            print(f"\n✅ Committed {update_count:,} reserve_number updates")
            
            # Verify
            pg_cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(reserve_number) as with_reserve
                FROM payments
            """)
            total, with_reserve = pg_cur.fetchone()
            
            print(f"\n📊 NEW STATE:")
            print(f"   Total payments: {total:,}")
            print(f"   With reserve: {with_reserve:,} ({with_reserve/total*100:.1f}%)")
            print(f"   Missing: {total - with_reserve:,} ({(total-with_reserve)/total*100:.1f}%)")
    else:
        print(f"\n⚠️  No matches found - payment IDs may not align between LMS and PostgreSQL")
        print(f"\n💡 Need alternative matching strategy:")
        print(f"   - Match by amount + date range")
        print(f"   - Match by payment_key (ETR: references)")
        print(f"   - Match by account_number + amount")
    
    pg_cur.close()
    pg_conn.close()
    
    print("\n" + "="*80)
    print("COMPLETE")
    print("="*80)
    
    if args.dry_run and total_matches > 0:
        print(f"\n💡 Run with --write to apply matches")

if __name__ == '__main__':
    main()
