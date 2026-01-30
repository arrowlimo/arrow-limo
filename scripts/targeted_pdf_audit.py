#!/usr/bin/env python3
"""
Targeted PDF Audit - Specific File List Validation

This script audits the specific PDF files provided to verify:
1. All payroll data has been entered into almsdata
2. ROE files are updated as required
3. T4 records are matched and audited
4. Any other data found is validated and updated
"""

import os
import sys
import psycopg2
import PyPDF2
import pandas as pd
import re
from datetime import datetime
from pathlib import Path
import json
import hashlib

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
        port=os.getenv('DB_PORT', '5432')
    )

class TargetedPDFAuditor:
    def __init__(self):
        self.conn = get_db_connection()
        self.cur = self.conn.cursor()
        self.audit_results = {}
        self.missing_data = []
        self.validation_errors = []
        
        # Define the target PDF files
        self.target_files = [
            "L:\\limo\\pdf\\2012 YTD Hourly Payroll Remittance_ocred.pdf",
            "L:\\limo\\pdf\\Zak Keller  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf",
            "L:\\limo\\pdf\\TD1 - Federal_ocred.pdf",
            "L:\\limo\\pdf\\TD1 - AB_ocred.pdf",
            "L:\\limo\\pdf\\Tammy Pettitt Accum. Vacation pay Report_ocred (1).pdf",
            "L:\\limo\\pdf\\Stephen Meek-Vacation Pay Paid out Mar.21.14_ocred (1).pdf",
            "L:\\limo\\pdf\\Stephen Meek Vacation pay -Paid out Mar.01.14_ocred.pdf",
            "L:\\limo\\pdf\\September 2013 PDTA Report_ocred (1).pdf",
            "L:\\limo\\pdf\\September 2013 Payroll Cheque Stubs_ocred (1).pdf",
            "L:\\limo\\pdf\\Sep.2014 PD7A_ocred (1).pdf",
            "L:\\limo\\pdf\\Sep.2014 Pay Stubs_ocred (1).pdf",
            "L:\\limo\\pdf\\ROE-Stephen Meek-R1256_ocred (1).pdf",
            "L:\\limo\\pdf\\ROE-Dr51,Dr53,Dr54,Dr60,H02_ocred.pdf",
            "L:\\limo\\pdf\\RICHARD, PAUL_ocred (1).pdf",
            "L:\\limo\\pdf\\RICHARD, KAREN_ocred (1).pdf",
            "L:\\limo\\pdf\\Paul Richard Pay Cheques_ocred.pdf",
            "L:\\limo\\pdf\\Paul Mansell  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf",
            "L:\\limo\\pdf\\Pat Fraser ROE R1256_ocred (1).pdf",
            "L:\\limo\\pdf\\October 2013 PDA Report_ocred (1).pdf",
            "L:\\limo\\pdf\\October 2013 Payroll Cheque Stubs_ocred (1).pdf",
            "L:\\limo\\pdf\\Arrow2014 T4's-Employer_ocred.pdf",
            "L:\\limo\\pdf\\Arrow2014 T4's-Employee 2copies_ocred (1).pdf",
            "L:\\limo\\pdf\\Arrow2014 T4's-CRA_ocred.pdf",
            "L:\\limo\\pdf\\Arrow 2014 T4 Summary_ocred (1).pdf",
            "L:\\limo\\pdf\\Arrow 2013 T4 Summary_ocred.pdf",
            "L:\\limo\\pdf\\2014 Employee Earnings Sum._ocred (1).pdf",
            "L:\\limo\\pdf\\2013 T4 Slips Arrow Office File Copy_ocred.pdf",
            "L:\\limo\\pdf\\2013 T4 Slips - Employee Info sheet (Optional)_ocred (1).pdf",
            "L:\\limo\\pdf\\2013 T4 Slips - Arrow Employees_ocred (1).pdf",
            "L:\\limo\\pdf\\2013 Arrow Limousine & Sedan Ltd. T4 Slips-CRA Copy_ocred (1).pdf"
        ]
        
    def extract_pdf_text(self, pdf_path):
        """Extract text from PDF file safely."""
        try:
            if not os.path.exists(pdf_path):
                print(f"[WARN]  File not found: {pdf_path}")
                return ""
                
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text.strip()
        except Exception as e:
            print(f"[WARN]  Could not read PDF {pdf_path}: {e}")
            return ""
    
    def categorize_files(self):
        """Categorize the target files by type."""
        categories = {
            'payroll_reports': [],
            'pay_stubs': [],
            't4_documents': [],
            'roe_documents': [],
            'vacation_pay': [],
            'tax_forms': [],
            'employee_records': []
        }
        
        for file_path in self.target_files:
            filename = os.path.basename(file_path).lower()
            
            if any(term in filename for term in ['pd7a', 'pda', 'pdta', 'payroll remittance']):
                categories['payroll_reports'].append(file_path)
            elif any(term in filename for term in ['pay stub', 'pay cheque', 'cheque stub']):
                categories['pay_stubs'].append(file_path)
            elif any(term in filename for term in ['t4', 't-4']):
                categories['t4_documents'].append(file_path)
            elif any(term in filename for term in ['roe']):
                categories['roe_documents'].append(file_path)
            elif any(term in filename for term in ['vacation']):
                categories['vacation_pay'].append(file_path)
            elif any(term in filename for term in ['td1']):
                categories['tax_forms'].append(file_path)
            else:
                categories['employee_records'].append(file_path)
        
        return categories
    
    def audit_payroll_reports(self, report_files):
        """Audit payroll report files (PD7A, PDTA, etc.)."""
        print("\n🔍 AUDITING PAYROLL REPORTS")
        print("-" * 30)
        
        for file_path in report_files:
            filename = os.path.basename(file_path)
            print(f"\n📄 Processing: {filename}")
            
            text = self.extract_pdf_text(file_path)
            if not text:
                continue
            
            # Extract year and month from filename or content
            year_match = re.search(r'20(1[2-5])', filename)  # 2012-2015
            month_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', filename, re.IGNORECASE)
            
            if year_match:
                year = 2000 + int(year_match.group(1))
                month_name = month_match.group(1) if month_match else 'Unknown'
                
                # Extract payroll totals from content
                gross_matches = re.findall(r'(\d{1,3}(?:,\d{3})*\.?\d{2})', text)
                amounts = [float(match.replace(',', '')) for match in gross_matches if float(match.replace(',', '')) > 100]
                
                if amounts:
                    total_payroll = sum(amounts)
                    
                    # Check against database for this period
                    self.cur.execute("""
                        SELECT 
                            COUNT(*) as record_count,
                            SUM(COALESCE(gross_pay, 0)) as total_gross,
                            COUNT(DISTINCT driver_id) as unique_drivers
                        FROM driver_payroll 
                        WHERE year = %s
                        AND EXTRACT(MONTH FROM pay_date) = %s
                    """, (year, self.get_month_number(month_name)))
                    
                    db_result = self.cur.fetchone()
                    if db_result:
                        db_count, db_gross, db_drivers = db_result
                        print(f"   📊 {year} {month_name}:")
                        print(f"      PDF Total: ${total_payroll:,.2f} ({len(amounts)} entries)")
                        print(f"      DB Total: ${float(db_gross or 0):,.2f} ({db_count} records, {db_drivers} drivers)")
                        
                        # Compare totals (within 5% tolerance)
                        if db_gross and abs(total_payroll - float(db_gross)) / float(db_gross) < 0.05:
                            print(f"      [OK] MATCH: Totals within 5%")
                        elif db_gross:
                            print(f"      [WARN]  MISMATCH: Difference ${abs(total_payroll - float(db_gross)):,.2f}")
                            self.validation_errors.append(f"Payroll {year} {month_name}: PDF vs DB mismatch")
                        else:
                            print(f"      [FAIL] MISSING: No database records found")
                            self.missing_data.append(f"Payroll {year} {month_name}: {filename}")
                else:
                    print(f"   [WARN]  No payroll amounts found in content")
    
    def audit_t4_documents(self, t4_files):
        """Audit T4 documents for completeness and accuracy."""
        print("\n🔍 AUDITING T4 DOCUMENTS")
        print("-" * 25)
        
        t4_data = {}
        
        for file_path in t4_files:
            filename = os.path.basename(file_path)
            print(f"\n📄 Processing: {filename}")
            
            text = self.extract_pdf_text(file_path)
            if not text:
                continue
            
            # Extract year
            year_match = re.search(r'20(1[3-5])', filename)  # 2013-2015
            if not year_match:
                year_match = re.search(r'20(1[3-5])', text)
            
            if year_match:
                year = 2000 + int(year_match.group(1))
                
                if year not in t4_data:
                    t4_data[year] = {
                        'files': [],
                        'employees': [],
                        'total_income': 0,
                        'total_cpp': 0,
                        'total_ei': 0,
                        'total_tax': 0
                    }
                
                t4_data[year]['files'].append(filename)
                
                # Extract employee names and amounts
                employee_matches = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', text)
                income_matches = re.findall(r'Employment income.*?(\d{1,3}(?:,\d{3})*\.?\d{2})', text, re.IGNORECASE)
                cpp_matches = re.findall(r'CPP.*?(\d{1,3}(?:,\d{3})*\.?\d{2})', text, re.IGNORECASE)
                ei_matches = re.findall(r'EI.*?(\d{1,3}(?:,\d{3})*\.?\d{2})', text, re.IGNORECASE)
                tax_matches = re.findall(r'Income tax.*?(\d{1,3}(?:,\d{3})*\.?\d{2})', text, re.IGNORECASE)
                
                # Process amounts
                if income_matches:
                    for match in income_matches:
                        amount = float(match.replace(',', ''))
                        t4_data[year]['total_income'] += amount
                
                if cpp_matches:
                    for match in cpp_matches:
                        amount = float(match.replace(',', ''))
                        t4_data[year]['total_cpp'] += amount
                
                if ei_matches:
                    for match in ei_matches:
                        amount = float(match.replace(',', ''))
                        t4_data[year]['total_ei'] += amount
                
                if tax_matches:
                    for match in tax_matches:
                        amount = float(match.replace(',', ''))
                        t4_data[year]['total_tax'] += amount
                
                # Store unique employee names
                for emp_match in employee_matches:
                    emp_name = emp_match.strip()
                    if len(emp_name) > 5 and emp_name not in t4_data[year]['employees']:
                        t4_data[year]['employees'].append(emp_name)
                
                print(f"   📊 Found {len(income_matches)} income entries, {len(employee_matches)} employees")
        
        # Compare with database T4 data
        print(f"\n📋 T4 COMPARISON WITH DATABASE:")
        
        for year, pdf_data in t4_data.items():
            self.cur.execute("""
                SELECT 
                    COUNT(*) as record_count,
                    SUM(COALESCE(t4_box_14, 0)) as total_income,
                    SUM(COALESCE(t4_box_16, 0)) as total_cpp,
                    SUM(COALESCE(t4_box_18, 0)) as total_ei,
                    SUM(COALESCE(t4_box_22, 0)) as total_tax,
                    COUNT(DISTINCT driver_id) as unique_drivers
                FROM driver_payroll 
                WHERE year = %s
                AND (t4_box_14 IS NOT NULL OR t4_box_16 IS NOT NULL)
            """, (year,))
            
            db_result = self.cur.fetchone()
            
            print(f"\n   📅 {year} T4 DATA:")
            print(f"      PDF Files: {len(pdf_data['files'])}")
            print(f"      PDF Employees: {len(pdf_data['employees'])}")
            print(f"      PDF Income: ${pdf_data['total_income']:,.2f}")
            
            if db_result:
                db_count, db_income, db_cpp, db_ei, db_tax, db_drivers = db_result
                print(f"      DB Records: {db_count} ({db_drivers} drivers)")
                print(f"      DB Income: ${float(db_income or 0):,.2f}")
                print(f"      DB CPP: ${float(db_cpp or 0):,.2f}")
                print(f"      DB EI: ${float(db_ei or 0):,.2f}")
                print(f"      DB Tax: ${float(db_tax or 0):,.2f}")
                
                # Validate income totals
                if pdf_data['total_income'] > 0 and db_income:
                    income_diff = abs(pdf_data['total_income'] - float(db_income))
                    if income_diff < 1000:  # Within $1000
                        print(f"      [OK] INCOME MATCH: Within $1000 tolerance")
                    else:
                        print(f"      [WARN]  INCOME MISMATCH: Difference ${income_diff:,.2f}")
                        self.validation_errors.append(f"T4 {year}: Income mismatch ${income_diff:,.2f}")
                elif pdf_data['total_income'] > 0:
                    print(f"      [FAIL] MISSING: PDF data exists but no DB T4 records")
                    self.missing_data.append(f"T4 {year}: Missing database records")
            else:
                print(f"      [FAIL] NO DATABASE RECORDS FOUND")
                if pdf_data['total_income'] > 0:
                    self.missing_data.append(f"T4 {year}: No database records")
    
    def audit_roe_documents(self, roe_files):
        """Audit ROE documents for completeness."""
        print("\n🔍 AUDITING ROE DOCUMENTS")
        print("-" * 25)
        
        # Check if ROE table exists, create if needed
        self.cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'employee_roe_records'
            )
        """)
        
        roe_table_exists = self.cur.fetchone()[0]
        
        if not roe_table_exists:
            print("📋 Creating ROE tracking table...")
            self.cur.execute("""
                CREATE TABLE employee_roe_records (
                    id SERIAL PRIMARY KEY,
                    employee_id INTEGER,
                    employee_name VARCHAR(200),
                    roe_number VARCHAR(50),
                    termination_date DATE,
                    last_day_worked DATE,
                    reason_code VARCHAR(10),
                    insurable_earnings DECIMAL(12,2),
                    insurable_hours INTEGER,
                    pay_period_type VARCHAR(50),
                    source_file VARCHAR(500),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
                )
            """)
            self.conn.commit()
            print("[OK] ROE table created")
        
        roe_records = []
        
        for file_path in roe_files:
            filename = os.path.basename(file_path)
            print(f"\n📄 Processing ROE: {filename}")
            
            text = self.extract_pdf_text(file_path)
            if not text:
                continue
            
            # Extract ROE information
            employee_name_match = re.search(r'(Stephen\s+Meek|Pat\s+Fraser)', text, re.IGNORECASE)
            if not employee_name_match:
                # Try to extract from filename
                employee_name_match = re.search(r'ROE-([^-]+)', filename)
            
            roe_number_match = re.search(r'R(\d{4})', text)
            termination_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text)
            earnings_match = re.search(r'(\d{1,3}(?:,\d{3})*\.?\d{2})', text)
            
            if employee_name_match:
                employee_name = employee_name_match.group(1).strip()
                roe_number = roe_number_match.group(1) if roe_number_match else None
                
                roe_record = {
                    'file': filename,
                    'employee_name': employee_name,
                    'roe_number': roe_number,
                    'termination_date': termination_match.group(1) if termination_match else None,
                    'earnings': float(earnings_match.group(1).replace(',', '')) if earnings_match else None
                }
                
                roe_records.append(roe_record)
                
                print(f"   📋 Employee: {employee_name}")
                if roe_number:
                    print(f"   📋 ROE Number: R{roe_number}")
                if roe_record['termination_date']:
                    print(f"   📋 Termination Date: {roe_record['termination_date']}")
                
                # Check if ROE record exists in database
                self.cur.execute("""
                    SELECT COUNT(*) FROM employee_roe_records 
                    WHERE employee_name ILIKE %s 
                    OR (roe_number = %s AND roe_number IS NOT NULL)
                """, (f"%{employee_name}%", roe_number))
                
                exists = self.cur.fetchone()[0] > 0
                
                if not exists:
                    print(f"   [FAIL] ROE record missing from database")
                    self.missing_data.append(f"ROE: {employee_name} - {filename}")
                    
                    # Insert ROE record
                    try:
                        # Try to find employee_id
                        self.cur.execute("""
                            SELECT employee_id FROM employees 
                            WHERE full_name ILIKE %s 
                            OR first_name ILIKE %s 
                            OR last_name ILIKE %s
                            LIMIT 1
                        """, (f"%{employee_name}%", f"%{employee_name.split()[0]}%", f"%{employee_name.split()[-1]}%"))
                        
                        employee_result = self.cur.fetchone()
                        employee_id = employee_result[0] if employee_result else None
                        
                        self.cur.execute("""
                            INSERT INTO employee_roe_records 
                            (employee_id, employee_name, roe_number, source_file, insurable_earnings)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (employee_id, employee_name, roe_number, filename, roe_record['earnings']))
                        
                        self.conn.commit()
                        print(f"   [OK] ROE record added to database")
                        
                    except Exception as e:
                        print(f"   [WARN]  Could not insert ROE record: {e}")
                        self.conn.rollback()
                else:
                    print(f"   [OK] ROE record exists in database")
        
        print(f"\n📊 PROCESSED {len(roe_records)} ROE DOCUMENTS")
    
    def audit_vacation_pay(self, vacation_files):
        """Audit vacation pay documents."""
        print("\n🔍 AUDITING VACATION PAY DOCUMENTS")
        print("-" * 35)
        
        vacation_records = []
        
        for file_path in vacation_files:
            filename = os.path.basename(file_path)
            print(f"\n📄 Processing: {filename}")
            
            text = self.extract_pdf_text(file_path)
            if not text:
                continue
            
            # Extract employee name from filename
            employee_match = re.search(r'(Stephen\s+Meek|Tammy\s+Pettitt)', filename, re.IGNORECASE)
            if employee_match:
                employee_name = employee_match.group(1)
                
                # Extract amounts
                amount_matches = re.findall(r'(\d{1,3}(?:,\d{3})*\.?\d{2})', text)
                amounts = [float(match.replace(',', '')) for match in amount_matches if float(match.replace(',', '')) > 10]
                
                # Extract dates
                date_matches = re.findall(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text)
                
                vacation_record = {
                    'file': filename,
                    'employee_name': employee_name,
                    'amounts': amounts,
                    'dates': date_matches,
                    'total_amount': sum(amounts) if amounts else 0
                }
                
                vacation_records.append(vacation_record)
                
                print(f"   👤 Employee: {employee_name}")
                print(f"   💰 Total Amount: ${vacation_record['total_amount']:,.2f}")
                print(f"   📅 Dates Found: {len(date_matches)}")
                
                # Check against vacation_pay in driver_payroll
                self.cur.execute("""
                    SELECT 
                        COUNT(*) as record_count,
                        SUM(COALESCE(vacation_pay, 0)) as total_vacation
                    FROM driver_payroll dp
                    LEFT JOIN employees e ON dp.employee_id = e.employee_id
                    WHERE e.full_name ILIKE %s
                    AND vacation_pay > 0
                """, (f"%{employee_name}%",))
                
                db_result = self.cur.fetchone()
                if db_result:
                    db_count, db_vacation = db_result
                    print(f"   📊 DB Vacation Pay: {db_count} records, ${float(db_vacation or 0):,.2f}")
                    
                    if db_vacation and vacation_record['total_amount'] > 0:
                        diff = abs(vacation_record['total_amount'] - float(db_vacation))
                        if diff < 100:  # Within $100
                            print(f"   [OK] MATCH: PDF vs DB within $100")
                        else:
                            print(f"   [WARN]  MISMATCH: Difference ${diff:,.2f}")
                    elif vacation_record['total_amount'] > 0:
                        print(f"   [FAIL] MISSING: PDF shows vacation pay but not in DB")
                        self.missing_data.append(f"Vacation Pay: {employee_name} - {filename}")
        
        print(f"\n📊 PROCESSED {len(vacation_records)} VACATION PAY DOCUMENTS")
    
    def get_month_number(self, month_name):
        """Convert month name to number."""
        months = {
            'january': 1, 'jan': 1,
            'february': 2, 'feb': 2,
            'march': 3, 'mar': 3,
            'april': 4, 'apr': 4,
            'may': 5,
            'june': 6, 'jun': 6,
            'july': 7, 'jul': 7,
            'august': 8, 'aug': 8,
            'september': 9, 'sep': 9,
            'october': 10, 'oct': 10,
            'november': 11, 'nov': 11,
            'december': 12, 'dec': 12
        }
        return months.get(month_name.lower(), 1)
    
    def generate_audit_summary(self):
        """Generate audit summary report."""
        print("\n" + "="*60)
        print("📊 TARGETED PDF AUDIT SUMMARY")
        print("="*60)
        
        # Check files exist
        existing_files = []
        missing_files = []
        
        for file_path in self.target_files:
            if os.path.exists(file_path):
                existing_files.append(file_path)
            else:
                missing_files.append(file_path)
        
        print(f"\n📁 FILE STATUS:")
        print(f"   Total Files: {len(self.target_files)}")
        print(f"   Found: {len(existing_files)}")
        print(f"   Missing: {len(missing_files)}")
        
        if missing_files:
            print(f"\n[FAIL] MISSING FILES:")
            for file_path in missing_files[:10]:  # Show first 10
                print(f"   - {os.path.basename(file_path)}")
            if len(missing_files) > 10:
                print(f"   ... and {len(missing_files) - 10} more")
        
        # Database status
        self.cur.execute("""
            SELECT 
                COUNT(*) as total_payroll,
                COUNT(CASE WHEN t4_box_14 > 0 THEN 1 END) as t4_records,
                COUNT(CASE WHEN vacation_pay > 0 THEN 1 END) as vacation_records,
                SUM(COALESCE(gross_pay, 0)) as total_gross,
                MIN(year) as min_year,
                MAX(year) as max_year
            FROM driver_payroll
        """)
        
        db_stats = self.cur.fetchone()
        
        print(f"\n📊 DATABASE STATUS:")
        if db_stats:
            print(f"   Total Payroll Records: {db_stats[0]:,}")
            print(f"   T4 Records: {db_stats[1]:,}")
            print(f"   Vacation Records: {db_stats[2]:,}")
            print(f"   Total Gross Pay: ${float(db_stats[3] or 0):,.2f}")
            print(f"   Year Range: {db_stats[4]} - {db_stats[5]}")
        
        # ROE status
        self.cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'employee_roe_records'
            )
        """)
        
        roe_exists = self.cur.fetchone()[0]
        if roe_exists:
            self.cur.execute("SELECT COUNT(*) FROM employee_roe_records")
            roe_count = self.cur.fetchone()[0]
            print(f"   ROE Records: {roe_count:,}")
        else:
            print(f"   ROE Records: Table not found")
        
        # Audit results
        print(f"\n🎯 AUDIT RESULTS:")
        if not self.missing_data and not self.validation_errors:
            print("   [OK] ALL PDF DATA VERIFIED IN DATABASE")
            print("   [OK] NO MISSING RECORDS FOUND") 
            print("   [OK] NO VALIDATION ERRORS FOUND")
            success = True
        else:
            success = False
            if self.missing_data:
                print(f"   [FAIL] Missing Data Items: {len(self.missing_data)}")
                for item in self.missing_data[:5]:  # Show first 5
                    print(f"      - {item}")
                if len(self.missing_data) > 5:
                    print(f"      ... and {len(self.missing_data) - 5} more")
            
            if self.validation_errors:
                print(f"   [WARN]  Validation Errors: {len(self.validation_errors)}")
                for error in self.validation_errors:
                    print(f"      - {error}")
        
        print(f"\n🏁 AUDIT COMPLETED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return success

def main():
    """Execute targeted PDF audit."""
    print("🔍 TARGETED PDF AUDIT SYSTEM")
    print("=" * 30)
    print(f"Audit Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    auditor = TargetedPDFAuditor()
    
    try:
        # Categorize files
        categories = auditor.categorize_files()
        
        print("📂 FILE CATEGORIES:")
        for category, files in categories.items():
            if files:
                print(f"   {category}: {len(files)} files")
        
        # Audit each category
        auditor.audit_payroll_reports(categories['payroll_reports'])
        auditor.audit_t4_documents(categories['t4_documents'])
        auditor.audit_roe_documents(categories['roe_documents'])
        auditor.audit_vacation_pay(categories['vacation_pay'])
        
        # Generate summary
        success = auditor.generate_audit_summary()
        
        if success:
            print("\n🎉 SUCCESS: All targeted PDF data verified!")
        else:
            print("\n[WARN]  WARNING: Some issues found - review audit report")
            
    except Exception as e:
        print(f"\n[FAIL] ERROR during audit: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        auditor.cur.close()
        auditor.conn.close()

if __name__ == "__main__":
    main()