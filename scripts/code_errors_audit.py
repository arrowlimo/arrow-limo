"""
Code Errors Audit - Find syntax errors, missing imports, incorrect SQL
"""

import os
import re
import ast
from pathlib import Path
from collections import defaultdict

print("=" * 80)
print("CODE ERRORS AUDIT - SYNTAX & SQL VALIDATION")
print("=" * 80)

errors = []
warnings = []
info = []

# Scan all Python files
code_dirs = ['desktop_app', 'scripts', 'modern_backend']
python_files = []

for code_dir in code_dirs:
    dir_path = Path(f'l:/limo/{code_dir}')
    if dir_path.exists():
        python_files.extend(dir_path.glob('**/*.py'))

print(f"\n📁 Scanning {len(python_files)} Python files...\n")

# Check 1: Syntax errors via AST parsing
print("[1/7] Checking for Python syntax errors...")
syntax_errors = []
for file_path in python_files:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            try:
                ast.parse(content)
            except SyntaxError as e:
                syntax_errors.append({
                    'file': str(file_path),
                    'line': e.lineno,
                    'error': str(e.msg),
                    'text': e.text
                })
    except Exception as e:
        errors.append(f"   Could not read {file_path}: {e}")

print(f"   Found {len(syntax_errors)} syntax errors")

# Check 2: Common Qt typos
print("[2/7] Checking for common Qt typos...")
qt_typos = []
qt_error_patterns = [
    (r'QFont\.Worth', 'QFont.Weight', 'QFont typo'),
    (r'\.setSelectionMode\(.*Multi', 'SingleSelection', 'Multi-selection where single expected'),
    (r'cur\.execute.*\n.*cur\.close\(\)', 'Missing conn.commit()', 'Database transaction not committed'),
]

for file_path in python_files:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            for pattern, suggestion, desc in qt_error_patterns:
                matches = list(re.finditer(pattern, content, re.MULTILINE | re.IGNORECASE))
                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    qt_typos.append({
                        'file': str(file_path),
                        'line': line_num,
                        'issue': desc,
                        'suggestion': suggestion
                    })
    except:
        pass

print(f"   Found {len(qt_typos)} Qt-related issues")

# Check 3: Missing conn.commit() after INSERT/UPDATE/DELETE
print("[3/7] Checking for missing database commits...")
missing_commits = []

for file_path in python_files:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                # Look for INSERT/UPDATE/DELETE
                if re.search(r'cur\.execute.*\b(INSERT|UPDATE|DELETE)\b', line, re.IGNORECASE):
                    # Check next 10 lines for commit()
                    has_commit = False
                    for j in range(i, min(i + 10, len(lines))):
                        if 'commit()' in lines[j]:
                            has_commit = True
                            break
                    if not has_commit:
                        missing_commits.append({
                            'file': str(file_path),
                            'line': i + 1,
                            'query_type': re.search(r'\b(INSERT|UPDATE|DELETE)\b', line, re.IGNORECASE).group(1),
                            'snippet': line.strip()[:80]
                        })
    except:
        pass

print(f"   Found {len(missing_commits)} potential missing commits")

# Check 4: References to non-existent columns
print("[4/7] Checking for references to non-existent columns...")
known_wrong_columns = {
    'total_price': 'total_amount_due',
    'charter_number': 'reserve_number',
    'payment_date': 'payment_datetime or charter date',
}

column_errors = []
for file_path in python_files:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            for line_num, line in enumerate(content.split('\n'), 1):
                for wrong, correct in known_wrong_columns.items():
                    if wrong in line and ('SELECT' in line or 'FROM' in line or 'WHERE' in line):
                        column_errors.append({
                            'file': str(file_path),
                            'line': line_num,
                            'wrong_column': wrong,
                            'correct_column': correct,
                            'snippet': line.strip()[:100]
                        })
    except:
        pass

print(f"   Found {len(column_errors)} column name errors")

# Check 5: charter_id vs reserve_number usage
print("[5/7] Checking for charter_id vs reserve_number confusion...")
charter_id_issues = []

