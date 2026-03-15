#!/usr/bin/env python3
"""Audit Vue and Python code for ID field naming consistency"""
import re
from pathlib import Path
from collections import defaultdict

# Define expected ID field mappings
EXPECTED_ID_FIELDS = {
    'receipts': 'receipt_id',
    'charters': 'charter_id',
    'vehicles': 'vehicle_id',
    'employees': 'employee_id',
    'customers': 'customer_id',
    'banking_transactions': 'transaction_id',
    'payments': 'payment_id',
    'charter_charges': 'charge_id',
}

# Common incorrect patterns
INCORRECT_PATTERNS = [
    (r'\breceiptId\b', 'receipt_id', 'camelCase instead of snake_case'),
    (r'\bcharterId\b', 'charter_id', 'camelCase instead of snake_case'),
    (r'\bvehicleId\b', 'vehicle_id', 'camelCase instead of snake_case'),
    (r'\bemployeeId\b', 'employee_id', 'camelCase instead of snake_case'),
    (r'\bcustomerId\b', 'customer_id', 'camelCase instead of snake_case'),
    (r'\btransactionId\b', 'transaction_id', 'camelCase instead of snake_case'),
]

def check_vue_files():
    """Check Vue files for ID naming issues"""
    print("=" * 80)
    print("VUE FILES AUDIT")
    print("=" * 80)
    
    vue_dir = Path('l:/limo/frontend/src')
    if not vue_dir.exists():
        print("⚠️  Vue src directory not found")
        return
    
    vue_files = list(vue_dir.glob('**/*.vue'))
    print(f"\nFound {len(vue_files)} Vue files\n")
    
    issues = defaultdict(list)
    
    for vue_file in vue_files:
        try:
            content = vue_file.read_text(encoding='utf-8')
            rel_path = vue_file.relative_to(Path('l:/limo'))
            
            # Check for incorrect camelCase IDs
            for pattern, correct, msg in INCORRECT_PATTERNS:
                matches = re.finditer(pattern, content)
                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    issues[str(rel_path)].append({
                        'line': line_num,
                        'issue': f"Found '{match.group()}' - should be '{correct}' ({msg})",
                        'type': 'naming'
                    })
        except Exception as e:
            print(f"Error reading {vue_file}: {e}")
    
    if issues:
        print("ISSUES FOUND:")
        print("-" * 80)
        for file, file_issues in sorted(issues.items()):
            print(f"\n{file}:")
            for issue in file_issues[:5]:  # Limit to 5 per file
                print(f"  Line {issue['line']}: {issue['issue']}")
            if len(file_issues) > 5:
                print(f"  ... and {len(file_issues) - 5} more issues")
    else:
        print("✓ No ID naming issues found in Vue files")

def check_python_files():
    """Check Python backend files for column naming issues"""
    print("\n" + "=" * 80)
    print("PYTHON BACKEND AUDIT")
    print("=" * 80)
    
    backend_dir = Path('l:/limo/modern_backend/app/routers')
    if not backend_dir.exists():
        print("⚠️  Backend routers directory not found")
        return
    
    py_files = list(backend_dir.glob('*.py'))
    print(f"\nFound {len(py_files)} Python router files\n")
    
    issues = defaultdict(list)
    
    for py_file in py_files:
        try:
            content = py_file.read_text(encoding='utf-8')
            rel_path = py_file.relative_to(Path('l:/limo'))
            
            # Check for SQL queries with potential issues
            sql_pattern = r'(SELECT|INSERT|UPDATE).*?(FROM|INTO)\s+(\w+)'
            matches = re.finditer(sql_pattern, content, re.IGNORECASE | re.DOTALL)
            
            for match in matches:
                table_name = match.group(3)
                line_num = content[:match.start()].count('\n') + 1
                
                # Check if expected ID field is referenced correctly
                if table_name in EXPECTED_ID_FIELDS:
                    expected_id = EXPECTED_ID_FIELDS[table_name]
                    # Look for the query context
                    query_start = max(0, match.start() - 100)
                    query_end = min(len(content), match.end() + 500)
                    query_context = content[query_start:query_end]
                    
                    # Check if correct ID field is used
                    incorrect_ids = []
                    for pattern, correct, msg in INCORRECT_PATTERNS:
                        if re.search(pattern, query_context):
                            incorrect_ids.append((pattern, correct, msg))
                    
                    if incorrect_ids:
                        for pattern, correct, msg in incorrect_ids:
                            issues[str(rel_path)].append({
                                'line': line_num,
                                'issue': f"Query on {table_name} may have {msg}",
                                'type': 'sql_naming'
                            })
        
        except Exception as e:
            print(f"Error reading {py_file}: {e}")
    
    if issues:
        print("ISSUES FOUND:")
        print("-" * 80)
        for file, file_issues in sorted(issues.items()):
            print(f"\n{file}:")
            for issue in file_issues[:5]:
                print(f"  Line {issue['line']}: {issue['issue']}")
            if len(file_issues) > 5:
                print(f"  ... and {len(file_issues) - 5} more issues")
    else:
        print("✓ No SQL naming issues found in Python files")

def check_spelling():
    """Check common spelling errors"""
    print("\n" + "=" * 80)
    print("SPELLING CHECK")
    print("=" * 80)
    
    common_misspellings = [
        (r'\bteh\b', 'the'),
        (r'\breciept\b', 'receipt'),
        (r'\bveicle\b', 'vehicle'),
        (r'\bemploye\b', 'employee'),
        (r'\bcustmer\b', 'customer'),
        (r'\btransacton\b', 'transaction'),
    ]
    
    issues = []
    
    # Check Vue files
    vue_dir = Path('l:/limo/frontend/src')
    if vue_dir.exists():
        for vue_file in vue_dir.glob('**/*.vue'):
            try:
                content = vue_file.read_text(encoding='utf-8')
                for pattern, correct in common_misspellings:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        line_num = content[:match.start()].count('\n') + 1
                        issues.append(f"{vue_file.name}:{line_num} - '{match.group()}' should be '{correct}'")
            except:
                pass
    
    if issues:
        print("\nSPELLING ISSUES:")
        for issue in issues[:20]:
            print(f"  {issue}")
        if len(issues) > 20:
            print(f"  ... and {len(issues) - 20} more")
    else:
        print("✓ No common spelling errors found")

if __name__ == '__main__':
    check_vue_files()
    check_python_files()
    check_spelling()
    print("\n" + "=" * 80)
    print("AUDIT COMPLETE")
    print("=" * 80)
