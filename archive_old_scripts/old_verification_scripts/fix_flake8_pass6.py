#!/usr/bin/env python3
"""
Final comprehensive flake8 violation fixer - Pass 6
Fixes E202, W291, and other mechanical issues
"""
import os
import re

def fix_file(filepath):
    """Fix violations in a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except (UnicodeDecodeError, IsADirectoryError):
        return False, "Could not read file"
    
    original = content
    
    # Fix W291: trailing whitespace
    lines = content.split('\n')
    fixed_lines = []
    for line in lines:
        fixed_lines.append(line.rstrip())
    content = '\n'.join(fixed_lines)
    
    # Fix E202: whitespace before ')' or ']' or '}'
    content = re.sub(r'\s+\)', ')', content)
    content = re.sub(r'\s+\]', ']', content)
    content = re.sub(r'\s+\}', '}', content)
    
    # Fix W391: blank line at end of file (ensure only one newline at end)
    content = content.rstrip('\n') + '\n'
    
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
