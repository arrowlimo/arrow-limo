#!/usr/bin/env python3
"""
Desktop App Button & Query Validator
Checks for:
- Button click handlers referencing non-existent methods
- SQL syntax issues
- Incorrect database API calls
- Missing method definitions
"""

import re
from pathlib import Path
from collections import defaultdict

def extract_python_methods(py_file):
    """Extract all method definitions from a Python file"""
    try:
        with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except:
        return set()
    
    # Find all method definitions
    pattern = r'def\s+([a-z_]\w*)\s*\('
    methods = set(re.findall(pattern, content))
    return methods

def extract_button_handlers(py_file):
    """Extract button click connections and their handlers"""
    try:
        with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except:
        return []
    
    handlers = []
    
    # Pattern: button.clicked.connect(self.method_name)
    pattern = r'\.clicked\.connect\(self\.([a-z_]\w*)\)'
    matches = re.findall(pattern, content)
    handlers.extend(matches)
    
    # Pattern: combo.currentTextChanged.connect(self.method_name)
    pattern = r'\.currentTextChanged\.connect\(self\.([a-z_]\w*)\)'
    matches = re.findall(pattern, content)
    handlers.extend(matches)
    
    # Pattern: combo.currentIndexChanged.connect(self.method_name)
    pattern = r'\.currentIndexChanged\.connect\(self\.([a-z_]\w*)\)'
    matches = re.findall(pattern, content)
    handlers.extend(matches)
    
    # Pattern: table.doubleClicked.connect(self.method_name)
    pattern = r'\.doubleClicked\.connect\(self\.([a-z_]\w*)\)'
    matches = re.findall(pattern, content)
    handlers.extend(matches)
    
    # Pattern: input.textChanged.connect(self.method_name)
    pattern = r'\.textChanged\.connect\(self\.([a-z_]\w*)\)'
    matches = re.findall(pattern, content)
    handlers.extend(matches)
    
    return handlers

def extract_sql_errors(py_file):
    """Find potential SQL issues"""
    try:
        with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except:
        return []
    
    issues = []
    
    for i, line in enumerate(lines, 1):
        # Check for cursor.execute without proper error handling
        if 'cur.execute' in line and 'cur.execute' in ''.join(lines[max(0, i-5):i]):
            # Look for try/except after this line
            context = ''.join(lines[max(0, i-10):min(len(lines), i+10)])
            if 'try:' not in context or 'except' not in context:
                issues.append(('missing_error_handling', i, line.strip()))
        
        # Check for SQL injection vulnerabilities
        if 'f"""' in line or "f'''" in line:
            if '%s' not in line:
                # Might be f-string SQL without parameterization
                sql_match = re.search(r'f["\']+(SELECT|INSERT|UPDATE|DELETE)', line, re.IGNORECASE)
                if sql_match:
                    issues.append(('potential_sql_injection', i, line.strip()))
        
        # Check for incomplete queries
        if 'cur.execute' in line and '"""' not in line and "'''" not in line:
            if 'VALUES' in line or 'WHERE' in line:
                if not any(x in line for x in ['%s', '%d', '%f']):
                    issues.append(('no_parameters', i, line.strip()))
    
    return issues

def extract_db_calls(py_file):
    """Extract database method calls"""
    try:
        with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except:
        return set()
    
    # Find all db.XXX() calls
    pattern = r'db\.([a-z_]\w*)\('
    calls = set(re.findall(pattern, content))
    
    # Find all self.db.XXX() calls
    pattern = r'self\.db\.([a-z_]\w*)\('
    calls.update(re.findall(pattern, content))
    
    # Find all cur.XXX() calls
    pattern = r'cur\.([a-z_]\w*)\('
    calls.update(re.findall(pattern, content))
    
    return calls

