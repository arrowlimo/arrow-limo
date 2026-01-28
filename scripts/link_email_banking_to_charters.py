#!/usr/bin/env python3
"""
Link reconciled e-transfer banking credits to charter payments.

Inputs:
  - reports/email_banking_reconciliation.csv (source=etransfer rows with bank_txn_id, bank_date, bank_amount)

Behavior:
  - Ensure a payments row exists for each bank_txn_id (BTX:<id>), creating one if missing.
  - Attempt to link that payment to a charter using amount=total_amount_due within ±14 days, unique match only.
  - Dry-run by default; use --apply to update DB.

Outputs:
  - reports/email_banking_charter_links_applied.csv
  - reports/email_banking_charter_links_skipped.csv
"""
import os
import csv
import argparse
import re
from datetime import timedelta, datetime

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()

DB_HOST = os.getenv('DB_HOST','localhost')
DB_PORT = int(os.getenv('DB_PORT','5432'))
DB_NAME = os.getenv('DB_NAME','almsdata')
DB_USER = os.getenv('DB_USER','postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD','')

CSV_IN = r"l:/limo/reports/email_banking_reconciliation.csv"
CSV_APPLIED = r"l:/limo/reports/email_banking_charter_links_applied.csv"
CSV_SKIPPED = r"l:/limo/reports/email_banking_charter_links_skipped.csv"

DATE_WINDOW_DAYS = int(os.getenv('EMAIL_LINK_DATE_WINDOW_DAYS','14'))
ADVANCE_PAYMENT_WINDOW_DAYS = int(os.getenv('ADVANCE_PAYMENT_WINDOW_DAYS','730'))  # 2 years for advance payments
AMOUNT_TOL = float(os.getenv('EMAIL_LINK_AMOUNT_TOLERANCE','1.00'))


