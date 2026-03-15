#!/usr/bin/env python3
"""
DATABASE COMPARISON: Local vs Neon
===================================

Comprehensive comparison of local almsdata and Neon databases:
1. Table existence and row counts
2. Column schemas and data types
3. Indexes and constraints
4. Data sample comparisons
5. Recommendations for sync direction

NO CHANGES ARE MADE - This is analysis only.
"""

import os
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

# Comparison results
comparison = {
    "timestamp": datetime.now().isoformat(),
    "local_analysis": {},
    "neon_analysis": {},
    "differences": {
        "missing_in_neon": [],
        "missing_in_local": [],
        "schema_mismatches": [],
        "row_count_differences": [],
    },
    "recommendations": []
}


def get_connection(db_type="local"):
    """Get database connection."""
    try:
        if db_type == "local":
            conn = psycopg2.connect(
                host=LOCAL_HOST,
                database=LOCAL_DB,
                user=LOCAL_USER,
                password=LOCAL_PASSWORD
            )
            print(f"✅ Connected to LOCAL database: {LOCAL_DB}")
            return conn
        else:  # neon
            conn = psycopg2.connect(
                host=NEON_HOST,
                database=NEON_DB,
                user=NEON_USER,
                password=NEON_PASSWORD,
                sslmode='require',
                connect_timeout=10
            )
            print(f"✅ Connected to NEON database: {NEON_DB}")
            return conn
    except Exception as e:
        print(f"❌ Failed to connect to {db_type.upper()} database: {e}")
        return None


