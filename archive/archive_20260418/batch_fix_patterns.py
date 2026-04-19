"""
Batch fix all common f-string error patterns
"""
import re
from pathlib import Path

def fix_common_patterns(filepath):
    """Fix common syntax patterns"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Pattern 1: Double closing parens ))
    content = re.sub(r'\)\)\s*\n', r')\n', content)
    
    # Pattern 2: Misaligned except blocks
    # except Exception:
    #         pass
    # Convert to proper indentation
    content = re.sub(
        r'(except Exception[^:]*:)\n(\s+)try:\n(\s+)(\S)',
        r'\1\n\2    try:\n\2        \4',
        content
    )
    
    # Pattern 3: Misaligned QMessageBox calls
    content = re.sub(
        r'QMessageBox\.\w+\(\s*\n\s*self,',
        lambda m: m.group(0).replace('\n', '\n                '),
        content
    )
    
    # Pattern 4: Fix nested except with wrong indentation
    #     except Exception:
    #             pass
    lines = content.split('\n')
    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if this is an except line with excessive indentation
        if re.match(r'^(\s+)except Exception:', line):
            base_indent = len(re.match(r'^(\s+)', line).group(1))
            # Check next line for excessive indentation
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if next_line.strip():
                    next_indent_match = re.match(r'^(\s+)', next_line)
                    if next_indent_match:
                        next_indent = len(next_indent_match.group(1))
                        # If next line is indented more than 4 spaces beyond except
                        if next_indent > base_indent + 8:
                            # Fix the indentation
                            lines[i + 1] = ' ' * (base_indent + 4) + next_line.strip()
        fixed_lines.append(line)
        i += 1
    
    content = '\n'.join(fixed_lines)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

# Process all files
desktop_app = Path("l:/limo/desktop_app")
skip_patterns = ['backup', 'BACKUP', 'OLD', 'BROKEN', 'CLEAN']

fixed = 0
for py_file in sorted(desktop_app.glob("*.py")):
    if any(pattern in py_file.name for pattern in skip_patterns):
        continue
    
    if fix_common_patterns(py_file):
        fixed += 1
        print(f"Fixed: {py_file.name}")

print(f"\nFixed {fixed} files")
