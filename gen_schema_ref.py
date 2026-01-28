#!/usr/bin/env python3
"""Generate comprehensive database reference guide from actual schema."""

import psycopg2
from collections import defaultdict

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REMOVED***')
cur = conn.cursor()

# Get all tables
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    ORDER BY table_name
""")
tables = [row[0] for row in cur.fetchall()]

reference = defaultdict(dict)

for table in sorted(tables):
    # Get columns for this table
    cur.execute("""
        SELECT 
            column_name, 
            data_type, 
            is_nullable,
            column_default
        FROM information_schema.columns 
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table,))
    
    columns = []
    for col_name, data_type, is_nullable, col_default in cur.fetchall():
        columns.append({
            "name": col_name,
            "type": data_type,
            "nullable": is_nullable == 'YES',
            "default": col_default
        })
    
    # Get constraints
    cur.execute("""
        SELECT constraint_type, constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = %s
    """, (table,))
    
    constraints = []
    for constraint_type, constraint_name in cur.fetchall():
        constraints.append({
            "type": constraint_type,
            "name": constraint_name
        })
    
    reference[table] = {
        "columns": columns,
        "constraints": constraints
    }

cur.close()
conn.close()

# Generate markdown
with open('L:\\limo\\docs\\DATABASE_SCHEMA_REFERENCE.md', 'w') as f:
    f.write("# Arrow Limousine Database Schema Reference\n\n")
    f.write("**Last Updated:** 2026-01-21\n\n")
    f.write("## Critical Business Rules\n\n")
    f.write("### Primary Keys vs Business Keys\n")
    f.write("- **charter_id** → Primary key (relationship field) - DO NOT use for business logic\n")
    f.write("- **reserve_number** → Business key - USE this to identify charters\n")
    f.write("- **dispatch_id** → Primary key (relationship field) - DO NOT use for business logic\n")
    f.write("- **receipt_id** → Primary key (relationship field) - DO NOT use for business logic\n\n")
    f.write("### Golden Rules\n")
    f.write("1. **NEVER use ID fields for business logic** - They exist only for relationships\n")
    f.write("2. **ALWAYS use reserve_number** for charter-payment matching\n")
    f.write("3. **Reserve_number is the universal business key** across charters, payments, and charges\n")
    f.write("4. **Date fields are always YYYY-MM-DD format** in database\n")
    f.write("5. **Currency fields are DECIMAL(12,2)** - never store as strings\n\n")
    
    f.write("---\n\n")
    
    for table in sorted(reference.keys()):
        data = reference[table]
        f.write(f"## Table: `{table}`\n\n")
        
        f.write("### Columns\n\n")
        f.write("| Column | Type | Nullable | Notes |\n")
        f.write("|--------|------|----------|-------|\n")
        
        for col in data['columns']:
            nullable = "Yes" if col['nullable'] else "No"
            default = f"DEFAULT {col['default']}" if col['default'] else ""
            f.write(f"| `{col['name']}` | `{col['type']}` | {nullable} | {default} |\n")
        
        if data['constraints']:
            f.write("\n### Constraints\n\n")
            for constraint in data['constraints']:
                f.write(f"- {constraint['type']}: {constraint['name']}\n")
        
        f.write("\n")

print("✅ Database schema reference generated: docs/DATABASE_SCHEMA_REFERENCE.md")
