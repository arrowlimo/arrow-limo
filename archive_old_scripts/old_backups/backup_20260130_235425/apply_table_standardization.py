#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Apply standardized column widths to all table widgets in desktop app.
"""

import os
import re
from pathlib import Path

# Standard column widths
COLUMN_WIDTHS = {
    'ID': 60,
    'Date': 100,
    'Amount': 110,
    'Paid': 110,
    'Balance': 110,
    'Running Balance': 130,
    'Status': 80,
    'Revenue': 110,
    'Expenses': 110,
    'Cost': 110,
    'Total': 110,
    'Payment': 110,
    'Invoice #': 120,
    'Booking ID': 100,
    'Request ID': 90,
    'Charter ID': 90,
    'Customer': 150,
    'Vehicle': 120,
    'Driver': 120,
    'Vendor': 150,
    'Description': 200,
}

def generate_width_code(table_var, headers_list):
    """Generate code to set column widths"""
    lines = []
    lines.append(f"        header = {table_var}.horizontalHeader()")
    
    for idx, header in enumerate(headers_list):
        header = header.strip()
        if header in COLUMN_WIDTHS:
            width = COLUMN_WIDTHS[header]
            lines.append(f"        header.setSectionResizeMode({idx}, QHeaderView.ResizeMode.Fixed)")
            lines.append(f"        header.setColumnWidth({idx}, {width})")
        else:
            lines.append(f"        header.setSectionResizeMode({idx}, QHeaderView.ResizeMode.Stretch)")
    
    return '\n'.join(lines)

def process_file(file_path):
    """Process a single file and add column width standardization"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    changes_made = 0
    
    # Pattern to find: table_var.setHorizontalHeaderLabels([...])
    # Followed by NOT already having header width code
    pattern = r'([ ]+)(self\.\w+|[\w_]+)\s*=\s*QTableWidget\(\).*?\n(.*?)\2\.setHorizontalHeaderLabels\(\[(.*?)\]\)'
    
    def replace_table(match):
        nonlocal changes_made
        indent = match.group(1)
        table_var = match.group(2)
        between = match.group(3)
        headers_str = match.group(4)
        
        # Parse headers
        headers_list = []
        for h in re.findall(r'["\']([^"\']+)["\']', headers_str):
            headers_list.append(h)
        
        # Check if width code already exists nearby
        full_match = match.group(0)
        lines_after = content[match.end():match.end()+500]
        if 'horizontalHeader()' in lines_after[:200] or 'setSectionResizeMode' in lines_after[:200]:
            # Already has width code, skip
            return full_match
        
        # Generate new code
        width_code = generate_width_code(table_var, headers_list)
        
        # Build replacement
        replacement = match.group(0) + '\n' + width_code
        changes_made += 1
        return replacement
    
    # Apply replacements
    content = re.sub(pattern, replace_table, content, flags=re.DOTALL)
    
    if changes_made > 0:
        # Write back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ {file_path.name}: Applied {changes_made} table standardizations")
        return True
    else:
        print(f"⏭️  {file_path.name}: No changes needed")
        return False

def main():
    """Main function"""
    desktop_app_dir = Path(r'L:\limo\desktop_app')
    
    files_to_process = [
        'dashboards.py',
        'dashboards_phase4_5_6.py',
        'dashboards_phase10.py',
        'dashboards_phase11.py',
        'dashboards_phase12.py',
        'dashboards_phase13.py',
        'client_drill_down.py',
        'drill_down_widgets.py',
        'business_entity_drill_down.py',
        'asset_management_widget.py',
    ]
    
    print("=" * 80)
    print("APPLYING TABLE COLUMN WIDTH STANDARDIZATION")
    print("=" * 80)
    print(f"\nProcessing {len(files_to_process)} files...\n")
    
    success_count = 0
    for filename in files_to_process:
        file_path = desktop_app_dir / filename
        if file_path.exists():
            if process_file(file_path):
                success_count += 1
        else:
            print(f"❌ {filename}: File not found")
    
    print(f"\n{'=' * 80}")
    print(f"COMPLETE: Modified {success_count} files")
    print(f"{'=' * 80}")
    print("\n📋 Standard widths applied:")
    for col, width in sorted(COLUMN_WIDTHS.items()):
        print(f"   {col:20s} = {width}px")

if __name__ == '__main__':
    main()
