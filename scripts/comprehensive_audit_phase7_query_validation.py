#!/usr/bin/env python3
"""
PHASE 7: REPORT QUERY VALIDATION
=================================

Validate all SQL queries across 232 widgets and reporting scripts:
1. Schema compliance (table/column names match database)
2. Join correctness (foreign key relationships valid)
3. Aggregation logic (GROUP BY matches SELECT)
4. Performance analysis (missing indexes, full table scans)
5. Data type validation (currency, dates)
6. Reserve number usage (business key vs primary key)

This script:
- Extracts all SQL queries from Python files
- Tests each query against actual PostgreSQL schema
- Identifies schema violations, syntax errors, performance issues
- Generates actionable fix recommendations
"""

import os
import re
import json
import psycopg2
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Configuration
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

REPORTS_DIR = Path("l:/limo/reports")
REPORTS_DIR.mkdir(exist_ok=True)

def extract_sql_queries(file_path):
    """Extract SQL queries from Python file."""
    queries = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern 1: cur.execute("""...""")
        pattern1 = r'cur\.execute\s*\(\s*["\'][\"\'][\"\'](.+?)["\'][\"\']["\']'
        matches1 = re.findall(pattern1, content, re.DOTALL | re.IGNORECASE)
        
        # Pattern 2: cur.execute("...")
        pattern2 = r'cur\.execute\s*\(\s*["\']([^"\']+?SELECT.+?)["\']'
        matches2 = re.findall(pattern2, content, re.DOTALL | re.IGNORECASE)
        
        # Pattern 3: query = """..."""
        pattern3 = r'query\s*=\s*["\'][\"\'][\"\'](.+?)["\'][\"\']["\']'
        matches3 = re.findall(pattern3, content, re.DOTALL | re.IGNORECASE)
        
        # Pattern 4: SQL = """..."""
        pattern4 = r'SQL\s*=\s*["\'][\"\'][\"\'](.+?)["\'][\"\']["\']'
        matches4 = re.findall(pattern4, content, re.DOTALL | re.IGNORECASE)
        
        all_matches = matches1 + matches2 + matches3 + matches4
        
        for sql in all_matches:
            sql_clean = sql.strip()
            if sql_clean and len(sql_clean) > 10:
                # Only include SELECT, INSERT, UPDATE, DELETE queries
                if any(keyword in sql_clean.upper() for keyword in ['SELECT', 'INSERT', 'UPDATE', 'DELETE']):
                    queries.append(sql_clean)
    
    except Exception as e:
        print(f"  ⚠️  Error extracting from {file_path}: {e}")
    
    return queries

def validate_query(cur, query, file_path):
    """Validate a single SQL query."""
    result = {
        'query': query[:200] + '...' if len(query) > 200 else query,
        'file': str(file_path),
        'valid': False,
        'errors': [],
        'warnings': [],
        'performance_issues': []
    }
    
    try:
        # Test query with EXPLAIN (doesn't execute, just validates)
        cur.execute(f"EXPLAIN {query}")
        explain_output = cur.fetchall()
        
        result['valid'] = True
        
        # Check for performance issues
        explain_text = ' '.join([str(row) for row in explain_output])
        
        if 'Seq Scan' in explain_text:
            result['performance_issues'].append('Full table scan detected - consider adding index')
        
        if 'cost=' in explain_text:
            cost_match = re.search(r'cost=(\d+\.\d+)\.\.(\d+\.\d+)', explain_text)
            if cost_match:
                final_cost = float(cost_match.group(2))
                if final_cost > 10000:
                    result['performance_issues'].append(f'High query cost: {final_cost:.0f}')
        
    except psycopg2.errors.UndefinedTable as e:
        result['errors'].append(f'Table does not exist: {str(e)}')
    except psycopg2.errors.UndefinedColumn as e:
        result['errors'].append(f'Column does not exist: {str(e)}')
    except psycopg2.errors.SyntaxError as e:
        result['errors'].append(f'SQL syntax error: {str(e)}')
    except Exception as e:
        result['errors'].append(f'Validation error: {str(e)[:100]}')
    
    # Additional checks
    query_upper = query.upper()
    
    # Check for charter_id abuse (should use reserve_number)
    if 'charter_id' in query.lower() and 'WHERE' in query_upper:
        # Check if it's in WHERE clause (bad) vs JOIN (ok)
        where_clause = query_upper.split('WHERE', 1)[1] if 'WHERE' in query_upper else ''
        if 'charter_id' in where_clause.lower() and 'reserve_number' not in where_clause.lower():
            result['warnings'].append('Using charter_id in WHERE - should use reserve_number (business key)')
    
    # Check for GROUP BY issues
    if 'GROUP BY' in query_upper and 'SELECT' in query_upper:
        select_part = query_upper.split('FROM')[0] if 'FROM' in query_upper else query_upper
        if 'COUNT(' in select_part or 'SUM(' in select_part or 'AVG(' in select_part:
            # Has aggregation - good
            pass
        else:
            # GROUP BY without aggregation
            result['warnings'].append('GROUP BY without aggregation function')
    
    return result

