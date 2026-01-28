#!/usr/bin/env python3
"""
Match Square payments to LMS data to find reserve numbers and link to charters.

Process:
1. Get unmatched Square payments from Postgres
2. Extract LMS Payment/Reserve data via ODBC
3. Match by amount (±$1) and date proximity (±7 days)
4. Use LMS Payment.Reserve_No to link Square payments to charters
5. Generate report and optionally apply matches
"""
import os
import csv
import pyodbc
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import argparse
from datetime import datetime, timedelta

load_dotenv('l:/limo/.env'); load_dotenv()

# PostgreSQL connection
PG_HOST = os.getenv('DB_HOST','localhost')
PG_PORT = int(os.getenv('DB_PORT','5432'))
PG_NAME = os.getenv('DB_NAME','almsdata')
PG_USER = os.getenv('DB_USER','postgres')
PG_PASSWORD = os.getenv('DB_PASSWORD','')

# LMS Access ODBC connection
LMS_PATH = r"L:\limo\backups\lms.mdb"

def get_lms_conn():
    """Connect to LMS Access database via ODBC"""
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)

def get_pg_conn():
    """Connect to PostgreSQL almsdata"""
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_NAME, user=PG_USER, password=PG_PASSWORD)

def get_unmatched_square_payments():
    """Get Square payments without charter links"""
    print("Fetching unmatched Square payments...")
    
    with get_pg_conn() as pg_conn:
        with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT payment_id, amount, payment_date, payment_key, notes
                FROM payments
                WHERE payment_method = 'credit_card' 
                  AND payment_key IS NOT NULL 
                  AND charter_id IS NULL
                ORDER BY payment_date DESC
            """)
            return cur.fetchall()

def extract_lms_payments_and_reserves():
    """Extract LMS Payment and Reserve data for matching"""
    print("Extracting LMS Payment and Reserve data...")
    
    with get_lms_conn() as lms_conn:
        # Get Payment data with reserve numbers (recent data only)
        print("  Extracting LMS Payments...")
        payments = []
        cur = lms_conn.cursor()
        cur.execute("""
            SELECT PaymentID, Account_No, Reserve_No, Amount, [Key], LastUpdated, LastUpdatedBy
            FROM Payment
            WHERE Reserve_No IS NOT NULL AND Amount > 0 AND LastUpdated >= #2024-01-01#
            ORDER BY LastUpdated DESC
        """)
        for row in cur.fetchall():
            payments.append({
                'payment_id': row[0],
                'account_number': row[1],
                'reserve_number': row[2],
                'amount': float(row[3]) if row[3] else 0.0,
                'key': row[4],
                'payment_date': row[5],
                'last_updated_by': row[6],
            })
        
        # Get Reserve data for additional context (recent data only)
        print("  Extracting LMS Reserves...")
        reserves = []
        cur.execute("""
            SELECT Reserve_No, Account_No, PU_Date, Rate, Balance, Deposit, 
                   Status, Pymt_Type, Notes, Name, Bill_Name, Attention
            FROM Reserve
            WHERE Reserve_No IS NOT NULL AND PU_Date >= #2024-01-01#
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
    
    print(f"  Extracted {len(payments)} LMS payments, {len(reserves)} reserves")
    return payments, reserves

