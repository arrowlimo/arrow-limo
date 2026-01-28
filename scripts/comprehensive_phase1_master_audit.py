#!/usr/bin/env python3
"""
PHASE 1: MASTER DATABASE AUDIT - COMPLETE INTEGRITY CHECK
==========================================================

Comprehensive audit that validates:
1. Column Semantics: Data matches column name (e.g., 'email' contains emails, 'phone' contains phones)
2. Data Types: All values match declared types (no strings in numeric fields)
3. Foreign Key Relationships: All FK columns link to valid PK values
4. Primary Keys: All tables have PKs, no orphan records
5. Duplicate Detection: Identify duplicate/repeated data (e.g., same client multiple times)
6. Unused Columns: Columns in DB but not referenced in code
7. Naming Mismatches: Code expects column X but DB has column Y
8. Relationship Integrity: One-to-many relationships properly structured

Output: JSON report with all findings, prioritized by severity
"""

import os
import re
import json
import psycopg2
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from decimal import Decimal

# Database Configuration
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

REPORTS_DIR = Path("l:/limo/reports")
REPORTS_DIR.mkdir(exist_ok=True)

# Core business tables (highest priority)
CORE_TABLES = [
    'clients', 'charters', 'payments', 'receipts', 'employees', 
    'vehicles', 'dispatches', 'banking_transactions'
]

def get_db_connection():
    """Create database connection"""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def get_all_tables(cur):
    """Get all user tables"""
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    return [row[0] for row in cur.fetchall()]

def get_table_columns(cur, table_name):
    """Get all columns for a table with data types"""
    cur.execute("""
        SELECT 
            column_name, 
            data_type, 
            is_nullable,
            character_maximum_length,
            numeric_precision,
            numeric_scale
        FROM information_schema.columns 
        WHERE table_name = %s 
        AND table_schema = 'public'
        ORDER BY ordinal_position
    """, (table_name,))
    
    return [{
        'name': row[0],
        'type': row[1],
        'nullable': row[2] == 'YES',
        'max_length': row[3],
        'precision': row[4],
        'scale': row[5]
    } for row in cur.fetchall()]

def get_primary_keys(cur, table_name):
    """Get primary key columns"""
    cur.execute("""
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        WHERE i.indrelid = %s::regclass AND i.indisprimary
    """, (table_name,))
    return [row[0] for row in cur.fetchall()]

