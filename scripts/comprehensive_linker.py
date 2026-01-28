#!/usr/bin/env python3
"""
Comprehensive Payment Linking Pipeline

Connects to:
- LMS Access database (via ODBC) for source payment/deposit/charter data
- PostgreSQL almsdata for target linking

Process:
1. Extract LMS data (Payment, Deposit, Charter tables)
2. Link by reserve_number and keys
3. Analyze payment types (cash, check, etc.)
4. Search email data for matching references
5. Create definitive payment links
"""
import os
import csv
import pyodbc
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import re
from datetime import datetime
import argparse

load_dotenv('l:/limo/.env'); load_dotenv()

# PostgreSQL connection
PG_HOST = os.getenv('DB_HOST','localhost')
PG_PORT = int(os.getenv('DB_PORT','5432'))
PG_NAME = os.getenv('DB_NAME','almsdata')
PG_USER = os.getenv('DB_USER','postgres')
PG_PASSWORD = os.getenv('DB_PASSWORD','')

# LMS Access ODBC connection
LMS_PATH = r"L:\limo\lms.mdb"

def get_lms_conn():
    """Connect to LMS Access database via ODBC"""
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)

def get_pg_conn():
    """Connect to PostgreSQL almsdata"""
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_NAME, user=PG_USER, password=PG_PASSWORD)

def extract_lms_data():
    """Extract all relevant LMS data with linking information"""
    print("Connecting to LMS Access database...")
    
    with get_lms_conn() as lms_conn:
        # Get Payment data (actual columns from LMS)
        print("Extracting Payment data...")
        payments = []
        cur = lms_conn.cursor()
        cur.execute("""
            SELECT TOP 100 PaymentID, Account_No, Reserve_No, Amount, [Key], LastUpdated, LastUpdatedBy
            FROM Payment
            ORDER BY LastUpdated DESC
        """)
        for row in cur.fetchall():
            payments.append({
                'payment_id': row[0],
                'account_number': row[1],
                'reserve_number': row[2],
                'amount': float(row[3]) if row[3] else 0.0,
                'key': row[4],
                'payment_date': row[5],  # using LastUpdated as proxy for date
                'last_updated_by': row[6],
                # fields not present in Payment table; keep placeholders for downstream logic
                'payment_method': None,
                'check_number': None,
                'notes': None,
                'credit_card_last4': None,
                'authorization_code': None,
            })
        
        # Get Deposit data (actual columns from LMS)
        print("Extracting Deposit data...")
        deposits = []
        cur.execute("""
            SELECT TOP 100 [Key], [Number], [Total], [Date], [Type], [Transact]
            FROM Deposit
            ORDER BY [Date] DESC
        """)
        for row in cur.fetchall():
            deposits.append({
                'key': row[0],
                'number': row[1],
                'amount': float(row[2]) if row[2] else 0.0,
                'date': row[3],
                'type': row[4],          # e.g., Cash, Credit Card, etc.
                'transact': row[5],      # e.g., R (receipt), D (deposit) per legacy schema
            })
        
        # Get Reserve/Charter data (actual columns from LMS)
        print("Extracting Reserve data...")
        reserves = []
        cur.execute("""
            SELECT TOP 100 Reserve_No, Account_No, PU_Date,
                   Rate, Balance, Deposit, Status, Pymt_Type, Notes,
                   Name, Bill_Name, Attention
            FROM Reserve
            ORDER BY PU_Date DESC
        """)
        for row in cur.fetchall():
            reserves.append({
                'reserve_number': row[0],
                'account_number': row[1],
                'charter_date': row[2],
                'rate': float(row[3]) if row[3] else 0.0,
                'balance': float(row[4]) if row[4] else 0.0,
                'deposit': float(row[5]) if row[5] else 0.0,
                'status': row[6],
                'pymt_type': row[7],
                'notes': row[8],
                'name': row[9],
                'bill_name': row[10],
                'attention': row[11],
            })
    
    return payments, deposits, reserves

