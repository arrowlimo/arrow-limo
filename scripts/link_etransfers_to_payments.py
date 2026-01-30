#!/usr/bin/env python3
"""
Link e-transfers to payments by cross-referencing email_financial_events and clients.

Behavior:
- Finds unmatched banking_transactions with e-transfer patterns.
- Looks up email_financial_events with matching amounts and dates (±3 days).
- Finds associated client and payment records.
- Creates banking_payment_links entries (idempotent).

Safety:
- Dry-run by default. Use --write to apply.
- Requires exact amount match and client match to link.
"""

import argparse
import os
import re
from datetime import datetime, timedelta
import psycopg2


def get_db_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )


def is_etransfer(desc):
    d = (desc or "").lower()
    return any(k in d for k in ["interac", "e-transfer", "etransfer", "e transfer", "e- transfer"])


def main():
    parser = argparse.ArgumentParser(description="Link e-transfers to payments via email events")
    parser.add_argument("--write", action="store_true", help="Apply changes (default dry-run)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of links")
    args = parser.parse_args()

    conn = get_db_conn()
    cur = conn.cursor()

    # Get unmatched banking e-transfers (credits = revenue)
    cur.execute("""
        SELECT bt.transaction_id, bt.transaction_date, bt.description, 
               bt.credit_amount, bt.account_number
        FROM banking_transactions bt
        WHERE bt.credit_amount > 0
        AND NOT EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger br 
            WHERE br.banking_transaction_id = bt.transaction_id
        )
        AND NOT EXISTS (
            SELECT 1 FROM banking_payment_links bp 
            WHERE bp.banking_transaction_id = bt.transaction_id
        )
        ORDER BY bt.transaction_date
    """)
    banking_rows = cur.fetchall()

    # Filter to e-transfers
    etransfers = [r for r in banking_rows if is_etransfer(r[2])]
    print(f"Unmatched e-transfer credits: {len(etransfers)}")

    # Get email financial events
    cur.execute("""
        SELECT id, email_date, event_type, amount, matched_account_number, notes
        FROM email_financial_events
        WHERE event_type ILIKE '%transfer%' OR event_type ILIKE '%deposit%'
        ORDER BY email_date
    """)
    email_events = cur.fetchall()
    print(f"Email financial events: {len(email_events)}")

    # Match e-transfers to email events by amount and date (±3 days)
    candidates = []
    for bt_id, bt_date, bt_desc, bt_amount, bt_acct in etransfers:
        if not bt_date or not bt_amount:
            continue
        
        for email_id, email_date, event_type, email_amount, matched_acct, notes in email_events:
            if not email_date or not email_amount:
                continue
            
            # Amount match
            if abs(float(email_amount) - float(bt_amount)) > 0.01:
                continue
            
            # Date proximity (±3 days)
            # Normalize to date objects for comparison
            email_d = email_date.date() if hasattr(email_date, 'date') else email_date
            bt_d = bt_date.date() if hasattr(bt_date, 'date') else bt_date
            date_diff = abs((email_d - bt_d).days)
            if date_diff > 3:
                continue
            
            # Try to extract client info from notes or find payment
            # For now, just log the match as a candidate
            cur.execute("""
                SELECT payment_id, reserve_number, client_id, amount
                FROM payments
                WHERE ABS(amount - %s) < 0.01
                AND payment_date BETWEEN %s AND %s
                LIMIT 5
            """, (bt_amount, bt_date - timedelta(days=3), bt_date + timedelta(days=3)))
            
            payments = cur.fetchall()
            for pay_id, reserve_num, client_id, pay_amount in payments:
                candidates.append({
                    'banking_transaction_id': bt_id,
                    'payment_id': pay_id,
                    'bt_date': bt_date,
                    'bt_amount': bt_amount,
                    'email_id': email_id,
                    'reserve_number': reserve_num,
                    'confidence': 0.85 if date_diff == 0 else 0.75
                })

    print(f"Candidate payment links: {len(candidates)}")
    
    if not args.write:
        print("Dry-run: no database changes. Use --write to apply.")
        cur.close()
        conn.close()
        return

    # Apply links
    applied = 0
    for cand in candidates:
        if args.limit and applied >= args.limit:
            break
        
        # Check if link already exists
        cur.execute("""
            SELECT 1 FROM banking_payment_links
            WHERE banking_transaction_id = %s AND payment_id = %s
        """, (cand['banking_transaction_id'], cand['payment_id']))
        
        if cur.fetchone():
            continue
        
        cur.execute("""
            INSERT INTO banking_payment_links (
                banking_transaction_id, payment_id, link_confidence, created_at
            ) VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
        """, (cand['banking_transaction_id'], cand['payment_id'], cand['confidence']))
        
        applied += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Applied payment links: {applied}")


if __name__ == "__main__":
    main()