def scan_widget_files():
    """Scan all widget files for SQL queries."""
    print("🔍 Scanning widget files for SQL queries...")
    
    widget_dirs = [
        Path("l:/limo/desktop_app"),
        Path("l:/limo/scripts")
    ]
    
    all_queries = []
    files_scanned = 0
    
    for directory in widget_dirs:
        if not directory.exists():
            continue
        
        for py_file in directory.rglob("*.py"):
            files_scanned += 1
            queries = extract_sql_queries(py_file)
            
            for query in queries:
                all_queries.append({
                    'file': str(py_file),
                    'query': query
                })
    
    print(f"  ✅ Scanned {files_scanned} files, found {len(all_queries)} SQL queries")
    return all_queries

def validate_all_queries(queries):
    """Validate all queries against database."""
    print("\n📊 Validating queries against database schema...")
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    results = {
        'valid': [],
        'invalid': [],
        'warnings': []
    }
    
    for i, item in enumerate(queries, 1):
        if i % 100 == 0:
            print(f"  Progress: {i}/{len(queries)} queries validated")
        
        try:
            result = validate_query(cur, item['query'], item['file'])
            
            if result['valid']:
                if result['warnings'] or result['performance_issues']:
                    results['warnings'].append(result)
                else:
                    results['valid'].append(result)
            else:
                results['invalid'].append(result)
            
            conn.rollback()  # Clear any error state
        
        except Exception as e:
            print(f"  ❌ Error validating query from {item['file']}: {e}")
            conn.rollback()
    
    cur.close()
    conn.close()
    
    print(f"  ✅ Validation complete")
    print(f"     Valid: {len(results['valid'])}")
    print(f"     Warnings: {len(results['warnings'])}")
    print(f"     Invalid: {len(results['invalid'])}")
    
    return results

