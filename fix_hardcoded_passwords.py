#!/usr/bin/env python3
"""Remove hardcoded database passwords from all Python files."""
import os
import re
from pathlib import Path

# Pattern to match hardcoded password
PATTERN = re.compile(
    r'(DB_PASSWORD\s*=\s*os\.environ\.get\(["\']DB_PASSWORD["\']\s*,\s*)["\']***REMOVED***["\'](\))',
    re.IGNORECASE
)

REPLACEMENT = r'\1os.environ.get("DB_PASSWORD")\2'

def fix_file(filepath):
    """Remove hardcoded password from a Python file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if file has hardcoded password
        if '***REMOVED***' not in content:
            return False
        
        # Replace hardcoded password
        new_content = PATTERN.sub(REPLACEMENT, content)
        
        # Also fix direct assignments
        new_content = new_content.replace(
            "DB_PASSWORD = os.environ.get('DB_PASSWORD')",
            "DB_PASSWORD = os.environ.get('DB_PASSWORD')"
        )
        new_content = new_content.replace(
            'DB_PASSWORD = os.environ.get("DB_PASSWORD")',
            'DB_PASSWORD = os.environ.get("DB_PASSWORD")'
        )
        
        if new_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"✅ Fixed: {filepath}")
            return True
        return False
    except Exception as e:
        print(f"❌ Error fixing {filepath}: {e}")
        return False

def main():
    """Scan and fix all Python files in the repository."""
    root = Path(__file__).parent
    fixed_count = 0
    
    for pyfile in root.rglob('*.py'):
        # Skip virtual environment and node_modules
        if '.venv' in str(pyfile) or 'node_modules' in str(pyfile):
            continue
        
        if fix_file(pyfile):
            fixed_count += 1
    
    print(f"\n✅ Fixed {fixed_count} files")
    print("\n⚠️  NEXT STEPS:")
    print("1. Set DB_PASSWORD environment variable")
    print("2. Change your local PostgreSQL password")
    print("3. Commit these changes")
    print("4. Consider the Neon password compromised if it was in .env.neon")

if __name__ == '__main__':
    main()
