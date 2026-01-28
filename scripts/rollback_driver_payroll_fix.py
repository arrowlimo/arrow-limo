#!/usr/bin/env python3
"""
Rollback driver_payroll fixes by restoring employee_id and driver_id from the latest
backup table named driver_payroll_backup_YYYYMMDD_HHMMSS.

Creates a rollback audit entry with counts.
"""
import psycopg2
from psycopg2 import sql
from datetime import datetime

def connect():
    return psycopg2.connect(dbname='almsdata', user='postgres', password='***REMOVED***', host='localhost')


def get_latest_backup_table(cur):
    cur.execute("""
        SELECT tablename
        FROM pg_tables
        WHERE schemaname='public' AND tablename LIKE 'driver_payroll_backup_%'
        ORDER BY tablename DESC
        LIMIT 1
    """)
    row = cur.fetchone()
    return row[0] if row else None


def ensure_rollback_audit(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payroll_fix_rollback_audit (
            id SERIAL PRIMARY KEY,
            backup_table VARCHAR(200) NOT NULL,
            restored_rows INTEGER NOT NULL,
            rolled_back_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def rollback():
    conn = connect(); cur = conn.cursor()

    backup_table = get_latest_backup_table(cur)
    if not backup_table:
        print("No backup table found (driver_payroll_backup_*). Aborting.")
        cur.close(); conn.close(); return

    print(f"Using backup table: {backup_table}")

    ensure_rollback_audit(cur)

    # Count rows to restore
    cur.execute(sql.SQL("SELECT COUNT(*) FROM {}".format(backup_table)))
    count = cur.fetchone()[0]
    print(f"Rows in backup: {count}")

    # Perform restore of fields we changed: employee_id, driver_id
    try:
        cur.execute(sql.SQL(
            """
            UPDATE driver_payroll dp
            SET employee_id = b.employee_id,
                driver_id = b.driver_id
            FROM {} b
            WHERE dp.id = b.id
            """
        ).format(sql.Identifier(backup_table)))
        restored = cur.rowcount
        cur.execute("INSERT INTO payroll_fix_rollback_audit (backup_table, restored_rows) VALUES (%s, %s)", (backup_table, restored))
        conn.commit()
        print(f"Restored rows: {restored}")
    except Exception as e:
        conn.rollback()
        print(f"Rollback failed: {e}")
    finally:
        cur.close(); conn.close()

if __name__ == '__main__':
    rollback()
