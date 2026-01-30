#!/usr/bin/env python3
"""
Column Update Mechanism Audit
Verifies that every database column that needs updating has a corresponding
input field or update mechanism in the desktop app
"""

import psycopg2
import os
import re
from pathlib import Path
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REDACTED***')
    )

def get_core_table_columns():
    """Get columns from core tables that typically need updating"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    core_tables = ['charters', 'clients', 'employees', 'vehicles', 'payments', 
                   'receipts', 'driver_payroll', 'banking_transactions']
    
    schema = {}
    for table in core_tables:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s ORDER BY ordinal_position
        """, (table,))
        schema[table] = [row[0] for row in cur.fetchall()]
    
    cur.close()
    conn.close()
    return schema

def find_update_mechanisms(py_dir):
    """Find all UPDATE statements and input widgets in desktop_app"""
    
    update_columns = defaultdict(set)  # table -> set of columns being updated
    input_widgets = defaultdict(set)   # column_name -> set of widget types found
    
    py_files = list(Path(py_dir).glob("*.py"))
    
    for py_file in py_files:
        try:
            with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except:
            continue
        
        # Find UPDATE statements
        update_pattern = r'UPDATE\s+(\w+)\s+SET\s+([^W]+?)(?:WHERE|;|$)'
        update_matches = re.findall(update_pattern, content, re.IGNORECASE)
        
        for table, set_clause in update_matches:
            # Extract column names from SET clause
            cols = re.findall(r'(\w+)\s*=', set_clause)
            for col in cols:
                if col not in ['CASE', 'WHEN', 'THEN', 'ELSE', 'END']:
                    update_columns[table].add(col)
        
        # Find INSERT statements
        insert_pattern = r'INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)'
        insert_matches = re.findall(insert_pattern, content, re.IGNORECASE)
        
        for table, columns_str in insert_matches:
            cols = [c.strip() for c in columns_str.split(',')]
            for col in cols:
                update_columns[table].add(col)
        
        # Find input widget patterns
        # QLineEdit, QTextEdit, QComboBox, QDateEdit, QDoubleSpinBox, QCheckBox
        widget_pattern = r'(QLineEdit|QTextEdit|QComboBox|QDateEdit|QDoubleSpinBox|QCheckBox|QSpinBox)\(\)'
        widgets = re.findall(widget_pattern, content)
        
        # Try to associate with column names via variable names
        var_pattern = r'self\.(\w+(?:_input|_edit|_combo|_check|_box))\s*=\s*(QLineEdit|QTextEdit|QComboBox|QDateEdit|QDoubleSpinBox|QCheckBox|QSpinBox)'
        var_matches = re.findall(var_pattern, content)
        
        for var_name, widget_type in var_matches:
            # Try to infer column name from variable
            col_name = var_name.replace('_input', '').replace('_edit', '').replace('_combo', '').replace('_check', '').replace('_box', '')
            input_widgets[col_name].add(widget_type)
    
    return update_columns, input_widgets

def main():
    print("Auditing column update mechanisms...")
    
    schema = get_core_table_columns()
    update_cols, input_widgets = find_update_mechanisms("l:\\limo\\desktop_app")
    
    output_file = "l:\\limo\\reports\\column_update_audit.txt"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
        f.write("="*100 + "\n")
        f.write("COLUMN UPDATE MECHANISM AUDIT\n")
        f.write("Verifies every updateable column has a UI input field\n")
        f.write("="*100 + "\n\n")
        
        # Categories
        categories = {
            'Identity/Key': ['id', '_id', 'number', 'code'],
            'Name/Text': ['name', 'title', 'description', 'notes', 'address', 'phone', 'email'],
            'Financial': ['amount', 'price', 'rate', 'balance', 'pay', 'gross', 'net', 'total', 'cost', 'fee', 'tax', 'gst'],
            'Date/Time': ['date', 'time', 'start', 'end', 'expiry', 'expires', 'valid', 'issued'],
            'Status/Category': ['status', 'type', 'category', 'class', 'kind', 'state'],
            'Flags/Boolean': ['is_', 'active', 'enabled', 'required', 'exempt', 'paid'],
            'System': ['created_at', 'updated_at', 'created_by', 'updated_by']
        }
        
        def categorize_column(col):
            col_lower = col.lower()
            for cat, keywords in categories.items():
                if any(kw in col_lower for kw in keywords):
                    return cat
            return 'Other'
        
        # Analyze each core table
        total_cols = 0
        total_updateable = 0
        total_with_ui = 0
        
        for table in sorted(schema.keys()):
            columns = schema[table]
            table_updates = update_cols.get(table, set())
            
            f.write(f"\n{table.upper()}\n")
            f.write("="*100 + "\n")
            
            # Exclude system columns that don't need UI
            system_cols = {'id', 'created_at', 'updated_at', 'created_by', 'updated_by'}
            updateable = [c for c in columns if not any(sys in c.lower() for sys in system_cols)]
            
            has_ui = []
            no_ui = []
            
            for col in updateable:
                category = categorize_column(col)
                in_update = col in table_updates
                has_input = any(col.replace('_', '') in w or col in w for w in input_widgets.keys())
                
                if in_update or has_input:
                    has_ui.append((col, category, in_update))
                else:
                    no_ui.append((col, category))
            
            # Show columns WITH update mechanisms
            f.write(f"\n✅ UPDATEABLE ({len(has_ui)} columns with mechanisms)\n")
            f.write("-"*100 + "\n")
            
            by_category = defaultdict(list)
            for col, cat, in_update in has_ui:
                by_category[cat].append((col, '✓' if in_update else '?'))
            
            for cat in sorted(by_category.keys()):
                cols = by_category[cat]
                f.write(f"\n  {cat}:\n")
                for col, status in cols:
                    f.write(f"    {status} {col}\n")
            
            # Show columns WITHOUT update mechanisms (CRITICAL)
            if no_ui:
                f.write(f"\n❌ NOT UPDATEABLE ({len(no_ui)} columns - MISSING UI)\n")
                f.write("-"*100 + "\n")
                
                for col, cat in no_ui:
                    f.write(f"    ❌ {col:<40} ({cat})\n")
            
            total_cols += len(columns)
            total_updateable += len(updateable)
            total_with_ui += len(has_ui)
        
        # Summary
        f.write("\n\n" + "="*100 + "\n")
        f.write("SUMMARY\n")
        f.write("="*100 + "\n\n")
        
        f.write(f"Total core table columns: {total_cols}\n")
        f.write(f"Updateable columns (excluding system): {total_updateable}\n")
        f.write(f"With UI mechanisms: {total_with_ui}\n")
        f.write(f"Coverage: {100*total_with_ui//total_updateable if total_updateable else 0}%\n\n")
        
        if total_with_ui == total_updateable:
            f.write("✅ ALL UPDATEABLE COLUMNS HAVE UI MECHANISMS\n")
        else:
            missing = total_updateable - total_with_ui
            f.write(f"⚠️ {missing} columns missing UI input mechanisms\n")
    
    print(f"✅ Report saved to: {output_file}")
    
    # Print summary
    print(f"\nTotal core columns: {total_cols}")
    print(f"Updateable columns: {total_updateable}")
    print(f"With UI mechanisms: {total_with_ui}")
    print(f"Coverage: {100*total_with_ui//total_updateable if total_updateable else 0}%")

if __name__ == '__main__':
    main()