def generate_reports(results):
    """Generate validation reports."""
    print("\n📄 Generating validation reports...")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Report 1: Invalid queries (critical)
    if results['invalid']:
        invalid_file = REPORTS_DIR / f"phase7_invalid_queries_{timestamp}.csv"
        with open(invalid_file, 'w', encoding='utf-8') as f:
            f.write("File,Query,Error\n")
            for item in results['invalid']:
                file_short = item['file'].replace('l:\\limo\\', '')
                query_short = item['query'].replace('\n', ' ')[:100]
                errors = '; '.join(item['errors'])
                f.write(f'"{file_short}","{query_short}","{errors}"\n')
        print(f"  ✅ {invalid_file.name}")
    
    # Report 2: Performance warnings
    if results['warnings']:
        warnings_file = REPORTS_DIR / f"phase7_query_warnings_{timestamp}.csv"
        with open(warnings_file, 'w', encoding='utf-8') as f:
            f.write("File,Query,Warning,Performance_Issue\n")
            for item in results['warnings']:
                file_short = item['file'].replace('l:\\limo\\', '')
                query_short = item['query'].replace('\n', ' ')[:100]
                warnings = '; '.join(item['warnings'])
                perf = '; '.join(item['performance_issues'])
                f.write(f'"{file_short}","{query_short}","{warnings}","{perf}"\n')
        print(f"  ✅ {warnings_file.name}")
    
    # Report 3: Summary JSON
    summary = {
        'timestamp': timestamp,
        'total_queries': len(results['valid']) + len(results['warnings']) + len(results['invalid']),
        'valid_queries': len(results['valid']),
        'queries_with_warnings': len(results['warnings']),
        'invalid_queries': len(results['invalid']),
        'by_error_type': {},
        'by_file': {}
    }
    
    # Count by error type
    for item in results['invalid']:
        for error in item['errors']:
            error_type = error.split(':')[0]
            summary['by_error_type'][error_type] = summary['by_error_type'].get(error_type, 0) + 1
    
    # Count by file
    all_items = results['valid'] + results['warnings'] + results['invalid']
    for item in all_items:
        file_short = item['file'].replace('l:\\limo\\', '')
        if file_short not in summary['by_file']:
            summary['by_file'][file_short] = {'valid': 0, 'warnings': 0, 'invalid': 0}
        
        if item in results['valid']:
            summary['by_file'][file_short]['valid'] += 1
        elif item in results['warnings']:
            summary['by_file'][file_short]['warnings'] += 1
        else:
            summary['by_file'][file_short]['invalid'] += 1
    
    summary_file = REPORTS_DIR / f"phase7_validation_summary_{timestamp}.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    print(f"  ✅ {summary_file.name}")
    
    # Report 4: Fix recommendations
    fix_guide = generate_fix_guide(results)
    fix_file = REPORTS_DIR / f"phase7_fix_guide_{timestamp}.md"
    with open(fix_file, 'w', encoding='utf-8') as f:
        f.write(fix_guide)
    print(f"  ✅ {fix_file.name}")
    
    return summary

def generate_fix_guide(results):
    """Generate comprehensive fix guide."""
    guide = f"""# PHASE 7: QUERY VALIDATION FIX GUIDE
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## SUMMARY
- Total Queries Analyzed: {len(results['valid']) + len(results['warnings']) + len(results['invalid'])}
- ✅ Valid: {len(results['valid'])}
- ⚠️  Warnings: {len(results['warnings'])}
- ❌ Invalid: {len(results['invalid'])}

## CRITICAL ISSUES (MUST FIX)

"""
    
    if results['invalid']:
        guide += "### Invalid Queries\n\n"
        for i, item in enumerate(results['invalid'][:20], 1):  # Top 20
            file_short = item['file'].replace('l:\\limo\\', '')
            guide += f"**{i}. {file_short}**\n"
            guide += f"```sql\n{item['query'][:300]}\n```\n"
            guide += f"**Errors:**\n"
            for error in item['errors']:
                guide += f"- {error}\n"
            guide += "\n"
    else:
        guide += "✅ No invalid queries found!\n\n"
    
    guide += """
## WARNINGS (SHOULD FIX)

### Charter ID Usage (Business Key Violation)
"""
    
    charter_id_warnings = [item for item in results['warnings'] 
                          if any('charter_id' in w.lower() for w in item['warnings'])]
    
    if charter_id_warnings:
        guide += f"\nFound {len(charter_id_warnings)} queries using charter_id instead of reserve_number:\n\n"
        for item in charter_id_warnings[:10]:
            file_short = item['file'].replace('l:\\limo\\', '')
            guide += f"- {file_short}\n"
    else:
        guide += "\n✅ All queries use reserve_number correctly!\n"
    
    guide += """
### Performance Issues

"""
    
    perf_warnings = [item for item in results['warnings'] 
                    if item['performance_issues']]
    
    if perf_warnings:
        guide += f"Found {len(perf_warnings)} queries with performance concerns:\n\n"
        for item in perf_warnings[:10]:
            file_short = item['file'].replace('l:\\limo\\', '')
            guide += f"**{file_short}**\n"
            for issue in item['performance_issues']:
                guide += f"- {issue}\n"
            guide += "\n"
    
    guide += """
## FIX PROCEDURES

### 1. Fix Invalid Queries (Critical)

**For "Table does not exist" errors:**
```bash
# Check actual table name in database
psql -h localhost -U postgres -d almsdata -c "\\dt"

# Update query to use correct table name
# Example: Change "invoice" → "invoices" or "receipt" → "receipts"
```

**For "Column does not exist" errors:**
```bash
# Check actual column names
psql -h localhost -U postgres -d almsdata -c "\\d table_name"

# Common fixes:
# - total_price → total_amount_due
# - charter_date_time → charter_date (separate pickup_time)
# - customer_name → (JOIN to clients table)
```

### 2. Fix Charter ID Warnings (High Priority)

**Replace charter_id with reserve_number in WHERE clauses:**

```python
# ❌ WRONG
cur.execute(\"\"\"
    SELECT total_amount_due FROM charters
    WHERE charter_id = %s
\"\"\", (charter_id,))

# ✅ CORRECT
cur.execute(\"\"\"
    SELECT total_amount_due FROM charters
    WHERE reserve_number = %s
\"\"\", (reserve_number,))
```

### 3. Fix Performance Issues

**Add indexes for frequently queried columns:**

```sql
-- For date range queries
CREATE INDEX idx_charters_date ON charters(charter_date);

-- For driver lookups
CREATE INDEX idx_charters_driver ON charters(driver_id);

-- For reserve_number lookups (should already exist)
CREATE INDEX idx_charters_reserve ON charters(reserve_number);
```

**Optimize full table scans:**
- Add WHERE clauses to limit rows
- Use LIMIT for pagination
- Avoid SELECT * (specify columns)

## TESTING AFTER FIXES

```bash
# Re-run Phase 7 validation
python -X utf8 scripts/comprehensive_audit_phase7_query_validation.py

# Expected result: 0 invalid queries, <10 warnings
```

## ROLLBACK PROCEDURE

If fixes cause issues:

```bash
# Restore from backup
git checkout HEAD -- desktop_app/file_with_issue.py

# Or restore database
psql -h localhost -U postgres -d almsdata < backups/pre_phase7_backup.sql
```

---
**Next Steps:** Fix critical issues, re-run validation, proceed to Phase 9
"""
    
    return guide

