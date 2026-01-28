#!/usr/bin/env python3
"""
Create e-transfer tracking table from Outlook emails and match to banking.

Steps:
1. Create etransfer_transactions table (direction, amount, date, name, email)
2. Populate from email_financial_events where event_type like '%transfer%'
3. Match to banking_transactions by amount + date (±3 days)
4. Report matched vs unmatched

Usage:
    python create_etransfer_table_and_match.py --dry-run
    python create_etransfer_table_and_match.py --write
"""

import os
import sys
import psycopg2
from datetime import datetime, timedelta
from decimal import Decimal

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '***REMOVED***')

DRY_RUN = '--write' not in sys.argv

def get_conn():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)

def create_etransfer_table(cur):
    """Create etransfer_transactions table."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS etransfer_transactions (
            etransfer_id SERIAL PRIMARY KEY,
            direction VARCHAR(10) NOT NULL,  -- 'IN' or 'OUT'
            amount DECIMAL(12,2) NOT NULL,
            transaction_date DATE NOT NULL,
            sender_recipient_name VARCHAR(200),
            sender_recipient_email VARCHAR(200),
            reference_number VARCHAR(100),
            status VARCHAR(50),
            email_event_id INTEGER REFERENCES email_financial_events(id),
            banking_transaction_id INTEGER REFERENCES banking_transactions(transaction_id),
            matched_at TIMESTAMP,
            match_confidence VARCHAR(20),  -- 'exact', 'date_amount', 'amount_only'
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_etransfer_date_amount 
        ON etransfer_transactions(transaction_date, amount)
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_etransfer_direction 
        ON etransfer_transactions(direction, status)
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_etransfer_banking 
        ON etransfer_transactions(banking_transaction_id)
    """)

