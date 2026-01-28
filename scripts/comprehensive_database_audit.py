#!/usr/bin/env python3
"""
COMPREHENSIVE DATABASE AUDIT - Arrow Limousine Management System

Identifies:
1. Scattered data (data in wrong columns)
2. Useless tables or columns
3. Missing elements
4. Data integrity issues:
   - Client name vs company_name confusion
   - charter_id vs reserve_number usage
   - client_id vs charter_number confusion
   - vehicle_id vs vehicle display number (L-xx)
   - Vehicle type inconsistencies (bus, under 11, stretch, party bus)

Run: python -X utf8 l:\limo\scripts\comprehensive_database_audit.py
"""

import psycopg2
import os
import json
from datetime import datetime
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***')
    )

def get_all_tables(cur):
    """Get all tables in database with row counts"""
    cur.execute("""
        SELECT 
            schemaname,
            tablename,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
    """)
    tables = []
    for schema, table, size in cur.fetchall():
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        tables.append({
            'name': table,
            'row_count': count,
            'size': size
        })
    return tables

def get_table_columns(cur, table_name):
    """Get all columns for a table with data types"""
    cur.execute("""
        SELECT 
            column_name,
            data_type,
            character_maximum_length,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    return cur.fetchall()

def check_reserve_number_vs_charter_id(cur):
    """Audit charter_id vs reserve_number usage"""
    issues = []
    
    # Check payments table - should use reserve_number NOT charter_id
    cur.execute("""
        SELECT 
            COUNT(*) as total_payments,
            COUNT(charter_id) as has_charter_id,
            COUNT(reserve_number) as has_reserve_number,
            COUNT(CASE WHEN charter_id IS NOT NULL AND reserve_number IS NULL THEN 1 END) as charter_id_only,
            COUNT(CASE WHEN charter_id IS NULL AND reserve_number IS NOT NULL THEN 1 END) as reserve_number_only,
            COUNT(CASE WHEN charter_id IS NULL AND reserve_number IS NULL THEN 1 END) as missing_both
        FROM payments
    """)
    row = cur.fetchone()
    if row[3] > 0:  # charter_id_only
        issues.append({
            'table': 'payments',
            'issue': 'charter_id_used_instead_of_reserve_number',
            'severity': 'HIGH',
            'count': row[3],
            'description': f'{row[3]} payments using charter_id when reserve_number should be used'
        })
    
    # Check if charters have reserve_number
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(reserve_number) as has_reserve_number,
            COUNT(charter_id) as has_charter_id
        FROM charters
        WHERE reserve_number IS NULL
    """)
    missing = cur.fetchone()[0]
    if missing > 0:
        issues.append({
            'table': 'charters',
            'issue': 'missing_reserve_number',
            'severity': 'CRITICAL',
            'count': missing,
            'description': f'{missing} charters missing reserve_number (business key)'
        })
    
    # Check for duplicate reserve_numbers
    cur.execute("""
        SELECT reserve_number, COUNT(*) as dup_count
        FROM charters
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
        HAVING COUNT(*) > 1
    """)
    dups = cur.fetchall()
    if dups:
        issues.append({
            'table': 'charters',
            'issue': 'duplicate_reserve_numbers',
            'severity': 'CRITICAL',
            'count': len(dups),
            'description': f'{len(dups)} duplicate reserve_numbers found',
            'examples': dups[:5]
        })
    
    return issues

