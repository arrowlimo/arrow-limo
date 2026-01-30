"""
Investigate why database 2013 payroll records show only 30% of T4 Summary CPP/EI totals.

Expected: T4 Summary CPP $14,387.58, EI $7,137.61
Actual DB: CPP $4,377.31, EI $1,301.25 (69.6% missing CPP, 81.8% missing EI)

Investigate:
1. Payroll_class filtering (WAGE vs ADJUSTMENT)
2. Source system breakdown (LMS, QBO, Square, manual)
3. Monthly coverage gaps
4. Employee coverage (are all employees present?)
5. Year boundary issues (2012 spillover, 2014 mislabeled)
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal
import json
from datetime import datetime

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

def investigate_discrepancy():
    """Comprehensive investigation of database discrepancy."""
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=" * 80)
    print("2013 DATABASE DISCREPANCY INVESTIGATION")
    print("=" * 80)
    print()
    
    print("TARGET VALUES (T4 Summary 2013):")
    print(f"  CPP: $14,387.58")
    print(f"  EI: $7,137.61")
    print()
    
    # 1. Check payroll_class filtering
    print("=" * 80)
    print("1. PAYROLL_CLASS BREAKDOWN")
    print("=" * 80)
    cur.execute("""
        SELECT 
            payroll_class,
            COUNT(*) as record_count,
            ROUND(SUM(COALESCE(cpp, 0))::numeric, 2) as total_cpp,
            ROUND(SUM(COALESCE(ei, 0))::numeric, 2) as total_ei,
            ROUND(SUM(COALESCE(tax, 0))::numeric, 2) as total_tax,
            ROUND(SUM(COALESCE(gross_pay, 0))::numeric, 2) as total_gross
        FROM driver_payroll
        WHERE year = 2013
        GROUP BY payroll_class
        ORDER BY payroll_class NULLS FIRST
    """)
    
    for row in cur.fetchall():
        print(f"\nPayroll Class: {row['payroll_class'] or 'NULL (wage records)'}")
        print(f"  Records: {row['record_count']}")
        print(f"  CPP: ${row['total_cpp']:,.2f}")
        print(f"  EI: ${row['total_ei']:,.2f}")
        print(f"  Tax: ${row['total_tax']:,.2f}")
        print(f"  Gross: ${row['total_gross']:,.2f}")
    
    # Get wage-only totals
    cur.execute("""
        SELECT 
            COUNT(*) as record_count,
            ROUND(SUM(COALESCE(cpp, 0))::numeric, 2) as total_cpp,
            ROUND(SUM(COALESCE(ei, 0))::numeric, 2) as total_ei,
            ROUND(SUM(COALESCE(tax, 0))::numeric, 2) as total_tax,
            ROUND(SUM(COALESCE(gross_pay, 0))::numeric, 2) as total_gross
        FROM driver_payroll
        WHERE year = 2013
        AND (payroll_class = 'WAGE' OR payroll_class IS NULL)
    """)
    wage_totals = cur.fetchone()
    
    print(f"\n{'='*80}")
    print("WAGE-ONLY TOTALS (excluding ADJUSTMENT):")
    print(f"  Records: {wage_totals['record_count']}")
    print(f"  CPP: ${wage_totals['total_cpp']:,.2f} (target: $14,387.58)")
    print(f"  EI: ${wage_totals['total_ei']:,.2f} (target: $7,137.61)")
    print(f"  Tax: ${wage_totals['total_tax']:,.2f}")
    print(f"  Gross: ${wage_totals['total_gross']:,.2f}")
    
    cpp_pct = (float(wage_totals['total_cpp']) / 14387.58) * 100
    ei_pct = (float(wage_totals['total_ei']) / 7137.61) * 100
    print(f"\nCoverage: CPP {cpp_pct:.1f}%, EI {ei_pct:.1f}%")
    
    # 2. Source system breakdown
    print(f"\n{'='*80}")
    print("2. SOURCE SYSTEM BREAKDOWN")
    print("=" * 80)
    cur.execute("""
        SELECT 
            source,
            COUNT(*) as record_count,
            ROUND(SUM(COALESCE(cpp, 0))::numeric, 2) as total_cpp,
            ROUND(SUM(COALESCE(ei, 0))::numeric, 2) as total_ei,
            ROUND(SUM(COALESCE(gross_pay, 0))::numeric, 2) as total_gross
        FROM driver_payroll
        WHERE year = 2013
        AND (payroll_class = 'WAGE' OR payroll_class IS NULL)
        GROUP BY source
        ORDER BY total_gross DESC NULLS LAST
    """)
    
    for row in cur.fetchall():
        print(f"\nSource: {row['source'] or 'NULL'}")
        print(f"  Records: {row['record_count']}")
        print(f"  CPP: ${row['total_cpp']:,.2f}")
        print(f"  EI: ${row['total_ei']:,.2f}")
        print(f"  Gross: ${row['total_gross']:,.2f}")
    
    # 3. Monthly coverage
    print(f"\n{'='*80}")
    print("3. MONTHLY COVERAGE")
    print("=" * 80)
    cur.execute("""
        SELECT 
            month,
            COUNT(*) as record_count,
            ROUND(SUM(COALESCE(cpp, 0))::numeric, 2) as total_cpp,
            ROUND(SUM(COALESCE(ei, 0))::numeric, 2) as total_ei,
            ROUND(SUM(COALESCE(gross_pay, 0))::numeric, 2) as total_gross
        FROM driver_payroll
        WHERE year = 2013
        AND (payroll_class = 'WAGE' OR payroll_class IS NULL)
        GROUP BY month
        ORDER BY month NULLS LAST
    """)
    
    months_data = cur.fetchall()
    if months_data:
        for row in months_data:
            print(f"\nMonth: {row['month'] or 'NULL'}")
            print(f"  Records: {row['record_count']}")
            print(f"  CPP: ${row['total_cpp']:,.2f}")
            print(f"  EI: ${row['total_ei']:,.2f}")
            print(f"  Gross: ${row['total_gross']:,.2f}")
    else:
        print("\n⚠️  NO MONTH FIELD DATA - All records have NULL month")
    
    # 4. Employee count
    print(f"\n{'='*80}")
    print("4. EMPLOYEE COVERAGE")
    print("=" * 80)
    cur.execute("""
        SELECT 
            COUNT(DISTINCT employee_id) as unique_employees,
            COUNT(DISTINCT driver_id) as unique_driver_ids,
            COUNT(CASE WHEN employee_id IS NULL THEN 1 END) as null_employee_id,
            COUNT(CASE WHEN driver_id IS NULL THEN 1 END) as null_driver_id
        FROM driver_payroll
        WHERE year = 2013
        AND (payroll_class = 'WAGE' OR payroll_class IS NULL)
    """)
    
    emp_stats = cur.fetchone()
    print(f"  Unique employee_id values: {emp_stats['unique_employees']}")
    print(f"  Unique driver_id values: {emp_stats['unique_driver_ids']}")
    print(f"  Records with NULL employee_id: {emp_stats['null_employee_id']}")
    print(f"  Records with NULL driver_id: {emp_stats['null_driver_id']}")
    
    # Sample employees
    cur.execute("""
        SELECT 
            COALESCE(employee_id::text, driver_id, 'UNKNOWN') as identifier,
            COUNT(*) as pay_count,
            ROUND(SUM(COALESCE(cpp, 0))::numeric, 2) as total_cpp,
            ROUND(SUM(COALESCE(ei, 0))::numeric, 2) as total_ei,
            ROUND(SUM(COALESCE(gross_pay, 0))::numeric, 2) as total_gross
        FROM driver_payroll
        WHERE year = 2013
        AND (payroll_class = 'WAGE' OR payroll_class IS NULL)
        GROUP BY employee_id, driver_id
        ORDER BY total_gross DESC
        LIMIT 10
    """)
    
    print(f"\nTop 10 Employees by Gross Pay:")
    for row in cur.fetchall():
        print(f"  {row['identifier']}: {row['pay_count']} pays, CPP ${row['total_cpp']:,.2f}, EI ${row['total_ei']:,.2f}, Gross ${row['total_gross']:,.2f}")
    
    # 5. Year boundary check
    print(f"\n{'='*80}")
    print("5. YEAR BOUNDARY CHECK")
    print("=" * 80)
    
    # Check for 2012 records that might be 2013
    cur.execute("""
        SELECT 
            COUNT(*) as record_count,
            ROUND(SUM(COALESCE(cpp, 0))::numeric, 2) as total_cpp,
            ROUND(SUM(COALESCE(ei, 0))::numeric, 2) as total_ei,
            ROUND(SUM(COALESCE(gross_pay, 0))::numeric, 2) as total_gross
        FROM driver_payroll
        WHERE year = 2012
        AND month = 12
        AND (payroll_class = 'WAGE' OR payroll_class IS NULL)
    """)
    
    dec_2012 = cur.fetchone()
    print(f"\n2012 December Records (might be late 2013 payments):")
    print(f"  Records: {dec_2012['record_count']}")
    print(f"  CPP: ${dec_2012['total_cpp']:,.2f}")
    print(f"  EI: ${dec_2012['total_ei']:,.2f}")
    print(f"  Gross: ${dec_2012['total_gross']:,.2f}")
    
    # Check for 2014 records that might be early 2013
    cur.execute("""
        SELECT 
            COUNT(*) as record_count,
            ROUND(SUM(COALESCE(cpp, 0))::numeric, 2) as total_cpp,
            ROUND(SUM(COALESCE(ei, 0))::numeric, 2) as total_ei,
            ROUND(SUM(COALESCE(gross_pay, 0))::numeric, 2) as total_gross
        FROM driver_payroll
        WHERE year = 2014
        AND month = 1
        AND (payroll_class = 'WAGE' OR payroll_class IS NULL)
    """)
    
    jan_2014 = cur.fetchone()
    print(f"\n2014 January Records (might be early 2013 payments):")
    print(f"  Records: {jan_2014['record_count']}")
    print(f"  CPP: ${jan_2014['total_cpp']:,.2f}")
    print(f"  EI: ${jan_2014['total_ei']:,.2f}")
    print(f"  Gross: ${jan_2014['total_gross']:,.2f}")
    
    # 6. Check pay_date field
    print(f"\n{'='*80}")
    print("6. PAY_DATE FIELD CHECK")
    print("=" * 80)
    cur.execute("""
        SELECT 
            COUNT(*) as with_pay_date,
            COUNT(CASE WHEN pay_date IS NULL THEN 1 END) as null_pay_date,
            MIN(pay_date) as earliest_pay_date,
            MAX(pay_date) as latest_pay_date
        FROM driver_payroll
        WHERE year = 2013
        AND (payroll_class = 'WAGE' OR payroll_class IS NULL)
    """)
    
    pay_date_stats = cur.fetchone()
    print(f"  Records with pay_date: {pay_date_stats['with_pay_date']}")
    print(f"  Records with NULL pay_date: {pay_date_stats['null_pay_date']}")
    if pay_date_stats['earliest_pay_date']:
        print(f"  Date range: {pay_date_stats['earliest_pay_date']} to {pay_date_stats['latest_pay_date']}")
    
    # Check if pay_date reveals year mismatch
    if pay_date_stats['earliest_pay_date']:
        cur.execute("""
            SELECT 
                EXTRACT(YEAR FROM pay_date)::int as pay_year,
                COUNT(*) as record_count,
                ROUND(SUM(COALESCE(cpp, 0))::numeric, 2) as total_cpp,
                ROUND(SUM(COALESCE(ei, 0))::numeric, 2) as total_ei
            FROM driver_payroll
            WHERE year = 2013
            AND pay_date IS NOT NULL
            AND (payroll_class = 'WAGE' OR payroll_class IS NULL)
            GROUP BY pay_year
            ORDER BY pay_year
        """)
        
        print(f"\n  Breakdown by actual pay_date year:")
        for row in cur.fetchall():
            print(f"    {row['pay_year']}: {row['record_count']} records, CPP ${row['total_cpp']:,.2f}, EI ${row['total_ei']:,.2f}")
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print("=" * 80)
    print(f"\nDatabase 2013 wage records: CPP ${wage_totals['total_cpp']:,.2f}, EI ${wage_totals['total_ei']:,.2f}")
    print(f"T4 Summary 2013: CPP $14,387.58, EI $7,137.61")
    print(f"\nMissing: CPP ${14387.58 - float(wage_totals['total_cpp']):,.2f}, EI ${7137.61 - float(wage_totals['total_ei']):,.2f}")
    print(f"Coverage: CPP {cpp_pct:.1f}%, EI {ei_pct:.1f}%")
    
    print("\n⚠️  LIKELY CAUSES:")
    print("  1. Incomplete payroll data import from 2013 source files")
    print("  2. Missing months of payroll data in database")
    print("  3. Source system may not have all payroll periods")
    print("  4. Year boundary mislabeling (2013 pay labeled as 2012 or 2014)")
    
    print("\n✅ RECOMMENDATION:")
    print("  Import T4 Summary as separate record with source='T4_SUMMARY_2013_PDF'")
    print("  This preserves authoritative CRA totals alongside existing detail records")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    investigate_discrepancy()
