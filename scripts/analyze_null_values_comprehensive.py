"""
Analyze NULL values across all database tables.

Identifies columns with high NULL rates and potential reasons for missing data.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def get_all_tables(cur):
    """Get all user tables in the database."""
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    return [row['table_name'] for row in cur.fetchall()]

def get_table_columns(cur, table_name):
    """Get all columns for a table with their data types."""
    cur.execute("""
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_name = %s
        AND table_schema = 'public'
        ORDER BY ordinal_position
    """, (table_name,))
    return cur.fetchall()

def analyze_column_nulls(cur, table_name, column_name):
    """Analyze NULL values for a specific column."""
    # Get total row count
    cur.execute(f'SELECT COUNT(*) as total FROM "{table_name}"')
    total_rows = cur.fetchone()['total']
    
    if total_rows == 0:
        return None
    
    # Get NULL count
    cur.execute(f'SELECT COUNT(*) as null_count FROM "{table_name}" WHERE "{column_name}" IS NULL')
    null_count = cur.fetchone()['null_count']
    
    # Get non-NULL count
    non_null_count = total_rows - null_count
    
    # Calculate percentage
    null_percentage = (null_count / total_rows * 100) if total_rows > 0 else 0
    
    return {
        'total_rows': total_rows,
        'null_count': null_count,
        'non_null_count': non_null_count,
        'null_percentage': null_percentage
    }

def categorize_null_reason(table_name, column_name, stats, column_info):
    """Suggest reasons why a column might have NULL values."""
    null_pct = stats['null_percentage']
    
    reasons = []
    
    # 100% NULL - completely unused
    if null_pct == 100:
        reasons.append("UNUSED - Column never populated")
    
    # Very high NULL rate (95-99%)
    elif null_pct >= 95:
        reasons.append("RARELY USED - Less than 5% populated")
    
    # High NULL rate (80-94%)
    elif null_pct >= 80:
        reasons.append("SPARSELY POPULATED - Majority missing")
    
    # Medium NULL rate (50-79%)
    elif null_pct >= 50:
        reasons.append("OPTIONAL - More than half missing")
    
    # Low NULL rate (1-49%)
    elif null_pct > 0:
        reasons.append("PARTIALLY POPULATED")
    
    # Check if column is nullable
    if column_info['is_nullable'] == 'NO' and null_pct > 0:
        reasons.append("⚠️  NOT NULL constraint violated!")
    
    # Check if has default value
    if column_info['column_default']:
        reasons.append(f"Has default: {column_info['column_default']}")
    
    # Common patterns
    if 'notes' in column_name.lower() or 'comment' in column_name.lower():
        reasons.append("Notes/comments are typically optional")
    
    if 'email' in column_name.lower() or 'phone' in column_name.lower():
        reasons.append("Contact info may be missing")
    
    if column_name.endswith('_id') and 'fk' not in column_name.lower():
        reasons.append("Foreign key - may indicate missing relationships")
    
    if 'date' in column_name.lower() and null_pct > 50:
        reasons.append("Date not set - event may not have occurred")
    
    return ' | '.join(reasons) if reasons else 'No specific reason identified'

def main():
    print("=" * 100)
    print("NULL VALUE ANALYSIS - All Database Tables")
    print("=" * 100)
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        tables = get_all_tables(cur)
        print(f"📊 Analyzing {len(tables)} tables...\n")
        
        all_issues = []
        
        for table_name in tables:
            columns = get_table_columns(cur, table_name)
            
            table_issues = []
            
            for col_info in columns:
                column_name = col_info['column_name']
                
                # Analyze NULL values
                stats = analyze_column_nulls(cur, table_name, column_name)
                
                if stats is None:
                    continue
                
                # Only report columns with NULL values
                if stats['null_count'] > 0:
                    reason = categorize_null_reason(table_name, column_name, stats, col_info)
                    
                    table_issues.append({
                        'table': table_name,
                        'column': column_name,
                        'data_type': col_info['data_type'],
                        'nullable': col_info['is_nullable'],
                        'stats': stats,
                        'reason': reason
                    })
            
            if table_issues:
                all_issues.extend(table_issues)
        
        # Sort by NULL percentage (highest first)
        all_issues.sort(key=lambda x: x['stats']['null_percentage'], reverse=True)
        
        # Print results grouped by severity
        print("\n" + "=" * 100)
        print("🔴 COMPLETELY UNUSED COLUMNS (100% NULL)")
        print("=" * 100)
        
        unused = [issue for issue in all_issues if issue['stats']['null_percentage'] == 100]
        if unused:
            for issue in unused:
                print(f"\n📋 {issue['table']}.{issue['column']}")
                print(f"   Type: {issue['data_type']} | Nullable: {issue['nullable']}")
                print(f"   Rows: {issue['stats']['total_rows']:,} | All NULL")
                print(f"   Reason: {issue['reason']}")
        else:
            print("✓ No completely unused columns found")
        
        print("\n" + "=" * 100)
        print("🟠 RARELY USED COLUMNS (95-99% NULL)")
        print("=" * 100)
        
        rarely_used = [issue for issue in all_issues if 95 <= issue['stats']['null_percentage'] < 100]
        if rarely_used:
            for issue in rarely_used:
                print(f"\n📋 {issue['table']}.{issue['column']}")
                print(f"   Type: {issue['data_type']} | Nullable: {issue['nullable']}")
                print(f"   Rows: {issue['stats']['total_rows']:,} | NULL: {issue['stats']['null_count']:,} ({issue['stats']['null_percentage']:.1f}%) | Populated: {issue['stats']['non_null_count']:,}")
                print(f"   Reason: {issue['reason']}")
        else:
            print("✓ No rarely used columns found")
        
        print("\n" + "=" * 100)
        print("🟡 SPARSELY POPULATED COLUMNS (80-94% NULL)")
        print("=" * 100)
        
        sparse = [issue for issue in all_issues if 80 <= issue['stats']['null_percentage'] < 95]
        if sparse:
            for issue in sparse[:20]:  # Limit to first 20
                print(f"\n📋 {issue['table']}.{issue['column']}")
                print(f"   Type: {issue['data_type']} | Nullable: {issue['nullable']}")
                print(f"   Rows: {issue['stats']['total_rows']:,} | NULL: {issue['stats']['null_count']:,} ({issue['stats']['null_percentage']:.1f}%) | Populated: {issue['stats']['non_null_count']:,}")
                print(f"   Reason: {issue['reason']}")
            if len(sparse) > 20:
                print(f"\n   ... and {len(sparse) - 20} more")
        else:
            print("✓ No sparsely populated columns found")
        
        print("\n" + "=" * 100)
        print("📊 SUMMARY STATISTICS")
        print("=" * 100)
        
        print(f"\nTotal tables analyzed: {len(tables)}")
        print(f"Total columns with NULLs: {len(all_issues)}")
        print(f"  - 100% NULL: {len(unused)}")
        print(f"  - 95-99% NULL: {len(rarely_used)}")
        print(f"  - 80-94% NULL: {len(sparse)}")
        print(f"  - 50-79% NULL: {len([i for i in all_issues if 50 <= i['stats']['null_percentage'] < 80])}")
        print(f"  - 1-49% NULL: {len([i for i in all_issues if 0 < i['stats']['null_percentage'] < 50])}")
        
        # Export detailed report
        report_file = f"l:\\limo\\reports\\null_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("Table,Column,Data Type,Nullable,Total Rows,NULL Count,Non-NULL Count,NULL %,Reason\n")
            for issue in all_issues:
                f.write(f'"{issue["table"]}","{issue["column"]}","{issue["data_type"]}","{issue["nullable"]}",'
                       f'{issue["stats"]["total_rows"]},{issue["stats"]["null_count"]},{issue["stats"]["non_null_count"]},'
                       f'{issue["stats"]["null_percentage"]:.2f},"{issue["reason"]}"\n')
        
        print(f"\n📄 Detailed report saved to: {report_file}")
        
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
