#!/usr/bin/env python3
"""
Script to fix flake8 violations systematically
"""
import os
import re
from pathlib import Path

def fix_file(filepath):
    """Fix flake8 violations in a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except (UnicodeDecodeError, IsADirectoryError):
        return False, "Could not read file"
    
    original = content
    
    # Fix W293: blank line contains whitespace
    lines = content.split('\n')
    fixed_lines = []
    for line in lines:
        if line and not line.strip():  # blank line with whitespace
            fixed_lines.append('')
        else:
            fixed_lines.append(line)
    content = '\n'.join(fixed_lines)
    
    # Fix W291: trailing whitespace
    content = re.sub(r'[ \t]+\n', '\n', content)
    
    # Fix W292: no newline at end of file
    if content and not content.endswith('\n'):
        content += '\n'
    
    # Fix bare except clauses (E722)
    content = re.sub(r'\nexcept\s*:\s*', '\nexcept Exception:\n    ', content)
    
    # Fix unused imports
    if 'from typing import List' in content and content.count('List[') == 0:
        content = content.replace('from typing import List\n', '')
        content = content.replace('from typing import List, ', 'from typing import ')
    
    # Fix F401 unused imports
    unused_imports = [
        ('from typing import List', 'List'),
        ('import json', 'json'),
        ('import subprocess', 'subprocess'),
        ('from fastapi import Depends', 'Depends'),
        ('from fastapi import Query', 'Query'),
        ('from fastapi import UploadFile', 'UploadFile'),
        ('from fastapi import File', 'File'),
        ('from fastapi import Form', 'Form'),
        ('from pydantic import Field', 'Field'),
        ('from io import BytesIO', 'BytesIO'),
    ]
    
    for import_stmt, name in unused_imports:
        # Only remove if it's imported and not used
        if import_stmt in content:
            # Check usage (very basic)
            pattern = r'\b' + re.escape(name) + r'\b'
            if len(re.findall(pattern, content)) <= 1:  # Only the import itself
                # Remove the import line
                content = re.sub(import_stmt + r'\n', '', content)
                # Also handle comma-separated imports
                content = re.sub(import_stmt + r', ', '', content)
    
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
            # Skip common non-code directories
            dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', '.pytest_cache', 'node_modules']]
            
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    total_files += 1
                    fixed, msg = fix_file(filepath)
                    if fixed:
                        fixed_files += 1
                        print(f"Fixed: {filepath}")
    
    print(f"\nTotal files processed: {total_files}")
    print(f"Files with changes: {fixed_files}")

if __name__ == '__main__':
    main()
