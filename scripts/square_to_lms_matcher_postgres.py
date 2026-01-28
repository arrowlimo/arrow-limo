#!/usr/bin/env python3
"""
Comprehensive Square Payment to LMS Matcher - Postgres Version

Matching Logic:
1. Square payment amount → LMS Deposit by amount (exact match)  
2. LMS Deposit → Charter (by deposit relationship)
3. Charter → Reserve (by reserve_number)
4. Validate CIBC banking date within 4 days (workweek timing)
5. Link Square payment to charter via reserve_number

This version uses the Postgres LMS tables for much faster performance.
"""
import os
import csv
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime, timedelta
import argparse

load_dotenv('l:/limo/.env'); load_dotenv()

# PostgreSQL connection
PG_HOST = os.getenv('DB_HOST','localhost')
PG_PORT = int(os.getenv('DB_PORT','5432'))
PG_NAME = os.getenv('DB_NAME','almsdata')
PG_USER = os.getenv('DB_USER','postgres')
PG_PASSWORD = os.getenv('DB_PASSWORD','')

def get_pg_conn():
    """Connect to PostgreSQL almsdata"""
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_NAME, user=PG_USER, password=PG_PASSWORD)

def build_customer_resolution_indexes():
    """Build quick lookup maps for resolving customer from email/name.
    Returns: (email_to_client_id, name_to_client_id, client_id_to_account)
    """
    email_to_client = {}
    name_to_client = {}
    client_to_account = {}
    with get_pg_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Clients: primary email/name
            cur.execute("""
                SELECT client_id, LOWER(TRIM(email)) AS email, LOWER(TRIM(client_name)) AS name,
                       account_number
                FROM clients
            """)
            for row in cur.fetchall():
                if row['email']:
                    email_to_client[row['email']] = row['client_id']
                if row['name']:
                    name_to_client[row['name']] = row['client_id']
                client_to_account[row['client_id']] = row['account_number']
            # Resolver: resolved email/name → client
            cur.execute("""
                SELECT alms_client_id AS client_id,
                       LOWER(TRIM(resolved_email)) AS email,
                       LOWER(TRIM(resolved_name)) AS name
                FROM customer_name_resolver
                WHERE alms_client_id IS NOT NULL
            """)
            for row in cur.fetchall():
                if row['email'] and row['email'] not in email_to_client:
                    email_to_client[row['email']] = row['client_id']
                if row['name'] and row['name'] not in name_to_client:
                    name_to_client[row['name']] = row['client_id']
            # Name mapping: LMS→ALMS
            cur.execute("""
                SELECT alms_client_id AS client_id,
                       LOWER(TRIM(COALESCE(lms_primary_name, lms_company_name))) AS name
                FROM customer_name_mapping
                WHERE alms_client_id IS NOT NULL
            """)
            for row in cur.fetchall():
                if row['name'] and row['name'] not in name_to_client:
                    name_to_client[row['name']] = row['client_id']
    return email_to_client, name_to_client, client_to_account

