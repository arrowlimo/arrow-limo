#!/usr/bin/env python3
"""
Comprehensive flake8 violation fixer - Pass 4
Fixes F541 (f-string without placeholders) and removes some unused imports
"""
import os
import re
from pathlib import Path

def fix_f_string_without_placeholders(content):
    """Fix F541: f-string without placeholders"""
    # Find f-strings without any {} placeholders
    lines = content.split('\n')
    fixed_lines = []
    
    for line in lines:
        # Look for f-strings without placeholders
        # Pattern: f"..." where there's no {
        while 'f"' in line or "f'" in line:
            # Match f-strings
            match = re.search(r"f(['\"])(?:[^'\"\\]|\\.)*?\1", line)
            if match:
                f_string = match.group(0)
                # Check if it has placeholders
                if '{' not in f_string:
                    # Remove the f prefix
                    regular_string = f_string[1:]  # Remove 'f'
                    line = line[:match.start()] + regular_string + line[match.end():]
                else:
                    break
            else:
                break
        fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)

def remove_unused_datetime_import(content):
    """Remove unused datetime.datetime imports"""
    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        # Skip lines that import datetime
        if 'from datetime import datetime' in line and 'from datetime import datetime, ' not in line:
            # Check if datetime is actually used
            datetime_count = content.count('datetime(')
            if datetime_count == 0:
                continue
        new_lines.append(line)
    
    return '\n'.join(new_lines)

def fix_file(filepath):
    """Fix violations in a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except (UnicodeDecodeError, IsADirectoryError):
        return False, "Could not read file"
    
    original = content
    
    # Fix F541: f-strings without placeholders
    content = fix_f_string_without_placeholders(content)
    
    if original != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True, "Fixed F541"
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
