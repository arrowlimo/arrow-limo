#!/usr/bin/env python3
"""
Comprehensive Square Payment to LMS Matcher

Matching Logic:
1. Square payment amount → LMS Deposit by amount (exact match)
2. LMS Deposit → Charter (by deposit relationship)
3. Charter → Reserve (by reserve_number)
4. Validate CIBC banking date within 4 days (workweek timing)
5. Link Square payment to charter via reserve_number

This follows the actual payment relationship flow through the LMS system.
"""
import os
import csv
import pyodbc
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

# LMS Access ODBC connection
LMS_PATH = r"L:\limo\lms.mdb"

def get_lms_conn():
    """Connect to LMS Access database via ODBC"""
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)

def get_pg_conn():
    """Connect to PostgreSQL almsdata"""
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_NAME, user=PG_USER, password=PG_PASSWORD)

def get_unmatched_square_payments():
    """Get all Square payments without charter links"""
    print("Fetching unmatched Square payments...")
    with get_pg_conn() as pg_conn:
        with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT payment_id, payment_date, amount, payment_key, notes, square_payment_id
                FROM payments
                WHERE square_payment_id IS NOT NULL
                  AND charter_id IS NULL
                ORDER BY payment_date DESC
            """)
            return cur.fetchall()

def get_lms_deposits():
    """Get LMS deposits from MS Access"""
    print("Fetching LMS deposits...")
    rows = []
    with get_lms_conn() as conn:
        cur = conn.cursor()
        # Use brackets for Access reserved words
        cur.execute("SELECT [Key], [Number], [Total], [Date], [Type], [Transact] FROM Deposit")
        for row in cur.fetchall():
            rows.append({
                'key': row[0],
                'number': row[1],
                'total': float(row[2]) if row[2] is not None else 0.0,
                'date': row[3],
                'type': row[4],
                'transact': row[5],
            })
    return rows

def get_lms_reserves():
    """Get LMS reserves from MS Access"""
    print("Fetching LMS reserves...")
    reserves = []
    with get_lms_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT Reserve_No, Account_No, PU_Date, Rate, Balance, Deposit, Status, Pymt_Type
            FROM Reserve
        """)
        for row in cur.fetchall():
            reserves.append({
                'reserve_number': row[0],
                'account_number': row[1],
                'pu_date': row[2],
                'rate': float(row[3]) if row[3] is not None else 0.0,
                'balance': float(row[4]) if row[4] is not None else 0.0,
                'deposit': float(row[5]) if row[5] is not None else 0.0,
                'status': row[6],
                'pymt_type': row[7],
            })
    return reserves

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

