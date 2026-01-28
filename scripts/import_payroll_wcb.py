#!/usr/bin/env python3
"""
Import Payroll and WCB Data

This script parses the payroll report with WCB data and imports
driver payroll records with detailed deductions and WCB calculations.
"""

import sys
import re
import psycopg2
from datetime import datetime
from decimal import Decimal, InvalidOperation

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres'
}

def connect_to_database():
    """Connect to PostgreSQL database."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def parse_payroll_report(file_path):
    """Parse the payroll report with WCB data."""
    payroll_records = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return []
    
    # Split by driver sections
    driver_sections = re.split(r'Driver:\s+(\w+)\s+Year:\s+(\d{4})\s+Month:\s+(\d+)', content)
    
    print(f"Found {len(driver_sections)//4} driver payroll sections to process")
    
    # Process sections in groups of 4 (split_result, driver_id, year, month, content)
    for i in range(1, len(driver_sections), 4):
        if i + 3 >= len(driver_sections):
            break
            
        try:
            driver_id = driver_sections[i].strip()
            year = int(driver_sections[i + 1])
            month = int(driver_sections[i + 2])
            section_content = driver_sections[i + 3] if i + 3 < len(driver_sections) else ""
            
            # Parse WCB payment info
            wcb_match = re.search(r'WCB Payment:\s*\$?([\d,.]+)\s*\(Rate:\s*([\d.]+)/\$100\)', section_content)
            wcb_payment = None
            wcb_rate = None
            
            if wcb_match:
                try:
                    wcb_payment = Decimal(wcb_match.group(1).replace(',', ''))
                    wcb_rate = Decimal(wcb_match.group(2))
                except InvalidOperation:
                    pass
            
            # Parse individual payroll entries
            payroll_entries = re.findall(
                r'(\d+)\s+(\d+)\s+(\d{4}-\d{2}-\d{2})\s+\$\s*([\d,.]+)\s+\$\s*([\d,.]+)\s+\$\s*([\d,.]+)\s+\$\s*([\d,.]+)\s+\$\s*([\d,.]+)\s+\$\s*([\d,.]+)\s+\$\s*([\d,.]+)',
                section_content
            )
            
            for entry in payroll_entries:
                try:
                    charter_id = entry[0]
                    reserve_number = entry[1]
                    pay_date = entry[2]
                    gross_pay = Decimal(entry[3].replace(',', ''))
                    cpp = Decimal(entry[4].replace(',', ''))
                    ei = Decimal(entry[5].replace(',', ''))
                    tax = Decimal(entry[6].replace(',', ''))
                    total_deductions = Decimal(entry[7].replace(',', ''))
                    net_pay = Decimal(entry[8].replace(',', ''))
                    expenses = Decimal(entry[9].replace(',', ''))
                    
                    payroll_record = {
                        'driver_id': driver_id,
                        'year': year,
                        'month': month,
                        'charter_id': charter_id,
                        'reserve_number': reserve_number,
                        'pay_date': pay_date,
                        'gross_pay': gross_pay,
                        'cpp': cpp,
                        'ei': ei,
                        'tax': tax,
                        'total_deductions': total_deductions,
                        'net_pay': net_pay,
                        'expenses': expenses,
                        'wcb_payment': wcb_payment,
                        'wcb_rate': wcb_rate,
                        'source': 'payroll_wcb_report'
                    }
                    
                    payroll_records.append(payroll_record)
                    
                except (InvalidOperation, ValueError, IndexError) as e:
                    print(f"Error parsing payroll entry: {e}")
                    continue
            
            # Parse TOTALS line for verification
            totals_match = re.search(r'TOTALS:\s+Gross=\$([\d,.]+)\s+Deductions=\$([\d,.]+)\s+Net=\$([\d,.]+)', section_content)
            if totals_match and payroll_entries:
                # Could add totals verification here if needed
                pass
                
        except (ValueError, IndexError) as e:
            print(f"Error parsing driver section {i//4}: {e}")
            continue
    
    print(f"Successfully parsed {len(payroll_records)} payroll records")
    return payroll_records

def create_payroll_tables(conn):
    """Create tables for payroll and WCB data."""
    try:
        cursor = conn.cursor()
        
        # Create payroll records table
        create_payroll_sql = """
        CREATE TABLE IF NOT EXISTS driver_payroll (
            id SERIAL PRIMARY KEY,
            driver_id VARCHAR(20),
            year INTEGER,
            month INTEGER,
            charter_id VARCHAR(20),
            reserve_number VARCHAR(20),
            pay_date DATE,
            gross_pay DECIMAL(10,2),
            cpp DECIMAL(10,2),
            ei DECIMAL(10,2),
            tax DECIMAL(10,2),
            total_deductions DECIMAL(10,2),
            net_pay DECIMAL(10,2),
            expenses DECIMAL(10,2),
            wcb_payment DECIMAL(10,2),
            wcb_rate DECIMAL(10,4),
            source VARCHAR(100),
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(driver_id, year, month, charter_id, reserve_number, pay_date)
        );
        """
        
        cursor.execute(create_payroll_sql)
        
        # Create WCB summary table
        create_wcb_sql = """
        CREATE TABLE IF NOT EXISTS wcb_summary (
            id SERIAL PRIMARY KEY,
            driver_id VARCHAR(20),
            year INTEGER,
            month INTEGER,
            wcb_payment DECIMAL(10,2),
            wcb_rate DECIMAL(10,4),
            total_gross_pay DECIMAL(10,2),
            source VARCHAR(100),
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(driver_id, year, month)
        );
        """
        
        cursor.execute(create_wcb_sql)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_driver_payroll_driver ON driver_payroll(driver_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_driver_payroll_date ON driver_payroll(pay_date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_driver_payroll_charter ON driver_payroll(charter_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wcb_summary_driver ON wcb_summary(driver_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wcb_summary_year_month ON wcb_summary(year, month);")
        
        conn.commit()
        print("Payroll and WCB tables created successfully")
        
    except Exception as e:
        print(f"Error creating payroll tables: {e}")
        conn.rollback()

def import_payroll_data(conn, payroll_records):
    """Import payroll data into database."""
    if not payroll_records:
        print("No payroll records to import")
        return 0
        
    cursor = conn.cursor()
    payroll_inserted = 0
    wcb_inserted = 0
    duplicate_count = 0
    error_count = 0
    
    # Insert payroll records
    payroll_sql = """
    INSERT INTO driver_payroll 
    (driver_id, year, month, charter_id, reserve_number, pay_date, gross_pay, cpp, ei, tax, 
     total_deductions, net_pay, expenses, wcb_payment, wcb_rate, source)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (driver_id, year, month, charter_id, reserve_number, pay_date) DO NOTHING
    """
    
    # Track WCB summaries by driver/year/month
    wcb_summaries = {}
    
    for i, record in enumerate(payroll_records):
        if i % 1000 == 0:
            print(f"Importing payroll record {i+1}/{len(payroll_records)}...")
            
        try:
            cursor.execute(payroll_sql, (
                record['driver_id'],
                record['year'],
                record['month'],
                record['charter_id'],
                record['reserve_number'],
                record['pay_date'],
                record['gross_pay'],
                record['cpp'],
                record['ei'],
                record['tax'],
                record['total_deductions'],
                record['net_pay'],
                record['expenses'],
                record['wcb_payment'],
                record['wcb_rate'],
                record['source']
            ))
            
            if cursor.rowcount > 0:
                payroll_inserted += 1
            else:
                duplicate_count += 1
            
            # Track WCB summary data
            wcb_key = (record['driver_id'], record['year'], record['month'])
            if wcb_key not in wcb_summaries:
                wcb_summaries[wcb_key] = {
                    'driver_id': record['driver_id'],
                    'year': record['year'],
                    'month': record['month'],
                    'wcb_payment': record['wcb_payment'],
                    'wcb_rate': record['wcb_rate'],
                    'total_gross_pay': Decimal('0')
                }
            
            if wcb_summaries[wcb_key]['total_gross_pay'] is not None:
                wcb_summaries[wcb_key]['total_gross_pay'] += record['gross_pay']
                
        except Exception as e:
            print(f"Error importing payroll record {i}: {e}")
            error_count += 1
            continue
    
    # Insert WCB summaries
    wcb_sql = """
    INSERT INTO wcb_summary 
    (driver_id, year, month, wcb_payment, wcb_rate, total_gross_pay, source)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (driver_id, year, month) DO NOTHING
    """
    
    for wcb_key, wcb_data in wcb_summaries.items():
        try:
            cursor.execute(wcb_sql, (
                wcb_data['driver_id'],
                wcb_data['year'],
                wcb_data['month'],
                wcb_data['wcb_payment'],
                wcb_data['wcb_rate'],
                wcb_data['total_gross_pay'],
                'payroll_wcb_report'
            ))
            
            if cursor.rowcount > 0:
                wcb_inserted += 1
                
        except Exception as e:
            print(f"Error importing WCB summary: {e}")
            continue
    
    try:
        conn.commit()
        print(f"Payroll import completed:")
        print(f"  Payroll records inserted: {payroll_inserted}")
        print(f"  WCB summaries inserted: {wcb_inserted}")
        print(f"  Duplicates skipped: {duplicate_count}")
        print(f"  Errors: {error_count}")
        
    except Exception as e:
        print(f"Error committing payroll data: {e}")
        conn.rollback()
        return 0
    
    return payroll_inserted

def main():
    """Main execution function."""
    print("=== Payroll and WCB Data Import ===")
    
    # File path
    payroll_file = "l:/limo/outlook_all_emails_scan/attachments/other/20250915_printable_pay_report_by_driver_with_charters_and_wcb.txt"
    
    print(f"Processing file: {payroll_file}")
    
    # Parse the payroll report
    print("Parsing payroll and WCB report...")
    payroll_records = parse_payroll_report(payroll_file)
    
    if not payroll_records:
        print("No payroll data found to import")
        return
    
    # Connect to database
    print("Connecting to database...")
    conn = connect_to_database()
    if not conn:
        print("Failed to connect to database")
        return
    
    try:
        # Create tables
        print("Creating payroll and WCB tables...")
        create_payroll_tables(conn)
        
        # Import data
        print("Importing payroll and WCB data...")
        imported_count = import_payroll_data(conn, payroll_records)
        
        print(f"\n=== Import Complete ===")
        print(f"Successfully processed {len(payroll_records)} payroll records")
        
    finally:
        conn.close()

if __name__ == "__main__":
    main()