def link_lms_data(payments, deposits, reserves):
    """Link LMS data by reserve_number and create unified view"""
    print(f"Linking {len(payments)} payments, {len(deposits)} deposits, {len(reserves)} reserves...")
    
    # Create lookups
    reserve_lookup = {r['reserve_number']: r for r in reserves if r['reserve_number']}
    deposit_lookup = {}
    for d in deposits:
        if d['key']:
            deposit_lookup.setdefault(d['key'], []).append(d)
    
    linked_records = []
    
    for payment in payments:
        record = {
            'payment_data': payment,
            'reserve_data': None,
            'deposits': [],
            'payment_indicators': []
        }
        
        # Link to reserve
        if payment['reserve_number'] and payment['reserve_number'] in reserve_lookup:
            record['reserve_data'] = reserve_lookup[payment['reserve_number']]
        
        # Link to deposits via Payment.[Key] primarily; also try Reserve_No fallback
        potential_keys = [payment.get('key'), payment.get('reserve_number')]
        for key in potential_keys:
            if key and key in deposit_lookup:
                record['deposits'].extend(deposit_lookup[key])
        
        # Analyze payment indicators
        indicators = []
        # Derive method from linked deposits (Type) and/or reserve payment type
        derived_methods = list({(d.get('type') or '').strip() for d in record['deposits'] if d.get('type')})
        if record['reserve_data'] and record['reserve_data'].get('pymt_type'):
            derived_methods.append(record['reserve_data']['pymt_type'])
        for m in {m.lower() for m in derived_methods if m}:
            if m in ['cash', 'check', 'credit card', 'debit', 'square', 'etransfer', 'e-transfer', 'refund']:
                indicators.append(f"method:{m}")

        # Check number or authorization hints from deposit.Number
        for d in record['deposits']:
            num = (d.get('number') or '').strip()
            if num:
                # If looks like a check number digits of length >=4
                m = re.search(r'\b(\d{4,})\b', num)
                if m:
                    indicators.append(f"check:{m.group(1)}")
                # Auth#XXXXXX pattern
                m2 = re.search(r'Auth#\s*([A-Za-z0-9]+)', num, re.IGNORECASE)
                if m2:
                    indicators.append(f"auth:{m2.group(1)}")

        # Hash codes from reserve notes
        reserve_notes = (record['reserve_data'].get('notes') if record['reserve_data'] else '') or ''
        hash_codes = re.findall(r'#([A-Za-z0-9]{4})', reserve_notes)
        for code in hash_codes:
            indicators.append(f"hash_code:{code}")
        
        record['payment_indicators'] = indicators
        linked_records.append(record)
    
    return linked_records

