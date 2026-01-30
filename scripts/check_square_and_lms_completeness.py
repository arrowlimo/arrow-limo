"""
Critical verification requested by user:
1. Check if Square payments were doubled in almsdata
2. Verify 2026 charges are correct
3. Compare driver/vehicle/routing data between LMS and almsdata
4. Verify payment matching
"""
import os
import psycopg2
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def connect():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def check_square_doubles():
    """Check for doubled Square payments (user concern from last update)"""
    print("=" * 80)
    print("1. CHECKING FOR DOUBLED SQUARE PAYMENTS")
    print("=" * 80)
    
    conn = connect()
    cur = conn.cursor()
    
    # Find exact duplicate payments (same reserve, date, amount)
    cur.execute("""
        SELECT 
            p.reserve_number,
            p.payment_date,
            p.amount,
            p.payment_method,
            COUNT(*) as duplicate_count,
            SUM(p.amount) as total_amount,
            STRING_AGG(p.payment_id::text, ', ' ORDER BY p.payment_id) as payment_ids,
            STRING_AGG(COALESCE(p.square_transaction_id, p.authorization_code, 'N/A'), ', ') as trans_ids
        FROM payments p
        WHERE p.payment_date >= '2024-01-01'
        GROUP BY p.reserve_number, p.payment_date, p.amount, p.payment_method
        HAVING COUNT(*) > 1
        ORDER BY SUM(p.amount) DESC
        LIMIT 30
    """)
    
    duplicates = cur.fetchall()
    if duplicates:
        print(f"\n⚠️  Found {len(duplicates)} sets of duplicate payments (same date+amount):\n")
        print(f"{'Reserve':<10} {'Date':<12} {'Method':<15} {'Amount':>12} {'Count':>6} {'Total':>12} {'Transaction IDs'}")
        print("-" * 120)
        for row in duplicates:
            reserve = row[0] or 'N/A'
            date = str(row[1]) if row[1] else 'N/A'
            amount = row[2] if row[2] is not None else 0.0  # amount is 3rd column
            method = (row[3] or 'N/A')[:15]  # method is 4th column
            count = row[4]
            total = row[5] if row[5] is not None else 0.0
            trans_ids = (row[7] or 'N/A')[:40]
            print(f"{reserve:<10} {date:<12} {method:<15} ${amount:10,.2f} {count:6} ${total:10,.2f} {trans_ids}")
    else:
        print("\n✅ No duplicate payments found (same date+amount)")
    
    # Check for Square-specific payments (identified by square_transaction_id)
    cur.execute("""
        SELECT COUNT(*), SUM(amount)
        FROM payments
        WHERE square_transaction_id IS NOT NULL
    """)
    row = cur.fetchone()
    if row[0] > 0:
        print(f"\nTotal Square payments (via square_transaction_id): {row[0]:,} totaling ${row[1] if row[1] else 0:,.2f}")
        
        # Check for duplicate Square transactions
        cur.execute("""
            SELECT 
                square_transaction_id,
                COUNT(*) as count,
                SUM(amount) as total,
                STRING_AGG(reserve_number, ', ') as reserves
            FROM payments
            WHERE square_transaction_id IS NOT NULL
            GROUP BY square_transaction_id
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC
            LIMIT 20
        """)
        sq_dups = cur.fetchall()
        if sq_dups:
            print(f"\n⚠️  Found {len(sq_dups)} DUPLICATE Square transactions (same transaction_id):")
            print(f"{'Transaction ID':<40} {'Count':>6} {'Total':>12} {'Reserves'}")
            print("-" * 120)
            for row in sq_dups:
                print(f"{row[0][:40]:<40} {row[1]:>6} ${row[2]:>10,.2f} {row[3][:30]}")
        else:
            print("✅ No duplicate Square transaction IDs found")
    else:
        print("\nℹ️  No Square payments found (square_transaction_id is NULL for all)")
    
    conn.close()

