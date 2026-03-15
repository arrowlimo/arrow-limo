"""
Fix missing closing parentheses that were removed by overeager regex
"""
import re
from pathlib import Path

def fix_missing_parens(filepath):
    """Fix lines ending with ( that should have )"""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    fixed = False
    for i, line in enumerate(lines):
        # Check for lines ending with addWidget(something without closing paren
        if re.search(r'addWidget\([^)]+$', line.rstrip()):
            lines[i] = line.rstrip() + ')\n'
            fixed = True
            print(f"  Fixed line {i+1}: addWidget")
        
        # Check for lines with setDate( without closing paren
        elif re.search(r'setDate\([^)]+$', line.rstrip()):
            lines[i] = line.rstrip() + ')\n'
            fixed = True
            print(f"  Fixed line {i+1}: setDate")
        
        # Check for lines with setItem( without closing paren
        elif re.search(r'setItem\([^)]+$', line.rstrip()):
            lines[i] = line.rstrip() + ')\n'
            fixed = True
            print(f"  Fixed line {i+1}: setItem")
        
        # Check for lines with QLabel( without closing paren
        elif re.search(r'QLabel\([^)]+$', line.rstrip()):
            lines[i] = line.rstrip() + ')\n'
            fixed = True
            print(f"  Fixed line {i+1}: QLabel")
    
    if fixed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        return True
    return False

# Process files
desktop_app = Path("l:/limo/desktop_app")
skip_patterns = ['backup', 'BACKUP', 'OLD', 'BROKEN', 'CLEAN']

fixed_count = 0
for py_file in sorted(desktop_app.glob("*.py")):
    if any(pattern in py_file.name for pattern in skip_patterns):
        continue
    
    print(f"Checking {py_file.name}...")
    if fix_missing_parens(py_file):
        fixed_count += 1

print(f"\nFixed {fixed_count} files")