def analyze_database(conn, db_name):
    """Comprehensive analysis of a database."""
    print(f"\n{'=' * 80}")
    print(f"ANALYZING {db_name.upper()} DATABASE")
    print(f"{'=' * 80}")
    
    cur = conn.cursor()
    analysis = {
        "tables": {},
        "total_tables": 0,
        "total_rows": 0
    }
    
    # Get all tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    
    tables = [row[0] for row in cur.fetchall()]
    analysis["total_tables"] = len(tables)
    
    print(f"\n📊 Found {len(tables)} tables")
    print(f"\nAnalyzing each table (schema + row count)...")
    
    for i, table in enumerate(tables, 1):
        if i % 20 == 0:
            print(f"   Progress: {i}/{len(tables)} tables analyzed...")
        
        table_info = {
            "columns": [],
            "row_count": 0,
            "indexes": [],
            "primary_key": None,
            "foreign_keys": []
        }
        
        # Get columns
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
        """, (table,))
        
        table_info["columns"] = [
            {
                "name": row[0],
                "type": row[1],
                "max_length": row[2],
                "nullable": row[3] == 'YES',
                "default": row[4]
            }
            for row in cur.fetchall()
        ]
        
        # Get row count
        try:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            table_info["row_count"] = cur.fetchone()[0]
            analysis["total_rows"] += table_info["row_count"]
        except:
            table_info["row_count"] = -1  # Error getting count
        
        # Get primary key
        cur.execute("""
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid
                AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = %s::regclass
            AND i.indisprimary
        """, (table,))
        
        pk_cols = [row[0] for row in cur.fetchall()]
        if pk_cols:
            table_info["primary_key"] = pk_cols
        
        # Get indexes
        cur.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = %s
            AND schemaname = 'public'
        """, (table,))
        
        table_info["indexes"] = [
            {"name": row[0], "definition": row[1]}
            for row in cur.fetchall()
        ]
        
        # Get foreign keys
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
        """, (table,))
        
        table_info["foreign_keys"] = [
            {
                "column": row[0],
                "references_table": row[1],
                "references_column": row[2]
            }
            for row in cur.fetchall()
        ]
        
        analysis["tables"][table] = table_info
    
    print(f"✅ Analysis complete: {len(tables)} tables, {analysis['total_rows']:,} total rows")
    
    cur.close()
    return analysis


def compare_schemas(local_analysis, neon_analysis):
    """Compare schemas between local and Neon."""
    print(f"\n{'=' * 80}")
    print(f"SCHEMA COMPARISON")
    print(f"{'=' * 80}")
    
    local_tables = set(local_analysis["tables"].keys())
    neon_tables = set(neon_analysis["tables"].keys())
    
    # Tables missing in Neon
    missing_in_neon = local_tables - neon_tables
    # Tables missing in Local
    missing_in_local = neon_tables - local_tables
    # Common tables
    common_tables = local_tables & neon_tables
    
    print(f"\n📊 Table Comparison:")
    print(f"   Local tables: {len(local_tables)}")
    print(f"   Neon tables: {len(neon_tables)}")
    print(f"   Common tables: {len(common_tables)}")
    print(f"   Missing in Neon: {len(missing_in_neon)}")
    print(f"   Missing in Local: {len(missing_in_local)}")
    
    # Analyze missing tables
    if missing_in_neon:
        print(f"\n❌ TABLES MISSING IN NEON ({len(missing_in_neon)}):")
        
        # Categorize by importance (based on row count and name)
        critical = []
        important = []
        staging = []
        
        for table in sorted(missing_in_neon):
            row_count = local_analysis["tables"][table]["row_count"]
            
            if any(x in table.lower() for x in ['staging', 'backup', '_tmp', 'temp']):
                staging.append((table, row_count))
            elif row_count > 100 or any(x in table.lower() for x in ['charter', 'payment', 'receipt', 'employee', 'client']):
                critical.append((table, row_count))
            else:
                important.append((table, row_count))
        
        if critical:
            print(f"\n   🔴 CRITICAL ({len(critical)} tables):")
            for table, count in sorted(critical, key=lambda x: x[1], reverse=True):
                print(f"      {table:50} {count:>10,} rows")
                comparison["differences"]["missing_in_neon"].append({
                    "table": table,
                    "priority": "CRITICAL",
                    "row_count": count
                })
        
        if important:
            print(f"\n   ⚠️  IMPORTANT ({len(important)} tables):")
            for table, count in sorted(important, key=lambda x: x[1], reverse=True)[:20]:
                print(f"      {table:50} {count:>10,} rows")
                comparison["differences"]["missing_in_neon"].append({
                    "table": table,
                    "priority": "IMPORTANT",
                    "row_count": count
                })
            if len(important) > 20:
                print(f"      ... and {len(important) - 20} more")
        
        if staging:
            print(f"\n   ℹ️  STAGING/BACKUP ({len(staging)} tables):")
            for table, count in sorted(staging, key=lambda x: x[1], reverse=True)[:10]:
                print(f"      {table:50} {count:>10,} rows")
                comparison["differences"]["missing_in_neon"].append({
                    "table": table,
                    "priority": "LOW",
                    "row_count": count
                })
            if len(staging) > 10:
                print(f"      ... and {len(staging) - 10} more")
    
    if missing_in_local:
        print(f"\n⚠️  TABLES MISSING IN LOCAL ({len(missing_in_local)}):")
        for table in sorted(missing_in_local)[:30]:
            row_count = neon_analysis["tables"][table]["row_count"]
            print(f"   {table:50} {row_count:>10,} rows")
            comparison["differences"]["missing_in_local"].append({
                "table": table,
                "row_count": row_count
            })
        if len(missing_in_local) > 30:
            print(f"   ... and {len(missing_in_local) - 30} more")
    
    # Compare common tables
    if common_tables:
        print(f"\n📋 COMPARING COMMON TABLES ({len(common_tables)}):")
        
        schema_diffs = []
        row_count_diffs = []
        
        for table in sorted(common_tables):
            local_table = local_analysis["tables"][table]
            neon_table = neon_analysis["tables"][table]
            
            # Compare columns
            local_cols = {c["name"]: c for c in local_table["columns"]}
            neon_cols = {c["name"]: c for c in neon_table["columns"]}
            
            missing_cols_neon = set(local_cols.keys()) - set(neon_cols.keys())
            missing_cols_local = set(neon_cols.keys()) - set(local_cols.keys())
            
            type_mismatches = []
            for col_name in set(local_cols.keys()) & set(neon_cols.keys()):
                if local_cols[col_name]["type"] != neon_cols[col_name]["type"]:
                    type_mismatches.append({
                        "column": col_name,
                        "local_type": local_cols[col_name]["type"],
                        "neon_type": neon_cols[col_name]["type"]
                    })
            
            if missing_cols_neon or missing_cols_local or type_mismatches:
                schema_diffs.append({
                    "table": table,
                    "missing_in_neon": list(missing_cols_neon),
                    "missing_in_local": list(missing_cols_local),
                    "type_mismatches": type_mismatches
                })
            
            # Compare row counts
            local_count = local_table["row_count"]
            neon_count = neon_table["row_count"]
            
            if local_count != neon_count and local_count >= 0 and neon_count >= 0:
                diff = local_count - neon_count
                diff_pct = (abs(diff) / max(local_count, 1)) * 100
                
                if diff_pct > 1 or abs(diff) > 100:  # More than 1% or 100 rows difference
                    row_count_diffs.append({
                        "table": table,
                        "local_count": local_count,
                        "neon_count": neon_count,
                        "difference": diff,
                        "diff_percent": diff_pct
                    })
        
        if schema_diffs:
            print(f"\n   ⚠️  SCHEMA DIFFERENCES ({len(schema_diffs)} tables):")
            for diff in schema_diffs[:10]:
                print(f"\n      Table: {diff['table']}")
                if diff['missing_in_neon']:
                    print(f"         Columns in LOCAL only: {', '.join(diff['missing_in_neon'])}")
                if diff['missing_in_local']:
                    print(f"         Columns in NEON only: {', '.join(diff['missing_in_local'])}")
                if diff['type_mismatches']:
                    print(f"         Type mismatches:")
                    for tm in diff['type_mismatches']:
                        print(f"            {tm['column']}: LOCAL={tm['local_type']}, NEON={tm['neon_type']}")
                
                comparison["differences"]["schema_mismatches"].append(diff)
            
            if len(schema_diffs) > 10:
                print(f"\n      ... and {len(schema_diffs) - 10} more tables with schema differences")
        
        if row_count_diffs:
            print(f"\n   📊 ROW COUNT DIFFERENCES ({len(row_count_diffs)} tables):")
            
            # Sort by largest absolute difference
            row_count_diffs.sort(key=lambda x: abs(x['difference']), reverse=True)
            
            for diff in row_count_diffs[:20]:
                direction = "LOCAL>" if diff['difference'] > 0 else "NEON>"
                print(f"      {diff['table']:40} {direction} Local: {diff['local_count']:>8,} | Neon: {diff['neon_count']:>8,} | Diff: {diff['difference']:>+8,} ({diff['diff_percent']:>5.1f}%)")
                
                comparison["differences"]["row_count_differences"].append(diff)
            
            if len(row_count_diffs) > 20:
                print(f"\n      ... and {len(row_count_diffs) - 20} more tables with row count differences")
        
        if not schema_diffs and not row_count_diffs:
            print(f"\n   ✅ All common tables have matching schemas and similar row counts!")


def generate_recommendations(local_analysis, neon_analysis):
    """Generate sync recommendations."""
    print(f"\n{'=' * 80}")
    print(f"SYNC RECOMMENDATIONS")
    print(f"{'=' * 80}")
    
    missing_in_neon = comparison["differences"]["missing_in_neon"]
    missing_in_local = comparison["differences"]["missing_in_local"]
    schema_mismatches = comparison["differences"]["schema_mismatches"]
    row_count_diffs = comparison["differences"]["row_count_differences"]
    
    recommendations = []
    
    # Critical tables to sync to Neon
    critical_tables = [t for t in missing_in_neon if t["priority"] == "CRITICAL"]
    if critical_tables:
        print(f"\n🔴 CRITICAL: Sync to Neon ({len(critical_tables)} tables)")
        print(f"   These tables have significant data and are likely used by the application:")
        for t in critical_tables[:10]:
            print(f"      • {t['table']} ({t['row_count']:,} rows)")
            recommendations.append({
                "action": "SYNC_TO_NEON",
                "priority": "CRITICAL",
                "table": t['table'],
                "reason": f"Has {t['row_count']:,} rows and appears to be application data"
            })
        if len(critical_tables) > 10:
            print(f"      ... and {len(critical_tables) - 10} more")
    
    # Important tables to sync to Neon
    important_tables = [t for t in missing_in_neon if t["priority"] == "IMPORTANT"]
    if important_tables:
        print(f"\n⚠️  IMPORTANT: Consider syncing to Neon ({len(important_tables)} tables)")
        for t in important_tables[:5]:
            print(f"      • {t['table']} ({t['row_count']:,} rows)")
            recommendations.append({
                "action": "REVIEW_THEN_SYNC",
                "priority": "IMPORTANT",
                "table": t['table'],
                "reason": f"Has {t['row_count']:,} rows - review if needed by app"
            })
        if len(important_tables) > 5:
            print(f"      ... and {len(important_tables) - 5} more")
    
    # Tables in Neon but not local
    if missing_in_local:
        print(f"\n📥 INFO: Tables in Neon only ({len(missing_in_local)} tables)")
        print(f"   These may be Neon-specific features or newer additions:")
        for t in missing_in_local[:5]:
            print(f"      • {t['table']} ({t['row_count']:,} rows)")
            recommendations.append({
                "action": "DOCUMENT",
                "priority": "INFO",
                "table": t['table'],
                "reason": "Exists in Neon but not local - may be Neon-specific"
            })
        if len(missing_in_local) > 5:
            print(f"      ... and {len(missing_in_local) - 5} more")
    
    # Schema mismatches
    if schema_mismatches:
        print(f"\n⚠️  SCHEMA SYNC REQUIRED ({len(schema_mismatches)} tables)")
        print(f"   These tables exist in both but have schema differences:")
        for diff in schema_mismatches[:5]:
            print(f"      • {diff['table']}")
            if diff['missing_in_neon']:
                print(f"         - Add to Neon: {', '.join(diff['missing_in_neon'][:3])}")
            if diff['type_mismatches']:
                print(f"         - Type conflicts: {len(diff['type_mismatches'])} columns")
            
            recommendations.append({
                "action": "SCHEMA_SYNC",
                "priority": "HIGH",
                "table": diff['table'],
                "reason": "Schema mismatch between local and Neon"
            })
        if len(schema_mismatches) > 5:
            print(f"      ... and {len(schema_mismatches) - 5} more")
    
    # Row count differences
    large_diffs = [d for d in row_count_diffs if abs(d['difference']) > 1000 or d['diff_percent'] > 10]
    if large_diffs:
        print(f"\n📊 DATA SYNC RECOMMENDED ({len(large_diffs)} tables)")
        print(f"   These tables have significant row count differences:")
        for diff in large_diffs[:5]:
            direction = "LOCAL → NEON" if diff['difference'] > 0 else "NEON → LOCAL"
            print(f"      • {diff['table']:40} {direction:15} ({abs(diff['difference']):,} rows)")
            
            recommendations.append({
                "action": "DATA_SYNC",
                "priority": "MEDIUM",
                "table": diff['table'],
                "reason": f"Row count difference: {abs(diff['difference']):,} rows ({diff['diff_percent']:.1f}%)",
                "direction": "to_neon" if diff['difference'] > 0 else "to_local"
            })
        if len(large_diffs) > 5:
            print(f"      ... and {len(large_diffs) - 5} more")
    
    comparison["recommendations"] = recommendations
    
    # Summary
    print(f"\n{'=' * 80}")
    print(f"RECOMMENDATION SUMMARY")
    print(f"{'=' * 80}")
    
    critical_count = len([r for r in recommendations if r['priority'] == 'CRITICAL'])
    high_count = len([r for r in recommendations if r['priority'] == 'HIGH'])
    medium_count = len([r for r in recommendations if r['priority'] == 'MEDIUM'])
    
    print(f"\n📋 Total Recommendations: {len(recommendations)}")
    print(f"   🔴 CRITICAL: {critical_count} (must sync to Neon)")
    print(f"   🟠 HIGH: {high_count} (schema fixes required)")
    print(f"   🟡 MEDIUM: {medium_count} (data sync recommended)")
    print(f"   ℹ️  INFO: {len(recommendations) - critical_count - high_count - medium_count} (document/review)")


def save_results():
    """Save comparison results to file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"database_comparison_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(comparison, f, indent=2)
    
    print(f"\n💾 Detailed comparison saved to: {filename}")
    
    # Also save a summary text file
    summary_file = f"database_comparison_summary_{timestamp}.txt"
    with open(summary_file, 'w') as f:
        f.write("DATABASE COMPARISON SUMMARY\n")
        f.write("=" * 80 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write(f"Local Database: {LOCAL_DB}\n")
        f.write(f"  Tables: {comparison['local_analysis']['total_tables']}\n")
        f.write(f"  Total Rows: {comparison['local_analysis']['total_rows']:,}\n\n")
        
        f.write(f"Neon Database: {NEON_DB}\n")
        f.write(f"  Tables: {comparison['neon_analysis']['total_tables']}\n")
        f.write(f"  Total Rows: {comparison['neon_analysis']['total_rows']:,}\n\n")
        
        f.write(f"Differences:\n")
        f.write(f"  Missing in Neon: {len(comparison['differences']['missing_in_neon'])}\n")
        f.write(f"  Missing in Local: {len(comparison['differences']['missing_in_local'])}\n")
        f.write(f"  Schema Mismatches: {len(comparison['differences']['schema_mismatches'])}\n")
        f.write(f"  Row Count Diffs: {len(comparison['differences']['row_count_differences'])}\n\n")
        
        f.write(f"Recommendations: {len(comparison['recommendations'])}\n")
        critical = len([r for r in comparison['recommendations'] if r['priority'] == 'CRITICAL'])
        f.write(f"  Critical Actions: {critical}\n")
    
    print(f"📄 Summary saved to: {summary_file}")


def main():
    """Run comprehensive database comparison."""
    print("=" * 80)
    print("DATABASE COMPARISON: Local vs Neon")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nLocal: {LOCAL_DB} @ {LOCAL_HOST}")
    print(f"Neon:  {NEON_DB} @ {NEON_HOST}")
    
    # Connect to databases
    local_conn = get_connection("local")
    neon_conn = get_connection("neon")
    
    if not local_conn or not neon_conn:
        print("\n❌ Failed to connect to one or both databases. Aborting.")
        return
    
    # Analyze both databases
    local_analysis = analyze_database(local_conn, "LOCAL")
    neon_analysis = analyze_database(neon_conn, "NEON")
    
    comparison["local_analysis"] = local_analysis
    comparison["neon_analysis"] = neon_analysis
    
    # Compare schemas
    compare_schemas(local_analysis, neon_analysis)
    
    # Generate recommendations
    generate_recommendations(local_analysis, neon_analysis)
    
    # Save results
    save_results()
    
    # Close connections
    local_conn.close()
    neon_conn.close()
    
    print(f"\n✅ Comparison complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nNO CHANGES WERE MADE to either database.")
    print(f"Review the recommendations above and saved files before proceeding.\n")


if __name__ == "__main__":
    main()
