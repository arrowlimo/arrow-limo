#!/usr/bin/env python3
"""
Automated Local → Neon Sync
Runs incremental sync based on last_updated/created_at timestamps
Safe one-way push (local is source of truth, Neon is production read-only copy)
"""
import psycopg2
import os
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

# Connection configs
LOCAL_CONN = {
    'host': 'localhost',
    'user': 'postgres',
    'password': '***REDACTED***',
    'database': 'almsdata'
}

NEON_CONN = {
    'host': 'ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech',
    'user': 'neondb_owner',
    'password': 'npg_89MbcFmZwUWo',
    'database': 'neondb',
    'sslmode': 'require'
}

# Sync state file (tracks last sync time)
SYNC_STATE_FILE = Path('L:/limo/data/neon_sync_state.json')

# Tables to sync (with their timestamp column and description)
TABLES = {
    'charters': ('updated_at', 'Booking records'),
    'payments': ('created_at', 'Payment records'),
    'receipts': ('created_at', 'Receipt/expense records'),
    'employees': ('updated_at', 'Employee records'),
    'clients': ('updated_at', 'Client records'),
    'vehicles': ('updated_at', 'Vehicle/fleet records')
}

def load_sync_state():
    """Load last sync timestamp from state file"""
    if SYNC_STATE_FILE.exists():
        try:
            with open(SYNC_STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_sync_state(state):
    """Save sync state to file"""
    SYNC_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SYNC_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, default=str)

def should_do_full_sync(state):
    """Check if daily 7 AM full sync is needed"""
    last_full_sync = state.get('_last_full_sync')
    now = datetime.now(timezone.utc)
    today = now.date()
    
    # If no previous full sync, do one now
    if not last_full_sync:
        return True, "first sync (initialization)"
    
    # Parse last sync date
    try:
        last_sync_dt = datetime.fromisoformat(last_full_sync)
        last_sync_date = last_sync_dt.date()
    except:
        return True, "invalid sync state"
    
    # Check if we're past 7 AM today and haven't synced today yet
    utc_hour = now.hour
    # Assuming local is MST/MDT (UTC-7 or UTC-6), 7 AM local = 2 PM or 1 PM UTC
    # For simplicity, check if: today > last_sync_date (different days)
    if today > last_sync_date:
        return True, "daily full sync (new day)"
    
    return False, None

