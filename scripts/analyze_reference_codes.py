#!/usr/bin/env python
"""
Check if unmatched payments have reference codes (like #ACc4) that could match to charters.
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
    
    print("=" * 100)
    print("UNMATCHED PAYMENT REFERENCE CODE ANALYSIS")
    print("=" * 100)
    
    # Check for hash-style references in unmatched payments
    print("\n1. PAYMENTS WITH HASH REFERENCES (#XXX pattern)")
    print("-" * 100)
    
    cur.execute("""
        SELECT p.payment_id, p.payment_key, p.reserve_number,
               COALESCE(p.payment_amount, p.amount) AS amt,
               p.payment_date, p.notes
        FROM payments p
        WHERE NOT EXISTS (
            SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
        )
        AND (
            p.payment_key ~ '#[A-Za-z0-9]{4}'
            OR p.reserve_number ~ '#[A-Za-z0-9]{4}'
            OR p.notes ~ '#[A-Za-z0-9]{4}'
        )
        ORDER BY amt DESC NULLS LAST
        LIMIT 50
    """)
    
    hash_refs = cur.fetchall()
    print(f"\nFound {len(hash_refs)} payments with hash-style references")
    
    if hash_refs:
        print("\nSample payments (first 20):")
        for pid, key, reserve, amt, date, notes in hash_refs[:20]:
            print(f"\n  PID {pid}: ${float(amt) if amt else 0:,.2f} on {date}")
            print(f"    Key: {key or 'None'}")
            print(f"    Reserve: {reserve or 'None'}")
            if notes:
                print(f"    Notes: {notes[:100]}")
    
    # Extract all hash patterns
    if hash_refs:
        print("\n" + "=" * 100)
        print("EXTRACTED HASH PATTERNS")
        print("-" * 100)
        
        hash_patterns = set()
        for row in hash_refs:
            pid, key, reserve, amt, date, notes = row
            text = f"{key or ''} {reserve or ''} {notes or ''}"
            # Find all #XXX patterns
            matches = re.findall(r'#[A-Za-z0-9]{4}', text)
            hash_patterns.update(matches)
        
        print(f"\nUnique hash patterns found: {len(hash_patterns)}")
        print("\nSample patterns:")
        for pattern in sorted(hash_patterns)[:30]:
            print(f"  {pattern}")
    
    # Check if charters have similar reference fields
    print("\n" + "=" * 100)
    print("2. CHECKING CHARTER REFERENCE FIELDS")
    print("-" * 100)
    
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'charters'
        AND (column_name LIKE '%ref%' 
             OR column_name LIKE '%code%'
             OR column_name LIKE '%id%'
             OR column_name LIKE '%number%')
        ORDER BY ordinal_position
    """)
    
    print("\nCharter reference columns:")
    ref_cols = []
    for (col,) in cur.fetchall():
        print(f"  - {col}")
        ref_cols.append(col)
    
    # Check if any of these have hash patterns
    if hash_patterns and ref_cols:
        print("\n" + "=" * 100)
        print("3. MATCHING HASH PATTERNS TO CHARTERS")
        print("-" * 100)
        
        # Build a query to check all reference columns for hash patterns
        sample_hashes = list(hash_patterns)[:10]
        
        for hash_val in sample_hashes:
            # Check in various fields
            cur.execute("""
                SELECT reserve_number, account_number, notes, booking_notes
                FROM charters
                WHERE notes LIKE %s
                   OR booking_notes LIKE %s
                   OR account_number LIKE %s
                LIMIT 5
            """, (f'%{hash_val}%', f'%{hash_val}%', f'%{hash_val}%'))
            
            matches = cur.fetchall()
            if matches:
                print(f"\n  Hash {hash_val} found in charters:")
                for reserve, acct, notes, booking_notes in matches:
                    print(f"    Charter {reserve} (account {acct})")
    
    # Check transaction_id or reference fields in payments
    print("\n" + "=" * 100)
    print("4. OTHER REFERENCE PATTERNS")
    print("-" * 100)
    
    cur.execute("""
        SELECT DISTINCT
            CASE 
                WHEN payment_key LIKE 'BTX:%' THEN 'Banking Transaction ID'
                WHEN payment_key LIKE 'LMSDEP:%' THEN 'LMS Deposit'
                WHEN payment_key LIKE 'SQ:%' THEN 'Square Transaction'
                WHEN payment_key LIKE 'QBO:%' THEN 'QuickBooks Online'
                WHEN payment_key ~ '^[0-9]+$' THEN 'Numeric Key'
                WHEN payment_key ~ '#[A-Za-z0-9]+' THEN 'Hash Reference'
                WHEN payment_key IS NULL THEN 'NULL'
                ELSE 'Other'
            END AS key_type,
            COUNT(*) AS cnt
        FROM payments p
        WHERE NOT EXISTS (
            SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
        )
        GROUP BY key_type
        ORDER BY cnt DESC
    """)
    
    print("\nUnmatched payment key patterns:")
    for key_type, cnt in cur.fetchall():
        print(f"  {key_type}: {cnt:,}")
    
    # Check authorization codes, check numbers, etc
    print("\n" + "=" * 100)
    print("5. TRANSACTION IDENTIFIERS IN PAYMENTS")
    print("-" * 100)
    
    cur.execute("""
        SELECT 
            COUNT(*) FILTER(WHERE check_number IS NOT NULL) AS has_check_num,
            COUNT(*) FILTER(WHERE authorization_code IS NOT NULL) AS has_auth_code,
            COUNT(*) FILTER(WHERE reference_number IS NOT NULL) AS has_ref_num,
            COUNT(*) FILTER(WHERE square_transaction_id IS NOT NULL) AS has_square_txn,
            COUNT(*) AS total
        FROM payments p
        WHERE NOT EXISTS (
            SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
        )
    """)
    
    check_num, auth_code, ref_num, square_txn, total = cur.fetchone()
    
    print(f"\nUnmatched payments with identifiers:")
    print(f"  Check Number: {check_num:,} ({check_num/total*100:.1f}%)")
    print(f"  Authorization Code: {auth_code:,} ({auth_code/total*100:.1f}%)")
    print(f"  Reference Number: {ref_num:,} ({ref_num/total*100:.1f}%)")
    print(f"  Square Transaction ID: {square_txn:,} ({square_txn/total*100:.1f}%)")
    
    # Sample check numbers and see if they appear in charter notes
    if check_num > 0:
        print("\n" + "=" * 100)
        print("6. CHECK NUMBER MATCHING POTENTIAL")
        print("-" * 100)
        
        cur.execute("""
            SELECT p.payment_id, p.check_number, 
                   COALESCE(p.payment_amount, p.amount) AS amt,
                   p.payment_date
            FROM payments p
            WHERE NOT EXISTS (
                SELECT 1 FROM charter_payments cp WHERE cp.payment_id = p.payment_id
            )
            AND p.check_number IS NOT NULL
            AND p.check_number <> ''
            ORDER BY amt DESC NULLS LAST
            LIMIT 20
        """)
        
        check_payments = cur.fetchall()
        print(f"\nSample payments with check numbers (first 20):")
        
        matched_by_check = 0
        for pid, check_num, amt, date in check_payments:
            # Try to find charter with this check number in notes
            cur.execute("""
                SELECT reserve_number FROM charters
                WHERE notes LIKE %s OR booking_notes LIKE %s
                LIMIT 1
            """, (f'%{check_num}%', f'%{check_num}%'))
            
            charter_match = cur.fetchone()
            if charter_match:
                print(f"  PID {pid}: Check #{check_num}, ${float(amt) if amt else 0:,.2f} → MATCHED to {charter_match[0]}")
                matched_by_check += 1
            else:
                print(f"  PID {pid}: Check #{check_num}, ${float(amt) if amt else 0:,.2f} → No match")
        
        print(f"\nMatchable by check number: {matched_by_check} of {len(check_payments)}")
    
    # Summary
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"\nPayments with hash references (#XXX): {len(hash_refs):,}")
    print(f"Unique hash patterns: {len(hash_patterns) if hash_refs else 0}")
    print(f"Payments with check numbers: {check_num:,}")
    print(f"Payments with authorization codes: {auth_code:,}")
    print(f"Payments with reference numbers: {ref_num:,}")
    
    print("\nRecommendations:")
    if hash_refs:
        print("  1. Investigate hash reference payments - may link to specific booking system")
    if check_num > 0:
        print("  2. Try matching by check number in charter notes")
    if auth_code > 0:
        print("  3. Check authorization codes against credit card transaction logs")
    
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
