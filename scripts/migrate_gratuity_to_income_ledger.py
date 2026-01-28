import argparse
import psycopg2
from datetime import datetime
import hashlib
import re

def get_db_connection():
    import os
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        dbname=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***')
    )

def print_header(mode):
    print("="*90)
    print("Migrate Gratuity Receipts to Income Ledger (GL 4150)")
    print(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S} | Mode: {mode}")
    print("="*90)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    mode = 'WRITE' if args.write else 'DRY-RUN'
    print_header(mode)

    conn = get_db_connection()
    cur = conn.cursor()

    # Fetch gratuity receipts candidates
    cur.execute(
        """
        SELECT r.receipt_id, r.receipt_date, r.vendor_name, r.description, r.category,
               r.gross_amount, r.gst_amount, r.net_amount,
               bm.banking_transaction_id
        FROM receipts r
        LEFT JOIN banking_receipt_matching_ledger bm ON bm.receipt_id = r.receipt_id
        WHERE r.gross_amount > 0
          AND (
               LOWER(r.category) = 'gratuity' OR
               LOWER(r.category) = 'gratuity_revenue' OR
               LOWER(r.description) LIKE '%gratuity%'
          )
        ORDER BY r.receipt_date
        """
    )
    rows = cur.fetchall()
    if not rows:
        print("No gratuity receipts found.")
        cur.close(); conn.close(); return

    print(f"Found {len(rows)} gratuity receipts candidates.")

    # Determine journal/unified ledger schema
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'unified_general_ledger'")
    ugl_cols = {row[0] for row in cur.fetchall()}
    use_ugl = 'account_code' in ugl_cols and 'credit_amount' in ugl_cols

    if not use_ugl:
        print("⚠️ unified_general_ledger not available; attempting 'journal' table")
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'journal'")
        journal_cols = {row[0] for row in cur.fetchall()}
        if not {'Account','Credit','Debit'}.issubset(journal_cols):
            print("❌ Neither unified_general_ledger nor journal have expected columns. Aborting.")
            cur.close(); conn.close(); return

    # Ensure link table exists for tiny record mapping
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS gratuity_income_links (
            id SERIAL PRIMARY KEY,
            receipt_id INTEGER NOT NULL,
            ugl_id INTEGER,
            reserve_number VARCHAR(20),
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
    )

    # Prepare inserts (dry run summary)
    to_insert = []
    for rid, rdate, vendor, desc, cat, gross, gst, net, bt_id in rows:
        # Build source hash to prevent duplicates
        h = hashlib.sha256(f"gratuity|{rdate}|{vendor}|{float(gross):.2f}".encode('utf-8')).hexdigest()
        # Extract reserve number from vendor/description if present
        rn = None
        for text in [vendor or '', desc or '']:
            m = re.search(r'(?:reserve[_\-\s:]*)?(\d{6})', text, re.IGNORECASE)
            if m:
                rn = m.group(1)
                break
        to_insert.append({
            'receipt_id': rid,
            'date': rdate,
            'vendor': vendor or 'Gratuity',
            'description': (desc or 'Gratuity revenue from charter'),
            'gross': float(gross),
            'gst': float(gst or 0.0),
            'net': float(net or 0.0),
            'banking_transaction_id': bt_id,
            'source_hash': h,
            'reserve_number': rn
        })

    print("\nSample to insert (first 10):")
    for s in to_insert[:10]:
        rn_disp = s['reserve_number'] or 'None'
        print(f"  {s['date']} | {s['vendor'][:28].ljust(28)} | gross=${s['gross']:>8,.2f} | gst=${s['gst']:>7,.2f} | net=${s['net']:>8,.2f} | RN:{rn_disp}")

    # Count existing entries by hash
    if use_ugl:
        cur.execute("SELECT description FROM unified_general_ledger WHERE description LIKE '%[gratuity:%]' ")
        # This query may be empty; rely on NOT EXISTS guards below
    else:
        pass

    if args.write:
        # Backup receipts being reclassified
        backup_name = f"receipts_gratuity_migration_backup_{datetime.now():%Y%m%d_%H%M%S}"
        cur.execute(f"""
            CREATE TABLE {backup_name} AS
            SELECT * FROM receipts r
            WHERE r.gross_amount > 0
              AND (LOWER(r.category) IN ('gratuity','gratuity_revenue')
                   OR LOWER(r.description) LIKE '%gratuity%')
        """)
        print(f"Backup created: {backup_name} ({len(rows)} rows)")

        inserted = 0
        for s in to_insert:
            if use_ugl:
                # Insert income (credit) into unified_general_ledger
                cur.execute(
                    """
                    INSERT INTO unified_general_ledger (
                        transaction_date, account_code, account_name, description,
                        debit_amount, credit_amount, source_system, source_transaction_id, created_at
                    )
                    SELECT %s, %s, %s, %s, NULL, %s, 'receipts', %s, NOW()
                    WHERE NOT EXISTS (
                        SELECT 1 FROM unified_general_ledger ugl
                        WHERE ugl.transaction_date = %s
                          AND ugl.account_code = %s
                          AND ugl.credit_amount = %s
                          AND ugl.description = %s
                    )
                    """,
                    (
                        s['date'], '4150', 'Gratuity Revenue', f"[gratuity:{s['receipt_id']}|RN:{s['reserve_number'] or 'None'}] " + s['description'],
                        s['gross'], s['receipt_id'],
                        s['date'], '4150', s['gross'], f"[gratuity:{s['receipt_id']}|RN:{s['reserve_number'] or 'None'}] " + s['description']
                    )
                )
                inserted += cur.rowcount
                # Fetch ugl_id (existing or just inserted) for tiny mapping record
                cur.execute(
                    """
                    SELECT id FROM unified_general_ledger
                    WHERE transaction_date = %s AND account_code = %s AND credit_amount = %s AND description = %s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (s['date'], '4150', s['gross'], f"[gratuity:{s['receipt_id']}|RN:{s['reserve_number'] or 'None'}] " + s['description'])
                )
                row = cur.fetchone()
                ugl_id = row[0] if row else None
                # Insert tiny link record
                cur.execute(
                    """
                    INSERT INTO gratuity_income_links (receipt_id, ugl_id, reserve_number)
                    SELECT %s, %s, %s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM gratuity_income_links WHERE receipt_id = %s AND COALESCE(ugl_id, -1) = COALESCE(%s, -1)
                    )
                    """,
                    (s['receipt_id'], ugl_id, s['reserve_number'], s['receipt_id'], ugl_id)
                )
            else:
                # Fallback to journal (Credit side)
                cur.execute(
                    """
                    INSERT INTO journal (Date, Account, Name, "Memo/Description", Credit, Debit, merchant, transaction_type, reference_number)
                    SELECT %s, %s, %s, %s, %s, NULL, %s, %s, %s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM journal j
                        WHERE j.Date = %s
                          AND j.Account = %s
                          AND j.Credit = %s
                          AND j."Memo/Description" = %s
                    )
                    """,
                    (
                        s['date'], '4150 Gratuity Revenue', s['vendor'], f"[gratuity:{s['receipt_id']}|RN:{s['reserve_number'] or 'None'}] " + s['description'],
                        s['gross'], s['vendor'], 'income', str(s['receipt_id']),
                        s['date'], '4150 Gratuity Revenue', s['gross'], f"[gratuity:{s['receipt_id']}|RN:{s['reserve_number'] or 'None'}] " + s['description']
                    )
                )
                inserted += cur.rowcount
                # Tiny link record without ugl_id
                cur.execute(
                    """
                    INSERT INTO gratuity_income_links (receipt_id, ugl_id, reserve_number)
                    SELECT %s, NULL, %s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM gratuity_income_links WHERE receipt_id = %s AND ugl_id IS NULL
                    )
                    """,
                    (s['receipt_id'], s['reserve_number'], s['receipt_id'])
                )

        # Mark receipts as reclassified (optional: adjust category)
                # Reclassify receipts (append marker to description; avoid notes column which may not exist)
                cur.execute(
                        """
                        UPDATE receipts
                        SET category = 'gratuity_income',
                                description = COALESCE(description,'') || ' [migrated_to_income_ledger]'
                        WHERE gross_amount > 0
                            AND (LOWER(category) IN ('gratuity','gratuity_revenue') OR LOWER(description) LIKE '%gratuity%')
                        """
                )

        conn.commit()
        print(f"Inserted {inserted} income ledger entries. Reclassified gratuity receipts and created tiny link records.")
    else:
        print("\nDRY-RUN only. Re-run with --write to migrate into income ledger and reclassify receipts.")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