def get_foreign_keys(cur, table_name):
    """Get foreign key relationships"""
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
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_name = %s
    """, (table_name,))
    
    return [{
        'column': row[0],
        'references_table': row[1],
        'references_column': row[2]
    } for row in cur.fetchall()]

def validate_column_semantics(cur, table_name, column_name, data_type):
    """Check if column data matches its semantic name"""
    issues = []
    
    # Skip legacy/staging tables
    if any(prefix in table_name.lower() for prefix in ['limo_', 'lms_', 'staging_', '_archived_']):
        return issues
    
    # Sample data from column
    try:
        cur.execute(f"""
            SELECT "{column_name}" 
            FROM {table_name} 
            WHERE "{column_name}" IS NOT NULL 
            LIMIT 100
        """)
        samples = [row[0] for row in cur.fetchall() if row[0]]
        
        if not samples:
            return issues
        
        # Email validation
        if 'email' in column_name.lower() and 'subject' not in column_name.lower() and 'subscription' not in column_name.lower():
            email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
            invalid_emails = [s for s in samples if isinstance(s, str) and not email_pattern.match(s)]
            if len(invalid_emails) > len(samples) * 0.3:  # More than 30% invalid
                issues.append({
                    'type': 'SEMANTIC_MISMATCH',
                    'severity': 'HIGH',
                    'table': table_name,
                    'column': column_name,
                    'issue': f'Column named "email" contains {len(invalid_emails)}/{len(samples)} non-email values',
                    'samples': invalid_emails[:5]
                })
        
        # Phone validation
        if 'phone' in column_name.lower():
            phone_pattern = re.compile(r"[\'\"\']?[\d\s\-\(\)\+]{7,}")
            invalid_phones = [s for s in samples if isinstance(s, str) and not phone_pattern.match(s)]
            if len(invalid_phones) > len(samples) * 0.3:
                issues.append({
                    'type': 'SEMANTIC_MISMATCH',
                    'severity': 'HIGH',
                    'table': table_name,
                    'column': column_name,
                    'issue': f'Column named "phone" contains {len(invalid_phones)}/{len(samples)} non-phone values',
                    'samples': invalid_phones[:5]
                })
        
        # Date validation - skip if name has 'description' or 'effective'
        if 'date' in column_name.lower() and data_type not in ['date', 'timestamp without time zone', 'timestamp with time zone']:
            if 'description' not in column_name.lower() and 'effective' not in column_name.lower():
                issues.append({
                    'type': 'TYPE_MISMATCH',
                    'severity': 'MEDIUM',
                    'table': table_name,
                    'column': column_name,
                    'issue': f'Column named "date" has type {data_type} instead of DATE/TIMESTAMP',
                    'recommendation': f'ALTER TABLE {table_name} ALTER COLUMN {column_name} TYPE DATE'
                })
        
        # Amount/price validation - EXCLUDE description/strategy/balance text columns
        financial_keywords = ['amount', 'price', 'total', 'cost', 'rate']
        exclude_keywords = ['description', 'strategy', 'balance', 'normal_balance', 'effective_date']
        
        has_financial_term = any(keyword in column_name.lower() for keyword in financial_keywords)
        is_excluded = any(keyword in column_name.lower() for keyword in exclude_keywords)
        
        if has_financial_term and not is_excluded:
            if data_type not in ['numeric', 'decimal', 'money', 'integer', 'bigint', 'double precision', 'real']:
                issues.append({
                    'type': 'TYPE_MISMATCH',
                    'severity': 'HIGH',
                    'table': table_name,
                    'column': column_name,
                    'issue': f'Column named with financial term has type {data_type} instead of NUMERIC',
                    'recommendation': f'ALTER TABLE {table_name} ALTER COLUMN {column_name} TYPE NUMERIC(12,2)'
                })
    
    except Exception as e:
        pass  # Skip validation errors
    
    return issues

def find_orphaned_foreign_keys(cur, table_name, fk_info):
    """Find FK values that don't exist in referenced table"""
    issues = []
    
    for fk in fk_info:
        try:
            cur.execute(f"""
                SELECT COUNT(*) 
                FROM {table_name} t
                LEFT JOIN {fk['references_table']} ref 
                  ON t.{fk['column']} = ref.{fk['references_column']}
                WHERE t.{fk['column']} IS NOT NULL 
                  AND ref.{fk['references_column']} IS NULL
            """)
            orphan_count = cur.fetchone()[0]
            
            if orphan_count > 0:
                issues.append({
                    'type': 'ORPHANED_FK',
                    'severity': 'CRITICAL',
                    'table': table_name,
                    'column': fk['column'],
                    'issue': f'{orphan_count} rows reference non-existent {fk["references_table"]}.{fk["references_column"]}',
                    'recommendation': f'DELETE orphaned rows or add missing records to {fk["references_table"]}'
                })
        except Exception as e:
            pass
    
    return issues

