"""
Verify recent refund cases from user input:
1. $1,452.40 - Darryl@carstarreddeer.ca res 016478 (Sep 13 2022, Visa 9965, Receipt #xWX4)
2. $699.05 - Richard Pfeifer & Trish res 015400 (Jul 9 2021, MasterCard 3313, Receipt #j1wP)
3. $560.25 - Accidental charge res 019592 (Sep 5 2025, Visa 9302, Receipt #pwqe)
   - Related to 019521 and 019522, Goodman Roofing $526.50 refund
"""
import os
import psycopg2
from datetime import date, timedelta

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

def check_refund(amount, reserve_num, date_approx, description):
    """Check if refund exists in charter_refunds or payments"""
    print(f"\n{'='*80}")
    print(f"Checking: ${amount} - Reserve {reserve_num} - {description}")
    print(f"{'='*80}")
    
    # Check charter_refunds
    print("\n--- charter_refunds ---")
    cur.execute("""
        SELECT id, refund_date, amount, reserve_number, charter_id, 
               square_payment_id, description, customer, source_file
        FROM charter_refunds
        WHERE ABS(amount) = %s
        ORDER BY ABS(EXTRACT(EPOCH FROM (refund_date::timestamp - %s::timestamp)))
        LIMIT 5
    """, (amount, date_approx))
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f"  ID: {r[0]}, Date: {r[1]}, Amount: {r[2]}, Reserve: {r[3]}, Charter: {r[4]}")
            print(f"  Square ID: {r[5]}, Desc: {r[6]}, Customer: {r[7]}")
            print(f"  Source: {r[8]}")
            print()
    else:
        print("  No matches in charter_refunds")
    
    # Check payments table for refunds
    print("\n--- payments (refunds) ---")
    cur.execute("""
        SELECT payment_id, payment_date, amount, reserve_number, charter_id,
               payment_method, square_payment_id, notes, status
        FROM payments
        WHERE (amount < 0 OR status ILIKE '%%refund%%')
          AND ABS(amount) = %s
        ORDER BY ABS(EXTRACT(EPOCH FROM (payment_date::timestamp - %s::timestamp)))
        LIMIT 5
    """, (amount, date_approx))
    rows_pay = cur.fetchall()
    if rows_pay:
        for r in rows_pay:
            print(f"  Payment ID: {r[0]}, Date: {r[1]}, Amount: {r[2]}, Reserve: {r[3]}, Charter: {r[4]}")
            print(f"  Method: {r[5]}, Square ID: {r[6]}, Status: {r[8]}")
            print(f"  Notes: {r[7]}")
            print()
    else:
        print("  No matches in payments")
    
    # Check if reserve number exists
    print(f"\n--- Charter {reserve_num} ---")
    cur.execute("""
        SELECT charter_id, reserve_number, charter_date, 
               total_amount_due, paid_amount, balance, status
        FROM charters
        WHERE reserve_number = %s
    """, (reserve_num,))
    charter = cur.fetchone()
    if charter:
        print(f"  Charter ID: {charter[0]}")
        print(f"  Date: {charter[2]}")
        print(f"  Amount Due: ${charter[3]}, Paid: ${charter[4]}, Balance: ${charter[5]}")
        print(f"  Status: {charter[6]}")
    else:
        print(f"  [WARN] Charter {reserve_num} NOT FOUND")
    
    return rows

# Case 1: $1,452.40 - Darryl@carstarreddeer.ca res 016478
check_refund(1452.40, '016478', '2022-09-13', 'Darryl@carstarreddeer.ca, Receipt #xWX4')

# Case 2: $699.05 - Richard Pfeifer & Trish res 015400
check_refund(699.05, '015400', '2021-07-09', 'Richard Pfeifer & Trish, Receipt #j1wP')

# Case 3: $560.25 - Accidental charge res 019592
check_refund(560.25, '019592', '2025-09-05', 'Accidental charge, Receipt #pwqe')

