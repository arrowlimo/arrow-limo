#!/usr/bin/env python3
"""
Desktop App Code Audit Scanner
Finds common issues before runtime:
- QDate.toString() used in SQL parameters
- SELECT DISTINCT with ORDER BY mismatches
- Non-existent table/column references
- Type conversion issues
- Missing error handling
"""

import os
import re
import json
from pathlib import Path
from collections import defaultdict

# Database schema from reference
KNOWN_TABLES = {
    'charters', 'payments', 'receipts', 'employees', 'vehicles',
    'clients', 'banking_transactions', 'chart_of_accounts',
    'driver_payroll', 'general_ledger', 'vendor_invoices',
    'maintenance_records', 'vehicle_maintenance', 'employee_expenses',
    'personal_expenses', 'charter_charges', 'banking_accounts',
    'information_schema', 'pg_catalog'  # PostgreSQL system tables
}

KNOWN_COLUMNS = {
    'charters': {
        'charter_id', 'reserve_number', 'charter_date', 'pickup_time',
        'client_id', 'vehicle_id', 'employee_id', 'assigned_driver_id',
        'status', 'booking_status', 'total_amount_due', 'paid_amount',
        'balance', 'pickup_address', 'dropoff_address', 'destination',
        'customer_name', 'client_display_name', 'booking_notes',
        'calendar_color', 'calendar_sync_status', 'calendar_notes',
        'quote_expires_at', 'depart_yard_time', 'booking_type',
        'is_out_of_town', 'driver', 'vehicle', 'charter_data'
    },
    'payments': {'payment_id', 'reserve_number', 'charter_id', 'amount', 'payment_date', 'payment_method', 'notes'},
    'receipts': {'receipt_id', 'receipt_date', 'vendor_name', 'gross_amount', 'gst_amount', 'category', 'banking_transaction_id'},
    'employees': {'employee_id', 'first_name', 'last_name', 'full_name', 'employee_name', 'cell_phone', 'email', 'employment_status', 'is_chauffeur', 'hire_date'},
    'vehicles': {'vehicle_id', 'vehicle_number', 'make', 'model', 'year', 'license_plate', 'status', 'operational_status', 'vehicle_type'},
}

