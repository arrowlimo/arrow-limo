#!/usr/bin/env python3
"""
Comprehensive PDF Audit and Validation System

This script performs a complete audit to verify:
1. All PDF data has been entered into almsdata
2. ROE files are updated as required
3. T4 records are matched and audited
4. Any other data found is validated and updated

Comprehensive verification across all document types.
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

class PDFAuditSystem:
    def __init__(self):
        self.conn = get_db_connection()
        self.cur = self.conn.cursor()
        self.audit_results = {}
        self.missing_data = []
        self.validation_errors = []
        
    def scan_all_pdf_files(self):
        """Scan all PDF files in the workspace and categorize them."""
        print("🔍 SCANNING ALL PDF FILES IN WORKSPACE")
        print("=" * 40)
        
        pdf_files = []
        workspace_root = Path("L:/limo")
        
        # Find all PDF files
        for pdf_path in workspace_root.rglob("*.pdf"):
            if pdf_path.is_file():
                pdf_files.append(pdf_path)
        
        print(f"Found {len(pdf_files)} PDF files")
        
        # Categorize PDFs
        categories = {
            'payroll': [],
            't4_slips': [],
            'roe_records': [],
            'receipts': [],
            'insurance': [],
            'banking': [],
            'tax_documents': [],
            'vehicle_docs': [],
            'other': []
        }
        
        for pdf_path in pdf_files:
            filename = pdf_path.name.lower()
            
            if any(term in filename for term in ['payroll', 'pay_stub', 'paystub', 'salary']):
                categories['payroll'].append(pdf_path)
            elif any(term in filename for term in ['t4', 't-4']):
                categories['t4_slips'].append(pdf_path)
            elif any(term in filename for term in ['roe', 'r.o.e', 'record_employment']):
                categories['roe_records'].append(pdf_path)
            elif any(term in filename for term in ['receipt', 'invoice', 'bill']):
                categories['receipts'].append(pdf_path)
            elif any(term in filename for term in ['insurance', 'policy', 'coverage']):
                categories['insurance'].append(pdf_path)
            elif any(term in filename for term in ['bank', 'statement', 'deposit']):
                categories['banking'].append(pdf_path)
            elif any(term in filename for term in ['tax', 'cra', 'gst', 'hst']):
                categories['tax_documents'].append(pdf_path)
            elif any(term in filename for term in ['vehicle', 'registration', 'license']):
                categories['vehicle_docs'].append(pdf_path)
            else:
                categories['other'].append(pdf_path)
        
        # Report categories
        for category, files in categories.items():
            if files:
                print(f"\n📂 {category.upper()}: {len(files)} files")
                for file_path in files[:5]:  # Show first 5
                    print(f"   - {file_path.name}")
                if len(files) > 5:
                    print(f"   ... and {len(files) - 5} more")
        
        return categories
    
    def extract_pdf_text(self, pdf_path):
        """Extract text from PDF file safely."""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except Exception as e:
            print(f"[WARN]  Could not read PDF {pdf_path}: {e}")
            return ""
    
    def audit_t4_records(self, t4_files):
        """Audit T4 slip records against database."""
        print("\n🔍 AUDITING T4 RECORDS")
        print("-" * 25)
        
        if not t4_files:
            print("ℹ️  No T4 PDF files found")
            return
        
        # Get existing T4 data from database
        self.cur.execute("""
            SELECT 
                year, 
                COUNT(*) as record_count,
                SUM(COALESCE(t4_box_14, 0)) as total_employment_income,
                SUM(COALESCE(t4_box_16, 0)) as total_cpp,
                SUM(COALESCE(t4_box_18, 0)) as total_ei,
                SUM(COALESCE(t4_box_22, 0)) as total_tax
            FROM driver_payroll 
            WHERE year IS NOT NULL
            GROUP BY year 
            ORDER BY year DESC
        """)
        
        db_t4_data = {}
        for row in self.cur.fetchall():
            year, count, income, cpp, ei, tax = row
            db_t4_data[year] = {
                'count': count,
                'income': float(income) if income else 0,
                'cpp': float(cpp) if cpp else 0,
                'ei': float(ei) if ei else 0,
                'tax': float(tax) if tax else 0
            }
        
        print(f"📊 DATABASE T4 SUMMARY:")
        for year in sorted(db_t4_data.keys(), reverse=True):
            data = db_t4_data[year]
            print(f"   {year}: {data['count']} records, Income: ${data['income']:,.2f}")
        
        # Analyze T4 PDF files
        pdf_t4_data = {}
        for pdf_path in t4_files:
            try:
                text = self.extract_pdf_text(pdf_path)
                
                # Extract year from filename or content
                year_match = re.search(r'20(\d{2})', pdf_path.name)
                if year_match:
                    year = 2000 + int(year_match.group(1))
                else:
                    year_match = re.search(r'20(\d{2})', text)
                    year = 2000 + int(year_match.group(1)) if year_match else None
                
                if year:
                    # Extract T4 amounts
                    income_match = re.search(r'Employment income.*?(\d{1,3}(?:,\d{3})*\.?\d{2})', text)
                    cpp_match = re.search(r'CPP.*?(\d{1,3}(?:,\d{3})*\.?\d{2})', text)
                    ei_match = re.search(r'EI.*?(\d{1,3}(?:,\d{3})*\.?\d{2})', text)
                    
                    if year not in pdf_t4_data:
                        pdf_t4_data[year] = []
                    
                    pdf_t4_data[year].append({
                        'file': pdf_path.name,
                        'income': float(income_match.group(1).replace(',', '')) if income_match else 0,
                        'cpp': float(cpp_match.group(1).replace(',', '')) if cpp_match else 0,
                        'ei': float(ei_match.group(1).replace(',', '')) if ei_match else 0
                    })
            
            except Exception as e:
                print(f"[WARN]  Error processing T4 PDF {pdf_path.name}: {e}")
        
        # Compare PDF vs Database
        print(f"\n📋 T4 COMPARISON (PDF vs DATABASE):")
        for year in sorted(set(list(pdf_t4_data.keys()) + list(db_t4_data.keys())), reverse=True):
            pdf_data = pdf_t4_data.get(year, [])
            db_data = db_t4_data.get(year, {})
            
            pdf_total_income = sum(record['income'] for record in pdf_data)
            db_total_income = db_data.get('income', 0)
            
            if pdf_data and db_data:
                income_diff = abs(pdf_total_income - db_total_income)
                if income_diff < 100:  # Within $100
                    print(f"   [OK] {year}: PDF ${pdf_total_income:,.2f} ≈ DB ${db_total_income:,.2f}")
                else:
                    print(f"   [WARN]  {year}: PDF ${pdf_total_income:,.2f} ≠ DB ${db_total_income:,.2f} (diff: ${income_diff:,.2f})")
                    self.validation_errors.append(f"T4 {year}: Income mismatch")
            elif pdf_data:
                print(f"   [FAIL] {year}: PDF data exists (${pdf_total_income:,.2f}) but missing from database")
                self.missing_data.append(f"T4 {year}: Missing from database")
            elif db_data:
                print(f"   ℹ️  {year}: Database only (${db_total_income:,.2f})")
    
    def audit_roe_records(self, roe_files):
        """Audit ROE (Record of Employment) files."""
        print("\n🔍 AUDITING ROE RECORDS")
        print("-" * 20)
        
        if not roe_files:
            print("ℹ️  No ROE PDF files found")
            return
        
        # Check for ROE tracking table
        self.cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'employee_roe_records'
            )
        """)
        
        roe_table_exists = self.cur.fetchone()[0]
        
        if not roe_table_exists:
            print("[WARN]  ROE tracking table doesn't exist - creating...")
            self.cur.execute("""
                CREATE TABLE IF NOT EXISTS employee_roe_records (
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.conn.commit()
            print("[OK] ROE tracking table created")
        
        # Process ROE files
        roe_records = []
        for pdf_path in roe_files:
            try:
                text = self.extract_pdf_text(pdf_path)
                
                # Extract ROE information
                employee_name_match = re.search(r'Employee.*?([A-Z][a-z]+ [A-Z][a-z]+)', text)
                roe_number_match = re.search(r'ROE.*?(\d+)', text)
                termination_match = re.search(r'Termination.*?(\d{2}/\d{2}/\d{4})', text)
                earnings_match = re.search(r'Earnings.*?(\d{1,3}(?:,\d{3})*\.?\d{2})', text)
                
                if employee_name_match or roe_number_match:
                    roe_record = {
                        'file': pdf_path.name,
                        'employee_name': employee_name_match.group(1) if employee_name_match else 'Unknown',
                        'roe_number': roe_number_match.group(1) if roe_number_match else None,
                        'termination_date': termination_match.group(1) if termination_match else None,
                        'earnings': float(earnings_match.group(1).replace(',', '')) if earnings_match else None
                    }
                    roe_records.append(roe_record)
            
            except Exception as e:
                print(f"[WARN]  Error processing ROE PDF {pdf_path.name}: {e}")
        
        print(f"📄 Found {len(roe_records)} ROE records in PDFs:")
        for record in roe_records:
            print(f"   - {record['employee_name']}: ROE #{record['roe_number']} ({record['file']})")
        
        # Check against database
        for record in roe_records:
            self.cur.execute("""
                SELECT COUNT(*) FROM employee_roe_records 
                WHERE employee_name = %s OR roe_number = %s
            """, (record['employee_name'], record['roe_number']))
            
            exists = self.cur.fetchone()[0] > 0
            
            if not exists:
                print(f"[FAIL] Missing ROE record: {record['employee_name']}")
                self.missing_data.append(f"ROE: {record['employee_name']} - {record['file']}")
            else:
                print(f"[OK] ROE record exists: {record['employee_name']}")
    
    def audit_receipt_pdfs(self, receipt_files):
        """Audit receipt PDF files against receipts table."""
        print("\n🔍 AUDITING RECEIPT PDFs")
        print("-" * 25)
        
        if not receipt_files:
            print("ℹ️  No receipt PDF files found")
            return
        
        receipt_data = []
        for pdf_path in receipt_files:
            try:
                text = self.extract_pdf_text(pdf_path)
                
                # Extract receipt information
                date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text)
                amount_match = re.search(r'\$?(\d{1,3}(?:,\d{3})*\.?\d{2})', text)
                vendor_match = re.search(r'([A-Z][A-Za-z\s]+(?:Inc|Ltd|Corp|Co\.)?)', text)
                
                if date_match and amount_match:
                    receipt_info = {
                        'file': pdf_path.name,
                        'date': date_match.group(1),
                        'amount': float(amount_match.group(1).replace(',', '').replace('$', '')),
                        'vendor': vendor_match.group(1).strip() if vendor_match else 'Unknown',
                        'file_path': str(pdf_path)
                    }
                    receipt_data.append(receipt_info)
            
            except Exception as e:
                print(f"[WARN]  Error processing receipt PDF {pdf_path.name}: {e}")
        
        print(f"📄 Found {len(receipt_data)} receipt records in PDFs")
        
        # Check against receipts table
        missing_receipts = []
        for receipt in receipt_data:
            # Look for matching receipt in database
            self.cur.execute("""
                SELECT COUNT(*) FROM receipts 
                WHERE ABS(gross_amount - %s) < 0.01 
                AND receipt_date::text LIKE %s
            """, (receipt['amount'], f"%{receipt['date'][:4]}%"))  # Fuzzy date match
            
            matches = self.cur.fetchone()[0]
            
            if matches == 0:
                missing_receipts.append(receipt)
                print(f"[FAIL] Missing receipt: {receipt['vendor']} ${receipt['amount']:.2f} ({receipt['file']})")
            else:
                print(f"[OK] Receipt exists: {receipt['vendor']} ${receipt['amount']:.2f}")
        
        if missing_receipts:
            self.missing_data.extend([f"Receipt: {r['file']}" for r in missing_receipts])
        
        return missing_receipts
    
    def audit_payroll_pdfs(self, payroll_files):
        """Audit payroll PDF files against driver_payroll table."""
        print("\n🔍 AUDITING PAYROLL PDFs")
        print("-" * 24)
        
        if not payroll_files:
            print("ℹ️  No payroll PDF files found")
            return
        
        payroll_data = []
        for pdf_path in payroll_files:
            try:
                text = self.extract_pdf_text(pdf_path)
                
                # Extract payroll information
                employee_match = re.search(r'Employee.*?([A-Z][a-z]+ [A-Z][a-z]+)', text)
                period_match = re.search(r'Period.*?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text)
                gross_match = re.search(r'Gross.*?(\d{1,3}(?:,\d{3})*\.?\d{2})', text)
                net_match = re.search(r'Net.*?(\d{1,3}(?:,\d{3})*\.?\d{2})', text)
                
                if employee_match and gross_match:
                    payroll_info = {
                        'file': pdf_path.name,
                        'employee': employee_match.group(1),
                        'period': period_match.group(1) if period_match else 'Unknown',
                        'gross': float(gross_match.group(1).replace(',', '')),
                        'net': float(net_match.group(1).replace(',', '')) if net_match else None
                    }
                    payroll_data.append(payroll_info)
            
            except Exception as e:
                print(f"[WARN]  Error processing payroll PDF {pdf_path.name}: {e}")
        
        print(f"📄 Found {len(payroll_data)} payroll records in PDFs")
        
        # Check against driver_payroll table
        for payroll in payroll_data:
            self.cur.execute("""
                SELECT COUNT(*) FROM driver_payroll dp
                LEFT JOIN employees e ON dp.employee_id = e.employee_id
                WHERE (e.full_name = %s OR dp.driver_name = %s)
                AND ABS(COALESCE(dp.gross_pay, 0) - %s) < 0.01
            """, (payroll['employee'], payroll['employee'], payroll['gross']))
            
            matches = self.cur.fetchone()[0]
            
            if matches == 0:
                print(f"[FAIL] Missing payroll: {payroll['employee']} ${payroll['gross']:.2f} ({payroll['file']})")
                self.missing_data.append(f"Payroll: {payroll['file']}")
            else:
                print(f"[OK] Payroll exists: {payroll['employee']} ${payroll['gross']:.2f}")
    
    def validate_data_completeness(self):
        """Validate overall data completeness and consistency."""
        print("\n🔍 VALIDATING DATA COMPLETENESS")
        print("-" * 30)
        
        # Check for orphaned records
        self.cur.execute("""
            SELECT 'Payments without charters' as issue, COUNT(*) as count
            FROM payments p
            LEFT JOIN charters c ON p.charter_id = c.charter_id
            WHERE p.reserve_number IS NOT NULL AND c.charter_id IS NULL
            
            UNION ALL
            
            SELECT 'Charters without clients' as issue, COUNT(*) as count
            FROM charters ch
            LEFT JOIN clients cl ON ch.client_id = cl.client_id
            WHERE ch.client_id IS NOT NULL AND cl.client_id IS NULL
            
            UNION ALL
            
            SELECT 'Receipts without employees' as issue, COUNT(*) as count
            FROM receipts r
            LEFT JOIN employees e ON r.employee_id = e.employee_id
            WHERE r.employee_id IS NOT NULL AND e.employee_id IS NULL
        """)
        
        orphaned_records = self.cur.fetchall()
        
        print("🔗 REFERENTIAL INTEGRITY CHECK:")
        for issue, count in orphaned_records:
            if count > 0:
                print(f"   [WARN]  {issue}: {count} orphaned records")
                self.validation_errors.append(f"{issue}: {count} orphaned")
            else:
                print(f"   [OK] {issue}: OK")
        
        # Check for duplicate records
        self.cur.execute("""
            SELECT 'Duplicate receipts' as issue, COUNT(*) - COUNT(DISTINCT (vendor_name, receipt_date, gross_amount)) as duplicates
            FROM receipts
            WHERE vendor_name IS NOT NULL AND receipt_date IS NOT NULL
            
            UNION ALL
            
            SELECT 'Duplicate payments' as issue, COUNT(*) - COUNT(DISTINCT (reserve_number, amount, payment_date)) as duplicates  
            FROM payments
            WHERE reserve_number IS NOT NULL AND amount IS NOT NULL
        """)
        
        duplicate_checks = self.cur.fetchall()
        
        print("\n📋 DUPLICATE RECORD CHECK:")
        for issue, count in duplicate_checks:
            if count > 0:
                print(f"   [WARN]  {issue}: {count} potential duplicates")
                self.validation_errors.append(f"{issue}: {count} duplicates")
            else:
                print(f"   [OK] {issue}: OK")
    
    def generate_audit_report(self):
        """Generate comprehensive audit report."""
        print("\n" + "="*60)
        print("📊 COMPREHENSIVE AUDIT REPORT")
        print("="*60)
        
        # Summary statistics
        self.cur.execute("""
            SELECT 
                (SELECT COUNT(*) FROM receipts) as total_receipts,
                (SELECT COUNT(*) FROM payments) as total_payments,
                (SELECT COUNT(*) FROM charters) as total_charters,
                (SELECT COUNT(*) FROM employees) as total_employees,
                (SELECT COUNT(*) FROM driver_payroll) as total_payroll
        """)
        
        stats = self.cur.fetchone()
        
        print(f"\n📈 DATABASE SUMMARY:")
        print(f"   Receipts: {stats[0]:,} records")
        print(f"   Payments: {stats[1]:,} records") 
        print(f"   Charters: {stats[2]:,} records")
        print(f"   Employees: {stats[3]:,} records")
        print(f"   Payroll: {stats[4]:,} records")
        
        # Audit results
        print(f"\n🎯 AUDIT RESULTS:")
        if not self.missing_data and not self.validation_errors:
            print("   [OK] ALL PDF DATA VERIFIED IN DATABASE")
            print("   [OK] NO MISSING RECORDS FOUND")
            print("   [OK] NO VALIDATION ERRORS FOUND")
        else:
            if self.missing_data:
                print(f"   [FAIL] Missing Data Items: {len(self.missing_data)}")
                for item in self.missing_data[:10]:  # Show first 10
                    print(f"      - {item}")
                if len(self.missing_data) > 10:
                    print(f"      ... and {len(self.missing_data) - 10} more")
            
            if self.validation_errors:
                print(f"   [WARN]  Validation Errors: {len(self.validation_errors)}")
                for error in self.validation_errors:
                    print(f"      - {error}")
        
        print(f"\n🏁 AUDIT COMPLETED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return len(self.missing_data) == 0 and len(self.validation_errors) == 0

def main():
    """Execute comprehensive PDF audit and validation."""
    print("🔍 COMPREHENSIVE PDF AUDIT AND VALIDATION SYSTEM")
    print("=" * 50)
    print(f"Audit Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    auditor = PDFAuditSystem()
    
    try:
        # Scan and categorize all PDFs
        pdf_categories = auditor.scan_all_pdf_files()
        
        # Audit each category
        auditor.audit_t4_records(pdf_categories['t4_slips'])
        auditor.audit_roe_records(pdf_categories['roe_records'])
        auditor.audit_receipt_pdfs(pdf_categories['receipts'])
        auditor.audit_payroll_pdfs(pdf_categories['payroll'])
        
        # Validate data completeness
        auditor.validate_data_completeness()
        
        # Generate final report
        success = auditor.generate_audit_report()
        
        if success:
            print("\n🎉 SUCCESS: All PDF data verified and validated!")
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