def match_square_to_lms(square_payments, lms_payments, lms_reserves):
    """Match Square payments to LMS data by amount and date proximity"""
    print(f"Matching {len(square_payments)} Square payments to LMS data...")
    print(f"  Available LMS payments: {len(lms_payments)}")
    print(f"  Available LMS reserves: {len(lms_reserves)}")
    
    # Create reserve lookup for additional context
    reserve_lookup = {r['reserve_number']: r for r in lms_reserves if r['reserve_number']}
    
    matches = []
    
    for sq_payment in square_payments:
        sq_amount = float(sq_payment['amount'])
        sq_date = sq_payment['payment_date']
        
        # Find matches in both LMS payments AND reserves
        candidates = []
        
        # Match against LMS Payment records
        for lms_payment in lms_payments:
            lms_amount = lms_payment['amount']
            lms_date = lms_payment['payment_date']
            
            # Amount match (±$1)
            if abs(sq_amount - lms_amount) <= 1.0:
                # Date proximity check (±60 days)
                date_diff = None
                if sq_date and lms_date:
                    try:
                        if isinstance(sq_date, str):
                            sq_dt = datetime.strptime(sq_date, '%Y-%m-%d').date()
                        elif hasattr(sq_date, 'date'):
                            sq_dt = sq_date.date() if hasattr(sq_date, 'date') else sq_date
                        else:
                            sq_dt = sq_date
                        
                        if isinstance(lms_date, str):
                            lms_dt = datetime.strptime(lms_date, '%Y-%m-%d %H:%M:%S').date()
                        elif hasattr(lms_date, 'date'):
                            lms_dt = lms_date.date() if hasattr(lms_date, 'date') else lms_date
                        else:
                            lms_dt = lms_date
                        
                        date_diff = abs((sq_dt - lms_dt).days)
                    except (ValueError, TypeError, AttributeError):
                        date_diff = 999  # Unknown date difference
                
                if date_diff is None or date_diff <= 60:
                    # Get reserve context
                    reserve_data = reserve_lookup.get(lms_payment['reserve_number'], {})
                    
                    # Calculate confidence score
                    confidence = 0
                    signals = []
                    
                    if abs(sq_amount - lms_amount) <= 0.01:
                        confidence += 2
                        signals.append('exact_amount')
                    elif abs(sq_amount - lms_amount) <= 1.0:
                        confidence += 1
                        signals.append('amount_close')
                    
                    if date_diff is not None:
                        if date_diff <= 3:
                            confidence += 2
                            signals.append('date_close')
                        elif date_diff <= 7:
                            confidence += 1
                            signals.append('date_nearby')
                    
                    # Credit card payment type hint
                    pymt_type = reserve_data.get('pymt_type', '').lower()
                    if any(term in pymt_type for term in ['credit', 'card', 'square']):
                        confidence += 1
                        signals.append('payment_type_match')
                    
                    candidates.append({
                        'match_type': 'lms_payment',
                        'lms_payment': lms_payment,
                        'reserve_data': reserve_data,
                        'confidence': confidence,
                        'signals': signals,
                        'date_diff': date_diff or 999,
                        'amount_diff': abs(sq_amount - lms_amount)
                    })
        
        # Match directly against Reserve records (Rate, Balance, Deposit amounts)
        for reserve in lms_reserves:
            reserve_amounts = []
            if reserve.get('rate') and reserve['rate'] > 0:
                reserve_amounts.append(('rate', reserve['rate']))
            if reserve.get('balance') and reserve['balance'] > 0:
                reserve_amounts.append(('balance', reserve['balance']))
            if reserve.get('deposit') and reserve['deposit'] > 0:
                reserve_amounts.append(('deposit', reserve['deposit']))
            
            for amount_type, reserve_amount in reserve_amounts:
                if abs(sq_amount - reserve_amount) <= 1.0:
                    # Date proximity check using PU_Date (±90 days)
                    date_diff = None
                    reserve_date = reserve.get('charter_date')  # This is PU_Date
                    if sq_date and reserve_date:
                        try:
                            if isinstance(sq_date, str):
                                sq_dt = datetime.strptime(sq_date, '%Y-%m-%d').date()
                            elif hasattr(sq_date, 'date'):
                                sq_dt = sq_date.date() if hasattr(sq_date, 'date') else sq_date
                            else:
                                sq_dt = sq_date
                            
                            if isinstance(reserve_date, str):
                                res_dt = datetime.strptime(reserve_date, '%Y-%m-%d %H:%M:%S').date()
                            elif hasattr(reserve_date, 'date'):
                                res_dt = reserve_date.date() if hasattr(reserve_date, 'date') else reserve_date
                            else:
                                res_dt = reserve_date
                            
                            date_diff = abs((sq_dt - res_dt).days)
                        except (ValueError, TypeError, AttributeError):
                            date_diff = 999
                    
                    if date_diff is None or date_diff <= 365:  # Allow up to 1 year difference
                        confidence = 0
                        signals = []
                        
                        if abs(sq_amount - reserve_amount) <= 0.01:
                            confidence += 2
                            signals.append(f'exact_{amount_type}')
                        elif abs(sq_amount - reserve_amount) <= 1.0:
                            confidence += 1
                            signals.append(f'{amount_type}_close')
                        
                        if date_diff is not None:
                            if date_diff <= 7:
                                confidence += 2
                                signals.append('date_close')
                            elif date_diff <= 14:
                                confidence += 1
                                signals.append('date_nearby')
                        
                        # Credit card payment type hint
                        pymt_type = reserve.get('pymt_type', '').lower()
                        if any(term in pymt_type for term in ['credit', 'card', 'square']):
                            confidence += 1
                            signals.append('payment_type_match')
                        
                        candidates.append({
                            'match_type': 'reserve_direct',
                            'lms_payment': {
                                'reserve_number': reserve['reserve_number'],
                                'amount': reserve_amount,
                                'payment_date': reserve_date,
                                'payment_id': f"RESERVE_{reserve['reserve_number']}_{amount_type}"
                            },
                            'reserve_data': reserve,
                            'confidence': confidence,
                            'signals': signals,
                            'date_diff': date_diff or 999,
                            'amount_diff': abs(sq_amount - reserve_amount)
                        })
        
        # Sort candidates by confidence, then by date proximity, then by amount proximity
        candidates.sort(key=lambda x: (-x['confidence'], x['date_diff'], x['amount_diff']))
        
        # Take the best candidate
        best_candidate = candidates[0] if candidates else None
        
        match_record = {
            'square_payment': dict(sq_payment),
            'lms_match': best_candidate,
            'candidate_count': len(candidates),
            'recommended_action': 'manual_review'
        }
        
        if best_candidate:
            if best_candidate['confidence'] >= 3:
                match_record['recommended_action'] = 'auto_link_high_confidence'
            elif best_candidate['confidence'] >= 2:
                match_record['recommended_action'] = 'auto_link_medium_confidence'
        
        matches.append(match_record)
    
    return matches

