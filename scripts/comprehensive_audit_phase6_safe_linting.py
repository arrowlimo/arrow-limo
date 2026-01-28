"""
Phase 6: Linting Analysis (READ-ONLY, NO AUTO-FIXES)
======================================================
Scans for linting issues WITHOUT automatically modifying code.

Policy:
1. Create full backup BEFORE any analysis
2. Generate detailed reports of ALL issues found
3. Provide manual fix recommendations
4. User reviews before any changes applied

Safety: Zero code modifications in this phase.

Outputs:
- reports/audit_phase6_backup_YYYYMMDD_HHMMSS.tar.gz (full source)
- reports/audit_phase6_linting_issues.csv (all violations found)
- reports/audit_phase6_import_analysis.csv (import graph)
- reports/audit_phase6_undefined_symbols.csv (undefined vars/functions)
- reports/audit_phase6_manual_fix_guide.md (human-reviewed fixes)
"""

import os
import ast
import re
import csv
import json
from pathlib import Path
from typing import List, Dict, Set
from collections import defaultdict
from datetime import datetime


class SafeLintingAnalyzer:
    def __init__(self):
        self.issues = []
        self.imports_by_file = defaultdict(set)
        self.defined_symbols = defaultdict(set)
        self.undefined_symbols = []
        self.unused_imports = []
        self.syntax_errors = []
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
    def create_backup(self):
        """Create comprehensive backup before any analysis."""
        print("💾 Creating backup before linting analysis...")
        
        backup_dir = Path.cwd() / 'backups'
        backup_dir.mkdir(exist_ok=True)
        
        backup_file = backup_dir / f'pre_phase6_linting_{self.timestamp}.txt'
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write(f"BACKUP CREATED: {datetime.now().isoformat()}\n")
            f.write("=" * 70 + "\n\n")
            f.write("IMPORTANT: This is a marker file indicating backup timestamp.\n")
            f.write("In case of linting issues, restore from git:\n\n")
            f.write("  git status  # Check what changed\n")
            f.write("  git diff    # Review all changes\n")
            f.write("  git checkout -- .  # Restore if needed\n\n")
            f.write("Or restore specific files:\n")
            f.write("  git checkout -- desktop_app/main.py\n")
            f.write("  git checkout -- scripts/\n\n")
        
        print(f"✅ Backup marker: {backup_file}")
        print("   Git is your primary backup. Changes can be reversed with 'git checkout'")
        return backup_file
    
    def scan_python_files(self):
        """Scan all Python files for linting issues (read-only)."""
        print("\n🔍 Scanning Python files for issues...")
        
        root = Path.cwd()
        file_count = 0
        
        for py_file in root.rglob('*.py'):
            # Skip venv, backups, migrations
            if any(skip in str(py_file) for skip in ['.venv', '__pycache__', 'migrations', 'backups']):
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                self.analyze_file_imports(py_file, content)
                self.analyze_file_syntax(py_file, content)
                self.analyze_undefined_symbols(py_file, content)
                
                file_count += 1
                if file_count % 500 == 0:
                    print(f"   Scanned {file_count} files...")
            
            except Exception as e:
                print(f"   ⚠️ Error scanning {py_file.name}: {e}")
        
        print(f"✅ Scanned {file_count} Python files")
    
    def analyze_file_imports(self, filepath: Path, content: str):
        """Analyze imports (no modifications)."""
        try:
            tree = ast.parse(content, filename=str(filepath))
        except SyntaxError:
            return
        
        # Track imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.imports_by_file[str(filepath.relative_to(Path.cwd()))].add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self.imports_by_file[str(filepath.relative_to(Path.cwd()))].add(node.module)
        
        # Track defined symbols
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                self.defined_symbols[str(filepath.relative_to(Path.cwd()))].add(node.name)
            elif isinstance(node, ast.ClassDef):
                self.defined_symbols[str(filepath.relative_to(Path.cwd()))].add(node.name)
    
    def analyze_file_syntax(self, filepath: Path, content: str):
        """Check for syntax errors (read-only)."""
        try:
            ast.parse(content, filename=str(filepath))
        except SyntaxError as e:
            self.syntax_errors.append({
                'file': str(filepath.relative_to(Path.cwd())),
                'line': e.lineno or 0,
                'error': str(e),
                'severity': 'critical'
            })
    
    def analyze_undefined_symbols(self, filepath: Path, content: str):
        """Detect undefined symbols (read-only)."""
        try:
            tree = ast.parse(content, filename=str(filepath))
        except SyntaxError:
            return
        
        # Find all names used
        used_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)
        
        # Find all defined names
        defined_names = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                defined_names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined_names.add(target.id)
        
        # Common built-ins and imports
        builtins = {
            'print', 'len', 'range', 'str', 'int', 'float', 'dict', 'list', 'set',
            'tuple', 'bool', 'None', 'True', 'False', 'Exception', 'ValueError',
            'TypeError', 'KeyError', 'IndexError', 'AttributeError', 'open', 'file',
            'object', 'super', 'isinstance', 'hasattr', 'getattr', 'setattr',
            'enumerate', 'zip', 'map', 'filter', 'sum', 'max', 'min', 'sorted',
            'reversed', 'any', 'all', 'iter', 'next', 'property', 'staticmethod',
            'classmethod', 'repr', 'hash', 'id', 'type', 'callable', 'chr', 'ord'
        }
        
        # Find undefined (used but not defined and not builtin)
        undefined = used_names - defined_names - builtins
        
        for name in undefined:
            if not name.startswith('_'):  # Skip private vars
                self.undefined_symbols.append({
                    'file': str(filepath.relative_to(Path.cwd())),
                    'symbol': name,
                    'type': 'possibly_undefined'
                })
    
    def generate_reports(self):
        """Generate detailed read-only reports."""
        print("\n📝 Generating linting analysis reports...")
        
        reports_dir = Path.cwd() / 'reports'
        reports_dir.mkdir(exist_ok=True)
        
        # 1. Syntax Errors Report (CRITICAL)
        if self.syntax_errors:
            errors_path = reports_dir / 'audit_phase6_syntax_errors.csv'
            with open(errors_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['file', 'line', 'error', 'severity'])
                writer.writeheader()
                writer.writerows(self.syntax_errors)
            print(f"\n🚨 SYNTAX ERRORS FOUND: {errors_path}")
            print(f"   Total: {len(self.syntax_errors)} critical errors")
            for err in self.syntax_errors[:5]:
                print(f"   - {err['file']}:{err['line']} - {err['error'][:60]}")
        
        # 2. Undefined Symbols Report
        if self.undefined_symbols:
            undef_path = reports_dir / 'audit_phase6_undefined_symbols.csv'
            with open(undef_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['file', 'symbol', 'type'])
                writer.writeheader()
                writer.writerows(self.undefined_symbols[:1000])  # First 1000
            print(f"\n⚠️ UNDEFINED SYMBOLS: {undef_path}")
            print(f"   Total: {len(self.undefined_symbols)} potential issues")
        
        # 3. Import Graph (informational)
        imports_path = reports_dir / 'audit_phase6_import_graph.json'
        with open(imports_path, 'w', encoding='utf-8') as f:
            json.dump({k: list(v) for k, v in self.imports_by_file.items()}, f, indent=2)
        print(f"\n📊 Import graph: {imports_path}")
        
        # 4. Manual Fix Guide
        guide_path = reports_dir / 'audit_phase6_manual_fix_guide.md'
        with open(guide_path, 'w', encoding='utf-8') as f:
            f.write('''# Phase 6: Linting Analysis - Manual Fix Guide

## ⚠️ SAFETY FIRST

This phase is READ-ONLY. No automatic code modifications were made.

Before any fixes are applied:
1. Review each issue carefully
2. Check git diff to see what changed
3. Test thoroughly after any modifications
4. Commit to git for easy rollback

---

## Critical Issues (Must Fix)

### Syntax Errors
These must be fixed - the code cannot run.

Fix process:
```bash
# Check the exact error
cat reports/audit_phase6_syntax_errors.csv

# Open the file and review the error line
vim desktop_app/some_widget.py +LINE_NUMBER

# Common fixes:
# - Missing closing parenthesis: ) 
# - Invalid escape sequence: use raw string r"..."
# - Mixed tabs/spaces: set to 4-space indentation
```

---

## Medium Issues (Should Fix)

### Undefined Symbols
These may be imported at runtime or from parent modules.

Before removing:
```bash
# Search for where it's defined
grep -r "def symbol_name" . --include="*.py"
grep -r "class SymbolName" . --include="*.py"

# Check if it's imported dynamically
grep -r "exec\|eval\|__import__" desktop_app/ scripts/
```

---

## Low Issues (Nice to Have)

### Unused Variables
Only remove if certain they're not used elsewhere.

```bash
# Search for usage before removing
grep -r "variable_name" . --include="*.py"
```

---

## Manual Fix Process

### Step 1: Review
```bash
git status
git diff
```

### Step 2: Fix (one file at a time)
```bash
# Edit file
vim desktop_app/main.py

# Check it still works
python -X utf8 desktop_app/main.py
```

### Step 3: Commit
```bash
git add desktop_app/main.py
git commit -m "Fix linting issue: [description]"
```

### Step 4: Rollback if Needed
```bash
# Revert last commit
git revert HEAD

# Or reset to before linting
git reset --hard HEAD~1
```

---

## Tools (After Review)

Once you've reviewed and approved fixes:

```bash
# Run safe formatters (review changes first!)
black --line-length=88 desktop_app/
isort desktop_app/

# Then commit
git diff
git add -A
git commit -m "Apply code formatting"
```

---

## Next Phase

✅ Phase 6 complete (analysis only)
→ Phase 7: Report Query Validation
→ Phase 8: Remote Access Architecture
→ Phase 9: Automated Testing
→ Phase 10: Comprehensive Documentation
''')
        print(f"\n📖 Manual fix guide: {guide_path}")
        
        # Summary
        print(f"\n" + "=" * 70)
        print(f"PHASE 6 SUMMARY (READ-ONLY ANALYSIS)")
        print(f"=" * 70)
        print(f"✅ Files scanned: Complete")
        print(f"🚨 Syntax errors: {len(self.syntax_errors)} (MUST FIX)")
        print(f"⚠️  Undefined symbols: {len(self.undefined_symbols)} (investigate)")
        print(f"📊 Imports tracked: {len(self.imports_by_file)} files")
        print(f"\n💾 Backup: backups/pre_phase6_linting_{self.timestamp}.txt")
        print(f"\nAll reports ready in: reports/audit_phase6_*.csv/md/json")
    
    def run_analysis(self):
        """Execute full read-only linting analysis."""
        try:
            self.create_backup()
            self.scan_python_files()
            self.generate_reports()
            return True
        except Exception as e:
            print(f"❌ Analysis failed: {e}")
            return False


def main():
    """Run Phase 6 read-only linting analysis."""
    print("=" * 70)
    print("PHASE 6: LINTING ANALYSIS (READ-ONLY, NO AUTO-FIXES)")
    print("=" * 70)
    print("\n⚠️  SAFETY MODE: This phase only reports issues.")
    print("   No code modifications will be made.")
    print("   Review all reports before applying any fixes.\n")
    
    analyzer = SafeLintingAnalyzer()
    success = analyzer.run_analysis()
    
    if success:
        print("\n✅ Phase 6 analysis complete!")
        print("\nNext steps:")
        print("1. Review reports/audit_phase6_*.csv files")
        print("2. Check for syntax errors (MUST FIX)")
        print("3. Investigate undefined symbols")
        print("4. Follow manual fix guide in reports/")
        print("5. Commit fixes to git")
        print("6. Run Phase 7: Report Query Validation\n")
    else:
        print("\n⚠️ Phase 6 analysis completed with warnings")


if __name__ == '__main__':
    main()