def check_client_name_vs_company(cur):
    """Check client_id and client_display_name usage"""
    issues = []
    
    # Check charters table - client_id should reference clients table
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(client_id) as has_client_id,
            COUNT(client_display_name) as has_display_name,
            COUNT(CASE WHEN client_id IS NULL AND client_display_name IS NOT NULL THEN 1 END) as display_no_id,
            COUNT(CASE WHEN client_id IS NOT NULL AND client_display_name IS NULL THEN 1 END) as id_no_display
        FROM charters
    """)
    row = cur.fetchone()
    if row[3] > 0:  # display_no_id
        issues.append({
            'table': 'charters',
            'issue': 'client_display_name_without_client_id',
            'severity': 'MEDIUM',
            'count': row[3],
            'description': f'{row[3]} charters have client_display_name but no client_id (broken FK)'
        })
    if row[4] > 0:  # id_no_display
        issues.append({
            'table': 'charters',
            'issue': 'client_id_without_display_name',
            'severity': 'LOW',
            'count': row[4],
            'description': f'{row[4]} charters have client_id but no client_display_name'
        })
    
    # Check for client_id confusion with charter numbers (should be different)
    cur.execute("""
        SELECT 
            COUNT(*) as potential_confusion
        FROM charters
        WHERE client_id IS NOT NULL 
        AND client_id::text = reserve_number
    """)
    confusion = cur.fetchone()[0]
    if confusion > 0:
        issues.append({
            'table': 'charters',
            'issue': 'client_id_equals_reserve_number',
            'severity': 'HIGH',
            'count': confusion,
            'description': f'{confusion} charters where client_id equals reserve_number (likely data entry error)'
        })
    
    # Check if client_id references valid clients
    cur.execute("""
        SELECT COUNT(*)
        FROM charters c
        WHERE c.client_id IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM clients cl WHERE cl.client_id = c.client_id
        )
    """)
    orphaned = cur.fetchone()[0]
    if orphaned > 0:
        issues.append({
            'table': 'charters',
            'issue': 'invalid_client_id_references',
            'severity': 'HIGH',
            'count': orphaned,
            'description': f'{orphaned} charters reference non-existent clients'
        })
    
    return issues

def check_vehicle_id_display_confusion(cur):
    """Check vehicle_id (integer) vs vehicle display number (L-xx)"""
    issues = []
    
    # Check vehicles table structure
    cur.execute("""
        SELECT 
            vehicle_id,
            vehicle_number,
            license_plate,
            fleet_number
        FROM vehicles
        LIMIT 10
    """)
    samples = cur.fetchall()
    
    # Check if vehicle_number contains L- format
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN vehicle_number LIKE 'L-%' THEN 1 END) as has_l_format,
            COUNT(CASE WHEN vehicle_number ~ '^[0-9]+$' THEN 1 END) as numeric_only
        FROM vehicles
    """)
    row = cur.fetchone()
    
    issues.append({
        'table': 'vehicles',
        'issue': 'vehicle_number_format_analysis',
        'severity': 'INFO',
        'description': f'Total: {row[0]}, L-format: {row[1]}, Numeric only: {row[2]}',
        'samples': samples[:5]
    })
    
    # Check if other tables reference vehicle_id correctly
    tables_with_vehicle_ref = [
        'charters',
        'maintenance_records',
        'incidents',
        'vehicle_fuel_log',
        'vehicle_mileage_log'
    ]
    
    for table in tables_with_vehicle_ref:
        cur.execute(f"""
            SELECT COUNT(*) 
            FROM information_schema.columns
            WHERE table_name = '{table}' AND column_name = 'vehicle_id'
        """)
        if cur.fetchone()[0] > 0:
            # Check for NULL vehicle_ids
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE vehicle_id IS NULL")
            null_count = cur.fetchone()[0]
            if null_count > 0:
                issues.append({
                    'table': table,
                    'issue': 'null_vehicle_id',
                    'severity': 'MEDIUM',
                    'count': null_count,
                    'description': f'{null_count} records with NULL vehicle_id'
                })
    
    return issues

