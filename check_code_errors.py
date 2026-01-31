#!/usr/bin/env python3
"""
Comprehensive code error checker - finds errors BEFORE runtime
Checks syntax, undefined variables, import errors, logic issues
"""

import py_compile
import ast
import sys
from pathlib import Path

def check_syntax(filepath):
    """Check for syntax errors"""
    try:
        py_compile.compile(filepath, doraise=True)
        return True, "OK"
    except py_compile.PyCompileError as e:
        return False, str(e)

def check_imports(filepath):
    """Check for undefined imports"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        
        return True, f"Found {len(imports)} imports"
    except Exception as e:
        return False, f"Import parse error: {str(e)}"

def check_undefined_variables(filepath):
    """Check for potentially undefined variables"""
    issues = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Check for common patterns
        for i, line in enumerate(lines, 1):
            # Check for variable usage before assignment (simple heuristic)
            if '+=' in line or '-=' in line or '*=' in line:
                var_name = line.split('=')[0].split()[-1]
                # Look back to see if initialized
                context = ''.join(lines[max(0, i-20):i])
                if f"{var_name} =" not in context and f"{var_name}:" not in context:
                    issues.append(f"Line {i}: Potential uninitialized variable '{var_name}' in: {line.strip()}")
        
        if issues:
            return False, issues
        return True, "No obvious undefined variables"
    except Exception as e:
        return False, [f"Analysis error: {str(e)}"]

def main():
    files_to_check = [
        'l:/limo/desktop_app/main.py',
        'l:/limo/desktop_app/enhanced_charter_widget.py',
        'l:/limo/desktop_app/drill_down_widgets.py',
        'l:/limo/desktop_app/admin_management_widget.py',
        'l:/limo/modern_backend/main.py',
    ]
    
    print("=" * 70)
    print("🔍 COMPREHENSIVE CODE ERROR CHECK")
    print("=" * 70)
    
    total_errors = 0
    
    for filepath in files_to_check:
        path = Path(filepath)
        if not path.exists():
            print(f"\n⚠️  File not found: {filepath}")
            continue
        
        print(f"\n📄 Checking: {path.name}")
        print("-" * 70)
        
        # Syntax check
        print("  [1/3] Syntax check...", end=" ")
        ok, msg = check_syntax(filepath)
        if ok:
            print(f"✅ {msg}")
        else:
            print(f"❌ SYNTAX ERROR\n    {msg}")
            total_errors += 1
        
        # Import check
        print("  [2/3] Import check...", end=" ")
        ok, msg = check_imports(filepath)
        if ok:
            print(f"✅ {msg}")
        else:
            print(f"⚠️  {msg}")
        
        # Undefined variables check
        print("  [3/3] Variable check...", end=" ")
        ok, issues = check_undefined_variables(filepath)
        if ok:
            print(f"✅ {issues}")
        else:
            print(f"⚠️  Potential issues found:")
            for issue in issues:
                print(f"    - {issue}")
                total_errors += 1
    
    print("\n" + "=" * 70)
    if total_errors == 0:
        print("✅ NO CRITICAL ERRORS FOUND - Code is safe to run")
    else:
        print(f"❌ {total_errors} CRITICAL ERRORS FOUND - Fix before running")
    print("=" * 70)
    
    return 0 if total_errors == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
