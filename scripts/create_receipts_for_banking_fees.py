#!/usr/bin/env python
"""
Create receipts for banking fees that don't have matching receipts.
Checks for: account fees, NSF fees, overdraft interest, ATM fees, service charges, etc.
"""

import psycopg2
import os
from datetime import datetime
import hashlib

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def generate_source_hash(date, description, amount):
    """Generate deterministic hash for receipt deduplication"""
    normalized = f"{date}|{description.strip().upper()}|{amount:.2f}"
    return hashlib.sha256(normalized.encode()).hexdigest()

def is_banking_fee(description):
    """Identify banking fee transactions"""
    fee_keywords = [
        'ACCOUNT FEE',
        'NSF',
        'OVERDRAFT',
        'ATM FEE',
        'SERVICE CHARGE',
        'S/C',
        'MONTHLY FEE',
        'TRANSACTION FEE',
        'E-TRANSFER FEE',
        'WIRE TRANSFER FEE',
        'STOP PAYMENT',
        'RETURNED ITEM',
        'INSUFFICIENT FUNDS'
    ]
    desc_upper = description.upper()
    return any(keyword in desc_upper for keyword in fee_keywords)

def categorize_fee(description):
    """Categorize the type of banking fee"""
    desc_upper = description.upper()
    
    if 'NSF' in desc_upper or 'INSUFFICIENT' in desc_upper or 'RETURNED ITEM' in desc_upper:
        return 'NSF Fee', 'Banking - NSF'
    elif 'OVERDRAFT' in desc_upper:
        return 'Overdraft Interest', 'Banking - Overdraft'
    elif 'ATM' in desc_upper:
        return 'ATM Fee', 'Banking - ATM'
    elif 'E-TRANSFER' in desc_upper:
        return 'E-Transfer Fee', 'Banking - E-Transfer'
    elif 'ACCOUNT FEE' in desc_upper or 'MONTHLY FEE' in desc_upper:
        return 'Monthly Account Fee', 'Banking - Account Fee'
    elif 'SERVICE CHARGE' in desc_upper or 'S/C' in desc_upper:
        return 'Service Charge', 'Banking - Service Charge'
    elif 'STOP PAYMENT' in desc_upper:
        return 'Stop Payment Fee', 'Banking - Stop Payment'
    elif 'WIRE TRANSFER' in desc_upper:
        return 'Wire Transfer Fee', 'Banking - Wire Transfer'
    else:
        return 'Bank Fee', 'Banking - Other'

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=== BANKING FEE RECEIPT CREATION ===\n")
    
    # Find all 2012 banking fee transactions
    print("Step 1: Finding banking fee transactions in 2012...")
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            account_number
        FROM banking_transactions
        WHERE transaction_date >= '2012-01-01'
        AND transaction_date <= '2012-12-31'
        AND account_number = '0228362'
        AND debit_amount > 0
        AND debit_amount IS NOT NULL
        ORDER BY transaction_date
    """)
    
    all_debits = cur.fetchall()
    fee_transactions = []
    
    for txn_id, txn_date, desc, amount, acct in all_debits:
        if is_banking_fee(desc):
            fee_transactions.append({
                'transaction_id': txn_id,
                'date': txn_date,
                'description': desc,
                'amount': amount,
                'account': acct
            })
    
    print(f"Found {len(fee_transactions)} banking fee transactions")
    
    if not fee_transactions:
        print("\n[OK] No banking fees found in 2012")
        cur.close()
        conn.close()
        return
    
    # Check which fees already have receipts
    print("\nStep 2: Checking for existing receipts...")
    
    # Get all existing receipts for comparison (within ±3 days, matching amount)
    existing_receipts = {}
    for fee in fee_transactions:
        cur.execute("""
            SELECT receipt_id, receipt_date, vendor_name, gross_amount
            FROM receipts
            WHERE receipt_date BETWEEN %s::date - INTERVAL '3 days' 
                                  AND %s::date + INTERVAL '3 days'
            AND gross_amount = %s
        """, (fee['date'], fee['date'], fee['amount']))
        
        matches = cur.fetchall()
        if matches:
            existing_receipts[fee['transaction_id']] = matches
    
    fees_without_receipts = [f for f in fee_transactions if f['transaction_id'] not in existing_receipts]
    fees_with_receipts = [f for f in fee_transactions if f['transaction_id'] in existing_receipts]
    
    print(f"  {len(fees_with_receipts)} fees already have matching receipts")
    print(f"  {len(fees_without_receipts)} fees need receipts created")
    
    # Display breakdown
    if fees_with_receipts:
        print("\n[OK] Fees with existing receipts:")
        for fee in fees_with_receipts:
            print(f"  {fee['date']} | ${fee['amount']:7.2f} | {fee['description'][:50]}")
    
    if not fees_without_receipts:
        print("\n[OK] All banking fees already have receipts!")
        cur.close()
        conn.close()
        return
    
    # Display fees that need receipts
    print("\n[WARN]  Fees WITHOUT receipts (will be created):")
    total_missing = 0
    for fee in fees_without_receipts:
        category, expense_account = categorize_fee(fee['description'])
        print(f"  {fee['date']} | ${fee['amount']:7.2f} | {category:25} | {fee['description'][:40]}")
        total_missing += fee['amount']
    
    print(f"\nTotal fees without receipts: ${total_missing:.2f}")
    
    # Create receipts for fees without matches
    print("\n" + "="*70)
    print("CREATING RECEIPTS FOR BANKING FEES")
    print("="*70)
    
    created_count = 0
    created_total = 0.0
    
    for fee in fees_without_receipts:
        category, expense_account = categorize_fee(fee['description'])
        source_hash = generate_source_hash(fee['date'], fee['description'], fee['amount'])
        
        # Check if source_hash already exists (extra safety)
        cur.execute("SELECT receipt_id FROM receipts WHERE source_hash = %s", (source_hash,))
        if cur.fetchone():
            print(f"[WARN]  SKIP: Hash collision for {fee['date']} ${fee['amount']:.2f}")
            continue
        
        # GST is included in banking fees (5% for Alberta)
        gross_amount = float(fee['amount'])
        gst_amount = round(gross_amount * 0.05 / 1.05, 2)
        net_amount = round(gross_amount - gst_amount, 2)
        
        try:
            cur.execute("""
                INSERT INTO receipts (
                    receipt_date,
                    vendor_name,
                    gross_amount,
                    net_amount,
                    gst_amount,
                    description,
                    category,
                    expense_account,
                    source_system,
                    source_reference,
                    source_hash,
                    validation_status,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING receipt_id
            """, (
                fee['date'],
                'CIBC',
                gross_amount,
                net_amount,
                gst_amount,
                fee['description'],
                category,
                expense_account,
                'BANKING_2012',
                f"BTX:{fee['transaction_id']}",
                source_hash,
                'auto_created',
                datetime.now()
            ))
            
            receipt_id = cur.fetchone()[0]
            created_count += 1
            created_total += gross_amount
            
            print(f"[OK] Created receipt {receipt_id}: {fee['date']} ${gross_amount:7.2f} - {category}")
            
        except psycopg2.errors.UniqueViolation as e:
            conn.rollback()
            print(f"[WARN]  SKIP: Duplicate for {fee['date']} ${fee['amount']:.2f} - {str(e)[:100]}")
            continue
        except Exception as e:
            conn.rollback()
            print(f"[FAIL] ERROR creating receipt for {fee['date']}: {e}")
            continue
    
    # Commit all changes
    conn.commit()
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Total banking fee transactions found: {len(fee_transactions)}")
    print(f"Fees with existing receipts: {len(fees_with_receipts)}")
    print(f"Fees needing receipts: {len(fees_without_receipts)}")
    print(f"Receipts created: {created_count}")
    print(f"Total amount of new receipts: ${created_total:.2f}")
    
    if created_count > 0:
        print("\n[OK] SUCCESS: Banking fee receipts created")
    else:
        print("\n[WARN]  No new receipts needed to be created")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
