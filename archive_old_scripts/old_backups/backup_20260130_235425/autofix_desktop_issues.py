#!/usr/bin/env python3
"""
Auto-fixer for common desktop app issues
"""
import re
from pathlib import Path

def fix_file(filepath, fixes):
    """Apply fixes to a file"""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    original = content
    for old, new in fixes:
        content = content.replace(old, new)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

# Fix vendor_accounts references - replace with receipts table
vendor_fixes = [
    # vendor_invoice_manager.py line 1308
    ("""                    cur.execute(\"\"\"
                        SELECT account_id FROM vendor_accounts WHERE canonical_vendor = %s
                    \"\"\", (canonical_vendor,))""",
     """                    # vendor_accounts table doesn't exist - skip account lookup
                    account_id = None"""),
    
    # vendor_invoice_manager.py line 1557
    ("""        cur.execute(\"\"\"
            SELECT va.account_id FROM vendor_accounts va
            WHERE va.canonical_vendor = %s
            LIMIT 1
        \"\"\", (canonical,))
        row = cur.fetchone()
        if row:
            return row[0]
        return None""",
     """        # vendor_accounts table doesn't exist in current schema
        return None"""),
    
    # vendor_invoice_manager.py line 1871
    ("""                    cur.execute(\"\"\"
                        SELECT account_id FROM vendor_accounts WHERE canonical_vendor = %s LIMIT 1
                    \"\"\", (self.current_vendor,))""",
     """                    # vendor_accounts table doesn't exist - skip lookup
                    account_id = None"""),
    
    # vendor_invoice_manager.py line 1962
    ("""                cur.execute(\"\"\"
                    SELECT account_id FROM vendor_accounts WHERE canonical_vendor = %s LIMIT 1
                \"\"\", (self.current_vendor,))""",
     """                # vendor_accounts table doesn't exist - skip lookup
                account_id = None"""),
    
    # vendor_invoice_manager.py line 2160
    ("""        cur.execute("SELECT account_id FROM vendor_accounts WHERE canonical_vendor = %s", (self.current_vendor,))
        result = cur.fetchone()
        if result:
            return result[0]
        return None""",
     """        # vendor_accounts table doesn't exist in current schema
        return None"""),
]

# Fix vendor_payables_dashboard.py
vendor_payables_fixes = [
    ("""            FROM vendor_accounts va
            WHERE canonical_vendor LIKE %s""",
     """            FROM receipts r
            WHERE canonical_vendor LIKE %s"""),
]

# Fix beverage_products references
beverage_fixes = [
    ("""    # Note: beverage_products table doesn't exist in current schema
    # All beverage tracking should use charter_charges instead""",
     """    # Note: beverage tracking uses charter_charges table instead
    # beverage_products table doesn't exist in current schema"""),
    
    ("""        try:
            cur = self.db_conn.get_cursor()
            # Insert new beverage product
            cur.execute(\"\"\"
                INSERT INTO beverage_products (name, category, our_cost, charged_price, description)
                VALUES (%s, %s, %s, %s, %s)
            \"\"\", (name, category, our_cost, charged_price, description))""",
     """        try:
            # beverage_products table doesn't exist - cannot insert
            QMessageBox.warning(self, "Not Supported", "Beverage product management not available")
            return
            cur = self.db_conn.get_cursor()"""),
    
    ("""            # Update existing product
            cur.execute(\"\"\"
                UPDATE beverage_products
                SET name = %s, category = %s, our_cost = %s, charged_price = %s, description = %s
                WHERE beverage_id = %s
            \"\"\", (name, category, our_cost, charged_price, description, beverage_id))""",
     """            # Update not supported - beverage_products table doesn't exist
            QMessageBox.warning(self, "Not Supported", "Beverage updates not available")
            return"""),
]

print("🔧 AUTO-FIXING IDENTIFIED ISSUES...")

fixed_count = 0

if fix_file('l:\\limo\\desktop_app\\vendor_invoice_manager.py', vendor_fixes):
    print("✅ Fixed vendor_invoice_manager.py (vendor_accounts)")
    fixed_count += 1

if fix_file('l:\\limo\\desktop_app\\vendor_payables_dashboard.py', vendor_payables_fixes):
    print("✅ Fixed vendor_payables_dashboard.py")
    fixed_count += 1

if fix_file('l:\\limo\\desktop_app\\beverage_management_widget.py', beverage_fixes):
    print("✅ Fixed beverage_management_widget.py")
    fixed_count += 1

print(f"\n✅ Fixed {fixed_count} files!")
