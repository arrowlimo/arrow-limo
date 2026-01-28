"""
Investigate the $560.25 accidental charge and verify charge+refund tracking.

From user input:
- Accidental charge $560.25 on res 019592 (Sep 5 2025, Visa 9302, Receipt #pwqe)
- Actual charges were on 019521 and 019522
- User expects to find the withdrawal of $526.50 from Goodman Roofing card
- User notes: "as far as i can see 521 and 522 were cancelled, we do not refund deposit"
- User wants reservations to have BOTH charge and refund linked for tracking
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
print("ACCIDENTAL CHARGE INVESTIGATION: $560.25 + Goodman Roofing Case")
print("="*80)

# Check all three reservations
for reserve in ['019592', '019521', '019522']:
    print(f"\n{'='*80}")
    print(f"RESERVE {reserve}")
    print(f"{'='*80}")
    
    cur.execute("""
        SELECT charter_id, reserve_number, charter_date, status, cancelled,
               total_amount_due, paid_amount, balance
        FROM charters
        WHERE reserve_number = %s
    """, (reserve,))
    charter = cur.fetchone()
    
    if not charter:
        print(f"[WARN] Charter {reserve} NOT FOUND")
        continue
    
    print(f"\nCharter: {charter[0]}")
    print(f"  Date: {charter[2]}")
    print(f"  Status: {charter[3]}, Cancelled: {charter[4]}")
    print(f"  Amount Due: ${charter[5]}, Paid: ${charter[6]}, Balance: ${charter[7]}")
    
    # Get all payments
    print(f"\n--- PAYMENTS for {reserve} ---")
    cur.execute("""
        SELECT payment_id, payment_date, amount, payment_method, 
               square_payment_id, status, notes
        FROM payments
        WHERE reserve_number = %s OR charter_id = %s
        ORDER BY payment_date
    """, (reserve, charter[0]))
    payments = cur.fetchall()
    
    if payments:
        for p in payments:
            print(f"  Payment #{p[0]}: ${p[2]:>8} on {p[1]} via {p[3]}")
            print(f"    Status: {p[5]}, Square: {p[4]}")
            if p[6]:
                print(f"    Notes: {p[6][:100]}")
    else:
        print("  No payments found")
    
    # Get all refunds
    print(f"\n--- REFUNDS for {reserve} ---")
    cur.execute("""
        SELECT id, refund_date, amount, square_payment_id, description, source_file
        FROM charter_refunds
        WHERE reserve_number = %s OR charter_id = %s
        ORDER BY refund_date
    """, (reserve, charter[0]))
    refunds = cur.fetchall()
    
    if refunds:
        for r in refunds:
            print(f"  Refund #{r[0]}: ${r[2]:>8} on {r[1]}")
            print(f"    Square: {r[3]}")
            print(f"    Desc: {r[4][:100] if r[4] else 'None'}")
            print(f"    Source: {r[5]}")
    else:
        print("  No refunds found")
    
    # Summary
    total_payments = sum(p[2] for p in payments if p[2] > 0)
    total_refunds = sum(r[2] for r in refunds)
    print(f"\n  SUMMARY: Total Payments: ${total_payments:.2f}, Total Refunds: ${total_refunds:.2f}")

# Check for $560.25 refund
print(f"\n{'='*80}")
print("SEARCH: $560.25 REFUND (Accidental charge)")
print(f"{'='*80}")

cur.execute("""
    SELECT id, refund_date, amount, reserve_number, charter_id, 
           square_payment_id, description
    FROM charter_refunds
    WHERE ABS(amount) = 560.25
    ORDER BY refund_date DESC
""")
refunds_560 = cur.fetchall()

if refunds_560:
    for r in refunds_560:
        print(f"\nRefund #{r[0]}: ${r[2]} on {r[1]}")
        print(f"  Reserve: {r[3]}, Charter: {r[4]}")
        print(f"  Square: {r[5]}")
        print(f"  Desc: {r[6]}")
else:
    print("No $560.25 refunds found")

# Check for corresponding $560.25 payment (the accidental charge)
print(f"\n{'='*80}")
print("SEARCH: $560.25 PAYMENT (Should match accidental charge)")
print(f"{'='*80}")

cur.execute("""
    SELECT payment_id, payment_date, amount, reserve_number, charter_id,
           payment_method, square_payment_id, status, notes
    FROM payments
    WHERE ABS(amount) = 560.25
    ORDER BY payment_date DESC
""")
payments_560 = cur.fetchall()

if payments_560:
    for p in payments_560:
        print(f"\nPayment #{p[0]}: ${p[2]} on {p[1]}")
        print(f"  Reserve: {p[3]}, Charter: {p[4]}")
        print(f"  Method: {p[5]}, Square: {p[6]}")
        print(f"  Status: {p[7]}")
        print(f"  Notes: {p[8]}")
else:
    print("No $560.25 payments found")

# Final analysis
print(f"\n{'='*80}")
print("ANALYSIS: Accidental Charge Tracking")
print(f"{'='*80}")

print("""
USER EXPECTATION:
- Accidental charges should show BOTH:
  1. The original charge (payment record)
  2. The refund (refund record)
  
CURRENT FINDINGS:
- Refund #1203 ($560.25) exists but is NOT linked to any charter
- No corresponding $560.25 payment found in payments table
- This means the accidental charge is NOT properly tracked

RECOMMENDATION:
1. If the $560.25 was accidentally charged to 019592:
   - Find the Square payment transaction for the original charge
   - Import it to payments table if missing
   - Link both the payment AND refund to 019592

2. If 019592 was never actually charged (refund only):
   - This represents a refund without a prior charge
   - May indicate the charge was made but not imported
   - Check Square directly for the original transaction
""")

cur.close()
conn.close()
