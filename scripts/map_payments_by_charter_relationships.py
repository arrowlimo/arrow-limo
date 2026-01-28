#!/usr/bin/env python3
"""
Map 205 unmatched payments to charters using payment method relationships.

Strategy:
1. Start with charters (not payments)
2. Map by payment method: e-transfer, cash, trade, square
3. For Square: Use transaction_id, refund relationships, client email similarity
4. Exclude all successfully matched
5. What remains = true orphan question

Author: Phase 1 QA Testing Agent
"""

import psycopg2
import pandas as pd
import os
from decimal import Decimal
from collections import defaultdict
import difflib

# Database connection
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def get_unmatched_payments():
    """Get 205 unmatched payments from Track B"""
    conn = connect_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            p.payment_id, p.amount, p.payment_date, p.payment_method, 
            p.square_transaction_id, p.notes, p.created_at
        FROM payments p
        WHERE p.reserve_number IS NULL
        AND p.payment_method = 'credit_card'  -- All 273 Square payments are credit_card
        ORDER BY p.payment_date, p.amount
    """)
    
    payments = cur.fetchall()
    columns = ['payment_id', 'amount', 'payment_date', 'payment_method', 
               'transaction_id', 'notes', 'created_at']
    df_payments = pd.DataFrame(payments, columns=columns)
    
    cur.close()
    conn.close()
    
    return df_payments

def get_charters_with_high_match_rate():
    """Get charters that had 85%+ match rate in LMS"""
    conn = connect_db()
    cur = conn.cursor()
    
    # Get all charters
    cur.execute("""
        SELECT 
            c.id as charter_id,
            c.reserve_number,
            c.charter_date,
            c.customer_email,
            c.total_amount_due,
            c.notes
        FROM charters c
        WHERE c.reserve_number IS NOT NULL
        ORDER BY c.charter_date DESC
    """)
    
    charters = cur.fetchall()
    columns = ['charter_id', 'reserve_number', 'charter_date', 'customer_email', 
               'total_amount_due', 'notes']
    df_charters = pd.DataFrame(charters, columns=columns)
    
    cur.close()
    conn.close()
    
    return df_charters

def get_payments_by_method():
    """Get all payments by method to understand distribution"""
    conn = connect_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            payment_method,
            COUNT(*) as count,
            SUM(amount) as total,
            COUNT(CASE WHEN reserve_number IS NOT NULL THEN 1 END) as linked,
            COUNT(CASE WHEN reserve_number IS NULL THEN 1 END) as orphaned
        FROM payments
        GROUP BY payment_method
        ORDER BY orphaned DESC
    """)
    
    result = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return result

