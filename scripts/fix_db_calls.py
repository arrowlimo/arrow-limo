#!/usr/bin/env python3
"""
Fix all self.db.conn and self.db.connection calls to use self.db.commit/rollback
"""
import re
import glob
import os

desktop_app_dir = r"l:\limo\desktop_app"

files_to_check = [
    "drill_down_widgets.py",
    "client_drill_down.py",
    "admin_management_widget.py",
    "dispatch_management_widget.py",
    "document_management_widget.py",
    "employee_drill_down.py",
    "enhanced_employee_widget.py",
    "vehicle_drill_down.py"
]

pattern_commit = re.compile(r'self\.db\.conn\.commit\(\)')
pattern_rollback = re.compile(r'self\.db\.conn\.rollback\(\)')
pattern_connection_commit = re.compile(r'self\.db\.connection\.commit\(\)')
pattern_connection_rollback = re.compile(r'self\.db\.connection\.rollback\(\)')

total_fixed = 0

for filename in files_to_check:
    filepath = os.path.join(desktop_app_dir, filename)
    if not os.path.exists(filepath):
        print(f"⚠️  File not found: {filename}")
        continue
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Replace self.db.conn.commit() → self.db.commit()
    content = pattern_commit.sub('self.db.commit()', content)
    
    # Replace self.db.conn.rollback() → self.db.rollback()
    content = pattern_rollback.sub('self.db.rollback()', content)
    
    # Replace self.db.connection.commit() → self.db.commit()
    content = pattern_connection_commit.sub('self.db.commit()', content)
    
    # Replace self.db.connection.rollback() → self.db.rollback()
    content = pattern_connection_rollback.sub('self.db.rollback()', content)
    
    if content != original:
        changes = len(pattern_commit.findall(original)) + len(pattern_rollback.findall(original)) + \
                  len(pattern_connection_commit.findall(original)) + len(pattern_connection_rollback.findall(original))
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Fixed {filename}: {changes} occurrences")
        total_fixed += changes
    else:
        print(f"⏭️  No changes needed in {filename}")

print(f"\n✅ Total fixes applied: {total_fixed}")