def generate_match_report(matches):
    """Generate comprehensive matching report"""
    print("Generating Square-LMS matching report...")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = f'l:/limo/reports/square_lms_matches_{timestamp}.csv'
    
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    
    with open(report_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'square_payment_id', 'square_amount', 'square_date', 'square_payment_key',
            'lms_reserve_number', 'lms_payment_id', 'lms_amount', 'lms_date',
            'reserve_charter_date', 'reserve_rate', 'reserve_balance', 'reserve_name',
            'match_confidence', 'match_signals', 'candidate_count', 'date_diff_days',
            'amount_diff', 'recommended_action'
        ])
        
        for match in matches:
            sq = match['square_payment']
            lms_match = match['lms_match']
            
            if lms_match:
                lms_payment = lms_match['lms_payment']
                reserve_data = lms_match['reserve_data']
                
                writer.writerow([
                    sq['payment_id'],
                    sq['amount'],
                    sq['payment_date'],
                    sq['payment_key'],
                    lms_payment['reserve_number'],
                    lms_payment['payment_id'],
                    lms_payment['amount'],
                    lms_payment['payment_date'],
                    reserve_data.get('charter_date', ''),
                    reserve_data.get('rate', ''),
                    reserve_data.get('balance', ''),
                    reserve_data.get('name', ''),
                    lms_match['confidence'],
                    '; '.join(lms_match['signals']),
                    match['candidate_count'],
                    lms_match['date_diff'],
                    lms_match['amount_diff'],
                    match['recommended_action']
                ])
            else:
                writer.writerow([
                    sq['payment_id'],
                    sq['amount'],
                    sq['payment_date'],
                    sq['payment_key'],
                    '', '', '', '', '', '', '', '',
                    0, '', 0, '', '', 'no_match_found'
                ])
    
    print(f"Report saved: {report_file}")
    return report_file

