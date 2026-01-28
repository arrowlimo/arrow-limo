#!/usr/bin/env python3
"""
Check Square refunds for transaction ID matching capability
"""
import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

conn = get_db_connection()
cur = conn.cursor()

print("="*100)
print("SQUARE REFUNDS - Transaction ID Analysis")
print("="*100)

# Check unlinked Square refunds
cur.execute("""
    SELECT 
        r.id,
        r.refund_date,
        r.amount,
        r.customer,
        r.description,
        r.square_payment_id,
        r.reserve_number,
        r.source_file
    FROM charter_refunds r
    WHERE r.reserve_number IS NULL
    AND r.source_file LIKE 'items-%'
    ORDER BY r.amount DESC
""")

rows = cur.fetchall()
print(f"\nUnlinked Square refunds: {len(rows)}\n")

print(f"{'ID':>5} | {'Date':10} | {'Amount':>12} | {'Has Square ID':13} | {'Description':50}")
print("-"*110)

for refund_id, date, amount, customer, desc, square_id, reserve, source in rows:
    has_square_id = "YES" if square_id else "NO"
    desc_str = (desc or "")[:50]
    print(f"{refund_id:5} | {date} | ${amount:>10,.2f} | {has_square_id:13} | {desc_str}")

# Now check if any of these square_payment_ids exist in payments table
print("\n" + "="*100)
print("MATCHING POTENTIAL")
print("="*100)

cur.execute("""
    SELECT 
        r.id as refund_id,
        r.amount as refund_amount,
        r.square_payment_id,
        p.payment_id,
        p.charter_id,
        p.reserve_number,
        p.amount as payment_amount
    FROM charter_refunds r
    JOIN payments p ON r.square_payment_id = p.square_payment_id
    WHERE r.reserve_number IS NULL
    AND r.source_file LIKE 'items-%'
    AND r.square_payment_id IS NOT NULL
    AND r.square_payment_id != ''
""")

matches = cur.fetchall()
if matches:
    print(f"\n[OK] Found {len(matches)} Square refunds that can be linked via square_payment_id!\n")
    for refund_id, refund_amt, square_id, payment_id, charter_id, reserve, payment_amt in matches:
        print(f"Refund #{refund_id}: ${refund_amt:,.2f} -> Charter {reserve} (${payment_amt:,.2f})")
        print(f"  Square ID: {square_id}")
else:
    print("\n[FAIL] No matches found via square_payment_id")

# Check for partial Square ID matching (first 4 + last 4)
print("\n" + "="*100)
print("CHECKING PARTIAL SQUARE ID MATCHING")
print("="*100)

cur.execute("""
    SELECT 
        r.id,
        r.amount,
        r.square_payment_id,
        LENGTH(r.square_payment_id) as id_length
    FROM charter_refunds r
    WHERE r.reserve_number IS NULL
    AND r.source_file LIKE 'items-%'
    AND r.square_payment_id IS NOT NULL
    AND r.square_payment_id != ''
""")

refunds_with_ids = cur.fetchall()
print(f"\nRefunds with Square IDs: {len(refunds_with_ids)}")

if refunds_with_ids:
    print("\nSample Square IDs:")
    for refund_id, amount, square_id, id_len in refunds_with_ids[:5]:
        first4 = square_id[:4] if square_id else ""
        last4 = square_id[-4:] if square_id else ""
        print(f"  Refund #{refund_id}: {first4}...{last4} (length: {id_len}) - ${amount:,.2f}")
    
    # Try fuzzy matching with first4+last4
    print("\n" + "="*100)
    print("TRYING FUZZY MATCH: First 4 + Last 4 characters")
    print("="*100)
    
    for refund_id, amount, square_id, id_len in refunds_with_ids:
        if square_id and len(square_id) >= 8:
            first4 = square_id[:4]
            last4 = square_id[-4:]
            
            cur.execute("""
                SELECT payment_id, charter_id, reserve_number, amount, square_payment_id
                FROM payments
                WHERE square_payment_id LIKE %s || '%%' || %s
                AND charter_id IS NOT NULL
            """, (first4, last4))
            
            fuzzy_matches = cur.fetchall()
            if fuzzy_matches:
                print(f"\n[OK] Refund #{refund_id} (${amount:,.2f}): {first4}...{last4}")
                print(f"   Refund Square ID: {square_id}")
                for p_id, c_id, reserve, p_amt, p_square_id in fuzzy_matches:
                    print(f"   -> Payment #{p_id}: Charter {reserve} (${p_amt:,.2f})")
                    print(f"      Payment Square ID: {p_square_id}")

cur.close()
conn.close()
