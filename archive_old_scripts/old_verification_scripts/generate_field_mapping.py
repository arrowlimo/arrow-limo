#!/usr/bin/env python3
"""
Generate comprehensive field mapping documentation for all database tables.
This will create TypeScript interfaces and Python Pydantic models from actual schema.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os
import json
from datetime import datetime

load_dotenv()

def postgres_to_typescript(pg_type):
    """Map PostgreSQL types to TypeScript"""
    mapping = {
        'integer': 'number',
        'bigint': 'number',
        'smallint': 'number',
        'numeric': 'number',
        'decimal': 'number',
        'real': 'number',
        'double precision': 'number',
        'character varying': 'string',
        'varchar': 'string',
        'char': 'string',
        'text': 'string',
        'boolean': 'boolean',
        'date': 'string',  # ISO date string
        'timestamp': 'string',  # ISO datetime string
        'time': 'string',  # HH:MM:SS
        'json': 'any',
        'jsonb': 'any',
        'uuid': 'string'
    }
    
    pg_lower = pg_type.lower()
    for pg, ts in mapping.items():
        if pg in pg_lower:
            return ts
    return 'any'

def postgres_to_python(pg_type):
    """Map PostgreSQL types to Python"""
    mapping = {
        'integer': 'int',
        'bigint': 'int',
        'smallint': 'int',
        'numeric': 'Decimal',
        'decimal': 'Decimal',
        'real': 'float',
        'double precision': 'float',
        'character varying': 'str',
        'varchar': 'str',
        'char': 'str',
        'text': 'str',
        'boolean': 'bool',
        'date': 'date',
        'timestamp': 'datetime',
        'time': 'time',
        'json': 'dict',
        'jsonb': 'dict',
        'uuid': 'str'
    }
    
    pg_lower = pg_type.lower()
    for pg, py in mapping.items():
        if pg in pg_lower:
            return py
    return 'str'

def generate_field_mapping():
    """Generate comprehensive field mapping documentation"""
    
    print("=" * 80)
    print("GENERATING FIELD MAPPING DOCUMENTATION")
    print("=" * 80)
    print()
    
    neon_conn = psycopg2.connect(os.getenv("NEON_DATABASE_URL"))
    
    # Key tables to map
    tables = [
        'charters', 'clients', 'payments', 'receipts', 
        'vehicles', 'employees', 'banking_receipt_matching_ledger',
        'chart_of_accounts', 'split_run_segments', 'beverage_orders'
    ]
    
    mapping = {}
    
    print("📊 Extracting schema from Neon database...")
    print()
    
    for table in tables:
        try:
            with neon_conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT 
                        column_name,
                        data_type,
                        is_nullable,
                        column_default,
                        character_maximum_length
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = %s
                    ORDER BY ordinal_position
                """, (table,))
                
                fields = cur.fetchall()
                mapping[table] = fields
                print(f"✅ {table}: {len(fields)} fields")
        except Exception as e:
            print(f"⚠️  {table}: Error - {e}")
    
    print()
    print("=" * 80)
    print("GENERATING OUTPUT FILES")
    print("=" * 80)
    print()
    
    # Save to JSON
    json_file = f'FIELD_MAPPING_COMPLETE_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(json_file, 'w') as f:
        json.dump(mapping, f, indent=2, default=str)
    print(f"✅ {json_file}")
    
    # Generate TypeScript interfaces
    ts_file = generate_typescript_interfaces(mapping)
    print(f"✅ {ts_file}")
    
    # Generate Python Pydantic models
    py_file = generate_pydantic_models(mapping)
    print(f"✅ {py_file}")
    
    # Generate markdown documentation
    md_file = generate_markdown_docs(mapping)
    print(f"✅ {md_file}")
    
    print()
    print("=" * 80)
    print("✅ FIELD MAPPING GENERATION COMPLETE")
    print("=" * 80)
    
    neon_conn.close()