def check_vehicle_type_consistency(cur):
    """Check vehicle type field inconsistencies"""
    issues = []
    
    # Check what vehicle type fields exist
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'vehicles'
        AND (column_name ILIKE '%type%' OR column_name ILIKE '%category%')
    """)
    type_columns = [row[0] for row in cur.fetchall()]
    
    issues.append({
        'table': 'vehicles',
        'issue': 'vehicle_type_columns_found',
        'severity': 'INFO',
        'description': f'Type-related columns: {", ".join(type_columns)}'
    })
    
    # Analyze each type column
    for col in type_columns:
        cur.execute(f"""
            SELECT {col}, COUNT(*) as count
            FROM vehicles
            WHERE {col} IS NOT NULL
            GROUP BY {col}
            ORDER BY count DESC
        """)
        values = cur.fetchall()
        
        # Check for inconsistent terminology
        inconsistent_terms = []
        for val, count in values:
            if val:
                val_lower = str(val).lower()
                # Check for conflicting terms
                if 'bus' in val_lower and 'passenger' in val_lower:
                    inconsistent_terms.append((val, count))
                elif any(term in val_lower for term in ['stretch', 'limo', 'sedan', 'suv']):
                    inconsistent_terms.append((val, count))
        
        issues.append({
            'table': 'vehicles',
            'column': col,
            'issue': 'vehicle_type_values',
            'severity': 'INFO',
            'unique_values': len(values),
            'total_records': sum(v[1] for v in values),
            'all_values': values,
            'inconsistent_terms': inconsistent_terms if inconsistent_terms else None
        })
    
    # Check for passenger capacity consistency
    cur.execute("""
        SELECT 
            passenger_capacity,
            COUNT(*) as count
        FROM vehicles
        WHERE passenger_capacity IS NOT NULL
        GROUP BY passenger_capacity
        ORDER BY passenger_capacity
    """)
    capacity_distribution = cur.fetchall()
    
    issues.append({
        'table': 'vehicles',
        'issue': 'passenger_capacity_distribution',
        'severity': 'INFO',
        'description': 'Distribution of passenger capacities',
        'data': capacity_distribution
    })
    
    return issues

def check_unused_columns(cur):
    """Find columns that are always NULL or never used"""
    issues = []
    
    tables = get_all_tables(cur)
    
    for table_info in tables:
        table = table_info['name']
        if table_info['row_count'] == 0:
            continue  # Skip empty tables
        
        columns = get_table_columns(cur, table)
        
        for col_name, data_type, max_len, nullable, default in columns:
            # Check if column is always NULL
            # Quote column name to handle case-sensitive names
            cur.execute(f"""
                SELECT COUNT(*) 
                FROM {table}
                WHERE "{col_name}" IS NOT NULL
            """)
            non_null_count = cur.fetchone()[0]
            
            if non_null_count == 0 and table_info['row_count'] > 10:
                issues.append({
                    'table': table,
                    'column': col_name,
                    'issue': 'always_null',
                    'severity': 'LOW',
                    'description': f'Column always NULL in {table_info["row_count"]} rows'
                })
            elif non_null_count > 0 and non_null_count < table_info['row_count'] * 0.01:
                # Less than 1% populated
                issues.append({
                    'table': table,
                    'column': col_name,
                    'issue': 'rarely_used',
                    'severity': 'LOW',
                    'description': f'Only {non_null_count}/{table_info["row_count"]} rows populated ({non_null_count/table_info["row_count"]*100:.1f}%)'
                })
    
    return issues

def check_missing_foreign_keys(cur):
    """Check for missing or broken foreign key relationships"""
    issues = []
    
    # Get all foreign keys
    cur.execute("""
        SELECT
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_schema = 'public'
    """)
    foreign_keys = cur.fetchall()
    
    # Check for orphaned records
    for table, col, ref_table, ref_col in foreign_keys:
        cur.execute(f"""
            SELECT COUNT(*)
            FROM {table} t
            WHERE t.{col} IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM {ref_table} r
                WHERE r.{ref_col} = t.{col}
            )
        """)
        orphaned = cur.fetchone()[0]
        if orphaned > 0:
            issues.append({
                'table': table,
                'column': col,
                'issue': 'orphaned_foreign_key',
                'severity': 'HIGH',
                'count': orphaned,
                'description': f'{orphaned} records reference non-existent {ref_table}.{ref_col}'
            })
    
    return issues

def check_duplicate_tables(cur):
    """Check for tables with similar names or purposes"""
    issues = []
    
    tables = get_all_tables(cur)
    table_names = [t['name'] for t in tables]
    
    # Look for similar table names
    similar_groups = defaultdict(list)
    for table in table_names:
        base = table.replace('_v2', '').replace('_new', '').replace('_old', '').replace('_temp', '')
        similar_groups[base].append(table)
    
    for base, similar in similar_groups.items():
        if len(similar) > 1:
            issues.append({
                'issue': 'similar_table_names',
                'severity': 'MEDIUM',
                'base_name': base,
                'tables': similar,
                'description': f'Multiple tables with similar names: {", ".join(similar)}'
            })
    
    return issues

def check_empty_or_useless_tables(cur):
    """Find empty tables or tables with very few records"""
    issues = []
    
    tables = get_all_tables(cur)
    
    for table_info in tables:
        if table_info['row_count'] == 0:
            issues.append({
                'table': table_info['name'],
                'issue': 'empty_table',
                'severity': 'MEDIUM',
                'description': f'Table has 0 rows (size: {table_info["size"]})'
            })
        elif table_info['row_count'] < 5:
            issues.append({
                'table': table_info['name'],
                'issue': 'nearly_empty_table',
                'severity': 'LOW',
                'count': table_info['row_count'],
                'description': f'Table has only {table_info["row_count"]} rows'
            })
    
    return issues

def generate_report(all_issues):
    """Generate formatted audit report"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    report = []
    report.append("="*100)
    report.append("COMPREHENSIVE DATABASE AUDIT REPORT - ARROW LIMOUSINE MANAGEMENT SYSTEM")
    report.append("="*100)
    report.append(f"Generated: {timestamp}")
    report.append("")
    
    # Group by severity
    critical = [i for i in all_issues if i.get('severity') == 'CRITICAL']
    high = [i for i in all_issues if i.get('severity') == 'HIGH']
    medium = [i for i in all_issues if i.get('severity') == 'MEDIUM']
    low = [i for i in all_issues if i.get('severity') == 'LOW']
    info = [i for i in all_issues if i.get('severity') == 'INFO']
    
    report.append("📊 SUMMARY")
    report.append("-" * 100)
    report.append(f"🔴 CRITICAL Issues: {len(critical)}")
    report.append(f"🟠 HIGH Priority: {len(high)}")
    report.append(f"🟡 MEDIUM Priority: {len(medium)}")
    report.append(f"🟢 LOW Priority: {len(low)}")
    report.append(f"ℹ️  INFO: {len(info)}")
    report.append(f"TOTAL: {len(all_issues)}")
    report.append("")
    
    # Critical Issues
    if critical:
        report.append("="*100)
        report.append("🔴 CRITICAL ISSUES - IMMEDIATE ATTENTION REQUIRED")
        report.append("="*100)
        for idx, issue in enumerate(critical, 1):
            report.append(f"\n[{idx}] {issue.get('table', 'N/A')} - {issue.get('issue', 'Unknown')}")
            report.append(f"    Description: {issue.get('description', 'N/A')}")
            if 'count' in issue:
                report.append(f"    Count: {issue['count']}")
            if 'examples' in issue:
                report.append(f"    Examples: {issue['examples']}")
        report.append("")
    
    # High Priority
    if high:
        report.append("="*100)
        report.append("🟠 HIGH PRIORITY ISSUES")
        report.append("="*100)
        for idx, issue in enumerate(high, 1):
            report.append(f"\n[{idx}] {issue.get('table', 'N/A')} - {issue.get('issue', 'Unknown')}")
            report.append(f"    Description: {issue.get('description', 'N/A')}")
            if 'count' in issue:
                report.append(f"    Count: {issue['count']}")
        report.append("")
    
    # Medium Priority
    if medium:
        report.append("="*100)
        report.append("🟡 MEDIUM PRIORITY ISSUES")
        report.append("="*100)
        for idx, issue in enumerate(medium, 1):
            report.append(f"\n[{idx}] {issue.get('table', 'N/A')} - {issue.get('issue', 'Unknown')}")
            report.append(f"    Description: {issue.get('description', 'N/A')}")
            if 'count' in issue:
                report.append(f"    Count: {issue['count']}")
            if 'examples' in issue and len(issue['examples']) <= 5:
                report.append(f"    Examples: {issue['examples']}")
        report.append("")
    
    # Low Priority
    if low:
        report.append("="*100)
        report.append("🟢 LOW PRIORITY ISSUES")
        report.append("="*100)
        # Group by issue type
        by_type = defaultdict(list)
        for issue in low:
            by_type[issue.get('issue', 'Unknown')].append(issue)
        
        for issue_type, issues in by_type.items():
            report.append(f"\n{issue_type.upper()} ({len(issues)} occurrences)")
            for issue in issues[:10]:  # Show first 10
                report.append(f"  - {issue.get('table', 'N/A')}.{issue.get('column', 'N/A')}: {issue.get('description', 'N/A')}")
            if len(issues) > 10:
                report.append(f"  ... and {len(issues) - 10} more")
        report.append("")
    
    # Info
    if info:
        report.append("="*100)
        report.append("ℹ️  INFORMATIONAL")
        report.append("="*100)
        for idx, issue in enumerate(info, 1):
            report.append(f"\n[{idx}] {issue.get('table', 'N/A')} - {issue.get('issue', 'Unknown')}")
            if 'column' in issue:
                report.append(f"    Column: {issue['column']}")
            report.append(f"    {issue.get('description', 'N/A')}")
            if 'all_values' in issue:
                report.append(f"    Values:")
                for val, count in issue['all_values'][:20]:  # Show first 20
                    report.append(f"      - {val}: {count}")
                if len(issue['all_values']) > 20:
                    report.append(f"      ... and {len(issue['all_values']) - 20} more")
            if 'inconsistent_terms' in issue and issue['inconsistent_terms']:
                report.append(f"    ⚠️  Inconsistent terms found:")
                for val, count in issue['inconsistent_terms']:
                    report.append(f"      - {val}: {count}")
        report.append("")
    
    report.append("="*100)
    report.append("END OF AUDIT REPORT")
    report.append("="*100)
    
    return "\n".join(report)

