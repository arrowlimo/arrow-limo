"""
Enhanced CLI for granular accounting lock/unlock control.
Supports: per-year, per-entity-type, per-action control.
"""
import os
import psycopg2
from datetime import datetime

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

HELP = """
Enhanced Accounting Lock Control

Usage:
  python -X utf8 scripts/accounting_lock_control_granular.py status
  python -X utf8 scripts/accounting_lock_control_granular.py status-year 2023
  python -X utf8 scripts/accounting_lock_control_granular.py status-type receipts
  python -X utf8 scripts/accounting_lock_control_granular.py lock-year 2023 receipts "Accountant Name" ["view,suggest only"]
  python -X utf8 scripts/accounting_lock_control_granular.py unlock-year 2023 receipts
  python -X utf8 scripts/accounting_lock_control_granular.py lock-type payments 2024 "Accountant Name" ["view,add only"]
  python -X utf8 scripts/accounting_lock_control_granular.py unlock-type payments 2024

Actions (comma-separated): view, add, suggest, edit, delete
  - view: read-only
  - add: allow new records
  - suggest: show corrections but require review
  - edit: modify existing
  - delete: remove records

Examples:
  Lock receipts for 2023 (view/suggest only, no edits):
    python -X utf8 scripts/accounting_lock_control_granular.py lock-year 2023 receipts "John Doe" "view,suggest"

  Lock all payments for 2024 (add/view only):
    python -X utf8 scripts/accounting_lock_control_granular.py lock-type payments 2024 "Jane Smith" "view,add"

  Unlock receipts for 2025 (allow corrections):
    python -X utf8 scripts/accounting_lock_control_granular.py unlock-year 2025 receipts
"""

