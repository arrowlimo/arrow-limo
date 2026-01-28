"""
Integration tests (multi-table workflows).
"""
import pytest
from decimal import Decimal
from datetime import date

def test_charter_payment_workflow(db_cursor, cleanup_test_data):
    """Test complete charter→payment workflow."""
    # Step 1: Create charter
    db_cursor.execute("""
        INSERT INTO charters (reserve_number, charter_date, total_amount_due, status)
        VALUES ('999999', %s, %s, 'assigned')
    """, (date.today(), Decimal("450.00")))
    
    # Step 2: Add partial payment
    db_cursor.execute("""
        INSERT INTO payments (reserve_number, amount, payment_date, payment_method)
        VALUES ('999999', %s, %s, 'cash')
    """, (Decimal("200.00"), date.today()))
    
    # Step 3: Add remaining payment
    db_cursor.execute("""
        INSERT INTO payments (reserve_number, amount, payment_date, payment_method)
        VALUES ('999999', %s, %s, 'credit_card')
    """, (Decimal("250.00"), date.today()))
    
    # Step 4: Verify balance = 0
    db_cursor.execute("""
        SELECT 
            c.total_amount_due - COALESCE(SUM(p.amount), 0) as balance
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        WHERE c.reserve_number = '999999'
        GROUP BY c.reserve_number, c.total_amount_due
    """)
    
    balance = db_cursor.fetchone()[0]
    assert balance == Decimal("0.00")
    
    # Step 5: Update charter status to completed
    db_cursor.execute("""
        UPDATE charters
        SET status = 'completed'
        WHERE reserve_number = '999999'
    """)
    
    db_cursor.execute("""
        SELECT status FROM charters WHERE reserve_number = '999999'
    """)
    
    status = db_cursor.fetchone()[0]
    assert status == 'completed'

def test_payment_reconciliation(db_cursor, cleanup_test_data):
    """Test payment reconciliation to banking."""
    # Create charter
    db_cursor.execute("""
        INSERT INTO charters (reserve_number, charter_date, total_amount_due)
        VALUES ('999999', %s, %s)
    """, (date.today(), Decimal("500.00")))
    
    # Create payment
    db_cursor.execute("""
        INSERT INTO payments (reserve_number, amount, payment_date, payment_method)
        VALUES ('999999', %s, %s, 'cash')
        RETURNING payment_id
    """, (Decimal("500.00"), date.today()))
    
    payment_id = db_cursor.fetchone()[0]
    
    # Create banking transaction
    db_cursor.execute("""
        INSERT INTO banking_transactions 
        (transaction_date, description, amount, mapped_bank_account_id)
        VALUES (%s, 'DEPOSIT - Cash', %s, 1)
        RETURNING banking_transaction_id
    """, (date.today(), Decimal("500.00")))
    
    banking_id = db_cursor.fetchone()[0]
    
    # Link payment to banking
    db_cursor.execute("""
        INSERT INTO banking_receipt_matching_ledger 
        (banking_transaction_id, receipt_id, matched_amount)
        VALUES (%s, %s, %s)
    """, (banking_id, payment_id, Decimal("500.00")))
    
    # Verify link
    db_cursor.execute("""
        SELECT COUNT(*) 
        FROM banking_receipt_matching_ledger
        WHERE banking_transaction_id = %s
    """, (banking_id,))
    
    count = db_cursor.fetchone()[0]
    assert count == 1
