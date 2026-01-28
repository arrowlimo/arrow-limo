#!/usr/bin/env python3
"""
Sync charter driver hours with actual payroll data (CRA authoritative source)

The driver_payroll table contains the authoritative pay data (CRA compliance).
We need to:
1. Calculate hours worked from gross_pay / hourly_rate in driver_payroll
2. Update charter.driver_hours_worked to match payroll hours
3. Update charter.driver_base_pay to match payroll gross_pay
4. Ensure data consistency between charters and payroll

This ensures charter records reflect what drivers were ACTUALLY paid.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import argparse
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def analyze_payroll_charter_linkage(conn):
    """Analyze current state of payroll-charter linkage"""
    
    print("=" * 80)
    print("PAYROLL-CHARTER LINKAGE ANALYSIS")
    print("=" * 80)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get payroll records with charter links
    cur.execute("""
        SELECT COUNT(*) as total,
               COUNT(charter_id) as with_charter_id,
               COUNT(reserve_number) as with_reserve,
               COUNT(CASE WHEN payroll_class = 'WAGE' OR payroll_class IS NULL THEN 1 END) as wage_entries,
               SUM(CASE WHEN payroll_class = 'WAGE' OR payroll_class IS NULL THEN gross_pay ELSE 0 END) as total_wages
        FROM driver_payroll
    """)
    
    payroll_summary = cur.fetchone()
    
    print(f"\n📊 PAYROLL TABLE STATUS:")
    print(f"   Total payroll records: {payroll_summary['total']:,}")
    print(f"   With charter_id: {payroll_summary['with_charter_id']:,} ({payroll_summary['with_charter_id']/payroll_summary['total']*100:.1f}%)")
    print(f"   With reserve_number: {payroll_summary['with_reserve']:,} ({payroll_summary['with_reserve']/payroll_summary['total']*100:.1f}%)")
    print(f"   Wage entries (non-ADJ): {payroll_summary['wage_entries']:,}")
    print(f"   Total wages paid: ${payroll_summary['total_wages']:,.2f}")
    
    # Check charters with payroll links
    cur.execute("""
        SELECT COUNT(*) as total_charters,
               COUNT(CASE WHEN EXISTS (
                   SELECT 1 FROM driver_payroll dp 
                   WHERE dp.charter_id::integer = c.charter_id
                   AND (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
               ) THEN 1 END) as with_payroll,
               COUNT(driver_hours_worked) as with_hours,
               COUNT(driver_base_pay) as with_base_pay
        FROM charters c
        WHERE cancelled = false
    """)
    
    charter_summary = cur.fetchone()
    
    print(f"\n📋 CHARTER TABLE STATUS:")
    print(f"   Total active charters: {charter_summary['total_charters']:,}")
    print(f"   Linked to payroll: {charter_summary['with_payroll']:,} ({charter_summary['with_payroll']/charter_summary['total_charters']*100:.1f}%)")
    print(f"   With driver_hours_worked: {charter_summary['with_hours']:,} ({charter_summary['with_hours']/charter_summary['total_charters']*100:.1f}%)")
    print(f"   With driver_base_pay: {charter_summary['with_base_pay']:,} ({charter_summary['with_base_pay']/charter_summary['total_charters']*100:.1f}%)")
    
    # Sample mismatches
    print(f"\n🔍 SAMPLE CHARTER-PAYROLL MISMATCHES:")
    cur.execute("""
        SELECT c.charter_id, c.reserve_number, c.charter_date,
               c.driver_hours_worked as charter_hours,
               c.driver_base_pay as charter_pay,
               dp.gross_pay as payroll_pay,
               (dp.gross_pay / NULLIF(c.driver_hourly_rate, 0)) as calculated_hours,
               c.driver_hourly_rate
        FROM charters c
        JOIN driver_payroll dp ON dp.charter_id::integer = c.charter_id
        WHERE (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
        AND c.cancelled = false
        AND (
            c.driver_hours_worked IS NULL 
            OR c.driver_base_pay IS NULL
            OR ABS(c.driver_base_pay - dp.gross_pay) > 1
        )
        ORDER BY c.charter_date DESC
        LIMIT 10
    """)
    
    mismatches = cur.fetchall()
    if mismatches:
        for row in mismatches:
            print(f"\n   Charter {row['reserve_number']} ({row['charter_date']}):")
            print(f"      Charter hours: {row['charter_hours']} | Charter pay: ${row['charter_pay'] or 0}")
            print(f"      Payroll pay: ${row['payroll_pay']} | Hourly rate: ${row['driver_hourly_rate'] or 0}")
            if row['calculated_hours']:
                print(f"      Calculated hours from payroll: {float(row['calculated_hours']):.2f}")
    else:
        print("   No mismatches found (or no payroll links exist)")
    
    cur.close()
    return payroll_summary, charter_summary

def calculate_driver_pay_by_charter(conn, dry_run=True):
    """Calculate driver pay for each charter from payroll records"""
    
    print(f"\n" + "=" * 80)
    print("CALCULATING DRIVER PAY BY CHARTER FROM PAYROLL")
    print("=" * 80)
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get all payroll entries linked to charters (WAGE only)
    cur.execute("""
        SELECT dp.id as payroll_id,
               dp.charter_id,
               dp.reserve_number,
               dp.gross_pay,
               dp.employee_id,
               dp.driver_id,
               c.charter_id as charter_pk,
               c.driver_hourly_rate,
               c.driver_hours_worked as current_hours,
               c.driver_base_pay as current_pay,
               c.reserve_number as charter_reserve
        FROM driver_payroll dp
        LEFT JOIN charters c ON dp.charter_id::integer = c.charter_id
        WHERE (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
        AND dp.gross_pay > 0
        AND dp.charter_id IS NOT NULL
        AND dp.charter_id != ''
        ORDER BY dp.charter_id
    """)
    
    payroll_entries = cur.fetchall()
    
    print(f"\n📊 Found {len(payroll_entries):,} payroll entries linked to charters")
    
    # Group by charter_id
    charter_pay_map = {}
    unlinked_payroll = []
    
    for entry in payroll_entries:
        if not entry['charter_pk']:
            unlinked_payroll.append(entry)
            continue
        
        charter_id = entry['charter_pk']
        
        if charter_id not in charter_pay_map:
            charter_pay_map[charter_id] = {
                'charter_id': charter_id,
                'reserve_number': entry['charter_reserve'],
                'payroll_entries': [],
                'total_pay': Decimal(0),
                'current_hours': entry['current_hours'],
                'current_pay': entry['current_pay'],
                'hourly_rate': entry['driver_hourly_rate']
            }
        
        charter_pay_map[charter_id]['payroll_entries'].append(entry)
        charter_pay_map[charter_id]['total_pay'] += entry['gross_pay']
    
    print(f"   Linked to {len(charter_pay_map):,} unique charters")
    print(f"   Unlinked payroll entries: {len(unlinked_payroll):,}")
    
    # Calculate updates needed
    updates_needed = []
    
    for charter_id, data in charter_pay_map.items():
        total_pay = data['total_pay']
        hourly_rate = data['hourly_rate'] or Decimal(0)
        
        # Calculate hours from pay
        if hourly_rate > 0:
            calculated_hours = total_pay / hourly_rate
        else:
            calculated_hours = None
        
        # Check if update needed
        current_pay = data['current_pay'] or Decimal(0)
        current_hours = data['current_hours'] or Decimal(0)
        
        needs_update = False
        if abs(current_pay - total_pay) > 1:  # More than $1 difference
            needs_update = True
        if calculated_hours and abs(float(current_hours) - float(calculated_hours)) > 0.1:  # More than 0.1 hour difference
            needs_update = True
        
        if needs_update:
            updates_needed.append({
                'charter_id': charter_id,
                'reserve_number': data['reserve_number'],
                'current_pay': current_pay,
                'new_pay': total_pay,
                'current_hours': current_hours,
                'new_hours': calculated_hours,
                'hourly_rate': hourly_rate,
                'payroll_count': len(data['payroll_entries'])
            })
    
    print(f"\n📝 UPDATES NEEDED:")
    print(f"   Charters requiring updates: {len(updates_needed):,}")
    
    if updates_needed:
        print(f"\n   Sample updates (first 10):")
        for update in updates_needed[:10]:
            print(f"\n      Charter {update['reserve_number']}:")
            print(f"         Pay: ${update['current_pay']:,.2f} → ${update['new_pay']:,.2f}")
            if update['new_hours']:
                print(f"         Hours: {float(update['current_hours']):.2f} → {float(update['new_hours']):.2f}")
            print(f"         Hourly rate: ${update['hourly_rate']:,.2f}")
            print(f"         Payroll entries: {update['payroll_count']}")
    
    if not dry_run and updates_needed:
        print(f"\n✍️  APPLYING UPDATES...")
        
        update_count = 0
        for update in updates_needed:
            cur.execute("""
                UPDATE charters
                SET driver_base_pay = %s,
                    driver_hours_worked = %s,
                    driver_total_expense = driver_base_pay + COALESCE(driver_gratuity, 0),
                    driver_notes = COALESCE(driver_notes || E'\n', '') || 
                                  'Pay synced from payroll: $' || %s || 
                                  ' (' || %s || ' entries, ' || %s || ' hours calculated)'
                WHERE charter_id = %s
            """, (
                update['new_pay'],
                update['new_hours'],
                f"{update['new_pay']:.2f}",
                update['payroll_count'],
                f"{float(update['new_hours']):.2f}" if update['new_hours'] else 'N/A',
                update['charter_id']
            ))
            update_count += 1
        
        conn.commit()
        print(f"   [OK] Updated {update_count:,} charters")
    else:
        print(f"\n   🔍 DRY RUN - Use --write to apply updates")
    
    cur.close()
    return updates_needed, unlinked_payroll

def main():
    parser = argparse.ArgumentParser(
        description='Sync charter driver pay/hours with payroll data (CRA authoritative)'
    )
    parser.add_argument('--write', action='store_true',
                       help='Apply updates (default is dry-run)')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("CHARTER DRIVER PAY CALCULATION FROM PAYROLL (CRA DATA)")
    print("=" * 80)
    print("""
This script ensures charter driver pay/hours match the authoritative payroll data.

Payroll records (driver_payroll) are the CRA-compliant source of truth.
Charter records will be updated to reflect actual amounts paid to drivers.
    """)
    
    conn = get_db_connection()
    
    try:
        # Analyze current state
        payroll_summary, charter_summary = analyze_payroll_charter_linkage(conn)
        
        # Calculate and apply updates
        updates, unlinked = calculate_driver_pay_by_charter(conn, dry_run=not args.write)
        
        print(f"\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"""
Payroll Analysis:
- Total payroll records: {payroll_summary['total']:,}
- Wage entries: {payroll_summary['wage_entries']:,}
- Total wages paid: ${payroll_summary['total_wages']:,.2f}

Charter Analysis:
- Total active charters: {charter_summary['total_charters']:,}
- Linked to payroll: {charter_summary['with_payroll']:,}

Updates:
- Charters needing sync: {len(updates):,}
- Unlinked payroll entries: {len(unlinked):,}

{'[OK] UPDATES APPLIED' if args.write else '🔍 DRY RUN MODE - Use --write to apply'}
        """)
        
    finally:
        conn.close()

if __name__ == '__main__':
    main()
