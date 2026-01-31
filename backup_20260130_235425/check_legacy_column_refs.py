#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Step 2: Check which legacy-only columns are actually being queried/updated in code.
"""
import os
import re

legacy_only_cols = {
    'limo_clients': [
        'address_line2', 'attention', 'cell_phone', 'contact_person', 
        'created_date', 'cross_street', 'data_issues', 'department', 
        'fax_phone', 'home_phone', 'map_reference', 'primary_address', 
        'service_preferences', 'work_phone'
    ],
    'lms_customers_enhanced': [
        'account_no', 'account_type', 'additional_addresses', 'address_line2',
        'admin_contacts', 'attention', 'cell_phone', 'fax_phone',
        'full_name_search', 'home_phone', 'primary_name', 'work_phone'
    ]
}

print("="*80)
print("STEP 2: CODE REFERENCE ANALYSIS")
print("="*80)

# Search Python files for references to these columns
search_dirs = ['desktop_app', 'scripts', 'modern_backend']
found_refs = {}

for table, cols in legacy_only_cols.items():
    found_refs[table] = {}
    for col in cols:
        found_refs[table][col] = []

for dir_name in search_dirs:
    if not os.path.exists(dir_name):
        continue
    
    for root, dirs, files in os.walk(dir_name):
        for file in files:
            if not file.endswith('.py'):
                continue
            
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                for table, cols in legacy_only_cols.items():
                    for col in cols:
                        # Search for column references
                        patterns = [
                            f"['\\\"]?{col}['\\\"]?",  # column name
                            f"\.{col}",                 # attribute access
                            f"{col}\s*[=:]",           # assignment
                        ]
                        
                        for pattern in patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                found_refs[table][col].append(filepath)
                                break
            except Exception as e:
                pass

print("\n📌 COLUMN USAGE IN APPLICATION CODE:")
print("-" * 80)

for table, cols in legacy_only_cols.items():
    print(f"\n{table}:")
    has_refs = False
    for col in sorted(cols):
        refs = found_refs[table][col]
        if refs:
            has_refs = True
            print(f"  ❌ {col:<25} - USED IN: {', '.join(set(refs))[:60]}...")
    if not has_refs:
        print(f"  ✅ No columns from this table are referenced in code")