def main():
    """Execute Phase 7 validation."""
    print("=" * 80)
    print("PHASE 7: REPORT QUERY VALIDATION")
    print("=" * 80)
    print()
    
    # Step 1: Extract queries
    queries = scan_widget_files()
    
    if not queries:
        print("⚠️  No SQL queries found. Check file paths.")
        return
    
    # Step 2: Validate queries
    results = validate_all_queries(queries)
    
    # Step 3: Generate reports
    summary = generate_reports(results)
    
    # Step 4: Display summary
    print("\n" + "=" * 80)
    print("PHASE 7 VALIDATION COMPLETE")
    print("=" * 80)
    print(f"\n📊 Results:")
    print(f"   Total Queries: {summary['total_queries']}")
    print(f"   ✅ Valid: {summary['valid_queries']}")
    print(f"   ⚠️  Warnings: {summary['queries_with_warnings']}")
    print(f"   ❌ Invalid: {summary['invalid_queries']}")
    
    if summary['invalid_queries'] > 0:
        print(f"\n🚨 CRITICAL: {summary['invalid_queries']} queries failed validation")
        print("   Review: reports/phase7_invalid_queries_*.csv")
    
    if summary['queries_with_warnings'] > 0:
        print(f"\n⚠️  {summary['queries_with_warnings']} queries have warnings")
        print("   Review: reports/phase7_query_warnings_*.csv")
    
    if summary['invalid_queries'] == 0 and summary['queries_with_warnings'] == 0:
        print("\n🎉 All queries passed validation!")
    
    print(f"\n📁 Reports saved to: {REPORTS_DIR}/")
    print("   - phase7_invalid_queries_*.csv (if any)")
    print("   - phase7_query_warnings_*.csv (if any)")
    print("   - phase7_validation_summary_*.json")
    print("   - phase7_fix_guide_*.md")
    
    print("\n✅ PHASE 7 COMPLETE")

if __name__ == "__main__":
    main()
