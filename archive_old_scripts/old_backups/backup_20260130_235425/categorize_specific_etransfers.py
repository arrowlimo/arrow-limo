#!/usr/bin/env python3
"""
Categorize specific E-transfers based on manual identification:
- Mike Woodrow = Rent payments
- Jason Rogers = Driver (one payment for furnace install)
- Dave Mundy = Driver
- Gostola Aleyna = Driver
- Others = Check if old drivers
"""

import psycopg2
import hashlib
from decimal import Decimal

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password='***REDACTED***',
)

def create_receipt(cur, trans_id, date, description, amount, vendor, category, 
                   expense_account, gl_code, gl_name, deductible, gst_rate, comment):
    """Create receipt if doesn't exist, return receipt_id"""
    
    source_hash = hashlib.md5(f"banking_{trans_id}_{date}_{amount}".encode()).hexdigest()
    
    # Check if receipt exists
    cur.execute("SELECT id FROM receipts WHERE source_hash = %s", (source_hash,))
    existing = cur.fetchone()
    
    if existing:
        return existing[0]
    
    # Calculate GST
    gst_amount = Decimal('0.00')
    if gst_rate > 0:
        gst_amount = amount * Decimal(str(gst_rate))
    
    # Create receipt
    cur.execute("""
        INSERT INTO receipts (
            receipt_date, vendor_name, description, gross_amount, gst_amount,
            category, expense_account, gl_account_code, gl_account_name,
            deductible_status, created_from_banking, source_system,
            source_reference, source_hash, auto_categorized, comment
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            true, 'banking_import', %s, %s, true, %s
        ) RETURNING id
    """, (
        date, vendor, description, amount, gst_amount,
        category, expense_account, gl_code, gl_name, deductible,
        str(trans_id), source_hash, comment
    ))
    
    return cur.fetchone()[0]

def update_matching_ledger(cur, trans_id, receipt_id, match_type, notes):
    """Update or insert matching ledger entry"""
    
    cur.execute("""
        SELECT id FROM banking_receipt_matching_ledger
        WHERE banking_transaction_id = %s
    """, (trans_id,))
    
    if cur.fetchone():
        cur.execute("""
            UPDATE banking_receipt_matching_ledger SET
                receipt_id = %s,
                match_type = %s,
                match_status = 'matched',
                match_confidence = 'manual',
                notes = %s
            WHERE banking_transaction_id = %s
        """, (receipt_id, match_type, notes, trans_id))
    else:
        cur.execute("""
            INSERT INTO banking_receipt_matching_ledger (
                banking_transaction_id, receipt_id, match_type,
                match_status, match_confidence, notes, created_by
            ) VALUES (%s, %s, %s, 'matched', 'manual', %s, 'manual_categorization')
        """, (trans_id, receipt_id, match_type, notes))

