#!/usr/bin/env python3
"""
Automated fix for f-string syntax errors across desktop_app
"""
import re
import os
from pathlib import Path

def fix_fstring_errors(file_path):
    """Fix f-string syntax errors in a Python file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    original_content = ''.join(lines)
    fixed_lines = []
    i = 0
    changes_made = False
    
    while i < len(lines):
        line = lines[i]
        
        # Check if line has f-string with opening brace at end
        if re.search(r'f["\'].*\{\s*$', line):
            # Look ahead for continuation
            combined = line.rstrip()
            j = i + 1
            
            # Collect continuation lines
            while j < len(lines) and not lines[j].strip().endswith(('}"', "}'", '")'):
                combined += lines[j].strip()
                j += 1
            
            # Add the closing line
            if j < len(lines):
                combined += lines[j].strip()
                j += 1
            
            # Clean up the combined line - remove internal newlines
            combined = combined.replace('\n', ' ').replace('  ', ' ')
            fixed_lines.append(combined + '\n')
            changes_made = True
            i = j
        else:
            fixed_lines.append(line)
            i += 1
    
    if not changes_made:
        return None
    
    fixed_content = ''.join(fixed_lines)
    
    # Backup original
    backup_path = str(file_path) + '.fstring_backup'
    if not os.path.exists(backup_path):
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_content)
    
    # Write fixed content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    return True

if __name__ == "__main__":
    desktop_app = Path("l:/limo/desktop_app")
    
    # Skip backup files
    skip_patterns = ['backup', 'BACKUP', 'OLD', 'BROKEN', 'CLEAN']
    
    fixed_files = []
    for py_file in desktop_app.glob("*.py"):
        if any(pattern in py_file.name for pattern in skip_patterns):
            continue
        try:
            if fix_fstring_errors(py_file):
                fixed_files.append(py_file.name)
                print(f"✓ Fixed: {py_file.name}")
        except Exception as e:
            print(f"✗ Error in {py_file.name}: {me)
            print(f"✓ Fixed: {py_file.name}")
    
    print(f"\n✓ Fixed {len(fixed_files)} files")