def compare_driver_vehicle_routing():
    """Compare driver/vehicle/routing completeness"""
    print("\n" + "=" * 80)
    print("2. DRIVER/VEHICLE/ROUTING DATA COMPLETENESS")
    print("=" * 80)
    
    conn = connect()
    cur = conn.cursor()
    
    # Driver completeness
    print("\n📋 DRIVER DATA:")
    print("-" * 80)
    cur.execute("""
        SELECT 
            'LMS' as source,
            COUNT(*) as total,
            SUM(CASE WHEN driver_code IS NOT NULL AND driver_code != '' THEN 1 ELSE 0 END) as with_driver,
            ROUND(100.0 * SUM(CASE WHEN driver_code IS NOT NULL AND driver_code != '' THEN 1 ELSE 0 END) / COUNT(*), 2) as pct
        FROM lms2026_reserves
        UNION ALL
        SELECT 
            'ALMSDATA',
            COUNT(*),
            SUM(CASE WHEN assigned_driver_id IS NOT NULL OR (driver IS NOT NULL AND driver != '') THEN 1 ELSE 0 END),
            ROUND(100.0 * SUM(CASE WHEN assigned_driver_id IS NOT NULL OR (driver IS NOT NULL AND driver != '') THEN 1 ELSE 0 END) / COUNT(*), 2)
        FROM charters
    """)
    
    print(f"{'Source':<12} {'Total':>10} {'With Driver':>12} {'Percent':>10}")
    print("-" * 80)
    for row in cur.fetchall():
        print(f"{row[0]:<12} {row[1]:>10,} {row[2]:>12,} {row[3] or 0:>9.2f}%")
    
    # Vehicle completeness
    print("\n📋 VEHICLE DATA:")
    print("-" * 80)
    cur.execute("""
        SELECT 
            'LMS' as source,
            COUNT(*) as total,
            SUM(CASE WHEN vehicle_code IS NOT NULL AND vehicle_code != '' THEN 1 ELSE 0 END) as with_vehicle,
            ROUND(100.0 * SUM(CASE WHEN vehicle_code IS NOT NULL AND vehicle_code != '' THEN 1 ELSE 0 END) / COUNT(*), 2) as pct
        FROM lms2026_reserves
        UNION ALL
        SELECT 
            'ALMSDATA',
            COUNT(*),
            SUM(CASE WHEN vehicle_id IS NOT NULL OR (vehicle IS NOT NULL AND vehicle != '') THEN 1 ELSE 0 END),
            ROUND(100.0 * SUM(CASE WHEN vehicle_id IS NOT NULL OR (vehicle IS NOT NULL AND vehicle != '') THEN 1 ELSE 0 END) / COUNT(*), 2)
        FROM charters
    """)
    
    print(f"{'Source':<12} {'Total':>10} {'With Vehicle':>12} {'Percent':>10}")
    print("-" * 80)
    for row in cur.fetchall():
        print(f"{row[0]:<12} {row[1]:>10,} {row[2]:>12,} {row[3] or 0:>9.2f}%")
    
    # Routing data (pickup/dropoff locations)
    print("\n📋 ROUTING DATA:")
    print("-" * 80)
    
    # LMS routing fields
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN pickup_address IS NOT NULL AND pickup_address != '' THEN 1 ELSE 0 END) as has_pickup,
            SUM(CASE WHEN dropoff_address IS NOT NULL AND dropoff_address != '' THEN 1 ELSE 0 END) as has_dropoff,
            SUM(CASE WHEN pu_time IS NOT NULL THEN 1 ELSE 0 END) as has_time
        FROM lms2026_reserves
    """)
    row = cur.fetchone()
    total_lms = row[0]
    print(f"LMS (out of {total_lms:,}):")
    print(f"  Pickup Location:  {row[1]:>8,} ({row[1]*100.0/total_lms:>6.2f}%)")
    print(f"  Dropoff Location: {row[2]:>8,} ({row[2]*100.0/total_lms:>6.2f}%)")
    print(f"  Pickup Time:      {row[3]:>8,} ({row[3]*100.0/total_lms:>6.2f}%)")
    
    # ALMSDATA routing fields
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN pickup_location IS NOT NULL AND pickup_location != '' THEN 1 ELSE 0 END) as has_pickup,
            SUM(CASE WHEN dropoff_location IS NOT NULL AND dropoff_location != '' THEN 1 ELSE 0 END) as has_dropoff,
            SUM(CASE WHEN pickup_time IS NOT NULL THEN 1 ELSE 0 END) as has_time
        FROM charters
    """)
    row = cur.fetchone()
    total_alms = row[0]
    print(f"\nALMSDATA (out of {total_alms:,}):")
    print(f"  Pickup Location:  {row[1]:>8,} ({row[1]*100.0/total_alms:>6.2f}%)")
    print(f"  Dropoff Location: {row[2]:>8,} ({row[2]*100.0/total_alms:>6.2f}%)")
    print(f"  Pickup Time:      {row[3]:>8,} ({row[3]*100.0/total_alms:>6.2f}%)")
    
    conn.close()

