#!/usr/bin/env python
"""
Analyze LMS Deposit payment keys to understand bulk deposit structure.
These are 22,033 payments totaling $9.5M that need allocation to charters.
"""
import psycopg2
import re


def get_conn():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***",
    )


def main():
    conn = get_conn()
    cur = conn.cursor()
    
    print("=" * 80)
    print("LMS DEPOSIT ANALYSIS")
    print("=" * 80)
    
    # Get all LMS deposit payments
    cur.execute("""
        SELECT p.payment_id, p.payment_key, p.account_number,
               COALESCE(p.payment_amount, p.amount) AS amt,
               p.payment_date, p.payment_method, p.notes
        FROM payments p
        WHERE p.payment_key LIKE 'LMSDEP:%'
        AND NOT EXISTS (
            SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
        )
        ORDER BY amt DESC
    """)
    
    lms_deposits = cur.fetchall()
    print(f"\nLMS Deposit payments: {len(lms_deposits):,}")
    print(f"Total amount: ${sum(float(row[3]) if row[3] else 0 for row in lms_deposits):,.2f}")
    
    # Parse payment_key structure: LMSDEP:{deposit_number}:{reserve_number}
    deposits_by_number = {}
    has_reserve = []
    no_reserve = []
    
    for row in lms_deposits:
        pid, key, account, amt, date, method, notes = row
        
        # Parse key: LMSDEP:0005768:004859
        parts = key.split(':')
        if len(parts) >= 3:
            deposit_num = parts[1]
            reserve_ref = parts[2]
            
            if deposit_num not in deposits_by_number:
                deposits_by_number[deposit_num] = []
            deposits_by_number[deposit_num].append(row)
            
            # Check if reserve_ref looks like a reserve number
            if reserve_ref and reserve_ref not in ['NA', 'uncollectable', '']:
                has_reserve.append((row, reserve_ref))
            else:
                no_reserve.append(row)
    
    print("\n" + "=" * 80)
    print("DEPOSIT BATCH STRUCTURE")
    print("=" * 80)
    print(f"\nUnique deposit batches: {len(deposits_by_number):,}")
    print(f"Payments with reserve reference: {len(has_reserve):,}")
    print(f"Payments without reserve reference: {len(no_reserve):,}")
    
    # Show largest deposit batches
    print("\nLargest deposit batches (top 10):")
    sorted_deposits = sorted(deposits_by_number.items(), 
                            key=lambda x: len(x[1]), reverse=True)
    
    for deposit_num, payments in sorted_deposits[:10]:
        total_amt = sum(float(p[3]) if p[3] else 0 for p in payments)
        print(f"\n  Deposit {deposit_num}: {len(payments):,} payments, ${total_amt:,.2f}")
        # Show sample
        for p in payments[:3]:
            pid, key, account, amt, date, method, notes = p
            reserve_ref = key.split(':')[2] if len(key.split(':')) >= 3 else 'N/A'
            print(f"    PID {pid}: ${float(amt):,.2f}, reserve_ref={reserve_ref}")
        if len(payments) > 3:
            print(f"    ... and {len(payments) - 3} more")
    
    # Check how many reserve references exist as charters
    print("\n" + "=" * 80)
    print("RESERVE REFERENCE VALIDATION")
    print("=" * 80)
    
    valid_reserves = []
    invalid_reserves = []
    
    for (row, reserve_ref) in has_reserve[:1000]:  # Sample 1000
        # Try to find charter
        # Reserve ref might be old format (004859) - need to check both formats
        cur.execute("""
            SELECT charter_id, reserve_number FROM charters 
            WHERE reserve_number = %s 
            OR reserve_number = %s
            OR reserve_number::text LIKE %s
        """, (reserve_ref, f"00{reserve_ref}", f"%{reserve_ref}%"))
        
        result = cur.fetchone()
        if result:
            valid_reserves.append((row, reserve_ref, result))
        else:
            invalid_reserves.append((row, reserve_ref))
    
    print(f"\nSampled {len(has_reserve[:1000]):,} payments with reserve references:")
    print(f"  Found matching charter: {len(valid_reserves):,}")
    print(f"  No matching charter: {len(invalid_reserves):,}")
    
    if valid_reserves:
        print("\nSample valid reserve matches (first 10):")
        for (row, reserve_ref, charter) in valid_reserves[:10]:
            pid, key, account, amt, date, method, notes = row
            charter_id, reserve_number = charter
            print(f"  PID {pid}: ref={reserve_ref} → Charter {reserve_number} (${float(amt):,.2f})")
    
    if invalid_reserves:
        print("\nSample invalid reserve references (first 10):")
        for (row, reserve_ref) in invalid_reserves[:10]:
            pid, key, account, amt, date, method, notes = row
            print(f"  PID {pid}: ref={reserve_ref} (${float(amt):,.2f}) - charter not found")
    
    # Check bulk deposits (single payment, large amount)
    print("\n" + "=" * 80)
    print("BULK UNALLOCATED DEPOSITS")
    print("=" * 80)
    
    bulk_unallocated = [row for row in lms_deposits if float(row[3] or 0) > 5000]
    print(f"\nPayments >$5K: {len(bulk_unallocated):,}")
    
    for row in bulk_unallocated[:10]:
        pid, key, account, amt, date, method, notes = row
        reserve_ref = key.split(':')[2] if len(key.split(':')) >= 3 else 'N/A'
        print(f"\n  PID {pid}: ${float(amt):,.2f} on {date}")
        print(f"    Reserve ref: {reserve_ref}")
        print(f"    Notes: {notes[:100] if notes else 'None'}")
    
    # Summary
    print("\n" + "=" * 80)
    print("MATCHING STRATEGY RECOMMENDATIONS")
    print("=" * 80)
    
    estimate_valid = int(len(has_reserve) * (len(valid_reserves) / len(has_reserve[:1000])))
    
    print(f"\n1. Auto-match by reserve_reference: ~{estimate_valid:,} payments")
    print("   - Parse LMSDEP:{deposit}:{reserve} format")
    print("   - Match reserve to charter (fuzzy match for old format)")
    print("   - Apply payment to matched charter")
    
    print(f"\n2. Bulk deposits needing manual allocation: {len(bulk_unallocated):,} payments (${sum(float(r[3] or 0) for r in bulk_unallocated):,.2f})")
    print("   - Review deposit notes for allocation instructions")
    print("   - May need to split across multiple charters")
    print("   - Check for 'uncollectable' or 'write-off' markers")
    
    print(f"\n3. Unallocated deposit pool: {len(no_reserve):,} payments")
    print("   - Deposit batches without reserve references")
    print("   - May need deposit register from LMS system")
    print("   - Consider as general revenue/unallocated")
    
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