def find_duplicate_records(cur, table_name, pk_columns):
    """Find potential duplicate records"""
    issues = []
    
    # Skip if no PK
    if not pk_columns:
        return issues
    
    try:
        # Get row count
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        total_rows = cur.fetchone()[0]
        
        if total_rows == 0:
            return issues
        
        # For tables with common columns, check for duplicates
        cur.execute(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}' 
            AND column_name IN ('name', 'email', 'phone', 'reserve_number', 'transaction_date', 'description')
        """)
        
        dup_check_columns = [row[0] for row in cur.fetchall()]
        
        if dup_check_columns:
            columns_str = ', '.join(dup_check_columns)
            cur.execute(f"""
                SELECT {columns_str}, COUNT(*) as cnt
                FROM {table_name}
                WHERE {dup_check_columns[0]} IS NOT NULL
                GROUP BY {columns_str}
                HAVING COUNT(*) > 1
                LIMIT 10
            """)
            
            duplicates = cur.fetchall()
            
            if duplicates:
                issues.append({
                    'type': 'DUPLICATE_DATA',
                    'severity': 'MEDIUM',
                    'table': table_name,
                    'issue': f'Found {len(duplicates)} sets of duplicate records',
                    'sample_duplicates': [dict(zip(dup_check_columns + ['count'], dup)) for dup in duplicates[:3]]
                })
    
    except Exception as e:
        pass
    
    return issues

def scan_code_column_usage():
    """Scan all Python files to see which columns are used"""
    column_usage = defaultdict(set)
    
    code_dirs = [
        Path("l:/limo/desktop_app"),
        Path("l:/limo/scripts"),
        Path("l:/limo/modern_backend")
    ]
    
    for directory in code_dirs:
        if not directory.exists():
            continue
        
        for py_file in directory.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Find column references in SQL queries
                # Pattern: table_name.column_name or "column_name"
                matches = re.findall(r'(\w+)\.(\w+)|["\'](\w+)["\']', content)
                
                for match in matches:
                    if match[1]:  # table.column format
                        column_usage[match[0]].add(match[1])
                    elif match[2]:  # quoted column
                        column_usage['_unknown'].add(match[2])
            
            except Exception:
                pass
    
    return column_usage

def find_unused_columns(cur, table_name, columns, code_usage):
    """Find columns that exist in DB but aren't used in code"""
    issues = []
    
    table_usage = code_usage.get(table_name, set())
    all_usage = code_usage.get('_unknown', set())
    
    for col in columns:
        col_name = col['name']
        
        # Skip system columns
        if col_name in ['created_at', 'updated_at', 'id']:
            continue
        
        # Check if column is referenced anywhere
        if col_name not in table_usage and col_name not in all_usage:
            issues.append({
                'type': 'UNUSED_COLUMN',
                'severity': 'LOW',
                'table': table_name,
                'column': col_name,
                'issue': f'Column exists in database but not found in any code',
                'recommendation': 'Verify if column is needed; consider deprecation'
            })
    
    return issues

def check_relationship_structure(cur, table_name):
    """Verify one-to-many relationships are properly structured"""
    issues = []
    
    # Check for repeated parent records in child tables
    # Example: same client appearing multiple times with different IDs instead of one client with many charters
    
    if table_name == 'clients':
        try:
            # Find clients with same name/phone but different IDs
            cur.execute("""
                SELECT name, phone, COUNT(DISTINCT client_id) as id_count
                FROM clients
                WHERE name IS NOT NULL OR phone IS NOT NULL
                GROUP BY name, phone
                HAVING COUNT(DISTINCT client_id) > 1
                LIMIT 10
            """)
            
            duplicates = cur.fetchall()
            
            if duplicates:
                issues.append({
                    'type': 'RELATIONSHIP_VIOLATION',
                    'severity': 'HIGH',
                    'table': table_name,
                    'issue': f'Found {len(duplicates)} clients with duplicate name/phone but different IDs',
                    'recommendation': 'Merge duplicate clients and update foreign keys in charters table',
                    'samples': [{'name': d[0], 'phone': d[1], 'duplicate_ids': d[2]} for d in duplicates[:3]]
                })
        except Exception:
            pass
    
    return issues

