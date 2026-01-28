#!/usr/bin/env python3
"""
Analyze 205 unmatched payments by relationship type.

Strategy:
1. Identify payment method and characteristics
2. For Square: Look at transaction ID, refund patterns, Square customer email
3. Map back to charters
4. What's left = true orphan question

Author: Phase 1 QA Testing Agent
"""

import psycopg2
import pandas as pd
import os
from decimal import Decimal

# Database connection
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def get_payment_method_distribution():
    """See payment method distribution"""
    conn = connect_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            payment_method,
            COUNT(*) as count,
            COALESCE(SUM(amount), 0) as total,
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

def get_unmatched_payments():
    """Get 205 unmatched payments with full Square details"""
    conn = connect_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            payment_id, amount, payment_date, payment_method,
            square_transaction_id, square_customer_email, square_customer_name,
            square_status, notes
        FROM payments
        WHERE reserve_number IS NULL
        ORDER BY payment_date, amount
    """)
    
    payments = cur.fetchall()
    columns = ['payment_id', 'amount', 'payment_date', 'payment_method',
               'square_txid', 'square_email', 'square_name',
               'square_status', 'notes']
    df = pd.DataFrame(payments, columns=columns)
    
    cur.close()
    conn.close()
    
    return df

def get_square_customers_map():
    """Get Square customers with email for matching"""
    conn = connect_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT DISTINCT
            square_customer_email, 
            COUNT(*) as count
        FROM payments
        WHERE square_customer_email IS NOT NULL
        GROUP BY square_customer_email
        ORDER BY count DESC
    """)
    
    result = cur.fetchall()
    cur.close()
    conn.close()
    
    return result

def analyze_square_transactions():
    """Analyze Square transaction patterns"""
    conn = connect_db()
    cur = conn.cursor()
    
    # Get all square transactions (both linked and unlinked)
    cur.execute("""
        SELECT 
            square_transaction_id,
            COUNT(*) as count,
            SUM(CASE WHEN reserve_number IS NOT NULL THEN 1 ELSE 0 END) as linked,
            SUM(CASE WHEN reserve_number IS NULL THEN 1 ELSE 0 END) as orphaned,
            COALESCE(SUM(amount), 0) as total_amount,
            MIN(payment_date) as earliest,
            MAX(payment_date) as latest
        FROM payments
        WHERE payment_method = 'credit_card'
        AND square_transaction_id IS NOT NULL
        GROUP BY square_transaction_id
        HAVING COUNT(*) > 1  -- Multi-part transactions (deposit+fee, refund+charge, etc.)
        ORDER BY count DESC
    """)
    
    result = cur.fetchall()
    cur.close()
    conn.close()
    
    return result

def categorize_unmatched(df_unmatched):
    """Categorize the 205 unmatched payments"""
    
    categories = {
        'square_refund': [],
        'round_amount_retainer': [],
        'duplicate_same_day': [],
        'high_amount_charge': [],
        'unclear': []
    }
    
    for idx, payment in df_unmatched.iterrows():
        pid = payment['payment_id']
        amt = float(payment['amount'])
        notes_str = str(payment['notes']).lower() if pd.notna(payment['notes']) else ''
        
        # Check if likely refund or fee
        if 'refund' in notes_str or 'fee' in notes_str or 'adjustment' in notes_str:
            categories['square_refund'].append(pid)
        # Check if round amount (retainer indicator)
        elif amt % 100 == 0 or amt % 50 == 0:
            categories['round_amount_retainer'].append(pid)
        # High amount charges
        elif amt > 1000:
            categories['high_amount_charge'].append(pid)
        # Default
        else:
            categories['unclear'].append(pid)
    
    return categories

