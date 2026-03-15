"""
Fix desktop_app import prefixes
When running from within the desktop_app folder, imports should not use the desktop_app. prefix
"""
import os
import re
from pathlib import Path

desktop_app_path = Path("L:/limo/desktop_app")

# Pattern to match: from desktop_app.module_name import
pattern = re.compile(r'^(\s*)from desktop_app\.([a-zA-Z0-9_]+) import', re.MULTILINE)

fixed_count = 0
file_count = 0

for py_file in desktop_app_path.glob("*.py"):
    try:
        content = py_file.read_text(encoding='utf-8')
        original = content
        
        # Replace desktop_app.module with just module
        content = pattern.sub(r'\1from \2 import', content)
        
        if content != original:
            py_file.write_text(content, encoding='utf-8')
            matches = len(pattern.findall(original))
            fixed_count += matches
            file_count += 1
            print(f"✓ Fixed {matches} imports in {py_file.name}")
    
    except Exception as e:
        print(f"✗ Error processing {py_file.name}: {e}")

print(f"\n{'='*60}")
print(f"Fixed {fixed_count} imports in {file_count} files")
print(f"{'='*60}")
