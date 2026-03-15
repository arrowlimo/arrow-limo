#!/usr/bin/env python3
"""
Frontend Live Data & UX Audit
==============================
Verify frontend uses live API data and audit all forms for proper UX.
"""
import os
import re
from pathlib import Path

FRONTEND_ROOT = Path("l:/limo/frontend/src")

def check_vue_file_for_live_data(filepath):
    """Check if Vue component uses live API calls vs hardcoded data."""
    content = filepath.read_text(encoding='utf-8')
    
    issues = []
    good_patterns = []
    
    # Check for API calls
    if re.search(r'fetch\(|axios\.|api\.|API_BASE', content, re.IGNORECASE):
        good_patterns.append("✓ Uses API calls")
    
    # Check for hardcoded data arrays
    hardcoded_data = re.findall(r'const \w+ = \[\s*\{[^}]+\}[^]]*\]', content)
    if hardcoded_data and len(hardcoded_data) > 2:
        issues.append(f"⚠️  {len(hardcoded_data)} potential hardcoded data arrays")
    
    # Check for reactive data
    if re.search(r'ref\(|reactive\(|computed\(', content):
        good_patterns.append("✓ Uses Vue 3 composition API")
    
    # Check for forms
    has_form = bool(re.search(r'<form|v-model', content))
    if has_form:
        # Check tab navigation
        if 'tabindex' not in content.lower():
            issues.append("❌ Form without tabindex attributes")
        
        # Check for proper input structure
        if not re.search(r'<label|for=', content):
            issues.append("⚠️  Form inputs without labels")
        
        # Check for validation
        if not re.search(r'@submit|validate|error', content):
            issues.append("⚠️  Form without validation")
        
        # Check for CRUD operations
        crud_ops = {
            'create': bool(re.search(r'create|add|new|save.*new', content, re.IGNORECASE)),
            'read': bool(re.search(r'fetch|load|get|read', content, re.IGNORECASE)),
            'update': bool(re.search(r'update|edit|modify|save', content, re.IGNORECASE)),
            'delete': bool(re.search(r'delete|remove|destroy', content, re.IGNORECASE))
        }
        missing_crud = [op for op, exists in crud_ops.items() if not exists]
        if missing_crud:
            issues.append(f"⚠️  Missing CRUD: {', '.join(missing_crud)}")
    
    return {
        'has_form': has_form,
        'issues': issues,
        'good_patterns': good_patterns
    }

def main():
    print("=" * 80)
    print("FRONTEND LIVE DATA & UX AUDIT")
    print("=" * 80)
    
    views_dir = FRONTEND_ROOT / "views"
    components_dir = FRONTEND_ROOT / "components"
    
    all_issues = []
    files_with_forms = []
    
    print("\n📋 SCANNING VIEWS...")
    print("-" * 80)
    
    for vue_file in sorted(views_dir.glob("*.vue")):
        result = check_vue_file_for_live_data(vue_file)
        
        if result['has_form'] or result['issues'] or result['good_patterns']:
            print(f"\n{vue_file.name}")
            for pattern in result['good_patterns']:
                print(f"  {pattern}")
            for issue in result['issues']:
                print(f"  {issue}")
                all_issues.append((vue_file.name, issue))
            
            if result['has_form']:
                files_with_forms.append(vue_file.name)
    
    print("\n\n📋 SCANNING COMPONENTS...")
    print("-" * 80)
    
    if components_dir.exists():
        for vue_file in sorted(components_dir.glob("*.vue")):
            result = check_vue_file_for_live_data(vue_file)
            
            if result['has_form'] or result['issues']:
                print(f"\n{vue_file.name}")
                for issue in result['issues']:
                    print(f"  {issue}")
                    all_issues.append((vue_file.name, issue))
                
                if result['has_form']:
                    files_with_forms.append(vue_file.name)
    
    print("\n\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Files with forms: {len(files_with_forms)}")
    print(f"Total issues found: {len(all_issues)}")
    
    if files_with_forms:
        print(f"\n📝 Files with forms:")
        for f in files_with_forms:
            print(f"  - {f}")
    
    if all_issues:
        print(f"\n⚠️  Issues by category:")
        issue_types = {}
        for file, issue in all_issues:
            issue_type = issue.split(':')[0].strip()
            if issue_type not in issue_types:
                issue_types[issue_type] = []
            issue_types[issue_type].append(file)
        
        for issue_type, files in sorted(issue_types.items()):
            print(f"\n{issue_type}")
            for f in set(files):
                print(f"    {f}")
    
    return 0 if len(all_issues) == 0 else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