for file_path in python_files:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Look for payments joined by charter_id
            if 'payments' in content:
                for line_num, line in enumerate(content.split('\n'), 1):
                    if 'charter_id' in line.lower() and 'payment' in line.lower():
                        if 'reserve_number' not in line.lower():
                            charter_id_issues.append({
                                'file': str(file_path),
                                'line': line_num,
                                'issue': 'Using charter_id instead of reserve_number for payments',
                                'snippet': line.strip()[:100]
                            })
    except:
        pass

print(f"   Found {len(charter_id_issues)} charter_id/reserve_number issues")

# Check 6: Missing error handling
print("[6/7] Checking for missing error handling...")
missing_try_catch = []

for file_path in python_files:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                # Database operations without try/except
                if 'cur.execute' in line or 'conn.cursor()' in line:
                    # Look backwards for try:
                    has_try = False
                    for j in range(max(0, i - 15), i):
                        if re.match(r'\s*try:', lines[j]):
                            has_try = True
                            break
                    if not has_try and 'try:' not in line:
                        missing_try_catch.append({
                            'file': str(file_path),
                            'line': i + 1,
                            'issue': 'Database operation without try/except',
                            'snippet': line.strip()[:80]
                        })
    except:
        pass

print(f"   Found {len(missing_try_catch)} potential missing error handlers")

# Check 7: Unused imports and dead code
print("[7/7] Checking for obvious dead code...")
dead_code = []

# Simple check: functions defined but never called
for file_path in python_files:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Find all function definitions
            func_defs = re.findall(r'def\s+([a-z_]+)\s*\(', content, re.IGNORECASE)
            for func in set(func_defs):
                # Count how many times it appears
                count = content.count(func)
                if count == 1:  # Only the definition
                    # Find line number
                    match = re.search(rf'def\s+{func}\s*\(', content)
                    if match:
                        line_num = content[:match.start()].count('\n') + 1
                        dead_code.append({
                            'file': str(file_path),
                            'line': line_num,
                            'function': func,
                            'issue': 'Function defined but never called'
                        })
    except:
        pass

print(f"   Found {len(dead_code)} potentially unused functions")

# Generate Report
print("\n" + "=" * 80)
print("GENERATING REPORT...")
print("=" * 80)

report = f"""# CODE ERRORS AUDIT REPORT
Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## EXECUTIVE SUMMARY
- Files Scanned: {len(python_files)}
- Syntax Errors: {len(syntax_errors)}
- Qt Typos/Issues: {len(qt_typos)}
- Missing Commits: {len(missing_commits)}
- Column Name Errors: {len(column_errors)}
- charter_id vs reserve_number Issues: {len(charter_id_issues)}
- Missing Error Handling: {len(missing_try_catch)}
- Potentially Dead Functions: {len(dead_code)}

---

## 1. SYNTAX ERRORS (CRITICAL)

"""

if syntax_errors:
    for i, err in enumerate(syntax_errors, 1):
        report += f"""
### {i}. {err['file']} (line {err['line']})
**Error:** {err['error']}
**Code:** `{err['text']}`

"""
else:
    report += "✅ No syntax errors found\n"

report += """
---

## 2. QT FRAMEWORK ISSUES

"""

if qt_typos:
    # Group by file
    by_file = defaultdict(list)
    for issue in qt_typos:
        by_file[issue['file']].append(issue)
    
    for file, issues in sorted(by_file.items())[:20]:
        report += f"\n### {file}\n"
        for issue in issues:
            report += f"- Line {issue['line']}: {issue['issue']}\n"
            report += f"  **Fix:** {issue['suggestion']}\n"
else:
    report += "✅ No Qt issues found\n"

report += """
---

## 3. MISSING DATABASE COMMITS (HIGH PRIORITY)

"""