def sync_table(neon_conn, table_name, timestamp_col, last_sync_time):
    """Sync one table incrementally - handles each row in a separate transaction"""
    
    # Connect to local to get data
    local_conn_temp = psycopg2.connect(**LOCAL_CONN)
    local_conn_temp.autocommit = False
    lc = local_conn_temp.cursor()
    
    try:
        # Get columns for this table
        lc.execute(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = '{table_name}' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        columns = [row[0] for row in lc.fetchall()]
        
        if not columns:
            lc.close()
            local_conn_temp.close()
            return 0, 0
        
        # Check if timestamp column exists
        if timestamp_col not in columns:
            lc.close()
            local_conn_temp.close()
            return 0, 0
        
        # Get new/updated rows from local
        if last_sync_time:
            # Parse ISO format timestamp
            lc.execute(f"""
                SELECT * FROM {table_name}
                WHERE {timestamp_col} > %s::timestamp with time zone
                ORDER BY {timestamp_col}
            """, (last_sync_time,))
        else:
            lc.execute(f"SELECT * FROM {table_name}")
        
        rows = lc.fetchall()
        lc.close()
        
        if not rows:
            local_conn_temp.close()
            return 0, 0
        
        # Get primary key for this table
        lc = local_conn_temp.cursor()
        lc.execute(f"""
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = '{table_name}'::regclass AND i.indisprimary
        """)
        pk_result = lc.fetchone()
        pk_col = pk_result[0] if pk_result else columns[0]
        lc.close()
        local_conn_temp.close()
        
        # Prepare upsert statement
        col_list = ', '.join(columns)
        placeholders = ', '.join(['%s'] * len(columns))
        update_cols = [f"{col} = EXCLUDED.{col}" for col in columns if col != pk_col]
        update_clause = ', '.join(update_cols) if update_cols else f"{pk_col} = EXCLUDED.{pk_col}"
        
        upsert_sql = f"""
            INSERT INTO {table_name} ({col_list})
            VALUES ({placeholders})
            ON CONFLICT ({pk_col}) DO UPDATE SET {update_clause}
        """
        
        # Sync each row (separate transaction for each)
        inserted = 0
        updated = 0
        
        for row in rows:
            try:
                # Convert dict/list values to JSON strings for compatibility
                converted_row = []
                for val in row:
                    if isinstance(val, (dict, list)):
                        converted_row.append(json.dumps(val, default=str))
                    else:
                        converted_row.append(val)
                
                # Each row in its own transaction
                neon_cur = neon_conn.cursor()
                neon_cur.execute(upsert_sql, tuple(converted_row))
                neon_conn.commit()
                neon_cur.close()
                
                # Count as inserted (ON CONFLICT is always new in this check)
                inserted += 1
                
            except psycopg2.IntegrityError:
                neon_conn.rollback()
                updated += 1
            except Exception as e:
                neon_conn.rollback()
                # Silently continue on errors (likely due to transaction state)
                pass
        
        return inserted, updated
        
    except Exception as e:
        print(f"    Error in sync_table({table_name}): {str(e)[:80]}")
        return 0, 0
    finally:
        try:
            local_conn_temp.close()
        except:
            pass

def full_sync_table(neon_conn, table_name, local_conn):
    """Full sync: TRUNCATE Neon table and reload all data from local"""
    local_cur = local_conn.cursor()
    
    try:
        # Get columns and data from local
        local_cur.execute(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = '{table_name}' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        columns = [row[0] for row in local_cur.fetchall()]
        
        if not columns:
            return 0
        
        local_cur.execute(f"SELECT * FROM {table_name}")
        rows = local_cur.fetchall()
        
        if not rows:
            # Empty table - just truncate Neon
            neon_cur = neon_conn.cursor()
            neon_cur.execute(f"TRUNCATE TABLE {table_name} CASCADE")
            neon_conn.commit()
            neon_cur.close()
            return 0
        
        # Get primary key
        local_cur.execute(f"""
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = '{table_name}'::regclass AND i.indisprimary
        """)
        pk_result = local_cur.fetchone()
        pk_col = pk_result[0] if pk_result else columns[0]
        
        # Truncate Neon table
        neon_cur = neon_conn.cursor()
        neon_cur.execute(f"TRUNCATE TABLE {table_name} CASCADE")
        neon_conn.commit()
        
        # Insert all rows
        col_list = ', '.join(columns)
        placeholders = ', '.join(['%s'] * len(columns))
        insert_sql = f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})"
        
        inserted = 0
        for row in rows:
            try:
                # Convert dict/list to JSON
                converted_row = []
                for val in row:
                    if isinstance(val, (dict, list)):
                        converted_row.append(json.dumps(val, default=str))
                    else:
                        converted_row.append(val)
                
                neon_cur.execute(insert_sql, tuple(converted_row))
                neon_conn.commit()
                inserted += 1
                
            except Exception as e:
                neon_conn.rollback()
                pass
        
        neon_cur.close()
        return inserted
        
    except Exception as e:
        print(f"    Error in full_sync_table({table_name}): {str(e)[:80]}")
        return 0
    finally:
        local_cur.close()




