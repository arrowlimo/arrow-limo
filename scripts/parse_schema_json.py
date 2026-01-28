#!/usr/bin/env python
"""
Parse JSON schema files to identify charter/payment differences
Use: reports/schema_comparison_2025-12-26.json
"""
import json
import os
from datetime import datetime

def load_schema_json():
    """Load the schema comparison JSON"""
    json_file = r"L:\limo\reports\schema_comparison_2025-12-26.json"
    
    if not os.path.exists(json_file):
        print(f"Error: {json_file} not found")
        return None
    
    with open(json_file, 'r') as f:
        return json.load(f)

def analyze_mdb_tables(schema):
    """Analyze MDB tables for charter-related data"""
    print("="*70)
    print("ANALYZING MDB TABLES FOR CHARTER DATA")
    print("="*70)
    
    # Look for charter/reserve/payment related tables
    charter_tables = {}
    payment_tables = {}
    charge_tables = {}
    
    for table_name, table_data in schema['tables'].items():
        if 'mdb_detail' in table_data and table_data['in_mdb']:
            # Check for charter/reserve tables
            if any(term in table_name.lower() for term in ['reserve', 'charter', 'order', 'ord']):
                charter_tables[table_name] = {
                    'columns': len(table_data.get('mdb_detail', {}).get('columns', [])),
                    'column_names': [col['name'] for col in table_data.get('mdb_detail', {}).get('columns', [])]
                }
            
            # Check for payment tables
            if any(term in table_name.lower() for term in ['payment', 'paid', 'ord_payment']):
                payment_tables[table_name] = {
                    'columns': len(table_data.get('mdb_detail', {}).get('columns', [])),
                    'column_names': [col['name'] for col in table_data.get('mdb_detail', {}).get('columns', [])]
                }
            
            # Check for charge tables
            if any(term in table_name.lower() for term in ['charge', 'invoice']):
                charge_tables[table_name] = {
                    'columns': len(table_data.get('mdb_detail', {}).get('columns', [])),
                    'column_names': [col['name'] for col in table_data.get('mdb_detail', {}).get('columns', [])]
                }
    
    print("\n📋 CHARTER/RESERVE TABLES IN MDB:")
    for table, info in sorted(charter_tables.items()):
        print(f"\n  {table}")
        print(f"    Columns: {info['columns']}")
        key_cols = [c for c in info['column_names'] if any(k in c.lower() for k in ['key', 'id', 'balance', 'gratuity', 'date'])]
        if key_cols:
            print(f"    Key fields: {', '.join(key_cols)}")
    
    print("\n💳 PAYMENT TABLES IN MDB:")
    for table, info in sorted(payment_tables.items()):
        print(f"\n  {table}")
        print(f"    Columns: {info['columns']}")
        key_cols = [c for c in info['column_names'] if any(k in c.lower() for k in ['key', 'id', 'paid', 'amount', 'date'])]
        if key_cols:
            print(f"    Key fields: {', '.join(key_cols)}")
    
    print("\n💰 CHARGE TABLES IN MDB:")
    for table, info in sorted(charge_tables.items()):
        print(f"\n  {table}")
        print(f"    Columns: {info['columns']}")
        key_cols = [c for c in info['column_names'] if any(k in c.lower() for k in ['key', 'id', 'charge', 'amount', 'total'])]
        if key_cols:
            print(f"    Key fields: {', '.join(key_cols)}")
    
    return charter_tables, payment_tables, charge_tables

