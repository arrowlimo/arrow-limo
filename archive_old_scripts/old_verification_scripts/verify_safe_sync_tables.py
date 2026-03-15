#!/usr/bin/env python3
"""
DATA VERIFICATION AND SAFE SYNC ANALYSIS
=========================================

Compares actual data content between local and Neon to determine:
1. Which data matches exactly (skip these)
2. Which tables are safe to sync (no risk of data loss)
3. Which tables need manual review (potential conflicts)

CRITICAL: Verifies before syncing to avoid overwriting good Neon data
          with stale local data.
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

# Analysis results
analysis = {
    "timestamp": datetime.now().isoformat(),
    "safe_to_sync": [],
    "needs_review": [],
    "skip_sync": [],
    "samples": {}
}


def get_connections():
    """Get both database connections."""
    try:
        local_conn = psycopg2.connect(
            host=LOCAL_HOST,
            database=LOCAL_DB,
            user=LOCAL_USER,
            password=LOCAL_PASSWORD
        )
        print(f"✅ Connected to LOCAL")
        
        neon_conn = psycopg2.connect(
            host=NEON_HOST,
            database=NEON_DB,
            user=NEON_USER,
            password=NEON_PASSWORD,
            sslmode='require',
            connect_timeout=10
        )
        print(f"✅ Connected to NEON")
        
        return local_conn, neon_conn
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return None, None


def sample_table_data(conn, table, limit=10):
    """Get sample data from a table."""
    try:
        cur = conn.cursor()
        
        # Get primary key or first column for ordering
        cur.execute(f"""
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = '{table}'::regclass AND i.indisprimary
            LIMIT 1
        """)
        
        pk_result = cur.fetchone()
        order_by = pk_result[0] if pk_result else "1"
        
        # Get sample rows
        cur.execute(f'SELECT * FROM "{table}" ORDER BY {order_by} LIMIT {limit}')
        rows = cur.fetchall()
        
        # Get column names
        cur.execute(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table}' 
            ORDER BY ordinal_position
        """)
        columns = [row[0] for row in cur.fetchall()]
        
        cur.close()
        return {"columns": columns, "rows": rows}
    except Exception as e:
        return {"error": str(e)}


def compare_table_samples(table, local_conn, neon_conn):
    """Compare sample data from both databases."""
    print(f"\n   Analyzing: {table}")
    
    local_sample = sample_table_data(local_conn, table, 5)
    neon_sample = sample_table_data(neon_conn, table, 5)
    
    if "error" in local_sample:
        print(f"      ⚠️ Can't read from local: {local_sample['error']}")
        return "skip"
    
    if "error" in neon_sample:
        print(f"      ⚠️ Can't read from Neon: {neon_sample['error']}")
        return "skip"
    
    # Get row counts
    try:
        local_cur = local_conn.cursor()
        local_cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        local_count = local_cur.fetchone()[0]
        local_cur.close()
        
        neon_cur = neon_conn.cursor()
        neon_cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        neon_count = neon_cur.fetchone()[0]
        neon_cur.close()
    except:
        return "skip"
    
    print(f"      Local: {local_count:,} rows | Neon: {neon_count:,} rows")
    
    # Check if data looks similar
    if local_count == 0 and neon_count == 0:
        print(f"      ✅ Both empty - skip")
        return "identical"
    
    if local_count == 0 and neon_count > 0:
        print(f"      ⚠️ Neon has data, local is empty - KEEP NEON")
        return "keep_neon"
    
    if local_count > 0 and neon_count == 0:
        print(f"      ✅ Neon empty, local has data - SAFE TO SYNC")
        return "safe_sync"
    
    # Both have data - need to check if it's the same
    if local_count == neon_count:
        # Sample first few rows to see if they match
        local_rows_str = str(local_sample["rows"][:3])
        neon_rows_str = str(neon_sample["rows"][:3])
        
        if local_rows_str == neon_rows_str:
            print(f"      ✅ Counts match, samples identical - skip")
            return "identical"
        else:
            print(f"      ⚠️ Same count but different data - NEEDS REVIEW")
            return "needs_review"
    else:
        # Different row counts
        diff = abs(local_count - neon_count)
        diff_pct = (diff / max(local_count, neon_count)) * 100
        
        if diff_pct > 10 or diff > 100:
            print(f"      ⚠️ Significant difference ({diff:,} rows, {diff_pct:.1f}%) - NEEDS REVIEW")
            return "needs_review"
        else:
            print(f"      ℹ️ Small difference ({diff:,} rows, {diff_pct:.1f}%) - NEEDS REVIEW")
            return "needs_review"


