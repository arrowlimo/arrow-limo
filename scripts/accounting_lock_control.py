"""
CLI to control accounting lock state (enable/disable) and view status.
Restoration-safe: does not enforce locks unless applied; this only flips state.
"""
import os
import psycopg2

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

HELP = """
Usage:
  python -X utf8 scripts/accounting_lock_control.py status
  python -X utf8 scripts/accounting_lock_control.py enable "Locked By Name" "Optional CRA notes"
  python -X utf8 scripts/accounting_lock_control.py disable
"""

def main():
    import sys
    if len(sys.argv) < 2 or sys.argv[1] not in ('status', 'enable', 'disable'):
        print(HELP)
        return

    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    # Ensure state exists
    cur.execute("""
    CREATE TABLE IF NOT EXISTS accounting_lock_state (
      id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
      lock_enabled BOOLEAN NOT NULL DEFAULT FALSE,
      locked_at TIMESTAMP,
      locked_by TEXT,
      cra_notes TEXT
    );
    """)
    cur.execute("""
    INSERT INTO accounting_lock_state (id, lock_enabled)
    SELECT 1, FALSE
    WHERE NOT EXISTS (SELECT 1 FROM accounting_lock_state WHERE id = 1);
    """)

    cmd = sys.argv[1]
    if cmd == 'status':
        cur.execute("SELECT lock_enabled, locked_at, locked_by, cra_notes FROM accounting_lock_state WHERE id = 1")
        lock_enabled, locked_at, locked_by, cra_notes = cur.fetchone()
        print(f"Accounting lock enabled: {lock_enabled}")
        print(f"Locked at: {locked_at}")
        print(f"Locked by: {locked_by}")
        print(f"CRA notes: {cra_notes}")

    elif cmd == 'enable':
        locked_by = sys.argv[2] if len(sys.argv) >= 3 else os.getlogin()
        cra_notes = sys.argv[3] if len(sys.argv) >= 4 else None
        cur.execute("UPDATE accounting_lock_state SET lock_enabled=TRUE, locked_at=NOW(), locked_by=%s, cra_notes=%s WHERE id=1", (locked_by, cra_notes))
        conn.commit()
        print("Lock enabled.")

    elif cmd == 'disable':
        cur.execute("UPDATE accounting_lock_state SET lock_enabled=FALSE, locked_at=NULL, locked_by=NULL WHERE id=1")
        conn.commit()
        print("Lock disabled.")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
