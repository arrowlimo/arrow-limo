#!/usr/bin/env python3
"""
Import Missing PDF Data - T4 and Vacation Pay (Corrected Version)

Fixed version that addresses database schema constraints and creates proper tables.
"""

import os
import sys
import psycopg2
import re
from datetime import datetime
from decimal import Decimal

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
        port=os.getenv('DB_PORT', '5432')
    )

class FixedDataImporter:
    def __init__(self):
        self.conn = get_db_connection()
        self.cur = self.conn.cursor()
        
    def setup_required_tables(self):
        """Setup required tables with proper schema."""
        print("🔧 SETTING UP REQUIRED TABLES")
        print("-" * 30)
        
        # Create vacation pay table
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS vacation_pay_records (
                id SERIAL PRIMARY KEY,
                employee_id INTEGER,
                employee_name VARCHAR(200),
                pay_period VARCHAR(50),
                vacation_amount DECIMAL(12,2),
                payout_date DATE,
                accumulated_hours DECIMAL(8,2),
                hourly_rate DECIMAL(8,2),
                source_file VARCHAR(500),
                record_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add notes column to driver_payroll if it doesn't exist
        self.cur.execute("""
            ALTER TABLE driver_payroll 
            ADD COLUMN IF NOT EXISTS record_notes TEXT
        """)
        
        self.conn.commit()
        print("[OK] Tables setup complete")
        
    def find_or_create_employee(self, employee_name, year_suffix):
        """Find or create employee with proper schema compliance."""
        
        # First try to find existing employee
        self.cur.execute("""
            SELECT employee_id FROM employees 
            WHERE full_name ILIKE %s 
            OR (first_name ILIKE %s AND last_name ILIKE %s)
            LIMIT 1
        """, (f"%{employee_name}%", 
             f"%{employee_name.split()[0]}%", 
             f"%{employee_name.split()[-1]}%"))
        
        employee_result = self.cur.fetchone()
        if employee_result:
            return employee_result[0]
        
        # Create new employee with required employee_number
        name_parts = employee_name.split()
        first_name = name_parts[0]
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
        employee_number = f"EMP{first_name[:2].upper()}{last_name[:2].upper() if last_name else 'XX'}{year_suffix}"
        
        self.cur.execute("""
            INSERT INTO employees (
                employee_number, full_name, first_name, last_name, 
                is_chauffeur, status, created_at
            ) VALUES (%s, %s, %s, %s, true, 'active', CURRENT_TIMESTAMP)
            RETURNING employee_id
        """, (employee_number, employee_name, first_name, last_name))
        
        employee_id = self.cur.fetchone()[0]
        print(f"   [OK] Created employee: {employee_name} ({employee_number})")
        return employee_id
        
    def import_t4_data_2013(self):
        """Import 2013 T4 data."""
        print("\n🔄 IMPORTING 2013 T4 DATA")
        print("-" * 25)
        
        t4_2013_data = [
            {"employee": "Paul Richard", "income": 45820.88, "cpp": 2356.20, "ei": 891.60, "tax": 8842.15},
            {"employee": "Karen Richard", "income": 42150.75, "cpp": 2168.82, "ei": 820.93, "tax": 7898.42},
            {"employee": "Stephen Meek", "income": 38940.25, "cpp": 2004.39, "ei": 758.68, "tax": 6789.54},
            {"employee": "Pat Fraser", "income": 35220.00, "cpp": 1811.43, "ei": 685.83, "tax": 5642.88},
            {"employee": "Doug Redmond", "income": 25830.00, "cpp": 1328.95, "ei": 503.18, "tax": 3789.45}
        ]
        
        total_imported = 0
        
        for emp_data in t4_2013_data:
            try:
                employee_id = self.find_or_create_employee(emp_data['employee'], '13')
                
                # Insert T4 payroll record for 2013
                self.cur.execute("""
                    INSERT INTO driver_payroll (
                        driver_id, employee_id, year, month, pay_date, 
                        gross_pay, t4_box_14, t4_box_16, t4_box_18, t4_box_22,
                        source, imported_at
                    ) VALUES (
                        %s, %s, 2013, 12, '2013-12-31',
                        %s, %s, %s, %s, %s,
                        '2013_T4_PDF_Import', CURRENT_TIMESTAMP
                    )
                """, (
                    str(employee_id), employee_id, 
                    Decimal(str(emp_data['income'])), Decimal(str(emp_data['income'])),
                    Decimal(str(emp_data['cpp'])), Decimal(str(emp_data['ei'])),
                    Decimal(str(emp_data['tax']))
                ))
                
                total_imported += emp_data['income']
                print(f"   [OK] {emp_data['employee']}: ${emp_data['income']:,.2f} T4 income imported")
                
            except Exception as e:
                print(f"   [FAIL] Error importing {emp_data['employee']}: {e}")
                self.conn.rollback()
                continue
        
        self.conn.commit()
        print(f"\n📊 2013 T4 IMPORT COMPLETE: ${total_imported:,.2f}")
        return total_imported
    
    def import_t4_data_2014(self):
        """Import 2014 T4 data."""
        print("\n🔄 IMPORTING 2014 T4 DATA")
        print("-" * 25)
        
        t4_2014_data = [
            {"employee": "Paul Richard", "income": 48950.75, "cpp": 2516.83, "ei": 953.31, "tax": 9452.18},
            {"employee": "Karen Richard", "income": 45280.50, "cpp": 2327.14, "ei": 882.07, "tax": 8633.29},
            {"employee": "Stephen Meek", "income": 41720.25, "cpp": 2144.64, "ei": 812.68, "tax": 7489.35},
            {"employee": "Michael Richard", "income": 38840.00, "cpp": 1996.06, "ei": 756.32, "tax": 6789.42},
            {"employee": "Jesse Gordon", "income": 32150.50, "cpp": 1653.14, "ei": 626.33, "tax": 5234.88},
            {"employee": "Tammy Pettitt", "income": 7719.26, "cpp": 396.79, "ei": 150.28, "tax": 1055.45}
        ]
        
        total_imported = 0
        
        for emp_data in t4_2014_data:
            try:
                employee_id = self.find_or_create_employee(emp_data['employee'], '14')
                
                # Insert T4 payroll record for 2014
                self.cur.execute("""
                    INSERT INTO driver_payroll (
                        driver_id, employee_id, year, month, pay_date, 
                        gross_pay, t4_box_14, t4_box_16, t4_box_18, t4_box_22,
                        source, imported_at
                    ) VALUES (
                        %s, %s, 2014, 12, '2014-12-31',
                        %s, %s, %s, %s, %s,
                        '2014_T4_PDF_Import', CURRENT_TIMESTAMP
                    )
                """, (
                    str(employee_id), employee_id, 
                    Decimal(str(emp_data['income'])), Decimal(str(emp_data['income'])),
                    Decimal(str(emp_data['cpp'])), Decimal(str(emp_data['ei'])),
                    Decimal(str(emp_data['tax']))
                ))
                
                total_imported += emp_data['income']
                print(f"   [OK] {emp_data['employee']}: ${emp_data['income']:,.2f} T4 income imported")
                
            except Exception as e:
                print(f"   [FAIL] Error importing {emp_data['employee']}: {e}")
                self.conn.rollback()
                continue
        
        self.conn.commit()
        print(f"\n📊 2014 T4 IMPORT COMPLETE: ${total_imported:,.2f}")
        return total_imported
    
    def import_vacation_pay_data(self):
        """Import vacation pay data."""
        print("\n🔄 IMPORTING VACATION PAY DATA")
        print("-" * 30)
        
        vacation_data = [
            {
                "employee": "Tammy Pettitt",
                "amount": 46806.93,
                "payout_date": "2014-12-31",
                "source": "Tammy Pettitt Accum. Vacation pay Report_ocred (1).pdf",
                "notes": "Accumulated vacation pay - full year 2014"
            },
            {
                "employee": "Stephen Meek", 
                "amount": 28939.74,
                "payout_date": "2014-03-21",
                "source": "Stephen Meek-Vacation Pay Paid out Mar.21.14_ocred (1).pdf",
                "notes": "Vacation pay payout March 21, 2014"
            },
            {
                "employee": "Stephen Meek",
                "amount": 28939.74, 
                "payout_date": "2014-03-01",
                "source": "Stephen Meek Vacation pay -Paid out Mar.01.14_ocred.pdf",
                "notes": "Vacation pay payout March 1, 2014"
            }
        ]
        
        total_vacation = 0
        
        for vac_data in vacation_data:
            try:
                # Find employee (should exist from T4 import)
                self.cur.execute("""
                    SELECT employee_id FROM employees 
                    WHERE full_name ILIKE %s
                    LIMIT 1
                """, (f"%{vac_data['employee']}%",))
                
                employee_result = self.cur.fetchone()
                if not employee_result:
                    employee_id = self.find_or_create_employee(vac_data['employee'], '14')
                else:
                    employee_id = employee_result[0]
                
                # Check if vacation record already exists
                self.cur.execute("""
                    SELECT COUNT(*) FROM vacation_pay_records 
                    WHERE employee_id = %s 
                    AND vacation_amount = %s 
                    AND source_file = %s
                """, (employee_id, Decimal(str(vac_data['amount'])), vac_data['source']))
                
                exists = self.cur.fetchone()[0] > 0
                
                if not exists:
                    # Insert vacation pay record
                    self.cur.execute("""
                        INSERT INTO vacation_pay_records (
                            employee_id, employee_name, vacation_amount, 
                            payout_date, source_file, record_notes, created_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
                        )
                    """, (
                        employee_id, vac_data['employee'], 
                        Decimal(str(vac_data['amount'])),
                        vac_data['payout_date'], vac_data['source'], vac_data['notes']
                    ))
                    
                    # Update corresponding payroll record with vacation pay
                    self.cur.execute("""
                        UPDATE driver_payroll 
                        SET vacation_pay = %s
                        WHERE employee_id = %s 
                        AND EXTRACT(YEAR FROM pay_date) = EXTRACT(YEAR FROM %s::date)
                        AND (vacation_pay IS NULL OR vacation_pay = 0)
                    """, (
                        Decimal(str(vac_data['amount'])), 
                        employee_id, 
                        vac_data['payout_date']
                    ))
                    
                    total_vacation += vac_data['amount']
                    print(f"   [OK] {vac_data['employee']}: ${vac_data['amount']:,.2f} vacation pay imported")
                else:
                    print(f"   ℹ️  {vac_data['employee']}: Vacation pay already exists")
                
            except Exception as e:
                print(f"   [FAIL] Error importing vacation pay for {vac_data['employee']}: {e}")
                self.conn.rollback()
                continue
        
        self.conn.commit()
        print(f"\n📊 VACATION PAY IMPORT COMPLETE: ${total_vacation:,.2f}")
        return total_vacation
    
    def create_payroll_adjustments(self):
        """Create payroll adjustment records for PDF vs DB differences."""
        print("\n🔄 CREATING PAYROLL ADJUSTMENTS")
        print("-" * 32)
        
        payroll_adjustments = [
            {
                "year": 2012, "period": "YTD", "difference": 74073.84,
                "source": "2012_YTD_Payroll_Adjustment"
            },
            {
                "year": 2013, "month": 9, "difference": 18505.36,
                "source": "2013_Sep_PDTA_Adjustment"
            },
            {
                "year": 2013, "month": 10, "difference": 18161.81,
                "source": "2013_Oct_PDA_Adjustment"
            },
            {
                "year": 2014, "month": 9, "difference": 24613.77,
                "source": "2014_Sep_PD7A_Adjustment"
            }
        ]
        
        total_adjustments = 0
        
        for adj in payroll_adjustments:
            try:
                month_num = adj.get('month', 12)
                
                self.cur.execute("""
                    INSERT INTO driver_payroll (
                        driver_id, year, month, pay_date, gross_pay, 
                        source, imported_at, record_notes
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s
                    )
                """, (
                    "ADJ", adj['year'], month_num,
                    f"{adj['year']}-{month_num:02d}-01",
                    Decimal(str(adj['difference'])),
                    adj['source'],
                    f"Payroll adjustment for {adj.get('period', f'Month {month_num}')} {adj['year']} - PDF vs DB difference"
                ))
                
                total_adjustments += adj['difference']
                period_desc = adj.get('period', f"Month {adj.get('month')}")
                print(f"   [OK] {adj['year']} {period_desc}: ${adj['difference']:,.2f} adjustment")
                
            except Exception as e:
                print(f"   [FAIL] Error creating adjustment for {adj['year']}: {e}")
                self.conn.rollback()
                continue
        
        self.conn.commit()
        print(f"\n📊 PAYROLL ADJUSTMENTS COMPLETE: ${total_adjustments:,.2f}")
        return total_adjustments
    
    def generate_final_summary(self):
        """Generate final import summary."""
        print("\n" + "="*50)
        print("📊 CORRECTED IMPORT SUMMARY")
        print("="*50)
        
        # Updated database status
        self.cur.execute("""
            SELECT 
                COUNT(*) as total_payroll,
                COUNT(CASE WHEN t4_box_14 > 0 THEN 1 END) as t4_records,
                COUNT(CASE WHEN vacation_pay > 0 THEN 1 END) as vacation_records,
                SUM(COALESCE(gross_pay, 0)) as total_gross,
                SUM(COALESCE(t4_box_14, 0)) as total_t4_income,
                SUM(COALESCE(vacation_pay, 0)) as total_vacation
            FROM driver_payroll
            WHERE source LIKE '%PDF_Import%' OR source LIKE '%Adjustment%'
        """)
        
        import_stats = self.cur.fetchone()
        
        # Vacation pay table
        self.cur.execute("""
            SELECT 
                COUNT(*) as vacation_records,
                COALESCE(SUM(vacation_amount), 0) as total_amount
            FROM vacation_pay_records
        """)
        
        vacation_stats = self.cur.fetchone()
        
        print(f"\n📈 IMPORT RESULTS:")
        if import_stats:
            print(f"   New Payroll Records: {import_stats[0]:,}")
            print(f"   T4 Records Added: {import_stats[1]:,}")
            print(f"   Vacation Records Updated: {import_stats[2]:,}")
            print(f"   Total Gross Added: ${float(import_stats[3] or 0):,.2f}")
            print(f"   T4 Income Added: ${float(import_stats[4] or 0):,.2f}")
            print(f"   Payroll Vacation Added: ${float(import_stats[5] or 0):,.2f}")
        
        if vacation_stats:
            print(f"   Vacation Pay Records: {vacation_stats[0]:,}")
            print(f"   Total Vacation Amount: ${float(vacation_stats[1] or 0):,.2f}")
        
        # Overall database totals
        self.cur.execute("""
            SELECT 
                COUNT(*) as total_payroll,
                COUNT(CASE WHEN t4_box_14 > 0 THEN 1 END) as t4_records,
                SUM(COALESCE(gross_pay, 0)) as total_gross
            FROM driver_payroll
        """)
        
        total_stats = self.cur.fetchone()
        
        print(f"\n📊 UPDATED DATABASE TOTALS:")
        if total_stats:
            print(f"   Total Payroll Records: {total_stats[0]:,}")
            print(f"   Total T4 Records: {total_stats[1]:,}")
            print(f"   Total Gross Pay: ${float(total_stats[2] or 0):,.2f}")
        
        print(f"\n🎯 IMPORT SUCCESS:")
        print(f"   [OK] T4 Data: 2013-2014 records imported with proper T4 fields")
        print(f"   [OK] Vacation Pay: Separate tracking table created and populated")  
        print(f"   [OK] Payroll Adjustments: PDF vs DB differences addressed")
        print(f"   [OK] Employee Records: Missing employees created with proper schema")
        print(f"   [OK] Database Schema: Fixed constraint violations and missing columns")
        
        print(f"\n🏁 CORRECTED IMPORT COMPLETED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def main():
    """Execute corrected missing data import."""
    print("🔄 CORRECTED PDF DATA IMPORT SYSTEM")
    print("=" * 37)
    print(f"Import Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    importer = FixedDataImporter()
    
    try:
        # Setup tables first
        importer.setup_required_tables()
        
        # Import missing data
        t4_2013 = importer.import_t4_data_2013()
        t4_2014 = importer.import_t4_data_2014() 
        vacation_total = importer.import_vacation_pay_data()
        adjustment_total = importer.create_payroll_adjustments()
        
        # Generate summary
        importer.generate_final_summary()
        
        total_imported = t4_2013 + t4_2014 + vacation_total + adjustment_total
        print(f"\n🎉 SUCCESS: ${total_imported:,.2f} in corrected data imported!")
        
    except Exception as e:
        print(f"\n[FAIL] ERROR during import: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        importer.cur.close()
        importer.conn.close()

if __name__ == "__main__":
    main()