def main():
    import sys
    if len(sys.argv) < 2 or sys.argv[1] not in (
        'status', 'status-year', 'status-type',
        'lock-year', 'unlock-year', 'lock-type', 'unlock-type'
    ):
        print(HELP)
        return

    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    # Ensure table exists
    cur.execute("""
    CREATE TABLE IF NOT EXISTS accounting_lock_controls (
      id SERIAL PRIMARY KEY,
      fiscal_year INTEGER NOT NULL,
      entity_type VARCHAR(50) NOT NULL,
      lock_enabled BOOLEAN NOT NULL DEFAULT FALSE,
      allowed_actions TEXT[] NOT NULL DEFAULT ARRAY['view', 'add'],
      locked_at TIMESTAMP,
      locked_by TEXT,
      notes TEXT,
      created_at TIMESTAMP DEFAULT NOW(),
      updated_at TIMESTAMP DEFAULT NOW(),
      UNIQUE(fiscal_year, entity_type)
    );
    """)

    # Seed defaults
    cur.execute("""
    INSERT INTO accounting_lock_controls (fiscal_year, entity_type, lock_enabled, allowed_actions)
    SELECT y, t, FALSE, ARRAY['view', 'add', 'suggest', 'edit', 'delete']
    FROM (
      SELECT generate_series(2012, 2026) AS y
    ) years
    CROSS JOIN (
      SELECT unnest(ARRAY['receipts', 'payments', 'banking_transactions', 'charters', 'invoices']) AS t
    ) types
    WHERE NOT EXISTS (
      SELECT 1 FROM accounting_lock_controls alc
      WHERE alc.fiscal_year = y AND alc.entity_type = t
    )
    ORDER BY y, t
    ON CONFLICT DO NOTHING;
    """)

    cmd = sys.argv[1]

    if cmd == 'status':
        cur.execute("""
        SELECT fiscal_year, entity_type, lock_enabled, array_to_string(allowed_actions, ', '),
               locked_at, locked_by, notes
        FROM accounting_lock_controls
        ORDER BY fiscal_year DESC, entity_type
        LIMIT 50
        """)
        print("\nGlobal Accounting Lock Status (first 50):\n")
        for year, entity, locked, actions, locked_at, locked_by, notes in cur.fetchall():
            status = "🔒 LOCKED" if locked else "🔓 UNLOCKED"
            print(f"  {status} | Year {year} | {entity:<20} | Actions: {actions}")
            if locked_by:
                print(f"           Locked by: {locked_by}, at {locked_at}")
            if notes:
                print(f"           Notes: {notes}")

    elif cmd == 'status-year':
        year = int(sys.argv[2]) if len(sys.argv) >= 3 else None
        if not year:
            print("Usage: status-year <year>")
            return
        cur.execute("""
        SELECT entity_type, lock_enabled, array_to_string(allowed_actions, ', '),
               locked_at, locked_by, notes
        FROM accounting_lock_controls
        WHERE fiscal_year = %s
        ORDER BY entity_type
        """, (year,))
        print(f"\nYear {year} Lock Status:\n")
        for entity, locked, actions, locked_at, locked_by, notes in cur.fetchall():
            status = "🔒 LOCKED" if locked else "🔓 UNLOCKED"
            print(f"  {status} | {entity:<20} | Actions: {actions}")
            if locked_by:
                print(f"           Locked by: {locked_by}")

    elif cmd == 'status-type':
        entity_type = sys.argv[2] if len(sys.argv) >= 3 else None
        if not entity_type:
            print("Usage: status-type <entity_type>")
            return
        cur.execute("""
        SELECT fiscal_year, lock_enabled, array_to_string(allowed_actions, ', '),
               locked_at, locked_by, notes
        FROM accounting_lock_controls
        WHERE entity_type = %s
        ORDER BY fiscal_year DESC
        """, (entity_type,))
        print(f"\n{entity_type} Lock Status (all years):\n")
        for year, locked, actions, locked_at, locked_by, notes in cur.fetchall():
            status = "🔒 LOCKED" if locked else "🔓 UNLOCKED"
            print(f"  {status} | Year {year:<6} | Actions: {actions}")

    elif cmd == 'lock-year':
        if len(sys.argv) < 5:
            print("Usage: lock-year <year> <entity_type> <locked_by> [allowed_actions]")
            return
        year = int(sys.argv[2])
        entity_type = sys.argv[3]
        locked_by = sys.argv[4]
        allowed_actions = (sys.argv[5].split(',') if len(sys.argv) >= 6 else ['view']).copy()
        allowed_actions = [a.strip() for a in allowed_actions]
        cur.execute("""
        UPDATE accounting_lock_controls
        SET lock_enabled = TRUE,
            allowed_actions = %s,
            locked_at = NOW(),
            locked_by = %s,
            updated_at = NOW()
        WHERE fiscal_year = %s AND entity_type = %s
        """, (allowed_actions, locked_by, year, entity_type))
        conn.commit()
        print(f"✓ Locked {entity_type} for {year}. Actions: {', '.join(allowed_actions)}")

    elif cmd == 'unlock-year':
        if len(sys.argv) < 4:
            print("Usage: unlock-year <year> <entity_type>")
            return
        year = int(sys.argv[2])
        entity_type = sys.argv[3]
        cur.execute("""
        UPDATE accounting_lock_controls
        SET lock_enabled = FALSE,
            allowed_actions = ARRAY['view', 'add', 'suggest', 'edit', 'delete'],
            locked_at = NULL,
            locked_by = NULL,
            updated_at = NOW()
        WHERE fiscal_year = %s AND entity_type = %s
        """, (year, entity_type))
        conn.commit()
        print(f"✓ Unlocked {entity_type} for {year}.")

    elif cmd == 'lock-type':
        if len(sys.argv) < 5:
            print("Usage: lock-type <entity_type> <year> <locked_by> [allowed_actions]")
            return
        entity_type = sys.argv[2]
        year = int(sys.argv[3])
        locked_by = sys.argv[4]
        allowed_actions = (sys.argv[5].split(',') if len(sys.argv) >= 6 else ['view']).copy()
        allowed_actions = [a.strip() for a in allowed_actions]
        cur.execute("""
        UPDATE accounting_lock_controls
        SET lock_enabled = TRUE,
            allowed_actions = %s,
            locked_at = NOW(),
            locked_by = %s,
            updated_at = NOW()
        WHERE entity_type = %s AND fiscal_year = %s
        """, (allowed_actions, locked_by, entity_type, year))
        conn.commit()
        print(f"✓ Locked {entity_type} for {year}. Actions: {', '.join(allowed_actions)}")

    elif cmd == 'unlock-type':
        if len(sys.argv) < 4:
            print("Usage: unlock-type <entity_type> <year>")
            return
        entity_type = sys.argv[2]
        year = int(sys.argv[3])
        cur.execute("""
        UPDATE accounting_lock_controls
        SET lock_enabled = FALSE,
            allowed_actions = ARRAY['view', 'add', 'suggest', 'edit', 'delete'],
            locked_at = NULL,
            locked_by = NULL,
            updated_at = NOW()
        WHERE entity_type = %s AND fiscal_year = %s
        """, (entity_type, year))
        conn.commit()
        print(f"✓ Unlocked {entity_type} for {year}.")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
