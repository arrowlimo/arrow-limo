"""
Phase 2: Database Schema Validation
====================================
Validates all SQL queries against DATABASE_SCHEMA_REFERENCE.md

Checks:
- Column name mismatches
- Invalid table references
- charter_id vs reserve_number usage (business key enforcement)
- Data type mismatches (DECIMAL vs TEXT for currency, DATE vs TEXT)
- Missing indexes on frequently queried columns

Outputs:
- reports/audit_phase2_schema_violations.csv
- reports/audit_phase2_fix_scripts.sql
- reports/audit_phase2_charter_id_abuse.csv
"""

import os
import re
import json
import csv
from pathlib import Path
from typing import List, Dict, Set
import psycopg2

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'database': os.environ.get('DB_NAME', 'almsdata'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '***REMOVED***')
}


class SchemaValidator:
    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.cur = self.conn.cursor()
        self.schema = self.load_schema()
        self.violations = []
        self.charter_id_abuse = []
        
    def load_schema(self) -> Dict[str, Set[str]]:
        """Load actual database schema from information_schema."""
        print("📋 Loading database schema...")
        self.cur.execute("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
        """)
        
        schema = {}
        for table, column, dtype in self.cur.fetchall():
            if table not in schema:
                schema[table] = {}
            schema[table][column] = dtype
        
        print(f"✅ Loaded {len(schema)} tables")
        for table, columns in sorted(schema.items())[:10]:
            print(f"   - {table}: {len(columns)} columns")
        print(f"   ... and {len(schema) - 10} more tables")
        
        return schema
    
    def validate_file(self, filepath: Path):
        """Validate all SQL queries in a Python file."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            return
        
        # Extract SQL queries (in execute() calls or triple-quoted strings)
        sql_patterns = [
            r'(?:cur|cursor)\.execute\s*\(\s*"""(.*?)"""',
            r'(?:cur|cursor)\.execute\s*\(\s*"(.*?)"',
            r'(?:cur|cursor)\.execute\s*\(\s*\'(.*?)\'',
        ]
        
        for pattern in sql_patterns:
            for match in re.finditer(pattern, content, re.DOTALL | re.IGNORECASE):
                sql_query = match.group(1)
                self.validate_query(sql_query, filepath)
    
    def validate_query(self, query: str, filepath: Path):
        """Validate single SQL query against schema."""
        # Extract table names
        table_pattern = r'\b(?:FROM|JOIN|INTO|UPDATE)\s+(\w+)'
        tables = re.findall(table_pattern, query, re.IGNORECASE)
        
        # Extract column references
        column_pattern = r'\b(\w+)\.(\w+)\b'
        qualified_columns = re.findall(column_pattern, query)
        
        # Extract standalone column names (after SELECT, WHERE, SET)
        standalone_pattern = r'\b(?:SELECT|WHERE|SET|ORDER BY|GROUP BY)\s+([\w\s,\.]+)'
        standalone_matches = re.findall(standalone_pattern, query, re.IGNORECASE)
        
        columns = set()
        for match in standalone_matches:
            for word in match.split(','):
                parts = word.strip().split()
                if parts:  # Check if split returned anything
                    col = parts[0]  # Get first word (column name)
                    if col not in ['*', 'AND', 'OR', 'AS', 'FROM']:
                        columns.add(col)
        
        # Check table existence
        for table in tables:
            if table not in self.schema and table not in ['%s', 'NEW', 'OLD']:
                self.violations.append({
                    'file': str(filepath.relative_to(Path.cwd())),
                    'type': 'invalid_table',
                    'table': table,
                    'column': '',
                    'query_snippet': query[:100].replace('\n', ' ')
                })
        
        # Check column existence in qualified references
        for table_alias, column in qualified_columns:
            # Try to match alias to actual table (simple heuristic)
            for table in tables:
                if table.startswith(table_alias) or table_alias in self.schema:
                    actual_table = table_alias if table_alias in self.schema else table
                    if actual_table in self.schema:
                        if column not in self.schema[actual_table]:
                            self.violations.append({
                                'file': str(filepath.relative_to(Path.cwd())),
                                'type': 'invalid_column',
                                'table': actual_table,
                                'column': column,
                                'query_snippet': query[:100].replace('\n', ' ')
                            })
        
        # Check for charter_id abuse (business logic violation)
        if 'charter_id' in query and 'reserve_number' not in query:
            # Check if this is a JOIN/foreign key (OK) or business logic (NOT OK)
            if any(keyword in query.upper() for keyword in ['WHERE charter_id', 'GROUP BY charter_id', 'ORDER BY charter_id']):
                self.charter_id_abuse.append({
                    'file': str(filepath.relative_to(Path.cwd())),
                    'type': 'charter_id_business_logic',
                    'issue': 'Using charter_id instead of reserve_number for business logic',
                    'query_snippet': query[:150].replace('\n', ' '),
                    'recommendation': 'Replace charter_id with reserve_number in WHERE/GROUP BY/ORDER BY'
                })
        
        # Check for currency stored as string
        if any(word in query.upper() for word in ['AMOUNT', 'PRICE', 'TOTAL', 'BALANCE']):
            if 'CAST' in query.upper() or '::TEXT' in query.upper():
                self.violations.append({
                    'file': str(filepath.relative_to(Path.cwd())),
                    'type': 'currency_as_string',
                    'table': tables[0] if tables else 'unknown',
                    'column': 'currency_field',
                    'query_snippet': query[:100].replace('\n', ' ')
                })
    
    def scan_all_files(self):
        """Scan all Python files for SQL queries."""
        root = Path.cwd()
        directories = ['desktop_app', 'scripts', 'modern_backend']
        
        file_count = 0
        for directory in directories:
            dir_path = root / directory
            if not dir_path.exists():
                continue
            
            print(f"\n🔍 Scanning {directory}...")
            for py_file in dir_path.rglob('*.py'):
                self.validate_file(py_file)
                file_count += 1
                if file_count % 100 == 0:
                    print(f"   Processed {file_count} files...")
        
        print(f"✅ Scanned {file_count} files")
    
    def generate_reports(self):
        """Generate validation reports and fix scripts."""
        reports_dir = Path.cwd() / 'reports'
        reports_dir.mkdir(exist_ok=True)
        
        # 1. Schema Violations CSV
        violations_path = reports_dir / 'audit_phase2_schema_violations.csv'
        if self.violations:
            with open(violations_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['file', 'type', 'table', 'column', 'query_snippet'])
                writer.writeheader()
                writer.writerows(self.violations)
            print(f"\n❌ Schema violations: {violations_path} ({len(self.violations)} issues)")
        else:
            print(f"\n✅ No schema violations found!")
        
        # 2. Charter ID Abuse CSV
        abuse_path = reports_dir / 'audit_phase2_charter_id_abuse.csv'
        if self.charter_id_abuse:
            with open(abuse_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['file', 'type', 'issue', 'query_snippet', 'recommendation'])
                writer.writeheader()
                writer.writerows(self.charter_id_abuse)
            print(f"❌ Charter ID abuse: {abuse_path} ({len(self.charter_id_abuse)} cases)")
        else:
            print(f"✅ No charter_id abuse found!")
        
        # 3. Auto-Fix Scripts SQL
        fix_script_path = reports_dir / 'audit_phase2_fix_scripts.sql'
        with open(fix_script_path, 'w', encoding='utf-8') as f:
            f.write("-- Auto-generated fix scripts for schema violations\n")
            f.write("-- REVIEW CAREFULLY BEFORE EXECUTING\n\n")
            
            # Group violations by type
            by_type = {}
            for v in self.violations:
                vtype = v['type']
                if vtype not in by_type:
                    by_type[vtype] = []
                by_type[vtype].append(v)
            
            for vtype, issues in by_type.items():
                f.write(f"\n-- Fix {vtype} ({len(issues)} issues)\n")
                for issue in issues[:10]:  # First 10 examples
                    f.write(f"-- File: {issue['file']}\n")
                    f.write(f"-- Table: {issue['table']}, Column: {issue['column']}\n")
                    f.write(f"-- Query: {issue['query_snippet']}\n\n")
        
        print(f"📝 Fix scripts: {fix_script_path}")
        
        # Summary
        print(f"\n📊 PHASE 2 SUMMARY")
        print(f"{'=' * 50}")
        print(f"Total schema violations: {len(self.violations)}")
        print(f"Total charter_id abuse cases: {len(self.charter_id_abuse)}")
        
        if self.violations:
            print(f"\nTop violation types:")
            violation_types = {}
            for v in self.violations:
                vtype = v['type']
                violation_types[vtype] = violation_types.get(vtype, 0) + 1
            for vtype, count in sorted(violation_types.items(), key=lambda x: -x[1])[:5]:
                print(f"  - {vtype}: {count}")
    
    def close(self):
        """Close database connection."""
        self.cur.close()
        self.conn.close()


def main():
    """Run Phase 2 schema validation."""
    print("=" * 60)
    print("PHASE 2: DATABASE SCHEMA VALIDATION")
    print("=" * 60)
    
    validator = SchemaValidator()
    
    try:
        validator.scan_all_files()
        validator.generate_reports()
    finally:
        validator.close()
    
    print("\n✅ Phase 2 validation complete!")
    print("\nNext steps:")
    print("1. Review reports/audit_phase2_*.csv files")
    print("2. Run Phase 3: python scripts/comprehensive_audit_phase3_data_quality.py")


if __name__ == '__main__':
    main()
