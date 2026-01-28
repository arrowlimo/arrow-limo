"""
Audit all SQL queries in desktop_app to verify column names match database schema
"""
import psycopg2
import re
import os
from pathlib import Path
from collections import defaultdict

# Connect to database
conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Get all table schemas
print("Loading database schemas...")
cur.execute("""
    SELECT table_name, column_name 
    FROM information_schema.columns 
    WHERE table_schema = 'public'
    ORDER BY table_name, ordinal_position
""")

schemas = defaultdict(set)
for table, column in cur.fetchall():
    schemas[table].add(column.lower())

print(f"Loaded {len(schemas)} tables\n")

# Find all Python files in desktop_app
desktop_app_dir = Path(r'L:\limo\desktop_app')
python_files = list(desktop_app_dir.glob('*.py'))

print(f"Scanning {len(python_files)} Python files...\n")

# Extract column references from SQL queries
errors = []
warnings = []

# Pattern to match SELECT statements
select_pattern = re.compile(
    r'SELECT\s+(.*?)\s+FROM\s+(\w+)',
    re.IGNORECASE | re.DOTALL
)

# Pattern to match WHERE/ORDER BY/GROUP BY clauses
where_pattern = re.compile(
    r'(?:WHERE|ORDER BY|GROUP BY|HAVING|JOIN \w+ ON)\s+(.*?)(?:ORDER BY|GROUP BY|LIMIT|OFFSET|;|$|"""|\'\'\')' ,
    re.IGNORECASE | re.DOTALL
)

for py_file in python_files:
    with open(py_file, 'r', encoding='utf-8') as f:
        try:
            content = f.read()
        except:
            continue
    
    # Find all SQL queries (in triple quotes or single quotes)
    sql_queries = re.findall(r'"""(.*?)"""|\'\'\'(.*?)\'\'\'', content, re.DOTALL)
    
    for query_tuple in sql_queries:
        query = query_tuple[0] or query_tuple[1]
        
        if 'SELECT' not in query.upper() and 'INSERT' not in query.upper() and 'UPDATE' not in query.upper():
            continue
        
        # Extract table name and columns from SELECT
        select_matches = select_pattern.findall(query)
        
        for columns_str, table_name in select_matches:
            table_name_lower = table_name.lower()
            
            # Skip if table doesn't exist
            if table_name_lower not in schemas:
                warnings.append(f"{py_file.name}: Unknown table '{table_name}'")
                continue
            
            # Parse column list
            columns_str = columns_str.strip()
            
            # Skip if using SELECT *
            if columns_str == '*':
                continue
            
            # Split by comma, handling nested functions/subqueries
            columns = []
            paren_depth = 0
            current_col = []
            
            for char in columns_str:
                if char == '(':
                    paren_depth += 1
                    current_col.append(char)
                elif char == ')':
                    paren_depth -= 1
                    current_col.append(char)
                elif char == ',' and paren_depth == 0:
                    columns.append(''.join(current_col).strip())
                    current_col = []
                else:
                    current_col.append(char)
            
            if current_col:
                columns.append(''.join(current_col).strip())
            
            # Check each column
            for col_expr in columns:
                # Extract column name (handle AS aliases, table prefixes, functions)
                col_expr = col_expr.strip()
                
                # Skip aggregate functions, literals, etc.
                if any(x in col_expr.upper() for x in ['COUNT(', 'SUM(', 'AVG(', 'MAX(', 'MIN(', 'COALESCE(', 'CAST(', 'EXTRACT(', 'CASE ', 'NULL', 'CURRENT_', 'NOW(', 'DISTINCT ']):
                    continue
                
                # Handle "column AS alias"
                if ' AS ' in col_expr.upper():
                    col_expr = col_expr.split(' AS ')[0].strip()
                
                # Handle "table.column"
                if '.' in col_expr:
                    parts = col_expr.split('.')
                    col_expr = parts[-1].strip()
                
                # Remove quotes
                col_expr = col_expr.replace('"', '').replace("'", '')
                
                # Skip if it's an expression or function
                if '(' in col_expr or ')' in col_expr or '+' in col_expr or '-' in col_expr or '*' in col_expr or '/' in col_expr:
                    continue
                
                col_name_lower = col_expr.lower().strip()
                
                # Check if column exists in table
                if col_name_lower and col_name_lower not in schemas[table_name_lower]:
                    errors.append(f"{py_file.name}: Table '{table_name}' has no column '{col_expr}'")

# Also check for known problematic patterns
print("Checking for known problematic patterns...")
problematic_patterns = [
    (r'\bsin\b(?!\s*\()', 'sin', 't4_sin', 'employees'),
    (r'\bpayroll_date\b', 'payroll_date', 'pay_date', 'driver_payroll'),
    (r'\bannual_salary\b', 'annual_salary', 'salary', 'employees'),
    (r'\baddress\b(?!\s*=\s*NULL)', 'address', 'street_address', 'employees'),
    (r'\btotal_price\b', 'total_price', 'total_amount_due', 'charters'),
]

for py_file in python_files:
    with open(py_file, 'r', encoding='utf-8') as f:
        try:
            content = f.read()
        except:
            continue
    
    for pattern, old_name, new_name, table_hint in problematic_patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            # Get line number
            line_num = content[:match.start()].count('\n') + 1
            errors.append(f"{py_file.name}:{line_num}: Use '{new_name}' instead of '{old_name}' (table: {table_hint})")

# Print results
print("\n" + "="*80)
print("AUDIT RESULTS")
print("="*80)

if errors:
    print(f"\n❌ ERRORS FOUND ({len(errors)}):\n")
    for error in sorted(set(errors)):
        print(f"  • {error}")
else:
    print("\n✅ No column name errors found!")

if warnings:
    print(f"\n⚠️  WARNINGS ({len(warnings)}):\n")
    for warning in sorted(set(warnings)):
        print(f"  • {warning}")

print("\n" + "="*80)

cur.close()
conn.close()