def match_square_to_lms_comprehensive(square_payments, lms_deposits, lms_reserves, cibc_transactions, retainer_map=None):
    """
    Comprehensive matching following the flow:
    Square → LMS Deposit → Reserve → CIBC validation
    """
    print("Starting comprehensive matching...")
    
    # Create more efficient lookups
    deposit_by_amount = {}
    deposit_by_amount_date = {}
    for deposit in lms_deposits:
        amount = round(deposit['total'], 2)  # Round to avoid floating point issues
        # Normalize deposit date to date for exact date+amount matching
        ddate = deposit.get('date')
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
    
    reserve_lookup = {r['reserve_number']: r for r in lms_reserves if r['reserve_number']}
    
    # Create reserve amount lookups for faster searching
    reserve_by_rate = {}
    reserve_by_balance = {}
    reserve_by_deposit = {}
    
    for reserve in lms_reserves:
        for amount_type, amount_dict in [
            ('rate', reserve_by_rate),
            ('balance', reserve_by_balance), 
            ('deposit', reserve_by_deposit)
        ]:
            amount = round(reserve[amount_type], 2) if reserve[amount_type] else 0
            if amount > 0:
                if amount not in amount_dict:
                    amount_dict[amount] = []
                amount_dict[amount].append(reserve)
    
    # CIBC date lookup
    cibc_by_date = {}
    for txn in cibc_transactions:
        date_key = txn['transaction_date'].date() if hasattr(txn['transaction_date'], 'date') else txn['transaction_date']
        if date_key not in cibc_by_date:
            cibc_by_date[date_key] = []
        cibc_by_date[date_key].append(txn)
    
    matches = []
    processed_squares = set()  # Prevent duplicate matches for same Square payment
    
    for square_payment in square_payments:
        if square_payment['payment_id'] in processed_squares:
            continue
            
        if square_payment['amount'] is None:
            continue  # Skip payments with null amounts
        square_amount = round(float(square_payment['amount']), 2)
        square_date = square_payment['payment_date'].date() if hasattr(square_payment['payment_date'], 'date') else square_payment['payment_date']
        
        best_match = None
        best_confidence = 0

        # Retainer matching rules for $205/$500 payments
        # Priority 1: Exact amount + exact date match using deposit_by_amount_date
        if square_amount in (205.00, 500.00) and square_date:
            # 0) If mapping provides direct PaymentID -> Reserve_No, use it immediately
            if retainer_map and square_payment.get('square_payment_id'):
                by_pid = retainer_map.get('by_paymentid') if isinstance(retainer_map, dict) else None
                reserve_no_direct = by_pid.get(str(square_payment['square_payment_id'])) if by_pid else None
                if reserve_no_direct and reserve_no_direct in reserve_lookup:
                    reserve = reserve_lookup[reserve_no_direct]
                    confidence = 5
                    best_match = {
                        'square_payment_id': square_payment['payment_id'],
                        'square_amount': square_amount,
                        'square_date': square_date,
                        'square_key': square_payment['payment_key'],
                        'lms_deposit_key': None,
                        'lms_deposit_total': None,
                        'lms_deposit_date': None,
                        'reserve_number': reserve['reserve_number'],
                        'reserve_rate': reserve['rate'],
                        'reserve_balance': reserve['balance'],
                        'reserve_date': reserve['pu_date'],
                        'cibc_match': False,
                        'cibc_transaction_id': None,
                        'cibc_date': None,
                        'confidence': confidence,
                        'match_method': f"Retainer direct map by PaymentID: ${square_amount}, Reserve={reserve['reserve_number']}"
                    }
                    best_confidence = confidence
                    matches.append(best_match)
                    processed_squares.add(square_payment['payment_id'])
                    continue

            exact_deps = deposit_by_amount_date.get((square_amount, square_date), [])
            for deposit in exact_deps:
                # Determine reserve number via mapping or direct key link
                reserve_no = None
                if retainer_map:
                    k = deposit.get('key')
                    by_key = retainer_map.get('by_key') if isinstance(retainer_map, dict) else None
                    # Try multiple key forms to be robust
                    reserve_no = (
                        (by_key.get(k) if by_key else None) or
                        (by_key.get(str(k)) if by_key else None) or
                        ((by_key.get(int(k)) if isinstance(k, str) and k.isdigit() else None) if by_key else None)
                    )
                if not reserve_no:
                    # Fallback to deposit Number being the reserve number
                    num = deposit.get('number')
                    if num in reserve_lookup:
                        reserve_no = num

                if reserve_no:
                    reserve = reserve_lookup.get(reserve_no)
                else:
                    reserve = None

                if reserve:
                    confidence = 5  # Highest confidence for exact date+amount retainer
                    best_match = {
                        'square_payment_id': square_payment['payment_id'],
                        'square_amount': square_amount,
                        'square_date': square_date,
                        'square_key': square_payment['payment_key'],
                        'lms_deposit_key': deposit['key'],
                        'lms_deposit_total': deposit['total'],
                        'lms_deposit_date': square_date,
                        'reserve_number': reserve['reserve_number'],
                        'reserve_rate': reserve['rate'],
                        'reserve_balance': reserve['balance'],
                        'reserve_date': reserve['pu_date'],
                        'cibc_match': False,
                        'cibc_transaction_id': None,
                        'cibc_date': None,
                        'confidence': confidence,
                        'match_method': f"Retainer exact date+amount: ${square_amount} on {square_date}, Reserve={reserve['reserve_number']}"
                    }
                    best_confidence = confidence
                    break

            # Priority 2: If no exact date, try within ±7 days of Square payment date
            if not best_match:
                for deposit in deposit_by_amount.get(square_amount, []):
                    deposit_date = deposit['date']
                    if isinstance(deposit_date, str):
                        try:
                            deposit_date = datetime.strptime(deposit_date, '%Y-%m-%d').date()
                        except Exception:
                            deposit_date = None
                    elif hasattr(deposit_date, 'date'):
                        deposit_date = deposit_date.date()

                    if square_date and deposit_date:
                        date_diff = abs((square_date - deposit_date).days)
                        if date_diff <= 7:
                            reserve_no = None
                            if retainer_map:
                                k = deposit.get('key')
                                by_key = retainer_map.get('by_key') if isinstance(retainer_map, dict) else None
                                reserve_no = (
                                    (by_key.get(k) if by_key else None) or
                                    (by_key.get(str(k)) if by_key else None) or
                                    ((by_key.get(int(k)) if isinstance(k, str) and k.isdigit() else None) if by_key else None)
                                )
                            if not reserve_no:
                                num = deposit.get('number')
                                if num in reserve_lookup:
                                    reserve_no = num

                            reserve = reserve_lookup.get(reserve_no) if reserve_no else None
                            if reserve:
                                confidence = 4
                                best_match = {
                                    'square_payment_id': square_payment['payment_id'],
                                    'square_amount': square_amount,
                                    'square_date': square_date,
                                    'square_key': square_payment['payment_key'],
                                    'lms_deposit_key': deposit['key'],
                                    'lms_deposit_total': deposit['total'],
                                    'lms_deposit_date': deposit_date,
                                    'reserve_number': reserve['reserve_number'],
                                    'reserve_rate': reserve['rate'],
                                    'reserve_balance': reserve['balance'],
                                    'reserve_date': reserve['pu_date'],
                                    'cibc_match': False,
                                    'cibc_transaction_id': None,
                                    'cibc_date': None,
                                    'confidence': confidence,
                                    'match_method': f"Retainer ±7d: ${square_amount} on {deposit_date}, Reserve={reserve['reserve_number']}"
                                }
                                best_confidence = confidence
                                break
        
        # Step 1: If no retainer match found, find matching LMS deposits by exact amount
        matching_deposits = []
        if not best_match:
            matching_deposits = deposit_by_amount.get(square_amount, [])
        
        for deposit in matching_deposits:
            # Step 2: Connect deposit to reserve via direct key or mapping (most reliable)
            reserve = None
            # Prefer explicit mapping if provided
            if retainer_map:
                k = deposit.get('key')
                by_key = retainer_map.get('by_key') if isinstance(retainer_map, dict) else None
                reserve_no = (
                    (by_key.get(k) if by_key else None) or
                    (by_key.get(str(k)) if by_key else None) or
                    ((by_key.get(int(k)) if isinstance(k, str) and k.isdigit() else None) if by_key else None)
                )
                if reserve_no:
                    reserve = reserve_lookup.get(reserve_no)
            # Fallback: use deposit Number as reserve number when present
            if reserve is None:
                num = deposit.get('number')
                if num in reserve_lookup:
                    reserve = reserve_lookup[num]
            # If still not found, skip
            if reserve is None:
                continue
                
                confidence = 3  # Base confidence for deposit->reserve link
                
                # Add date proximity bonus
                deposit_date = deposit['date']
                reserve_date = reserve['pu_date']
                
                if isinstance(deposit_date, str):
                    try:
                        deposit_date = datetime.strptime(deposit_date, '%Y-%m-%d').date()
                    except:
                        deposit_date = None
                elif hasattr(deposit_date, 'date'):
                    deposit_date = deposit_date.date()
                
                if isinstance(reserve_date, str):
                    try:
                        reserve_date = datetime.strptime(reserve_date, '%Y-%m-%d').date()
                    except:
                        reserve_date = None
                elif hasattr(reserve_date, 'date'):
                    reserve_date = reserve_date.date()
                
                if deposit_date and reserve_date:
                    date_diff = abs((deposit_date - reserve_date).days)
                    if date_diff <= 1:
                        confidence += 2
                    elif date_diff <= 7:
                        confidence += 1
                
                # Step 3: CIBC banking validation
                cibc_match = False
                cibc_details = None
                
                if square_date:
                    for i in range(-4, 5):  # Check ±4 days
                        check_date = square_date + timedelta(days=i)
                        if check_date in cibc_by_date:
                            for cibc_txn in cibc_by_date[check_date]:
                                if abs(float(cibc_txn['amount']) - square_amount) < 0.01:
                                    cibc_match = True
                                    cibc_details = cibc_txn
                                    confidence += 2
                                    break
                        if cibc_match:
                            break
                
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = {
                        'square_payment_id': square_payment['payment_id'],
                        'square_amount': square_amount,
                        'square_date': square_date,
                        'square_key': square_payment['payment_key'],
                        'lms_deposit_key': deposit['key'],
                        'lms_deposit_total': deposit['total'],
                        'lms_deposit_date': deposit_date,
                        'reserve_number': reserve['reserve_number'],
                        'reserve_rate': reserve['rate'],
                        'reserve_balance': reserve['balance'],
                        'reserve_date': reserve_date,
                        'cibc_match': cibc_match,
                        'cibc_transaction_id': cibc_details['transaction_id'] if cibc_details else None,
                        'cibc_date': cibc_details['transaction_date'] if cibc_details else None,
                        'confidence': confidence,
                        'match_method': f"Deposit key link: Amount={square_amount}, Deposit={deposit['key']}, Reserve={reserve['reserve_number']}"
                    }
        
        # Special case: $774.00 amounts are Waste Connections charters
        if square_amount == 774.00:
            # Look for any reserve with $774 in deposit amount (broader date range)
            matching_reserves = reserve_by_deposit.get(774.00, [])
            for reserve in matching_reserves:
                confidence = 4  # High confidence for known pattern
                
                reserve_date = reserve['pu_date']
                if isinstance(reserve_date, str):
                    try:
                        reserve_date = datetime.strptime(reserve_date, '%Y-%m-%d').date()
                    except:
                        reserve_date = None
                elif hasattr(reserve_date, 'date'):
                    reserve_date = reserve_date.date()
                
                # More lenient date matching for Waste Connections
                if square_date and reserve_date:
                    date_diff = abs((square_date - reserve_date).days)
                    if date_diff <= 180:  # 6 months tolerance for Waste Connections
                        confidence += 1
                
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = {
                        'square_payment_id': square_payment['payment_id'],
                        'square_amount': square_amount,
                        'square_date': square_date,
                        'square_key': square_payment['payment_key'],
                        'lms_deposit_key': None,
                        'lms_deposit_total': None,
                        'lms_deposit_date': None,
                        'reserve_number': reserve['reserve_number'],
                        'reserve_rate': reserve['rate'],
                        'reserve_balance': reserve['balance'],
                        'reserve_date': reserve_date,
                        'cibc_match': False,
                        'cibc_transaction_id': None,
                        'cibc_date': None,
                        'confidence': confidence,
                        'match_method': f"Waste Connections $774 pattern: Reserve={reserve['reserve_number']}"
                    }

        # If no deposit->reserve link found, try direct amount matching to reserves
        if not best_match or best_confidence < 3:
            for amount_type, reserve_dict in [
                ('rate', reserve_by_rate),
                ('balance', reserve_by_balance),
                ('deposit', reserve_by_deposit)
            ]:
                matching_reserves = reserve_dict.get(square_amount, [])
                
                for reserve in matching_reserves:
                    confidence = 2  # Lower confidence for direct amount match
                    
                    # Date proximity with Square payment - more lenient for exact matches
                    reserve_date = reserve['pu_date']
                    if isinstance(reserve_date, str):
                        try:
                            reserve_date = datetime.strptime(reserve_date, '%Y-%m-%d').date()
                        except:
                            reserve_date = None
                    elif hasattr(reserve_date, 'date'):
                        reserve_date = reserve_date.date()
                    
                    if square_date and reserve_date:
                        date_diff = abs((square_date - reserve_date).days)
                        if date_diff <= 7:
                            confidence += 2  # Same week
                        elif date_diff <= 30:
                            confidence += 1   # Same month
                        elif date_diff <= 90:
                            confidence += 0.5 # Same quarter (for exact amounts)
                    
                    # CIBC validation
                    cibc_match = False
                    cibc_details = None
                    
                    if square_date:
                        for i in range(-4, 5):
                            check_date = square_date + timedelta(days=i)
                            if check_date in cibc_by_date:
                                for cibc_txn in cibc_by_date[check_date]:
                                    if abs(float(cibc_txn['amount']) - square_amount) < 0.01:
                                        cibc_match = True
                                        cibc_details = cibc_txn
                                        confidence += 1
                                        break
                            if cibc_match:
                                break
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = {
                            'square_payment_id': square_payment['payment_id'],
                            'square_amount': square_amount,
                            'square_date': square_date,
                            'square_key': square_payment['payment_key'],
                            'lms_deposit_key': None,
                            'lms_deposit_total': None,
                            'lms_deposit_date': None,
                            'reserve_number': reserve['reserve_number'],
                            'reserve_rate': reserve['rate'],
                            'reserve_balance': reserve['balance'],
                            'reserve_date': reserve_date,
                            'cibc_match': cibc_match,
                            'cibc_transaction_id': cibc_details['transaction_id'] if cibc_details else None,
                            'cibc_date': cibc_details['transaction_date'] if cibc_details else None,
                            'confidence': confidence,
                            'match_method': f"Direct {amount_type} match: Amount={square_amount}, Reserve={reserve['reserve_number']}"
                        }
        
        # If still no good match, try percentage-based tolerance (±5%)
        if not best_match or best_confidence < 2.5:
            tolerance = square_amount * 0.05  # 5% tolerance
            
            for reserve in lms_reserves:
                for field, value in [('rate', reserve['rate']), ('balance', reserve['balance']), ('deposit', reserve['deposit'])]:
                    if value and abs(value - square_amount) <= tolerance and abs(value - square_amount) > 0.01:
                        confidence = 1.5  # Lower confidence for approximate matches
                        
                        reserve_date = reserve['pu_date']
                        if isinstance(reserve_date, str):
                            try:
                                reserve_date = datetime.strptime(reserve_date, '%Y-%m-%d').date()
                            except:
                                reserve_date = None
                        elif hasattr(reserve_date, 'date'):
                            reserve_date = reserve_date.date()
                        
                        if square_date and reserve_date:
                            date_diff = abs((square_date - reserve_date).days)
                            if date_diff <= 30:
                                confidence += 1
                        
                        if confidence > best_confidence:
                            best_confidence = confidence
                            best_match = {
                                'square_payment_id': square_payment['payment_id'],
                                'square_amount': square_amount,
                                'square_date': square_date,
                                'square_key': square_payment['payment_key'],
                                'lms_deposit_key': None,
                                'lms_deposit_total': None,
                                'lms_deposit_date': None,
                                'reserve_number': reserve['reserve_number'],
                                'reserve_rate': reserve['rate'],
                                'reserve_balance': reserve['balance'],
                                'reserve_date': reserve_date,
                                'cibc_match': False,
                                'cibc_transaction_id': None,
                                'cibc_date': None,
                                'confidence': confidence,
                                'match_method': f"Approximate {field} match (±5%): {value} ≈ {square_amount}, Reserve={reserve['reserve_number']}"
                            }

        if best_match:
            matches.append(best_match)
            processed_squares.add(square_payment['payment_id'])
    
    # Sort by confidence descending, then by Square payment ID for consistency
    matches.sort(key=lambda x: (x['confidence'], x['square_payment_id']), reverse=True)
    return matches