def analyze_pg_tables(schema):
    """Analyze PostgreSQL tables for charter-related data"""
    print("\n" + "="*70)
    print("ANALYZING POSTGRESQL TABLES FOR CHARTER DATA")
    print("="*70)
    
    charter_tables = {}
    payment_tables = {}
    charge_tables = {}
    
    for table_name, table_data in schema['tables'].items():
        if 'pg_detail' in table_data and table_data['in_pg']:
            # Check for charter tables
            if any(term in table_name.lower() for term in ['charter', 'reserve']):
                charter_tables[table_name] = {
                    'columns': table_data.get('pg_columns', 0),
                    'row_count': table_data.get('pg_row_count', 0),
                    'last_modified': table_data.get('pg_last_modified'),
                    'column_names': [col['name'] for col in table_data.get('pg_detail', {}).get('columns', [])]
                }
            
            # Check for payment tables
            if any(term in table_name.lower() for term in ['payment']):
                payment_tables[table_name] = {
                    'columns': table_data.get('pg_columns', 0),
                    'row_count': table_data.get('pg_row_count', 0),
                    'last_modified': table_data.get('pg_last_modified'),
                    'column_names': [col['name'] for col in table_data.get('pg_detail', {}).get('columns', [])]
                }
            
            # Check for charge tables
            if any(term in table_name.lower() for term in ['charge']):
                charge_tables[table_name] = {
                    'columns': table_data.get('pg_columns', 0),
                    'row_count': table_data.get('pg_row_count', 0),
                    'last_modified': table_data.get('pg_last_modified'),
                    'column_names': [col['name'] for col in table_data.get('pg_detail', {}).get('columns', [])]
                }
    
    print("\n📋 CHARTER TABLES IN POSTGRESQL:")
    for table, info in sorted(charter_tables.items()):
        print(f"\n  {table}")
        print(f"    Columns: {info['columns']}, Rows: {info['row_count']}")
        key_cols = [c for c in info['column_names'] if any(k in c.lower() for k in ['reserve', 'id', 'balance', 'gratuity', 'date'])]
        if key_cols:
            print(f"    Key fields: {', '.join(key_cols[:8])}")
        if info['last_modified']:
            print(f"    Last modified: {info['last_modified']}")
    
    print("\n💳 PAYMENT TABLES IN POSTGRESQL:")
    for table, info in sorted(payment_tables.items()):
        print(f"\n  {table}")
        print(f"    Columns: {info['columns']}, Rows: {info['row_count']}")
        key_cols = [c for c in info['column_names'] if any(k in c.lower() for k in ['reserve', 'id', 'amount', 'date'])]
        if key_cols:
            print(f"    Key fields: {', '.join(key_cols[:8])}")
        if info['last_modified']:
            print(f"    Last modified: {info['last_modified']}")
    
    print("\n💰 CHARGE TABLES IN POSTGRESQL:")
    for table, info in sorted(charge_tables.items()):
        print(f"\n  {table}")
        print(f"    Columns: {info['columns']}, Rows: {info['row_count']}")
        key_cols = [c for c in info['column_names'] if any(k in c.lower() for k in ['reserve', 'id', 'amount'])]
        if key_cols:
            print(f"    Key fields: {', '.join(key_cols[:8])}")
        if info['last_modified']:
            print(f"    Last modified: {info['last_modified']}")
    
    return charter_tables, payment_tables, charge_tables

