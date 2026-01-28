#!/usr/bin/env python3
"""
Enhanced Square Data Sync - Add Service Fees and Loan Payment Tracking

This script extends the existing square_sync.py to add:
1. Service fee tracking table (processing fees per transaction)
2. Loan payment tracking (Square Capital repayments)
3. Detailed fee reports by card brand and entry method

Run this FIRST to create the enhanced tables, then run square_sync.py normally.
"""

import os
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )

def create_enhanced_tables():
    """Create tables for service fees and loan tracking."""
    
    conn = get_db_conn()
    cur = conn.cursor()
    
    print('=' * 100)
    print('CREATING ENHANCED SQUARE TRACKING TABLES')
    print('=' * 100)
    
    # 1. Square Processing Fees table
    print('\n1. Creating square_processing_fees table...')
    cur.execute("""
        CREATE TABLE IF NOT EXISTS square_processing_fees (
            fee_id SERIAL PRIMARY KEY,
            payment_id TEXT NOT NULL,
            square_payment_id TEXT,
            transaction_date TIMESTAMPTZ,
            gross_amount NUMERIC(12,2),
            processing_fee_amount NUMERIC(12,2),
            net_amount NUMERIC(12,2),
            card_brand TEXT,
            card_last4 TEXT,
            entry_method TEXT,
            fee_type TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_square_fees_payment 
        ON square_processing_fees(square_payment_id)
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_square_fees_date 
        ON square_processing_fees(transaction_date)
    """)
    
    print('  ✓ square_processing_fees table created')
    
    # 2. Square Capital Loans table
    print('\n2. Creating square_capital_loans table...')
    cur.execute("""
        CREATE TABLE IF NOT EXISTS square_capital_loans (
            loan_id SERIAL PRIMARY KEY,
            square_loan_id TEXT UNIQUE,
            loan_amount NUMERIC(12,2),
            received_date DATE,
            status TEXT,
            banking_transaction_id INTEGER,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_banking_txn FOREIGN KEY (banking_transaction_id)
                REFERENCES banking_transactions(transaction_id) ON DELETE SET NULL
        )
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_square_loans_date 
        ON square_capital_loans(received_date)
    """)
    
    print('  ✓ square_capital_loans table created')
    
    # 3. Square Loan Payments table
    print('\n3. Creating square_loan_payments table...')
    cur.execute("""
        CREATE TABLE IF NOT EXISTS square_loan_payments (
            payment_id SERIAL PRIMARY KEY,
            loan_id INTEGER,
            payment_date DATE,
            payment_amount NUMERIC(12,2),
            banking_transaction_id INTEGER,
            payout_id TEXT,
            payment_type TEXT,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_loan FOREIGN KEY (loan_id)
                REFERENCES square_capital_loans(loan_id) ON DELETE CASCADE,
            CONSTRAINT fk_banking_payment FOREIGN KEY (banking_transaction_id)
                REFERENCES banking_transactions(transaction_id) ON DELETE SET NULL
        )
    """)
    
    # Indexes will be created after commit
    print('  ✓ square_loan_payments table created')
    
    print('  ✓ square_loan_payments table created')
    
    # Commit table creation before creating indexes
    conn.commit()
    
    # Now create indexes
    print('\n4. Creating indexes...')
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_square_loan_payments_date 
        ON square_loan_payments(payment_date)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_square_loan_payments_loan 
        ON square_loan_payments(loan_id)
    """)
    print('  ✓ Indexes created')
    
    # 5. Create views for reporting
    print('\n5. Creating reporting views...')
    
    # Service fee summary by month
    cur.execute("""
        CREATE OR REPLACE VIEW square_monthly_fee_summary AS
        SELECT 
            DATE_TRUNC('month', transaction_date) as month,
            COUNT(*) as transaction_count,
            SUM(gross_amount) as total_gross,
            SUM(processing_fee_amount) as total_fees,
            SUM(net_amount) as total_net,
            ROUND(SUM(processing_fee_amount) / NULLIF(SUM(gross_amount), 0) * 100, 2) as avg_fee_percentage
        FROM square_processing_fees
        GROUP BY DATE_TRUNC('month', transaction_date)
        ORDER BY month DESC
    """)
    
    print('  ✓ square_monthly_fee_summary view created')
    
    # Service fee by card brand
    cur.execute("""
        CREATE OR REPLACE VIEW square_fee_by_card_brand AS
        SELECT 
            card_brand,
            COUNT(*) as transaction_count,
            SUM(gross_amount) as total_gross,
            SUM(processing_fee_amount) as total_fees,
            SUM(net_amount) as total_net,
            ROUND(SUM(processing_fee_amount) / NULLIF(SUM(gross_amount), 0) * 100, 2) as avg_fee_percentage
        FROM square_processing_fees
        GROUP BY card_brand
        ORDER BY total_gross DESC
    """)
    
    print('  ✓ square_fee_by_card_brand view created')
    
    # Loan payment summary
    cur.execute("""
        CREATE OR REPLACE VIEW square_loan_summary AS
        SELECT 
            l.loan_id,
            l.square_loan_id,
            l.loan_amount,
            l.received_date,
            l.status,
            COUNT(p.payment_id) as payment_count,
            COALESCE(SUM(p.payment_amount), 0) as total_paid,
            l.loan_amount - COALESCE(SUM(p.payment_amount), 0) as remaining_balance
        FROM square_capital_loans l
        LEFT JOIN square_loan_payments p ON l.loan_id = p.loan_id
        GROUP BY l.loan_id, l.square_loan_id, l.loan_amount, l.received_date, l.status
        ORDER BY l.received_date DESC
    """)
    
    print('  ✓ square_loan_summary view created')
    
    conn.commit()
    
    # Show existing data counts
    print('\n' + '=' * 100)
    print('CURRENT DATA STATUS')
    print('=' * 100)
    
    cur.execute("SELECT COUNT(*) FROM payments WHERE square_payment_id IS NOT NULL")
    square_payments = cur.fetchone()[0]
    print(f'\nExisting Square payments in database: {square_payments}')
    
    cur.execute("SELECT COUNT(*) FROM square_payouts")
    payouts = cur.fetchone()[0]
    print(f'Existing Square payouts: {payouts}')
    
    cur.execute("SELECT COUNT(*) FROM square_processing_fees")
    fees = cur.fetchone()[0]
    print(f'Processing fee records: {fees}')
    
    cur.execute("SELECT COUNT(*) FROM square_capital_loans")
    loans = cur.fetchone()[0]
    print(f'Capital loan records: {loans}')
    
    cur.execute("SELECT COUNT(*) FROM square_loan_payments")
    loan_payments = cur.fetchone()[0]
    print(f'Loan payment records: {loan_payments}')
    
    if fees == 0 and square_payments > 0:
        print('\n⚠ You have Square payments but no processing fee records.')
        print('  Run the enhanced square_sync script to populate fee data.')
    
    if loans == 0:
        print('\n⚠ No loan records found.')
        print('  Check banking_transactions for Square Capital deposits to populate.')
    
    cur.close()
    conn.close()
    
    print('\n' + '=' * 100)
    print('✓ ENHANCED TABLES CREATED SUCCESSFULLY')
    print('=' * 100)
    print('\nNext steps:')
    print('1. Run: python l:\\limo\\scripts\\populate_square_fees.py')
    print('   (Populate processing fees from existing payment data)')
    print('2. Run: python l:\\limo\\scripts\\identify_square_loans.py')
    print('   (Identify and link Square Capital loans from banking data)')
    print('3. Run: python l:\\limo\\scripts\\square_sync.py')
    print('   (Regular sync of new Square payments and payouts)')
    print('4. Generate reports:')
    print('   SELECT * FROM square_monthly_fee_summary;')
    print('   SELECT * FROM square_fee_by_card_brand;')
    print('   SELECT * FROM square_loan_summary;')

if __name__ == '__main__':
    create_enhanced_tables()