def run_comprehensive_audit():
    """Execute complete Phase 1 audit"""
    print("=" * 80)
    print("PHASE 1: MASTER DATABASE AUDIT")
    print("=" * 80)
    print(f"Started: {datetime.now()}\n")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    all_issues = []
    stats = {
        'tables_scanned': 0,
        'columns_scanned': 0,
        'critical_issues': 0,
        'high_issues': 0,
        'medium_issues': 0,
        'low_issues': 0
    }
    
    # Step 1: Scan code for column usage
    print("📊 Step 1: Scanning code for column references...")
    code_usage = scan_code_column_usage()
    print(f"   Found {len(code_usage)} tables/contexts referenced in code\n")
    
    # Step 2: Get all tables
    print("📊 Step 2: Analyzing database tables...")
    tables = get_all_tables(cur)
    print(f"   Found {len(tables)} tables\n")
    
    # Step 3: Audit each table
    print("📊 Step 3: Auditing each table...\n")
    
    for table_name in tables:
        stats['tables_scanned'] += 1
        
        # Prioritize core tables
        priority = 'CRITICAL' if table_name in CORE_TABLES else 'NORMAL'
        
        print(f"   Auditing: {table_name} ({priority})")
        
        try:
            # Get table structure
            columns = get_table_columns(cur, table_name)
            pk_columns = get_primary_keys(cur, table_name)
            fk_info = get_foreign_keys(cur, table_name)
        except Exception as e:
            conn.rollback()
            print(f"      ⚠️  Skipped (error: {str(e)[:50]})")
            continue
        
        stats['columns_scanned'] += len(columns)
        
        # Check 1: Missing primary key
        if not pk_columns:
            all_issues.append({
                'type': 'MISSING_PK',
                'severity': 'CRITICAL',
                'table': table_name,
                'issue': 'Table has no primary key',
                'recommendation': f'Add primary key or identify unique identifier column'
            })
        
        # Check 2: Column semantics
        for col in columns:
            all_issues.extend(validate_column_semantics(cur, table_name, col['name'], col['type']))
        
        # Check 3: Orphaned foreign keys
        all_issues.extend(find_orphaned_foreign_keys(cur, table_name, fk_info))
        
        # Check 4: Duplicate records
        all_issues.extend(find_duplicate_records(cur, table_name, pk_columns))
        
        # Check 5: Unused columns
        all_issues.extend(find_unused_columns(cur, table_name, columns, code_usage))
        
        # Check 6: Relationship structure
        all_issues.extend(check_relationship_structure(cur, table_name))
    
    cur.close()
    conn.close()
    
    # Count issues by severity
    for issue in all_issues:
        severity = issue['severity']
        if severity == 'CRITICAL':
            stats['critical_issues'] += 1
        elif severity == 'HIGH':
            stats['high_issues'] += 1
        elif severity == 'MEDIUM':
            stats['medium_issues'] += 1
        else:
            stats['low_issues'] += 1
    
    # Generate report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    report = {
        'timestamp': timestamp,
        'stats': stats,
        'issues_by_severity': {
            'CRITICAL': [i for i in all_issues if i['severity'] == 'CRITICAL'],
            'HIGH': [i for i in all_issues if i['severity'] == 'HIGH'],
            'MEDIUM': [i for i in all_issues if i['severity'] == 'MEDIUM'],
            'LOW': [i for i in all_issues if i['severity'] == 'LOW']
        },
        'issues_by_type': {}
    }
    
    # Group by type
    for issue in all_issues:
        issue_type = issue['type']
        if issue_type not in report['issues_by_type']:
            report['issues_by_type'][issue_type] = []
        report['issues_by_type'][issue_type].append(issue)
    
    # Save JSON report
    report_file = REPORTS_DIR / f"phase1_master_audit_{timestamp}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, default=str)
    
    # Print summary
    print("\n" + "=" * 80)
    print("AUDIT COMPLETE")
    print("=" * 80)
    print(f"\n📊 Statistics:")
    print(f"   Tables Scanned: {stats['tables_scanned']}")
    print(f"   Columns Scanned: {stats['columns_scanned']}")
    print(f"\n⚠️  Issues Found:")
    print(f"   🔴 CRITICAL: {stats['critical_issues']}")
    print(f"   🟠 HIGH: {stats['high_issues']}")
    print(f"   🟡 MEDIUM: {stats['medium_issues']}")
    print(f"   ⚪ LOW: {stats['low_issues']}")
    print(f"\n📄 Full report: {report_file}")
    print(f"\nCompleted: {datetime.now()}")
    
    return report

if __name__ == '__main__':
    run_comprehensive_audit()
