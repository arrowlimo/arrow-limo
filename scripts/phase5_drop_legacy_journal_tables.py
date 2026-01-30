"""
Phase 5: Drop legacy journal tables (QuickBooks import data).
Keep general_ledger_headers/lines (active journal system).
"""
import psycopg2
import os
from datetime import datetime

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
conn.autocommit = False
cur = conn.cursor()

# Legacy journal tables to drop
LEGACY_JOURNAL_TABLES = [
    'journal',           # QuickBooks import (1,229 records, TEXT dates)
    'journal_batches',   # Receipt events (835 batches, inactive since Sept 2025)
    'journal_lines'      # Receipt journal lines (2,455 lines, inactive)
]

# KEEP: general_ledger_headers, general_ledger_lines (active journal system)

try:
    print("=" * 80)
    print("PHASE 5: DROP LEGACY JOURNAL TABLES")
    print("=" * 80)
    
    # Step 1: Backup legacy journal tables
    print(f"\n📝 Step 1: Backing up {len(LEGACY_JOURNAL_TABLES)} legacy journal tables...")
    
    for table_name in LEGACY_JOURNAL_TABLES:
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        
        if count == 0:
            print(f"  ⏭️  {table_name} (0 records, skipping backup)")
            continue
        
        backup_file = f"L:/limo/reports/legacy_table_backups/{table_name}_PHASE5_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            cur.execute(f"""
                COPY (SELECT * FROM {table_name})
                TO '{backup_file}'
                WITH (FORMAT CSV, HEADER TRUE, ENCODING 'UTF8')
            """)
            print(f"  ✅ {table_name} ({count:,} records) → backup saved")
        except Exception as e:
            print(f"  ⚠️  {table_name} backup failed: {e}")
    
    # Step 2: Drop legacy journal tables
    print(f"\n📝 Step 2: Dropping {len(LEGACY_JOURNAL_TABLES)} legacy journal tables...")
    
    dropped_count = 0
    for table_name in LEGACY_JOURNAL_TABLES:
        try:
            cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
            print(f"  ✅ Dropped: {table_name}")
            dropped_count += 1
        except Exception as e:
            print(f"  ❌ Failed to drop {table_name}: {e}")
    
    # Commit changes
    conn.commit()
    
    print("\n" + "=" * 80)
    print("✅ PHASE 5 COMPLETE")
    print("=" * 80)
    
    # Verify what remains
    cur.execute("""
        SELECT table_name, 
               (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as col_count
        FROM information_schema.tables t
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        AND (
            table_name LIKE '%journal%'
            OR table_name LIKE '%ledger%'
        )
        ORDER BY table_name
    """)
    
    remaining = cur.fetchall()
    print(f"\nRemaining journal/ledger tables ({len(remaining)}):")
    for table_name, col_count in remaining:
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        status = "✅ ACTIVE" if table_name in ['general_ledger_headers', 'general_ledger_lines'] else "📊 DATA"
        print(f"  {status} {table_name:40} {count:>8,} records")
    
    # Final database stats
    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")
    table_count = cur.fetchone()[0]
    
    cur.execute("SELECT pg_size_pretty(pg_database_size('almsdata'))")
    db_size = cur.fetchone()[0]
    
    print(f"\n📊 Database: {table_count} tables, {db_size}")
    print(f"\n✅ Dropped {dropped_count} legacy journal tables")
    print("✅ Kept general_ledger_headers/lines (active journal system)")
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    raise
finally:
    cur.close()
    conn.close()
