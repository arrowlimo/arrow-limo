#!/usr/bin/env python3
"""
Comprehensive Data Integrity and Architecture Audit
Verifies all 404 tables, columns, and data quality
"""

import os
import sys
import psycopg2
from pathlib import Path
from collections import defaultdict
import json
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))


class DataAudit:
    def __init__(self):
        self.conn = None
        self.results = {
            'table_usage': {},
            'column_usage': {},
            'data_quality': {},
            'naming_issues': [],
            'summary': {}
        }
        self.codebase_path = Path("L:/limo")
        
    def connect(self):
        """Connect to database"""
        try:
            self.conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            print("✅ Database connected")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def get_all_tables(self):
        """Get all tables in schema"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = [row[0] for row in cur.fetchall()]
        cur.close()
        return tables
    
    def get_table_info(self, table_name):
        """Get row count, column count, and column details"""
        cur = self.conn.cursor()
        
        # Row count
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cur.fetchone()[0]
        
        # Columns
        cur.execute(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        cur.close()
        
        return {
            'row_count': row_count,
            'columns': columns
        }
    
    def check_table_usage_in_code(self, table_name):
        """Check if table is referenced in Python code"""
        files_referencing = []
        
        for py_file in self.codebase_path.rglob("*.py"):
            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')
                # Search for table name in queries and code
                if f"FROM {table_name}" in content.upper() or \
                   f"INSERT INTO {table_name}" in content.upper() or \
                   f"UPDATE {table_name}" in content.upper() or \
                   f"DELETE FROM {table_name}" in content.upper():
                    files_referencing.append(str(py_file.relative_to(self.codebase_path)))
            except:
                pass
        
        return files_referencing
    
    def sample_column_data(self, table_name, column_name, limit=5):
        """Get sample data from column"""
        try:
            cur = self.conn.cursor()
            cur.execute(f"""
                SELECT DISTINCT {column_name}
                FROM {table_name}
                WHERE {column_name} IS NOT NULL
                LIMIT {limit}
            """)
            samples = [row[0] for row in cur.fetchall()]
            cur.close()
            return samples
        except:
            return []
    
    def get_null_percentage(self, table_name, column_name, total_rows):
        """Get NULL percentage for column"""
        if total_rows == 0:
            return 0
        try:
            cur = self.conn.cursor()
            cur.execute(f"""
                SELECT COUNT(*)
                FROM {table_name}
                WHERE {column_name} IS NULL
            """)
            null_count = cur.fetchone()[0]
            cur.close()
            return round((null_count / total_rows) * 100, 2)
        except:
            return 0
    
    def detect_data_anomalies(self, table_name, column_name, data_type, samples):
        """Detect data anomalies"""
        anomalies = []
        
        # Check address columns
        if 'address' in column_name.lower() and samples:
            for sample in samples:
                sample_str = str(sample).lower()
                # Check if contains phone pattern
                if any(pattern in sample_str for pattern in ['(', ')', '-'] * 3):
                    anomalies.append("Contains phone number in address field")
                    break
        
        # Check phone columns
        if 'phone' in column_name.lower() and samples:
            for sample in samples:
                sample_str = str(sample).lower()
                if len(sample_str) > 20 or '@' in sample_str:
                    anomalies.append("Contains non-phone data (email or long text)")
                    break
        
        # Check date columns
        if 'date' in column_name.lower() and data_type == 'text' and samples:
            anomalies.append(f"Date field is TEXT not DATE type")
        
        # Check amount/currency columns
        if any(x in column_name.lower() for x in ['amount', 'price', 'cost']) and data_type == 'text':
            anomalies.append(f"Currency field is TEXT not DECIMAL/NUMERIC")
        
        return anomalies
    
    def check_column_usage_in_code(self, table_name, column_name):
        """Check if column is used in code"""
        files_using = []
        
        for py_file in self.codebase_path.rglob("*.py"):
            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')
                # Look for column references in SQL
                patterns = [
                    f"'{column_name}'",
                    f'"{column_name}"',
                    f".{column_name}",
                    f"[{column_name}]",
                ]
                if any(pattern in content for pattern in patterns):
                    files_using.append(str(py_file.relative_to(self.codebase_path)))
            except:
                pass
        
        return files_using
    
    def run_full_audit(self):
        """Run complete audit"""
        if not self.connect():
            return False
        
        print("\n" + "="*80)
        print("COMPREHENSIVE DATA AUDIT")
        print("="*80)
        
        tables = self.get_all_tables()
        print(f"\n📊 Found {len(tables)} tables")
        
        # Audit 1: Table Usage
        print("\n" + "-"*80)
        print("AUDIT 1: Table Usage Analysis")
        print("-"*80)
        
        used_tables = 0
        unused_tables = []
        
        for i, table in enumerate(tables):
            info = self.get_table_info(table)
            files_using = self.check_table_usage_in_code(table)
            
            self.results['table_usage'][table] = {
                'row_count': info['row_count'],
                'column_count': len(info['columns']),
                'used_by': files_using,
                'is_used': len(files_using) > 0
            }
            
            if files_using:
                used_tables += 1
            else:
                unused_tables.append((table, info['row_count']))
            
            # Progress indicator
            if (i + 1) % 50 == 0:
                print(f"  Processed {i+1}/{len(tables)} tables...")
        
        print(f"\n✅ Used tables: {used_tables}")
        print(f"⚠️  Unused tables: {len(unused_tables)}")
        if unused_tables:
            print("\nUnused tables (may be old/deprecated):")
            for table, rows in sorted(unused_tables)[:20]:  # Show first 20
                print(f"  - {table} ({rows} rows)")
        
        # Audit 2: Data Quality
        print("\n" + "-"*80)
        print("AUDIT 2: Data Quality & Type Validation")
        print("-"*80)
        
        data_issues = []
        
        for i, table in enumerate(tables):
            info = self.get_table_info(table)
            if info['row_count'] == 0:
                continue  # Skip empty tables
            
            for col_name, col_type, nullable in info['columns']:
                samples = self.sample_column_data(table, col_name)
                null_pct = self.get_null_percentage(table, col_name, info['row_count'])
                anomalies = self.detect_data_anomalies(table, col_name, col_type, samples)
                
                if anomalies or null_pct > 50:
                    data_issues.append({
                        'table': table,
                        'column': col_name,
                        'type': col_type,
                        'rows': info['row_count'],
                        'null_pct': null_pct,
                        'anomalies': anomalies,
                        'samples': samples
                    })
                
                self.results['data_quality'][f"{table}.{col_name}"] = {
                    'data_type': col_type,
                    'null_percentage': null_pct,
                    'anomalies': anomalies,
                    'samples': samples[:3]
                }
            
            if (i + 1) % 50 == 0:
                print(f"  Checked {i+1}/{len(tables)} tables...")
        
        print(f"\n⚠️  Data quality issues found: {len(data_issues)}")
        if data_issues:
            print("\nIssues (first 20):")
            for issue in data_issues[:20]:
                print(f"  - {issue['table']}.{issue['column']}: {issue['anomalies']}")
        
        # Audit 3: Column Usage
        print("\n" + "-"*80)
        print("AUDIT 3: Column Usage Analysis")
        print("-"*80)
        
        unused_columns = []
        
        for i, table in enumerate(tables):
            info = self.get_table_info(table)
            
            for col_name, col_type, nullable in info['columns']:
                files_using = self.check_column_usage_in_code(table, col_name)
                
                if not files_using:
                    unused_columns.append((table, col_name, col_type))
                
                self.results['column_usage'][f"{table}.{col_name}"] = {
                    'used_by': files_using,
                    'is_used': len(files_using) > 0
                }
            
            if (i + 1) % 50 == 0:
                print(f"  Checked {i+1}/{len(tables)} tables...")
        
        print(f"\n⚠️  Unused columns: {len(unused_columns)}")
        if unused_columns:
            print("\nUnused columns (first 30):")
            for table, col, col_type in sorted(unused_columns)[:30]:
                print(f"  - {table}.{col} ({col_type})")
        
        self.results['summary'] = {
            'total_tables': len(tables),
            'used_tables': used_tables,
            'unused_tables': len(unused_tables),
            'data_quality_issues': len(data_issues),
            'unused_columns': len(unused_columns),
            'scan_timestamp': datetime.now().isoformat()
        }
        
        return True
    
    def save_reports(self):
        """Save audit results to files"""
        reports_dir = Path("L:/limo/reports")
        reports_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. Summary report
        summary_path = reports_dir / f"audit_summary_{timestamp}.txt"
        with open(summary_path, 'w') as f:
            f.write("COMPREHENSIVE DATA AUDIT SUMMARY\n")
            f.write("="*80 + "\n\n")
            f.write(f"Scan Date: {self.results['summary']['scan_timestamp']}\n\n")
            f.write(f"Total Tables: {self.results['summary']['total_tables']}\n")
            f.write(f"Used Tables: {self.results['summary']['used_tables']}\n")
            f.write(f"Unused Tables: {self.results['summary']['unused_tables']}\n")
            f.write(f"Data Quality Issues: {self.results['summary']['data_quality_issues']}\n")
            f.write(f"Unused Columns: {self.results['summary']['unused_columns']}\n")
        
        # 2. Detailed JSON
        json_path = reports_dir / f"audit_details_{timestamp}.json"
        with open(json_path, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        # 3. CSV reports
        import csv
        
        # Table usage CSV
        table_csv = reports_dir / f"table_usage_{timestamp}.csv"
        with open(table_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Table', 'Rows', 'Columns', 'Used', 'Used By Files'])
            for table, info in sorted(self.results['table_usage'].items()):
                writer.writerow([
                    table,
                    info['row_count'],
                    info['column_count'],
                    'YES' if info['is_used'] else 'NO',
                    '; '.join(info['used_by'][:3])
                ])
        
        # Column usage CSV
        col_csv = reports_dir / f"column_usage_{timestamp}.csv"
        with open(col_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Table.Column', 'Used', 'Used By Files'])
            for col, info in sorted(self.results['column_usage'].items()):
                if not info['is_used']:
                    writer.writerow([
                        col,
                        'NO',
                        '; '.join(info['used_by'][:3])
                    ])
        
        print(f"\n✅ Reports saved:")
        print(f"   - {summary_path}")
        print(f"   - {json_path}")
        print(f"   - {table_csv}")
        print(f"   - {col_csv}")


def main():
    audit = DataAudit()
    if audit.run_full_audit():
        audit.save_reports()
    
    if audit.conn:
        audit.conn.close()


if __name__ == '__main__':
    main()
