"""
Fix all actual column name errors found in the audit
"""
import re
from pathlib import Path

# Real column name fixes (not SQL expressions)
fixes = {
    # employees table
    'sin': 't4_sin',
    'address': 'street_address',
    'annual_salary': 'salary',
    
    # banking_transactions table  
    'trans_date': 'transaction_date',
    'trans_description': 'description',
    'balance_after': 'running_balance',
    
    # receipts table
    'trans_date': 'receipt_date',
    'trans_description': 'description',
    'transaction_id': 'receipt_id',
    
    # driver_payroll table
    'payroll_date': 'pay_date',
    
    # driver_hos_log table
    'log_date': 'start_time',  # or 'end_time', need to check context
}

desktop_app_dir = Path(r'L:\limo\desktop_app')
python_files = list(desktop_app_dir.glob('*.py'))

print("Files that need column name fixes:\n")

# Files with specific issues from audit
files_to_fix = {
    'employee_drill_down.py': [
        ('\\bsin\\b(?!\\s*\\()', 't4_sin'),  # sin -> t4_sin
        ('\\baddress\\b(?!\\s*[=!]|\\s+as\\s)', 'street_address'),  # address -> street_address (not in comparisons)
        ('\\bannual_salary\\b', 'salary'),  # annual_salary -> salary
    ],
    'main.py': [
        ('(?<!\\.)address\\b(?!\\s*[=!]|\\s+as\\s)', 'street_address'),
    ],
    'client_drill_down.py': [
        ('(?<!\\.)address\\b(?!\\s*[=!]|\\s+as\\s)', 'street_address'),
    ],
    'drill_down_widgets.py': [
        ('(?<!\\.)address\\b(?!\\s*[=!]|\\s+as\\s)', 'street_address'),
    ],
    'business_entity_drill_down.py': [
        ('(?<!\\.)address\\b(?!\\s*[=!]|\\s+as\\s)', 'street_address'),
    ],
    'dispatch_management_widget.py': [
        ('(?<!\\.)address\\b(?!\\s*[=!]|\\s+as\\s)', 'street_address'),
    ],
    'dashboards_phase13.py': [
        ('(?<!\\.)address\\b(?!\\s*[=!]|\\s+as\\s)', 'street_address'),
    ],
    'dashboards_phase14.py': [
        ('(?<!\\.)address\\b(?!\\s*[=!]|\\s+as\\s)', 'street_address'),
    ],
}

for filename, replacements in files_to_fix.items():
    filepath = desktop_app_dir / filename
    if not filepath.exists():
        print(f"⚠️  {filename} not found")
        continue
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    changes = []
    
    for pattern, replacement in replacements:
        # Only replace in SQL queries (between triple quotes)
        def replace_in_sql(match):
            sql = match.group(0)
            modified = re.sub(pattern, replacement, sql)
            if modified != sql:
                changes.append(f"{pattern} -> {replacement}")
            return modified
        
        content = re.sub(r'""".*?"""', replace_in_sql, content, flags=re.DOTALL)
        content = re.sub(r"'''.*?'''", replace_in_sql, content, flags=re.DOTALL)
    
    if content != original:
        print(f"✏️  {filename}: {len(changes)} changes")
        for change in set(changes):
            print(f"    • {change}")
        
        # Uncomment to apply fixes
        # with open(filepath, 'w', encoding='utf-8') as f:
        #     f.write(content)

print("\n" + "="*80)
print("Preview complete. To apply fixes, uncomment the write section.")
print("="*80)
