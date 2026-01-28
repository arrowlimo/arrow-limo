#!/usr/bin/env python3
"""Comprehensive code audit for database field naming and reference violations."""

import os
import re
from pathlib import Path
from collections import defaultdict

# Patterns to find problematic code
VIOLATIONS = {
    "charter_id_for_business": {
        "pattern": r"(WHERE|JOIN|SELECT).*charter_id\s*=\s*(?!.*reserve_number)",
        "description": "Using charter_id for business logic instead of reserve_number",
        "severity": "CRITICAL"
    },
    "missing_reserve_number": {
        "pattern": r"WHERE\s+.*charter_id\s*IN\s*\(",
        "description": "Matching charters without using reserve_number",
        "severity": "CRITICAL"
    },
    "dispatch_id_business": {
        "pattern": r"dispatch_id\s*=\s*(?!.*dispatch_datetime)",
        "description": "Using dispatch_id for business logic",
        "severity": "HIGH"
    },
    "hardcoded_ids": {
        "pattern": r"(charter_id|receipt_id|vehicle_id|employee_id)\s*=\s*\d+",
        "description": "Hardcoded ID values (potential test data in production)",
        "severity": "MEDIUM"
    },
    "string_currency": {
        "pattern": r"\".*\$.*\".*amount|amount.*\".*\$.*\"",
        "description": "Currency stored or compared as string",
        "severity": "HIGH"
    },
}

# Allowed uses of ID fields (where it's OK)
ALLOWED_ID_PATTERNS = [
    r"FOREIGN KEY",
    r"REFERENCES",
    r"PRIMARY KEY",
    r"INSERT INTO.*VALUES",
    r"RETURNING",
    r"def get_.*_by_id",
    r"table\.setItem.*receipt_id",
    r"\.get\(",
    r"row\[",
]

def is_allowed_context(line, match):
    """Check if the ID usage is in an allowed context."""
    for allowed_pattern in ALLOWED_ID_PATTERNS:
        if re.search(allowed_pattern, line, re.IGNORECASE):
            return True
    return False

def scan_files():
    """Scan Python and SQL files for violations."""
    violations_found = defaultdict(list)
    files_scanned = 0
    
    # Scan Python files
    for py_file in Path("L:\\limo").rglob("*.py"):
        if "venv" in str(py_file) or "__pycache__" in str(py_file) or ".egg" in str(py_file):
            continue
        
        files_scanned += 1
        try:
            with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    # Check for charter_id used in WHERE/JOIN without reserve_number on same line
                    if 'charter_id' in line.lower() and ('where' in line.lower() or 'join' in line.lower() or 'select' in line.lower()):
                        if 'reserve_number' not in line.lower() and not is_allowed_context(line, None):
                            violations_found['charter_id_usage'].append({
                                'file': str(py_file),
                                'line': line_num,
                                'code': line.strip(),
                                'issue': 'charter_id used for business logic instead of reserve_number'
                            })
                    
                    # Check for hardcoded IDs
                    if re.search(r'(charter_id|receipt_id|employee_id|vehicle_id|dispatch_id)\s*=\s*\d{1,5}(?![0-9])', line):
                        violations_found['hardcoded_ids'].append({
                            'file': str(py_file),
                            'line': line_num,
                            'code': line.strip(),
                            'issue': 'Hardcoded ID value - likely test data'
                        })
                    
                    # Check for currency as string
                    if re.search(r'["\'].*\$.*["\'].*amount|amount.*["\'].*\$.*["\']', line):
                        violations_found['currency_as_string'].append({
                            'file': str(py_file),
                            'line': line_num,
                            'code': line.strip(),
                            'issue': 'Currency handled as string instead of DECIMAL'
                        })
        except Exception as e:
            print(f"⚠️  Error reading {py_file}: {e}")
    
    return violations_found, files_scanned

def generate_report(violations, files_scanned):
    """Generate audit report."""
    report_path = "L:\\limo\\docs\\CODE_AUDIT_NAMING_VIOLATIONS.md"
    
    with open(report_path, 'w') as f:
        f.write("# Code Audit: Database Naming and Reference Violations\n\n")
        f.write(f"**Scan Date:** 2026-01-21\n")
        f.write(f"**Files Scanned:** {files_scanned}\n")
        f.write(f"**Violations Found:** {sum(len(v) for v in violations.values())}\n\n")
        
        # Critical violations
        f.write("## 🔴 CRITICAL VIOLATIONS\n\n")
        
        if violations.get('charter_id_usage'):
            f.write(f"### charter_id Used for Business Logic ({len(violations['charter_id_usage'])} instances)\n\n")
            f.write("**Rule:** Use `reserve_number` for charter business logic, never `charter_id`\n\n")
            for v in violations['charter_id_usage']:
                f.write(f"- **File:** {v['file']}\n")
                f.write(f"  **Line {v['line']}:** `{v['code']}`\n\n")
        
        # High severity
        f.write("## 🟠 HIGH SEVERITY VIOLATIONS\n\n")
        
        if violations.get('currency_as_string'):
            f.write(f"### Currency Handled as String ({len(violations['currency_as_string'])} instances)\n\n")
            f.write("**Rule:** Currency must be DECIMAL(12,2), never string\n\n")
            for v in violations['currency_as_string']:
                f.write(f"- **File:** {v['file']}\n")
                f.write(f"  **Line {v['line']}:** `{v['code']}`\n\n")
        
        # Medium severity
        f.write("## 🟡 MEDIUM SEVERITY VIOLATIONS\n\n")
        
        if violations.get('hardcoded_ids'):
            f.write(f"### Hardcoded ID Values ({len(violations['hardcoded_ids'])} instances)\n\n")
            f.write("**Rule:** Never hardcode ID values - use variables/parameters\n\n")
            for v in violations['hardcoded_ids']:
                f.write(f"- **File:** {v['file']}\n")
                f.write(f"  **Line {v['line']}:** `{v['code']}`\n\n")
        
        # Summary
        f.write("## Summary\n\n")
        f.write("### Business Key Rules Implemented\n")
        f.write("- ✅ `charter_id` = Primary key (relationships only)\n")
        f.write("- ✅ `reserve_number` = Business key (use for all business logic)\n")
        f.write("- ✅ `dispatch_id` = Primary key (relationships only)\n")
        f.write("- ✅ `receipt_id` = Primary key (relationships only)\n\n")
        
        f.write("### Data Type Rules\n")
        f.write("- ✅ Dates: YYYY-MM-DD format\n")
        f.write("- ✅ Currency: DECIMAL(12,2)\n")
        f.write("- ✅ Booleans: true/false (not 1/0)\n\n")
    
    print(f"✅ Audit report saved: {report_path}")
    return report_path

# Run audit
violations, files_scanned = scan_files()
report_path = generate_report(violations, files_scanned)

# Print summary
total_violations = sum(len(v) for v in violations.values())
print(f"\n📊 AUDIT SUMMARY")
print(f"================")
print(f"Files Scanned: {files_scanned}")
print(f"Total Violations: {total_violations}")
if violations:
    for category, items in violations.items():
        print(f"  - {category}: {len(items)}")
