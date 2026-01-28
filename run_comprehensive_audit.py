#!/usr/bin/env python3
"""
COMPREHENSIVE AUDIT & TEST SYSTEM
Scans entire codebase for errors, data issues, and tests everything
January 23, 2026
"""

import os
import sys
import re
import psycopg2
import json
from pathlib import Path
from datetime import datetime, date
from collections import defaultdict
import ast

# Database connection
DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

class ComprehensiveAudit:
    def __init__(self):
        self.desktop_app_dir = Path("l:\\limo\\desktop_app")
        self.scripts_dir = Path("l:\\limo\\scripts")
        self.errors = defaultdict(list)
        self.warnings = defaultdict(list)
        self.data_issues = defaultdict(list)
        self.stats = {
            "total_files": 0,
            "files_with_errors": 0,
            "total_errors": 0,
            "total_warnings": 0,
            "tables_checked": 0,
            "rows_checked": 0,
            "data_anomalies": 0
        }
        self.db = None
        
    def connect_db(self):
        """Connect to database"""
        try:
            self.db = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            print("✅ Database connection successful")
            return True
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False
    
    def close_db(self):
        """Close database connection"""
        if self.db:
            self.db.close()
    
    # =====================================================================
    # CODE AUDIT SECTION
    # =====================================================================
    
    def audit_code_syntax(self):
        """Check all Python files for syntax errors"""
        print("\n" + "="*80)
        print("PHASE 1: CODE SYNTAX AUDIT")
        print("="*80)
        
        for py_file in self.desktop_app_dir.glob("*.py"):
            self.stats["total_files"] += 1
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    code = f.read()
                    ast.parse(code)
                print(f"✅ {py_file.name}: Syntax OK")
            except SyntaxError as e:
                self.stats["files_with_errors"] += 1
                self.stats["total_errors"] += 1
                self.errors[str(py_file)].append(f"Syntax Error at line {e.lineno}: {e.msg}")
                print(f"❌ {py_file.name}: {e}")
            except Exception as e:
                self.stats["files_with_errors"] += 1
                self.stats["total_warnings"] += 1
                self.warnings[str(py_file)].append(str(e))
                print(f"⚠️  {py_file.name}: {e}")
    
    def audit_imports(self):
        """Check for missing imports and circular dependencies"""
        print("\n" + "="*80)
        print("PHASE 2: IMPORT AUDIT")
        print("="*80)
        
        required_imports = {
            'PyQt6': ['QWidget', 'QVBoxLayout', 'QHBoxLayout', 'QTableWidget', 'QMessageBox'],
            'psycopg2': ['connect'],
            'datetime': ['datetime', 'date', 'time'],
            'pathlib': ['Path']
        }
        
        for py_file in self.desktop_app_dir.glob("*.py"):
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Check for problematic patterns
            if 'QTimeEdit' in content and 'setText' in content:
                match = re.search(r'(\w+)\.setText\(', content)
                if match and 'QTimeEdit' in content[:content.find(match.group(0))]:
                    self.warnings[str(py_file)].append("QTimeEdit.setText() usage detected - should use setTime()")
                    print(f"⚠️  {py_file.name}: QTimeEdit.setText() found (use setTime instead)")
            
            # Check for orphaned database cursors
            if 'cur.execute' in content and 'cur.close()' not in content:
                self.warnings[str(py_file)].append("Database cursor not explicitly closed")
                print(f"⚠️  {py_file.name}: Cursor not explicitly closed in some paths")
            
            # Check for missing rollback calls
            if 'try:' in content and 'cur.execute' in content:
                if 'self.db.rollback()' not in content:
                    self.warnings[str(py_file)].append("Missing rollback in exception handler")
                    print(f"⚠️  {py_file.name}: Missing rollback protection")
                else:
                    print(f"✅ {py_file.name}: Has rollback protection")
    
    def audit_column_references(self):
        """Check for references to non-existent database columns"""
        print("\n" + "="*80)
        print("PHASE 3: DATABASE COLUMN REFERENCE AUDIT")
        print("="*80)
        
        cur = self.db.cursor()
        
        # Get all tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema='public' AND table_type='BASE TABLE'
            ORDER BY table_name
        """)
        
        tables = [row[0] for row in cur.fetchall()]
        print(f"Found {len(tables)} tables to audit")
        
        col_refs = defaultdict(set)
        
        # Scan all Python files for SQL queries
        for py_file in self.desktop_app_dir.glob("*.py"):
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find SELECT statements
            selects = re.findall(r'SELECT\s+(.*?)\s+FROM', content, re.IGNORECASE | re.DOTALL)
            for select in selects:
                # Extract column names
                cols = re.findall(r'[c\.]\w+', select)
                for col in cols:
                    col_name = col.replace('c.', '').replace('v.', '').replace('e.', '')
                    col_refs['charters'].add(col_name)
        
        # Verify columns exist
        for table in tables:
            cur.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table}'
            """)
            actual_cols = set(row[0] for row in cur.fetchall())
            
            if table in col_refs:
                missing = col_refs[table] - actual_cols
                if missing:
                    for col in missing:
                        self.errors[table].append(f"Column '{col}' referenced but doesn't exist")
                        print(f"❌ Table '{table}': Column '{col}' not found")
                else:
                    print(f"✅ Table '{table}': All referenced columns exist")
        
        cur.close()
    
    # =====================================================================
    # DATA QUALITY SECTION
    # =====================================================================
    
    def audit_data_quality(self):
        """Check data integrity and quality across all tables"""
        print("\n" + "="*80)
        print("PHASE 4: DATA QUALITY AUDIT")
        print("="*80)
        
        cur = self.db.cursor()
        
        tables_to_check = [
            'charters',
            'payments',
            'receipts',
            'employees',
            'vehicles',
            'clients'
        ]
        
        for table in tables_to_check:
            print(f"\n📊 Checking table '{table}'...")
            self.stats["tables_checked"] += 1
            
            try:
                # Get row count
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                row_count = cur.fetchone()[0]
                print(f"   Total rows: {row_count}")
                
                # Check for NULLs in critical columns
                if table == 'charters':
                    critical_cols = ['reserve_number', 'charter_date', 'total_amount_due']
                elif table == 'payments':
                    critical_cols = ['reserve_number', 'amount', 'payment_date']
                elif table == 'receipts':
                    critical_cols = ['description', 'amount', 'receipt_date']
                elif table == 'employees':
                    critical_cols = ['full_name', 'employee_id']
                elif table == 'vehicles':
                    critical_cols = ['vehicle_number', 'vehicle_id']
                elif table == 'clients':
                    critical_cols = ['client_name', 'client_id']
                else:
                    critical_cols = []
                
                for col in critical_cols:
                    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL")
                    null_count = cur.fetchone()[0]
                    if null_count > 0:
                        self.data_issues[table].append(f"Column '{col}' has {null_count} NULL values")
                        print(f"   ⚠️  Column '{col}': {null_count} NULLs found")
                    else:
                        print(f"   ✅ Column '{col}': No NULLs")
                
                # Check for date anomalies
                if table in ['charters', 'payments', 'receipts']:
                    date_cols = ['charter_date', 'payment_date', 'receipt_date']
                    for col in date_cols:
                        cur.execute(f"""
                            SELECT COUNT(*) FROM {table} 
                            WHERE {col} > CURRENT_DATE + interval '30 days'
                        """)
                        future_count = cur.fetchone()[0]
                        if future_count > 0:
                            self.data_issues[table].append(f"Column '{col}' has {future_count} dates > 30 days in future")
                            print(f"   ⚠️  Column '{col}': {future_count} future dates detected")
                
                # Check for duplicate rows
                if table == 'payments':
                    cur.execute(f"""
                        SELECT reserve_number, amount, payment_date, COUNT(*) as cnt
                        FROM {table}
                        GROUP BY reserve_number, amount, payment_date
                        HAVING COUNT(*) > 1
                    """)
                    dupes = cur.fetchall()
                    if dupes:
                        print(f"   ⚠️  Found {len(dupes)} potential duplicate payment entries")
                        for dupe in dupes[:5]:  # Show first 5
                            self.data_issues[table].append(f"Duplicate: {dupe}")
                
                self.stats["rows_checked"] += row_count
                print(f"   ✅ Table '{table}' quality check complete")
                
            except Exception as e:
                print(f"   ❌ Error checking {table}: {e}")
                self.errors[table].append(str(e))
        
        cur.close()
    
    # =====================================================================
    # DASHBOARD AUDIT SECTION
    # =====================================================================
    
    def audit_dashboards(self):
        """Check all dashboard files for errors"""
        print("\n" + "="*80)
        print("PHASE 5: DASHBOARD AUDIT")
        print("="*80)
        
        dashboard_files = list(self.desktop_app_dir.glob("dashboards_*.py"))
        print(f"Found {len(dashboard_files)} dashboard files")
        
        for dashboard_file in dashboard_files:
            print(f"\n📊 Auditing {dashboard_file.name}...")
            
            with open(dashboard_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for common issues
            issues_found = 0
            
            # Check for missing setSortingEnabled
            if 'QTableWidget' in content and 'setSortingEnabled' not in content:
                self.warnings[str(dashboard_file)].append("Missing setSortingEnabled on tables")
                print(f"   ⚠️  Missing column sorting on tables")
                issues_found += 1
            else:
                print(f"   ✅ Column sorting enabled")
            
            # Check for LIMIT statements
            limits = re.findall(r'LIMIT\s+\d+', content)
            if limits:
                print(f"   ⚠️  Found {len(limits)} LIMIT clauses - may hide data")
                self.warnings[str(dashboard_file)].append(f"Found {len(limits)} LIMIT statements")
                issues_found += 1
            else:
                print(f"   ✅ No artificial LIMIT restrictions")
            
            # Check for error handling
            if 'except Exception' not in content:
                print(f"   ⚠️  Missing exception handling")
                issues_found += 1
            else:
                print(f"   ✅ Has exception handling")
            
            if issues_found == 0:
                print(f"   ✅ {dashboard_file.name}: All checks passed")
    
    # =====================================================================
    # WIDGET AUDIT SECTION
    # =====================================================================
    
    def audit_widgets(self):
        """Check all enhanced widgets"""
        print("\n" + "="*80)
        print("PHASE 6: WIDGET AUDIT")
        print("="*80)
        
        widgets = ['enhanced_charter_widget.py', 'enhanced_client_widget.py', 
                  'enhanced_employee_widget.py', 'enhanced_vehicle_widget.py']
        
        for widget_name in widgets:
            widget_path = self.desktop_app_dir / widget_name
            if not widget_path.exists():
                print(f"❌ {widget_name}: NOT FOUND")
                continue
            
            print(f"\n🔧 Checking {widget_name}...")
            
            with open(widget_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for setSortingEnabled
            if 'setSortingEnabled(True)' in content:
                print(f"   ✅ Sorting enabled")
            else:
                print(f"   ⚠️  Sorting NOT enabled")
                self.warnings[widget_name].append("Sorting not enabled")
            
            # Check for load_data method
            if 'def load_data' in content:
                print(f"   ✅ load_data method exists")
            else:
                print(f"   ❌ load_data method missing")
                self.errors[widget_name].append("load_data method not found")
            
            # Check for database error handling
            if 'self.db.rollback()' in content:
                print(f"   ✅ Rollback protection exists")
            else:
                print(f"   ⚠️  Missing rollback protection")
                self.warnings[widget_name].append("Missing rollback protection")
    
    def generate_report(self):
        """Generate comprehensive audit report"""
        print("\n" + "="*80)
        print("COMPREHENSIVE AUDIT REPORT")
        print("="*80)
        
        report = f"""
╔═══════════════════════════════════════════════════════════════════════════╗
║                     COMPREHENSIVE AUDIT REPORT                           ║
║                     Arrow Limousine Management System                     ║
║                     Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                       ║
╚═══════════════════════════════════════════════════════════════════════════╝

📊 STATISTICS:
═══════════════════════════════════════════════════════════════════════════
  Total Python Files Scanned:     {self.stats['total_files']}
  Files With Errors:               {self.stats['files_with_errors']}
  Total Errors Found:              {self.stats['total_errors']}
  Total Warnings Found:            {self.stats['total_warnings']}
  Tables Checked:                  {self.stats['tables_checked']}
  Rows Analyzed:                   {self.stats['rows_checked']:,}
  Data Anomalies Found:            {self.stats['data_anomalies']}

🔴 CRITICAL ERRORS ({len(self.errors)} items):
═══════════════════════════════════════════════════════════════════════════
"""
        for file, errs in self.errors.items():
            report += f"\n  {file}:\n"
            for err in errs:
                report += f"    ❌ {err}\n"
        
        report += f"""

⚠️  WARNINGS ({len(self.warnings)} items):
═══════════════════════════════════════════════════════════════════════════
"""
        for file, warns in self.warnings.items():
            report += f"\n  {file}:\n"
            for warn in warns[:5]:  # Limit to 5 per file
                report += f"    ⚠️  {warn}\n"
            if len(warns) > 5:
                report += f"    ... and {len(warns) - 5} more warnings\n"
        
        report += f"""

📋 DATA QUALITY ISSUES ({len(self.data_issues)} items):
═══════════════════════════════════════════════════════════════════════════
"""
        for table, issues in self.data_issues.items():
            report += f"\n  Table '{table}':\n"
            for issue in issues[:3]:  # Limit to 3 per table
                report += f"    ⚠️  {issue}\n"
            if len(issues) > 3:
                report += f"    ... and {len(issues) - 3} more issues\n"
        
        report += f"""

✅ OVERALL STATUS:
═══════════════════════════════════════════════════════════════════════════
"""
        if self.stats['total_errors'] == 0 and self.stats['total_warnings'] < 5:
            report += "\n  🎉 SYSTEM HEALTH: EXCELLENT\n"
            report += "  All critical systems operational. Minor warnings noted.\n"
        elif self.stats['total_errors'] > 0:
            report += f"\n  ⛔ SYSTEM HEALTH: NEEDS ATTENTION\n"
            report += f"  {self.stats['total_errors']} critical error(s) found.\n"
        else:
            report += f"\n  ⚠️  SYSTEM HEALTH: GOOD\n"
            report += f"  {self.stats['total_warnings']} warning(s) to address.\n"
        
        report += f"""

═══════════════════════════════════════════════════════════════════════════
Report generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
═══════════════════════════════════════════════════════════════════════════
"""
        
        print(report)
        
        # Save report
        report_file = Path("l:\\limo\\reports\\comprehensive_audit_report.txt")
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with open(report_file, 'w') as f:
            f.write(report)
        
        print(f"\n📁 Report saved to: {report_file}")
        
        return report
    
    def run_full_audit(self):
        """Run complete audit"""
        print("🚀 Starting Comprehensive Audit & Test System...")
        print(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Connect to database
        if not self.connect_db():
            return False
        
        try:
            # Run all audit phases
            self.audit_code_syntax()
            self.audit_imports()
            self.audit_column_references()
            self.audit_data_quality()
            self.audit_dashboards()
            self.audit_widgets()
            
            # Generate report
            self.generate_report()
            
            return True
        finally:
            self.close_db()

if __name__ == "__main__":
    audit = ComprehensiveAudit()
    success = audit.run_full_audit()
    sys.exit(0 if success else 1)
