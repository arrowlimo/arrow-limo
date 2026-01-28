"""
Link the $560.25 accidental charge refund to reservation 019592.

From investigation:
- Payment #25228 ($560.25) on 2025-09-02 is linked to charter 18570 (reserve 019592)
- Refund #1203 ($560.25) on 2025-09-05 exists but is unlinked
- These represent the accidental charge and its refund
"""
import os
import psycopg2
import argparse

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

parser = argparse.ArgumentParser()
parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
args = parser.parse_args()

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

REFUND_ID = 1203
RESERVE = '019592'
CHARTER_ID = 18570

print("="*80)
print(f"LINKING ACCIDENTAL CHARGE REFUND")
print("="*80)

# Verify refund exists
cur.execute("""
    SELECT id, refund_date, amount, reserve_number, charter_id, 
           square_payment_id, description
    FROM charter_refunds
    WHERE id = %s
""", (REFUND_ID,))
refund = cur.fetchone()

if not refund:
    print(f"[WARN] Refund #{REFUND_ID} not found!")
    exit(1)

print(f"\nRefund #{refund[0]}: ${refund[2]} on {refund[1]}")
print(f"  Current: Reserve={refund[3]}, Charter={refund[4]}")
print(f"  Square: {refund[5]}")
print(f"  Desc: {refund[6]}")

# Verify charter exists
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, status
    FROM charters
    WHERE charter_id = %s AND reserve_number = %s
""", (CHARTER_ID, RESERVE))
charter = cur.fetchone()

if not charter:
    print(f"[WARN] Charter {CHARTER_ID} / Reserve {RESERVE} not found!")
    exit(1)

print(f"\nTarget Charter {charter[0]} ({charter[1]})")
print(f"  Date: {charter[2]}, Status: {charter[3]}")

# Verify corresponding payment exists
cur.execute("""
    SELECT payment_id, payment_date, amount, payment_method, status
    FROM payments
    WHERE (reserve_number = %s OR charter_id = %s)
      AND ABS(amount) = %s
    ORDER BY payment_date DESC
    LIMIT 1
""", (RESERVE, CHARTER_ID, abs(refund[2])))
payment = cur.fetchone()

if payment:
    print(f"\nMatching Payment #{payment[0]}: ${payment[2]} on {payment[1]}")
    print(f"  Method: {payment[3]}, Status: {payment[4]}")
    print(f"  [OK] CONFIRMED: Payment exists for this charter")
else:
    print(f"\n[WARN] WARNING: No matching payment found for ${refund[2]} on this charter")
    print(f"  This may indicate the payment was not imported or is linked differently")

if args.write:
    cur.execute("""
        UPDATE charter_refunds
        SET reserve_number = %s,
            charter_id = %s
        WHERE id = %s
    """, (RESERVE, CHARTER_ID, REFUND_ID))
    conn.commit()
    print(f"\n[OK] UPDATED refund #{REFUND_ID} -> Reserve {RESERVE}, Charter {CHARTER_ID}")
else:
    print(f"\nDRY-RUN: Would update refund #{REFUND_ID} -> Reserve {RESERVE}, Charter {CHARTER_ID}")

# Verification
cur.execute("""
    SELECT id, refund_date, amount, reserve_number, charter_id
    FROM charter_refunds
    WHERE id = %s
""", (REFUND_ID,))
refund_check = cur.fetchone()

print(f"\n{'='*80}")
print("VERIFICATION")
print(f"{'='*80}")

if refund_check:
    linked = refund_check[3] == RESERVE and refund_check[4] == CHARTER_ID
    status = "[OK] LINKED" if linked else "[WARN] NOT LINKED"
    print(f"{status} Refund #{refund_check[0]}: ${refund_check[2]} -> Reserve {refund_check[3]}, Charter {refund_check[4]}")
    
    if linked or args.write:
        # Show full charge+refund tracking for this charter
        print(f"\n{'='*80}")
        print(f"COMPLETE TRACKING FOR CHARTER {RESERVE}")
        print(f"{'='*80}")
        
        cur.execute("""
            SELECT payment_id, payment_date, amount, payment_method, status
            FROM payments
            WHERE reserve_number = %s OR charter_id = %s
            ORDER BY payment_date
        """, (RESERVE, CHARTER_ID))
        payments = cur.fetchall()
        
        print(f"\nPayments ({len(payments)}):")
        for p in payments:
            print(f"  Payment #{p[0]}: ${p[2]:>8} on {p[1]} ({p[3]}) - {p[4]}")
        
        cur.execute("""
            SELECT id, refund_date, amount, description
            FROM charter_refunds
            WHERE reserve_number = %s OR charter_id = %s
            ORDER BY refund_date
        """, (RESERVE, CHARTER_ID))
        refunds = cur.fetchall()
        
        print(f"\nRefunds ({len(refunds)}):")
        for r in refunds:
            print(f"  Refund #{r[0]}: ${r[2]:>8} on {r[1]}")
            if r[3]:
                print(f"    {r[3][:80]}")
        
        total_paid = sum(p[2] for p in payments if p[2] > 0)
        total_refunded = sum(r[2] for r in refunds)
        net = total_paid - total_refunded
        
        print(f"\nSummary:")
        print(f"  Total Paid: ${total_paid:.2f}")
        print(f"  Total Refunded: ${total_refunded:.2f}")
        print(f"  Net: ${net:.2f}")

cur.close()
conn.close()