def verify_2026_charges():
    """Check 2026 charges specifically"""
    print("\n" + "=" * 80)
    print("3. 2026 CHARGES VERIFICATION")
    print("=" * 80)
    
    conn = connect()
    cur = conn.cursor()
    
    # Count 2026 charges in both systems
    cur.execute("""
        SELECT 
            COUNT(*) as charge_count,
            COUNT(DISTINCT lms.reserve_no) as charter_count,
            SUM(lms.amount) as total_amount
        FROM lms2026_charges lms
        JOIN lms2026_reserves r ON r.reserve_no = lms.reserve_no
        WHERE r.pu_date >= '2026-01-01'
    """)
    lms_row = cur.fetchone()
    
    cur.execute("""
        SELECT 
            COUNT(*) as charge_count,
            COUNT(DISTINCT cc.reserve_number) as charter_count,
            SUM(cc.amount) as total_amount
        FROM charter_charges cc
        JOIN charters c ON c.reserve_number = cc.reserve_number
        WHERE c.charter_date >= '2026-01-01'
    """)
    alms_row = cur.fetchone()
    
    print(f"\n{'Source':<12} {'Charges':>10} {'Charters':>10} {'Total Amount':>15}")
    print("-" * 80)
    print(f"{'LMS':<12} {lms_row[0]:>10,} {lms_row[1]:>10,} ${lms_row[2] if lms_row[2] else 0:>13,.2f}")
    print(f"{'ALMSDATA':<12} {alms_row[0]:>10,} {alms_row[1]:>10,} ${alms_row[2] if alms_row[2] else 0:>13,.2f}")
    
    diff_charges = alms_row[0] - lms_row[0]
    diff_amt = (alms_row[2] if alms_row[2] else 0) - (lms_row[2] if lms_row[2] else 0)
    print(f"{'Difference':<12} {diff_charges:>10,} {alms_row[1] - lms_row[1]:>10,} ${diff_amt:>13,.2f}")
    
    if diff_charges > 0:
        print(f"\n⚠️  ALMSDATA has {diff_charges:,} MORE charges than LMS (${diff_amt:,.2f})")
        print("    This could indicate doubled entries or legitimate additions")
    elif diff_charges < 0:
        print(f"\n⚠️  LMS has {abs(diff_charges):,} MORE charges than ALMSDATA (${abs(diff_amt):,.2f})")
        print("    This could indicate missing data in almsdata")
    
    # Sample 2026 charters with mismatches
    cur.execute("""
        SELECT 
            c.reserve_number,
            c.charter_date,
            c.customer_name,
            COALESCE(lms_charges.count, 0) as lms_count,
            COALESCE(lms_charges.total, 0) as lms_total,
            COALESCE(alms_charges.count, 0) as alms_count,
            COALESCE(alms_charges.total, 0) as alms_total,
            c.total_amount_due
        FROM charters c
        LEFT JOIN (
            SELECT lms.reserve_no, COUNT(*) as count, SUM(lms.amount) as total
            FROM lms2026_charges lms
            GROUP BY lms.reserve_no
        ) lms_charges ON lms_charges.reserve_no = c.reserve_number
        LEFT JOIN (
            SELECT cc.reserve_number, COUNT(*) as count, SUM(cc.amount) as total
            FROM charter_charges cc
            GROUP BY cc.reserve_number
        ) alms_charges ON alms_charges.reserve_number = c.reserve_number
        WHERE c.charter_date >= '2026-01-01'
          AND ABS(COALESCE(lms_charges.total, 0) - COALESCE(alms_charges.total, 0)) > 0.01
        ORDER BY ABS(COALESCE(lms_charges.total, 0) - COALESCE(alms_charges.total, 0)) DESC
        LIMIT 15
    """)
    
    print("\nSample 2026 charters with charge mismatches:")
    print("-" * 120)
    print(f"{'Reserve':<10} {'Date':<12} {'Customer':<25} {'LMS#':>5} {'LMS$':>10} {'ALMS#':>5} {'ALMS$':>10} {'ChrtTotal':>12}")
    print("-" * 120)
    for row in cur.fetchall():
        print(f"{row[0]:<10} {str(row[1]):<12} {(row[2] or 'N/A')[:25]:<25} "
              f"{row[3]:>5} ${row[4]:>9,.2f} {row[5]:>5} ${row[6]:>9,.2f} ${row[7] if row[7] else 0:>11,.2f}")
    
    conn.close()

