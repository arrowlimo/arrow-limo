"""
Automated f-string fixer - reads error locations and fixes them
"""
import re
from pathlib import Path

def fix_file(filepath, error_line):
    """Fix f-string error at specified line"""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find the problematic f-string (look a few lines before error_line)
    search_start = max(0, error_line - 5)
    
    fixed = False
    for i in range(search_start, min(error_line + 2, len(lines))):
        line = lines[i]
        
        # Check for f-string with unclosed brace
        if re.search(r'f["\'][^"\']*\{\s*$', line):
            # Collect all continuation lines
            combined = line.rstrip()
            j = i + 1
            
            while j < len(lines):
                next_line = lines[j]
                combined += ' ' + next_line.strip()
                
                # Check if we've found the closing quote
                if '}"' in next_line or "}'" in next_line:
                    # Clean up the combined line
                    combined = re.sub(r'\s+', ' ', combined)
                    
                    # Replace the lines
                    lines[i] = combined + '\n'
                    # Remove the continuation lines
                    for k in range(i + 1, j + 1):
                        lines[k] = ''
                    
                    fixed = True
                    break
                
                j += 1
                if j - i > 10:  # Safety limit
                    break
            
            if fixed:
                break
    
    if fixed:
        # Write back
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines([line for line in lines if line])
        return True
    return False

# Read error report
errors = []
with open('l:/limo/fstring_errors.txt', 'r') as f:
    for line in f:
        line = line.strip()
        if ':' in line and not line.startswith('Total'):
            parts = line.split(':')
            if len(parts) == 2:
                try:
                    filename, linenum = parts[0], int(parts[1])
                    errors.append((filename, linenum))
                except ValueError:
                    pass

fixed_count = 0
for filename, linenum in errors:
    filepath = Path(f'l:/limo/desktop_app/{filename}')
    if filepath.exists():
        if fix_file(filepath, linenum):
            print(f"FIXED {filename}:{linenum}")
            fixed_count += 1
        else:
            print(f"FAILED {filename}:{linenum}")

print(f"\nFixed {fixed_count}/{len(errors)} errors")
