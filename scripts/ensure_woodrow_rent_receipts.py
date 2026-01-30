#!/usr/bin/env python3
"""
Ensure all e-transfer rent payments to Mike Woodrow (parking/shop landlord)
exist as receipts. Create missing receipts as 6800 - Rent (business expense).

Rules:
- Match banking rows: description ILIKE '%E-TRANSFER%' and ILIKE '%WOODROW%'
- Only debits (money out)
- Use deterministic source_reference: WOODROW_ETRANSFER_<transaction_id>
- Use source_hash = sha256('BANK_TXN:' + transaction_id)
- Category: '6800 - Rent', expense_account '6800'
- GST: default to 0.00 (assume landlord not GST-registered unless instructed)
- created_from_banking = true

Also update prior gas reimbursement (PARKING_SHOP_GAS_20250703) to mark as
business expense (deductible_status='business', business_personal='business').
"""

import os
import psycopg2
import hashlib

DB = dict(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***'),
)

VENDOR = 'Mike Woodrow'

def main():
    created = 0
    skipped = 0

    with psycopg2.connect(**DB) as conn:
        with conn.cursor() as cur:
            # Update prior gas reimbursement to business expense
            cur.execute("""
                UPDATE receipts
                SET deductible_status = 'business',
                    business_personal = 'business'
                WHERE source_reference = 'PARKING_SHOP_GAS_20250703'
            """)

            # Find all candidate banking transactions
            cur.execute(
                """
                SELECT transaction_id, transaction_date, description,
                       COALESCE(debit_amount,0) AS debit
                FROM banking_transactions
                WHERE COALESCE(debit_amount,0) > 0
                  AND description ILIKE '%E-TRANSFER%'
                  AND description ILIKE '%WOODROW%'
                ORDER BY transaction_date, transaction_id
                """
            )
            rows = cur.fetchall()
            print(f"Found {len(rows)} Woodrow e-transfer debit(s) in banking.")
            for tid, tdate, desc, debit in rows:
                src_ref = f"WOODROW_ETRANSFER_{tid}"
                src_hash = hashlib.sha256(f"BANK_TXN:{tid}".encode()).hexdigest()

                # Does a receipt already exist?
                cur.execute(
                    """
                    SELECT id FROM receipts
                    WHERE source_reference = %s OR source_hash = %s
                    LIMIT 1
                    """,
                    (src_ref, src_hash)
                )
                existing = cur.fetchone()
                if existing:
                    skipped += 1
                    print(f"  Skipping existing receipt for txn {tid} (id {existing[0]})")
                    continue

                # Insert new rent receipt (GST=0 by default)
                cur.execute(
                    """
                    INSERT INTO receipts (
                        vendor_name,
                        receipt_date,
                        category,
                        description,
                        source_system,
                        source_reference,
                        source_hash,
                        gross_amount,
                        gst_amount,
                        expense_account,
                        deductible_status,
                        business_personal,
                        created_from_banking,
                        created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true, CURRENT_TIMESTAMP
                    )
                    RETURNING id
                    """,
                    (
                        VENDOR,
                        tdate,
                        '6800 - Rent',
                        'Parking/Shop Rent (e-transfer) - ' + desc,
                        'BANKING_ETRANSFER',
                        src_ref,
                        src_hash,
                        float(debit),
                        0.00,            # GST assumed 0 by default
                        '6800',
                        'business',
                        'business'
                    )
                )
                rid = cur.fetchone()[0]
                created += 1
                print(f"  + Created receipt {rid} for txn {tid} on {tdate} ${float(debit):.2f}")

            conn.commit()

    print(f"\nSummary: created={created}, skipped_existing={skipped}")

if __name__ == '__main__':
    main()