def load_retainer_mapping(file_path):
    """Load optional mapping CSV supporting both Deposit Key -> Reserve_No and PaymentID -> Reserve_No."""
    if not file_path or not os.path.exists(file_path):
        return None
    by_key = {}
    by_paymentid = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            key_val = row.get('Key') or row.get('key') or row.get('deposit_key') or row.get('Deposit_Key')
            res_val = row.get('Reserve_No') or row.get('reserve_no') or row.get('Reserve') or row.get('reserve')
            pid_val = row.get('PaymentID') or row.get('payment_id') or row.get('SquarePaymentID') or row.get('square_payment_id')
            if res_val is None:
                continue
            # Normalize reserve number
            try:
                res_no = int(str(res_val).strip())
            except Exception:
                try:
                    res_no = int(float(str(res_val).strip()))
                except Exception:
                    continue
            # Map by key if present
            if key_val is not None:
                key_str = str(key_val).strip()
                by_key[key_str] = res_no
                try:
                    by_key[int(key_str)] = res_no
                except Exception:
                    pass
            # Map by payment id if present
            if pid_val:
                pid_str = str(pid_val).strip()
                by_paymentid[pid_str] = res_no
    print(f"Loaded mapping: by_key={len(by_key)}, by_paymentid={len(by_paymentid)} from {file_path}")
    return {'by_key': by_key, 'by_paymentid': by_paymentid}