def identify_critical_fields(mdb_charter, mdb_payment, mdb_charge, pg_charter, pg_payment, pg_charge):
    """Identify which fields likely changed"""
    print("\n" + "="*70)
    print("IDENTIFYING CRITICAL FIELDS THAT LIKELY CHANGED")
    print("="*70)
    
    changes = {
        'gratuity_fields': [],
        'balance_fields': [],
        'extra_fields': [],
        'payment_fields': [],
        'charge_fields': []
    }
    
    # Check MDB for gratuity fields
    for table, info in mdb_charter.items():
        for col in info['column_names']:
            if 'gratuity' in col.lower():
                changes['gratuity_fields'].append({
                    'mdb_table': table,
                    'field': col
                })
    
    # Check MDB for balance fields
    for table, info in mdb_charter.items():
        for col in info['column_names']:
            if 'balance' in col.lower():
                changes['balance_fields'].append({
                    'mdb_table': table,
                    'field': col
                })
    
    # Check MDB for extra fields (extra_gratuity, etc)
    for table, info in mdb_charter.items():
        for col in info['column_names']:
            if 'extra' in col.lower():
                changes['extra_fields'].append({
                    'mdb_table': table,
                    'field': col
                })
    
    # Check payment fields
    for table, info in mdb_payment.items():
        for col in info['column_names']:
            if any(term in col.lower() for term in ['paid', 'amount', 'method', 'date']):
                changes['payment_fields'].append({
                    'mdb_table': table,
                    'field': col
                })
    
    # Check charge fields
    for table, info in mdb_charge.items():
        for col in info['column_names']:
            if any(term in col.lower() for term in ['amount', 'total', 'gst', 'charge']):
                changes['charge_fields'].append({
                    'mdb_table': table,
                    'field': col
                })
    
    print("\n🔄 GRATUITY FIELDS (likely separated to extra_gratuity):")
    for item in changes['gratuity_fields']:
        print(f"  MDB {item['mdb_table']}.{item['field']}")
    
    print("\n📊 BALANCE FIELDS (likely reduced by bad debt):")
    for item in changes['balance_fields']:
        print(f"  MDB {item['mdb_table']}.{item['field']}")
    
    print("\n➕ EXTRA/NON-TAXED FIELDS (likely added or populated):")
    for item in changes['extra_fields']:
        print(f"  MDB {item['mdb_table']}.{item['field']}")
    
    print("\n💳 PAYMENT FIELDS (likely entries added):")
    for item in list(set((i['mdb_table'], i['field']) for i in changes['payment_fields']))[:10]:
        print(f"  MDB {item[0]}.{item[1]}")
    
    print("\n💰 CHARGE FIELDS (likely reduced by bad debt):")
    for item in list(set((i['mdb_table'], i['field']) for i in changes['charge_fields']))[:10]:
        print(f"  MDB {item[0]}.{item[1]}")
    
    return changes

if __name__ == '__main__':
    print("\n")
    schema = load_schema_json()
    
    if not schema:
        print("Could not load schema JSON")
        exit(1)
    
    print(f"Loaded schema with {len(schema['tables'])} tables")
    print(f"MDB: {schema['mdb_tables']} tables")
    print(f"PostgreSQL: {schema['pg_tables']} tables")
    
    # Analyze both databases
    mdb_charter, mdb_payment, mdb_charge = analyze_mdb_tables(schema)
    pg_charter, pg_payment, pg_charge = analyze_pg_tables(schema)
    
    # Identify critical fields
    changes = identify_critical_fields(mdb_charter, mdb_payment, mdb_charge, 
                                      pg_charter, pg_payment, pg_charge)
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"\n✓ MDB has {len(mdb_charter)} charter-related tables")
    print(f"✓ PostgreSQL has {len(pg_charter)} charter-related tables")
    print(f"✓ MDB has {len(mdb_payment)} payment-related tables")
    print(f"✓ PostgreSQL has {len(pg_payment)} payment-related tables")
    print(f"✓ MDB has {len(mdb_charge)} charge-related tables")
    print(f"✓ PostgreSQL has {len(pg_charge)} charge-related tables")
    
    print("\n" + "="*70)
    print("NEXT STEPS:")
    print("="*70)
    print("1. Map MDB table columns to PostgreSQL columns")
    print("2. Create extraction scripts for MDB charters, payments, charges")
    print("3. Generate detailed difference report by reserve_number")
    print("4. Identify missing payments in PostgreSQL")
    print("5. Flag balance changes > $100 for verification")
    
    # Save analysis
    output_file = r"L:\limo\reports\charter_field_analysis.json"
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'mdb_charter_tables': mdb_charter,
            'mdb_payment_tables': mdb_payment,
            'mdb_charge_tables': mdb_charge,
            'pg_charter_tables': pg_charter,
            'pg_payment_tables': pg_payment,
            'pg_charge_tables': pg_charge,
            'identified_changes': changes
        }, f, indent=2, default=str)
    
    print(f"\n✓ Analysis saved to {output_file}")
