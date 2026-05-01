"""
Audit script: for each key widget, verify SELECT/INSERT/UPDATE column names
exist in the actual schema, and flag mismatches.
"""
import psycopg2
import re
import os

conn = psycopg2.connect(
    host='localhost', port=5432, database='almsdata',
    user='postgres', password='ArrowLimousine'
)
cur = conn.cursor()

# Build schema map: table -> set of columns
cur.execute("""
    SELECT table_name, column_name
    FROM information_schema.columns
    WHERE table_schema = 'public'
    ORDER BY table_name, ordinal_position
""")
schema = {}
for table, col in cur.fetchall():
    schema.setdefault(table, set()).add(col)

cur.close()
conn.close()

DESKTOP_APP = r'l:\limo\desktop_app'
AUDIT_FILES = [
    'charter_form_widget.py',
    'improved_customer_widget.py',
    'employee_management_widget.py',
    'vehicle_management_widget.py',
    'manage_receipts_widget.py',
    'payment_dialog.py',
    'payroll_entry_widget.py',
    'vendor_invoice_manager.py',
    'manage_banking_widget.py',
    'checkbook_management_widget.py',
    'enhanced_employee_widget.py',
    'enhanced_vehicle_widget.py',
    'enhanced_client_widget.py',
]

# Pattern: find bare column references in SELECT/INSERT/UPDATE/SET clauses
# We look for "table.column" or standalone column names in SQL strings
SQL_BLOCK = re.compile(
    r'(?:SELECT|INSERT\s+INTO\s+\w+\s*\([^)]+\)|UPDATE\s+\w+\s+SET|FROM|WHERE|JOIN)'
    r'.{0,2000}?(?="""|\'\'\')' ,
    re.DOTALL | re.IGNORECASE
)

# Simpler: find all .execute( calls and extract the SQL string
EXECUTE_RE = re.compile(
    r'(?:cur(?:sor)?|cur\w*)\.execute\s*\(\s*(?:f?"""(.*?)"""|f?\'\'\'(.*?)\'\'\'|f?"(.*?)"|f?\'(.*?)\')',
    re.DOTALL
)

# Extract table.column or bare column after known keywords
COL_REF = re.compile(
    r'(?:SELECT|,|\bSET\b|\bWHERE\b|\bAND\b|\bOR\b|\bJOIN\b\s+\w+\s+ON\b)'
    r'\s+(?:\w+\.)?(\w+)\s*(?:=|,|FROM|WHERE|\)|$)',
    re.IGNORECASE
)

# Table name in FROM/INTO/UPDATE
TABLE_REF = re.compile(
    r'(?:FROM|INTO|UPDATE|JOIN)\s+(\w+)',
    re.IGNORECASE
)


def extract_sql_blocks(src):
    """Extract SQL strings from execute() calls."""
    blocks = []
    for m in EXECUTE_RE.finditer(src):
        sql = m.group(1) or m.group(2) or m.group(3) or m.group(4) or ''
        blocks.append(sql)
    return blocks


issues = []

for fname in AUDIT_FILES:
    fpath = os.path.join(DESKTOP_APP, fname)
    if not os.path.exists(fpath):
        print(f'MISSING FILE: {fname}')
        continue

    with open(fpath, encoding='utf-8', errors='ignore') as f:
        src = f.read()

    sql_blocks = extract_sql_blocks(src)

    for sql in sql_blocks:
        if not sql.strip():
            continue

        # Find tables referenced
        tables = [t.lower() for t in TABLE_REF.findall(sql)]
        tables = [t for t in tables if t in schema]

        if not tables:
            continue

        # Find explicit table.column references
        tc_re = re.compile(r'\b(\w+)\.(\w+)\b')
        for tbl, col in tc_re.findall(sql):
            tbl_l = tbl.lower()
            col_l = col.lower()
            if tbl_l in schema and col_l not in schema[tbl_l]:
                issues.append(
                    f'{fname}: {tbl}.{col} — column NOT in schema'
                    f' (table has {len(schema[tbl_l])} cols)'
                )

        # Find c.column_name style (common alias)
        alias_map = {'c': None, 'e': None, 'v': None, 'ch': None}
        # Try to infer alias -> table from "FROM charters c" etc.
        alias_re = re.compile(
            r'(?:FROM|JOIN)\s+(\w+)\s+(\w+)', re.IGNORECASE)
        for tbl, alias in alias_re.findall(sql):
            tbl_l = tbl.lower()
            if tbl_l in schema:
                alias_map[alias] = tbl_l

        for alias, tbl_l in alias_map.items():
            if not tbl_l:
                continue
            pat = re.compile(
                r'\b' + re.escape(alias) + r'\.(\w+)\b')
            for col in pat.findall(sql):
                col_l = col.lower()
                if col_l not in schema[tbl_l]:
                    issues.append(
                        f'{fname}: alias {alias}.{col} '
                        f'(table={tbl_l}) — column NOT in schema'
                    )

print(f'\n=== SCHEMA MISMATCH REPORT ===')
if issues:
    seen = set()
    for issue in issues:
        if issue not in seen:
            print(issue)
            seen.add(issue)
else:
    print('No explicit table.column mismatches detected.')

print(f'\nTables in schema: {len(schema)}')
print('Done.')
