"""
Audit charter data for missing information across all years.
Check for incomplete fields, missing required data, and data quality issues.
"""
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("\n" + "=" * 100)
    print("CHARTER DATA COMPLETENESS AUDIT")
    print("=" * 100)
    
    # Get total charter count
    cur.execute("SELECT COUNT(*) as total FROM charters")
    total_charters = cur.fetchone()['total']
    print(f"\nTotal Charters: {total_charters:,}")
    
    # Check missing critical fields
    print("\n" + "=" * 100)
    print("CRITICAL FIELDS MISSING DATA")
    print("=" * 100)
    
    critical_fields = {
        'reserve_number': 'Reservation Number',
        'charter_date': 'Charter Date',
        'client_id': 'Client ID',
        'total_amount_due': 'Total Amount Due',
        'pickup_address': 'Pickup Address',
        'dropoff_address': 'Dropoff Address'
    }
    
    missing_data = {}
    for field, label in critical_fields.items():
        if field == 'total_amount_due':
            cur.execute(f"""
                SELECT COUNT(*) as missing
                FROM charters
                WHERE {field} IS NULL OR {field} = 0
            """)
        elif field == 'charter_date':
            cur.execute(f"""
                SELECT COUNT(*) as missing
                FROM charters
                WHERE {field} IS NULL
            """)
        elif field == 'client_id':
            cur.execute(f"""
                SELECT COUNT(*) as missing
                FROM charters
                WHERE {field} IS NULL
            """)
        else:
            cur.execute(f"""
                SELECT COUNT(*) as missing
                FROM charters
                WHERE {field} IS NULL OR {field} = ''
            """)
        missing = cur.fetchone()['missing']
        pct = (missing / total_charters * 100) if total_charters > 0 else 0
        missing_data[field] = {'count': missing, 'pct': pct, 'label': label}
        
        status = "[!]" if pct > 5 else "[OK]" if missing == 0 else "[*]"
        print(f"{status} {label:<25} Missing: {missing:>6,} ({pct:>5.1f}%)")
    
    # Check vehicle information
    print("\n" + "=" * 100)
    print("VEHICLE INFORMATION")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN vehicle IS NULL OR vehicle = '' THEN 1 END) as missing_vehicle,
            COUNT(CASE WHEN vehicle_id IS NULL THEN 1 END) as missing_vehicle_id,
            COUNT(CASE WHEN vehicle_type_requested IS NULL OR vehicle_type_requested = '' THEN 1 END) as missing_type
        FROM charters
    """)
    vehicle_info = cur.fetchone()
    
    print(f"[!] Missing Vehicle Name: {vehicle_info['missing_vehicle']:,} ({vehicle_info['missing_vehicle']/total_charters*100:.1f}%)")
    print(f"[!] Missing Vehicle ID: {vehicle_info['missing_vehicle_id']:,} ({vehicle_info['missing_vehicle_id']/total_charters*100:.1f}%)")
    print(f"[*] Missing Vehicle Type: {vehicle_info['missing_type']:,} ({vehicle_info['missing_type']/total_charters*100:.1f}%)")
    
    # Check driver information
    print("\n" + "=" * 100)
    print("DRIVER INFORMATION")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN driver IS NULL OR driver = '' THEN 1 END) as missing_driver_name,
            COUNT(CASE WHEN assigned_driver_id IS NULL THEN 1 END) as missing_driver_id,
            COUNT(CASE WHEN employee_id IS NULL THEN 1 END) as missing_employee_id
        FROM charters
    """)
    driver_info = cur.fetchone()
    
    print(f"[*] Missing Driver Name: {driver_info['missing_driver_name']:,} ({driver_info['missing_driver_name']/total_charters*100:.1f}%)")
    print(f"[!] Missing Driver ID (assigned): {driver_info['missing_driver_id']:,} ({driver_info['missing_driver_id']/total_charters*100:.1f}%)")
    print(f"[!] Missing Employee ID: {driver_info['missing_employee_id']:,} ({driver_info['missing_employee_id']/total_charters*100:.1f}%)")
    
    # Check financial fields
    print("\n" + "=" * 100)
    print("FINANCIAL FIELDS")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN rate IS NULL OR rate = 0 THEN 1 END) as missing_rate,
            COUNT(CASE WHEN total_amount_due IS NULL OR total_amount_due = 0 THEN 1 END) as missing_total,
            COUNT(CASE WHEN paid_amount IS NULL THEN 1 END) as missing_paid,
            COUNT(CASE WHEN balance IS NULL THEN 1 END) as missing_balance,
            COUNT(CASE WHEN payment_status IS NULL OR payment_status = '' THEN 1 END) as missing_payment_status
        FROM charters
    """)
    financial = cur.fetchone()
    
    print(f"[*] Missing Rate: {financial['missing_rate']:,} ({financial['missing_rate']/total_charters*100:.1f}%)")
    print(f"[!] Missing Total Amount: {financial['missing_total']:,} ({financial['missing_total']/total_charters*100:.1f}%)")
    print(f"[OK] Missing Paid Amount: {financial['missing_paid']:,} ({financial['missing_paid']/total_charters*100:.1f}%)")
    print(f"[OK] Missing Balance: {financial['missing_balance']:,} ({financial['missing_balance']/total_charters*100:.1f}%)")
    print(f"[*] Missing Payment Status: {financial['missing_payment_status']:,} ({financial['missing_payment_status']/total_charters*100:.1f}%)")
    
    # Check charter status
    print("\n" + "=" * 100)
    print("CHARTER STATUS")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            status,
            COUNT(*) as count
        FROM charters
        GROUP BY status
        ORDER BY count DESC
    """)
    statuses = cur.fetchall()
    
    for s in statuses:
        status_val = s['status'] or 'NULL'
        print(f"  {status_val:<20} {s['count']:>6,} ({s['count']/total_charters*100:>5.1f}%)")
    
    # Check cancelled/closed charters
    print("\n" + "=" * 100)
    print("CANCELLED/CLOSED CHARTERS")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN cancelled = TRUE THEN 1 END) as cancelled,
            COUNT(CASE WHEN closed = TRUE THEN 1 END) as closed,
            COUNT(CASE WHEN cancelled = TRUE AND closed = TRUE THEN 1 END) as both
        FROM charters
    """)
    cancel_info = cur.fetchone()
    
    print(f"Cancelled: {cancel_info['cancelled']:,} ({cancel_info['cancelled']/total_charters*100:.1f}%)")
    print(f"Closed: {cancel_info['closed']:,} ({cancel_info['closed']/total_charters*100:.1f}%)")
    print(f"Both: {cancel_info['both']:,}")
    
    # Check time information
    print("\n" + "=" * 100)
    print("TIME INFORMATION")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN pickup_time IS NULL THEN 1 END) as missing_pickup_time,
            COUNT(CASE WHEN reservation_time IS NULL THEN 1 END) as missing_reservation_time,
            COUNT(CASE WHEN actual_start_time IS NULL THEN 1 END) as missing_actual_start,
            COUNT(CASE WHEN actual_end_time IS NULL THEN 1 END) as missing_actual_end
        FROM charters
    """)
    time_info = cur.fetchone()
    
    print(f"[*] Missing Pickup Time: {time_info['missing_pickup_time']:,} ({time_info['missing_pickup_time']/total_charters*100:.1f}%)")
    print(f"[*] Missing Reservation Time: {time_info['missing_reservation_time']:,} ({time_info['missing_reservation_time']/total_charters*100:.1f}%)")
    print(f"[*] Missing Actual Start: {time_info['missing_actual_start']:,} ({time_info['missing_actual_start']/total_charters*100:.1f}%)")
    print(f"[*] Missing Actual End: {time_info['missing_actual_end']:,} ({time_info['missing_actual_end']/total_charters*100:.1f}%)")
    
    # Check charter charges linkage
    print("\n" + "=" * 100)
    print("CHARTER CHARGES LINKAGE")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            COUNT(*) as charters_with_charges
        FROM charters c
        WHERE EXISTS (
            SELECT 1 FROM charter_charges cc
            WHERE cc.charter_id = c.charter_id
        )
    """)
    with_charges = cur.fetchone()['charters_with_charges']
    without_charges = total_charters - with_charges
    
    print(f"Charters WITH Charges: {with_charges:,} ({with_charges/total_charters*100:.1f}%)")
    print(f"Charters WITHOUT Charges: {without_charges:,} ({without_charges/total_charters*100:.1f}%)")
    
    # Find charters with total_amount_due but no charges
    cur.execute("""
        SELECT COUNT(*) as count
        FROM charters c
        WHERE (total_amount_due IS NOT NULL AND total_amount_due > 0)
        AND NOT EXISTS (
            SELECT 1 FROM charter_charges cc
            WHERE cc.charter_id = c.charter_id
        )
    """)
    missing_charges = cur.fetchone()['count']
    if missing_charges > 0:
        print(f"[!] Charters with amount but NO charges: {missing_charges:,}")
    
    # Check payments linkage
    print("\n" + "=" * 100)
    print("PAYMENT LINKAGE")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            COUNT(DISTINCT c.charter_id) as charters_with_payments
        FROM charters c
        WHERE EXISTS (
            SELECT 1 FROM payments p
            WHERE p.reserve_number = c.reserve_number
        )
    """)
    with_payments = cur.fetchone()['charters_with_payments']
    without_payments = total_charters - with_payments
    
    print(f"Charters WITH Payments: {with_payments:,} ({with_payments/total_charters*100:.1f}%)")
    print(f"Charters WITHOUT Payments: {without_payments:,} ({without_payments/total_charters*100:.1f}%)")
    
    # Check for charters with balance but no payments
    cur.execute("""
        SELECT COUNT(*) as count
        FROM charters c
        WHERE balance > 0
        AND NOT EXISTS (
            SELECT 1 FROM payments p
            WHERE p.reserve_number = c.reserve_number
        )
    """)
    unpaid_no_payments = cur.fetchone()['count']
    if unpaid_no_payments > 0:
        print(f"[!] Unpaid charters with NO payment records: {unpaid_no_payments:,}")
    
    # Year-by-year breakdown
    print("\n" + "=" * 100)
    print("COMPLETENESS BY YEAR")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM charter_date) as year,
            COUNT(*) as total,
            COUNT(CASE WHEN client_id IS NULL THEN 1 END) as missing_client,
            COUNT(CASE WHEN total_amount_due IS NULL OR total_amount_due = 0 THEN 1 END) as missing_amount,
            COUNT(CASE WHEN vehicle IS NULL OR vehicle = '' THEN 1 END) as missing_vehicle,
            COUNT(CASE WHEN driver IS NULL OR driver = '' THEN 1 END) as missing_driver
        FROM charters
        WHERE charter_date IS NOT NULL
        GROUP BY EXTRACT(YEAR FROM charter_date)
        ORDER BY year
    """)
    yearly = cur.fetchall()
    
    print(f"\n{'Year':<6} {'Charters':<10} {'Missing Client':<15} {'Missing Amount':<15} {'Missing Vehicle':<15} {'Missing Driver':<15}")
    print("-" * 100)
    
    for row in yearly:
        year = int(row['year']) if row['year'] else 'NULL'
        print(f"{year:<6} {row['total']:<10,} {row['missing_client']:<15,} {row['missing_amount']:<15,} "
              f"{row['missing_vehicle']:<15,} {row['missing_driver']:<15,}")
    
    # Sample incomplete charters
    print("\n" + "=" * 100)
    print("SAMPLE INCOMPLETE CHARTERS (Top 10 by Amount)")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            reserve_number,
            charter_date,
            COALESCE(client_id::text, 'NULL') as client_id,
            COALESCE(vehicle, 'NULL') as vehicle,
            COALESCE(driver, 'NULL') as driver,
            COALESCE(total_amount_due, 0) as total_amount_due,
            COALESCE(status, 'NULL') as status
        FROM charters
        WHERE (client_id IS NULL 
           OR vehicle IS NULL OR vehicle = ''
           OR driver IS NULL OR driver = ''
           OR total_amount_due IS NULL OR total_amount_due = 0)
        ORDER BY total_amount_due DESC NULLS LAST
        LIMIT 10
    """)
    samples = cur.fetchall()
    
    if samples:
        print(f"\n{'Reserve#':<12} {'Date':<12} {'Client':<10} {'Vehicle':<15} {'Driver':<15} {'Amount':<12} {'Status':<15}")
        print("-" * 100)
        for s in samples:
            print(f"{s['reserve_number']:<12} {str(s['charter_date']):<12} {s['client_id']:<10} "
                  f"{s['vehicle'][:14]:<15} {s['driver'][:14]:<15} ${s['total_amount_due']:<11,.2f} {s['status']:<15}")
    
    # Summary
    print("\n" + "=" * 100)
    print("SUMMARY & RECOMMENDATIONS")
    print("=" * 100)
    
    critical_issues = []
    
    if missing_data['reserve_number']['count'] > 0:
        critical_issues.append(f"- {missing_data['reserve_number']['count']} charters missing reserve_number")
    
    if missing_data['total_amount_due']['count'] > total_charters * 0.05:
        critical_issues.append(f"- {missing_data['total_amount_due']['count']} charters missing total_amount_due (>{5}%)")
    
    if driver_info['missing_driver_id'] > total_charters * 0.5:
        critical_issues.append(f"- {driver_info['missing_driver_id']:,} charters missing driver ID assignment")
    
    if vehicle_info['missing_vehicle_id'] > total_charters * 0.5:
        critical_issues.append(f"- {vehicle_info['missing_vehicle_id']:,} charters missing vehicle ID assignment")
    
    if missing_charges > 100:
        critical_issues.append(f"- {missing_charges} charters have amount but no charge breakdown")
    
    if critical_issues:
        print("\n[!] CRITICAL ISSUES FOUND:")
        for issue in critical_issues:
            print(f"  {issue}")
    else:
        print("\n[OK] No critical data completeness issues found")
    
    print("\nRECOMMENDATIONS:")
    print("  1. Link driver names to employee_id using employee matching")
    print("  2. Link vehicle names to vehicle_id using vehicle matching")
    print("  3. Create charter_charges for charters with amounts but no breakdown")
    print("  4. Verify client_id linkage for all charters")
    print("  5. Update payment_status field based on balance")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
