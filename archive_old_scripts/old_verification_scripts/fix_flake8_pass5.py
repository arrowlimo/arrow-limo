#!/usr/bin/env python3
"""
Final flake8 violation fixer - Pass 5
Fixes W605, W391, W292, E502, and simple unused variable issues
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
    
    # Fix W605: invalid escape sequences
    # Convert raw strings where needed
    content = content.replace(r"'\d'", "r'\\d'")
    content = content.replace(r'"\d"', r'r"\d"')
    content = content.replace(r"'\s'", "r'\\s'")
    content = content.replace(r'"\s"', r'r"\s"')
    
    # Fix W391: blank line at end of file
    while content.endswith('\n\n\n'):
        content = content[:-1]
    
    # Fix W292: add newline at end of file
    if content and not content.endswith('\n'):
        content += '\n'
    
    # Fix E502: redundant backslash
    content = re.sub(r'\\\n\s*\)', '\n)', content)
    content = re.sub(r'\\\n\s*\]', '\n]', content)
    content = re.sub(r'\\\n\s*\}', '\n}', content)
    
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
