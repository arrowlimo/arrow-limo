#!/usr/bin/env python3
"""
One-way sync: local almsdata → Neon (push only).
- Detects new/updated rows using last_updated/updated_at/created_at
- Pushes changes from local → Neon (no pull/backfill from Neon)
- Uses reserve_number as the business key for charters/payments

Usage:
    python sync_local_neon.py                # push local → Neon
    python sync_local_neon.py --test         # insert sample then push
    python sync_local_neon.py --limit 100    # limit rows pushed
"""

import os
import argparse
import psycopg2
from datetime import datetime, timedelta
from typing import List, Dict, Tuple

# Connection settings (env overrides defaults)
LOCAL_CONN = {
    'host': os.environ.get('DB_HOST_LOCAL', 'localhost'),
    'database': os.environ.get('DB_NAME_LOCAL', 'almsdata'),
    'user': os.environ.get('DB_USER_LOCAL', 'postgres'),
    'password': os.environ.get('DB_PASSWORD_LOCAL', '***REDACTED***'),
}

NEON_CONN = {
    # Prefer explicit NEON_* vars; fall back to generic DB_* if provided
    'host': os.environ.get('NEON_HOST') or os.environ.get('DB_HOST') or 'ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech',
    'user': os.environ.get('NEON_USER') or os.environ.get('DB_USER') or 'neondb_owner',
    'password': os.environ.get('NEON_PASSWORD') or os.environ.get('DB_PASSWORD') or 'npg_89MbcFmZwUWo',
    'database': os.environ.get('NEON_DB') or os.environ.get('DB_NAME') or 'neondb',
    'sslmode': os.environ.get('NEON_SSLMODE') or os.environ.get('DB_SSLMODE') or 'require',
    'port': int(os.environ.get('NEON_PORT') or os.environ.get('DB_PORT') or 5432),
}


def connect_local():
    return psycopg2.connect(**LOCAL_CONN)


def connect_neon():
    return psycopg2.connect(**NEON_CONN)


def get_columns(cur, table: str) -> List[str]:
    """Return list of columns for a table (public schema)."""
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table,)
    )
    return [r[0] for r in cur.fetchall()]


def find_recent_inserts(cur, table: str, since_minutes: int = 60) -> List[Dict]:
    """Find rows inserted/updated in the last N minutes."""
    cutoff = datetime.utcnow() - timedelta(minutes=since_minutes)
    
    # Check if table has created_at or last_updated
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = %s AND column_name IN ('created_at', 'last_updated', 'updated_at')
        LIMIT 1
    """, (table,))
    
    ts_col = cur.fetchone()
    if not ts_col:
        return []
    
    ts_col = ts_col[0]
    
    # Get columns for the table
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = %s AND table_schema = 'public'
        ORDER BY ordinal_position
    """, (table,))
    
    columns = [r[0] for r in cur.fetchall()]
    col_list = ', '.join(columns)
    
    query = f"""
        SELECT {col_list} FROM {table}
        WHERE {ts_col} >= %s
        ORDER BY {ts_col} DESC
    """
    
    cur.execute(query, (cutoff,))
    rows = cur.fetchall()
    
    return [dict(zip(columns, row)) for row in rows]


def push_charters(local_cur, neon_cur, limit: int = None) -> Tuple[int, int]:
    """Push new/updated charters from local → Neon."""
    recent = find_recent_inserts(local_cur, 'charters', since_minutes=1440)
    if limit:
        recent = recent[:limit]
    
    pushed = 0
    skipped = 0
    
    for row in recent:
        res_no = row.get('reserve_number')
        if not res_no:
            skipped += 1
            continue
        
        # Check if exists in Neon
        neon_cur.execute(
            "SELECT charter_id FROM charters WHERE reserve_number = %s",
            (res_no,)
        )
        neon_exists = neon_cur.fetchone()
        
        if not neon_exists:
            # Insert only (don't try to update with non-existent columns)
            cols = [c for c in row.keys() if c != 'charter_id']
            placeholders = ', '.join(['%s'] * len(cols))
            col_list = ', '.join(cols)
            values = [row[c] for c in cols]
            
            query = f"INSERT INTO charters ({col_list}) VALUES ({placeholders})"
            try:
                neon_cur.execute(query, values)
                pushed += 1
            except Exception as e:
                print(f"  ⚠ Failed to insert charter {res_no}: {e}")
                skipped += 1
        else:
            skipped += 1  # Already exists
    
    return pushed, skipped


