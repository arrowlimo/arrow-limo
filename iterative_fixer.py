"""
Comprehensive Python syntax fixer - iteratively fix files until they compile
"""
import re
import subprocess
from pathlib import Path

def get_syntax_error_line(filepath):
    """Get the line number of syntax error"""
    result = subprocess.run(
        ['python', '-m', 'py_compile', str(filepath)],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        return None
    match = re.search(r'line (\d+)', result.stderr)
    return int(match.group(1)) if match else None

def fix_line(lines, line_num):
    """Try to fix common syntax errors on a specific line"""
    if line_num <= 0 or line_num > len(lines):
        return False
    
    idx = line_num - 1  # Convert to 0-indexed
    line = lines[idx]
    original = line
    
    #Fix 1: Missing closing paren at end of line
    # Check for common patterns: addWidget(, setFont(, QLabel(, etc.
    patterns = [
        (r'(addWidget\([^)]+)$', r'\1)'),
        (r'(setFont\([^)]+)$', r'\1)'),
        (r'(QLabel\([^)]+)$', r'\1)'),
        (r'(setItem\([^)]*\([^)]*\))$', r'\1)'),
        (r'(insertLayout\([^)]+)$', r'\1)'),
        (r'(addLayout\([^)]+)$', r'\1)'),
        (r'(append\(\([^)]+\))$', r'\1)'),
        (r'(setStyleSheet\([^)]+)$', r'\1)'),
        (r'(QFont\([^)]+)$', r'\1)'),
    ]
    
    for pattern, replacement in patterns:
        line = re.sub(pattern, replacement, line)
    
    # Fix 2: f-string split across lines - merge with next line
    if re.search(r'f["\'][^"\']*\{\s*$', line) and idx + 1 < len(lines):
        # Merge with next line
        next_line = lines[idx + 1].strip()
        line = line.rstrip() + ' ' + next_line + '\n'
        lines[idx + 1] = ''  # Clear the next line
    
    if line != original:
        lines[idx] = line
        return True
    return False

def fix_file_iteratively(filepath, max_iterations=20):
    """Keep fixing until file compiles or max iterations reached"""
    for iteration in range(max_iterations):
        error_line = get_syntax_error_line(filepath)
        if error_line is None:
            return True, iteration  # File compiles!
        
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Try to fix the error line and surrounding lines
        fixed = False
        for offset in [0, -1, 1, -2, 2]:
            if fix_line(lines, error_line + offset):
                fixed = True
                break
        
        if not fixed:
            return False, iteration  # Can't fix this error
        
        # Write back
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines([l for l in lines if l])
    
    return False, max_iterations  # Max iterations reached

# Process files
broken_files = []
with open('l:/limo/broken_list.txt', 'r') as f:
    broken_files = [line.strip() for line in f if line.strip()]

desktop_app = Path("l:/limo/desktop_app")
fixed_count = 0
failed = []

for filename in broken_files:
    filepath = desktop_app / filename
    if not filepath.exists():
        continue
    
    success, iterations = fix_file_iteratively(filepath)
    if success:
        print(f"FIXED {filename} (fixed in {iterations} iterations)")
        fixed_count += 1
    else:
        print(f"FAILED {filename} (gave up after {iterations} attempts)")
        failed.append(filename)

print(f"\nFIXED: {fixed_count} files")
print(f"FAILED: {len(failed)} files")
if failed:
    print("\nStill broken:")
    for f in failed[:10]:
        print(f"  - {f}")
