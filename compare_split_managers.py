"""Compare the backup (fixed) vs active split_receipt_manager_dialog.py"""

import os

backup_path = r"l:\limo\archive_old_scripts\old_backups\backup_20260130_235425\split_receipt_manager_dialog.py"
active_path = r"l:\limo\desktop_app\split_receipt_manager_dialog.py"

print("=" * 80)
print("COMPARISON: Fixed Backup vs Active Desktop App")
print("=" * 80)

# Read both files
with open(backup_path, 'r', encoding='utf-8') as f:
    backup_content = f.read()

with open(active_path, 'r', encoding='utf-8') as f:
    active_content = f.read()

print(f"\n📊 File Sizes:")
print(f"   Fixed Backup: {len(backup_content):,} chars, {backup_content.count(chr(10))} lines")
print(f"   Active:       {len(active_content):,} chars, {active_content.count(chr(10))} lines")

print(f"\n🔍 Key Differences:")

# Check for our fixes in each
fixes_to_check = {
    "STYLE_ERROR_LABEL": "String constant extraction",
    "_extract_split_row_data": "Helper method for row data",
    "_create_child_receipt": "Helper method for child receipts", 
    "_cleanup_original_receipt": "Helper method for cleanup",
    "except Exception:": "Proper exception handling",
}

print(f"\n✅ Fixes in BACKUP (archive):")
for pattern, desc in fixes_to_check.items():
    if pattern in backup_content:
        print(f"   ✅ {desc}")

print(f"\n❓ Fixes in ACTIVE (desktop_app):")
for pattern, desc in fixes_to_check.items():
    if pattern in active_content:
        print(f"   ✅ {desc}")
    else:
        print(f"   ❌ MISSING: {desc}")

# Check for potential issues in active
issues_in_active = []

if "self.db.rollback()" in active_content:
    count = active_content.count("self.db.rollback()")
    issues_in_active.append(f"Uses 'self.db.rollback()' {count} time(s) - should be 'self.conn.rollback()'")

print(f"\n⚠️  Potential Issues in ACTIVE version:")
if issues_in_active:
    for issue in issues_in_active:
        print(f"   ⚠️  {issue}")
else:
    print(f"   ✅ No obvious issues detected")

# Check table differences
if "receipt_splits" in backup_content and "receipt_gl_splits" in active_content:
    print(f"\n📋 Table Usage:")
    print(f"   Backup:  Uses 'receipt_splits' table")
    print(f"   Active:  Uses 'receipt_gl_splits' table")
    print(f"   Note: Different data models - active version may be newer")

print("\n" + "=" * 80)
print("RECOMMENDATION")
print("=" * 80)
print("""
The ACTIVE desktop_app version appears to be a different/newer implementation.
It has some similar issues (self.db.rollback) but uses different database tables.

Options:
1. Keep both versions separate (backup is archived, active continues)
2. Apply our refactoring improvements to active version (extract helper methods)
3. Fix only the critical bugs in active version (self.db.rollback errors)
""")
