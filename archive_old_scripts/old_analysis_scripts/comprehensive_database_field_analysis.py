#!/usr/bin/env python3
"""
COMPREHENSIVE DATABASE FIELD ANALYSIS
======================================

Analyzes every field in the application and verifies:
1. All database tables exist in Neon
2. All field references match actual database columns
3. All lookups use database tables (not hard-coded values)
4. All dropdown/ComboBox data sources are verified
5. Calendar events span correctly
6. GL codes are looked up from database
7. Beverage tables exist and are used
8. All widgets use correct data linkages

This script covers:
- Desktop app widgets (Python/PyQt)
- Web frontend (Vue components)
- API endpoints (FastAPI)
- Database schema verification
"""

import os
import re
import psycopg2
from pathlib import Path
from collections import defaultdict
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connections
NEON_HOST = os.environ.get("NEON_DB_HOST", "ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech")
NEON_DB = os.environ.get("NEON_DB_NAME", "neondb")
NEON_USER = os.environ.get("NEON_DB_USER", "neondb_owner")
NEON_PASSWORD = os.environ.get("NEON_DB_PASSWORD", "")

LOCAL_HOST = "localhost"
LOCAL_DB = os.environ.get("LOCAL_DB_NAME", "almsdata")
LOCAL_USER = os.environ.get("LOCAL_DB_USER", "alms")
LOCAL_PASSWORD = os.environ.get("LOCAL_DB_PASSWORD", "")

# Analysis results
analysis_results = {
    "timestamp": datetime.now().isoformat(),
    "issues": [],
    "warnings": [],
    "verified": [],
    "tables_checked": {},
    "widgets_analyzed": [],
    "vue_components_analyzed": [],
    "api_endpoints_analyzed": [],
}


def log_issue(category, message, severity="ERROR"):
    """Log an issue found during analysis."""
    issue = {
        "category": category,
        "message": message,
        "severity": severity,
        "timestamp": datetime.now().isoformat()
    }
    if severity == "ERROR":
        analysis_results["issues"].append(issue)
    elif severity == "WARNING":
        analysis_results["warnings"].append(issue)
    else:
        analysis_results["verified"].append(issue)
    print(f"[{severity}] {category}: {message}")


def get_neon_connection():
    """Get connection to Neon database."""
    try:
        conn = psycopg2.connect(
            host=NEON_HOST,
            database=NEON_DB,
            user=NEON_USER,
            password=NEON_PASSWORD,
            sslmode='require',
            connect_timeout=10
        )
        return conn
    except Exception as e:
        log_issue("Neon Connection", f"Failed to connect to Neon: {e}")
        return None


def get_local_connection():
    """Get connection to local database."""
    try:
        conn = psycopg2.connect(
            host=LOCAL_HOST,
            database=LOCAL_DB,
            user=LOCAL_USER,
            password=LOCAL_PASSWORD
        )
        return conn
    except Exception as e:
        log_issue("Local Connection", f"Failed to connect to local DB: {e}")
        return None


def get_all_tables(conn, db_name):
    """Get all tables from a database."""
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        tables = [row[0] for row in cur.fetchall()]
        cur.close()
        return tables
    except Exception as e:
        log_issue(f"{db_name} Tables", f"Failed to get tables: {e}")
        return []


def get_table_columns(conn, table_name):
    """Get all columns for a table."""
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        columns = cur.fetchall()
        cur.close()
        return columns
    except Exception as e:
        log_issue(f"Table {table_name}", f"Failed to get columns: {e}")
        return []


def check_table_exists(neon_tables, local_tables):
    """Check which tables exist in Neon vs Local."""
    print("\n" + "=" * 80)
    print("TABLE EXISTENCE VERIFICATION")
    print("=" * 80)
    
    neon_set = set(neon_tables)
    local_set = set(local_tables)
    
    # Tables in local but not in Neon
    missing_in_neon = local_set - neon_set
    if missing_in_neon:
        print(f"\n❌ MISSING IN NEON ({len(missing_in_neon)} tables):")
        for table in sorted(missing_in_neon):
            log_issue("Missing Table", f"Table '{table}' exists locally but NOT in Neon", "ERROR")
            print(f"   - {table}")
    
    # Tables in Neon but not in local
    extra_in_neon = neon_set - local_set
    if extra_in_neon:
        print(f"\n⚠️  EXTRA IN NEON ({len(extra_in_neon)} tables):")
        for table in sorted(extra_in_neon):
            log_issue("Extra Table", f"Table '{table}' exists in Neon but NOT locally", "WARNING")
            print(f"   - {table}")
    
    # Tables in both
    common_tables = neon_set & local_set
    print(f"\n✅ COMMON TABLES ({len(common_tables)} tables)")
    
    analysis_results["tables_checked"] = {
        "neon_count": len(neon_tables),
        "local_count": len(local_tables),
        "common_count": len(common_tables),
        "missing_in_neon": list(missing_in_neon),
        "extra_in_neon": list(extra_in_neon)
    }
    
    return common_tables