def get_conn():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def read_reconciled_rows():
    rows = []
    if not os.path.exists(CSV_IN):
        return rows
    with open(CSV_IN, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            if (row.get('source') or '').lower() != 'etransfer':
                continue
            try:
                bank_id = row.get('bank_txn_id')
                bank_date = row.get('bank_date')
                amount = float(row.get('bank_amount') or row.get('amount') or 0)
                if bank_id and bank_date and amount:
                    rows.append({
                        'bank_txn_id': bank_id,
                        'bank_date': datetime.strptime(bank_date, '%Y-%m-%d').date(),
                        'amount': round(float(amount), 2),
                        'email_subject': row.get('email_subject') or '',
                        'email_uid': row.get('email_uid') or '',
                        'reference_number': row.get('reference_number') or row.get('bank_desc') or '',
                    })
            except Exception:
                continue
    return rows


def ensure_payment(cur, bank_txn_id: str, bank_date, amount: float, note: str):
    pkey = f"BTX:{bank_txn_id}"
    cur.execute("SELECT payment_id FROM payments WHERE payment_key=%s", (pkey,))
    ex = cur.fetchone()
    if ex:
        return ex[0]
    cur.execute(
        """
        INSERT INTO payments (amount, payment_date, charter_id, payment_method, payment_key, notes, last_updated, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        RETURNING payment_id
        """,
        (amount, bank_date, None, 'bank_transfer', pkey, note[:500])
    )
    return cur.fetchone()[0]


def lookup_reserve_from_lms_chain(cur, search_term: str) -> list:
    """
    Look up reserve numbers using LMS payment→deposit→email chain.
    Search for various identifiers: 4-char codes, number sequences, check numbers, etc.
    """
    reserves = []
    try:
        # Strategy 1: Look in lms_deposits for the search term in the Number field
        cur.execute(
            """
            SELECT DISTINCT ld.payment_key, ld.number, ld.amount, ld.deposit_date, ld.payment_method
            FROM lms_deposits ld 
            WHERE ld.number ILIKE %s OR ld.number ILIKE %s OR ld.number = %s
            """, 
            (f'%{search_term}%', f'%#{search_term}%', search_term)
        )
        deposit_matches = cur.fetchall()
        
        for dep in deposit_matches:
            # Extract reserve number from payment_key (format: LMSDEP:xxxxxxx:reserve_part)
            if dep[0] and ':' in dep[0]:
                parts = dep[0].split(':')
                if len(parts) >= 3:
                    reserve_part = parts[2]
                    # Look for 6-digit reserve patterns
                    reserve_matches = re.findall(r'0\d{5}', reserve_part)
                    reserves.extend(reserve_matches)
        
        # Strategy 2: Look for the term in payment_key or notes of existing payments
        cur.execute(
            """
            SELECT DISTINCT c.reserve_number 
            FROM payments p
            JOIN charters c ON p.charter_id = c.charter_id
            WHERE (p.payment_key ILIKE %s OR p.notes ILIKE %s) 
              AND c.reserve_number IS NOT NULL
            """,
            (f'%{search_term}%', f'%{search_term}%')
        )
        payment_matches = cur.fetchall()
        reserves.extend([pm[0] for pm in payment_matches if pm[0]])
        
        # Strategy 3: If it looks like a check number, search check_number field
        if search_term.isdigit():
            cur.execute(
                """
                SELECT DISTINCT c.reserve_number
                FROM payments p
                JOIN charters c ON p.charter_id = c.charter_id  
                WHERE p.check_number = %s AND c.reserve_number IS NOT NULL
                """,
                (search_term,)
            )
            check_matches = cur.fetchall()
            reserves.extend([cm[0] for cm in check_matches if cm[0]])
        
    except Exception as e:
        print(f"Error in LMS chain lookup for {search_term}: {e}")
    
    return list(set(reserves))  # Remove duplicates


def extract_reserve_hints(cur, email_subject: str, reference_number: str) -> list:
    """Extract potential reserve numbers from email subject and reference fields."""
    hints = []
    
    # Extract 6-digit numbers (reserve format like 019500)
    for text in [email_subject, reference_number]:
        if text:
            # Look for 6-digit numbers starting with 0
            six_digit = re.findall(r'\b0\d{5}\b', text)
            hints.extend(six_digit)
            
            # Look for #NNNNNN patterns (6-digit)
            hash_nums_6 = re.findall(r'#(\d{6})', text)
            hints.extend([f"0{n}" if len(n) == 5 else n for n in hash_nums_6])
            
            # Look for 4-character codes like #RGbm, #CAQiVzqR, etc.
            four_char_codes = re.findall(r'#([A-Za-z0-9]{4,8})', text)
            
            # Look for standalone number sequences (6+ digits, potential check/reference numbers)
            number_sequences = re.findall(r'\b(\d{6,12})\b', text)
            
            # Search terms to look up in LMS chain
            search_terms = four_char_codes + number_sequences
            
            # For each search term, look up via LMS chain
            for term in search_terms:
                lms_reserves = lookup_reserve_from_lms_chain(cur, term)
                hints.extend(lms_reserves)
                # Don't keep the original search terms as they're not reserve numbers
            
            # Also look for common patterns that might be in banking descriptions
            # Names, amounts, dates could also be search keys
            name_matches = re.findall(r'\b([A-Z]{2,}\s+[A-Z]{2,})\b', text.upper())
            for name in name_matches:
                name_reserves = lookup_reserve_from_lms_chain(cur, name.strip())
                hints.extend(name_reserves)
    
    return list(set(hints))  # Remove duplicates


def find_unique_charter(cur, amount: float, bank_date, email_subject: str = '', reference_number: str = ''):
    # Extract reserve hints using LMS chain lookup
    reserve_hints = extract_reserve_hints(cur, email_subject, reference_number)
    
    # Strategy 1: If we have reserve hints, try exact reserve match first
    if reserve_hints:
        for reserve in reserve_hints:
            # Skip 4-char codes, look for 6-digit reserves only
            if len(reserve) == 6 and reserve.startswith('0'):
                cur.execute(
                    """
                    SELECT charter_id, reserve_number, charter_date, 
                           COALESCE(total_amount_due, COALESCE(rate,0)) AS total_amount_due,
                           COALESCE(retainer, deposit, 0) AS retainer
                      FROM charters
                     WHERE reserve_number = %s
                       AND charter_date BETWEEN %s AND %s
                       AND (ABS(COALESCE(total_amount_due, COALESCE(rate,0)) - %s) <= %s
                            OR ABS(COALESCE(retainer, deposit, 0) - %s) <= %s)
                     ORDER BY ABS(COALESCE(retainer, deposit, 0) - %s) ASC, 
                              ABS(COALESCE(total_amount_due, COALESCE(rate,0)) - %s) ASC
                    """,
                    (reserve, 
                     bank_date - timedelta(days=DATE_WINDOW_DAYS), 
                     bank_date + timedelta(days=ADVANCE_PAYMENT_WINDOW_DAYS),
                     amount, AMOUNT_TOL, amount, AMOUNT_TOL, amount, amount)
                )
                exact_matches = cur.fetchall()
                if len(exact_matches) == 1:
                    row = exact_matches[0]
                    return {
                        'charter_id': row[0],
                        'reserve_number': row[1], 
                        'charter_date': row[2],
                        'total_amount_due': row[3],
                        'retainer': row[4]
                    }
    
    # Start with simplest strategy: match retainer amounts for future charters
    cur.execute(
        """
        SELECT charter_id, reserve_number, charter_date, 
               COALESCE(total_amount_due, COALESCE(rate,0)) AS total_amount_due,
               COALESCE(retainer, deposit, 0) AS retainer
          FROM charters
         WHERE charter_date BETWEEN %s AND %s
           AND COALESCE(retainer, deposit, 0) > 0
           AND ABS(COALESCE(retainer, deposit, 0) - %s) <= %s
         ORDER BY ABS(COALESCE(retainer, deposit, 0) - %s) ASC, charter_date ASC
        """,
        (bank_date - timedelta(days=DATE_WINDOW_DAYS), 
         bank_date + timedelta(days=ADVANCE_PAYMENT_WINDOW_DAYS), 
         amount, AMOUNT_TOL, amount)
    )
    ret_rows = cur.fetchall()
    if len(ret_rows) == 1:
        return {
            'charter_id': ret_rows[0][0],
            'reserve_number': ret_rows[0][1], 
            'charter_date': ret_rows[0][2],
            'total_amount_due': ret_rows[0][3],
            'retainer': ret_rows[0][4]
        }
        
    # Fall back to matching the full due amount for future charters
    cur.execute(
        """
        SELECT charter_id, reserve_number, charter_date, 
               COALESCE(total_amount_due, COALESCE(rate,0)) AS total_amount_due,
               COALESCE(retainer, deposit, 0) AS retainer
          FROM charters
         WHERE charter_date BETWEEN %s AND %s
           AND ABS(COALESCE(total_amount_due, COALESCE(rate,0)) - %s) <= %s
         ORDER BY ABS(COALESCE(total_amount_due, COALESCE(rate,0)) - %s) ASC, charter_date ASC
        """,
        (bank_date - timedelta(days=DATE_WINDOW_DAYS), 
         bank_date + timedelta(days=ADVANCE_PAYMENT_WINDOW_DAYS), 
         amount, AMOUNT_TOL, amount)
    )
    rows = cur.fetchall()
    if len(rows) == 1:
        return {
            'charter_id': rows[0][0],
            'reserve_number': rows[0][1], 
            'charter_date': rows[0][2],
            'total_amount_due': rows[0][3],
            'retainer': rows[0][4]
        }
    return None


def main():
    ap = argparse.ArgumentParser(description='Link reconciled e-transfer deposits to charter payments')
    ap.add_argument('--apply', action='store_true', help='Perform DB updates')
    args = ap.parse_args()

    os.makedirs(os.path.dirname(CSV_APPLIED), exist_ok=True)
    applied = []
    skipped = []

    rows = read_reconciled_rows()
    if not rows:
        print('No reconciled e-transfer rows found to link.')
        return

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for r in rows:
                try:
                    pid = ensure_payment(cur, r['bank_txn_id'], r['bank_date'], r['amount'], f"[Interac email] {r['email_subject']}")
                    # Skip if already linked
                    cur.execute("SELECT charter_id FROM payments WHERE payment_id=%s", (pid,))
                    ch = cur.fetchone()
                    if ch and ch['charter_id'] is not None:
                        skipped.append({**r, 'reason':'already_linked', 'payment_id': pid})
                        continue
                    charter = find_unique_charter(cur, r['amount'], r['bank_date'], r['email_subject'], r['reference_number'])
                    if charter:
                        if args.apply:
                            cur.execute("UPDATE payments SET charter_id=%s, last_updated=NOW() WHERE payment_id=%s AND charter_id IS NULL", (charter['charter_id'], pid))
                        applied.append({
                            **r,
                            'payment_id': pid,
                            'charter_id': charter['charter_id'],
                            'reserve_number': charter['reserve_number'],
                            'charter_date': str(charter['charter_date']),
                            'due_amount': float(charter['total_amount_due'] or 0),
                            'outstanding': float(charter.get('outstanding', 0) or 0),
                            'retainer': float(charter.get('retainer', 0) or 0),
                        })
                    else:
                        skipped.append({**r, 'reason':'no_unique_charter_match', 'payment_id': pid})
                except Exception as e:
                    print(f"Error processing {r}: {e}")
                    skipped.append({**r, 'reason': f'error: {str(e)[:100]}'})
            if args.apply:
                conn.commit()

    with open(CSV_APPLIED, 'w', newline='', encoding='utf-8') as f:
        if applied:
            w = csv.DictWriter(f, fieldnames=list(applied[0].keys()))
            w.writeheader(); w.writerows(applied)
        else:
            f.write('')
    with open(CSV_SKIPPED, 'w', newline='', encoding='utf-8') as f:
        if skipped:
            keys = set()
            for r in skipped:
                keys.update(r.keys())
            w = csv.DictWriter(f, fieldnames=sorted(keys))
            w.writeheader(); w.writerows(skipped)
        else:
            f.write('')

    print(f"Email→Banking→Charter linking complete: applied={len(applied)}, skipped={len(skipped)}")
    print(' ', CSV_APPLIED)
    print(' ', CSV_SKIPPED)


if __name__ == '__main__':
    main()
