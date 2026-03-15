#!/usr/bin/env python3
"""
Ultra-safe flake8 violation fixer - Pass 8
Only removes completely unused imports from common stdlib and packages
"""
import os
import re

# List of safe-to-remove imports (not used by their mere presence)
SAFE_UNUSED_IMPORTS = {
    'datetime': ('datetime',),
    'json': ('json',),
    'os': ('os',),
    're': ('re',),
    'sys': ('sys',),
    'subprocess': ('subprocess',),
    'shutil': ('shutil',),
    'traceback': ('traceback',),
}

def fix_file(filepath):
    """Fix obvious unused imports"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except (UnicodeDecodeError, IsADirectoryError):
        return False, "Could not read file"
    
    original = content
    lines = content.split('\n')
    fixed_lines = []
    
    for line in lines:
        skip = False
        # Check for simple, complete-module imports that aren't used
        for module, names in SAFE_UNUSED_IMPORTS.items():
            if f'import {module}' in line and 'from ' not in line:
                # Check if module is used (except in comments or the import itself)
                usage_count = content.count(module + '.')
                import_count = content.count(f'import {module}')
                if usage_count == 0 and import_count == 1:
                    skip = True
                    break
        
        if not skip:
            fixed_lines.append(line)
    
    content = '\n'.join(fixed_lines)
    
    if original != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True, "Fixed"
    return False, "No changes"

def main():
    base_dirs = [
        'l:\\limo\\desktop_app',
        'l:\\limo\\modern_backend',
    ]
    
    total_files = 0
    fixed_files = 0
    
    for base_dir in base_dirs:
        if not os.path.exists(base_dir):
            continue
        
        for root, dirs, files in os.walk(base_dir):
            dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', '.pytest_cache', 'node_modules']]
            
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    total_files += 1
                    fixed, msg = fix_file(filepath)
                    if fixed:
                        fixed_files += 1
                        print(f"Fixed: {filepath}")
    
    print(f"\nTotal files: {total_files}, Fixed: {fixed_files}")

if __name__ == '__main__':
    main()
