#!/usr/bin/env python3
"""
Advanced flake8 violation fixer
"""
import os
import re
from pathlib import Path

def fix_bare_except(content):
    """Fix E722: bare except clauses"""
    # Match bare except: patterns
    content = re.sub(
        r'\nexcept\s*:\s*\n',
        '\nexcept Exception:\n',
        content
    )
    return content

def fix_unused_imports(content):
    """Remove unused imports"""
    # Remove unused datetime imports
    if 'from datetime import datetime' in content:
        if 'datetime(' not in content and 'datetime.now' not in content:
            content = content.replace('from datetime import datetime\n', '')
    
    if 'import datetime' in content:
        # Check if datetime is used (not just datetime.datetime)
        if content.count('datetime.') == content.count('from datetime import') + \
           content.count('import datetime') + content.count('# datetime'):
            if 'datetime.datetime' not in content.replace('from datetime import datetime', ''):
                content = content.replace('import datetime\n', '')
    
    return content

def fix_file(filepath):
    """Fix violations in a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except (UnicodeDecodeError, IsADirectoryError):
        return False, "Could not read file"
    
    original = content
    
    # Fix E722: bare except
    content = fix_bare_except(content)
    
    # Fix F401: unused imports
    content = fix_unused_imports(content)
    
    # Remove blank line at end of file (W391)
    while content.endswith('\n\n\n'):
        content = content[:-1]
    
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