def populate_from_emails(cur):
    """Populate etransfer table from email_financial_events."""
    
    # Clear existing data
    cur.execute("DELETE FROM etransfer_transactions")
    
    # Get e-transfer events from emails (only those with amounts and dates)
    cur.execute("""
        SELECT 
            id,
            email_date,
            subject,
            from_email,
            event_type,
            amount,
            status,
            notes
        FROM email_financial_events
        WHERE amount IS NOT NULL
        AND email_date IS NOT NULL
        AND (
            event_type ILIKE '%transfer%'
            OR event_type ILIKE '%interac%'
            OR subject ILIKE '%interac%'
            OR subject ILIKE '%e-transfer%'
        )
        ORDER BY email_date
    """)
    
    emails = cur.fetchall()
    
    inserted = 0
    for email in emails:
        event_id, email_date, subject, from_email, event_type, amount, status, notes = email
        
        # Determine direction from subject/event_type
        direction = 'OUT'
        name = None
        email_addr = None
        ref_num = None
        
        subject_lower = (subject or '').lower()
        notes_lower = (notes or '').lower()
        
        # Direction detection
        if 'sent' in subject_lower or 'sent' in notes_lower:
            direction = 'OUT'
        elif 'received' in subject_lower or 'deposit' in subject_lower or 'received' in notes_lower:
            direction = 'IN'
        elif 'request' in subject_lower:
            direction = 'OUT'  # Request sent = money going out
        
        # Extract name/email from subject
        if 'to:' in subject_lower:
            parts = subject.split('to:', 1)
            if len(parts) > 1:
                name = parts[1].strip().split()[0] if parts[1].strip() else None
        elif 'from:' in subject_lower:
            parts = subject.split('from:', 1)
            if len(parts) > 1:
                name = parts[1].strip().split()[0] if parts[1].strip() else None
        
        # Try to extract email from notes or subject
        if notes and '@' in notes:
            import re
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', notes)
            if email_match:
                email_addr = email_match.group(0)
        
        # Extract reference number
        if notes and '#' in notes:
            import re
            ref_match = re.search(r'#(\d+)', notes)
            if ref_match:
                ref_num = ref_match.group(1)
        
        cur.execute("""
            INSERT INTO etransfer_transactions (
                direction, amount, transaction_date, 
                sender_recipient_name, sender_recipient_email,
                reference_number, status, email_event_id, notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (direction, amount, email_date.date() if email_date else None, 
              name, email_addr, ref_num, status, event_id, subject))
        
        inserted += 1
    
    return inserted

def match_to_banking(cur):
    """Match e-transfers to banking_transactions."""
    
    # Get unmatched e-transfers
    cur.execute("""
        SELECT 
            etransfer_id, direction, amount, transaction_date,
            sender_recipient_name, sender_recipient_email
        FROM etransfer_transactions
        WHERE banking_transaction_id IS NULL
        ORDER BY transaction_date, amount
    """)
    
    etransfers = cur.fetchall()
    
    matched_exact = 0
    matched_date_amount = 0
    matched_amount_only = 0
    unmatched = 0
    
    for etrans in etransfers:
        etrans_id, direction, amount, tdate, name, email = etrans
        
        if not tdate or not amount:
            unmatched += 1
            continue
        
        # Determine if we're looking for debit or credit in banking
        if direction == 'OUT':
            amount_col = 'debit_amount'
        else:
            amount_col = 'credit_amount'
        
        # Strategy 1: Exact date + amount + name in description
        if name:
            cur.execute(f"""
                SELECT transaction_id, description
                FROM banking_transactions
                WHERE account_number = '0228362'
                AND transaction_date = %s
                AND {amount_col} IS NOT NULL
                AND ABS({amount_col} - %s) < 0.01
                AND (description ILIKE %s OR description ILIKE %s)
                LIMIT 1
            """, (tdate, amount, f'%{name}%', '%e-transfer%'))
            
            match = cur.fetchone()
            if match:
                cur.execute("""
                    UPDATE etransfer_transactions
                    SET banking_transaction_id = %s,
                        matched_at = CURRENT_TIMESTAMP,
                        match_confidence = 'exact'
                    WHERE etransfer_id = %s
                """, (match[0], etrans_id))
                matched_exact += 1
                continue
        
        # Strategy 2: Date ±3 days + exact amount
        cur.execute(f"""
            SELECT transaction_id, transaction_date, description
            FROM banking_transactions
            WHERE account_number = '0228362'
            AND transaction_date BETWEEN %s AND %s
            AND {amount_col} IS NOT NULL
            AND ABS({amount_col} - %s) < 0.01
            AND (description ILIKE %s OR description ILIKE %s)
            ORDER BY ABS(transaction_date - %s)
            LIMIT 1
        """, (tdate - timedelta(days=3), tdate + timedelta(days=3), 
              amount, '%e-transfer%', '%interac%', tdate))
        
        match = cur.fetchone()
        if match:
            cur.execute("""
                UPDATE etransfer_transactions
                SET banking_transaction_id = %s,
                    matched_at = CURRENT_TIMESTAMP,
                    match_confidence = 'date_amount'
                WHERE etransfer_id = %s
            """, (match[0], etrans_id))
            matched_date_amount += 1
            continue
        
        # Strategy 3: Amount only (within same year)
        cur.execute(f"""
            SELECT transaction_id, transaction_date, description
            FROM banking_transactions
            WHERE account_number = '0228362'
            AND EXTRACT(YEAR FROM transaction_date) = %s
            AND {amount_col} IS NOT NULL
            AND ABS({amount_col} - %s) < 0.01
            AND (description ILIKE %s OR description ILIKE %s)
            ORDER BY ABS(transaction_date - %s)
            LIMIT 1
        """, (tdate.year, amount, '%e-transfer%', '%interac%', tdate))
        
        match = cur.fetchone()
        if match:
            cur.execute("""
                UPDATE etransfer_transactions
                SET banking_transaction_id = %s,
                    matched_at = CURRENT_TIMESTAMP,
                    match_confidence = 'amount_only'
                WHERE etransfer_id = %s
            """, (match[0], etrans_id))
            matched_amount_only += 1
            continue
        
        unmatched += 1
    
    return matched_exact, matched_date_amount, matched_amount_only, unmatched

def generate_report(cur):
    """Generate summary report."""
    
    print("\n" + "="*80)
    print("E-TRANSFER TABLE & MATCHING REPORT")
    print("="*80)
    
    # Overall counts
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN direction = 'IN' THEN 1 END) as incoming,
            COUNT(CASE WHEN direction = 'OUT' THEN 1 END) as outgoing,
            SUM(CASE WHEN direction = 'IN' THEN amount ELSE 0 END) as total_in,
            SUM(CASE WHEN direction = 'OUT' THEN amount ELSE 0 END) as total_out
        FROM etransfer_transactions
    """)
    
    totals = cur.fetchone()
    print(f"\nE-Transfer Summary:")
    print(f"  Total: {totals[0]:,}")
    print(f"  Incoming: {totals[1]:,} (${totals[3]:,.2f})")
    print(f"  Outgoing: {totals[2]:,} (${totals[4]:,.2f})")
    
    # Matching stats
    cur.execute("""
        SELECT 
            match_confidence,
            COUNT(*) as count,
            SUM(amount) as total
        FROM etransfer_transactions
        WHERE banking_transaction_id IS NOT NULL
        GROUP BY match_confidence
        ORDER BY 
            CASE match_confidence
                WHEN 'exact' THEN 1
                WHEN 'date_amount' THEN 2
                WHEN 'amount_only' THEN 3
                ELSE 4
            END
    """)
    
    matches = cur.fetchall()
    
    print(f"\nMatching Results:")
    total_matched = 0
    for conf, count, amt in matches:
        print(f"  {conf}: {count:,} (${amt:,.2f})")
        total_matched += count
    
    cur.execute("""
        SELECT COUNT(*), SUM(amount)
        FROM etransfer_transactions
        WHERE banking_transaction_id IS NULL
    """)
    
    unmatched = cur.fetchone()
    print(f"  Unmatched: {unmatched[0]:,} (${unmatched[1] or 0:,.2f})")
    
    # Show unmatched samples by direction
    print(f"\nUnmatched INCOMING (first 10):")
    cur.execute("""
        SELECT transaction_date, amount, sender_recipient_name, sender_recipient_email
        FROM etransfer_transactions
        WHERE banking_transaction_id IS NULL
        AND direction = 'IN'
        ORDER BY amount DESC
        LIMIT 10
    """)
    
    for tdate, amt, name, email in cur.fetchall():
        print(f"  {tdate} | ${amt:>10.2f} | {name or 'Unknown'} | {email or ''}")
    
    print(f"\nUnmatched OUTGOING (first 10):")
    cur.execute("""
        SELECT transaction_date, amount, sender_recipient_name, sender_recipient_email
        FROM etransfer_transactions
        WHERE banking_transaction_id IS NULL
        AND direction = 'OUT'
        ORDER BY amount DESC
        LIMIT 10
    """)
    
    for tdate, amt, name, email in cur.fetchall():
        print(f"  {tdate} | ${amt:>10.2f} | {name or 'Unknown'} | {email or ''}")