def search_email_data(pg_conn, linked_records):
    """Search email data for matching payment references"""
    print("Searching email data for payment matches...")
    
    with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check if email_banking_reconciliation table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'email_banking_reconciliation'
            ) AS exists
        """)
        has_email_table = cur.fetchone()['exists']
        
        etransfer_emails = []
        if has_email_table:
            try:
                cur.execute("""
                    SELECT DISTINCT email_uid, email_subject, 
                           CAST(amount AS DECIMAL) as amount,
                           bank_txn_id, bank_date, bank_desc
                    FROM email_banking_reconciliation
                    WHERE source = 'etransfer'
                    LIMIT 100
                """)
                etransfer_emails = cur.fetchall()
            except Exception as e:
                print(f"Could not read etransfer emails: {e}")
        # CSV fallback if no rows (email_banking_reconciliation)
        if not etransfer_emails:
            try:
                csv_path = 'l:/limo/reports/email_banking_reconciliation.csv'
                if os.path.exists(csv_path):
                    with open(csv_path, newline='', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if (row.get('source') or '').lower() != 'etransfer':
                                continue
                            try:
                                amt = row.get('bank_amount') or row.get('amount') or ''
                                etransfer_emails.append({
                                    'email_uid': row.get('email_uid'),
                                    'email_subject': row.get('email_subject'),
                                    'amount': float(amt) if amt else None,
                                    'bank_txn_id': row.get('bank_txn_id'),
                                    'bank_date': row.get('bank_date'),
                                    'bank_desc': row.get('bank_desc'),
                                })
                            except Exception:
                                continue
            except Exception as e:
                print(f"CSV fallback failed for etransfers: {e}")

        # Additional CSV source: etransfer_emails.csv (raw mailbox exports)
        try:
            csv_path2 = 'l:/limo/reports/etransfer_emails.csv'
            if os.path.exists(csv_path2):
                with open(csv_path2, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            amt = row.get('amount') or ''
                            subj = row.get('subject') or row.get('email_subject') or ''
                            # Use from_name as an extra place to search for names
                            from_name = row.get('from_name') or ''
                            etransfer_emails.append({
                                'email_uid': row.get('uid') or row.get('email_uid'),
                                'email_subject': subj,
                                'amount': float(amt) if amt else None,
                                'bank_txn_id': None,
                                'bank_date': row.get('email_date'),
                                'bank_desc': from_name,
                            })
                        except Exception:
                            continue
        except Exception as e:
            print(f"CSV fallback (etransfer_emails.csv) failed: {e}")

        # Additional CSV source: etransfer_emails_deposit.csv (Interac "to X was deposited" messages)
        try:
            csv_path3 = 'l:/limo/reports/etransfer_emails_deposit.csv'
            if os.path.exists(csv_path3):
                with open(csv_path3, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            amt = row.get('amount') or ''
                            subj = row.get('subject') or ''
                            from_name = row.get('from_name') or ''
                            # Combine from_name and subject into bank_desc to maximize name matching surface
                            bank_desc = ' | '.join([p for p in [from_name, subj] if p])
                            etransfer_emails.append({
                                'email_uid': row.get('uid') or row.get('email_uid'),
                                'email_subject': subj,
                                'amount': float(amt) if amt else None,
                                'bank_txn_id': None,
                                'bank_date': row.get('email_date'),
                                'bank_desc': bank_desc,
                            })
                        except Exception:
                            continue
        except Exception as e:
            print(f"CSV fallback (etransfer_emails_deposit.csv) failed: {e}")

        # Additional CSV source: non_card_payment_candidates.csv (bank-side e-transfer transactions)
        try:
            csv_path4 = 'l:/limo/reports/non_card_payment_candidates.csv'
            if os.path.exists(csv_path4):
                with open(csv_path4, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            method = (row.get('method') or '').lower()
                            if method not in ('etransfer', 'e-transfer', 'interac', 'interac e transfer'):
                                continue
                            amt = row.get('amount') or ''
                            desc = row.get('description') or ''
                            txn_id = row.get('transaction_id') or ''
                            etransfer_emails.append({
                                'email_uid': f"BTX:{txn_id}" if txn_id else desc[:40],
                                'email_subject': desc,
                                'amount': float(amt) if amt else None,
                                'bank_txn_id': txn_id or None,
                                'bank_date': row.get('payment_date'),
                                'bank_desc': desc,
                            })
                        except Exception:
                            continue
        except Exception as e:
            print(f"CSV fallback (non_card_payment_candidates.csv) failed: {e}")

        # Deduplicate simple: by (bank_txn_id if present else email_uid/subject, amount)
        if etransfer_emails:
            seen = set()
            deduped = []
            for em in etransfer_emails:
                key = (em.get('bank_txn_id') or em.get('email_uid') or em.get('email_subject'), str(em.get('amount')))
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(em)
            etransfer_emails = deduped
        
        # Check square_emails table
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'square_emails'
            ) AS exists
        """)
        has_square_table = cur.fetchone()['exists']
        
        square_emails = []
        if has_square_table:
            try:
                cur.execute("""
                    SELECT email_uid, email_subject, amount, reference_number
                    FROM square_emails
                    WHERE email_type IN ('payment_received', 'payout', 'refund')
                    LIMIT 100
                """)
                square_emails = cur.fetchall()
            except Exception as e:
                print(f"Could not read square emails: {e}")
        # CSV fallback for Square
        if not square_emails:
            try:
                csv_path = 'l:/limo/reports/square_emails.csv'
                if os.path.exists(csv_path):
                    with open(csv_path, newline='', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            try:
                                # Only consider payout and payment_received-like rows
                                typ = (row.get('type') or '').lower()
                                if typ not in ('payout', 'payment_received', 'refund'):
                                    continue
                                amt = row.get('amount')
                                square_emails.append({
                                    'email_uid': row.get('uid'),
                                    'email_subject': row.get('subject'),
                                    'amount': float(amt) if amt else None,
                                    'reference_number': '',  # not available in CSV
                                })
                            except Exception:
                                continue
            except Exception as e:
                print(f"CSV fallback failed for square emails: {e}")
    
    print(f"Found {len(etransfer_emails)} etransfer emails, {len(square_emails)} square emails")
    
    # Match emails to linked records
    for record in linked_records:
        payment = record['payment_data']
        indicators = record['payment_indicators']
        
        record['email_matches'] = []
        
        # Search etransfer emails
        for email in etransfer_emails:
            matches = []
            
            # Amount match (within $1)
            if email['amount'] and abs(float(email['amount']) - payment['amount']) <= 1.0:
                matches.append('amount')
            
            # Reference code match
            for indicator in indicators:
                if indicator.startswith('hash_code:'):
                    code = indicator.split(':')[1]
                    if code.upper() in (email['email_subject'] or '').upper():
                        matches.append(f'hash_code:{code}')
                    if code.upper() in (email['bank_desc'] or '').upper():
                        matches.append(f'bank_desc:{code}')
            # Name match using reserve data (Name/Bill_Name/Attention) and deposit.Number
            reserve = record.get('reserve_data') or {}
            candidate_names = []
            for nm in [reserve.get('name'), reserve.get('bill_name'), reserve.get('attention')]:
                if nm and isinstance(nm, str) and len(nm.strip()) >= 3:
                    candidate_names.append(nm.strip())
            # Names from deposit numbers
            for d in record.get('deposits', []):
                num = (d.get('number') or '').strip()
                if num and any(c.isalpha() for c in num):
                    candidate_names.append(num)
            subj = (email.get('email_subject') or '')
            bdesc = (email.get('bank_desc') or '')
            for nm in candidate_names:
                if nm and (nm.lower() in subj.lower() or nm.lower() in bdesc.lower()):
                    matches.append(f'name:{nm}')
            
            # Check number match
            for indicator in indicators:
                if indicator.startswith('check:'):
                    check_num = indicator.split(':')[1]
                    if check_num in (email['bank_desc'] or ''):
                        matches.append(f'check:{check_num}')
            
            if matches:
                record['email_matches'].append({
                    'type': 'etransfer',
                    'email': dict(email),
                    'matches': matches,
                    'confidence': len(matches)
                })
        
        # Search square emails similarly
        for email in square_emails:
            matches = []
            
            if email['amount'] and abs(float(email['amount']) - payment['amount']) <= 1.0:
                matches.append('amount')
            
            for indicator in indicators:
                if indicator.startswith('hash_code:'):
                    code = indicator.split(':')[1]
                    if code.upper() in (email['reference_number'] or '').upper():
                        matches.append(f'hash_code:{code}')
            # Name match for Square subjects
            reserve = record.get('reserve_data') or {}
            candidate_names = []
            for nm in [reserve.get('name'), reserve.get('bill_name'), reserve.get('attention')]:
                if nm and isinstance(nm, str) and len(nm.strip()) >= 3:
                    candidate_names.append(nm.strip())
            subj = (email.get('email_subject') or email.get('subject') or '')
            for nm in candidate_names:
                if nm and nm.lower() in subj.lower():
                    matches.append(f'name:{nm}')
            
            if matches:
                record['email_matches'].append({
                    'type': 'square',
                    'email': dict(email),
                    'matches': matches,
                    'confidence': len(matches)
                })
    
    return linked_records

def generate_linking_report(linked_records):
    """Generate comprehensive linking report"""
    print("Generating linking report...")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = f'l:/limo/reports/comprehensive_payment_links_{timestamp}.csv'
    
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    
    with open(report_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'reserve_number', 'payment_id', 'amount', 'derived_method',
            'payment_date', 'check_number', 'auth_code', 'payment_indicators',
            'email_matches_count', 'best_email_match_type', 'best_email_amount', 'best_email_bank_txn_id', 'best_email_bank_desc', 'best_match_confidence',
            'charter_rate', 'charter_deposit', 'charter_status', 'reserve_pymt_type',
            'deposit_count', 'deposit_methods', 'deposit_keys', 'deposit_numbers', 'deposit_dates',
            'recommended_action'
        ])
        
        for record in linked_records:
            payment = record['payment_data']
            reserve = record['reserve_data']
            deposits = record['deposits']
            email_matches = record['email_matches']
            
            # Best email match (prefer etransfer ties)
            best_match = None
            if email_matches:
                best_match = max(email_matches, key=lambda x: (x['confidence'], 1 if x['type']=='etransfer' else 0))
            
            # Determine a derived method for reporting
            deposit_methods = [d.get('type') or '' for d in deposits]
            reserve_method = reserve.get('pymt_type') if reserve else None
            method_candidates = [m for m in deposit_methods + ([reserve_method] if reserve_method else []) if m]
            derived_method = method_candidates[0] if method_candidates else ''

            # Recommended action
            action = 'manual_review'
            if best_match and best_match['confidence'] >= 2:
                action = 'auto_link_high_confidence'
            elif best_match and best_match['confidence'] == 1 and payment['amount'] > 0:
                action = 'auto_link_medium_confidence'
            elif not email_matches and derived_method in ['Cash', 'Check', 'cash', 'check']:
                action = 'link_as_cash_check'
            
            writer.writerow([
                payment['reserve_number'],
                payment['payment_id'],
                payment['amount'],
                derived_method,
                payment['payment_date'],
                '',
                '',
                '; '.join(record['payment_indicators']),
                len(email_matches),
                best_match['type'] if best_match else '',
                (best_match['email'].get('amount') if best_match else ''),
                (best_match['email'].get('bank_txn_id') if best_match else ''),
                (best_match['email'].get('bank_desc') if best_match else ''),
                best_match['confidence'] if best_match else 0,
                reserve['rate'] if reserve else '',
                reserve['deposit'] if reserve else '',
                reserve['status'] if reserve else '',
                reserve.get('pymt_type') if reserve else '',
                len(deposits),
                '; '.join([d.get('type') or '' for d in deposits]),
                '; '.join([d.get('key') or '' for d in deposits]),
                '; '.join([d.get('number') or '' for d in deposits]),
                '; '.join([str(d.get('date') or '') for d in deposits]),
                action
            ])
    
    print(f"Report saved: {report_file}")
    return report_file

