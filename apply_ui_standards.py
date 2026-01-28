"""
UI Improvement Auto-Applier
Automatically updates widgets to use new UI standards
"""

import re
import os
from pathlib import Path


DESKTOP_APP_DIR = Path("L:/limo/desktop_app")


def apply_ui_standards_to_file(filepath):
    """
    Apply UI standards to a single widget file
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    changes_made = []
    
    # 1. Add imports if not present
    if 'from desktop_app.ui_standards import' not in content:
        # Find last PyQt6 import
        import_pattern = r'(from PyQt6\.QtWidgets import.*?\))'
        match = re.search(import_pattern, content, re.DOTALL)
        if match:
            end_pos = match.end()
            ui_import = '\nfrom desktop_app.ui_standards import (\n    setup_standard_table, SmartFormField, enable_fuzzy_search,\n    make_read_only_table, TabOrderManager\n)'
            content = content[:end_pos] + ui_import + content[end_pos:]
            changes_made.append("Added ui_standards import")
    
    # 2. Replace manual table column setup with setup_standard_table
    # Pattern: table.setColumnCount(...) followed by setHorizontalHeaderLabels
    table_pattern = r'(\w+)\.setColumnCount\((\d+)\)\s+\1\.setHorizontalHeaderLabels\(\[(.*?)\]\)'
    
    def replace_table_setup(match):
        table_name = match.group(1)
        headers_str = match.group(3)
        # Extract header names
        headers = re.findall(r'"([^"]+)"', headers_str)
        
        replacement = f'''setup_standard_table({table_name}, 
            [{", ".join(f'"{h}"' for h in headers)}]
        )'''
        changes_made.append(f"Converted {table_name} to smart table")
        return replacement
    
    content = re.sub(table_pattern, replace_table_setup, content, flags=re.DOTALL)
    
    # 3. Replace manual column width settings that follow old patterns
    # Remove setSectionResizeMode and setColumnWidth calls
    content = re.sub(r'\s+header\s*=\s*\w+\.horizontalHeader\(\)\s*\n', '', content)
    content = re.sub(r'\s+header\.setSectionResizeMode\([^)]+\)\s*\n', '', content)
    content = re.sub(r'\s+\w+\.setColumnWidth\([^)]+\)\s*\n', '', content)
    
    # 4. Replace QLineEdit phone fields
    phone_pattern = r'self\.(\w*phone\w*)\s*=\s*QLineEdit\(\)'
    content = re.sub(phone_pattern, r'self.\1 = SmartFormField.phone_field()', content)
    if re.search(phone_pattern, original_content):
        changes_made.append("Converted phone fields to SmartFormField")
    
    # 5. Replace QLineEdit email fields
    email_pattern = r'self\.(\w*email\w*)\s*=\s*QLineEdit\(\)'
    content = re.sub(email_pattern, r'self.\1 = SmartFormField.email_field()', content)
    if re.search(email_pattern, original_content):
        changes_made.append("Converted email fields to SmartFormField")
    
    # 6. Replace postal code fields
    postal_pattern = r'self\.(\w*postal\w*)\s*=\s*QLineEdit\(\)'
    content = re.sub(postal_pattern, r'self.\1 = SmartFormField.postal_code_field()', content)
    if re.search(postal_pattern, original_content):
        changes_made.append("Converted postal fields to SmartFormField")
    
    # 7. Replace QTextEdit notes with auto-expanding
    notes_pattern = r'self\.(\w*notes?\w*)\s*=\s*QTextEdit\(\)\s+self\.\1\.setMaximumHeight\((\d+)\)'
    content = re.sub(notes_pattern, r'self.\1 = SmartFormField.auto_expanding_text(max_height=\2)', content)
    if re.search(notes_pattern, original_content):
        changes_made.append("Converted notes fields to auto-expanding")
    
    # 8. Add make_read_only_table to tables that should be read-only
    # Look for tables that don't have any "clicked.connect" but might have "doubleClicked.connect"
    
    # Only write if changes were made
    if content != original_content:
        backup_path = filepath.with_suffix(filepath.suffix + '.bak')
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_content)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return changes_made
    
    return []


def scan_and_apply_all():
    """
    Scan all widget files and apply UI standards
    """
    results = {}
    
    # Find all Python files in desktop_app
    for py_file in DESKTOP_APP_DIR.glob("*.py"):
        # Skip certain files
        if py_file.name in ['__init__.py', 'ui_standards.py', 'main.py']:
            continue
        
        # Only process files that look like widgets
        if not any(x in py_file.name.lower() for x in ['widget', 'dialog', 'dashboard']):
            continue
        
        print(f"Processing: {py_file.name}")
        changes = apply_ui_standards_to_file(py_file)
        
        if changes:
            results[py_file.name] = changes
            print(f"  ✅ {len(changes)} changes made")
            for change in changes:
                print(f"     - {change}")
        else:
            print(f"  ⏭️  No changes needed")
    
    return results


def generate_report(results):
    """Generate a report of all changes made"""
    report = []
    report.append("=" * 80)
    report.append("UI STANDARDS AUTO-APPLICATION REPORT")
    report.append("=" * 80)
    report.append("")
    
    total_files = len(results)
    total_changes = sum(len(changes) for changes in results.values())
    
    report.append(f"Files Modified: {total_files}")
    report.append(f"Total Changes: {total_changes}")
    report.append("")
    report.append("=" * 80)
    report.append("")
    
    for filename, changes in sorted(results.items()):
        report.append(f"📄 {filename}")
        report.append("-" * 80)
        for change in changes:
            report.append(f"  ✓ {change}")
        report.append("")
    
    report.append("=" * 80)
    report.append("BACKUP FILES CREATED")
    report.append("=" * 80)
    report.append("All original files backed up with .bak extension")
    report.append("To restore: copy filename.py.bak to filename.py")
    report.append("")
    
    return "\n".join(report)


if __name__ == '__main__':
    print("🔧 UI Standards Auto-Applier")
    print("=" * 80)
    print("This will automatically update widget files to use new UI standards:")
    print("  - Smart table column sizing")
    print("  - Proper field widths (phone, email, postal)")
    print("  - Auto-expanding text fields")
    print("  - Read-only table configuration")
    print("")
    
    response = input("Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Aborted.")
        exit(0)
    
    print("")
    print("Scanning and applying standards...")
    print("")
    
    results = scan_and_apply_all()
    
    print("")
    print("=" * 80)
    print("COMPLETE!")
    print("=" * 80)
    
    report = generate_report(results)
    print(report)
    
    # Save report
    report_path = Path("L:/limo/UI_STANDARDS_APPLICATION_REPORT.txt")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"Report saved to: {report_path}")
