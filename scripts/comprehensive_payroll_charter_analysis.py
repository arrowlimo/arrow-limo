#!/usr/bin/env python3
"""
Comprehensive payroll-charter matching analysis to answer:
1. Is all payroll data applied to charters?
2. What years are missing payroll-charter matches?
3. Which cancelled charters have drivers assigned (need removal)?
4. Were hosts/training (second drivers) paid and recorded?
5. Do we need to cancel more charters?
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def analyze_payroll_charter_matching():
    """Check if all payroll entries are linked to charters"""
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=" * 80)
    print("1. PAYROLL-CHARTER MATCHING STATUS")
    print("=" * 80)
    
    # Total payroll entries
    cur.execute("""
        SELECT COUNT(*) as total,
               COUNT(charter_id) as with_charter_id,
               COUNT(CASE WHEN charter_id IS NULL THEN 1 END) as no_charter_id,
               SUM(CASE WHEN payroll_class = 'WAGE' OR payroll_class IS NULL THEN gross_pay ELSE 0 END) as total_wages
        FROM driver_payroll
        WHERE payroll_class = 'WAGE' OR payroll_class IS NULL
    """)
    
    payroll = cur.fetchone()
    
    print(f"\n📊 PAYROLL SUMMARY (WAGE entries only):")
    print(f"   Total payroll entries: {payroll['total']:,}")
    print(f"   With charter_id: {payroll['with_charter_id']:,} ({payroll['with_charter_id']/payroll['total']*100:.1f}%)")
    print(f"   WITHOUT charter_id: {payroll['no_charter_id']:,} ({payroll['no_charter_id']/payroll['total']*100:.1f}%)")
    print(f"   Total wages paid: ${payroll['total_wages']:,.2f}")
    
    # Unlinked payroll by year
    cur.execute("""
        SELECT EXTRACT(YEAR FROM pay_date) as year,
               COUNT(*) as unlinked_count,
               SUM(gross_pay) as unlinked_wages
        FROM driver_payroll
        WHERE (payroll_class = 'WAGE' OR payroll_class IS NULL)
        AND charter_id IS NULL
        GROUP BY EXTRACT(YEAR FROM pay_date)
        ORDER BY year
    """)
    
    unlinked_by_year = cur.fetchall()
    
    if unlinked_by_year:
        print(f"\n📅 UNLINKED PAYROLL BY YEAR:")
        for row in unlinked_by_year:
            year = int(row['year']) if row['year'] else 'NULL'
            print(f"   {year}: {row['unlinked_count']:,} entries, ${row['unlinked_wages']:,.2f}")
    
    # Check if unlinked payroll has reserve numbers
    cur.execute("""
        SELECT COUNT(*) as cnt,
               SUM(gross_pay) as total_pay
        FROM driver_payroll
        WHERE (payroll_class = 'WAGE' OR payroll_class IS NULL)
        AND charter_id IS NULL
        AND reserve_number IS NOT NULL
    """)
    
    has_reserve = cur.fetchone()
    
    if has_reserve['cnt'] > 0:
        print(f"\n🔍 UNLINKED PAYROLL WITH RESERVE NUMBERS:")
        print(f"   Count: {has_reserve['cnt']:,}")
        print(f"   Total pay: ${has_reserve['total_pay']:,.2f}")
        print(f"   → These could potentially be matched!")
        
        # Sample unlinked with reserve numbers
        cur.execute("""
            SELECT reserve_number, pay_date, gross_pay
            FROM driver_payroll
            WHERE (payroll_class = 'WAGE' OR payroll_class IS NULL)
            AND charter_id IS NULL
            AND reserve_number IS NOT NULL
            ORDER BY pay_date DESC
            LIMIT 10
        """)
        
        samples = cur.fetchall()
        print(f"\n   Sample unlinked payroll with reserve numbers:")
        for s in samples:
            print(f"      {s['reserve_number']}: ${s['gross_pay']:.2f} on {s['pay_date']}")
    
    cur.close()
    conn.close()

def analyze_cancelled_with_drivers():
    """Find cancelled charters that still have drivers assigned"""
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("\n" + "=" * 80)
    print("2. CANCELLED CHARTERS WITH DRIVERS ASSIGNED")
    print("=" * 80)
    
    # Cancelled charters with drivers
    cur.execute("""
        SELECT COUNT(*) as total_cancelled,
               COUNT(CASE WHEN assigned_driver_id IS NOT NULL THEN 1 END) as with_driver
        FROM charters
        WHERE cancelled = true
    """)
    
    cancelled = cur.fetchone()
    
    print(f"\n📊 CANCELLED CHARTERS:")
    print(f"   Total cancelled: {cancelled['total_cancelled']:,}")
    print(f"   With driver assigned: {cancelled['with_driver']:,} ({cancelled['with_driver']/cancelled['total_cancelled']*100:.1f}%)")
    
    if cancelled['with_driver'] > 0:
        print(f"\n   [WARN] These {cancelled['with_driver']:,} cancelled charters should NOT have drivers!")
        
        # Sample cancelled with drivers
        cur.execute("""
            SELECT c.reserve_number, c.charter_date, c.cancelled,
                   e.full_name as driver_name,
                   c.balance, c.total_amount_due
            FROM charters c
            LEFT JOIN employees e ON e.employee_id = c.assigned_driver_id
            WHERE c.cancelled = true
            AND c.assigned_driver_id IS NOT NULL
            ORDER BY c.charter_date DESC
            LIMIT 15
        """)
        
        samples = cur.fetchall()
        print(f"\n   📋 Sample cancelled charters with drivers (need cleanup):")
        for s in samples:
            print(f"      {s['reserve_number']} ({s['charter_date']}): {s['driver_name']} - Bal: ${s['balance'] or 0:.2f}")
    
    # Check if cancelled charters have payroll
    cur.execute("""
        SELECT COUNT(DISTINCT c.charter_id) as cnt,
               SUM(dp.gross_pay) as total_pay
        FROM charters c
        JOIN driver_payroll dp ON dp.charter_id::integer = c.charter_id
        WHERE c.cancelled = true
        AND (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
    """)
    
    cancelled_paid = cur.fetchone()
    
    if cancelled_paid['cnt'] > 0:
        print(f"\n   [WARN] CANCELLED CHARTERS WITH PAYROLL:")
        print(f"      {cancelled_paid['cnt']:,} cancelled charters have payroll entries")
        print(f"      Total paid: ${cancelled_paid['total_pay']:,.2f}")
        print(f"      → These may be last-minute cancellations where driver was paid anyway")
    
    cur.close()
    conn.close()

def analyze_multiple_drivers_per_charter():
    """Check if hosts/training drivers (second employees) are recorded"""
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("\n" + "=" * 80)
    print("3. HOSTS / TRAINING DRIVERS (MULTIPLE EMPLOYEES PER CHARTER)")
    print("=" * 80)
    
    # Charters with multiple payroll entries
    cur.execute("""
        SELECT charter_id, COUNT(*) as employee_count,
               SUM(gross_pay) as total_pay,
               ARRAY_AGG(e.full_name) as employees,
               ARRAY_AGG(dp.gross_pay) as pay_amounts
        FROM driver_payroll dp
        LEFT JOIN employees e ON e.employee_id = dp.employee_id
        WHERE (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
        AND charter_id IS NOT NULL
        GROUP BY charter_id
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
        LIMIT 20
    """)
    
    multiple = cur.fetchall()
    
    if multiple:
        print(f"\n📊 CHARTERS WITH MULTIPLE EMPLOYEES:")
        print(f"   Found {len(multiple):,} charters with 2+ payroll entries")
        
        print(f"\n   📋 Sample charters with multiple employees:")
        for m in multiple[:10]:
            employees_str = ', '.join([f"{name} (${pay:.2f})" for name, pay in zip(m['employees'], m['pay_amounts']) if name])
            print(f"      Charter {m['charter_id']}: {m['employee_count']} employees, ${m['total_pay']:.2f} total")
            print(f"         → {employees_str}")
        
        # Check if charter has single assigned_driver_id but multiple payroll
        cur.execute("""
            SELECT c.charter_id, c.reserve_number, c.assigned_driver_id,
                   e_assigned.full_name as assigned_driver,
                   COUNT(dp.id) as payroll_count
            FROM charters c
            JOIN driver_payroll dp ON dp.charter_id::integer = c.charter_id
            LEFT JOIN employees e_assigned ON e_assigned.employee_id = c.assigned_driver_id
            WHERE (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
            AND c.assigned_driver_id IS NOT NULL
            GROUP BY c.charter_id, c.reserve_number, c.assigned_driver_id, e_assigned.full_name
            HAVING COUNT(dp.id) > 1
            LIMIT 10
        """)
        
        single_assigned = cur.fetchall()
        
        if single_assigned:
            print(f"\n   [WARN] LIMITATION: Charter has single assigned_driver_id but multiple paid:")
            print(f"      {len(single_assigned):,} charters show this pattern")
            print(f"      → Second driver (host/training) not tracked in charter.assigned_driver_id")
            print(f"      → Only payroll table shows multiple employees")
    else:
        print(f"\n✓ No charters with multiple payroll entries found")
        print(f"   → Hosts/training drivers may not be separately tracked in payroll")
    
    cur.close()
    conn.close()

def analyze_charters_needing_cancellation():
    """Identify charters that should potentially be cancelled"""
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("\n" + "=" * 80)
    print("4. CHARTERS THAT MAY NEED CANCELLATION")
    print("=" * 80)
    
    # Charters with no payroll, no payments, old dates
    cur.execute("""
        SELECT COUNT(*) as cnt
        FROM charters c
        WHERE c.cancelled = false
        AND c.charter_date < CURRENT_DATE - INTERVAL '30 days'
        AND NOT EXISTS (
            SELECT 1 FROM driver_payroll dp 
            WHERE dp.charter_id::integer = c.charter_id
            AND (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
        )
        AND NOT EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.charter_id = c.charter_id
        )
        AND c.total_amount_due > 0
    """)
    
    suspect = cur.fetchone()['cnt']
    
    print(f"\n📊 SUSPECT CHARTERS (old, no payroll, no payments, amount due):")
    print(f"   Found: {suspect:,} charters")
    
    if suspect > 0:
        print(f"   → These may be bookings that never happened")
        
        # Sample suspect charters
        cur.execute("""
            SELECT c.reserve_number, c.charter_date, c.total_amount_due, c.balance,
                   c.assigned_driver_id
            FROM charters c
            WHERE c.cancelled = false
            AND c.charter_date < CURRENT_DATE - INTERVAL '30 days'
            AND NOT EXISTS (
                SELECT 1 FROM driver_payroll dp 
                WHERE dp.charter_id::integer = c.charter_id
                AND (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
            )
            AND NOT EXISTS (
                SELECT 1 FROM payments p 
                WHERE p.charter_id = c.charter_id
            )
            AND c.total_amount_due > 0
            ORDER BY c.charter_date DESC
            LIMIT 20
        """)
        
        samples = cur.fetchall()
        print(f"\n   📋 Sample suspect charters:")
        for s in samples:
            driver = '✓ Has driver' if s['assigned_driver_id'] else '✗ No driver'
            print(f"      {s['reserve_number']} ({s['charter_date']}): ${s['total_amount_due']:.2f} due, {driver}")
    
    # Future charters (2026+)
    cur.execute("""
        SELECT COUNT(*) as cnt,
               COUNT(CASE WHEN assigned_driver_id IS NOT NULL THEN 1 END) as with_driver
        FROM charters
        WHERE cancelled = false
        AND charter_date >= '2026-01-01'
    """)
    
    future = cur.fetchone()
    
    print(f"\n📅 FUTURE BOOKINGS (2026+):")
    print(f"   Total: {future['cnt']:,}")
    print(f"   With driver: {future['with_driver']:,}")
    print(f"   → These are legitimate future bookings, not cancellation candidates")
    
    cur.close()
    conn.close()

def analyze_payroll_coverage_by_year():
    """Show payroll-charter matching by year"""
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("\n" + "=" * 80)
    print("5. PAYROLL COVERAGE BY YEAR")
    print("=" * 80)
    
    # Charters by year with payroll status
    cur.execute("""
        SELECT EXTRACT(YEAR FROM c.charter_date) as year,
               COUNT(*) as total_charters,
               COUNT(CASE WHEN EXISTS (
                   SELECT 1 FROM driver_payroll dp 
                   WHERE dp.charter_id::integer = c.charter_id
                   AND (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
               ) THEN 1 END) as with_payroll,
               COUNT(CASE WHEN c.assigned_driver_id IS NOT NULL THEN 1 END) as with_driver
        FROM charters c
        WHERE c.cancelled = false
        AND c.charter_date IS NOT NULL
        GROUP BY EXTRACT(YEAR FROM c.charter_date)
        ORDER BY year
    """)
    
    by_year = cur.fetchall()
    
    print(f"\n📊 CHARTER-PAYROLL MATCHING BY YEAR:")
    print(f"\n   {'Year':<8} {'Total':<10} {'W/Payroll':<12} {'W/Driver':<12} {'Match %':<10}")
    print(f"   {'-'*70}")
    
    for row in by_year:
        year = int(row['year']) if row['year'] else 'NULL'
        total = row['total_charters']
        with_payroll = row['with_payroll']
        with_driver = row['with_driver']
        match_pct = (with_payroll / total * 100) if total > 0 else 0
        
        status = '✓' if match_pct >= 95 else '[WARN]' if match_pct >= 80 else '✗'
        
        print(f"   {year:<8} {total:<10,} {with_payroll:<12,} {with_driver:<12,} {match_pct:<9.1f}% {status}")
    
    cur.close()
    conn.close()

def main():
    print("=" * 80)
    print("COMPREHENSIVE PAYROLL-CHARTER ANALYSIS")
    print("=" * 80)
    print("\nAnswering key questions:")
    print("1. Is all payroll data applied to charters?")
    print("2. What years are missing payroll-charter matches?")
    print("3. Which cancelled charters have drivers (need removal)?")
    print("4. Are hosts/training drivers recorded separately?")
    print("5. Do we need to cancel more charters?")
    print("=" * 80)
    
    analyze_payroll_charter_matching()
    analyze_cancelled_with_drivers()
    analyze_multiple_drivers_per_charter()
    analyze_charters_needing_cancellation()
    analyze_payroll_coverage_by_year()
    
    print("\n" + "=" * 80)
    print("✓ ANALYSIS COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    main()
