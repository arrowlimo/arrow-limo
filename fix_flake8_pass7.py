#!/usr/bin/env python3
"""
Line wrapper to fix E501 violations - Pass 7
Wraps lines that exceed 79 characters
"""
import os
import re

def wrap_long_line(line, max_length=79):
    """Try to wrap a long line intelligently"""
    if len(line.rstrip()) <= max_length:
        return line
    
    indent = len(line) - len(line.lstrip())
    indent_str = line[:indent]
    code = line[indent:].rstrip()
    
    # Don't try to wrap comments or strings that are inherently long
    if code.startswith('#'):
        return line
    
    if code.startswith(('f"', '"', "f'", "'")):
        return line
    
    # Try to split on operators or commas
    # Look for the last occurrence of an operator or comma before max_length
    split_points = []
    for i, char in enumerate(code):
        if i > max_length and char in (' ', ',', '=', '(', '[', '{'):
            split_points.append(i)
    
    if not split_points:
        return line
    
    # Take the best split point (closest to max_length from the left)
    valid_splits = [s for s in split_points if s < len(code) - 1]
    if not valid_splits:
        return line
    split_pos = max(valid_splits)
    
    if split_pos < max_length * 0.5:  # Don't split too early
        return line
    
    # Find the right split character
    # Back up to find the actual boundary
    while split_pos > 0 and code[split_pos] not in (' ', ',', '=', '(', '[', '{'):
        split_pos -= 1
    
    if split_pos < indent + 20:
        return line
    
    # For imports, special handling
    if 'import ' in code:
        if ' as ' in code:
            parts = code.split(' as ')
            if len(parts) == 2:
                return line  # Don't wrap simple imports
        elif 'from ' in code:
            match = re.match(r'^from\s+(\S+)\s+import\s+(.+)$', code)
            if match:
                module = match.group(1)
                imports = match.group(2)
                if ',' in imports:
                    # Split imports across lines
                    import_list = [i.strip() for i in imports.split(',')]
                    if len(import_list) > 1:
                        wrapped = f'{indent_str}from {module} import (\n'
                        for i, imp in enumerate(import_list[:-1]):
                            wrapped += f'{indent_str}    {imp},\n'
                        wrapped += f'{indent_str}    {import_list[-1]}\n{indent_str})'
                        return wrapped
        return line
    
    # For other long lines, don't wrap automatically (too risky)
    return line

def fix_file(filepath):
    """Fix E501 violations in a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except (UnicodeDecodeError, IsADirectoryError):
        return False, "Could not read file"
    
    original = content
    lines = content.split('\n')
    fixed_lines = []
    
    for line in lines:
        if len(line.rstrip()) > 79:
            wrapped = wrap_long_line(line)
            if wrapped != line:
                fixed_lines.extend(wrapped.split('\n'))
            else:
                fixed_lines.append(line)
        else:
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
