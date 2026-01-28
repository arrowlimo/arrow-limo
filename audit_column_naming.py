#!/usr/bin/env python3
"""
Column Naming and Schema Consistency Audit
Identifies naming mismatches between database and code expectations
"""

import os
import re
from pathlib import Path
import json
from datetime import datetime
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")


class SchemaNamingAudit:
    def __init__(self):
        self.conn = None
        self.codebase_path = Path("L:/limo")
        self.results = {
            'naming_mismatches': [],
            'naming_recommendations': [],
            'code_expectations': {},
            'summary': {}
        }
    
    def connect(self):
        """Connect to database"""
        try:
            self.conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def get_code_column_expectations(self):
        """Extract column references from code"""
        expectations = {}  # table -> list of expected columns
        
        print("Scanning code for column references...")
        
        for py_file in self.codebase_path.rglob("*.py"):
            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')
                
                # Find SQL queries with SELECT
                select_pattern = r"SELECT\s+([^F]+?)\s+FROM\s+(\w+)"
                for match in re.finditer(select_pattern, content, re.IGNORECASE):
                    cols_str = match.group(1).strip()
                    table = match.group(2).lower()
                    
                    # Parse columns
                    cols = [c.strip().split('.')[-1].strip('`"') 
                           for c in cols_str.split(',')]
                    
                    if table not in expectations:
                        expectations[table] = set()
                    expectations[table].update(cols)
                
                # Find UPDATE statements
                update_pattern = r"UPDATE\s+(\w+)\s+SET\s+([^W]+?)(?:WHERE|$)"
                for match in re.finditer(update_pattern, content, re.IGNORECASE):
                    table = match.group(1).lower()
                    assignments = match.group(2).strip()
                    
                    cols = [c.split('=')[0].strip().split('.')[-1].strip('`"')
                           for c in assignments.split(',')]
                    
                    if table not in expectations:
                        expectations[table] = set()
                    expectations[table].update(cols)
                
                # Find INSERT statements
                insert_pattern = r"INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)"
                for match in re.finditer(insert_pattern, content, re.IGNORECASE):
                    table = match.group(1).lower()
                    cols_str = match.group(2)
                    
                    cols = [c.strip().strip('`"') for c in cols_str.split(',')]
                    
                    if table not in expectations:
                        expectations[table] = set()
                    expectations[table].update(cols)
            
            except:
                pass
        
        return expectations
    
    def get_actual_columns(self):
        """Get actual columns from database"""
        actual = {}
        
        cur = self.conn.cursor()
        cur.execute("""
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
        """)
        
        for table, col in cur.fetchall():
            if table not in actual:
                actual[table] = set()
            actual[table].add(col)
        
        cur.close()
        return actual
    
    def find_naming_mismatches(self, expectations, actual):
        """Find where code expects different names than database has"""
        mismatches = []
        
        print("\nFinding naming mismatches...")
        
        # Known aliases and common mismatches
        common_mismatches = {
            'phone': ['primary_phone', 'phone_number', 'contact_phone'],
            'email': ['email_address', 'contact_email'],
            'address': ['address_line1', 'street_address'],
            'total_price': ['total_amount_due', 'total_charge'],
            'amount': ['amount_paid', 'payment_amount'],
            'name': ['first_name', 'full_name', 'client_name'],
            'date': ['charter_date', 'created_date', 'updated_date'],
        }
        
        for table, expected_cols in expectations.items():
            if table not in actual:
                continue
            
            actual_cols = actual[table]
            
            for expected_col in expected_cols:
                if expected_col not in actual_cols:
                    # Check if it's a known mismatch
                    for pattern, aliases in common_mismatches.items():
                        if pattern in expected_col.lower():
                            for alias in aliases:
                                if alias in actual_cols:
                                    mismatches.append({
                                        'table': table,
                                        'code_expects': expected_col,
                                        'database_has': alias,
                                        'pattern': pattern,
                                        'severity': 'HIGH' if alias in ['primary_phone', 'address_line1', 'total_amount_due'] else 'MEDIUM'
                                    })
                                    break
        
        return mismatches
    
    def recommend_renames(self):
        """Recommend column renames for consistency"""
        recommendations = [
            {
                'table': 'All tables',
                'rename': 'id → uuid (if using UUIDs, for consistency)',
                'reason': 'Better naming for distributed systems'
            },
            {
                'table': 'charters',
                'rename': 'total_price → total_amount_due',
                'reason': 'Matches payment calculation logic in code'
            },
            {
                'table': 'clients',
                'rename': 'phone → primary_phone',
                'reason': 'Clarifies which phone number if multiple exist'
            },
            {
                'table': 'clients',
                'rename': 'address → address_line1',
                'reason': 'Supports multi-line addresses (line1, line2, city, etc)'
            },
            {
                'table': 'vehicles',
                'rename': 'plate_number → license_plate',
                'reason': 'Industry-standard terminology'
            },
            {
                'table': 'employees',
                'rename': 'wage_per_hour → hourly_rate',
                'reason': 'More standard terminology'
            },
        ]
        
        return recommendations
    
    def generate_report(self):
        """Generate naming consistency report"""
        print("\n" + "="*80)
        print("COLUMN NAMING AND SCHEMA CONSISTENCY AUDIT")
        print("="*80)
        
        expectations = self.get_code_column_expectations()
        actual = self.get_actual_columns()
        
        print(f"\n📊 Found {len(expectations)} tables referenced in code")
        print(f"📊 Database has {len(actual)} tables")
        
        mismatches = self.find_naming_mismatches(expectations, actual)
        recommendations = self.recommend_renames()
        
        print(f"\n⚠️  Found {len(mismatches)} naming mismatches")
        
        if mismatches:
            print("\nMismatches (HIGH priority first):")
            for mismatch in sorted(mismatches, key=lambda x: x['severity'], reverse=True)[:20]:
                print(f"\n  ⚠️  {mismatch['table']}")
                print(f"     Code expects: {mismatch['code_expects']}")
                print(f"     Database has: {mismatch['database_has']}")
                print(f"     Severity: {mismatch['severity']}")
        
        print(f"\n💡 {len(recommendations)} column rename recommendations")
        print("  (for clarity and consistency):\n")
        
        for rec in recommendations[:15]:
            print(f"  {rec['table']}:")
            print(f"    Rename: {rec['rename']}")
            print(f"    Reason: {rec['reason']}\n")
        
        self.results['naming_mismatches'] = mismatches
        self.results['naming_recommendations'] = recommendations
        self.results['code_expectations'] = {k: list(v) for k, v in expectations.items()}
        self.results['summary'] = {
            'total_mismatches': len(mismatches),
            'high_severity': len([m for m in mismatches if m['severity'] == 'HIGH']),
            'recommendations': len(recommendations),
            'scan_timestamp': datetime.now().isoformat()
        }
        
        # Save report
        reports_dir = Path("L:/limo/reports")
        reports_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = reports_dir / f"naming_audit_{timestamp}.json"
        
        with open(report_path, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"\n✅ Report saved: {report_path}")
    
    def run(self):
        """Run complete audit"""
        if not self.connect():
            return False
        
        self.generate_report()
        
        if self.conn:
            self.conn.close()
        
        return True


def main():
    audit = SchemaNamingAudit()
    audit.run()


if __name__ == '__main__':
    main()
