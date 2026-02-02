#!/usr/bin/env python3
"""
Comprehensive flake8 violation fixer - Pass 3
Fixes E722 (bare except) violations
"""
import os
import re
from pathlib import Path

def fix_bare_except(content):
    """Fix E722: bare except clauses"""
    lines = content.split('\n')
    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check if this is a bare except line
        if re.match(r'^\s*except\s*:\s*$', line):
            # Get the indentation
            indent_match = re.match(r'^(\s*)except\s*:\s*$', line)
            if indent_match:
                indent = indent_match.group(1)
                fixed_lines.append(indent + 'except Exception:')
            else:
                fixed_lines.append(line)
        else:
            fixed_lines.append(line)
        i += 1
    
    return '\n'.join(fixed_lines)

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
