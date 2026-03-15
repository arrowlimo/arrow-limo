#!/usr/bin/env python3
"""
INVESTIGATE NEEDS REVIEW TABLES
================================

Detailed investigation of tables that need manual review before syncing.
These are tables missing in Neon that may contain important configuration
or reference data.
"""

import os
import psycopg2
from datetime import datetime
from collections import defaultdict
import json
from dotenv import load_dotenv

load_dotenv()

# Database credentials
LOCAL_HOST = "localhost"
LOCAL_DB = os.environ.get("LOCAL_DB_NAME", "almsdata")
LOCAL_USER = os.environ.get("LOCAL_DB_USER", "alms")
LOCAL_PASSWORD = os.environ.get("LOCAL_DB_PASSWORD", "")

NEON_HOST = os.environ.get("NEON_DB_HOST", "")
NEON_DB = os.environ.get("NEON_DB_NAME", "neondb")
NEON_USER = os.environ.get("NEON_DB_USER", "neondb_owner")
NEON_PASSWORD = os.environ.get("NEON_DB_PASSWORD", "")

# Tables to investigate
NEEDS_REVIEW = [
    "employee_pay_master",
    "transaction_categories",
    "transaction_subcategories",
    "tax_periods",
    "tax_returns",
    "tax_variances",
    "tax_overrides",
    "tax_remittances",
    "tax_rollovers",
    "category_mappings",
    "account_categories",
    "category_to_account_map",
]

investigation = {
    "timestamp": datetime.now().isoformat(),
    "tables": {},
    "recommendations": []
}


def get_local_connection():
    """Get local database connection."""
    try:
        conn = psycopg2.connect(
            host=LOCAL_HOST,
            database=LOCAL_DB,
            user=LOCAL_USER,
            password=LOCAL_PASSWORD
        )
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to local DB: {e}")
        return None


def get_neon_connection():
    """Get Neon database connection."""
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
        print(f"❌ Failed to connect to Neon: {e}")
        return None


def check_table_exists(conn, table):
    """Check if table exists."""
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = %s AND table_schema = 'public'
            )
        """, (table,))
        exists = cur.fetchone()[0]
        cur.close()
        return exists
    except Exception as e:
        return False


def get_table_schema(conn, table):
    """Get table schema."""
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                column_name, 
                data_type,
                character_maximum_length,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_name = %s AND table_schema = 'public'
            ORDER BY ordinal_position
        """, (table,))
        
        columns = []
        for row in cur.fetchall():
            col_def = f"{row[0]} {row[1]}"
            if row[2]:
                col_def += f"({row[2]})"
            if row[3] == 'NO':
                col_def += " NOT NULL"
            if row[4]:
                col_def += f" DEFAULT {row[4]}"
            columns.append(col_def)
        
        cur.close()
        return columns
    except Exception as e:
        return [f"Error: {e}"]


def get_row_count(conn, table):
    """Get row count."""
    try:
        cur = conn.cursor()
        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        count = cur.fetchone()[0]
        cur.close()
        return count
    except Exception as e:
        return -1


def get_sample_data(conn, table, limit=10):
    """Get sample data from table."""
    try:
        cur = conn.cursor()
        
        # Get all data for small tables
        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        total = cur.fetchone()[0]
        
        if total <= 20:
            limit = total
        
        cur.execute(f'SELECT * FROM "{table}" LIMIT {limit}')
        rows = cur.fetchall()
        
        # Get column names
        cur.execute(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s AND table_schema = 'public'
            ORDER BY ordinal_position
        """, (table,))
        columns = [row[0] for row in cur.fetchall()]
        
        cur.close()
        return {"columns": columns, "rows": rows, "total": total}
    except Exception as e:
        return {"error": str(e)}


def get_foreign_keys(conn, table):
    """Get foreign key relationships."""
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                kcu.column_name,
                ccu.table_name AS foreign_table,
                ccu.column_name AS foreign_column
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = %s
        """, (table,))
        
        fks = []
        for row in cur.fetchall():
            fks.append(f"{row[0]} -> {row[1]}.{row[2]}")
        
        cur.close()
        return fks
    except Exception as e:
        return []


