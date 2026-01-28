"""
Additional fixes finder - scan for remaining issues
"""

import re
from pathlib import Path
from collections import defaultdict

def scan_for_issues():
    """Scan desktop_app for remaining common issues"""
    
    issues = defaultdict(list)
    desktop_app = Path('l:/limo/desktop_app')
    
    # Skip backup files
    skip_patterns = ['backup', 'CLEAN_', 'PREV_', '__pycache__', '.pyc']
    
    for py_file in desktop_app.glob('*.py'):
        if any(skip in str(py_file) for skip in skip_patterns):
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            rel_path = py_file.relative_to(desktop_app.parent)
            
            # Issue 1: Missing commit after INSERT/UPDATE/DELETE
            if 'cur.execute' in content:
                for i, line in enumerate(lines, 1):
                    if 'cur.execute' in line and any(cmd in line.upper() for cmd in ['INSERT', 'UPDATE', 'DELETE']):
                        # Check next 20 lines for commit
                        window = '\n'.join(lines[i:min(i+20, len(lines))])
                        if 'commit()' not in window and 'conn.commit' not in window and 'self.db.commit' not in window:
                            issues['missing_commit'].append(f"{rel_path}:{i}")
            
            # Issue 2: Exception handling without rollback
            for i, line in enumerate(lines, 1):
                if 'except Exception as' in line or 'except:' in line:
                    # Check if there's a rollback in the except block
                    window_start = i
                    window_end = min(i+10, len(lines))
                    except_block = '\n'.join(lines[window_start:window_end])
                    if 'rollback' not in except_block and 'cur.execute' in '\n'.join(lines[max(0,i-30):i]):
                        issues['missing_rollback_in_except'].append(f"{rel_path}:{i}")
            
            # Issue 3: Using string concatenation in SQL (SQL injection risk)
            for i, line in enumerate(lines, 1):
                if 'cur.execute' in line and (f'f"' in line or f"f'" in line or '+ ' in line):
                    if '%s' not in line and not line.strip().startswith('#'):
                        issues['sql_injection_risk'].append(f"{rel_path}:{i}")
            
            # Issue 4: QMessageBox in __init__ (timing issue)
            for i, line in enumerate(lines, 1):
                if 'def __init__' in line:
                    # Check init method for QMessageBox
                    init_end = i + 100
                    for j in range(i, min(init_end, len(lines))):
                        if 'def ' in lines[j] and j > i:
                            init_end = j
                            break
                    init_block = '\n'.join(lines[i:init_end])
                    if 'QMessageBox.' in init_block and 'critical' in init_block:
                        issues['qmessagebox_in_init'].append(f"{rel_path}:{i}")
                        break
            
        except Exception as e:
            issues['scan_errors'].append(f"{rel_path}: {e}")
    
    return issues

def main():
    print("=" * 80)
    print("SCANNING FOR ADDITIONAL ISSUES")
    print("=" * 80)
    
    issues = scan_for_issues()
    
    total_issues = sum(len(v) for v in issues.values() if v and 'error' not in str(v).lower())
    
    if total_issues == 0:
        print("\n✅ No additional issues found!")
        print("\nThe codebase looks clean. Main categories checked:")
        print("  - Missing commits after INSERT/UPDATE/DELETE")
        print("  - Missing rollback in exception handlers")
        print("  - SQL injection risks (string concatenation)")
        print("  - QMessageBox timing issues in __init__")
        return
    
    print(f"\n📊 Found {total_issues} potential issues:\n")
    
    for issue_type, locations in sorted(issues.items()):
        if not locations or 'error' in issue_type:
            continue
        
        print(f"\n{issue_type.replace('_', ' ').title()}: {len(locations)}")
        print("-" * 80)
        
        # Show first 10 examples
        for loc in locations[:10]:
            print(f"  {loc}")
        
        if len(locations) > 10:
            print(f"  ... and {len(locations) - 10} more")
    
    if issues.get('scan_errors'):
        print(f"\n⚠️  Scan Errors:")
        for err in issues['scan_errors']:
            print(f"  {err}")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS:")
    print("=" * 80)
    
    if issues.get('missing_commit'):
        print("\n1. Missing Commits:")
        print("   Add self.db.commit() or conn.commit() after INSERT/UPDATE/DELETE")
        print("   This ensures database changes are persisted")
    
    if issues.get('missing_rollback_in_except'):
        print("\n2. Missing Rollback in Exception Handlers:")
        print("   Add self.db.rollback() in except blocks that handle database errors")
        print("   This prevents transaction lock issues")
    
    if issues.get('sql_injection_risk'):
        print("\n3. SQL Injection Risks:")
        print("   Replace string concatenation with parameterized queries")
        print("   Use %s placeholders instead of f-strings or + concatenation")
    
    if issues.get('qmessagebox_in_init'):
        print("\n4. QMessageBox Timing Issues:")
        print("   Move QMessageBox calls out of __init__ to load_data or other methods")
        print("   Use print() instead during initialization")

if __name__ == "__main__":
    main()
