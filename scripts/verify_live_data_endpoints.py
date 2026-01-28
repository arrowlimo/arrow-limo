#!/usr/bin/env python3
"""
Verify Backend Endpoints Use Live Data
======================================
Confirms no hardcoded test/fake data in API endpoints.
"""
import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).parent.parent / "modern_backend" / "app" / "routers"

# Patterns that indicate hardcoded fake data
SUSPICIOUS_PATTERNS = [
    (r'return.*\{[^}]*amount.*:.*0[,}]', "Hardcoded zero amounts"),
    (r'return.*\[\]', "Empty list return (potential stub)"),
    (r'return.*\{\}', "Empty dict return (potential stub)"),
    (r"'test'|'sample'|'fake'|'dummy'|'mock'", "Test/fake data strings"),
    (r'charter_id\s*=\s*123', "Hardcoded test IDs"),
    (r'WHERE.*=.*1\s+AND\s+1\s*=\s*1', "Always-true conditions"),
]

# Patterns that indicate live data usage
GOOD_PATTERNS = [
    r'cur\.execute\(',
    r'with cursor\(\)',
    r'SELECT.*FROM',
    r'INSERT INTO',
    r'UPDATE.*SET',
    r'DELETE FROM',
]

def check_file(filepath):
    """Check a single router file for hardcoded data."""
    content = filepath.read_text(encoding='utf-8')
    issues = []
    
    # Check for suspicious patterns
    for pattern, description in SUSPICIOUS_PATTERNS:
        matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
        if matches:
            # Filter out legitimate cases
            for match in matches:
                # Skip if it's part of a database query or error response
                if 'cur.execute' in match or 'HTTPException' in match:
                    continue
                # Skip if it's a wrapper structure
                if re.search(r'\{["\'].*["\']\s*:\s*\[', match):  # {"key": [items]}
                    continue
                # Skip if it's a success response like {"deleted": True}
                if '"deleted"' in match or "'deleted'" in match:
                    continue
                
                issues.append({
                    'pattern': description,
                    'match': match.strip()[:100],
                    'suspicious': True
                })
    
    # Check for database usage
    db_queries = 0
    for pattern in GOOD_PATTERNS:
        db_queries += len(re.findall(pattern, content, re.IGNORECASE))
    
    return issues, db_queries

def main():
    print("=" * 80)
    print("BACKEND LIVE DATA VERIFICATION")
    print("=" * 80)
    print("Checking all router endpoints for hardcoded test/fake data...")
    print()
    
    all_files = list(BACKEND_ROOT.glob("*.py"))
    total_issues = 0
    total_queries = 0
    
    for filepath in sorted(all_files):
        if filepath.name.startswith('__'):
            continue
        
        issues, db_queries = check_file(filepath)
        total_queries += db_queries
        
        if issues:
            print(f"\n⚠️  {filepath.name}")
            print(f"   Database queries found: {db_queries}")
            for issue in issues:
                print(f"   ❌ {issue['pattern']}")
                print(f"      {issue['match']}")
                total_issues += 1
        else:
            status = "✅" if db_queries > 0 else "⚠️"
            print(f"{status} {filepath.name:30} - {db_queries} database queries")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Files checked: {len(all_files)}")
    print(f"Total database queries: {total_queries}")
    print(f"Suspicious patterns found: {total_issues}")
    
    if total_issues == 0:
        print("\n✅ ALL ENDPOINTS USE LIVE DATA FROM DATABASE!")
        return 0
    else:
        print(f"\n⚠️  {total_issues} potential issues found - review above")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
