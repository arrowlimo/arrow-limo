#!/usr/bin/env python3
"""Verify error logging system is working correctly"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'desktop_app'))

import psycopg2

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def main():
    print("=" * 60)
    print("Error Logging System Verification")
    print("=" * 60)
    
    try:
        # Connect to database
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cur = conn.cursor()
        
        # Check if app_errors table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'app_errors'
            );
        """)
        table_exists = cur.fetchone()[0]
        
        if table_exists:
            print("✅ app_errors table EXISTS")
            
            # Get table structure
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'app_errors'
                ORDER BY ordinal_position;
            """)
            columns = cur.fetchall()
            print("\nTable Structure:")
            print("-" * 60)
            for col_name, col_type in columns:
                print(f"  {col_name:20s} {col_type}")
            
            # Count errors
            cur.execute("SELECT COUNT(*) FROM app_errors;")
            total_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM app_errors WHERE resolved = FALSE;")
            unresolved_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM app_errors WHERE resolved = TRUE;")
            resolved_count = cur.fetchone()[0]
            
            print("\nError Statistics:")
            print("-" * 60)
            print(f"  Total Errors:      {total_count}")
            print(f"  Unresolved Errors: {unresolved_count}")
            print(f"  Resolved Errors:   {resolved_count}")
            
            # Show recent errors (if any)
            if total_count > 0:
                cur.execute("""
                    SELECT error_id, timestamp, error_type, widget_name, 
                           LEFT(error_message, 50) as msg_preview, resolved
                    FROM app_errors
                    ORDER BY timestamp DESC
                    LIMIT 5;
                """)
                recent = cur.fetchall()
                print("\nRecent Errors (Last 5):")
                print("-" * 60)
                for eid, ts, etype, widget, msg, res in recent:
                    status = "✅" if res else "❌"
                    print(f"  {status} #{eid} [{ts}] {etype}")
                    print(f"     Widget: {widget}")
                    print(f"     Message: {msg}...")
                    print()
            
            # Check error_log.jsonl file
            log_file = os.path.join(os.path.dirname(__file__), 'desktop_app', 'error_log.jsonl')
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                print(f"✅ error_log.jsonl file EXISTS ({len(lines)} entries)")
            else:
                print("⚠️  error_log.jsonl file NOT FOUND (will be created on first error)")
            
        else:
            print("❌ app_errors table NOT FOUND")
            print("\nThe table should be created automatically when error_logger is initialized.")
            print("Try running the desktop app first.")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("Verification Complete")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
