import psycopg2
import os
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

reserve = "013886"

# Get charter detail
cur.execute("""
    SELECT charter_id, reserve_number, status, charter_date, total_amount_due, paid_amount, balance
    FROM charters
    WHERE reserve_number = %s
""", (reserve,))
charter = cur.fetchone()

if not charter:
    print(f"Charter {reserve} not found")
else:
    print(f"\n{'='*70}")
    print(f"CHARTER {reserve}")
    print(f"{'='*70}")
    print(f"Charter ID:          {charter[0]}")
    print(f"Status:              {charter[2]}")
    print(f"Date:                {charter[3]}")
    print(f"Total Amount Due:    ${charter[4]:.2f}")
    print(f"Paid Amount:         ${charter[5]:.2f}")
    print(f"Balance:             ${charter[6]:.2f}")
    
    # Get charges
    cur.execute("""
        SELECT charge_id, reserve_number, charter_id, description, amount, created_at
        FROM charter_charges
        WHERE reserve_number = %s OR (charter_id = %s AND reserve_number IS NULL)
        ORDER BY created_at
    """, (reserve, charter[0]))
    charges = cur.fetchall()
    
    print(f"\n{'CHARGES:':<70}")
    print(f"{'ID':<8} {'Reserve/ID':<12} {'Description':<25} {'Amount':>12} {'Date':<12}")
    print(f"{'-'*70}")
    charge_sum = Decimal('0.00')
    for c in charges:
        print(f"{c[0]:<8} {str(c[1] or c[2]):<12} {(c[3] or '')[:25]:<25} ${c[4]:>11.2f} {str(c[5])[:10]}")
        charge_sum += c[4] if c[4] else Decimal('0.00')
    print(f"{'-'*70}")
    print(f"{'TOTAL CHARGES:':<48} ${charge_sum:>11.2f}")
    print(f"DEFICIT:                              ${(charter[4] - charge_sum):>11.2f}")
    
    # Get payments
    cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_date, payment_method
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date
    """, (reserve,))
    payments = cur.fetchall()
    
    print(f"\n{'PAYMENTS:':<70}")
    print(f"{'ID':<8} {'Reserve':<12} {'Amount':>12} {'Date':<12} {'Method':<20}")
    print(f"{'-'*70}")
    pay_sum = Decimal('0.00')
    for p in payments:
        print(f"{p[0]:<8} {str(p[1]):<12} ${p[2]:>11.2f} {str(p[3])[:10]:<12} {(p[4] or '')[:20]}")
        pay_sum += p[2] if p[2] else Decimal('0.00')
    print(f"{'-'*70}")
    print(f"{'TOTAL PAYMENTS:':<48} ${pay_sum:>11.2f}")
    
    # Check LMS artifacts
    cur.execute("""
        SELECT chart_id, total_charge, total_paid, notes
        FROM lms_charters
        WHERE chart_id LIKE %s
        LIMIT 1
    """, (f"%{reserve}%",))
    lms = cur.fetchone()
    
    if lms:
        print(f"\n{'LMS ARTIFACT:':<70}")
        print(f"  Chart ID:  {lms[0]}")
        print(f"  Charged:   ${lms[1]:.2f}")
        print(f"  Paid:      ${lms[2]:.2f}")
        print(f"  Notes:     {lms[3]}")

cur.close()
conn.close()