if missing_commits:
    # Group by file
    by_file = defaultdict(list)
    for issue in missing_commits:
        by_file[issue['file']].append(issue)
    
    for file, issues in sorted(by_file.items())[:15]:
        report += f"\n### {file}\n"
        for issue in issues:
            report += f"- Line {issue['line']}: {issue['query_type']} without commit()\n"
            report += f"  `{issue['snippet']}`\n"
else:
    report += "✅ All database modifications properly committed\n"

report += """
---

## 4. COLUMN NAME ERRORS

"""

if column_errors:
    # Group by wrong column
    by_column = defaultdict(list)
    for err in column_errors:
        by_column[err['wrong_column']].append(err)
    
    for col, issues in sorted(by_column.items()):
        report += f"\n### Using '{col}' instead of '{issues[0]['correct_column']}'\n"
        report += f"**Occurrences:** {len(issues)}\n\n"
        for issue in issues[:5]:
            report += f"- {issue['file']} (line {issue['line']})\n"
            report += f"  `{issue['snippet']}`\n"
else:
    report += "✅ No known column name errors found\n"

report += """
---

## 5. CHARTER_ID vs RESERVE_NUMBER ISSUES

**CRITICAL:** Payments MUST use reserve_number as business key, NOT charter_id.

"""

if charter_id_issues:
    # Group by file
    by_file = defaultdict(list)
    for issue in charter_id_issues:
        by_file[issue['file']].append(issue)
    
    for file, issues in sorted(by_file.items())[:10]:
        report += f"\n### {file}\n"
        for issue in issues[:5]:
            report += f"- Line {issue['line']}: {issue['issue']}\n"
            report += f"  `{issue['snippet']}`\n"
else:
    report += "✅ All code properly uses reserve_number for payments\n"

report += """
---

## 6. MISSING ERROR HANDLING

"""

if missing_try_catch:
    report += f"**Total:** {len(missing_try_catch)} database operations without try/except\n\n"
    # Show first 20
    for i, issue in enumerate(missing_try_catch[:20], 1):
        report += f"{i}. {issue['file']} (line {issue['line']})\n"
        report += f"   `{issue['snippet']}`\n\n"
else:
    report += "✅ All database operations properly wrapped in error handling\n"

report += """
---

## 7. POTENTIALLY DEAD CODE

"""

if dead_code:
    report += f"**Total:** {len(dead_code)} functions defined but never called\n\n"
    # Group by file
    by_file = defaultdict(list)
    for dc in dead_code:
        by_file[dc['file']].append(dc)
    
    for file, funcs in sorted(by_file.items())[:10]:
        report += f"\n### {file}\n"
        for func in funcs[:5]:
            report += f"- Line {func['line']}: `{func['function']}()`\n"
else:
    report += "✅ No obviously dead functions found\n"

report += """
---

## RECOMMENDATIONS

### Immediate Actions
1. Fix all syntax errors
2. Add missing conn.commit() calls
3. Replace charter_id with reserve_number in payment queries
4. Fix column name errors (total_price → total_amount_due)
5. Add try/except around database operations

### Code Quality Improvements
1. Remove dead/unused functions
2. Standardize error handling patterns
3. Add type hints to function signatures
4. Create reusable database helper functions
5. Add unit tests for critical business logic

---

**End of Code Errors Audit**
"""

# Save report
output_file = 'l:/limo/reports/CODE_ERRORS_AUDIT_REPORT.md'
os.makedirs(os.path.dirname(output_file), exist_ok=True)
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(report)

print(f"\n✅ Report saved to: {output_file}")
print("\n📊 SUMMARY:")
print(f"   🔴 Syntax Errors: {len(syntax_errors)}")
print(f"   🟠 Qt Issues: {len(qt_typos)}")
print(f"   🟡 Missing Commits: {len(missing_commits)}")
print(f"   🟡 Column Errors: {len(column_errors)}")
print(f"   🟡 charter_id Issues: {len(charter_id_issues)}")
print(f"   🔵 Missing Error Handling: {len(missing_try_catch)}")
print(f"   ℹ️  Dead Code: {len(dead_code)}")
print("\n" + "=" * 80)