def main():
    output_file = "l:\\limo\\reports\\desktop_app_buttons_queries_audit.txt"
    desktop_app = Path("l:\\limo\\desktop_app")
    py_files = list(desktop_app.glob("*.py"))
    
    missing_handlers = {}
    sql_issues = {}
    db_calls = defaultdict(set)
    
    print("Scanning desktop_app for button handlers and SQL issues...")
    
    for py_file in sorted(py_files):
        methods = extract_python_methods(py_file)
        handlers = extract_button_handlers(py_file)
        sql_errs = extract_sql_errors(py_file)
        db_method_calls = extract_db_calls(py_file)
        
        # Check for missing handlers
        missing = [h for h in handlers if h not in methods]
        if missing:
            missing_handlers[py_file.name] = missing
        
        if sql_errs:
            sql_issues[py_file.name] = sql_errs
        
        for call in db_method_calls:
            db_calls[call].add(py_file.name)
    
    # Generate report
    with open(output_file, 'w') as f:
        f.write("="*100 + "\n")
        f.write("DESKTOP APP BUTTON & QUERY AUDIT\n")
        f.write("="*100 + "\n\n")
        
        # Missing handlers
        f.write("SECTION 1: MISSING BUTTON HANDLERS\n")
        f.write("-"*100 + "\n")
        
        if missing_handlers:
            f.write(f"❌ Found {sum(len(v) for v in missing_handlers.values())} missing handlers:\n\n")
            for filename, handlers in sorted(missing_handlers.items()):
                f.write(f"{filename}:\n")
                for handler in sorted(set(handlers)):
                    f.write(f"  ❌ {handler}() - referenced but not defined\n")
                f.write("\n")
        else:
            f.write("✅ All button handlers are defined\n\n")
        
        # SQL issues
        f.write("\nSECTION 2: POTENTIAL SQL ISSUES\n")
        f.write("-"*100 + "\n")
        
        if sql_issues:
            f.write(f"⚠️ Found potential SQL issues:\n\n")
            for filename, issues in sorted(sql_issues.items()):
                f.write(f"{filename}:\n")
                for issue_type, line_no, code in issues[:5]:  # Show first 5
                    f.write(f"  Line {line_no}: {issue_type}\n")
                    f.write(f"    {code[:80]}...\n")
                f.write("\n")
        else:
            f.write("✅ No obvious SQL issues found\n\n")
        
        # Database API calls
        f.write("\nSECTION 3: DATABASE API CALLS SUMMARY\n")
        f.write("-"*100 + "\n")
        f.write("Valid database methods:\n")
        valid_methods = ['get_cursor', 'execute', 'fetchone', 'fetchall', 'commit', 'rollback', 
                        'close', 'connect', 'cursor', 'query']
        
        for call in sorted(db_calls.keys()):
            count = len(db_calls[call])
            is_valid = call in valid_methods
            status = "✅" if is_valid else "⚠️"
            f.write(f"  {status} {call}() - used in {count} files\n")
        
        f.write("\n" + "="*100 + "\n")
        f.write("SUMMARY\n")
        f.write("="*100 + "\n")
        f.write(f"Total files scanned: {len(py_files)}\n")
        f.write(f"Missing handlers: {sum(len(v) for v in missing_handlers.values())}\n")
        f.write(f"SQL issues found: {sum(len(v) for v in sql_issues.values())}\n")
        f.write(f"Unique DB API calls: {len(db_calls)}\n")
        
        if not missing_handlers and not sql_issues:
            f.write("\n✅ NO CRITICAL ISSUES FOUND\n")
    
    print(f"✅ Report saved to: {output_file}")
    
    # Print summary
    if missing_handlers:
        print(f"\n❌ Missing handlers found: {sum(len(v) for v in missing_handlers.values())}")
        for filename, handlers in list(missing_handlers.items())[:3]:
            print(f"  {filename}: {', '.join(handlers[:3])}")
    else:
        print("\n✅ All button handlers are defined")
    
    if sql_issues:
        print(f"\n⚠️ SQL issues found: {sum(len(v) for v in sql_issues.values())}")
    else:
        print("✅ No obvious SQL issues found")
    
    print(f"\n✅ Database API calls found: {len(db_calls)}")

if __name__ == '__main__':
    main()