class CodeAuditor:
    def __init__(self):
        self.issues = defaultdict(list)
        self.stats = {'files_scanned': 0, 'total_issues': 0}
        
    def scan_file(self, filepath):
        """Scan a single Python file for issues"""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            print(f"❌ Could not read {filepath}: {e}")
            return
        
        rel_path = os.path.relpath(filepath, 'l:\\limo')
        self.stats['files_scanned'] += 1
        
        # Check for QDate.toString() in SQL parameters
        self._check_qdate_issues(rel_path, lines)
        
        # Check for SELECT DISTINCT issues
        self._check_select_distinct_issues(rel_path, lines)
        
        # Check for missing error handling on database calls
        self._check_missing_error_handling(rel_path, lines)
        
        # Check for type conversion issues
        self._check_type_conversion_issues(rel_path, lines)
        
        # Check for references to non-existent tables
        self._check_table_references(rel_path, lines)
        
    def _check_qdate_issues(self, filepath, lines):
        """Find QDate.toString() used directly in SQL execute"""
        for i, line in enumerate(lines, 1):
            # Pattern: execute(..., (...toString()...)
            if '.toString(' in line and 'execute' in lines[max(0, i-3):min(len(lines), i+3)]:
                # Look back to see if this is in a SQL execute call
                context_start = max(0, i-5)
                context = '\n'.join(lines[context_start:min(len(lines), i+1)])
                if 'execute' in context and '.toString(' in line:
                    self.issues[filepath].append({
                        'line': i,
                        'type': '⚠️  QDate.toString() in SQL',
                        'code': line.strip()[:80],
                        'fix': 'Use .toPyDate() instead of .toString("yyyy-MM-dd")'
                    })
                    self.stats['total_issues'] += 1
    
    def _check_select_distinct_issues(self, filepath, lines):
        """Find SELECT DISTINCT with ORDER BY columns not in SELECT"""
        for i, line in enumerate(lines, 1):
            if 'SELECT DISTINCT' in line.upper():
                # Collect the full query (may span multiple lines)
                query_lines = [line]
                j = i
                while j < len(lines) and ')' not in ''.join(query_lines):
                    query_lines.append(lines[j])
                    j += 1
                
                query_text = '\n'.join(query_lines)
                
                # Check if ORDER BY is present
                if 'ORDER BY' in query_text.upper():
                    # Extract SELECT columns (crude but effective)
                    select_match = re.search(r'SELECT DISTINCT\s+([^F]+?)\s+FROM', query_text, re.IGNORECASE)
                    order_match = re.search(r'ORDER BY\s+(.+?)(?:\)|\s*$)', query_text, re.IGNORECASE)
                    
                    if select_match and order_match:
                        select_cols = select_match.group(1)
                        order_cols = order_match.group(1)
                        
                        # Simple check: if CASE WHEN in ORDER BY but not in SELECT, flag it
                        if 'CASE WHEN' in order_cols.upper() and 'CASE WHEN' not in select_cols.upper():
                            self.issues[filepath].append({
                                'line': i,
                                'type': '🔴 SELECT DISTINCT with non-SELECT ORDER BY',
                                'code': query_text.split('\n')[0][:80],
                                'fix': 'Add ORDER BY columns to SELECT or use subquery'
                            })
                            self.stats['total_issues'] += 1
    
    def _check_missing_error_handling(self, filepath, lines):
        """Find SQL execute calls without try-except"""
        for i, line in enumerate(lines, 1):
            if '.execute(' in line and 'cur' in line:
                # Check if within try block
                context_start = max(0, i-10)
                context = '\n'.join(lines[context_start:i])
                
                # Count try/except in context
                try_count = context.count('try:')
                except_count = context.count('except')
                
                # Simple heuristic: if execute is not in a try, flag it
                # (Not foolproof but catches obvious cases)
                if 'def _load' in filepath or 'load_' in line:
                    if try_count == 0 and 'self.db.rollback()' not in context:
                        # Check if it's a SELECT (less critical)
                        if 'SELECT' not in '\n'.join(lines[max(0,i-3):i+1]).upper():
                            self.issues[filepath].append({
                                'line': i,
                                'type': '⚠️  Missing error handling on execute',
                                'code': line.strip()[:80],
                                'fix': 'Wrap in try-except and add db.rollback()'
                            })
                            self.stats['total_issues'] += 1
    
    def _check_type_conversion_issues(self, filepath, lines):
        """Find potential type conversion issues"""
        for i, line in enumerate(lines, 1):
            # Check for string date formats being used for DATE columns
            if 'charter_date' in line and '=' in line:
                if "'" in line or '"' in line:
                    # Check if it's being set to a formatted string
                    if any(fmt in line for fmt in ['%Y-%m-%d', 'yyyy-MM-dd', '%d/%m/%Y']):
                        if 'toPyDate' not in line and 'date.fromisoformat' not in line:
                            self.issues[filepath].append({
                                'line': i,
                                'type': '⚠️  String format for date column',
                                'code': line.strip()[:80],
                                'fix': 'Use Python date object instead of string'
                            })
                            self.stats['total_issues'] += 1
    
    def _check_table_references(self, filepath, lines):
        """Find references to tables that don't exist"""
        problem_tables = {'beverage_products', 'calendar_events', 'charter_events', 'vendor_accounts'}
        
        for i, line in enumerate(lines, 1):
            for table in problem_tables:
                if f"'{table}'" in line or f'"{table}"' in line or f' {table} ' in line or f' {table},' in line:
                    if 'FROM' in line.upper() or 'JOIN' in line.upper() or 'information_schema' not in line:
                        self.issues[filepath].append({
                            'line': i,
                            'type': f'🔴 Reference to non-existent table: {table}',
                            'code': line.strip()[:80],
                            'fix': f'Remove or replace {table} reference'
                        })
                        self.stats['total_issues'] += 1
    
    def generate_report(self):
        """Print audit report"""
        print("\n" + "="*80)
        print("🔍 DESKTOP APP CODE AUDIT REPORT")
        print("="*80)
        
        if not self.issues:
            print("✅ No issues found!")
            print(f"\nScanned {self.stats['files_scanned']} files")
            return
        
        # Sort by issue type
        issue_counts = defaultdict(int)
        
        for filepath in sorted(self.issues.keys()):
            for issue in self.issues[filepath]:
                issue_counts[issue['type']] += 1
        
        # Print summary
        print(f"\n📊 SUMMARY ({self.stats['total_issues']} issues in {len(self.issues)} files):\n")
        for issue_type in sorted(issue_counts.keys()):
            count = issue_counts[issue_type]
            print(f"  {issue_type}: {count}")
        
        # Print detailed issues
        print("\n" + "-"*80)
        print("DETAILED ISSUES:\n")
        
        for filepath in sorted(self.issues.keys()):
            print(f"\n📄 {filepath}")
            for issue in sorted(self.issues[filepath], key=lambda x: x['line']):
                print(f"  Line {issue['line']}: {issue['type']}")
                print(f"    Code: {issue['code']}")
                print(f"    Fix:  {issue['fix']}")
        
        print("\n" + "="*80)
        print(f"✅ Scanned {self.stats['files_scanned']} files, found {self.stats['total_issues']} issues")
        print("="*80 + "\n")
    
    def run(self, directory='l:\\limo\\desktop_app'):
        """Scan all Python files in directory"""
        py_files = list(Path(directory).glob('*.py'))
        print(f"🔍 Scanning {len(py_files)} files in {directory}...\n")
        
        for py_file in sorted(py_files):
            if py_file.name.startswith('_'):
                continue
            self.scan_file(str(py_file))
        
        self.generate_report()
        
        return self.stats['total_issues'] == 0

if __name__ == '__main__':
    auditor = CodeAuditor()
    success = auditor.run()
    exit(0 if success else 1)