def generate_typescript_interfaces(mapping):
    """Generate TypeScript interfaces from actual database schema"""
    output = [
        "// AUTO-GENERATED TypeScript interfaces from database schema",
        f"// Generated: {datetime.now().isoformat()}",
        "// DO NOT EDIT MANUALLY - regenerate using generate_field_mapping.py",
        ""
    ]
    
    for table, fields in sorted(mapping.items()):
        # Convert table_name to TableName (PascalCase)
        interface_name = ''.join(word.capitalize() for word in table.split('_'))
        
        output.append(f"export interface {interface_name} {{")
        
        for field in fields:
            ts_type = postgres_to_typescript(field['data_type'])
            nullable = '?' if field['is_nullable'] == 'YES' else ''
            
            # Add comment with SQL type
            comment = f"  // {field['data_type']}"
            if field['character_maximum_length']:
                comment += f"({field['character_maximum_length']})"
            
            output.append(f"  {field['column_name']}{nullable}: {ts_type};{comment}")
        
        output.append("}")
        output.append("")
    
    filename = f'database_types_{datetime.now().strftime("%Y%m%d_%H%M%S")}.ts'
    with open(filename, 'w') as f:
        f.write('\n'.join(output))
    
    return filename

def generate_pydantic_models(mapping):
    """Generate Pydantic models from actual database schema"""
    output = [
        "# AUTO-GENERATED Pydantic models from database schema",
        f"# Generated: {datetime.now().isoformat()}",
        "# DO NOT EDIT MANUALLY - regenerate using generate_field_mapping.py",
        "",
        "from pydantic import BaseModel",
        "from typing import Optional",
        "from decimal import Decimal",
        "from datetime import date, time, datetime",
        ""
    ]
    
    for table, fields in sorted(mapping.items()):
        # Convert table_name to TableName (PascalCase)
        class_name = ''.join(word.capitalize() for word in table.split('_'))
        
        output.append(f"class {class_name}(BaseModel):")
        
        if not fields:
            output.append("    pass")
        else:
            for field in fields:
                py_type = postgres_to_python(field['data_type'])
                
                if field['is_nullable'] == 'YES':
                    field_def = f"Optional[{py_type}] = None"
                else:
                    field_def = py_type
                
                # Add comment with SQL type
                comment = f"  # {field['data_type']}"
                if field['character_maximum_length']:
                    comment += f"({field['character_maximum_length']})"
                
                output.append(f"    {field['column_name']}: {field_def}{comment}")
        
        output.append("")
    
    filename = f'database_models_{datetime.now().strftime("%Y%m%d_%H%M%S")}.py'
    with open(filename, 'w') as f:
        f.write('\n'.join(output))
    
    return filename

def generate_markdown_docs(mapping):
    """Generate human-readable markdown documentation"""
    output = [
        "# Database Schema Field Reference",
        f"**Generated:** {datetime.now().isoformat()}",
        "",
        "Complete field listing for all database tables.",
        ""
    ]
    
    for table, fields in sorted(mapping.items()):
        output.append(f"## {table}")
        output.append("")
        output.append("| Field | Type | Nullable | Default |")
        output.append("|-------|------|----------|---------|")
        
        for field in fields:
            null_str = "YES" if field['is_nullable'] == 'YES' else "NO"
            default = field['column_default'] or '-'
            if len(default) > 30:
                default = default[:27] + '...'
            
            data_type = field['data_type']
            if field['character_maximum_length']:
                data_type += f"({field['character_maximum_length']})"
            
            output.append(f"| `{field['column_name']}` | {data_type} | {null_str} | {default} |")
        
        output.append("")
    
    filename = f'DATABASE_SCHEMA_REFERENCE_{datetime.now().strftime("%Y%m%d_%H%M%S")}.md'
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output))
    
    return filename

if __name__ == '__main__':
    generate_field_mapping()
