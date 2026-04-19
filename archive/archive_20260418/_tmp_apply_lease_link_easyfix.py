import psycopg2
from decimal import Decimal, ROUND_HALF_UP

missing_ids = [77875,60621,102454,102455,78789]

conn = psycopg2.connect(host='localhost',port=5432,dbname='almsdata',user='postgres',password='ArrowLimousine')
cur = conn.cursor()

try:
    cur.execute('CREATE TABLE IF NOT EXISTS backup_easyfix_lease_links_20260407 AS SELECT * FROM receipts WHERE 1=0')

    backup_ids = [143479,150730,150731]
    cur.execute('''
        INSERT INTO backup_easyfix_lease_links_20260407
        SELECT * FROM receipts WHERE receipt_id = ANY(%s)
    ''', (backup_ids,))

    # Relink three obvious rows to resolve missing banking links safely
    cur.execute('''
        UPDATE receipts
        SET banking_transaction_id = 60621,
            updated_at = NOW(),
            receipt_review_notes = COALESCE(receipt_review_notes,'') ||
                CASE WHEN COALESCE(receipt_review_notes,'')='' THEN '' ELSE E'\\n' END ||
                'Easy fix 2026-04-07: relinked from banking txn 100254 to 60621 (Lease Finance Group).'
        WHERE receipt_id = 143479 AND banking_transaction_id = 100254
    ''')
    u1 = cur.rowcount

    cur.execute('''
        UPDATE receipts
        SET banking_transaction_id = 102454,
            updated_at = NOW(),
            receipt_review_notes = COALESCE(receipt_review_notes,'') ||
                CASE WHEN COALESCE(receipt_review_notes,'')='' THEN '' ELSE E'\\n' END ||
                'Easy fix 2026-04-07: relinked from banking txn 82690 to 102454 duplicate import id.'
        WHERE receipt_id = 150730 AND banking_transaction_id = 82690
    ''')
    u2 = cur.rowcount

    cur.execute('''
        UPDATE receipts
        SET banking_transaction_id = 102455,
            updated_at = NOW(),
            receipt_review_notes = COALESCE(receipt_review_notes,'') ||
                CASE WHEN COALESCE(receipt_review_notes,'')='' THEN '' ELSE E'\\n' END ||
                'Easy fix 2026-04-07: relinked from banking txn 82691 to 102455 duplicate import id.'
        WHERE receipt_id = 150731 AND banking_transaction_id = 82691
    ''')
    u3 = cur.rowcount

    # Backup existing rows for two transaction IDs if already present (defensive)
    cur.execute('''
        INSERT INTO backup_easyfix_lease_links_20260407
        SELECT * FROM receipts
        WHERE banking_transaction_id IN (77875, 78789)
    ''')

    # Insert two truly missing Jack Carter lease receipts if no receipt currently linked
    cur.execute('''
        INSERT INTO receipts (
            receipt_date, vendor_name, canonical_vendor, description,
            gross_amount, gst_amount,
            gl_account_code, gl_code,
            category,
            banking_transaction_id,
            created_from_banking,
            receipt_source,
            is_nsf,
            exclude_from_reports,
            potential_duplicate,
            receipt_review_status,
            receipt_review_notes,
            created_at,
            updated_at
        )
        SELECT
            bt.transaction_date,
            'JACK CARTER',
            'JACK CARTER',
            bt.description,
            bt.debit_amount,
            ROUND((bt.debit_amount * 0.05 / 1.05)::numeric, 2),
            '5150',
            '5150',
            'LEASE',
            bt.transaction_id,
            TRUE,
            'easy_fix_lease_link_20260407',
            FALSE,
            FALSE,
            FALSE,
            'LEASE_LINKED',
            'Easy fix 2026-04-07: inserted missing Jack Carter lease receipt for existing banking transaction.',
            NOW(),
            NOW()
        FROM banking_transactions bt
        WHERE bt.transaction_id IN (77875, 78789)
          AND COALESCE(bt.debit_amount,0) > 0
          AND NOT EXISTS (
              SELECT 1 FROM receipts r WHERE r.banking_transaction_id = bt.transaction_id
          )
    ''')
    ins = cur.rowcount

    # Post-check unresolved IDs
    cur.execute('''
        SELECT COUNT(*)
        FROM banking_transactions bt
        LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
        WHERE bt.transaction_id = ANY(%s)
          AND r.receipt_id IS NULL
    ''', (missing_ids,))
    unresolved = cur.fetchone()[0]

    conn.commit()
    print('LEASE_LINK_EASY_FIX_APPLIED')
    print('updated_relinks', u1 + u2 + u3, 'details', u1, u2, u3)
    print('inserted_new_receipts', ins)
    print('unresolved_missing_ids', unresolved)

except Exception:
    conn.rollback()
    raise
finally:
    cur.close()
    conn.close()