def analyze_non_impacting_tables(local_conn, neon_conn):
    """Analyze the safe, non-impacting tables."""
    print("\n" + "=" * 80)
    print("ANALYZING NON-IMPACTING TABLES")
    print("=" * 80)
    
    # Tables user specified as non-impacting
    non_impacting_tables = [
        "beverage_products",
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
    
    print(f"\nChecking {len(non_impacting_tables)} non-impacting tables...")
    
    safe_to_sync = []
    needs_review = []
    skip_sync = []
    
    for table in non_impacting_tables:
        result = compare_table_samples(table, local_conn, neon_conn)
        
        if result == "safe_sync":
            safe_to_sync.append(table)
            analysis["safe_to_sync"].append({
                "table": table,
                "reason": "Neon is empty, local has data"
            })
        elif result == "needs_review":
            needs_review.append(table)
            analysis["needs_review"].append({
                "table": table,
                "reason": "Both have data but differs - manual review required"
            })
        elif result == "keep_neon":
            skip_sync.append(table)
            analysis["skip_sync"].append({
                "table": table,
                "reason": "Neon has data, local is empty - keep Neon"
            })
        elif result == "identical":
            skip_sync.append(table)
            analysis["skip_sync"].append({
                "table": table,
                "reason": "Data is identical - no sync needed"
            })
        else:
            skip_sync.append(table)
            analysis["skip_sync"].append({
                "table": table,
                "reason": "Error or skip"
            })
    
    return safe_to_sync, needs_review, skip_sync


def analyze_critical_missing_tables(local_conn, neon_conn):
    """Analyze tables that are missing in Neon entirely."""
    print("\n" + "=" * 80)
    print("ANALYZING TABLES MISSING IN NEON")
    print("=" * 80)
    
    # Tables missing in Neon that have significant data
    missing_tables = [
        "lms2026_payment_matches",
        "charter_gst_details_2010_2012",
        "employee_t4_records",
        "employee_t4_summary",
        "alcohol_business_tracking",
        "charter_incidents",
        "charter_receipts",
        "charters_routing_times",
        "receipt_banking_links",
        "receipt_cashbox_links",
    ]
    
    print(f"\nChecking {len(missing_tables)} tables missing in Neon...")
    
    safe_to_create = []
    
    for table in missing_tables:
        try:
            local_cur = local_conn.cursor()
            local_cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            local_count = local_cur.fetchone()[0]
            local_cur.close()
            
            print(f"\n   {table}: {local_count:,} rows in local")
            
            if local_count > 0:
                # Get sample for inspection
                sample = sample_table_data(local_conn, table, 3)
                analysis["samples"][table] = {
                    "row_count": local_count,
                    "columns": sample.get("columns", []),
                    "sample_rows": len(sample.get("rows", []))
                }
                
                print(f"      ✅ Safe to create and sync to Neon")
                safe_to_create.append(table)
                analysis["safe_to_sync"].append({
                    "table": table,
                    "reason": f"Missing in Neon, has {local_count:,} rows in local"
                })
            else:
                print(f"      ℹ️ Empty table - skip")
                analysis["skip_sync"].append({
                    "table": table,
                    "reason": "Empty in local"
                })
        except Exception as e:
            print(f"      ❌ Error: {e}")
    
    return safe_to_create


def analyze_data_discrepancies(local_conn, neon_conn):
    """Analyze tables with major row count differences."""
    print("\n" + "=" * 80)
    print("ANALYZING TABLES WITH DATA DISCREPANCIES")
    print("=" * 80)
    print("\nThese need MANUAL REVIEW - do NOT auto-sync!")
    
    # Tables with significant differences from earlier comparison
    discrepancy_tables = [
        "receipts",
        "banking_receipt_matching_ledger",
        "payments",
        "clients",
        "charter_routes",
        "general_ledger",
        "charter_payments",
        "charter_charges",
    ]
    
    for table in discrepancy_tables:
        result = compare_table_samples(table, local_conn, neon_conn)
        
        if result == "needs_review" or result == "keep_neon":
            analysis["needs_review"].append({
                "table": table,
                "reason": "Significant data differences - requires manual investigation"
            })


def print_summary():
    """Print analysis summary."""
    print("\n" + "=" * 80)
    print("SYNC SAFETY ANALYSIS SUMMARY")
    print("=" * 80)
    
    safe = analysis["safe_to_sync"]
    review = analysis["needs_review"]
    skip = analysis["skip_sync"]
    
    print(f"\n✅ SAFE TO SYNC ({len(safe)} tables):")
    print("   These can be synced safely - Neon is empty or missing:")
    for item in safe:
        print(f"      • {item['table']:40} - {item['reason']}")
    
    print(f"\n⚠️  NEEDS MANUAL REVIEW ({len(review)} tables):")
    print("   DO NOT auto-sync - investigate first:")
    for item in review:
        print(f"      • {item['table']:40} - {item['reason']}")
    
    print(f"\n⏭️  SKIP SYNC ({len(skip)} tables):")
    print("   No sync needed:")
    for item in skip[:10]:
        print(f"      • {item['table']:40} - {item['reason']}")
    if len(skip) > 10:
        print(f"      ... and {len(skip) - 10} more")


def save_analysis():
    """Save analysis to file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sync_safety_analysis_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(analysis, f, indent=2)
    
    print(f"\n💾 Detailed analysis saved to: {filename}")
    
    # Create sync script for safe tables
    if analysis["safe_to_sync"]:
        sync_script = f"sync_safe_tables_{timestamp}.txt"
        with open(sync_script, 'w') as f:
            f.write("SAFE TO SYNC - Tables that can be safely copied to Neon\n")
            f.write("=" * 70 + "\n\n")
            
            f.write("These tables are either:\n")
            f.write("- Missing in Neon entirely\n")
            f.write("- Empty in Neon but have data in local\n")
            f.write("- Have no risk of overwriting important Neon data\n\n")
            
            f.write("TABLES:\n")
            for item in analysis["safe_to_sync"]:
                f.write(f"  {item['table']}\n")
                f.write(f"    Reason: {item['reason']}\n\n")
        
        print(f"📄 Safe sync list saved to: {sync_script}")


def main():
    """Run data verification analysis."""
    print("=" * 80)
    print("DATA VERIFICATION AND SAFE SYNC ANALYSIS")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print("Purpose: Identify which tables can be safely synced to Neon")
    print("         without overwriting good data with stale data.\n")
    
    # Connect
    local_conn, neon_conn = get_connections()
    if not local_conn or not neon_conn:
        print("\n❌ Failed to connect - aborting")
        return
    
    # Analyze non-impacting tables
    safe_to_sync, needs_review, skip_sync = analyze_non_impacting_tables(local_conn, neon_conn)
    
    # Analyze tables missing in Neon
    safe_to_create = analyze_critical_missing_tables(local_conn, neon_conn)
    
    # Analyze tables with discrepancies
    analyze_data_discrepancies(local_conn, neon_conn)
    
    # Print summary
    print_summary()
    
    # Save analysis
    save_analysis()
    
    # Close connections
    local_conn.close()
    neon_conn.close()
    
    print(f"\n✅ Analysis complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nNEXT STEPS:")
    print(f"1. Review the safe_to_sync list above")
    print(f"2. For tables marked SAFE TO SYNC, we can sync immediately")
    print(f"3. For tables marked NEEDS REVIEW, manual investigation required")
    print(f"4. I'll create a sync script for the safe tables only")


if __name__ == "__main__":
    main()