def main():
    cur = conn.cursor()
    
    print("\n" + "=" * 100)
    print("CATEGORIZING SPECIFIC E-TRANSFERS")
    print("=" * 100)
    
    total_categorized = 0
    
    # ============================================================================
    # 1. MIKE WOODROW - Rent Payments
    # ============================================================================
    print("\n1. Processing MIKE WOODROW - Rent Payments...")
    cur.execute("""
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = 2019
        AND debit_amount > 0
        AND UPPER(description) LIKE '%MIKE WOODROW%'
        AND NOT EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger ml 
            WHERE ml.banking_transaction_id = transaction_id
            AND ml.match_status = 'matched'
        )
    """)
    
    woodrow_transactions = cur.fetchall()
    print(f"   Found {len(woodrow_transactions)} transactions")
    
    for trans_id, date, desc, amount in woodrow_transactions:
        receipt_id = create_receipt(
            cur, trans_id, date, desc, amount,
            vendor="MIKE WOODROW",
            category="Rent",
            expense_account="Shop Rent",
            gl_code="5410",
            gl_name="Rent Expense",
            deductible="BUSINESS",
            gst_rate=0,  # Rent is usually exempt from GST
            comment="Shop rent payment to Mike Woodrow"
        )
        update_matching_ledger(cur, trans_id, receipt_id, 'rent_payment', "Shop rent - Mike Woodrow")
        total_categorized += 1
        print(f"   [OK] {date} ${amount:,.2f} - Rent payment")
    
    # ============================================================================
    # 2. JASON ROGERS - Driver & Heating Install
    # ============================================================================
    print("\n2. Processing JASON ROGERS - Driver/Heating Install...")
    cur.execute("""
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = 2019
        AND debit_amount > 0
        AND UPPER(description) LIKE '%JASON ROGERS%'
        AND NOT EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger ml 
            WHERE ml.banking_transaction_id = transaction_id
            AND ml.match_status = 'matched'
        )
    """)
    
    rogers_transactions = cur.fetchall()
    print(f"   Found {len(rogers_transactions)} transactions")
    
    for trans_id, date, desc, amount in rogers_transactions:
        # Check if it's the heating install (mentioned "Armor Heatco")
        if 'ARMOR' in desc.upper() or 'HEATCO' in desc.upper():
            receipt_id = create_receipt(
                cur, trans_id, date, desc, amount,
                vendor="JASON ROGERS - ARMOR HEATCO",
                category="Repairs & Maintenance",
                expense_account="Building Repairs",
                gl_code="5420",
                gl_name="Repairs & Maintenance",
                deductible="BUSINESS",
                gst_rate=0.05,  # GST on service
                comment="Furnace/heating installation for shop by Jason Rogers"
            )
            update_matching_ledger(cur, trans_id, receipt_id, 'building_repair', "Heating install - Jason Rogers")
            print(f"   [OK] {date} ${amount:,.2f} - Heating install (with GST)")
        else:
            # Driver payment
            receipt_id = create_receipt(
                cur, trans_id, date, desc, amount,
                vendor="JASON ROGERS",
                category="Driver Payment",
                expense_account="Driver Payments",
                gl_code="5160",
                gl_name="Driver Payments",
                deductible="BUSINESS",
                gst_rate=0,
                comment="Driver payment to Jason Rogers"
            )
            update_matching_ledger(cur, trans_id, receipt_id, 'driver_payment', "Driver payment - Jason Rogers")
            print(f"   [OK] {date} ${amount:,.2f} - Driver payment")
        
        total_categorized += 1
    
    # ============================================================================
    # 3. DAVE MUNDY - Driver
    # ============================================================================
    print("\n3. Processing DAVE MUNDY - Driver...")
    cur.execute("""
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = 2019
        AND debit_amount > 0
        AND UPPER(description) LIKE '%DAVE MUNDY%'
        AND NOT EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger ml 
            WHERE ml.banking_transaction_id = transaction_id
            AND ml.match_status = 'matched'
        )
    """)
    
    mundy_transactions = cur.fetchall()
    print(f"   Found {len(mundy_transactions)} transactions")
    
    for trans_id, date, desc, amount in mundy_transactions:
        receipt_id = create_receipt(
            cur, trans_id, date, desc, amount,
            vendor="DAVE MUNDY",
            category="Driver Payment",
            expense_account="Driver Payments",
            gl_code="5160",
            gl_name="Driver Payments",
            deductible="BUSINESS",
            gst_rate=0,
            comment="Driver payment to Dave Mundy"
        )
        update_matching_ledger(cur, trans_id, receipt_id, 'driver_payment', "Driver payment - Dave Mundy")
        total_categorized += 1
        print(f"   [OK] {date} ${amount:,.2f} - Driver payment")
    
    # ============================================================================
    # 4. GOSTOLA ALEYNA - Driver
    # ============================================================================
    print("\n4. Processing GOSTOLA ALEYNA - Driver...")
    cur.execute("""
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = 2019
        AND debit_amount > 0
        AND (
            UPPER(description) LIKE '%GOSTOLA%ALEYNA%'
            OR UPPER(description) LIKE '%ALEYNA%GOSTOLA%'
            OR UPPER(description) LIKE '%GOSTOLA%ALENA%'
        )
        AND NOT EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger ml 
            WHERE ml.banking_transaction_id = transaction_id
            AND ml.match_status = 'matched'
        )
    """)
    
    gostola_transactions = cur.fetchall()
    print(f"   Found {len(gostola_transactions)} transactions")
    
    for trans_id, date, desc, amount in gostola_transactions:
        receipt_id = create_receipt(
            cur, trans_id, date, desc, amount,
            vendor="GOSTOLA ALEYNA",
            category="Driver Payment",
            expense_account="Driver Payments",
            gl_code="5160",
            gl_name="Driver Payments",
            deductible="BUSINESS",
            gst_rate=0,
            comment="Driver payment to Gostola Aleyna"
        )
        update_matching_ledger(cur, trans_id, receipt_id, 'driver_payment', "Driver payment - Gostola Aleyna")
        total_categorized += 1
        print(f"   [OK] {date} ${amount:,.2f} - Driver payment")
    
    # ============================================================================
    # 5. OTHER POTENTIAL DRIVERS - Flag for review
    # ============================================================================
    print("\n5. Checking other E-transfers for potential old drivers...")
    
    other_names = [
        'TENISHA WOODRIDGE',
        'JACK CORNWALL',
        'KARALEE SMALL'
    ]
    
    for name in other_names:
        cur.execute(f"""
            SELECT transaction_id, transaction_date, description, debit_amount
            FROM banking_transactions
            WHERE EXTRACT(YEAR FROM transaction_date) = 2019
            AND debit_amount > 0
            AND UPPER(description) LIKE '%{name}%'
            AND NOT EXISTS (
                SELECT 1 FROM banking_receipt_matching_ledger ml 
                WHERE ml.banking_transaction_id = transaction_id
                AND ml.match_status = 'matched'
            )
        """)
        
        results = cur.fetchall()
        if results:
            print(f"\n   {name}: Found {len(results)} transactions - Categorizing as potential driver")
            for trans_id, date, desc, amount in results:
                receipt_id = create_receipt(
                    cur, trans_id, date, desc, amount,
                    vendor=name.title(),
                    category="Driver Payment",
                    expense_account="Driver Payments - Review",
                    gl_code="5160",
                    gl_name="Driver Payments",
                    deductible="BUSINESS",
                    gst_rate=0,
                    comment=f"Possible driver payment to {name.title()} - verify if old driver"
                )
                update_matching_ledger(cur, trans_id, receipt_id, 'driver_payment', 
                                     f"Potential driver payment - {name.title()} (verify)")
                total_categorized += 1
                print(f"   [WARN]  {date} ${amount:,.2f} - Needs verification")
    
    conn.commit()
    
    # ============================================================================
    # SUMMARY
    # ============================================================================
    print("\n" + "=" * 100)
    print("SUMMARY - MANUAL E-TRANSFER CATEGORIZATION")
    print("=" * 100)
    print(f"Total E-transfers categorized: {total_categorized}")
    
    # Get updated stats
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE ml.match_status = 'matched') as matched,
            SUM(bt.debit_amount) FILTER (WHERE ml.match_status = 'matched') as matched_amt
        FROM banking_transactions bt
        LEFT JOIN banking_receipt_matching_ledger ml ON bt.transaction_id = ml.banking_transaction_id
        WHERE EXTRACT(YEAR FROM bt.transaction_date) = 2019
        AND bt.debit_amount > 0
    """)
    
    total_matched, total_amt = cur.fetchone()
    
    cur.execute("""
        SELECT COUNT(*), SUM(debit_amount)
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = 2019
        AND debit_amount > 0
    """)
    
    total, total_sum = cur.fetchone()
    
    print("\n" + "=" * 100)
    print("OVERALL RECONCILIATION PROGRESS")
    print("=" * 100)
    print(f"Total 2019 transactions: {total:,} (${total_sum:,.2f})")
    print(f"Matched: {total_matched:,} (${total_amt:,.2f}) - {total_matched/total*100:.1f}%")
    print(f"Unmatched: {total - total_matched:,} (${total_sum - total_amt:,.2f})")
    print("=" * 100 + "\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
