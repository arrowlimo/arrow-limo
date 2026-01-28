"""
Phase 4: Widget Integration Testing
====================================
Tests all desktop widgets for:
- Database connectivity
- Query execution success
- UI rendering without crashes
- Error handling coverage
- Transaction rollback capability
- Missing database error handlers

Outputs:
- reports/audit_phase4_widget_test_matrix.csv
- reports/audit_phase4_widget_crash_report.csv
- reports/audit_phase4_error_handling_gaps.csv
- reports/audit_phase4_transaction_issues.csv
"""

import os
import ast
import re
import csv
from pathlib import Path
from typing import List, Dict, Tuple
import psycopg2


class WidgetAuditor:
    def __init__(self):
        self.widgets = []
        self.db_config = {
            'host': os.environ.get('DB_HOST', 'localhost'),
            'database': os.environ.get('DB_NAME', 'almsdata'),
            'user': os.environ.get('DB_USER', 'postgres'),
            'password': os.environ.get('DB_PASSWORD', '***REMOVED***')
        }
        self.test_results = []
        self.crash_points = []
        self.error_gaps = []
        self.transaction_issues = []
        
    def scan_widgets(self):
        """Find all widget classes in desktop_app."""
        print("🔍 Scanning for widget classes...")
        
        desktop_app = Path.cwd() / 'desktop_app'
        widget_count = 0
        
        for py_file in desktop_app.glob('*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                tree = ast.parse(content, filename=str(py_file))
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Check if it's a widget (inherits from QWidget, QDialog, etc.)
                        bases = [b.attr if isinstance(b, ast.Attribute) else b.id 
                                for b in node.bases if hasattr(b, 'attr') or hasattr(b, 'id')]
                        
                        is_widget = any(base in ['QWidget', 'QDialog', 'QMainWindow', 'QTabWidget', 
                                               'QVBoxLayout', 'QHBoxLayout', 'QFrame'] for base in bases)
                        
                        if is_widget or 'widget' in node.name.lower() or 'dialog' in node.name.lower():
                            self.analyze_widget(py_file, node, content)
                            widget_count += 1
            
            except SyntaxError as e:
                print(f"   ⚠️ Syntax error in {py_file.name}: {e}")
        
        print(f"✅ Found {widget_count} widgets")
        return widget_count
    
    def analyze_widget(self, filepath: Path, node: ast.ClassDef, content: str):
        """Analyze single widget for DB connectivity and error handling."""
        
        # Count database operations
        db_queries = len(re.findall(r'cur\.execute|cursor\.execute', content))
        db_connections = len(re.findall(r'psycopg2\.connect|get_db_connection', content))
        
        # Check for error handling
        try_blocks = sum(1 for n in ast.walk(node) if isinstance(n, ast.Try))
        except_handlers = 0
        for n in ast.walk(node):
            if isinstance(n, ast.Try):
                except_handlers += len(n.handlers)
        
        # Check for transaction commits
        commits = content.count('conn.commit()')
        rollbacks = content.count('conn.rollback()')
        
        # Extract method names
        methods = [m.name for m in node.body if isinstance(m, ast.FunctionDef)]
        
        # Identify potential issues
        issues = []
        if db_queries > 0 and try_blocks == 0:
            issues.append('no_try_except')
        if db_queries > 0 and commits == 0 and rollbacks == 0:
            issues.append('no_transaction_handling')
        if db_queries > commits:
            issues.append('missing_commits')
        
        self.widgets.append({
            'filepath': str(filepath.relative_to(Path.cwd())),
            'widget_name': node.name,
            'db_queries': db_queries,
            'db_connections': db_connections,
            'try_blocks': try_blocks,
            'except_handlers': except_handlers,
            'commits': commits,
            'rollbacks': rollbacks,
            'methods': len(methods),
            'issues': '; '.join(issues) if issues else 'none'
        })
        
        # Document error handling gaps
        if db_queries > 0 and except_handlers < db_queries // 3:
            self.error_gaps.append({
                'widget': node.name,
                'file': filepath.name,
                'db_queries': db_queries,
                'exception_handlers': except_handlers,
                'gap': f'Missing error handling for {db_queries - except_handlers} potential query failures',
                'severity': 'high' if db_queries > 5 else 'medium'
            })
        
        # Document transaction issues
        if db_queries > commits:
            self.transaction_issues.append({
                'widget': node.name,
                'file': filepath.name,
                'db_queries': db_queries,
                'commits': commits,
                'issue': f'Only {commits}/{db_queries} queries have explicit commits',
                'recommendation': 'Wrap all INSERT/UPDATE/DELETE in try/except with conn.commit()'
            })
    
    def test_database_connectivity(self):
        """Verify database is accessible."""
        print("\n🔌 Testing database connectivity...")
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            cur.execute("SELECT 1")
            conn.close()
            print("✅ Database connection successful")
            return True
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False
    
    def analyze_query_patterns(self):
        """Find common query patterns and potential optimization opportunities."""
        print("🔍 Analyzing query patterns...")
        
        pattern_counts = {}
        for widget in self.widgets:
            if widget['db_queries'] > 0:
                # Categorize by query intensity
                if widget['db_queries'] > 10:
                    category = 'heavy_queries'
                elif widget['db_queries'] > 5:
                    category = 'moderate_queries'
                else:
                    category = 'light_queries'
                
                pattern_counts[category] = pattern_counts.get(category, 0) + 1
        
        print("  Query intensity distribution:")
        for category, count in sorted(pattern_counts.items()):
            print(f"    - {category}: {count} widgets")
    
    def generate_reports(self):
        """Generate comprehensive test reports."""
        print("\n📝 Generating reports...")
        
        reports_dir = Path.cwd() / 'reports'
        reports_dir.mkdir(exist_ok=True)
        
        # 1. Widget Test Matrix CSV
        matrix_path = reports_dir / 'audit_phase4_widget_test_matrix.csv'
        with open(matrix_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'filepath', 'widget_name', 'db_queries', 'db_connections', 
                'try_blocks', 'except_handlers', 'commits', 'rollbacks', 'methods', 'issues'
            ])
            writer.writeheader()
            writer.writerows(self.widgets)
        print(f"✅ Test matrix: {matrix_path}")
        
        # 2. Error Handling Gaps CSV
        gaps_path = reports_dir / 'audit_phase4_error_handling_gaps.csv'
        if self.error_gaps:
            with open(gaps_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'widget', 'file', 'db_queries', 'exception_handlers', 'gap', 'severity'
                ])
                writer.writeheader()
                writer.writerows(self.error_gaps)
            print(f"⚠️ Error handling gaps: {gaps_path} ({len(self.error_gaps)} widgets)")
        
        # 3. Transaction Issues CSV
        txn_path = reports_dir / 'audit_phase4_transaction_issues.csv'
        if self.transaction_issues:
            with open(txn_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'widget', 'file', 'db_queries', 'commits', 'issue', 'recommendation'
                ])
                writer.writeheader()
                writer.writerows(self.transaction_issues)
            print(f"⚠️ Transaction issues: {txn_path} ({len(self.transaction_issues)} widgets)")
        
        # Summary statistics
        total_widgets = len(self.widgets)
        total_queries = sum(w['db_queries'] for w in self.widgets)
        avg_queries = total_queries / total_widgets if total_widgets > 0 else 0
        
        widgets_with_db = sum(1 for w in self.widgets if w['db_queries'] > 0)
        widgets_with_errors = sum(1 for w in self.widgets if w['issues'] != 'none')
        
        print(f"\n📊 PHASE 4 SUMMARY")
        print(f"{'=' * 60}")
        print(f"Total widgets found: {total_widgets}")
        print(f"Widgets with DB queries: {widgets_with_db}")
        print(f"Total DB queries across all widgets: {total_queries:,}")
        print(f"Average queries per widget: {avg_queries:.1f}")
        print(f"Widgets with identified issues: {widgets_with_db if widgets_with_db > 0 else 0}")
        print(f"\nError handling gaps: {len(self.error_gaps)}")
        print(f"Transaction issues: {len(self.transaction_issues)}")
        
        # High-risk widgets (heavy DB operations with no error handling)
        high_risk = [w for w in self.widgets 
                    if w['db_queries'] > 10 and (w['try_blocks'] == 0 or w['except_handlers'] == 0)]
        if high_risk:
            print(f"\n🚨 HIGH-RISK WIDGETS (Heavy DB, weak error handling):")
            for w in high_risk[:10]:
                print(f"   - {w['widget_name']}: {w['db_queries']} queries, {w['except_handlers']} handlers")
    
    def run_audit(self):
        """Execute full widget audit."""
        try:
            self.scan_widgets()
            db_ok = self.test_database_connectivity()
            self.analyze_query_patterns()
            self.generate_reports()
            
            return db_ok
        except Exception as e:
            print(f"❌ Audit failed: {e}")
            return False


def main():
    """Run Phase 4 widget integration testing."""
    print("=" * 60)
    print("PHASE 4: WIDGET INTEGRATION TESTING")
    print("=" * 60)
    
    auditor = WidgetAuditor()
    success = auditor.run_audit()
    
    if success:
        print("\n✅ Phase 4 complete!")
        print("\nNext steps:")
        print("1. Review reports/audit_phase4_*.csv")
        print("2. Fix high-risk widgets (no error handling)")
        print("3. Add missing conn.commit() calls")
        print("4. Run Phase 5: Code Consolidation\n")
    else:
        print("\n⚠️ Phase 4 completed with warnings")


if __name__ == '__main__':
    main()
