"""
Check charter_charges for 28 charters with total_amount_due = 0 but LMS Est_Charge > 0
Determines if charges are missing or if total_amount_due just needs recalculation
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

# 28 zero-total suspects from discrepancy analysis
SUSPECTS = [
    (18658, '019743', 467.25, 2025),
    (18656, '019746', 369.00, 2025),
    (18660, '019739', 1825.50, 2025),
    (18659, '019744', 645.75, 2025),
    (18661, '019736', 312.00, 2025),
    (18662, '019719', 184.50, 2025),
    (18663, '019732', 335.55, 2025),
    (18664, '019734', 1193.10, 2025),
    (18666, '019741', 874.50, 2025),
    (18665, '019742', 738.00, 2025),
    (18667, '019740', 386.25, 2025),
    (18668, '019738', 1968.00, 2026),
    (18672, '019726', 1107.00, 2025),
    (18673, '019728', 861.00, 2025),
    (18674, '019727', 1845.00, 2025),
    (18685, '019717', 615.00, 2025),
    (18681, '019722', 844.50, 2025),
    (18682, '019721', 2091.00, 2026),
    (18683, '019720', 1534.00, 2026),
    (18657, '019745', 990.00, 2025),
    (18669, '019737', 327.75, 2025),
    (18670, '019733', 719.55, 2025),
    (18671, '019735', 553.50, 2025),
    (18677, '019723', 861.00, 2025),
    (18678, '019731', 2029.50, 2025),
    (18679, '019725', 1660.50, 2026),
    (18680, '019724', 369.00, 2025),
    (18684, '019718', 3510.00, 2025),
]

def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("="*110)
    print("ZERO-TOTAL CHARTER_CHARGES INSPECTION (28 SUSPECTS)")
    print("="*110)
    print(f"{'Reserve':<10}{'CharterID':<10}{'LMS_Est':>12}{'Charge_Rows':>12}{'Charge_Sum':>12}{'Status':>15}")
    print("-"*110)

    missing_charges = []
    has_charges_wrong_total = []
    
    for charter_id, reserve, lms_est, year in SUSPECTS:
        cur.execute("""
            SELECT COUNT(*) as row_count, COALESCE(SUM(amount), 0) as charge_sum
            FROM charter_charges
            WHERE charter_id = %s
        """, (charter_id,))
        result = cur.fetchone()
        
        row_count = result['row_count']
        charge_sum = float(result['charge_sum'])
        
        if row_count == 0:
            status = "MISSING"
            missing_charges.append((charter_id, reserve, lms_est, year))
        elif abs(charge_sum - lms_est) < 0.02:
            status = "HAS_CHARGES_OK"
            has_charges_wrong_total.append((charter_id, reserve, charge_sum))
        else:
            status = "WRONG_SUM"
            has_charges_wrong_total.append((charter_id, reserve, charge_sum))
        
        print(f"{reserve:<10}{charter_id:<10}{lms_est:12.2f}{row_count:12}{charge_sum:12.2f}{status:>15}")

    print("\n" + "="*110)
    print("SUMMARY")
    print("="*110)
    print(f"Total suspects: {len(SUSPECTS)}")
    print(f"Missing charter_charges entirely: {len(missing_charges)}")
    print(f"Has charges but total_amount_due wrong: {len(has_charges_wrong_total)}")
    
    if missing_charges:
        print(f"\nMISSING CHARGES (need import from LMS):")
        print(f"Total charters: {len(missing_charges)}")
        print(f"Total LMS Est_Charge: ${sum(x[2] for x in missing_charges):,.2f}")
        
    if has_charges_wrong_total:
        print(f"\nHAS CHARGES (need total_amount_due recalculation):")
        print(f"Total charters: {len(has_charges_wrong_total)}")
        print(f"Total charge_sum: ${sum(x[2] for x in has_charges_wrong_total):,.2f}")

    print("\nNext Steps:")
    if missing_charges:
        print("  1. Run import script to add charter_charges from LMS for missing charters")
    if has_charges_wrong_total:
        print("  2. Run recalculate_charter_totals.py to sync total_amount_due with charter_charges sum")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
