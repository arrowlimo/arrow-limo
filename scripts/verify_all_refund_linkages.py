"""
Comprehensive verification that all refunds are linked and have matching payments.
"""
import os
import psycopg2

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("="*80)
print("COMPREHENSIVE REFUND LINKAGE VERIFICATION")
print("="*80)

# Get all refunds
cur.execute("""
    SELECT COUNT(*) as total,
           COUNT(reserve_number) as linked,
           COUNT(*) - COUNT(reserve_number) as unlinked
    FROM charter_refunds
""")
stats = cur.fetchone()
print(f"\n📊 OVERALL STATISTICS:")
print(f"  Total Refunds: {stats[0]}")
print(f"  Linked: {stats[1]} ({stats[1]/stats[0]*100:.1f}%)")
print(f"  Unlinked: {stats[2]} ({stats[2]/stats[0]*100:.1f}%)")

# Check the 4 specific refunds we just linked
print(f"\n{'='*80}")
print("RECENTLY LINKED REFUNDS (November 8, 2025)")
print(f"{'='*80}")

RECENT_REFUNDS = [
    (1056, '016478', 15361, 1452.40, 'Darryl@carstarreddeer.ca'),
    (1061, '015400', 14290, 699.05, 'Richard Pfeifer & Trish'),
    (1204, '019521', 18394, 526.50, 'Goodman Roofing'),
    (1203, '019592', 18570, 560.25, 'Accidental Charge'),
]

for refund_id, expected_reserve, expected_charter, amount, description in RECENT_REFUNDS:
    print(f"\n{'*'*60}")
    print(f"Refund #{refund_id}: ${amount} - {description}")
    print(f"{'*'*60}")
    
    # Check refund linkage
    cur.execute("""
        SELECT id, refund_date, amount, reserve_number, charter_id, 
               square_payment_id, source_file
        FROM charter_refunds
        WHERE id = %s
    """, (refund_id,))
    refund = cur.fetchone()
    
    if not refund:
        print(f"  [FAIL] REFUND NOT FOUND")
        continue
    
    linked = refund[3] == expected_reserve and refund[4] == expected_charter
    print(f"  {'[OK]' if linked else '[FAIL]'} Linkage: Reserve={refund[3]}, Charter={refund[4]}")
    print(f"     Date: {refund[1]}, Amount: ${refund[2]}")
    print(f"     Square: {refund[5]}")
    print(f"     Source: {refund[6]}")
    
    if not linked:
        print(f"  [WARN] EXPECTED: Reserve={expected_reserve}, Charter={expected_charter}")
        continue
    
    # Find matching payments for this charter
    cur.execute("""
        SELECT payment_id, payment_date, amount, payment_method, 
               square_payment_id, status, notes
        FROM payments
        WHERE (reserve_number = %s OR charter_id = %s)
          AND ABS(amount) = %s
        ORDER BY payment_date DESC
    """, (expected_reserve, expected_charter, amount))
    payments = cur.fetchall()
    
    if payments:
        print(f"\n  💰 MATCHING PAYMENTS FOUND: {len(payments)}")
        for p in payments:
            print(f"     Payment #{p[0]}: ${p[2]} on {p[1]}")
            print(f"       Method: {p[3]}, Status: {p[5]}")
            if p[4]:
                print(f"       Square: {p[4]}")
    else:
        print(f"\n  [WARN] NO MATCHING PAYMENT FOUND for ${amount}")
        # Check if ANY payments exist for this charter
        cur.execute("""
            SELECT COUNT(*), SUM(amount)
            FROM payments
            WHERE reserve_number = %s OR charter_id = %s
        """, (expected_reserve, expected_charter))
        any_payments = cur.fetchone()
        if any_payments[0] > 0:
            print(f"     Charter has {any_payments[0]} other payments totaling ${any_payments[1]}")
        else:
            print(f"     Charter has NO payments at all")

# Check for any remaining unlinked refunds
print(f"\n{'='*80}")
print("UNLINKED REFUNDS ANALYSIS")
print(f"{'='*80}")

cur.execute("""
    SELECT id, refund_date, amount, square_payment_id, description, 
           customer, source_file
    FROM charter_refunds
    WHERE reserve_number IS NULL OR charter_id IS NULL
    ORDER BY refund_date DESC
    LIMIT 20
""")
unlinked = cur.fetchall()

