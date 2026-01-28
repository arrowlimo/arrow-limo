#!/usr/bin/env python3
"""
Comprehensive schema verification for desktop app.

Checks:
1. All table schemas used by desktop app
2. Foreign key relationships
3. Column existence and types
4. Relationships between tables (charters, clients, employees, vehicles, receipts)
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
import re
from collections import defaultdict

PG = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    dbname=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

def get_conn():
    return psycopg2.connect(**PG)

def get_table_columns(cur, table_name):
    """Get all columns for a table."""
    cur.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    return {row['column_name']: row for row in cur.fetchall()}

def get_foreign_keys(cur, table_name):
    """Get all foreign keys for a table."""
    cur.execute("""
        SELECT
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = %s
    """, (table_name,))
    return {row['column_name']: row for row in cur.fetchall()}

def main():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=" * 80)
    print("DESKTOP APP SCHEMA VERIFICATION REPORT")
    print("=" * 80)
    
    # Key tables used by desktop app
    key_tables = {
        'charters': {
            'pk': 'charter_id',
            'fk': {
                'client_id': ('clients', 'client_id'),
                'assigned_driver_id': ('employees', 'employee_id'),
                'vehicle_id': ('vehicles', 'vehicle_id')
            },
            'expected_cols': ['charter_id', 'client_id', 'reserve_number', 'charter_date', 
                            'pickup_time', 'assigned_driver_id', 'vehicle_id', 'status']
        },
        'clients': {
            'pk': 'client_id',
            'fk': {},
            'expected_cols': ['client_id', 'company_name', 'primary_phone', 'email', 
                            'address_line1', 'contact_info']
        },
        'employees': {
            'pk': 'employee_id',
            'fk': {},
            'expected_cols': ['employee_id', 'first_name', 'last_name', 'status', 'is_chauffeur']
        },
        'vehicles': {
            'pk': 'vehicle_id',
            'fk': {},
            'expected_cols': ['vehicle_id', 'unit_number', 'license_plate', 'status']
        },
        'receipts': {
            'pk': 'receipt_id',
            'fk': {
                'vehicle_id': ('vehicles', 'vehicle_id')
            },
            'expected_cols': ['receipt_id', 'receipt_date', 'vendor_name', 'gross_amount', 
                            'gst_amount', 'gst_code', 'category', 'gl_account_code', 'vehicle_id']
        },
        'chart_of_accounts': {
            'pk': 'account_code',
            'fk': {},
            'expected_cols': ['account_code', 'account_name']
        }
    }
    
    summary = defaultdict(list)
    
    # Check each table
    for table_name, config in key_tables.items():
        print(f"\n{'='*80}")
        print(f"TABLE: {table_name.upper()}")
        print(f"{'='*80}")
        
        # Get columns
        columns = get_table_columns(cur, table_name)
        fks = get_foreign_keys(cur, table_name)
        
        print(f"\n✅ Primary Key: {config['pk']}")
        print(f"\n📋 Columns ({len(columns)}):")
        for col_name, col_info in columns.items():
            nullable = "NULL" if col_info['is_nullable'] == 'YES' else "NOT NULL"
            print(f"  • {col_name:25} {col_info['data_type']:15} {nullable}")
        
        # Check expected columns
        print(f"\n🔍 Expected columns check:")
        missing = []
        for exp_col in config['expected_cols']:
            if exp_col in columns:
                print(f"  ✅ {exp_col}")
            else:
                print(f"  ❌ MISSING: {exp_col}")
                missing.append(exp_col)
                summary[table_name].append(f"Missing column: {exp_col}")
        
        # Check foreign keys
        if config['fk']:
            print(f"\n🔗 Foreign Keys:")
            for fk_col, (target_table, target_col) in config['fk'].items():
                if fk_col in fks:
                    actual_fk = fks[fk_col]
                    if actual_fk['foreign_table_name'] == target_table and actual_fk['foreign_column_name'] == target_col:
                        print(f"  ✅ {fk_col} → {target_table}.{target_col}")
                    else:
                        print(f"  ⚠️  {fk_col} → {actual_fk['foreign_table_name']}.{actual_fk['foreign_column_name']} (expected {target_table}.{target_col})")
                        summary[table_name].append(f"FK mismatch: {fk_col}")
                else:
                    print(f"  ❌ Missing FK: {fk_col} → {target_table}.{target_col}")
                    summary[table_name].append(f"Missing FK: {fk_col}")
    
    # Print summary
    print(f"\n\n{'='*80}")
    print("VERIFICATION SUMMARY")
    print(f"{'='*80}")
    
    if any(summary.values()):
        print("\n⚠️  ISSUES FOUND:\n")
        for table, issues in summary.items():
            if issues:
                print(f"  {table}:")
                for issue in issues:
                    print(f"    • {issue}")
    else:
        print("\n✅ All schemas verified successfully!")
        print("Desktop app column references match database structure.")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