def main():
    print("\n" + "="*80)
    print("E-TRANSFER TABLE CREATION & MATCHING")
    print("="*80)
    print(f"Mode: {'DRY RUN' if DRY_RUN else 'WRITE'}")
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        print("\n1. Creating etransfer_transactions table...")
        create_etransfer_table(cur)
        print("   ✓ Table created/verified")
        
        print("\n2. Populating from email_financial_events...")
        inserted = populate_from_emails(cur)
        print(f"   ✓ Inserted {inserted:,} e-transfer records")
        
        print("\n3. Matching to banking_transactions...")
        exact, date_amt, amt_only, unmatched = match_to_banking(cur)
        print(f"   ✓ Exact matches: {exact:,}")
        print(f"   ✓ Date+Amount matches: {date_amt:,}")
        print(f"   ✓ Amount-only matches: {amt_only:,}")
        print(f"   ✓ Unmatched: {unmatched:,}")
        
        generate_report(cur)
        
        if DRY_RUN:
            conn.rollback()
            print("\n[DRY RUN] No changes saved to database.")
            print("Run with --write to apply changes.")
        else:
            conn.commit()
            print("\n[SUCCESS] Changes committed to database.")
        
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()
    
    print("\n" + "="*80)

if __name__ == '__main__':
    main()