if unlinked:
    print(f"\n[WARN] Found {len(unlinked)} unlinked refunds (showing first 20):")
    for r in unlinked:
        print(f"\n  Refund #{r[0]}: ${r[2]} on {r[1]}")
        print(f"    Square: {r[3]}")
        print(f"    Customer: {r[5]}")
        print(f"    Desc: {r[4][:80] if r[4] else 'None'}")
        print(f"    Source: {r[6]}")
else:
    print(f"\n[OK] ALL REFUNDS ARE LINKED!")

# Summary by source
print(f"\n{'='*80}")
print("REFUND LINKAGE BY SOURCE")
print(f"{'='*80}")

cur.execute("""
    SELECT 
        source_file,
        COUNT(*) as total,
        COUNT(reserve_number) as linked,
        COUNT(*) - COUNT(reserve_number) as unlinked
    FROM charter_refunds
    GROUP BY source_file
    ORDER BY total DESC
""")
by_source = cur.fetchall()

for source, total, linked, unlinked in by_source:
    pct = linked/total*100 if total > 0 else 0
    print(f"\n  {source}:")
    print(f"    Total: {total}, Linked: {linked} ({pct:.1f}%), Unlinked: {unlinked}")

# Charter-level verification: refunds should match payments
print(f"\n{'='*80}")
print("CHARTER-LEVEL PAYMENT/REFUND RECONCILIATION")
print(f"{'='*80}")

for refund_id, reserve, charter_id, amount, description in RECENT_REFUNDS:
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            COALESCE(SUM(CASE WHEN p.amount > 0 THEN p.amount ELSE 0 END), 0) as total_paid,
            COALESCE(SUM(CASE WHEN p.amount < 0 THEN ABS(p.amount) ELSE 0 END), 0) as total_payment_refunds,
            COALESCE(SUM(cr.amount), 0) as total_charter_refunds
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number OR p.charter_id = c.charter_id
        LEFT JOIN charter_refunds cr ON cr.reserve_number = c.reserve_number OR cr.charter_id = c.charter_id
        WHERE c.reserve_number = %s
        GROUP BY c.charter_id, c.reserve_number, c.charter_date
    """, (reserve,))
    charter = cur.fetchone()
    
    if charter:
        print(f"\n  Charter {charter[1]} (ID: {charter[0]})")
        print(f"    Date: {charter[2]}")
        print(f"    Total Paid: ${charter[3]:.2f}")
        print(f"    Payment Refunds: ${charter[4]:.2f}")
        print(f"    Charter Refunds: ${charter[5]:.2f}")
        print(f"    Net: ${charter[3] - charter[4] - charter[5]:.2f}")
        
        # Verify the specific refund is included
        if charter[5] >= amount:
            print(f"    [OK] Refund ${amount} is included in total")
        else:
            print(f"    [WARN] Expected refund ${amount} not in total ${charter[5]}")

# Final summary
print(f"\n{'='*80}")
print("VERIFICATION SUMMARY")
print(f"{'='*80}")

# Check if all 4 refunds are linked
cur.execute("""
    SELECT id FROM charter_refunds 
    WHERE reserve_number IS NOT NULL 
      AND charter_id IS NOT NULL
      AND id IN %s
""", (tuple([r[0] for r in RECENT_REFUNDS]),))
linked_refunds = cur.fetchall()
all_linked = len(linked_refunds) == 4

if all_linked:
    print("\n[OK] ALL 4 RECENTLY LINKED REFUNDS ARE PROPERLY LINKED")
else:
    print(f"\n[WARN] ONLY {len(linked_refunds)} OUT OF 4 REFUNDS ARE PROPERLY LINKED")

# Check if payments exist for each
cur.execute("""
    SELECT 
        COUNT(DISTINCT cr.id) as refunds_with_payments
    FROM charter_refunds cr
    INNER JOIN payments p ON (
        (p.reserve_number = cr.reserve_number OR p.charter_id = cr.charter_id)
        AND ABS(p.amount) = cr.amount
    )
    WHERE cr.id IN %s
""", (tuple([r[0] for r in RECENT_REFUNDS]),))
refunds_with_payments = cur.fetchone()[0]

print(f"\n💰 {refunds_with_payments} out of 4 refunds have matching payment records")

if refunds_with_payments == 4:
    print("   [OK] ALL refunds have corresponding payments!")
elif refunds_with_payments > 0:
    print(f"   [WARN] {4 - refunds_with_payments} refund(s) missing matching payments")
else:
    print("   [FAIL] NO refunds have matching payments found")

cur.close()
conn.close()

print(f"\n{'='*80}")
print("VERIFICATION COMPLETE")
print(f"{'='*80}")