def investigate_table(local_conn, neon_conn, table):
    """Detailed investigation of a table."""
    print(f"\n{'=' * 80}")
    print(f"INVESTIGATING: {table}")
    print(f"{'=' * 80}")
    
    table_info = {
        "exists_in_local": False,
        "exists_in_neon": False,
        "recommendation": ""
    }
    
    # Check local
    exists_local = check_table_exists(local_conn, table)
    table_info["exists_in_local"] = exists_local
    
    if not exists_local:
        print(f"❌ Does NOT exist in local database")
        table_info["recommendation"] = "SKIP - doesn't exist in local"
        return table_info
    
    print(f"✅ Exists in LOCAL")
    
    # Get local details
    row_count = get_row_count(local_conn, table)
    table_info["local_row_count"] = row_count
    print(f"   Rows: {row_count:,}")
    
    if row_count == 0:
        print(f"   ⚠️ Table is EMPTY in local")
        table_info["recommendation"] = "SKIP - empty table"
        return table_info
    
    # Get schema
    schema = get_table_schema(local_conn, table)
    table_info["schema"] = schema
    print(f"\n📋 Schema ({len(schema)} columns):")
    for col in schema[:10]:
        print(f"   {col}")
    if len(schema) > 10:
        print(f"   ... and {len(schema) - 10} more columns")
    
    # Get foreign keys
    fks = get_foreign_keys(local_conn, table)
    if fks:
        table_info["foreign_keys"] = fks
        print(f"\n🔗 Foreign Keys:")
        for fk in fks:
            print(f"   {fk}")
    
    # Get sample data
    sample = get_sample_data(local_conn, table, 10)
    if "error" not in sample:
        table_info["sample_count"] = len(sample["rows"])
        print(f"\n📊 Sample Data ({len(sample['rows'])} of {sample['total']} rows):")
        
        # Display as table
        cols = sample["columns"]
        print(f"   {' | '.join(cols[:5])}")  # Show first 5 columns
        print(f"   {'-' * 100}")
        
        for row in sample["rows"][:5]:
            # Convert to strings and truncate
            row_strs = [str(val)[:20] if val is not None else 'NULL' for val in row[:5]]
            print(f"   {' | '.join(row_strs)}")
        
        if len(sample["rows"]) > 5:
            print(f"   ... and {len(sample['rows']) - 5} more rows")
        
        # Store sample for JSON
        table_info["sample_data"] = {
            "columns": cols,
            "rows": [[str(v)[:50] if v is not None else None for v in row] for row in sample["rows"][:5]]
        }
    
    # Check if exists in Neon
    exists_neon = check_table_exists(neon_conn, table)
    table_info["exists_in_neon"] = exists_neon
    
    if exists_neon:
        neon_count = get_row_count(neon_conn, table)
        table_info["neon_row_count"] = neon_count
        print(f"\n⚠️ Table EXISTS in Neon with {neon_count:,} rows")
        print(f"   This needs careful review - data conflict possible!")
        table_info["recommendation"] = "MANUAL REVIEW - exists in both databases"
    else:
        print(f"\n✅ Table does NOT exist in Neon")
        print(f"   Safe to create and sync")
        table_info["recommendation"] = "SAFE TO SYNC - missing in Neon"
    
    # Add to investigation
    investigation["tables"][table] = table_info
    
    return table_info


def generate_recommendations():
    """Generate sync recommendations."""
    print(f"\n{'=' * 80}")
    print("RECOMMENDATIONS")
    print(f"{'=' * 80}")
    
    safe_to_sync = []
    needs_manual = []
    skip = []
    
    for table, info in investigation["tables"].items():
        if "SAFE TO SYNC" in info["recommendation"]:
            safe_to_sync.append((table, info["local_row_count"]))
        elif "MANUAL REVIEW" in info["recommendation"]:
            needs_manual.append((table, info.get("local_row_count", 0), info.get("neon_row_count", 0)))
        else:
            skip.append((table, info["recommendation"]))
    
    if safe_to_sync:
        print(f"\n✅ SAFE TO SYNC ({len(safe_to_sync)} tables):")
        print("   These can be synced immediately - they don't exist in Neon:")
        for table, count in safe_to_sync:
            print(f"      • {table:40} ({count:,} rows)")
            investigation["recommendations"].append({
                "table": table,
                "action": "SYNC",
                "reason": f"Missing in Neon, has {count:,} rows in local"
            })
    
    if needs_manual:
        print(f"\n⚠️  NEEDS MANUAL REVIEW ({len(needs_manual)} tables):")
        print("   These exist in BOTH databases - careful investigation required:")
        for table, local_count, neon_count in needs_manual:
            print(f"      • {table:40} Local: {local_count:,} | Neon: {neon_count:,}")
            investigation["recommendations"].append({
                "table": table,
                "action": "REVIEW",
                "reason": f"Exists in both - Local: {local_count:,}, Neon: {neon_count:,}"
            })
    
    if skip:
        print(f"\n⏭️  SKIP ({len(skip)} tables):")
        for table, reason in skip:
            print(f"      • {table:40} - {reason}")
            investigation["recommendations"].append({
                "table": table,
                "action": "SKIP",
                "reason": reason
            })


def save_investigation():
    """Save investigation results."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"needs_review_investigation_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(investigation, f, indent=2)
    
    print(f"\n💾 Detailed investigation saved to: {filename}")


def main():
    """Run investigation."""
    print("=" * 80)
    print("NEEDS REVIEW TABLES - DETAILED INVESTIGATION")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print(f"Investigating {len(NEEDS_REVIEW)} tables...")
    
    # Connect
    local_conn = get_local_connection()
    neon_conn = get_neon_connection()
    
    if not local_conn or not neon_conn:
        print("\n❌ Failed to connect to databases")
        return
    
    # Investigate each table
    for table in NEEDS_REVIEW:
        investigate_table(local_conn, neon_conn, table)
    
    # Generate recommendations
    generate_recommendations()
    
    # Save results
    save_investigation()
    
    # Close connections
    local_conn.close()
    neon_conn.close()
    
    print(f"\n✅ Investigation complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
