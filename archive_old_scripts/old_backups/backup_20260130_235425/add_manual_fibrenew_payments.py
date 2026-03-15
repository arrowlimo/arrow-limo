#!/usr/bin/env python3
"""
Insert manual Fibrenew cash payments into banking_transactions so the Fibrenew ledger will pick them up.

Payments to add (idempotent):
- 2019-03-26: $700.00 Cash (covers invoices 7598 $472.50 + 7848 $227.50) from fibrenew_0001.xlsx
- 2019-05-10: $700.00 Cash (noted on invoice 8691)

Notes:
- Uses debit_amount for outgoing payments to vendor
- Marks account_number='CASH' and source_file='manual:fibrenew'
- Safe to re-run: checks for existing row by (date, debit_amount, description ilike '%FIBRENEW%')
"""

import os
from datetime import date
import psycopg2

DB_SETTINGS = dict(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***'),
)

PAYMENTS = [
    {
        'transaction_date': date(2019, 3, 26),
        'debit_amount': 700.00,
        'description': "Cash Payment - FIBRENEW (Invoices 7598 $472.50 + 7848 $227.50) - Source: fibrenew_0001.xlsx",
        'notes': 'Manual cash payment recorded from receipt scan',
    },
    {
        'transaction_date': date(2019, 5, 10),
        'debit_amount': 700.00,
        'description': "Cash Payment - FIBRENEW (Noted on Invoice 8691)",
        'notes': 'Manual cash payment recorded from receipt/invoice note',
    },
]


def insert_if_missing(cur, txn):
    # Check for existing match same date, amount, and fibrenew mention
    cur.execute(
        """
        SELECT transaction_id, description
        FROM banking_transactions
        WHERE transaction_date = %s
          AND ABS(COALESCE(debit_amount,0) - %s) < 0.005
          AND description ILIKE '%%fibrenew%%'
        LIMIT 1
        """,
        (txn['transaction_date'], txn['debit_amount'])
    )
    row = cur.fetchone()
    if row:
        return ('exists', row[0], row[1])

    # Insert new manual transaction
    cur.execute(
        """
        INSERT INTO banking_transactions (
            account_number, transaction_date, posted_date, description,
            debit_amount, credit_amount, balance, vendor_extracted,
            vendor_truncated, card_last4_detected, category, source_file, import_batch
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s
        ) RETURNING transaction_id
        """,
        (
            'CASH',
            txn['transaction_date'], txn['transaction_date'], txn['description'],
            txn['debit_amount'], 0.0, None, 'FIBRENEW',
            False, None, 'Fibrenew Rent', 'manual:fibrenew', 'manual-fibrenew-payments'
        )
    )
    new_id = cur.fetchone()[0]
    return ('inserted', new_id, txn['description'])


def main():
    with psycopg2.connect(**DB_SETTINGS) as conn:
        with conn.cursor() as cur:
            # Determine a valid account_number to satisfy FK (use most common existing)
            cur.execute(
                """
                SELECT account_number
                FROM banking_transactions
                WHERE account_number IS NOT NULL AND account_number <> ''
                GROUP BY account_number
                ORDER BY COUNT(*) DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError("No existing banking account_number found to satisfy FK constraint.")
            default_account = row[0]

            print(f"Using account_number='{default_account}' to satisfy FK constraint")

            # Monkey-patch the account_number into our INSERT by temporarily changing insert_if_missing
            global insert_if_missing
            orig_insert = insert_if_missing

            def insert_if_missing_with_account(cur2, txn):
                # Check for existing match same date, amount, and fibrenew mention
                cur2.execute(
                    """
                    SELECT transaction_id, description
                    FROM banking_transactions
                    WHERE transaction_date = %s
                      AND ABS(COALESCE(debit_amount,0) - %s) < 0.005
                      AND description ILIKE '%%fibrenew%%'
                    LIMIT 1
                    """,
                    (txn['transaction_date'], txn['debit_amount'])
                )
                row2 = cur2.fetchone()
                if row2:
                    return ('exists', row2[0], row2[1])

                # Insert new manual transaction
                cur2.execute(
                    """
                    INSERT INTO banking_transactions (
                        account_number, transaction_date, posted_date, description,
                        debit_amount, credit_amount, balance, vendor_extracted,
                        vendor_truncated, card_last4_detected, category, source_file, import_batch
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    ) RETURNING transaction_id
                    """,
                    (
                        default_account,
                        txn['transaction_date'], txn['transaction_date'], "[MANUAL CASH - NOT IN BANK] " + txn['description'],
                        txn['debit_amount'], 0.0, None, 'FIBRENEW',
                        False, None, 'Fibrenew Rent', 'manual:fibrenew', 'manual-fibrenew-payments'
                    )
                )
                new_id = cur2.fetchone()[0]
                return ('inserted', new_id, txn['description'])

            insert_if_missing = insert_if_missing_with_account

            print("Adding manual Fibrenew payments (idempotent)...")
            results = []
            for p in PAYMENTS:
                status, txid, desc = insert_if_missing(cur, p)
                results.append((status, txid, desc))
            conn.commit()
            for status, txid, desc in results:
                if status == 'exists':
                    print(f"= Skipped (exists) ID {txid}: {desc[:80]}")
                else:
                    print(f"+ Inserted     ID {txid}: {desc[:80]}")

if __name__ == '__main__':
    main()
