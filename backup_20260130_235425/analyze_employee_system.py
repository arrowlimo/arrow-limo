#!/usr/bin/env python3
"""
Employee System Analysis - Complete Table Structure and Relationships
Analyze all employee-related tables and their relationships
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json

def get_db_connection():
    """Get PostgreSQL connection"""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
        cursor_factory=RealDictCursor
    )

def main():
    print("🧑‍💼 EMPLOYEE SYSTEM COMPREHENSIVE ANALYSIS")
    print("=" * 60)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 1. Find all employee-related tables
        print("📊 EMPLOYEE-RELATED TABLES:")
        
        cur.execute("""
            SELECT table_name, 
                   (SELECT count(*) FROM information_schema.columns 
                    WHERE table_name = t.table_name AND table_schema = 'public') as column_count
            FROM information_schema.tables t
            WHERE table_schema = 'public' 
            AND (table_name LIKE '%employee%' 
                 OR table_name LIKE '%driver%' 
                 OR table_name LIKE '%payroll%'
                 OR table_name LIKE '%staff%'
                 OR table_name LIKE '%chauffeur%')
            ORDER BY table_name
        """)
        
        employee_tables = cur.fetchall()
        
        for table in employee_tables:
            cur.execute(f"SELECT COUNT(*) as record_count FROM {table['table_name']}")
            record_count = cur.fetchone()['record_count']
            print(f"   {table['table_name']}: {table['column_count']} columns, {record_count:,} records")
        
        # 2. Main employees table analysis
        print(f"\n📋 MAIN EMPLOYEES TABLE ANALYSIS:")
        
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'employees' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        
        employee_columns = cur.fetchall()
        
        if employee_columns:
            print(f"   employees table has {len(employee_columns)} columns:")
            for col in employee_columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
                print(f"      {col['column_name']}: {col['data_type']} {nullable}{default}")
        
        # 3. Employee record analysis
        print(f"\n👥 EMPLOYEE RECORDS ANALYSIS:")
        
        cur.execute("""
            SELECT 
                COUNT(*) as total_employees,
                COUNT(*) FILTER (WHERE status = 'active') as active_employees,
                COUNT(*) FILTER (WHERE status = 'inactive') as inactive_employees,
                COUNT(*) FILTER (WHERE is_chauffeur = true) as chauffeur_count,
                COUNT(*) FILTER (WHERE position IS NOT NULL) as with_position,
                COUNT(*) FILTER (WHERE hourly_rate IS NOT NULL) as with_hourly_rate,
                COUNT(*) FILTER (WHERE salary IS NOT NULL) as with_salary,
                MIN(hire_date) as earliest_hire,
                MAX(hire_date) as latest_hire
            FROM employees
        """)
        
        emp_stats = cur.fetchone()
        
        for key, value in emp_stats.items():
            print(f"   {key.replace('_', ' ').title()}: {value}")
        
        # 4. Payroll-related tables analysis
        print(f"\n💰 PAYROLL SYSTEM ANALYSIS:")
        
        payroll_tables = [table['table_name'] for table in employee_tables if 'payroll' in table['table_name']]
        
        for table_name in payroll_tables:
            # Get column info first
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s AND table_schema = 'public'
                AND column_name IN ('pay_period_start', 'payroll_date', 'date_created', 'created_at', 'pay_date', 'period_start')
            """, (table_name,))
            
            date_columns = [row['column_name'] for row in cur.fetchall()]
            
            cur.execute(f"SELECT COUNT(*) as record_count FROM {table_name}")
            stats = cur.fetchone()
            print(f"   {table_name}: {stats['record_count']:,} records")
            
            if date_columns:
                date_col = date_columns[0]  # Use first available date column
                cur.execute(f"SELECT MIN({date_col})::date as min_date, MAX({date_col})::date as max_date FROM {table_name}")
                date_stats = cur.fetchone()
                if date_stats['min_date'] and date_stats['max_date']:
                    print(f"      Date range: {date_stats['min_date']} to {date_stats['max_date']}")
            else:
                print(f"      No date columns found")
        
        # 5. Driver-specific analysis
        print(f"\n🚗 DRIVER-SPECIFIC ANALYSIS:")
        
        # Check for driver-related fields in employees
        cur.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE is_chauffeur = true) as total_drivers,
                COUNT(*) FILTER (WHERE driver_license_number IS NOT NULL) as with_license,
                COUNT(*) FILTER (WHERE driver_license_expiry IS NOT NULL) as with_expiry,
                COUNT(*) FILTER (WHERE medical_cert_expiry IS NOT NULL) as with_medical,
                AVG(hourly_rate) FILTER (WHERE is_chauffeur = true AND hourly_rate IS NOT NULL) as avg_driver_rate
            FROM employees
        """)
        
        driver_stats = cur.fetchone()
        
        for key, value in driver_stats.items():
            if 'avg' in key and value:
                print(f"   {key.replace('_', ' ').title()}: ${value:.2f}")
            else:
                print(f"   {key.replace('_', ' ').title()}: {value}")
        
        # 6. Charter-employee relationships
        print(f"\n🔗 CHARTER-EMPLOYEE RELATIONSHIPS:")
        
        cur.execute("""
            SELECT 
                COUNT(DISTINCT driver) as drivers_with_charters,
                COUNT(DISTINCT assigned_driver_id) as assigned_driver_ids,
                COUNT(*) FILTER (WHERE driver IS NOT NULL) as charters_with_driver,
                COUNT(*) FILTER (WHERE assigned_driver_id IS NOT NULL) as charters_with_assigned_id
            FROM charters
        """)
        
        charter_stats = cur.fetchone()
        
        for key, value in charter_stats.items():
            print(f"   {key.replace('_', ' ').title()}: {value:,}")
        
        # 7. Employee positions analysis
        print(f"\n📍 EMPLOYEE POSITIONS ANALYSIS:")
        
        cur.execute("""
            SELECT 
                position,
                COUNT(*) as employee_count,
                COUNT(*) FILTER (WHERE status = 'active') as active_count,
                AVG(hourly_rate) FILTER (WHERE hourly_rate IS NOT NULL) as avg_hourly_rate,
                AVG(salary) FILTER (WHERE salary IS NOT NULL) as avg_salary
            FROM employees
            WHERE position IS NOT NULL
            GROUP BY position
            ORDER BY employee_count DESC
        """)
        
        positions = cur.fetchall()
        
        for pos in positions:
            print(f"   {pos['position']}: {pos['employee_count']} total ({pos['active_count']} active)")
            if pos['avg_hourly_rate']:
                print(f"      Avg hourly rate: ${pos['avg_hourly_rate']:.2f}")
            if pos['avg_salary']:
                print(f"      Avg salary: ${pos['avg_salary']:,.2f}")
        
        # 8. Sample employee records
        print(f"\n📝 SAMPLE EMPLOYEE RECORDS:")
        
        cur.execute("""
            SELECT 
                employee_id, employee_number, full_name, position, 
                status, is_chauffeur, hourly_rate, hire_date
            FROM employees
            WHERE status = 'active'
            ORDER BY hire_date DESC
            LIMIT 10
        """)
        
        sample_employees = cur.fetchall()
        
        for emp in sample_employees:
            chauffeur = "Driver" if emp['is_chauffeur'] else "Staff"
            rate = f"${emp['hourly_rate']:.2f}/hr" if emp['hourly_rate'] else "No rate"
            print(f"   {emp['employee_id']}: {emp['full_name']} ({chauffeur}, {emp['position']}) - {rate}")
        
        # 9. Related table relationships
        print(f"\n🔗 EMPLOYEE RELATIONSHIP ANALYSIS:")
        
        # Check foreign key relationships
        cur.execute("""
            SELECT 
                tc.table_name, 
                kcu.column_name, 
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name 
            FROM information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' 
            AND tc.table_schema = 'public'
            AND (ccu.table_name = 'employees' 
                 OR tc.table_name = 'employees'
                 OR tc.table_name LIKE '%employee%'
                 OR tc.table_name LIKE '%payroll%'
                 OR tc.table_name LIKE '%driver%')
            ORDER BY tc.table_name, kcu.column_name
        """)
        
        relationships = cur.fetchall()
        
        if relationships:
            print("   Foreign Key Relationships:")
            for rel in relationships:
                print(f"      {rel['table_name']}.{rel['column_name']} → {rel['foreign_table_name']}.{rel['foreign_column_name']}")
        else:
            print("   No foreign key relationships found")
        
        # 10. Summary
        print(f"\n🎯 EMPLOYEE SYSTEM SUMMARY:")
        print(f"   Employee Tables: {len(employee_tables)}")
        print(f"   Total Employees: {emp_stats['total_employees']:,}")
        print(f"   Active Employees: {emp_stats['active_employees']:,}")
        print(f"   Drivers/Chauffeurs: {driver_stats['total_drivers']:,}")
        print(f"   Payroll Tables: {len(payroll_tables)}")
        print(f"   Employee-Charter Links: {charter_stats['charters_with_driver']:,} charters")
        
    except Exception as e:
        print(f"[FAIL] Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()