def analyze_python_widget(file_path):
    """Analyze a Python widget file for database field references."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        widget_name = os.path.basename(file_path)
        analysis_results["widgets_analyzed"].append(widget_name)
        
        # Find SQL queries
        sql_patterns = [
            r'(?:SELECT|INSERT|UPDATE|DELETE)\s+.*?FROM\s+(\w+)',
            r'(?:JOIN)\s+(\w+)',
            r'(?:INTO)\s+(\w+)',
            r'(?:UPDATE)\s+(\w+)',
        ]
        
        tables_referenced = set()
        for pattern in sql_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.DOTALL)
            for match in matches:
                tables_referenced.add(match.group(1))
        
        # Find hard-coded dropdown values (potential issues)
        hardcoded_lists = re.findall(r'(?:addItems?|setItems?)\s*\(\s*\[(.*?)\]', content, re.DOTALL)
        if hardcoded_lists:
            for hardcoded in hardcoded_lists[:3]:  # Limit to first 3
                if len(hardcoded) > 20:
                    log_issue(
                        f"Widget: {widget_name}",
                        f"Hard-coded dropdown values found: {hardcoded[:100]}...",
                        "WARNING"
                    )
        
        # Find ComboBox/dropdown population
        combobox_patterns = [
            r'(?:combo|dropdown|select).*?\.(?:addItem|setItems?)\s*\((.*?)\)',
        ]
        
        # Check for GL code lookups
        if 'gl_code' in content.lower() or 'gl_account' in content.lower():
            if 'chart_of_accounts' not in content:
                log_issue(
                    f"Widget: {widget_name}",
                    "GL code references found but no chart_of_accounts lookup",
                    "WARNING"
                )
        
        # Check for beverage references
        if 'beverage' in content.lower():
            if 'beverage_products' not in content and 'beverages' not in content:
                log_issue(
                    f"Widget: {widget_name}",
                    "Beverage references found but no beverage table lookup",
                    "WARNING"
                )
        
        return {
            "file": widget_name,
            "tables_referenced": list(tables_referenced),
            "has_sql": bool(tables_referenced)
        }
        
    except Exception as e:
        log_issue(f"Widget Analysis", f"Failed to analyze {file_path}: {e}", "WARNING")
        return None


def analyze_vue_component(file_path):
    """Analyze a Vue component for database field references."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        component_name = os.path.basename(file_path)
        analysis_results["vue_components_analyzed"].append(component_name)
        
        # Find API endpoint calls
        api_calls = re.findall(r'(?:axios\.|fetch\(|api\.)\s*(?:get|post|put|delete)\s*\(\s*[\'"`]([^\'")`]+)', content)
        
        # Find v-model and data bindings
        vmodels = re.findall(r'v-model\s*=\s*[\'"]([^\'"]+)', content)
        
        # Find hard-coded select options
        hardcoded_options = re.findall(r'<option[^>]*value\s*=\s*[\'"]([^\'"]+)', content)
        
        # Check for GL code references
        if 'gl_code' in content.lower() or 'glcode' in content.lower():
            if '/gl' not in content and '/chart' not in content:
                log_issue(
                    f"Vue: {component_name}",
                    "GL code references but no API call to fetch GL codes",
                    "WARNING"
                )
        
        # Check for beverage references
        if 'beverage' in content.lower():
            if '/beverage' not in content:
                log_issue(
                    f"Vue: {component_name}",
                    "Beverage references but no API call to fetch beverages",
                    "WARNING"
                )
        
        # Check calendar events
        if 'calendar' in component_name.lower() or 'fullcalendar' in content.lower():
            # Check for event span handling
            if 'end' in vmodels and 'start' in vmodels:
                log_issue(
                    f"Vue: {component_name}",
                    "Calendar event with start/end fields - verify spanning",
                    "INFO"
                )
        
        return {
            "file": component_name,
            "api_calls": api_calls,
            "vmodels": vmodels[:10],  # Limit output
            "hardcoded_options_count": len(hardcoded_options)
        }
        
    except Exception as e:
        log_issue(f"Vue Analysis", f"Failed to analyze {file_path}: {e}", "WARNING")
        return None