# Additional check for Goodman Roofing
print(f"\n{'='*80}")
print("Checking: Goodman Roofing - $526.50 refund + reservations 019521, 019522")
print(f"{'='*80}")

for reserve in ['019521', '019522']:
    print(f"\n--- Charter {reserve} ---")
    cur.execute("""
        SELECT charter_id, reserve_number, charter_date,
               total_amount_due, paid_amount, balance, status, cancelled
        FROM charters
        WHERE reserve_number = %s
    """, (reserve,))
    charter = cur.fetchone()
    if charter:
        print(f"  Charter ID: {charter[0]}")
        print(f"  Date: {charter[2]}")
        print(f"  Amount Due: ${charter[3]}, Paid: ${charter[4]}, Balance: ${charter[5]}")
        print(f"  Status: {charter[6]}, Cancelled: {charter[7]}")
        
        # Check payments for this charter
        cur.execute("""
            SELECT payment_id, payment_date, amount, payment_method, square_payment_id, status
            FROM payments
            WHERE reserve_number = %s OR charter_id = %s
            ORDER BY payment_date
        """, (reserve, charter[0]))
        payments = cur.fetchall()
        if payments:
            print(f"  Payments ({len(payments)}):")
            for p in payments:
                print(f"    Payment {p[0]}: ${p[2]} on {p[1]} ({p[3]}) - {p[5]}")
        
        # Check refunds
        cur.execute("""
            SELECT id, refund_date, amount, description
            FROM charter_refunds
            WHERE reserve_number = %s OR charter_id = %s
            ORDER BY refund_date
        """, (reserve, charter[0]))
        refunds = cur.fetchall()
        if refunds:
            print(f"  Refunds ({len(refunds)}):")
            for r in refunds:
                print(f"    Refund {r[0]}: ${r[2]} on {r[1]} - {r[3]}")
    else:
        print(f"  [WARN] Charter {reserve} NOT FOUND")

# Search for Goodman Roofing by name
print("\n--- Goodman Roofing (search by notes/description) ---")
cur.execute("""
    SELECT charter_id, reserve_number, charter_date,
           total_amount_due, paid_amount, balance, status
    FROM charters
    WHERE notes ILIKE '%goodman%' OR notes ILIKE '%roofing%'
       OR booking_notes ILIKE '%goodman%' OR booking_notes ILIKE '%roofing%'
    ORDER BY charter_date DESC
    LIMIT 10
""")
goodman_charters = cur.fetchall()
if goodman_charters:
    print(f"Found {len(goodman_charters)} charters:")
    for c in goodman_charters:
        print(f"  {c[1]} on {c[2]} - ${c[3]} (Balance: ${c[5]})")
else:
    print("  No charters found with 'Goodman' or 'Roofing'")

# Search for $526.50 amount
print("\n--- $526.50 refund search ---")
cur.execute("""
    SELECT id, refund_date, amount, reserve_number, charter_id, description, customer
    FROM charter_refunds
    WHERE ABS(amount) = 526.50
    ORDER BY refund_date DESC
""")
refund_526 = cur.fetchall()
if refund_526:
    for r in refund_526:
        print(f"  Refund {r[0]}: ${r[2]} on {r[1]} - Reserve {r[3]}, Charter {r[4]}")
        print(f"    Customer: {r[6]}, Desc: {r[5]}")
else:
    print("  No $526.50 refunds found")

cur.execute("""
    SELECT payment_id, payment_date, amount, reserve_number, charter_id, payment_method, notes
    FROM payments
    WHERE ABS(amount) = 526.50
    ORDER BY payment_date DESC
""")
payment_526 = cur.fetchall()
if payment_526:
    print("\n  In payments table:")
    for p in payment_526:
        print(f"  Payment {p[0]}: ${p[2]} on {p[1]} - Reserve {p[3]}, Charter {p[4]}")
        print(f"    Method: {p[5]}, Notes: {p[6]}")
else:
    print("  No $526.50 payments found")

cur.close()
conn.close()

print("\n" + "="*80)
print("VERIFICATION COMPLETE")
print("="*80)