def compare_payment_totals():
    """Compare payment totals and matching"""
    print("\n" + "=" * 80)
    print("4. PAYMENT MATCHING VERIFICATION")
    print("=" * 80)
    
    conn = connect()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            COUNT(DISTINCT lms.reserve_no) as charters,
            COUNT(*) as payments,
            SUM(lms.amount) as total
        FROM lms2026_payments lms
        WHERE lms.reserve_no IS NOT NULL AND lms.reserve_no != ''
    """)
    lms_row = cur.fetchone()
    
    cur.execute("""
        SELECT 
            COUNT(DISTINCT p.reserve_number) as charters,
            COUNT(*) as payments,
            SUM(p.amount) as total
        FROM payments p
        WHERE p.reserve_number IS NOT NULL AND p.reserve_number != ''
    """)
    alms_row = cur.fetchone()
    
    print(f"\n{'Source':<12} {'Charters':>10} {'Payments':>10} {'Total Paid':>15}")
    print("-" * 80)
    print(f"{'LMS':<12} {lms_row[0]:>10,} {lms_row[1]:>10,} ${lms_row[2] if lms_row[2] else 0:>13,.2f}")
    print(f"{'ALMSDATA':<12} {alms_row[0]:>10,} {alms_row[1]:>10,} ${alms_row[2] if alms_row[2] else 0:>13,.2f}")
    
    diff_payments = alms_row[1] - lms_row[1]
    diff_amt = (alms_row[2] if alms_row[2] else 0) - (lms_row[2] if lms_row[2] else 0)
    print(f"{'Difference':<12} {alms_row[0] - lms_row[0]:>10,} {diff_payments:>10,} ${diff_amt:>13,.2f}")
    
    if diff_amt > 10000:
        print(f"\n⚠️  ALMSDATA has ${diff_amt:,.2f} MORE in payments than LMS")
        print("    This could indicate doubled payments or legitimate additional payments")
    
    conn.close()

def main():
    print("=" * 80)
    print("CRITICAL ALMSDATA INTEGRITY CHECK")
    print("User Concern: Square payments may be doubled, need to verify data sources")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    check_square_doubles()
    compare_driver_vehicle_routing()
    verify_2026_charges()
    compare_payment_totals()
    
    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("1. Review duplicates above - if Square payments are doubled, need to remove")
    print("2. Check which system (LMS vs ALMSDATA) has more complete driver/vehicle data")
    print("3. Verify 2026 charges - determine authoritative source")
    print("4. Review payment totals - investigate if difference is legitimate or doubled")

if __name__ == "__main__":
    main()