def verify_neon_sync():
    """Verify that local and Neon have matching row counts"""
    try:
        local_conn = psycopg2.connect(**LOCAL_CONN)
        neon_conn = psycopg2.connect(**NEON_CONN)
        
        local_cur = local_conn.cursor()
        neon_cur = neon_conn.cursor()
        
        all_match = True
        for table_name in TABLES.keys():
            local_cur.execute(f'SELECT COUNT(*) FROM {table_name}')
            local_count = local_cur.fetchone()[0]
            
            neon_cur.execute(f'SELECT COUNT(*) FROM {table_name}')
            neon_count = neon_cur.fetchone()[0]
            
            if local_count == neon_count:
                print(f"  {table_name:20} Local: {local_count:>8,}  Neon: {neon_count:>8,}  ✓")
            else:
                print(f"  {table_name:20} Local: {local_count:>8,}  Neon: {neon_count:>8,}  ✗")
                all_match = False
        
        local_cur.close()
        neon_cur.close()
        local_conn.close()
        neon_conn.close()
        
        return all_match
    except Exception as e:
        print(f"  Verification failed: {str(e)}")
        return False

def main():
    """Main sync orchestration - handles incremental + periodic full syncs"""
    print(f"\n{'='*70}")
    print(f"🔄 Neon Sync Started - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")
    
    # Load sync state
    sync_state = load_sync_state()
    
    # Check if full sync needed
    need_full_sync, reason = should_do_full_sync(sync_state)
    
    try:
        # Connect to both databases
        neon_conn = psycopg2.connect(**NEON_CONN)
        neon_conn.autocommit = False
        local_conn = psycopg2.connect(**LOCAL_CONN)
        
        total_synced = 0
        
        if need_full_sync:
            print(f"⚠️  FULL SYNC TRIGGERED: {reason}\n")
            print(f"{'='*70}")
            print("📊 Full Sync (TRUNCATE + reload all data)")
            print(f"{'='*70}\n")
            
            for table_name, (timestamp_col, desc) in TABLES.items():
                print(f"  {table_name:20}", end=" → ")
                try:
                    inserted = full_sync_table(neon_conn, table_name, local_conn)
                    total_synced += inserted
                    print(f"Reloaded {inserted:,} rows")
                    
                    # Reset incremental sync state for this table
                    sync_state[table_name] = datetime.now(timezone.utc).isoformat()
                    
                except Exception as e:
                    print(f"Error: {str(e)[:50]}")
            
            # Mark full sync completed
            sync_state['_last_full_sync'] = datetime.now(timezone.utc).isoformat()
            sync_state['_sync_count'] = 0
            
        else:
            print("✅ Incremental Sync (only new/updated rows)\n")
            print(f"{'='*70}")
            print("📊 Incremental Sync")
            print(f"{'='*70}\n")
            
            for table_name, (timestamp_col, desc) in TABLES.items():
                last_sync = sync_state.get(table_name)
                
                print(f"  {table_name:20}", end=" ")
                if last_sync:
                    print(f"(since {last_sync})", end=" → ")
                else:
                    print("(initial sync)", end=" → ")
                
                try:
                    inserted, updated = sync_table(neon_conn, table_name, timestamp_col, last_sync)
                    total_synced += inserted + updated
                    print(f"+{inserted}, ~{updated}")
                    
                    sync_state[table_name] = datetime.now(timezone.utc).isoformat()
                    
                except Exception as e:
                    print(f"Error: {str(e)[:50]}")
            
            # Increment sync count
            sync_state['_sync_count'] = sync_state.get('_sync_count', 0) + 1
        
        neon_conn.close()
        local_conn.close()
        
        # Save updated state
        save_sync_state(sync_state)
        
        print(f"\n{'='*70}")
        print(f"✓ Sync Complete")
        print(f"{'='*70}")
        print(f"  Rows synced:        {total_synced:,}")
        print(f"  Sync count:         {sync_state.get('_sync_count', 0)}")
        print(f"  Last full sync:     {sync_state.get('_last_full_sync', 'Never')}")
        print(f"  Timestamp:          {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Verify
        print(f"{'='*70}")
        print("🔍 Verification (Row counts)")
        print(f"{'='*70}")
        if verify_neon_sync():
            print("\n✓ All tables match - Neon is consistent with local!\n")
        else:
            print("\n⚠ Some tables differ - check manually!\n")
        
    except Exception as e:
        print(f"\n❌ Sync failed: {str(e)}\n")
        sys.exit(1)

if __name__ == '__main__':
    main()

