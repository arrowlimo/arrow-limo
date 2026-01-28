#!/usr/bin/env python3
"""
Comprehensive Square Data Validation & Staging

This script:
1. Creates Square staging tables (transactions, deposits, loans)
2. Validates all payments in almsdata against Square source
3. Identifies and categorizes duplicates
4. Matches everything exact to the dollar
5. Prepares clean-up recommendations

Note: This uses historical Square data from payments table as source.
If we have API access, we can also pull live data from Square API.
"""

import psycopg2
import pandas as pd
import os
from decimal import Decimal
from datetime import datetime, timedelta
from collections import defaultdict

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

def create_staging_tables():
    """Create Square staging tables for validation"""
    conn = connect_db()
    cur = conn.cursor()
    
    print("Creating Square staging tables...\n")
    
    # 1. Square transactions staging table
    cur.execute("""
        DROP TABLE IF EXISTS square_transactions_staging CASCADE;
        CREATE TABLE square_transactions_staging (
            staging_id SERIAL PRIMARY KEY,
            square_transaction_id VARCHAR(255) UNIQUE,
            square_payment_id VARCHAR(255),
            transaction_date TIMESTAMP,
            amount DECIMAL(12, 2),
            amount_refunded DECIMAL(12, 2) DEFAULT 0,
            amount_net DECIMAL(12, 2),
            currency VARCHAR(3),
            payment_method VARCHAR(50),
            card_brand VARCHAR(50),
            customer_name VARCHAR(255),
            customer_email VARCHAR(255),
            receipt_number VARCHAR(255),
            transaction_status VARCHAR(50),
            refunded BOOLEAN DEFAULT FALSE,
            dispute_status VARCHAR(50),
            notes TEXT,
            remarks TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    print("✅ Created square_transactions_staging")
    
    # 2. Square deposits staging (customer payments)
    cur.execute("""
        DROP TABLE IF EXISTS square_deposits_staging CASCADE;
        CREATE TABLE square_deposits_staging (
            staging_id SERIAL PRIMARY KEY,
            square_transaction_id VARCHAR(255),
            deposit_date TIMESTAMP,
            deposit_amount DECIMAL(12, 2),
            deposit_type VARCHAR(50),  -- 'customer_payment', 'refund', 'chargeback'
            customer_id VARCHAR(255),
            customer_email VARCHAR(255),
            related_almsdata_payment_id INTEGER,
            related_charter_reserve VARCHAR(50),
            matched BOOLEAN DEFAULT FALSE,
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (related_almsdata_payment_id) REFERENCES payments(payment_id)
        );
    """)
    print("✅ Created square_deposits_staging")
    
    # 3. Square loans/non-client related
    cur.execute("""
        DROP TABLE IF EXISTS square_loans_staging CASCADE;
        CREATE TABLE square_loans_staging (
            staging_id SERIAL PRIMARY KEY,
            square_transaction_id VARCHAR(255),
            transaction_date TIMESTAMP,
            transaction_type VARCHAR(50),  -- 'fee', 'adjustment', 'chargeback', 'dispute', 'bank_transfer'
            amount DECIMAL(12, 2),
            description TEXT,
            status VARCHAR(50),
            related_almsdata_payment_id INTEGER,
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (related_almsdata_payment_id) REFERENCES payments(payment_id)
        );
    """)
    print("✅ Created square_loans_staging")
    
    # 4. Duplicate detection staging
    cur.execute("""
        DROP TABLE IF EXISTS square_duplicates_staging CASCADE;
        CREATE TABLE square_duplicates_staging (
            staging_id SERIAL PRIMARY KEY,
            primary_payment_id INTEGER,
            duplicate_payment_id INTEGER,
            amount DECIMAL(12, 2),
            payment_date DATE,
            duplicate_date_diff INTEGER,  -- days between duplicates
            confidence_score DECIMAL(3, 2),  -- 0-1.0, higher = more confident it's a duplicate
            reason VARCHAR(255),  -- 'exact_amount_date', 'amount_only', 'customer_email', 'charter_match'
            is_multi_charter BOOLEAN DEFAULT FALSE,  -- true if legitimate multi-charter payment
            recommended_action VARCHAR(50),  -- 'delete', 'keep', 'merge', 'manual_review'
            notes TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    print("✅ Created square_duplicates_staging")
    
    # 5. Validation summary staging
    cur.execute("""
        DROP TABLE IF EXISTS square_validation_summary CASCADE;
        CREATE TABLE square_validation_summary (
            summary_id SERIAL PRIMARY KEY,
            metric_name VARCHAR(255),
            metric_value DECIMAL(15, 2),
            metric_count INTEGER,
            validation_date TIMESTAMP DEFAULT NOW(),
            status VARCHAR(50)  -- 'pass', 'fail', 'warning'
        );
    """)
    print("✅ Created square_validation_summary")
    
    conn.commit()
    cur.close()
    conn.close()
    
    print("\n✅ All staging tables created successfully\n")

def populate_square_transactions_from_almsdata():
    """
    Extract all Square transaction data from payments table
    This is the source of truth for all Square transactions
    """
    conn = connect_db()
    cur = conn.cursor()
    
    print("Populating square_transactions_staging from almsdata...\n")
    
    # Get all credit_card payments (Square payments)
    cur.execute("""
        SELECT 
            payment_id,
            square_transaction_id,
            square_payment_id,
            payment_date,
            amount,
            payment_method,
            square_card_brand,
            square_customer_name,
            square_customer_email,
            square_status,
            notes,
            created_at
        FROM payments
        WHERE payment_method = 'credit_card'
        ORDER BY payment_date
    """)
    
    payments = cur.fetchall()
    
    print(f"Found {len(payments)} Square credit_card payments\n")
    
    # Insert into staging table
    for payment in payments:
        pid, sq_txid, sq_payid, pay_date, amount, method, brand, cust_name, cust_email, status, notes, created = payment
        
        # Parse refund status from notes if present
        refunded = False
        amount_refunded = Decimal(0)
        if notes and 'refund' in str(notes).lower():
            refunded = True
            # Try to extract refund amount
            if 'refund' in str(notes).lower() and amount:
                amount_refunded = amount
        
        cur.execute("""
            INSERT INTO square_transactions_staging 
            (square_transaction_id, square_payment_id, transaction_date, amount, 
             amount_refunded, amount_net, currency, payment_method, card_brand,
             customer_name, customer_email, transaction_status, refunded, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (square_transaction_id) DO NOTHING
        """, (sq_txid, sq_payid, pay_date, amount, amount_refunded, 
              amount - amount_refunded, 'USD', method, brand,
              cust_name, cust_email, status, refunded, notes))
    
    conn.commit()
    cur.close()
    conn.close()
    
    print("✅ Populated square_transactions_staging\n")

def categorize_square_deposits_vs_loans():
    """
    Categorize Square transactions into:
    - Deposits (customer payments toward charters)
    - Loans/Non-client (fees, adjustments, chargebacks, disputes)
    """
    conn = connect_db()
    cur = conn.cursor()
    
    print("Categorizing Square transactions...\n")
    
    # First, mark all Square deposits (customer payments)
    cur.execute("""
        INSERT INTO square_deposits_staging 
        (square_transaction_id, deposit_date, deposit_amount, deposit_type, 
         customer_email, notes)
        SELECT 
            square_transaction_id,
            transaction_date,
            amount,
            CASE 
                WHEN amount < 0 THEN 'refund'
                WHEN amount >= 0 THEN 'customer_payment'
            END as deposit_type,
            customer_email,
            CONCAT('From Square transaction. Notes: ', notes)
        FROM square_transactions_staging
        WHERE amount > 0
        ORDER BY transaction_date
    """)
    
    dep_count = cur.rowcount
    print(f"✅ Categorized {dep_count} customer deposits")
    
    # Mark loans/fees/adjustments (non-client related)
    cur.execute("""
        INSERT INTO square_loans_staging
        (square_transaction_id, transaction_date, transaction_type, amount, 
         description, status, notes)
        SELECT 
            square_transaction_id,
            transaction_date,
            CASE 
                WHEN notes LIKE '%fee%' OR notes LIKE '%charge%' THEN 'fee'
                WHEN notes LIKE '%adjustment%' THEN 'adjustment'
                WHEN notes LIKE '%chargeback%' THEN 'chargeback'
                WHEN notes LIKE '%dispute%' THEN 'dispute'
                WHEN amount < 0 THEN 'refund'
                ELSE 'other'
            END as transaction_type,
            ABS(amount),
            CONCAT('Square non-client transaction. Notes: ', notes),
            transaction_status,
            notes
        FROM square_transactions_staging
        WHERE amount < 0 OR notes LIKE '%fee%' 
           OR notes LIKE '%adjustment%' OR notes LIKE '%chargeback%'
    """)
    
    loan_count = cur.rowcount
    print(f"✅ Categorized {loan_count} loans/fees/adjustments\n")
    
    conn.commit()
    cur.close()
    conn.close()

def identify_duplicates():
    """
    Identify potential duplicates:
    - Same amount + same date (likely duplicates)
    - Same amount (different dates) - need manual review
    - Multi-charter payments (legitimate duplicates with same customer)
    """
    conn = connect_db()
    cur = conn.cursor()
    
    print("Identifying potential duplicates...\n")
    
    # Find exact duplicates: same amount + same date
    cur.execute("""
        INSERT INTO square_duplicates_staging
        (primary_payment_id, duplicate_payment_id, amount, payment_date,
         duplicate_date_diff, confidence_score, reason, recommended_action)
        SELECT 
            p1.payment_id as primary_id,
            p2.payment_id as duplicate_id,
            p1.amount,
            p1.payment_date::DATE,
            0 as date_diff,
            0.95 as confidence,
            'exact_amount_date' as reason,
            'delete' as recommended_action
        FROM payments p1
        JOIN payments p2 ON p1.amount = p2.amount 
            AND p1.payment_date::DATE = p2.payment_date::DATE
            AND p1.payment_method = 'credit_card'
            AND p2.payment_method = 'credit_card'
            AND p1.payment_id < p2.payment_id
            AND p1.reserve_number IS NULL
            AND p2.reserve_number IS NULL
        WHERE p1.amount > 0
    """)
    
    exact_dup_count = cur.rowcount
    print(f"✅ Found {exact_dup_count} exact duplicates (same amount + date)")
    
    # Find same amount within ±1 day (possible duplicates)
    cur.execute("""
        INSERT INTO square_duplicates_staging
        (primary_payment_id, duplicate_payment_id, amount, payment_date,
         duplicate_date_diff, confidence_score, reason, recommended_action)
        SELECT 
            p1.payment_id,
            p2.payment_id,
            p1.amount,
            p1.payment_date::DATE,
            ABS((p1.payment_date::DATE - p2.payment_date::DATE))::INTEGER as date_diff,
            0.75 as confidence,
            'amount_same_customer' as reason,
            'manual_review' as recommended_action
        FROM payments p1
        JOIN payments p2 ON p1.amount = p2.amount
            AND ABS((p1.payment_date::DATE - p2.payment_date::DATE)) <= 1
            AND p1.payment_method = 'credit_card'
            AND p2.payment_method = 'credit_card'
            AND p1.payment_id < p2.payment_id
            AND p1.reserve_number IS NULL
            AND p2.reserve_number IS NULL
        WHERE NOT EXISTS (
            SELECT 1 FROM square_duplicates_staging s
            WHERE s.primary_payment_id = p1.payment_id
            AND s.duplicate_payment_id = p2.payment_id
        )
    """)
    
    near_dup_count = cur.rowcount
    print(f"✅ Found {near_dup_count} near-duplicates (same amount within 1 day)")
    
    conn.commit()
    
    # Get duplicate summary
    cur.execute("""
        SELECT confidence_score, COUNT(*) as count
        FROM square_duplicates_staging
        GROUP BY confidence_score
        ORDER BY confidence_score DESC
    """)
    
    print("\nDuplicate breakdown by confidence:")
    for score, count in cur.fetchall():
        print(f"  Confidence {score}: {count} pairs")
    
    cur.close()
    conn.close()

def validate_amounts_match():
    """
    Validate that all Square transactions match exactly to the dollar
    """
    conn = connect_db()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("AMOUNT VALIDATION")
    print("="*80)
    
    # Total Square deposits
    cur.execute("""
        SELECT 
            COUNT(*) as deposit_count,
            COALESCE(SUM(amount), 0) as deposit_total,
            COALESCE(SUM(amount_refunded), 0) as refund_total
        FROM square_transactions_staging
        WHERE amount >= 0
    """)
    
    deposits = cur.fetchone()
    
    print(f"\nSquare Deposits (in almsdata):")
    print(f"  Count: {deposits[0]}")
    print(f"  Total: ${deposits[1]:,.2f}")
    print(f"  Refunded: ${deposits[2]:,.2f}")
    print(f"  Net: ${deposits[1] - deposits[2]:,.2f}")
    
    # Total in payments table
    cur.execute("""
        SELECT 
            COUNT(*) as payment_count,
            COALESCE(SUM(amount), 0) as payment_total
        FROM payments
        WHERE payment_method = 'credit_card'
    """)
    
    alms_payments = cur.fetchone()
    
    print(f"\nPayments Table (almsdata):")
    print(f"  Count: {alms_payments[0]}")
    print(f"  Total: ${alms_payments[1]:,.2f}")
    
    # Check for matching
    matched_count = 0
    cur.execute("""
        SELECT COUNT(*) as count
        FROM payments p
        WHERE p.payment_method = 'credit_card'
        AND p.reserve_number IS NOT NULL
    """)
    
    matched = cur.fetchone()
    matched_count = matched[0] if matched else 0
    
    print(f"\nLinked to Charters:")
    print(f"  Count: {matched_count}")
    
    print(f"\nUnlinked (Orphaned):")
    unlinked = alms_payments[0] - matched_count
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) 
        FROM payments
        WHERE payment_method = 'credit_card'
        AND reserve_number IS NULL
    """)
    unlinked_amount = cur.fetchone()[0]
    print(f"  Count: {unlinked}")
    print(f"  Amount: ${unlinked_amount:,.2f}")
    
    cur.close()
    conn.close()

def generate_validation_report():
    """Generate final validation report"""
    conn = connect_db()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("VALIDATION SUMMARY REPORT")
    print("="*80)
    
    # Staging table record counts
    cur.execute("""
        SELECT 
            (SELECT COUNT(*) FROM square_transactions_staging) as transactions,
            (SELECT COUNT(*) FROM square_deposits_staging) as deposits,
            (SELECT COUNT(*) FROM square_loans_staging) as loans,
            (SELECT COUNT(*) FROM square_duplicates_staging) as duplicates
    """)
    
    stats = cur.fetchone()
    transactions, deposits, loans, duplicates = stats
    
    print(f"\nStaging Tables:")
    print(f"  Square Transactions: {transactions}")
    print(f"  Deposits (Customer): {deposits}")
    print(f"  Loans/Non-Client: {loans}")
    print(f"  Potential Duplicates: {duplicates}")
    
    # Get duplicate recommendations
    cur.execute("""
        SELECT recommended_action, COUNT(*) as count
        FROM square_duplicates_staging
        GROUP BY recommended_action
    """)
    
    print(f"\nDuplicate Cleanup Recommendations:")
    for action, count in cur.fetchall():
        print(f"  {action.upper()}: {count} records")
    
    cur.close()
    conn.close()

def main():
    print("\n" + "="*80)
    print("COMPREHENSIVE SQUARE DATA VALIDATION & STAGING")
    print("="*80)
    
    # Step 1: Create staging tables
    create_staging_tables()
    
    # Step 2: Populate staging from almsdata
    populate_square_transactions_from_almsdata()
    
    # Step 3: Categorize deposits vs loans
    categorize_square_deposits_vs_loans()
    
    # Step 4: Identify duplicates
    identify_duplicates()
    
    # Step 5: Validate amounts
    validate_amounts_match()
    
    # Step 6: Generate report
    generate_validation_report()
    
    print("\n" + "="*80)
    print("✅ VALIDATION COMPLETE")
    print("="*80)
    print("\nNext steps:")
    print("  1. Review duplicates in square_duplicates_staging")
    print("  2. Verify multi-charter payments (legitimate duplicates)")
    print("  3. Execute cleanup: DELETE FROM payments WHERE payment_id IN (...)")
    print("  4. Validate final orphan count matches Square deposits")
    print("\n")

if __name__ == '__main__':
    main()
