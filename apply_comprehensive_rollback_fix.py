"""
Comprehensive fix: Add transaction rollback protection to all database queries
Applies to all desktop_app widgets that query database without rollback
"""

import os
import re
from pathlib import Path

# Pattern to find methods that need rollback protection
PATTERN = re.compile(
    r'(    def (?:load_data|refresh|load_\w+)\(self\):.*?\n'
    r'(?:.*?\n)*?'  # Any docstring or comments
    r'        try:\n'
    r'            cur = self\.db\.get_cursor\(\))',
    re.MULTILINE | re.DOTALL
)

# Replacement with rollback protection
REPLACEMENT = r'''\1
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
                
            cur = self.db.get_cursor()'''

def fix_file(file_path):
    """Add rollback protection to a single file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if file needs fixing
        if 'cur = self.db.get_cursor()' not in content:
            return 0, "No database queries found"
        
        # Check if already has rollback protection
        if 'self.db.rollback()' in content and 'cur = self.db.get_cursor()' in content:
            # Count how many queries already have rollback
            rollback_count = content.count('self.db.rollback()')
            query_count = content.count('cur = self.db.get_cursor()')
            if rollback_count >= query_count:
                return 0, f"Already protected ({rollback_count}/{query_count})"
        
        original_content = content
        
        # Apply fix - simpler approach: find pattern and insert rollback
        lines = content.split('\n')
        new_lines = []
        i = 0
        fixes_applied = 0
        
        while i < len(lines):
            line = lines[i]
            new_lines.append(line)
            
            # Check if this is a database cursor line without prior rollback
            if 'cur = self.db.get_cursor()' in line and 'self.db' in line:
                # Check previous 10 lines for rollback
                start_check = max(0, i - 10)
                prior_lines = '\n'.join(lines[start_check:i])
                
                if 'self.db.rollback()' not in prior_lines:
                    # Insert rollback protection before this line
                    indent = len(line) - len(line.lstrip())
                    rollback_code = [
                        ' ' * indent + '# Rollback any failed transactions first',
                        ' ' * indent + 'try:',
                        ' ' * indent + '    self.db.rollback()',
                        ' ' * indent + 'except:',
                        ' ' * indent + '    pass',
                        ' ' * indent,
                    ]
                    # Insert before the cursor line
                    new_lines = new_lines[:-1] + rollback_code + [line]
                    fixes_applied += 1
            
            i += 1
        
        if fixes_applied > 0:
            new_content = '\n'.join(new_lines)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return fixes_applied, "Fixed"
        else:
            return 0, "No fixes needed"
            
    except Exception as e:
        return 0, f"Error: {e}"

def main():
    """Apply fixes to all desktop_app Python files"""
    desktop_app_dir = Path('l:/limo/desktop_app')
    
    # Find all Python files (excluding backups and __pycache__)
    python_files = []
    for py_file in desktop_app_dir.rglob('*.py'):
        if '__pycache__' not in str(py_file) and '.pyc' not in str(py_file):
            python_files.append(py_file)
    
    print(f"Found {len(python_files)} Python files in desktop_app/")
    print("=" * 80)
    
    total_fixes = 0
    fixed_files = []
    
    for py_file in sorted(python_files):
        rel_path = py_file.relative_to(desktop_app_dir.parent)
        fixes, status = fix_file(py_file)
        
        if fixes > 0:
            print(f"✅ {rel_path}: {fixes} queries protected")
            total_fixes += fixes
            fixed_files.append(str(rel_path))
        elif 'Error' in status:
            print(f"❌ {rel_path}: {status}")
        # Skip "already protected" and "no queries" messages for cleaner output
    
    print("=" * 80)
    print(f"\n📊 Summary:")
    print(f"  Total files processed: {len(python_files)}")
    print(f"  Files modified: {len(fixed_files)}")
    print(f"  Database queries protected: {total_fixes}")
    
    if fixed_files:
        print(f"\n📝 Modified files:")
        for f in fixed_files:
            print(f"  - {f}")
    
    return total_fixes

if __name__ == "__main__":
    fixes = main()
    print(f"\n{'='*80}")
    if fixes > 0:
        print(f"✅ Applied {fixes} rollback protections successfully!")
    else:
        print("ℹ️  No additional fixes needed - all queries already protected!")