def find_best_charter_for_client(client_id, payment_amount, payment_date):
    """Find the most plausible charter for a client around a payment date.
    Prefers charters within [-60, +120] days with amount close to payment.
    Returns (charter_id, reserve_number, method, score) or (None, None, None, 0)
    """
    with get_pg_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT charter_id, reserve_number, charter_date,
                       COALESCE(total_amount_due, rate, 0) AS amount,
                       COALESCE(balance, 0) AS balance,
                       COALESCE(deposit, 0) AS deposit
                FROM charters
                WHERE client_id = %s
                  AND charter_date BETWEEN %s::date - INTERVAL '60 days' AND %s::date + INTERVAL '120 days'
                ORDER BY charter_date DESC
                LIMIT 200
                """,
                (client_id, payment_date, payment_date),
            )
            candidates = cur.fetchall()
            best = (None, None, None, 0.0)
            if not candidates:
                return best
            for c in candidates:
                amount = float(c['amount'] or 0)
                bal = float(c['balance'] or 0)
                dep = float(c['deposit'] or 0)
                # Compute closeness to total amount and to outstanding balance
                diffs = []
                if amount > 0:
                    diffs.append((abs(amount - payment_amount) / max(amount, 1.0), 'total_amount'))
                if bal > 0:
                    diffs.append((abs(bal - payment_amount) / max(bal, 1.0), 'balance'))
                if dep > 0:
                    diffs.append((abs(dep - payment_amount) / max(dep, 1.0), 'deposit'))
                if not diffs:
                    continue
                rel_diff, basis = min(diffs, key=lambda x: x[0])
                # Date proximity weighting
                days_apart = abs((c['charter_date'] - payment_date).days)
                # Score: inverse of relative diff, penalized by days apart
                score = max(0.0, 1.0 - rel_diff) * 1.0 / (1.0 + days_apart / 30.0)
                # Track best
                if score > best[3]:
                    best = (c['charter_id'], c['reserve_number'], f"{basis} proximity", score)
            return best

def build_last4_index():
    """Build a map client_id -> set of last4 values seen in historical payments (square_last4 and credit_card_last4)."""
    m = {}
    with get_pg_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT client_id,
                       NULLIF(TRIM(LOWER(square_last4)), '') AS s4,
                       NULLIF(TRIM(LOWER(credit_card_last4)), '') AS c4
                FROM payments
                WHERE client_id IS NOT NULL
                """
            )
            for row in cur.fetchall():
                cid = row['client_id']
                if not cid:
                    continue
                s = m.setdefault(cid, set())
                if row['s4']:
                    s.add(row['s4'])
                if row['c4']:
                    s.add(row['c4'])
    return m

def get_unmatched_square_payments():
    """Get all Square payments without charter links"""
    print("Fetching unmatched Square payments...")
    with get_pg_conn() as pg_conn:
        with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT payment_id, payment_date, amount, payment_key, notes,
                       square_payment_id, square_customer_name, square_customer_email, square_last4
                FROM payments
                WHERE square_payment_id IS NOT NULL
                  AND charter_id IS NULL
                ORDER BY payment_date DESC
            """)
            return cur.fetchall()

def get_lms_unified_data():
    """Get unified LMS mapping data from Postgres"""
    print("Fetching LMS unified mapping data...")
    with get_pg_conn() as pg_conn:
        with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT payment_id, reserve_no, payment_amount, payment_date_text,
                       deposit_key, number as deposit_number, deposit_total, deposit_date,
                       payment_method, payment_key
                FROM lms_unified_map
                ORDER BY payment_id
            """)
            return cur.fetchall()

def get_lms_deposits():
    """Get LMS deposits from Postgres"""
    print("Fetching LMS deposits...")
    with get_pg_conn() as pg_conn:
        with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT dep_key as deposit_key, number as deposit_number, 
                       total as deposit_total, dep_date as deposit_date, 
                       type as deposit_type, transact
                FROM lms_deposits
                ORDER BY dep_date DESC
            """)
            return cur.fetchall()

def get_lms_reserves():
    """Get LMS reserves from Postgres"""
    print("Fetching LMS reserves...")
    with get_pg_conn() as pg_conn:
        with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT reserve_no, pu_date_text as pu_date, rate, balance, deposit, 
                       status, pymt_type
                FROM lms_reserves
                ORDER BY reserve_no
            """)
            return cur.fetchall()

def get_lms_charges():
    """Get LMS charges from Postgres"""
    print("Fetching LMS charges...")
    with get_pg_conn() as pg_conn:
        with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT charge_id, reserve_no, account_no, amount, description,
                       rate, sequence, last_updated
                FROM lms_charges
                WHERE amount > 0
                ORDER BY reserve_no, charge_id
            """)
            return cur.fetchall()

def get_cibc_banking_transactions():
    """Get CIBC banking transactions for date validation"""
    print("Fetching CIBC banking transactions...")
    with get_pg_conn() as pg_conn:
        with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT transaction_id, transaction_date, 
                       COALESCE(credit_amount, 0) - COALESCE(debit_amount, 0) as amount,
                       description, account_number
                FROM banking_transactions
                WHERE description ILIKE '%square%'
                OR description ILIKE '%electronic funds transfer%'
                ORDER BY transaction_date DESC
            """)
            return cur.fetchall()

