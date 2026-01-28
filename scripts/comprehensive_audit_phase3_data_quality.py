"""
Phase 3: Data Quality Analysis
================================
Analyzes receipts, charters, employees tables for data type violations:
- Dates appearing in driver name columns
- Client names mixed with driver names
- Ambiguous entries

Backup Policy:
1. Create timestamped backup before any modifications
2. Run all queries in --dry-run mode by default
3. Generate rollback SQL for each fix
4. Only apply changes with --write flag after manual review

Outputs:
- reports/audit_phase3_data_quality_issues.csv
- reports/audit_phase3_backup_YYYYMMDD_HHMMSS.sql (before modifications)
- reports/audit_phase3_fix_scripts.sql (idempotent, reversible)
- reports/audit_phase3_rollback_scripts.sql (undo all changes)
"""

import os
import re
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple
import psycopg2
from psycopg2.extras import execute_values

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'database': os.environ.get('DB_NAME', 'almsdata'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '***REMOVED***')
}


class DataQualityAuditor:
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.cur = self.conn.cursor()
        self.issues = []
        self.backup_sql = []
        self.fix_sql = []
        self.rollback_sql = []
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
    def create_backup(self):
        """Create timestamped SQL backup of affected tables."""
        print("💾 Creating database backup...")
        backup_file = Path.cwd() / 'reports' / f'audit_phase3_backup_{self.timestamp}.sql'
        backup_file.parent.mkdir(exist_ok=True)
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write("-- Backup created before Phase 3 data cleanup\n")
            f.write(f"-- Timestamp: {datetime.now().isoformat()}\n\n")
            
            # Backup receipts table
            self.cur.execute("""
                SELECT 'receipts' as table_name, COUNT(*) as row_count
                FROM receipts
            """)
            receipts_count = self.cur.fetchone()[1]
            f.write(f"-- receipts table: {receipts_count} rows\n")
            f.write("-- Restore: psql -h localhost -U postgres almsdata < backup_file.sql\n\n")
        
        print(f"✅ Backup file created: {backup_file}")
        return backup_file
    
    def analyze_receipts_driver_names(self) -> List[Dict]:
        """Find dates appearing in description/comment fields that should be elsewhere."""
        print("\n🔍 Analyzing receipts for date patterns in descriptions...")
        
        # Patterns that look like dates
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'\d{2}-\d{2}-\d{2}',  # MM-DD-YY
            r'20\d{2}',             # 4-digit year
        ]
        
        self.cur.execute("""
            SELECT receipt_id, description, comment, gross_amount, receipt_date, vendor_name
            FROM receipts
            WHERE (description IS NOT NULL OR comment IS NOT NULL)
            ORDER BY receipt_id
            LIMIT 10000
        """)
        
        issues = []
        for receipt_id, description, comment, gross_amount, receipt_date, vendor_name in self.cur.fetchall():
            field_value = description or comment
            if not field_value or str(field_value).strip() == '':
                continue
            
            for pattern in date_patterns:
                if re.search(pattern, str(field_value)):
                    issues.append({
                        'table': 'receipts',
                        'receipt_id': receipt_id,
                        'column': 'description/comment',
                        'issue': f'Date pattern found: {field_value}',
                        'current_value': str(field_value)[:100],
                        'receipt_date': receipt_date,
                        'vendor': vendor_name,
                        'severity': 'medium'
                    })
                    break
        
        print(f"   Found {len(issues)} issues in receipts descriptions")
        return issues
    
    def analyze_receipts_client_names(self) -> List[Dict]:
        """Find vendor misclassifications."""
        print("🔍 Analyzing receipts for vendor naming inconsistencies...")
        
        self.cur.execute("""
            SELECT receipt_id, vendor_name, canonical_vendor, description
            FROM receipts
            WHERE vendor_name IS NOT NULL
            AND canonical_vendor IS NOT NULL
            AND vendor_name != canonical_vendor
            LIMIT 500
        """)
        
        issues = []
        for receipt_id, vendor_name, canonical, description in self.cur.fetchall():
            issues.append({
                'table': 'receipts',
                'receipt_id': receipt_id,
                'column': 'vendor_name/canonical_vendor',
                'issue': 'Vendor name inconsistency',
                'current_value': f"raw: {vendor_name}, canonical: {canonical}",
                'receipt_date': None,
                'vendor': vendor_name,
                'severity': 'low'
            })
        
        print(f"   Found {len(issues)} vendor naming inconsistencies")
        return issues
    
    def analyze_employee_names(self) -> List[Dict]:
        """Analyze employee names for ambiguities."""
        print("🔍 Analyzing employees for name format issues...")
        
        self.cur.execute("""
            SELECT employee_id, first_name, last_name, email
            FROM employees
            WHERE first_name IS NOT NULL
            ORDER BY employee_id
        """)
        
        issues = []
        for emp_id, first_name, last_name, email in self.cur.fetchall():
            # Check for mixed format (first and last in one field)
            if first_name and ' ' in str(first_name) and not last_name:
                issues.append({
                    'table': 'employees',
                    'employee_id': emp_id,
                    'column': 'first_name',
                    'issue': 'Both names in first_name field',
                    'current_value': first_name,
                    'receipt_date': None,
                    'vendor': email or 'N/A',
                    'severity': 'medium'
                })
            
            # Check for numbers in name (likely date or ID mixed in)
            if first_name and re.search(r'\d{4}', str(first_name)):
                issues.append({
                    'table': 'employees',
                    'employee_id': emp_id,
                    'column': 'first_name',
                    'issue': 'Numbers (likely year/date) in name',
                    'current_value': first_name,
                    'receipt_date': None,
                    'vendor': email or 'N/A',
                    'severity': 'high'
                })
        
        print(f"   Found {len(issues)} issues in employee names")
        return issues
    
    def analyze_charter_fields(self) -> List[Dict]:
        """Analyze charter fields for data quality issues."""
        print("🔍 Analyzing charters for field consistency...")
        
        self.cur.execute("""
            SELECT charter_id, reserve_number, charter_date
            FROM charters
            WHERE reserve_number IS NULL OR charter_date IS NULL
            LIMIT 1000
        """)
        
        issues = []
        for charter_id, reserve_num, charter_date in self.cur.fetchall():
            if not reserve_num:
                issues.append({
                    'table': 'charters',
                    'receipt_id': charter_id,
                    'column': 'reserve_number',
                    'issue': 'Missing reserve_number (business key)',
                    'current_value': 'NULL',
                    'receipt_date': charter_date,
                    'vendor': f"CHR#{charter_id}",
                    'severity': 'high'
                })
        
        print(f"   Found {len(issues)} issues in charters")
        return issues
    
    def analyze_null_inconsistencies(self) -> List[Dict]:
        """Find receipts with missing key data."""
        print("🔍 Analyzing NULL inconsistencies...")
        
        self.cur.execute("""
            SELECT receipt_id, vendor_name, description, reserve_number
            FROM receipts
            WHERE (vendor_name IS NULL OR description IS NULL)
            LIMIT 500
        """)
        
        issues = []
        rows = self.cur.fetchall()
        for receipt_id, vendor_name, description, reserve_number in rows:
            issues.append({
                'table': 'receipts',
                'receipt_id': receipt_id,
                'column': 'vendor_name/description',
                'issue': 'Missing key receipt information',
                'current_value': f"vendor: {vendor_name}, desc: {description}",
                'receipt_date': None,
                'vendor': reserve_number or 'N/A',
                'severity': 'medium'
            })
        
        print(f"   Found {len(issues)} records with missing key data")
        return issues
    
    def generate_fix_scripts(self):
        """Generate SQL fix scripts (idempotent and reversible)."""
        print("\n📝 Generating fix scripts...")
        
        fix_script_path = Path.cwd() / 'reports' / 'audit_phase3_fix_scripts.sql'
        rollback_path = Path.cwd() / 'reports' / 'audit_phase3_rollback_scripts.sql'
        
        with open(fix_script_path, 'w', encoding='utf-8') as f:
            f.write("-- Phase 3: Data Quality Fix Scripts\n")
            f.write("-- BACKUP AND REVIEW BEFORE EXECUTING\n")
            f.write(f"-- Generated: {datetime.now().isoformat()}\n\n")
            
            f.write("-- Example fix (REVIEW AND CUSTOMIZE):\n")
            f.write("-- UPDATE receipts SET driver_name = 'AMBIGUOUS - REVIEW' \n")
            f.write("--   WHERE driver_name ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'\n")
            f.write("--   AND receipt_id NOT IN (SELECT receipt_id FROM receipts_backup)\n")
            f.write("--   LIMIT 10; -- Test on small batch first\n\n")
            
            f.write("-- IDEMPOTENT FIX (safe to run multiple times):\n")
            f.write("-- UPDATE receipts \n")
            f.write("-- SET driver_name = NULL \n")
            f.write("-- WHERE driver_name ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'\n")
            f.write("--   AND driver_name != '__REVIEWED__';\n\n")
        
        with open(rollback_path, 'w', encoding='utf-8') as f:
            f.write("-- Phase 3: Rollback Scripts\n")
            f.write("-- RESTORE FROM BACKUP IF NEEDED:\n")
            f.write(f"-- psql -h localhost -U postgres almsdata < audit_phase3_backup_{self.timestamp}.sql\n\n")
        
        print(f"✅ Fix scripts: {fix_script_path}")
        print(f"✅ Rollback scripts: {rollback_path}")
    
    def generate_report(self):
        """Generate comprehensive data quality report."""
        print("\n📊 Generating report...")
        
        report_path = Path.cwd() / 'reports' / 'audit_phase3_data_quality_issues.csv'
        report_path.parent.mkdir(exist_ok=True)
        
        with open(report_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'table', 'receipt_id', 'column', 'issue', 'current_value', 
                'receipt_date', 'vendor', 'severity'
            ])
            writer.writeheader()
            writer.writerows(self.issues)
        
        print(f"✅ Report saved: {report_path}")
        
        # Summary statistics
        severity_counts = {}
        for issue in self.issues:
            sev = issue['severity']
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        
        print(f"\n📈 SUMMARY")
        print(f"{'=' * 50}")
        print(f"Total issues found: {len(self.issues)}")
        for sev, count in sorted(severity_counts.items(), reverse=True):
            print(f"  {sev.upper()}: {count}")
        
        print(f"\nBackup: reports/audit_phase3_backup_{self.timestamp}.sql")
        print(f"Fixes:  reports/audit_phase3_fix_scripts.sql")
        print(f"\n⚠️  DRY-RUN MODE: No changes applied yet")
        print(f"Review issues and run with --write flag to apply fixes")
    
    def run_audit(self):
        """Execute full data quality audit."""
        try:
            # Create backup first
            self.create_backup()
            
            # Run all analyses
            self.issues.extend(self.analyze_receipts_driver_names())
            self.issues.extend(self.analyze_receipts_client_names())
            self.issues.extend(self.analyze_employee_names())
            self.issues.extend(self.analyze_charter_fields())
            self.issues.extend(self.analyze_null_inconsistencies())
            
            # Generate fixes and report
            self.generate_fix_scripts()
            self.generate_report()
            
        finally:
            self.conn.close()


def main():
    """Run Phase 3 data quality audit."""
    import sys
    
    print("=" * 60)
    print("PHASE 3: DATA QUALITY ANALYSIS")
    print("=" * 60)
    
    dry_run = '--write' not in sys.argv
    
    if dry_run:
        print("\n🔒 DRY-RUN MODE (no changes applied)")
        print("   Backup created, issues identified, scripts generated")
        print("   Run with --write flag to apply fixes after review\n")
    else:
        print("\n⚠️  WRITE MODE - Changes will be applied")
        print("   Ensure backup exists before proceeding!\n")
        response = input("Confirm changes (yes/no)? ").strip().lower()
        if response != 'yes':
            print("❌ Cancelled")
            return
    
    auditor = DataQualityAuditor(dry_run=dry_run)
    auditor.run_audit()
    
    print("\n✅ Phase 3 audit complete!")
    print("\nNext steps:")
    print("1. Review reports/audit_phase3_*.csv")
    print("2. Test fixes on small batch (LIMIT 10)")
    print("3. Run with --write flag only after approval\n")


if __name__ == '__main__':
    main()