def apply_high_confidence_links(pg_conn, linked_records, apply_changes=False, min_confidence: int = 2):
    """Create/link payments in Postgres for high-confidence Interac matches.

    - Only applies for etransfer matches with confidence >= 2
    - Requires reserve mapping to a charter_id via reserve_number
    - Creates or updates payments keyed by BTX:<bank_txn_id>
    """
    applied = []
    skipped = []

    def ensure_payment(cur, amount, pay_date, method, key, notes):
        cur.execute("SELECT payment_id, charter_id FROM payments WHERE payment_key=%s", (key,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            """
            INSERT INTO payments (amount, payment_date, charter_id, payment_method, payment_key, notes, last_updated, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            RETURNING payment_id
            """,
            (amount, pay_date, None, method, key, notes[:500] if notes else None)
        )
        return cur.fetchone()[0]

    applied_csv = f"l:/limo/reports/comprehensive_links_applied_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    skipped_csv = f"l:/limo/reports/comprehensive_links_skipped_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    with pg_conn.cursor() as cur:
        for r in linked_records:
            payment = r['payment_data']
            reserve = r['reserve_data']
            if not r.get('email_matches'):
                skipped.append({'payment_id': payment['payment_id'], 'reason': 'no_email_matches'})
                continue
            best = max(r['email_matches'], key=lambda x: (x['confidence'], 1 if x['type']=='etransfer' else 0))
            # Only auto-apply Interac matches
            if best['type'] != 'etransfer' or best['confidence'] < min_confidence:
                skipped.append({'payment_id': payment['payment_id'], 'reason': 'low_confidence_or_non_etransfer'})
                continue
            if not reserve or not reserve.get('reserve_number'):
                skipped.append({'payment_id': payment['payment_id'], 'reason': 'no_reserve'})
                continue
            # Find charter by reserve_number
            cur.execute("SELECT charter_id, charter_date FROM charters WHERE reserve_number=%s ORDER BY charter_date DESC LIMIT 1", (reserve['reserve_number'],))
            ch = cur.fetchone()
            if not ch:
                skipped.append({'payment_id': payment['payment_id'], 'reason': 'reserve_not_in_charters', 'reserve_number': reserve['reserve_number']})
                continue
            charter_id = ch[0]
            email = best['email']
            key = f"BTX:{email.get('bank_txn_id')}" if email.get('bank_txn_id') else f"ETR:{email.get('email_uid')}"
            pay_date = email.get('bank_date') or payment.get('payment_date')
            try:
                if apply_changes:
                    pid = ensure_payment(cur, payment['amount'], pay_date, 'bank_transfer', key, f"Auto-linked from comprehensive linker; signals={best['matches']}")
                    # Link charter
                    cur.execute("UPDATE payments SET charter_id=%s, last_updated=NOW() WHERE payment_id=%s AND charter_id IS NULL", (charter_id, pid))
                    applied.append({'payment_id': payment['payment_id'], 'new_payment_id': pid, 'charter_id': charter_id, 'reserve_number': reserve['reserve_number'], 'confidence': best['confidence'], 'key': key})
                else:
                    # Dry-run: report what would be applied without writing
                    applied.append({'payment_id': payment['payment_id'], 'new_payment_id': None, 'charter_id': charter_id, 'reserve_number': reserve['reserve_number'], 'confidence': best['confidence'], 'key': key})
            except Exception as e:
                skipped.append({'payment_id': payment['payment_id'], 'reason': f'error:{str(e)[:120]}'})

        if apply_changes:
            pg_conn.commit()

    # Write CSV summaries
    os.makedirs('l:/limo/reports', exist_ok=True)
    with open(applied_csv, 'w', newline='', encoding='utf-8') as f:
        if applied:
            w = csv.DictWriter(f, fieldnames=list(applied[0].keys()))
            w.writeheader(); w.writerows(applied)
    with open(skipped_csv, 'w', newline='', encoding='utf-8') as f:
        if skipped:
            keys = set()
            for row in skipped:
                keys.update(row.keys())
            w = csv.DictWriter(f, fieldnames=sorted(keys))
            w.writeheader(); w.writerows(skipped)

    print(f"Apply step complete: applied={len(applied)}, skipped={len(skipped)}")
    print(f"  {applied_csv}")
    print(f"  {skipped_csv}")
    return applied_csv, skipped_csv

def main():
    print("=== Comprehensive Payment Linking Pipeline ===")
    ap = argparse.ArgumentParser(description='Comprehensive LMS + Email payment linker')
    ap.add_argument('--apply', action='store_true', help='Apply Interac matches to Postgres payments table')
    ap.add_argument('--min-confidence', type=int, default=2, help='Minimum confidence to auto-apply Interac matches (default: 2)')
    args = ap.parse_args()
    
    try:
        # Extract LMS data
        payments, deposits, reserves = extract_lms_data()
        print(f"Extracted: {len(payments)} payments, {len(deposits)} deposits, {len(reserves)} reserves")
        
        # Link LMS data internally
        linked_records = link_lms_data(payments, deposits, reserves)
        
        # Search email data for matches
        with get_pg_conn() as pg_conn:
            linked_records = search_email_data(pg_conn, linked_records)
        
        # Generate report (expanded)
        report_file = generate_linking_report(linked_records)
        
        # Summary stats
        total_records = len(linked_records)
        with_email_matches = len([r for r in linked_records if r['email_matches']])
        high_confidence = len([r for r in linked_records if r['email_matches'] and max(m['confidence'] for m in r['email_matches']) >= 2])
        
        print(f"\n=== Summary ===")
        print(f"Total payment records: {total_records}")
        print(f"With email matches: {with_email_matches}")
        print(f"High confidence matches: {high_confidence}")
        print(f"Report saved: {report_file}")
        
        # Optional apply step
        with get_pg_conn() as pg_conn:
            apply_high_confidence_links(pg_conn, linked_records, apply_changes=args.apply, min_confidence=args.min_confidence)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()