def generate_matching_report(matches):
    """Generate comprehensive matching report"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = f'l:/limo/reports/square_lms_comprehensive_matches_{timestamp}.csv'
    
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    
    with open(report_file, 'w', newline='', encoding='utf-8') as f:
        if matches:
            writer = csv.DictWriter(f, fieldnames=list(matches[0].keys()))
            writer.writeheader()
            writer.writerows(matches)
        else:
            writer = csv.writer(f)
            writer.writerow(['No matches found'])
    
    print(f"Report saved: {report_file}")
    return report_file

def apply_matches(matches, min_confidence=3, apply_changes=False):
    """Apply high-confidence matches to link Square payments to charters"""
    applied = []
    skipped = []
    
    with get_pg_conn() as pg_conn:
        with pg_conn.cursor() as cur:
            for match in matches:
                if match['confidence'] < min_confidence:
                    skipped.append({**match, 'skip_reason': 'low_confidence'})
                    continue
                
                # Find charter by reserve_number
                cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", 
                           (match['reserve_number'],))
                charter_row = cur.fetchone()
                
                if not charter_row:
                    skipped.append({**match, 'skip_reason': 'no_charter_found'})
                    continue
                
                charter_id = charter_row[0]
                
                # Update Square payment with charter link
                if apply_changes:
                    cur.execute("""
                        UPDATE payments 
                        SET charter_id = %s, 
                            notes = COALESCE(notes || ' | ', '') || %s,
                            last_updated = NOW()
                        WHERE payment_id = %s
                    """, (
                        charter_id,
                        f"Auto-linked via LMS: {match['match_method']} (confidence={match['confidence']})",
                        match['square_payment_id']
                    ))
                
                applied.append({
                    **match,
                    'charter_id': charter_id,
                    'action': 'linked' if apply_changes else 'would_link'
                })
            
            if apply_changes:
                pg_conn.commit()
    
    print(f"Applied: {len(applied)}, Skipped: {len(skipped)}")
    return applied, skipped

def main():
    parser = argparse.ArgumentParser(description='Comprehensive Square to LMS matcher')
    parser.add_argument('--apply', action='store_true', help='Apply matches to database')
    parser.add_argument('--min-confidence', type=int, default=3, help='Minimum confidence for auto-apply')
    parser.add_argument('--retainer-map', dest='retainer_map', help='CSV file mapping Deposit Key -> Reserve_No to boost retainer matches', default=None)
    args = parser.parse_args()
    
    print("=== Square to LMS Comprehensive Matcher ===")
    
    try:
        # Get all data
        square_payments = get_unmatched_square_payments()
        lms_deposits = get_lms_deposits()
        lms_reserves = get_lms_reserves()
        cibc_transactions = get_cibc_banking_transactions()
        
        print(f"Data loaded: {len(square_payments)} Square payments, {len(lms_deposits)} LMS deposits, {len(lms_reserves)} reserves, {len(cibc_transactions)} CIBC transactions")
        
        # Optional mapping for $205/$500 retainer matches
        retainer_map = load_retainer_mapping(args.retainer_map) if args.retainer_map else None

        # Perform comprehensive matching
        matches = match_square_to_lms_comprehensive(square_payments, lms_deposits, lms_reserves, cibc_transactions, retainer_map)
        
        # Generate report
        report_file = generate_matching_report(matches)
        
        # Summary
        high_confidence = len([m for m in matches if m['confidence'] >= args.min_confidence])
        with_cibc = len([m for m in matches if m['cibc_match']])
        
        print(f"\n=== Summary ===")
        print(f"Total matches found: {len(matches)}")
        print(f"High confidence (>={args.min_confidence}): {high_confidence}")
        print(f"With CIBC validation: {with_cibc}")
        
        # Apply matches if requested
        if matches:
            applied, skipped = apply_matches(matches, args.min_confidence, args.apply)
            
            if args.apply:
                print(f"Successfully linked {len(applied)} Square payments to charters")
            else:
                print(f"Would link {len(applied)} Square payments (use --apply to execute)")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()