def get_square_transactions():
    """Get all square transactions to understand refund patterns"""
    conn = connect_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            payment_id, amount, payment_date, square_transaction_id, notes,
            reserve_number, payment_method
        FROM payments
        WHERE payment_method = 'credit_card'
        AND square_transaction_id IS NOT NULL
        ORDER BY square_transaction_id, payment_date
    """)
    
    transactions = cur.fetchall()
    columns = ['payment_id', 'amount', 'payment_date', 'transaction_id', 'notes',
               'reserve_number', 'payment_method']
    df = pd.DataFrame(transactions, columns=columns)
    
    cur.close()
    conn.close()
    
    return df

def map_square_by_transaction_id(df_unmatched, df_square):
    """
    For Square deposits: Match by transaction_id
    Square transactions are typically:
    - Original charge: positive amount
    - Refund: negative amount with same transaction_id
    """
    mapped = []
    unmapped = []
    
    # Group square transactions by transaction_id
    square_by_txid = df_square[df_square['transaction_id'].notna()].groupby('transaction_id')
    
    for idx, payment in df_unmatched.iterrows():
        if pd.isna(payment['transaction_id']):
            unmapped.append({
                'payment_id': payment['payment_id'],
                'amount': payment['amount'],
                'payment_date': payment['payment_date'],
                'reason': 'No transaction_id in Square payment'
            })
            continue
        
        # Look for same transaction_id in linked payments
        matching_txid = df_square[df_square['transaction_id'] == payment['transaction_id']]
        
        if len(matching_txid) > 0 and matching_txid['reserve_number'].notna().any():
            # Found matching reserve in same transaction
            reserve = matching_txid[matching_txid['reserve_number'].notna()]['reserve_number'].iloc[0]
            mapped.append({
                'payment_id': payment['payment_id'],
                'amount': payment['amount'],
                'payment_date': payment['payment_date'],
                'reserve_number': reserve,
                'method': 'square_transaction_id_refund_match',
                'confidence': 'HIGH'
            })
        else:
            unmapped.append({
                'payment_id': payment['payment_id'],
                'amount': payment['amount'],
                'payment_date': payment['payment_date'],
                'transaction_id': payment['transaction_id'],
                'reason': 'Transaction ID not linked to any reserve'
            })
    
    return mapped, unmapped

def map_by_email_similarity(df_unmatched, df_charters):
    """
    For Square: Match by customer email similarity
    Square client email should match charter customer_email
    """
    mapped = []
    unmapped = []
    
    for idx, payment in df_unmatched.iterrows():
        notes = str(payment['notes']).lower() if pd.notna(payment['notes']) else ''
        
        # Try to extract email from notes
        payment_email = None
        if 'square' in notes and '@' in notes:
            # Try to extract email pattern from notes
            import re
            emails = re.findall(r'[\w\.-]+@[\w\.-]+', notes)
            if emails:
                payment_email = emails[0].lower()
        
        if payment_email is None:
            unmapped.append({
                'payment_id': payment['payment_id'],
                'amount': payment['amount'],
                'payment_date': payment['payment_date'],
                'reason': 'No email found in Square notes'
            })
            continue
        
        # Find charter with matching email
        matching_charters = []
        for _, charter in df_charters.iterrows():
            charter_email = str(charter['customer_email']).lower() if pd.notna(charter['customer_email']) else ''
            
            # Exact match
            if charter_email == payment_email:
                matching_charters.append({
                    'reserve_number': charter['reserve_number'],
                    'charter_date': charter['charter_date'],
                    'confidence': 'EXACT'
                })
            # Similarity match (>80%)
            elif charter_email and payment_email:
                ratio = difflib.SequenceMatcher(None, charter_email, payment_email).ratio()
                if ratio > 0.80:
                    matching_charters.append({
                        'reserve_number': charter['reserve_number'],
                        'charter_date': charter['charter_date'],
                        'confidence': f'SIMILAR ({ratio:.1%})'
                    })
        
        if len(matching_charters) == 1:
            # Exactly one match
            mapped.append({
                'payment_id': payment['payment_id'],
                'amount': payment['amount'],
                'payment_date': payment['payment_date'],
                'reserve_number': matching_charters[0]['reserve_number'],
                'method': 'square_email_match',
                'confidence': matching_charters[0]['confidence']
            })
        elif len(matching_charters) > 1:
            unmapped.append({
                'payment_id': payment['payment_id'],
                'amount': payment['amount'],
                'payment_date': payment['payment_date'],
                'reason': f'Ambiguous: {len(matching_charters)} email matches',
                'candidate_reserves': [c['reserve_number'] for c in matching_charters]
            })
        else:
            unmapped.append({
                'payment_id': payment['payment_id'],
                'amount': payment['amount'],
                'payment_date': payment['payment_date'],
                'reason': 'No email match in charters'
            })
    
    return mapped, unmapped

def analyze_remaining_unmatched(df_unmatched, already_mapped_ids):
    """
    Categorize remaining unmatched by pattern:
    1. Round amounts (retainers)
    2. Duplicates
    3. Missing charter
    """
    remaining = df_unmatched[~df_unmatched['payment_id'].isin(already_mapped_ids)].copy()
    
    analysis = {
        'round_amounts': [],
        'duplicates': [],
        'missing_charter': [],
        'unclear': []
    }
    
    # Check for round amounts (retainer indicator)
    for idx, payment in remaining.iterrows():
        if float(payment['amount']) % 100 == 0:
            analysis['round_amounts'].append({
                'payment_id': payment['payment_id'],
                'amount': payment['amount']
            })
    
    # Check for duplicates
    dup_groups = remaining.groupby(['amount', 'payment_date']).size()
    for (amt, date), count in dup_groups.items():
        if count > 1:
            dup_payments = remaining[
                (remaining['amount'] == amt) & 
                (remaining['payment_date'] == date)
            ]
            for _, payment in dup_payments.iterrows():
                analysis['duplicates'].append({
                    'payment_id': payment['payment_id'],
                    'amount': payment['amount'],
                    'date': date,
                    'count_same_date': count
                })
    
    # Remaining unclassified
    round_ids = {p['payment_id'] for p in analysis['round_amounts']}
    dup_ids = {p['payment_id'] for p in analysis['duplicates']}
    
    for idx, payment in remaining.iterrows():
        if payment['payment_id'] not in round_ids and payment['payment_id'] not in dup_ids:
            analysis['unclear'].append({
                'payment_id': payment['payment_id'],
                'amount': payment['amount'],
                'payment_date': payment['payment_date'],
                'notes': payment['notes']
            })
    
    return analysis

def main():
    print("\n" + "=" * 80)
    print("MAPPING PAYMENTS TO CHARTERS BY RELATIONSHIP TYPE")
    print("=" * 80)
    
    # Step 1: Get data
    print("\n📊 Loading data...")
    df_unmatched = get_unmatched_payments()
    df_charters = get_charters_with_high_match_rate()
    df_square = get_square_transactions()
    
    print(f"   Unmatched payments: {len(df_unmatched)}")
    print(f"   Charters: {len(df_charters)}")
    print(f"   Square transactions (all): {len(df_square)}")
    
    # Step 2: Show payment method distribution
    print("\n" + "=" * 80)
    print("PAYMENT METHOD DISTRIBUTION")
    print("=" * 80)
    payment_methods = get_payments_by_method()
    for method, count, total, linked, orphaned in payment_methods:
        print(f"{method:20s}: {count:5d} total | {linked:5d} linked | {orphaned:5d} orphaned | ${total:12,.2f}")
    
    # Step 3: Map Square by transaction ID
    print("\n" + "=" * 80)
    print("TRACK 1: SQUARE TRANSACTION ID + REFUND MATCHING")
    print("=" * 80)
    mapped_txid, unmapped_txid = map_square_by_transaction_id(df_unmatched, df_square)
    print(f"✅ Matched via transaction_id: {len(mapped_txid)}")
    print(f"❌ Unmatched: {len(unmapped_txid)}")
    
    if mapped_txid:
        print("\n   Sample matched:")
        for m in mapped_txid[:5]:
            print(f"     Payment {m['payment_id']:5d} ${m['amount']:10.2f} → Reserve {m['reserve_number']}")
    
    # Step 4: Map Square by email similarity
    print("\n" + "=" * 80)
    print("TRACK 2: SQUARE EMAIL SIMILARITY MATCHING")
    print("=" * 80)
    unmapped_after_txid = pd.DataFrame(unmapped_txid)
    if len(unmapped_after_txid) > 0:
        mapped_email, unmapped_email = map_by_email_similarity(
            df_unmatched[df_unmatched['payment_id'].isin(unmapped_after_txid['payment_id'])],
            df_charters
        )
    else:
        mapped_email, unmapped_email = [], []
    
    print(f"✅ Matched via email: {len(mapped_email)}")
    print(f"❌ Unmatched: {len(unmapped_email)}")
    
    if mapped_email:
        print("\n   Sample matched:")
        for m in mapped_email[:5]:
            print(f"     Payment {m['payment_id']:5d} ${m['amount']:10.2f} → Reserve {m['reserve_number']}")
    
    # Step 5: Analyze remaining
    print("\n" + "=" * 80)
    print("TRACK 3: PATTERN ANALYSIS OF REMAINING UNMATCHED")
    print("=" * 80)
    
    already_mapped = set([m['payment_id'] for m in mapped_txid] + [m['payment_id'] for m in mapped_email])
    remaining = df_unmatched[~df_unmatched['payment_id'].isin(already_mapped)]
    
    print(f"\n📊 Still unmatched after Square matching: {len(remaining)}")
    
    analysis = analyze_remaining_unmatched(df_unmatched, already_mapped)
    
    print(f"\n   🔵 Likely RETAINERS (round amounts): {len(analysis['round_amounts'])}")
    print(f"   🔴 Likely DUPLICATES (same amt+date): {len(analysis['duplicates'])}")
    print(f"   ⚫ UNCLEAR: {len(analysis['unclear'])}")
    
    # Show samples
    if analysis['round_amounts']:
        print("\n   Sample retainers (round amounts):")
        for r in analysis['round_amounts'][:5]:
            print(f"     Payment {r['payment_id']:5d} ${r['amount']:10.2f}")
    
    if analysis['duplicates']:
        print("\n   Sample duplicates (same amount + date):")
        seen = set()
        for d in analysis['duplicates']:
            key = (d['amount'], d['date'])
            if key not in seen:
                print(f"     ${d['amount']:10.2f} on {d['date']} × {d['count_same_date']} payments")
                seen.add(key)
    
    # Step 6: Summary
    print("\n" + "=" * 80)
    print("SUMMARY: WHAT REMAINS IS THE QUESTION")
    print("=" * 80)
    
    total_matched = len(mapped_txid) + len(mapped_email)
    print(f"\n✅ Total matched to charters:")
    print(f"   Transaction ID matches: {len(mapped_txid)}")
    print(f"   Email matches: {len(mapped_email)}")
    print(f"   ───────────────────────")
    print(f"   TOTAL MATCHED: {total_matched}")
    
    print(f"\n🤔 REMAINING UNMATCHED: {len(remaining)}")
    print(f"   ├─ Likely retainers: {len(analysis['round_amounts'])} (keep)")
    print(f"   ├─ Likely duplicates: {len(analysis['duplicates'])} (delete after verify)")
    print(f"   └─ Unclear: {len(analysis['unclear'])} (requires decision)")
    
    print(f"\n📋 THE QUESTION:")
    print(f"   1. Are {len(analysis['round_amounts'])} retainers legitimate?")
    print(f"   2. Are {len(analysis['duplicates'])} duplicate entries true duplicates?")
    print(f"   3. Do {len(analysis['unclear'])} unclear payments need missing charters?")
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    main()
