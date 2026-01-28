#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Standardize table column widths across all desktop app files.
Apply consistent widths for Date, Amount, Status, etc.
"""

import os
import re

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

def find_table_definitions(file_path):
    """Find all table definitions in a file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find patterns like: setHorizontalHeaderLabels([...])
    pattern = r'\.setHorizontalHeaderLabels\(\[(.*?)\]\)'
    matches = re.findall(pattern, content, re.DOTALL)
    
    return matches, content

def generate_column_width_code(headers):
    """Generate code for setting column widths"""
    # Parse header list
    headers_clean = [h.strip().strip('"').strip("'") for h in headers.split(',')]
    
    code_lines = []
    code_lines.append("        header = self.table.horizontalHeader()")  # Assuming 'table' variable
    
    for idx, header in enumerate(headers_clean):
        if header in COLUMN_WIDTHS:
            width = COLUMN_WIDTHS[header]
            code_lines.append(f"        header.setSectionResizeMode({idx}, QHeaderView.ResizeMode.Fixed)")
            code_lines.append(f"        header.setColumnWidth({idx}, {width})")
        else:
            # Stretch for unknown columns
            code_lines.append(f"        header.setSectionResizeMode({idx}, QHeaderView.ResizeMode.Stretch)")
    
    return '\n'.join(code_lines)

def process_file(file_path, dry_run=True):
    """Process a single file"""
    matches, content = find_table_definitions(file_path)
    
    if not matches:
        return False
    
    print(f"\n{'='*80}")
    print(f"File: {os.path.basename(file_path)}")
    print(f"{'='*80}")
    
    for match in matches[:5]:  # Limit to first 5 to avoid spam
        headers = match.strip()
        print(f"\nHeaders: {headers}")
        print("\nGenerated code:")
        print(generate_column_width_code(headers))
    
    if len(matches) > 5:
        print(f"\n... and {len(matches) - 5} more table(s)")
    
    return True

def main():
    """Main function"""
    desktop_app_dir = r'L:\limo\desktop_app'
    
    print("=" * 80)
    print("TABLE COLUMN WIDTH STANDARDIZATION ANALYSIS")
    print("=" * 80)
    
    files_to_check = [
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
    
    processed_count = 0
    
    for filename in files_to_check:
        file_path = os.path.join(desktop_app_dir, filename)
        if os.path.exists(file_path):
            if process_file(file_path, dry_run=True):
                processed_count += 1
    
    print(f"\n{'='*80}")
    print(f"SUMMARY: Found table definitions in {processed_count} files")
    print(f"{'='*80}")
    print("\nStandard widths to apply:")
    for col, width in sorted(COLUMN_WIDTHS.items()):
        print(f"  {col:20s} = {width}px")
    
    print("\n💡 To apply these changes, we need to:")
    print("   1. Find each table widget initialization")
    print("   2. Add header width code after setHorizontalHeaderLabels()")
    print("   3. Replace any existing .Stretch mode with specific widths")
    print("\n⚠️  This is a DRY RUN - no files modified")

if __name__ == '__main__':
    main()
