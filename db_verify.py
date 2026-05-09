import psycopg
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from tabulate import tabulate


load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)

# Tables to check
TABLES = [
    'employees',
    'charters',
    'charter_payments',
    'receipts',
    'vendor_accounts',
    'driver_payroll'
]

def get_table_counts(conn, db_name):
    """Execute COUNT(*) on all tables"""
    results = {}
    try:
        with conn.cursor() as cur:
            for table in TABLES:
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cur.fetchone()[0]
                    results[table] = count
                except Exception as e:
                    results[table] = f"ERROR: {str(e)}"
    except Exception as e:
        return {"error": f"Connection error: {str(e)}"}
    
    return results

def test_local_db():
    """Test LOCAL database connection"""
    print("=" * 80)
    print("TESTING LOCAL DATABASE (localhost:5432/almsdata)")
    print("=" * 80)
    
    try:
        conn = psycopg.connect(
            host=os.environ.get("LOCAL_DB_HOST", "localhost"),
            port=int(os.environ.get("LOCAL_DB_PORT", "5432")),
            database=os.environ.get("LOCAL_DB_NAME", "almsdata"),
            user=os.environ.get("LOCAL_DB_USER", "postgres"),
            password=os.environ.get("LOCAL_DB_PASSWORD", ""),
            sslmode=os.environ.get("LOCAL_DB_SSLMODE", "prefer") or "prefer",
        )
        print("✓ Connection successful to LOCAL database")
        
        # Get counts
        results = get_table_counts(conn, "LOCAL")
        conn.close()
        
        return results
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return None

def check_neon_env():
    """Check for Neon environment variables"""
    print("\n" + "=" * 80)
    print("CHECKING FOR NEON CREDENTIALS IN ENVIRONMENT")
    print("=" * 80)
    
    neon_vars = {
        'NEON_HOST': os.environ.get('NEON_HOST'),
        'NEON_DATABASE_URL': os.environ.get('NEON_DATABASE_URL'),
        'DATABASE_URL': os.environ.get('DATABASE_URL'),
        'PGHOST': os.environ.get('PGHOST'),
    }
    
    for var, value in neon_vars.items():
        if value:
            print(f"✓ Found {var}")
        else:
            print(f"✗ Not found {var}")
    
    # Check if any Neon-like URL exists
    neon_url = os.environ.get('DATABASE_URL') or os.environ.get('NEON_DATABASE_URL')
    return neon_url

def test_neon_db(neon_url):
    """Test Neon database connection"""
    print("\n" + "=" * 80)
    print("TESTING NEON DATABASE")
    print("=" * 80)
    
    if not neon_url:
        print("✗ No Neon connection URL available")
        return None
    
    try:
        print("Attempting connection to Neon...")
        conn = psycopg.connect(neon_url)
        print("✓ Connection successful to NEON database")
        
        # Get counts
        results = get_table_counts(conn, "NEON")
        conn.close()
        
        return results
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return None


def test_neon_from_env():
    """Test Neon database connection from explicit env vars."""
    print("\n" + "=" * 80)
    print("TESTING NEON DATABASE (env vars)")
    print("=" * 80)
    try:
        conn = psycopg.connect(
            host=os.environ.get("NEON_DB_HOST", os.environ.get("DB_HOST", "")),
            port=int(os.environ.get("NEON_DB_PORT", os.environ.get("DB_PORT", "5432"))),
            database=os.environ.get("NEON_DB_NAME", os.environ.get("DB_NAME", "neondb")),
            user=os.environ.get("NEON_DB_USER", os.environ.get("DB_USER", "")),
            password=os.environ.get("NEON_DB_PASSWORD", os.environ.get("DB_PASSWORD", "")),
            sslmode=os.environ.get("NEON_DB_SSLMODE", os.environ.get("DB_SSLMODE", "require")) or "require",
        )
        print("✓ Connection successful to NEON database")
        results = get_table_counts(conn, "NEON")
        conn.close()
        return results
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return None

def compare_results(local_results, neon_results):
    """Compare results between LOCAL and NEON"""
    print("\n" + "=" * 80)
    print("COMPREHENSIVE RESULTS COMPARISON")
    print("=" * 80)
    
    # Prepare table data
    table_data = []
    mismatches = []
    
    for table in TABLES:
        local_count = local_results.get(table, "N/A") if local_results else "N/A"
        neon_count = neon_results.get(table, "N/A") if neon_results else "N/A"
        
        # Check for mismatch
        mismatch = ""
        if local_results and neon_results:
            if isinstance(local_count, int) and isinstance(neon_count, int):
                if local_count != neon_count:
                    mismatch = "⚠ MISMATCH"
                    mismatches.append(table)
        
        table_data.append([
            table,
            str(local_count),
            str(neon_count) if neon_results else "N/A",
            mismatch
        ])
    
    # Display table
    headers = ["Table", "LOCAL Count", "NEON Count", "Status"]
    print("\n")
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if local_results:
        local_total = sum(v for v in local_results.values() if isinstance(v, int))
        print(f"LOCAL Total Records: {local_total}")
    
    if neon_results:
        neon_total = sum(v for v in neon_results.values() if isinstance(v, int))
        print(f"NEON Total Records: {neon_total}")
        
        if mismatches:
            print(f"\n⚠ MISMATCHES FOUND in tables: {', '.join(mismatches)}")
        else:
            print("\n✓ All table counts match between LOCAL and NEON")
    else:
        print("NEON database not accessible")
    
    print(f"\nVerification completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def main():
    print("\nArrow Limo System - Database Verification Pass")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    run_local = "--local" in sys.argv

    # Default: Neon primary. Use --local for emergency verification only.
    neon_results = test_neon_from_env()
    if not neon_results:
        neon_url = check_neon_env()
        if neon_url:
            neon_results = test_neon_db(neon_url)

    local_results = test_local_db() if run_local else None
    
    # Step 4: Compare and display results
    compare_results(local_results, neon_results)

if __name__ == "__main__":
    main()