def main():
    print("Starting comprehensive database audit...")
    print("This may take several minutes...\n")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    all_issues = []
    
    # Run all checks
    print("[1/9] Checking reserve_number vs charter_id usage...")
    all_issues.extend(check_reserve_number_vs_charter_id(cur))
    
    print("[2/9] Checking client_id and client_display_name usage...")
    all_issues.extend(check_client_name_vs_company(cur))
    
    print("[3/9] Checking vehicle_id vs display number confusion...")
    all_issues.extend(check_vehicle_id_display_confusion(cur))
    
    print("[4/9] Checking vehicle type consistency...")
    all_issues.extend(check_vehicle_type_consistency(cur))
    
    print("[5/9] Checking for unused columns...")
    all_issues.extend(check_unused_columns(cur))
    
    print("[6/9] Checking for missing/broken foreign keys...")
    all_issues.extend(check_missing_foreign_keys(cur))
    
    print("[7/9] Checking for duplicate tables...")
    all_issues.extend(check_duplicate_tables(cur))
    
    print("[8/9] Checking for empty/useless tables...")
    all_issues.extend(check_empty_or_useless_tables(cur))
    
    print("[9/9] Generating report...")
    
    # Generate report
    report = generate_report(all_issues)
    
    # Save to file
    output_file = f"l:\\limo\\reports\\database_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    # Also save JSON for programmatic access
    json_file = output_file.replace('.txt', '.json')
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(all_issues, f, indent=2, default=str)
    
    print(f"\n✅ Audit complete!")
    print(f"📄 Report saved to: {output_file}")
    print(f"📊 JSON data saved to: {json_file}")
    print(f"\n📊 Found {len(all_issues)} issues total")
    
    # Print summary to console
    print("\n" + report)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
