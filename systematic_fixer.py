"""
Systematic Python syntax fixer - handles common patterns
"""
import re
import ast
from pathlib import Path

def fix_file_systematically(filepath):
    """Apply systematic fixes to a Python file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Fix 1: addWidget( without closing paren
    content = re.sub(r'(addWidget\([^)]+)$', r'\1)', content, flags=re.MULTILINE)
    
    # Fix 2: setItem( with missing closing paren
    content = re.sub(r'(setItem\([^)]*\([^)]*\))$', r'\1)', content, flags=re.MULTILINE)
    
    # Fix 3: append( with tuples missing closing paren  
    content = re.sub(r"(append\(\([^)]+\))$", r'\1)', content, flags=re.MULTILINE)
    
    # Fix 4: QLabel( without closing paren
    content = re.sub(r'(QLabel\([^)]+)$', r'\1)', content, flags=re.MULTILINE)
    
    # Fix 5: setDate/setTime without closing paren
    content = re.sub(r'(set(?:Date|Time)\([^)]+)$', r'\1)', content, flags=re.MULTILINE)
    
    # Fix 6: int( without closing paren
    content = re.sub(r'(int\([^)]+)$', r'\1)', content, flags=re.MULTILINE)
    
    # Fix 7: set( without closing paren
    content = re.sub(r'(\bset\([^)]+)$', r'\1)', content, flags=re.MULTILINE)
    
    # Fix 8: execute( without closing paren
    content = re.sub(r'(execute\([^)]*,[^)]*\))$', r'\1)', content, flags=re.MULTILINE)
    
    # Fix 9: Misaligned except blocks
    lines = content.split('\n')
    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check for: except Exception:
        #                 pass
        # That should be: except Exception:
        #             pass
        if 'except Exception:' in line and i + 1 < len(lines):
            next_line = lines[i + 1]
            if next_line.strip() == 'pass' or next_line.strip().startswith('self.db.rollback'):
                # Get current indentation
                curr_indent = len(line) - len(line.lstrip())
                next_indent = len(next_line) - len(next_line.lstrip())
                
                # If next line is indented more than expected
                if next_indent > curr_indent + 8:
                    # Fix it to proper indentation
                    lines[i + 1] = ' ' * (curr_indent + 4) + next_line.lstrip()
        
        fixed_lines.append(lines[i])
        i += 1
    
    content = '\n'.join(fixed_lines)
    
    # Try to compile to verify
    try:
        compile(content, filepath.name, 'exec')
        compiles = True
    except SyntaxError:
        compiles = False
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True, compiles
    return False, compiles

# Process all files
desktop_app = Path("l:/limo/desktop_app")
skip_patterns = ['backup', 'BACKUP', 'OLD', 'BROKEN', 'CLEAN', 'recovered']

fixed_count = 0
compiled_count = 0

for py_file in sorted(desktop_app.glob("*.py")):
    if any(pattern in py_file.name for pattern in skip_patterns):
        continue
    
    changed, compiles = fix_file_systematically(py_file)
    if changed:
        fixed_count += 1
        status = "COMPILES" if compiles else "STILL HAS ERRORS"
        print(f"{status}: {py_file.name}")
        if compiles:
            compiled_count += 1

print(f"\nModified: {fixed_count} files")
print(f"Now compile: {compiled_count} files")
