"""
Phase 1: Comprehensive Codebase Structure Audit
================================================
Scans all Python files for:
- File inventory with LOC counts
- Import analysis
- Function/class definitions
- Potential orphaned code
- Duplicate patterns
- Database query patterns

Outputs:
- reports/audit_phase1_file_inventory.csv
- reports/audit_phase1_import_graph.json
- reports/audit_phase1_orphaned_candidates.csv
- reports/audit_phase1_duplicate_patterns.csv
"""

import os
import ast
import json
import csv
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple
import re

# Database connection for reference queries
import psycopg2

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'database': os.environ.get('DB_NAME', 'almsdata'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '***REDACTED***')
}


class CodebaseAuditor:
    def __init__(self, root_dir: Path):
        self.root = root_dir
        self.files: List[Dict] = []
        self.imports: Dict[str, Set[str]] = defaultdict(set)
        self.definitions: Dict[str, List[str]] = defaultdict(list)
        self.callers: Dict[str, Set[str]] = defaultdict(set)
        self.db_queries: List[Dict] = []
        
    def scan_directory(self, directory: str):
        """Scan specific directory for Python files."""
        dir_path = self.root / directory
        if not dir_path.exists():
            print(f"⚠️ Directory not found: {directory}")
            return
            
        print(f"\n📂 Scanning {directory}...")
        for py_file in dir_path.rglob('*.py'):
            try:
                self.analyze_file(py_file)
            except Exception as e:
                print(f"  ❌ Error analyzing {py_file.name}: {e}")
    
    def analyze_file(self, filepath: Path):
        """Analyze single Python file."""
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Count lines
        lines = content.split('\n')
        loc = len(lines)
        code_lines = len([l for l in lines if l.strip() and not l.strip().startswith('#')])
        
        # Parse AST
        try:
            tree = ast.parse(content, filename=str(filepath))
        except SyntaxError as e:
            print(f"  ⚠️ Syntax error in {filepath.name}: {e}")
            self.files.append({
                'filepath': str(filepath.relative_to(self.root)),
                'loc': loc,
                'code_lines': 0,
                'functions': 0,
                'classes': 0,
                'imports': 0,
                'db_queries': 0,
                'status': 'syntax_error'
            })
            return
        
        # Extract imports
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
                    self.imports[str(filepath.relative_to(self.root))].add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
                    self.imports[str(filepath.relative_to(self.root))].add(node.module)
        
        # Extract function/class definitions
        functions = []
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(node.name)
                self.definitions[str(filepath.relative_to(self.root))].append(f"func:{node.name}")
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
                self.definitions[str(filepath.relative_to(self.root))].append(f"class:{node.name}")
        
        # Find database queries
        db_query_count = 0
        for pattern in [r'cur\.execute\(', r'cursor\.execute\(', r'SELECT\s+', r'INSERT\s+', r'UPDATE\s+', r'DELETE\s+']:
            db_query_count += len(re.findall(pattern, content, re.IGNORECASE))
        
        # Find SQL column references
        sql_columns = set()
        for match in re.finditer(r'(SELECT|FROM|WHERE|JOIN|UPDATE|SET|INSERT INTO)\s+[\w,\s.]+', content, re.IGNORECASE):
            sql_columns.update(re.findall(r'\b(\w+)\b', match.group()))
        
        self.files.append({
            'filepath': str(filepath.relative_to(self.root)),
            'loc': loc,
            'code_lines': code_lines,
            'functions': len(functions),
            'classes': len(classes),
            'imports': len(imports),
            'db_queries': db_query_count,
            'status': 'ok'
        })
        
        # Store query details for schema validation
        if db_query_count > 0:
            self.db_queries.append({
                'file': str(filepath.relative_to(self.root)),
                'query_count': db_query_count,
                'sql_tokens': list(sql_columns)
            })
    
    def find_orphaned_candidates(self) -> List[Dict]:
        """Identify files with no imports by other files."""
        imported_modules = set()
        for file, imports in self.imports.items():
            for imp in imports:
                # Extract module name from path
                module = imp.split('.')[0]
                imported_modules.add(module)
        
        orphans = []
        for file_info in self.files:
            filepath = file_info['filepath']
            # Extract filename without extension
            module_name = Path(filepath).stem
            
            # Check if this file is imported anywhere
            is_imported = any(module_name in imp for importer, imports in self.imports.items() 
                            for imp in imports if importer != filepath)
            
            # Check if it's a main entry point
            is_entry_point = (
                'main.py' in filepath or
                '__main__' in filepath or
                'test_' in filepath or
                filepath.startswith('scripts/') or
                filepath.startswith('migrations/')
            )
            
            # Orphan candidate: not imported, not entry point, no DB queries
            if not is_imported and not is_entry_point and file_info['db_queries'] == 0:
                orphans.append({
                    'filepath': filepath,
                    'loc': file_info['loc'],
                    'functions': file_info['functions'],
                    'classes': file_info['classes'],
                    'risk': 'low' if file_info['code_lines'] < 50 else 'medium'
                })
        
        return orphans
    
    def find_duplicate_patterns(self) -> List[Dict]:
        """Identify duplicate code patterns."""
        # Simple heuristic: files with same function counts and similar names
        duplicates = []
        function_map = defaultdict(list)
        
        for file_info in self.files:
            key = (file_info['functions'], file_info['classes'])
            function_map[key].append(file_info['filepath'])
        
        for (funcs, classes), files in function_map.items():
            if len(files) > 1 and funcs > 0:
                duplicates.append({
                    'pattern': f"{funcs} functions, {classes} classes",
                    'files': files,
                    'count': len(files)
                })
        
        return duplicates
    
    def generate_reports(self):
        """Generate all audit reports."""
        reports_dir = self.root / 'reports'
        reports_dir.mkdir(exist_ok=True)
        
        # 1. File Inventory CSV
        inventory_path = reports_dir / 'audit_phase1_file_inventory.csv'
        with open(inventory_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['filepath', 'loc', 'code_lines', 'functions', 'classes', 'imports', 'db_queries', 'status'])
            writer.writeheader()
            writer.writerows(self.files)
        print(f"\n✅ File inventory: {inventory_path}")
        
        # 2. Import Graph JSON
        import_graph_path = reports_dir / 'audit_phase1_import_graph.json'
        with open(import_graph_path, 'w', encoding='utf-8') as f:
            json.dump({k: list(v) for k, v in self.imports.items()}, f, indent=2)
        print(f"✅ Import graph: {import_graph_path}")
        
        # 3. Orphaned Candidates CSV
        orphans = self.find_orphaned_candidates()
        orphans_path = reports_dir / 'audit_phase1_orphaned_candidates.csv'
        with open(orphans_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['filepath', 'loc', 'functions', 'classes', 'risk'])
            writer.writeheader()
            writer.writerows(orphans)
        print(f"✅ Orphaned candidates: {orphans_path} ({len(orphans)} files)")
        
        # 4. Duplicate Patterns CSV
        duplicates = self.find_duplicate_patterns()
        duplicates_path = reports_dir / 'audit_phase1_duplicate_patterns.csv'
        with open(duplicates_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['pattern', 'files', 'count'])
            writer.writeheader()
            for dup in duplicates:
                writer.writerow({
                    'pattern': dup['pattern'],
                    'files': '; '.join(dup['files'][:5]),  # First 5 files
                    'count': dup['count']
                })
        print(f"✅ Duplicate patterns: {duplicates_path} ({len(duplicates)} patterns)")
        
        # 5. Database Query Inventory JSON
        db_queries_path = reports_dir / 'audit_phase1_db_queries.json'
        with open(db_queries_path, 'w', encoding='utf-8') as f:
            json.dump(self.db_queries, f, indent=2)
        print(f"✅ Database queries: {db_queries_path} ({len(self.db_queries)} files)")
        
        # Summary statistics
        total_loc = sum(f['loc'] for f in self.files)
        total_code = sum(f['code_lines'] for f in self.files)
        total_funcs = sum(f['functions'] for f in self.files)
        total_classes = sum(f['classes'] for f in self.files)
        total_db_files = len(self.db_queries)
        
        print(f"\n📊 SUMMARY STATISTICS")
        print(f"{'=' * 50}")
        print(f"Total files scanned: {len(self.files)}")
        print(f"Total lines of code: {total_loc:,}")
        print(f"Total code lines (non-comment): {total_code:,}")
        print(f"Total functions: {total_funcs:,}")
        print(f"Total classes: {total_classes:,}")
        print(f"Files with DB queries: {total_db_files}")
        print(f"Orphaned candidates: {len(orphans)}")
        print(f"Duplicate patterns: {len(duplicates)}")


def main():
    """Run Phase 1 audit."""
    print("=" * 60)
    print("PHASE 1: COMPREHENSIVE CODEBASE STRUCTURE AUDIT")
    print("=" * 60)
    
    root = Path(__file__).parent.parent
    auditor = CodebaseAuditor(root)
    
    # Scan key directories
    directories = [
        'desktop_app',
        'scripts',
        'modern_backend/app',
        'frontend/src'  # TypeScript - will skip if not .py
    ]
    
    for directory in directories:
        auditor.scan_directory(directory)
    
    # Generate all reports
    auditor.generate_reports()
    
    print("\n✅ Phase 1 audit complete!")
    print("\nNext steps:")
    print("1. Review reports/audit_phase1_*.csv files")
    print("2. Run Phase 2: python scripts/comprehensive_audit_phase2_schema.py")


if __name__ == '__main__':
    main()
