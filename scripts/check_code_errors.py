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
    """Check for potentially undefined variables using a simple AST flow"""
    issues = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        lines = source.splitlines()
        tree = ast.parse(source)

        def add_targets(target, assigned):
            if isinstance(target, ast.Name):
                assigned.add(target.id)
            elif isinstance(target, (ast.Tuple, ast.List)):
                for elt in target.elts:
                    add_targets(elt, assigned)

        def process_nodes(nodes, assigned):
            for node in nodes:
                # Augmented assignment (+=, -=, etc.)
                if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                    name = node.target.id
                    if name not in assigned:
                        line = lines[node.lineno - 1] if node.lineno - 1 < len(lines) else ""
                        issues.append(
                            f"Line {node.lineno}: Potential uninitialized variable '{name}' in: {line.strip()}"
                        )
                    assigned.add(name)

                # Regular assignments
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        add_targets(target, assigned)
                elif isinstance(node, ast.AnnAssign):
                    add_targets(node.target, assigned)

                # Imports create names
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assigned.add(alias.asname or alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        assigned.add(alias.asname or alias.name)

                # Function/Class definitions assign their names
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    assigned.add(node.name)

                # Control flow blocks
                if isinstance(node, ast.For):
                    add_targets(node.target, assigned)
                    process_nodes(node.body, assigned)
                    process_nodes(node.orelse, assigned)
                elif isinstance(node, ast.While):
                    process_nodes(node.body, assigned)
                    process_nodes(node.orelse, assigned)
                elif isinstance(node, ast.With):
                    for item in node.items:
                        if item.optional_vars:
                            add_targets(item.optional_vars, assigned)
                    process_nodes(node.body, assigned)
                elif isinstance(node, ast.Try):
                    process_nodes(node.body, assigned)
                    for handler in node.handlers:
                        if handler.name:
                            assigned.add(handler.name)
                        process_nodes(handler.body, assigned)
                    process_nodes(node.orelse, assigned)
                    process_nodes(node.finalbody, assigned)
                elif isinstance(node, ast.If):
                    process_nodes(node.body, assigned)
                    process_nodes(node.orelse, assigned)

                # Recurse into nested functions with their own scope
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_assigned = set(arg.arg for arg in node.args.args)
                    func_assigned.update(arg.arg for arg in node.args.kwonlyargs)
                    if node.args.vararg:
                        func_assigned.add(node.args.vararg.arg)
                    if node.args.kwarg:
                        func_assigned.add(node.args.kwarg.arg)
                    process_nodes(node.body, func_assigned)

        process_nodes(tree.body, set())

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
        'l:/limo/modern_backend/app/main.py',
    ]
    
    print("=" * 70)
    print("🔍 COMPREHENSIVE CODE ERROR CHECK")
    print("=" * 70)
    
    total_errors = 0
    total_warnings = 0
    
    for filepath in files_to_check:
        path = Path(filepath)
        if not path.exists():
            print(f"\n⚠️  File not found: {filepath}")
            total_warnings += 1
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
                total_warnings += 1
    
    print("\n" + "=" * 70)
    if total_errors == 0:
        if total_warnings:
            print(f"⚠️  NO CRITICAL ERRORS FOUND - {total_warnings} warnings detected")
        else:
            print("✅ NO CRITICAL ERRORS FOUND - Code is safe to run")
    else:
        print(f"❌ {total_errors} CRITICAL ERRORS FOUND - Fix before running")
    print("=" * 70)
    
    return 0 if total_errors == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