def push_payments(local_cur, neon_cur, limit: int = None) -> Tuple[int, int]:
    """Push new payments from local → Neon."""
    recent = find_recent_inserts(local_cur, 'payments', since_minutes=1440)
    if limit:
        recent = recent[:limit]
    
    pushed = 0
    skipped = 0
    
    for row in recent:
        res_no = row.get('reserve_number')
        amt = row.get('amount')
        
        if not res_no or amt is None:
            skipped += 1
            continue
        
        # Check if exists (by reserve + amount + date)
        payment_date = row.get('payment_date') or row.get('created_at')
        
        if payment_date:
            neon_cur.execute(
                """SELECT payment_id FROM payments 
                   WHERE reserve_number = %s AND amount = %s 
                   AND CAST(payment_date AS DATE) = CAST(%s AS DATE)
                   LIMIT 1""",
                (res_no, amt, payment_date)
            )
            if neon_cur.fetchone():
                skipped += 1
                continue
        
        # Insert payment
        cols = list(row.keys())
        placeholders = ', '.join(['%s'] * len(cols))
        col_list = ', '.join(cols)
        values = [row[c] for c in cols]
        
        query = f"INSERT INTO payments ({col_list}) VALUES ({placeholders})"
        try:
            neon_cur.execute(query, values)
            pushed += 1
        except Exception as e:
            print(f"  ⚠ Failed to insert payment for {res_no}: {e}")
            skipped += 1
    
    return pushed, skipped


def pull_from_neon(neon_cur, local_cur, table: str, limit: int = None) -> Tuple[int, int]:
    """Pull new rows from Neon → local (read-only, for verification)."""
    recent = find_recent_inserts(neon_cur, table, since_minutes=1440)
    if limit:
        recent = recent[:limit]
    
    pulled = 0
    skipped = 0
    
    print(f"  Found {len(recent)} recent rows in Neon.{table}")
    # For now, just report (read-only pull)
    
    return pulled, skipped


def main():
    ap = argparse.ArgumentParser(description="One-way sync local → Neon (push only)")
    ap.add_argument('--test', action='store_true', help='Test mode: insert sample and sync')
    ap.add_argument('--limit', type=int, default=None, help='Limit rows to sync')
    args = ap.parse_args()
    
    local = connect_local()
    neon = connect_neon()
    local_cur = local.cursor()
    neon_cur = neon.cursor()
    
    try:
        print("[ONE-WAY SYNC] Local → Neon")
        print("=" * 60)
        
        if args.test:
            print("\n[TEST MODE] Inserting sample charters and payments...")
            
            # Insert test charter into local
            test_res = '099999'
            local_cur.execute(
                """INSERT INTO charters (reserve_number, account_number, charter_date, total_amount_due, paid_amount, balance, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, NOW())
                   ON CONFLICT (reserve_number) DO NOTHING""",
                (test_res, 'TEST_ACCT', datetime.utcnow().date(), 500.00, 0.00, 500.00)
            )
            local.commit()
            print(f"  OK Inserted test charter {test_res} into local")
            
            # Insert test payment
            local_cur.execute(
                """INSERT INTO payments (reserve_number, amount, payment_date, created_at)
                   VALUES (%s, %s, %s, NOW())""",
                (test_res, 100.00, datetime.utcnow().date())
            )
            local.commit()
            print(f"  OK Inserted test payment $100 into local")
            print()
        
        print("[PUSH] Local -> Neon")
        print("-" * 60)
        
        c_pushed, c_skipped = push_charters(local_cur, neon_cur, args.limit)
        print(f"  Charters: {c_pushed} pushed, {c_skipped} skipped")
        
        p_pushed, p_skipped = push_payments(local_cur, neon_cur, args.limit)
        print(f"  Payments: {p_pushed} pushed, {p_skipped} skipped")
        
        neon.commit()
        print(f"  SUCCESS Neon committed")
        
        # Final counts
        print("\n" + "=" * 60)
        print("FINAL COUNTS:")
        
        local_cur.execute("SELECT COUNT(*) FROM charters")
        local_charters = local_cur.fetchone()[0]
        
        neon_cur.execute("SELECT COUNT(*) FROM charters")
        neon_charters = neon_cur.fetchone()[0]
        
        local_cur.execute("SELECT COUNT(*) FROM payments")
        local_payments = local_cur.fetchone()[0]
        
        neon_cur.execute("SELECT COUNT(*) FROM payments")
        neon_payments = neon_cur.fetchone()[0]
        
        sync_charters = 'OK SYNCED' if local_charters == neon_charters else 'FAIL OUT OF SYNC'
        sync_payments = 'OK SYNCED' if local_payments == neon_payments else 'FAIL OUT OF SYNC'
        print(f"Charters: Local={local_charters:,} | Neon={neon_charters:,} | {sync_charters}")
        print(f"Payments: Local={local_payments:,} | Neon={neon_payments:,} | {sync_payments}")
        
    finally:
        local_cur.close()
        neon_cur.close()
        local.close()
        neon.close()


if __name__ == '__main__':
    main()