def apply_matches(matches, apply_changes=False, min_confidence=3):
    """Apply high-confidence matches to link Square payments to charters"""
    print(f"Applying matches with min_confidence={min_confidence}, apply_changes={apply_changes}")
    
    applied = []
    skipped = []
    
    with get_pg_conn() as pg_conn:
        with pg_conn.cursor() as cur:
            for match in matches:
                sq_payment = match['square_payment']
                lms_match = match['lms_match']
                
                if not lms_match or lms_match['confidence'] < min_confidence:
                    skipped.append({
                        'square_payment_id': sq_payment['payment_id'],
                        'reason': 'low_confidence' if lms_match else 'no_match'
                    })
                    continue
                
                reserve_number = lms_match['lms_payment']['reserve_number']
                
                # Find charter by reserve_number
                cur.execute("""
                    SELECT charter_id, charter_date, total_amount_due 
                    FROM charters 
                    WHERE reserve_number = %s 
                    ORDER BY charter_date DESC 
                    LIMIT 1
                """, (reserve_number,))
                
                charter_row = cur.fetchone()
                if not charter_row:
                    skipped.append({
                        'square_payment_id': sq_payment['payment_id'],
                        'reason': 'reserve_not_in_charters',
                        'reserve_number': reserve_number
                    })
                    continue
                
                charter_id = charter_row[0]
                
                # Update Square payment with charter link
                if apply_changes:
                    cur.execute("""
                        UPDATE payments 
                        SET charter_id = %s, 
                            notes = COALESCE(notes || ' | ', '') || 'Auto-linked via LMS reserve ' || %s,
                            last_updated = NOW()
                        WHERE payment_id = %s
                    """, (charter_id, reserve_number, sq_payment['payment_id']))
                
                applied.append({
                    'square_payment_id': sq_payment['payment_id'],
                    'charter_id': charter_id,
                    'reserve_number': reserve_number,
                    'confidence': lms_match['confidence'],
                    'signals': '; '.join(lms_match['signals'])
                })
        
        if apply_changes:
            pg_conn.commit()
    
    # Write summary CSVs
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    applied_csv = f"l:/limo/reports/square_lms_applied_{timestamp}.csv"
    skipped_csv = f"l:/limo/reports/square_lms_skipped_{timestamp}.csv"
    
    os.makedirs('l:/limo/reports', exist_ok=True)
    
    with open(applied_csv, 'w', newline='', encoding='utf-8') as f:
        if applied:
            w = csv.DictWriter(f, fieldnames=list(applied[0].keys()))
            w.writeheader()
            w.writerows(applied)
    
    with open(skipped_csv, 'w', newline='', encoding='utf-8') as f:
        if skipped:
            keys = set()
            for row in skipped:
                keys.update(row.keys())
            w = csv.DictWriter(f, fieldnames=sorted(keys))
            w.writeheader()
            w.writerows(skipped)
    
    print(f"Apply complete: applied={len(applied)}, skipped={len(skipped)}")
    print(f"  Applied: {applied_csv}")
    print(f"  Skipped: {skipped_csv}")
    
    return applied_csv, skipped_csv

def main():
    print("=== Square-to-LMS Charter Matching ===")
    
    parser = argparse.ArgumentParser(description='Match Square payments to LMS data for charter linking')
    parser.add_argument('--apply', action='store_true', help='Apply high-confidence matches to Postgres')
    parser.add_argument('--min-confidence', type=int, default=3, help='Minimum confidence to auto-apply (default: 3)')
    args = parser.parse_args()
    
    try:
        # Get unmatched Square payments
        square_payments = get_unmatched_square_payments()
        print(f"Found {len(square_payments)} unmatched Square payments")
        
        if not square_payments:
            print("No unmatched Square payments found!")
            return
        
        # Extract LMS data
        lms_payments, lms_reserves = extract_lms_payments_and_reserves()
        
        # Perform matching
        matches = match_square_to_lms(square_payments, lms_payments, lms_reserves)
        
        # Generate report
        report_file = generate_match_report(matches)
        
        # Summary stats
        high_confidence = len([m for m in matches if m['lms_match'] and m['lms_match']['confidence'] >= 3])
        medium_confidence = len([m for m in matches if m['lms_match'] and m['lms_match']['confidence'] == 2])
        with_matches = len([m for m in matches if m['lms_match']])
        
        print(f"\n=== Summary ===")
        print(f"Total Square payments: {len(square_payments)}")
        print(f"With LMS matches: {with_matches}")
        print(f"High confidence (3+): {high_confidence}")
        print(f"Medium confidence (2): {medium_confidence}")
        print(f"Report saved: {report_file}")
        
        # Apply matches if requested
        if args.apply or high_confidence > 0:
            apply_matches(matches, apply_changes=args.apply, min_confidence=args.min_confidence)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()