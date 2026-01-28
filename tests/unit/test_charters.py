"""
Unit tests for charter CRUD operations.
"""
import pytest
from decimal import Decimal
from datetime import date

def test_create_charter(db_cursor, sample_charter_data, cleanup_test_data):
    """Test charter creation."""
    db_cursor.execute("""
        INSERT INTO charters (reserve_number, charter_date, pickup_time, 
                             dropoff_time, pickup_location, dropoff_location,
                             total_amount_due, status)
        VALUES (%(reserve_number)s, %(charter_date)s, %(pickup_time)s,
                %(dropoff_time)s, %(pickup_location)s, %(dropoff_location)s,
                %(total_amount_due)s, %(status)s)
        RETURNING charter_id
    """, sample_charter_data)
    
    charter_id = db_cursor.fetchone()[0]
    assert charter_id is not None
    assert isinstance(charter_id, int)

def test_read_charter_by_reserve_number(db_cursor, sample_charter_data, cleanup_test_data):
    """Test reading charter by reserve_number (business key)."""
    # Create charter
    db_cursor.execute("""
        INSERT INTO charters (reserve_number, charter_date, total_amount_due)
        VALUES (%(reserve_number)s, %(charter_date)s, %(total_amount_due)s)
    """, sample_charter_data)
    
    # Read by reserve_number
    db_cursor.execute("""
        SELECT reserve_number, total_amount_due
        FROM charters
        WHERE reserve_number = %s
    """, (sample_charter_data['reserve_number'],))
    
    result = db_cursor.fetchone()
    assert result is not None
    assert result[0] == sample_charter_data['reserve_number']
    assert result[1] == sample_charter_data['total_amount_due']

def test_update_charter_status(db_cursor, sample_charter_data, cleanup_test_data):
    """Test updating charter status."""
    # Create charter
    db_cursor.execute("""
        INSERT INTO charters (reserve_number, charter_date, total_amount_due, status)
        VALUES (%(reserve_number)s, %(charter_date)s, %(total_amount_due)s, %(status)s)
    """, sample_charter_data)
    
    # Update status
    db_cursor.execute("""
        UPDATE charters
        SET status = 'completed'
        WHERE reserve_number = %s
    """, (sample_charter_data['reserve_number'],))
    
    # Verify update
    db_cursor.execute("""
        SELECT status FROM charters WHERE reserve_number = %s
    """, (sample_charter_data['reserve_number'],))
    
    status = db_cursor.fetchone()[0]
    assert status == 'completed'

def test_delete_charter(db_cursor, sample_charter_data):
    """Test charter deletion."""
    # Create charter
    db_cursor.execute("""
        INSERT INTO charters (reserve_number, charter_date, total_amount_due)
        VALUES (%(reserve_number)s, %(charter_date)s, %(total_amount_due)s)
    """, sample_charter_data)
    
    # Delete charter
    db_cursor.execute("""
        DELETE FROM charters WHERE reserve_number = %s
    """, (sample_charter_data['reserve_number'],))
    
    # Verify deletion
    db_cursor.execute("""
        SELECT COUNT(*) FROM charters WHERE reserve_number = %s
    """, (sample_charter_data['reserve_number'],))
    
    count = db_cursor.fetchone()[0]
    assert count == 0

def test_charter_balance_calculation(db_cursor, sample_charter_data, cleanup_test_data):
    """Test charter balance calculation."""
    # Create charter
    db_cursor.execute("""
        INSERT INTO charters (reserve_number, charter_date, total_amount_due)
        VALUES (%(reserve_number)s, %(charter_date)s, %(total_amount_due)s)
    """, sample_charter_data)
    
    # Add payment
    db_cursor.execute("""
        INSERT INTO payments (reserve_number, amount, payment_date, payment_method)
        VALUES (%s, %s, %s, %s)
    """, (sample_charter_data['reserve_number'], Decimal("200.00"), date.today(), "cash"))
    
    # Calculate balance
    db_cursor.execute("""
        SELECT 
            c.total_amount_due,
            COALESCE(SUM(p.amount), 0) as total_paid,
            c.total_amount_due - COALESCE(SUM(p.amount), 0) as balance
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        WHERE c.reserve_number = %s
        GROUP BY c.reserve_number, c.total_amount_due
    """, (sample_charter_data['reserve_number'],))
    
    result = db_cursor.fetchone()
    assert result[0] == Decimal("450.00")  # total_amount_due
    assert result[1] == Decimal("200.00")  # total_paid
    assert result[2] == Decimal("250.00")  # balance