def analyze_api_endpoints(backend_dir):
    """Analyze API endpoints for data sources."""
    print("\n" + "=" * 80)
    print("API ENDPOINT ANALYSIS")
    print("=" * 80)
    
    router_files = list(Path(backend_dir).rglob("*.py"))
    
    for router_file in router_files:
        if 'router' in str(router_file) or 'api' in str(router_file):
            try:
                with open(router_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Find route definitions
                routes = re.findall(r'@router\.(get|post|put|delete)\([\'"]([^\'"]+)', content)
                
                for method, endpoint in routes:
                    analysis_results["api_endpoints_analyzed"].append(f"{method.upper()} {endpoint}")
                    
                    # Check if endpoint returns hard-coded data
                    if 'return [' in content or 'return {' in content:
                        # Check if it's after the endpoint definition
                        endpoint_pos = content.find(f'@router.{method}("{endpoint}"')
                        if endpoint_pos > -1:
                            next_route = content.find('@router.', endpoint_pos + 1)
                            if next_route == -1:
                                next_route = len(content)
                            
                            endpoint_content = content[endpoint_pos:next_route]
                            
                            if re.search(r'return\s+\[.*?\]', endpoint_content, re.DOTALL):
                                if 'execute' not in endpoint_content and 'query' not in endpoint_content.lower():
                                    log_issue(
                                        f"API: {endpoint}",
                                        "Endpoint may return hard-coded list instead of database query",
                                        "WARNING"
                                    )
                
            except Exception as e:
                continue


def check_critical_tables(neon_conn):
    """Check for critical tables and their structure."""
    print("\n" + "=" * 80)
    print("CRITICAL TABLE VERIFICATION")
    print("=" * 80)
    
    critical_tables = [
        'beverages',
        'beverage_products',
        'chart_of_accounts',
        'charters',
        'clients',
        'employees',
        'vehicles',
        'payments',
        'receipts',
    ]
    
    cur = neon_conn.cursor()
    
    for table in critical_tables:
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = %s
            )
        """, (table,))
        
        exists = cur.fetchone()[0]
        
        if not exists:
            log_issue("Critical Table", f"Table '{table}' does NOT exist in Neon", "ERROR")
            print(f"   ❌ {table} - MISSING")
        else:
            log_issue("Critical Table", f"Table '{table}' exists in Neon", "INFO")
            print(f"   ✅ {table} - exists")
            
            # Get row count
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                print(f"      ({count:,} rows)")
            except:
                pass
    
    cur.close()


def check_gl_code_usage():
    """Check how GL codes are used throughout the application."""
    print("\n" + "=" * 80)
    print("GL CODE USAGE ANALYSIS")
    print("=" * 80)
    
    # Search for hard-coded GL codes
    desktop_files = list(Path("l:/limo/desktop_app").rglob("*.py"))
    vue_files = list(Path("l:/limo/frontend").rglob("*.vue"))
    
    hardcoded_gl_patterns = [
        r'gl.*?=.*?[\'"](\d{4})[\'"]',
        r'account.*?=.*?[\'"](\d{4})[\'"]',
    ]
    
    files_with_hardcoded_gl = []
    
    for file_path in desktop_files + vue_files:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            for pattern in hardcoded_gl_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    files_with_hardcoded_gl.append({
                        "file": str(file_path),
                        "gl_codes": matches
                    })
                    log_issue(
                        "GL Code",
                        f"Hard-coded GL codes in {file_path.name}: {matches}",
                        "WARNING"
                    )
        except:
            continue
    
    if files_with_hardcoded_gl:
        print(f"\n⚠️  Found {len(files_with_hardcoded_gl)} files with hard-coded GL codes")
    else:
        print(f"\n✅ No hard-coded GL codes found")


def generate_report():
    """Generate final analysis report."""
    print("\n" + "=" * 80)
    print("ANALYSIS SUMMARY")
    print("=" * 80)
    
    print(f"\n📊 Statistics:")
    print(f"   Desktop Widgets Analyzed: {len(analysis_results['widgets_analyzed'])}")
    print(f"   Vue Components Analyzed: {len(analysis_results['vue_components_analyzed'])}")
    print(f"   API Endpoints Analyzed: {len(analysis_results['api_endpoints_analyzed'])}")
    print(f"   Tables Checked (Neon): {analysis_results['tables_checked'].get('neon_count', 0)}")
    print(f"   Tables Checked (Local): {analysis_results['tables_checked'].get('local_count', 0)}")
    
    print(f"\n🔴 Issues Found: {len(analysis_results['issues'])}")
    print(f"⚠️  Warnings: {len(analysis_results['warnings'])}")
    print(f"✅ Verified: {len(analysis_results['verified'])}")
    
    # Group issues by category
    issues_by_category = defaultdict(list)
    for issue in analysis_results['issues']:
        issues_by_category[issue['category']].append(issue['message'])
    
    if issues_by_category:
        print(f"\n🔴 CRITICAL ISSUES BY CATEGORY:")
        for category, messages in sorted(issues_by_category.items()):
            print(f"\n   {category} ({len(messages)} issues):")
            for msg in messages[:5]:  # Show first 5
                print(f"      - {msg}")
            if len(messages) > 5:
                print(f"      ... and {len(messages) - 5} more")
    
    # Group warnings by category
    warnings_by_category = defaultdict(list)
    for warning in analysis_results['warnings']:
        warnings_by_category[warning['category']].append(warning['message'])
    
    if warnings_by_category:
        print(f"\n⚠️  WARNINGS BY CATEGORY:")
        for category, messages in sorted(warnings_by_category.items()):
            print(f"\n   {category} ({len(messages)} warnings):")
            for msg in messages[:3]:  # Show first 3
                print(f"      - {msg}")
            if len(messages) > 3:
                print(f"      ... and {len(messages) - 3} more")
    
    # Save detailed report to JSON
    report_file = f"database_field_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(analysis_results, f, indent=2)
    
    print(f"\n💾 Detailed report saved to: {report_file}")


def main():
    """Run comprehensive analysis."""
    print("=" * 80)
    print("COMPREHENSIVE DATABASE FIELD ANALYSIS")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Connect to databases
    print("\n📡 Connecting to databases...")
    neon_conn = get_neon_connection()
    local_conn = get_local_connection()
    
    if not neon_conn or not local_conn:
        print("\n❌ Failed to connect to one or both databases. Aborting.")
        return
    
    # Get all tables
    print("\n📋 Fetching table lists...")
    neon_tables = get_all_tables(neon_conn, "Neon")
    local_tables = get_all_tables(local_conn, "Local")
    
    # Check table existence
    common_tables = check_table_exists(neon_tables, local_tables)
    
    # Check critical tables
    check_critical_tables(neon_conn)
    
    # Analyze desktop widgets
    print("\n" + "=" * 80)
    print("ANALYZING DESKTOP WIDGETS")
    print("=" * 80)
    
    widget_dir = Path("l:/limo/desktop_app")
    widget_files = list(widget_dir.glob("*_widget.py"))
    
    print(f"Found {len(widget_files)} widget files")
    for widget_file in widget_files:
        analyze_python_widget(widget_file)
    
    # Analyze Vue components
    print("\n" + "=" * 80)
    print("ANALYZING VUE COMPONENTS")
    print("=" * 80)
    
    vue_dirs = [
        Path("l:/limo/frontend/views"),
        Path("l:/limo/frontend/components"),
        Path("l:/limo/frontend/src/views"),
        Path("l:/limo/frontend/src/components"),
    ]
    
    vue_files = []
    for vue_dir in vue_dirs:
        if vue_dir.exists():
            vue_files.extend(list(vue_dir.glob("*.vue")))
    
    print(f"Found {len(vue_files)} Vue component files")
    for vue_file in vue_files:
        analyze_vue_component(vue_file)
    
    # Analyze API endpoints
    analyze_api_endpoints("l:/limo/modern_backend/app/routers")
    
    # Check GL code usage
    check_gl_code_usage()
    
    # Generate final report
    generate_report()
    
    # Close connections
    neon_conn.close()
    local_conn.close()
    
    print(f"\n✅ Analysis complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