def main():
    print("\n" + "=" * 80)
    print("ANALYZING 205 UNMATCHED PAYMENTS BY RELATIONSHIP TYPE")
    print("=" * 80)
    
    # Step 1: Payment method distribution
    print("\n1️⃣ PAYMENT METHOD DISTRIBUTION")
    print("─" * 80)
    methods = get_payment_method_distribution()
    for method, count, total, linked, orphaned in methods:
        if orphaned > 0:
            pct = (orphaned / count * 100)
            print(f"{method:20s}: {count:5d} total | {linked:5d} linked | {orphaned:5d} orphaned ({pct:.1f}%) | ${total:12,.2f}")
    
    # Step 2: Get unmatched payments
    print("\n2️⃣ LOADING UNMATCHED PAYMENT DATA")
    print("─" * 80)
    df_unmatched = get_unmatched_payments()
    print(f"Total unmatched: {len(df_unmatched)}")
    print(f"Total amount: ${df_unmatched['amount'].sum():,.2f}")
    print(f"Payment methods in unmatched:")
    for method, count in df_unmatched['payment_method'].value_counts().items():
        print(f"  {method:20s}: {count:5d}")
    
    # Step 3: Square customer emails
    print("\n3️⃣ SQUARE CUSTOMER EMAIL ANALYSIS")
    print("─" * 80)
    sq_emails = get_square_customers_map()
    print(f"Unique Square customer emails: {len(sq_emails)}")
    if sq_emails:
        print(f"Top 10 most common Square emails:")
        for email, count in sq_emails[:10]:
            email_display = email[:40] + "..." if email and len(email) > 40 else email
            print(f"  {email_display:43s}: {count:3d} payments")
    
    # Step 4: Multi-transaction analysis
    print("\n4️⃣ SQUARE TRANSACTION ID PATTERNS")
    print("─" * 80)
    multi_trans = analyze_square_transactions()
    print(f"Transaction IDs with multiple payments (deposits, refunds, fees): {len(multi_trans)}")
    if multi_trans:
        print(f"Top 10 most complex transactions:")
        for txid, count, linked, orphaned, total, earliest, latest in multi_trans[:10]:
            print(f"  TxID {str(txid)[:20]:20s}: {count} parts | {linked} linked | {orphaned} orphaned | ${total:10.2f}")
    
    # Step 5: Categorize unmatched
    print("\n5️⃣ CATEGORIZATION OF 205 UNMATCHED")
    print("─" * 80)
    categories = categorize_unmatched(df_unmatched)
    
    print(f"\n🔵 Likely SQUARE REFUNDS/FEES: {len(categories['square_refund'])} payments")
    if categories['square_refund']:
        samples = df_unmatched[df_unmatched['payment_id'].isin(categories['square_refund'][:5])]
        for _, p in samples.iterrows():
            print(f"     Payment {p['payment_id']:5d} ${p['amount']:10.2f} ({p['square_status']})")
    
    print(f"\n💰 ROUND AMOUNT RETAINERS: {len(categories['round_amount_retainer'])} payments")
    if categories['round_amount_retainer']:
        samples = df_unmatched[df_unmatched['payment_id'].isin(categories['round_amount_retainer'][:5])]
        for _, p in samples.iterrows():
            print(f"     Payment {p['payment_id']:5d} ${p['amount']:10.2f}")
    
    print(f"\n⚡ HIGH AMOUNT CHARGES (>$1000): {len(categories['high_amount_charge'])} payments")
    if categories['high_amount_charge']:
        samples = df_unmatched[df_unmatched['payment_id'].isin(categories['high_amount_charge'][:5])]
        for _, p in samples.iterrows():
            print(f"     Payment {p['payment_id']:5d} ${p['amount']:10.2f}")
    
    print(f"\n❓ UNCLEAR: {len(categories['unclear'])} payments")
    if categories['unclear']:
        samples = df_unmatched[df_unmatched['payment_id'].isin(categories['unclear'][:5])]
        for _, p in samples.iterrows():
            print(f"     Payment {p['payment_id']:5d} ${p['amount']:10.2f}")
    
    # Step 6: Summary
    print("\n" + "=" * 80)
    print("🤔 THE REMAINING QUESTION")
    print("=" * 80)
    
    print(f"\nAfter starting with charters and mapping by relationship:")
    print(f"\n  ✅ 56 payments linked via LMS matching (TRACK A)")
    print(f"  ✅ {len(categories['square_refund'])} payments identified as Square refunds/fees")
    print(f"  ✅ {len(categories['round_amount_retainer'])} payments identified as round-amount retainers")
    print(f"  ✅ {len(categories['high_amount_charge'])} high-amount charges (may be legitimate deposits)")
    print(f"  ❓ {len(categories['unclear'])} payments remain categorized as UNCLEAR")
    
    print(f"\nNext decision points:")
    print(f"  1. Are {len(categories['round_amount_retainer'])} retainers legitimate? (KEEP)")
    print(f"  2. Should {len(categories['square_refund'])} refunds/fees be cleaned up? (DELETE/REVERSE)")
    print(f"  3. Do {len(categories['high_amount_charge'])} high charges need investigation? (VERIFY)")
    print(f"  4. How to handle {len(categories['unclear'])} unclear payments? (MANUAL REVIEW)")

if __name__ == '__main__':
    main()