def load_retainer_mapping(file_path):
    """Load retainer mapping CSV if provided"""
    if not file_path or not os.path.exists(file_path):
        return {}
    
    print(f"Loading retainer mapping from {file_path}...")
    mapping = {'by_key': {}, 'by_paymentid': {}}
    
    try:
        with open(file_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Map by deposit key
                if 'Key' in row and 'Reserve_No' in row:
                    key = row['Key'].strip() if row['Key'] else None
                    reserve_no = row['Reserve_No'].strip() if row['Reserve_No'] else None
                    if key and reserve_no:
                        mapping['by_key'][key] = reserve_no
                
                # Map by payment ID  
                if 'PaymentID' in row and 'Reserve_No' in row:
                    payment_id = row['PaymentID'].strip() if row['PaymentID'] else None
                    reserve_no = row['Reserve_No'].strip() if row['Reserve_No'] else None
                    if payment_id and reserve_no:
                        mapping['by_paymentid'][payment_id] = reserve_no
        
        print(f"Loaded mapping: {len(mapping['by_key'])} by key, {len(mapping['by_paymentid'])} by payment ID")
        return mapping
    except Exception as e:
        print(f"Error loading retainer mapping: {e}")
        return {}

def match_square_to_lms_comprehensive(square_payments, unified_data, lms_deposits, lms_reserves, lms_charges, cibc_transactions, retainer_map=None):
    """
    Comprehensive matching using Postgres LMS tables
    """
    print("Starting comprehensive matching...")
    
    # Create efficient lookups
    unified_by_deposit_key = {u['deposit_key']: u for u in unified_data if u['deposit_key']}
    unified_by_payment_id = {u['payment_id']: u for u in unified_data if u['payment_id']}
    
    deposit_by_amount = {}
    deposit_by_amount_date = {}
    for deposit in lms_deposits:
        amount = round(float(deposit['deposit_total'] or 0), 2)
        ddate = deposit.get('deposit_date')
        
        # Normalize date
        if isinstance(ddate, str):
            try:
                ddate_key = datetime.strptime(ddate, '%Y-%m-%d').date()
            except Exception:
                ddate_key = None
        elif hasattr(ddate, 'date'):
            ddate_key = ddate.date()
        else:
            ddate_key = ddate

        if amount > 0:
            deposit_list = deposit_by_amount.setdefault(amount, [])
            deposit_list.append(deposit)

            if ddate_key is not None:
                key = (amount, ddate_key)
                deposit_by_amount_date.setdefault(key, []).append(deposit)
    
    reserve_lookup = {r['reserve_no']: r for r in lms_reserves if r['reserve_no']}
    
    # Create charge amount lookups
    charges_by_reserve = {}
    for charge in lms_charges:
        reserve_no = charge['reserve_no']
        if reserve_no:
            charges_by_reserve.setdefault(reserve_no, []).append(charge)
    
    # Create CIBC date lookup for fast validation
    cibc_by_date = {}
    for txn in cibc_transactions:
        txn_date = txn['transaction_date'].date() if hasattr(txn['transaction_date'], 'date') else txn['transaction_date']
        cibc_by_date.setdefault(txn_date, []).append(txn)
    
    matches = []
    # Build customer lookup once
    email_to_client, name_to_client, client_to_account = build_customer_resolution_indexes()
    client_last4_index = build_last4_index()
    
    
    for payment in square_payments:
        payment_amount = round(float(payment['amount'] or 0), 2)
        payment_date = payment['payment_date'].date() if hasattr(payment['payment_date'], 'date') else payment['payment_date']
        
        # Try multiple matching strategies
        match_found = False
        confidence = 0
        match_method = ""
        reserve_number = None
        cibc_validated = False
        resolved_client_id = None
        
        # Strategy 1: Retainer exact date+amount match (highest priority for $205/$500)
        if payment_amount in [205.0, 500.0] and not match_found:
            exact_key = (payment_amount, payment_date)
            if exact_key in deposit_by_amount_date:
                matching_deposits = deposit_by_amount_date[exact_key]
                for deposit in matching_deposits:
                    # Try unified mapping first
                    unified = unified_by_deposit_key.get(deposit['deposit_key'])
                    if unified and unified['reserve_no']:
                        reserve_number = unified['reserve_no']
                        confidence = 5  # High confidence for exact retainer match
                        match_method = f"Retainer exact date+amount via unified map"
                        match_found = True
                        break
                    
                    # Try retainer mapping if provided
                    if retainer_map and deposit['deposit_key'] in retainer_map['by_key']:
                        reserve_number = retainer_map['by_key'][deposit['deposit_key']]
                        confidence = 5
                        match_method = f"Retainer exact date+amount via mapping CSV"
                        match_found = True
                        break
        
        # Strategy 2: Retainer approximate date match (±7 days for $205/$500)
        if payment_amount in [205.0, 500.0] and not match_found:
            for days_offset in range(-7, 8):
                check_date = payment_date + timedelta(days=days_offset)
                approx_key = (payment_amount, check_date)
                if approx_key in deposit_by_amount_date:
                    matching_deposits = deposit_by_amount_date[approx_key]
                    for deposit in matching_deposits:
                        # Try unified mapping
                        unified = unified_by_deposit_key.get(deposit['deposit_key'])
                        if unified and unified['reserve_no']:
                            reserve_number = unified['reserve_no']
                            confidence = 4
                            match_method = f"Retainer ±{abs(days_offset)} days via unified map"
                            match_found = True
                            break
                        
                        # Try retainer mapping
                        if retainer_map and deposit['deposit_key'] in retainer_map['by_key']:
                            reserve_number = retainer_map['by_key'][deposit['deposit_key']]
                            confidence = 4
                            match_method = f"Retainer ±{abs(days_offset)} days via mapping CSV"
                            match_found = True
                            break
                    if match_found:
                        break
        
        # Strategy 3: Waste Connections $774 rule (extended date tolerance)
        if payment_amount == 774.0 and not match_found:
            for days_offset in range(-14, 15):  # Extended range for Waste Connections
                check_date = payment_date + timedelta(days=days_offset)
                approx_key = (payment_amount, check_date)
                if approx_key in deposit_by_amount_date:
                    matching_deposits = deposit_by_amount_date[approx_key]
                    for deposit in matching_deposits:
                        unified = unified_by_deposit_key.get(deposit['deposit_key'])
                        if unified and unified['reserve_no']:
                            reserve_number = unified['reserve_no']
                            confidence = 4
                            match_method = f"Waste Connections $774 ±{abs(days_offset)} days"
                            match_found = True
                            break
                    if match_found:
                        break
        
        # Strategy 4: General amount match with deposit
        if not match_found and payment_amount in deposit_by_amount:
            matching_deposits = deposit_by_amount[payment_amount]
            for deposit in matching_deposits:
                unified = unified_by_deposit_key.get(deposit['deposit_key'])
                if unified and unified['reserve_no']:
                    reserve_number = unified['reserve_no']
                    confidence = 3
                    match_method = f"Amount match via unified map"
                    match_found = True
                    break
        
        # Strategy 4.5: Name/Email-based client resolution → best charter by amount/date
        if not match_found:
            sq_email = (payment.get('square_customer_email') or '').strip().lower()
            sq_name = (payment.get('square_customer_name') or '').strip().lower()
            sq_last4 = (payment.get('square_last4') or '').strip().lower()
            client_id = None
            method_extra = None
            if sq_email and sq_email in email_to_client:
                client_id = email_to_client[sq_email]
                method_extra = 'email'
            elif sq_name and sq_name in name_to_client:
                client_id = name_to_client[sq_name]
                method_extra = 'name'
            if client_id:
                resolved_client_id = client_id
                best_charter_id, best_reserve, basis, score = find_best_charter_for_client(client_id, payment_amount, payment_date)
                if best_charter_id and best_reserve:
                    reserve_number = best_reserve
                    # Confidence based on method and score
                    if method_extra == 'email' and score >= 0.85:
                        confidence = 5
                    elif method_extra == 'email' and score >= 0.75:
                        confidence = 4
                    elif score >= 0.75:
                        confidence = 3
                    else:
                        confidence = 2
                    # Boost with last4 corroboration where available
                    if sq_last4 and client_last4_index.get(client_id) and sq_last4 in client_last4_index[client_id]:
                        confidence = max(confidence, 4)
                    match_method = f"Name-based ({method_extra}); {basis} match"
                    match_found = True

        # Strategy 5: Direct reserve amount matches
        if not match_found:
            for reserve in lms_reserves:
                # Check various amount fields
                amounts_to_check = []
                if reserve['rate']: amounts_to_check.append(('rate', round(float(reserve['rate']), 2)))
                if reserve['balance']: amounts_to_check.append(('balance', round(float(reserve['balance']), 2)))
                if reserve['deposit']: amounts_to_check.append(('deposit', round(float(reserve['deposit']), 2)))
                
                for field_name, reserve_amount in amounts_to_check:
                    if abs(reserve_amount - payment_amount) < 0.01:  # Exact match
                        reserve_number = reserve['reserve_no']
                        confidence = 2
                        match_method = f"Direct reserve {field_name} match"
                        match_found = True
                        break
                    elif payment_amount > 0 and abs(reserve_amount - payment_amount) / payment_amount <= 0.05:  # 5% tolerance
                        reserve_number = reserve['reserve_no']
                        confidence = 1
                        match_method = f"Direct reserve {field_name} ~5% match"
                        match_found = True
                        break
                
                if match_found:
                    break
        
        # CIBC Validation - check if there's a matching banking transaction within ±4 days
        if match_found:
            for days_offset in range(-4, 5):
                check_date = payment_date + timedelta(days=days_offset)
                if check_date in cibc_by_date:
                    for cibc_txn in cibc_by_date[check_date]:
                        cibc_amount = float(cibc_txn['amount'])
                        if abs(cibc_amount - payment_amount) < 0.01:
                            cibc_validated = True
                            confidence += 1  # Boost confidence for CIBC validation
                            break
                if cibc_validated:
                    break
        
        # Record the match (even if not found for reporting)
        matches.append({
            'payment_id': payment['payment_id'],
            'square_payment_id': payment['square_payment_id'],
            'payment_amount': payment_amount,
            'payment_date': payment_date,
            'reserve_number': reserve_number,
            'confidence': confidence,
            'match_method': match_method if match_found else "No match found",
            'cibc_validated': cibc_validated,
            'client_id': resolved_client_id
        })
    
    print(f"Matching completed. Found {len([m for m in matches if m['reserve_number']])} matches out of {len(matches)} payments")
    return matches

def apply_matches(matches, min_confidence=3):
    """Apply high-confidence matches to the database"""
    print(f"Applying matches with confidence >= {min_confidence}...")
    to_apply = [m for m in matches if m['confidence'] >= min_confidence and m['reserve_number']]
    if not to_apply:
        print("No matches to apply at this threshold")
        return 0
    applied_count = 0
    with get_pg_conn() as pg_conn:
        with pg_conn.cursor() as cur:
            for match in to_apply:
                try:
                    # Find charter_id by reserve_number
                    cur.execute("""
                        SELECT charter_id FROM charters 
                        WHERE reserve_number = %s 
                        LIMIT 1
                    """, (match['reserve_number'],))
                    
                    charter_result = cur.fetchone()
                    if charter_result:
                        charter_id = charter_result[0]
                        
                        # Update the payment
                        cur.execute("""
                            UPDATE payments 
                            SET charter_id = %s,
                                notes = COALESCE(notes, '') || %s
                            WHERE payment_id = %s
                        """, (
                            charter_id,
                            f" [AUTO-MATCHED: {match['match_method']}, confidence {match['confidence']}]",
                            match['payment_id']
                        ))
                        
                        applied_count += 1
                        print(f"Applied: Payment {match['payment_id']} → Charter {charter_id} (Reserve {match['reserve_number']})")
                    else:
                        print(f"Warning: No charter found for reserve {match['reserve_number']}")
                        
                except Exception as e:
                    print(f"Error applying match for payment {match['payment_id']}: {e}")
        
        pg_conn.commit()
    
    print(f"Successfully applied {applied_count} matches")
    return applied_count

def save_matches_report(matches, filename=None):
    """Save matches to CSV report"""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"l:/limo/reports/square_lms_matches_postgres_{timestamp}.csv"
    
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    print(f"Saving matches report to {filename}")
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['payment_id', 'square_payment_id', 'payment_amount', 'payment_date', 
                     'reserve_number', 'confidence', 'match_method', 'cibc_validated', 'client_id']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(matches)
    
    # Print summary statistics
    total_matches = len(matches)
    found_matches = len([m for m in matches if m['reserve_number']])
    high_confidence = len([m for m in matches if m['confidence'] >= 4])
    cibc_validated = len([m for m in matches if m['cibc_validated']])
    
    print(f"\nMatch Summary:")
    print(f"Total payments: {total_matches}")
    print(f"Matches found: {found_matches}")
    print(f"High confidence (>=4): {high_confidence}")
    print(f"CIBC validated: {cibc_validated}")
    
    return filename

def main():
    parser = argparse.ArgumentParser(description='Match Square payments to LMS charters using Postgres')
    parser.add_argument('--min-confidence', type=int, default=4, help='Minimum confidence to auto-apply matches')
    parser.add_argument('--apply', action='store_true', help='Apply high-confidence matches to database')
    parser.add_argument('--retainer-map', help='Path to retainer mapping CSV file')
    parser.add_argument('--report-only', action='store_true', help='Generate report only, do not apply matches')
    
    args = parser.parse_args()
    
    try:
        # Load data
        print("Loading data from Postgres...")
        square_payments = get_unmatched_square_payments()
        unified_data = get_lms_unified_data()
        lms_deposits = get_lms_deposits()
        lms_reserves = get_lms_reserves()
        lms_charges = get_lms_charges()
        cibc_transactions = get_cibc_banking_transactions()
        
        # Load retainer mapping if provided
        retainer_map = load_retainer_mapping(args.retainer_map) if args.retainer_map else None
        
        print(f"Data loaded:")
        print(f"  Square payments: {len(square_payments)}")
        print(f"  LMS unified records: {len(unified_data)}")
        print(f"  LMS deposits: {len(lms_deposits)}")
        print(f"  LMS reserves: {len(lms_reserves)}")
        print(f"  LMS charges: {len(lms_charges)}")
        print(f"  CIBC transactions: {len(cibc_transactions)}")
        
        # Perform matching
        matches = match_square_to_lms_comprehensive(
            square_payments, unified_data, lms_deposits, lms_reserves, 
            lms_charges, cibc_transactions, retainer_map
        )
        
        # Save report
        report_file = save_matches_report(matches)
        
        # Apply matches if requested
        applied_count = 0
        if args.apply and not args.report_only:
            # Lower threshold to 3 for auto-apply
            applied_count = apply_matches(matches, min_confidence=3)
        elif not args.report_only:
            high_confidence = len([m for m in matches if m['confidence'] >= 3 and m['reserve_number']])
            print(f"\nFound {high_confidence} matches with confidence >=3 (use --apply to apply them)")
        
        print(f"\nCompleted! Report saved to: {report_file}")
        if applied_count > 0:
            print(f"Applied {applied_count} matches to database")
            
    except Exception as e:
        print(f"Error: {e}")
        raise

if __name__ == "__main__":
    main()