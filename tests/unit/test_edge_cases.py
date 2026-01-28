"""
Edge case tests (boundaries, limits, special scenarios).
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta

def test_max_charter_routes(db_cursor, cleanup_test_data):
    """Test maximum number of routes in a charter (edge case: 10+)."""
    # Create charter with 15 routes
    db_cursor.execute("""
        INSERT INTO charters (reserve_number, charter_date, total_amount_due)
        VALUES ('999999', %s, %s)
        RETURNING charter_id
    """, (date.today(), Decimal("1500.00")))
    
    charter_id = db_cursor.fetchone()[0]
    
    # Add 15 routes
    for i in range(15):
        db_cursor.execute("""
            INSERT INTO charter_routes (charter_id, stop_number, location, stop_time)
            VALUES (%s, %s, %s, %s)
        """, (charter_id, i + 1, f"Stop {i + 1}", f"{10 + i}:00:00"))
    
    # Verify count
    db_cursor.execute("""
        SELECT COUNT(*) FROM charter_routes WHERE charter_id = %s
    """, (charter_id,))
    
    count = db_cursor.fetchone()[0]
    assert count == 15

def test_midnight_crossing_charter(db_cursor, cleanup_test_data):
    """Test charter that crosses midnight."""
    db_cursor.execute("""
        INSERT INTO charters (reserve_number, charter_date, pickup_time, dropoff_time, total_amount_due)
        VALUES ('999999', %s, '23:30:00', '01:00:00', %s)
    """, (date.today(), Decimal("300.00")))
    
    # Verify charter created
    db_cursor.execute("""
        SELECT pickup_time, dropoff_time 
        FROM charters 
        WHERE reserve_number = '999999'
    """)
    
    result = db_cursor.fetchone()
    assert result is not None
    # Note: dropoff_time is next day but stored as time only

def test_zero_amount_charter(db_cursor, cleanup_test_data):
    """Test charter with $0 amount (trade of services)."""
    db_cursor.execute("""
        INSERT INTO charters (reserve_number, charter_date, total_amount_due)
        VALUES ('999999', %s, %s)
    """, (date.today(), Decimal("0.00")))
    
    db_cursor.execute("""
        SELECT total_amount_due FROM charters WHERE reserve_number = '999999'
    """)
    
    amount = db_cursor.fetchone()[0]
    assert amount == Decimal("0.00")

def test_negative_balance_allowed(db_cursor, cleanup_test_data):
    """Test overpayment scenario (negative balance)."""
    # Create charter
    db_cursor.execute("""
        INSERT INTO charters (reserve_number, charter_date, total_amount_due)
        VALUES ('999999', %s, %s)
    """, (date.today(), Decimal("100.00")))
    
    # Add overpayment
    db_cursor.execute("""
        INSERT INTO payments (reserve_number, amount, payment_date, payment_method)
        VALUES ('999999', %s, %s, 'cash')
    """, (Decimal("150.00"), date.today()))
    
    # Check balance
    db_cursor.execute("""
        SELECT 
            c.total_amount_due - COALESCE(SUM(p.amount), 0) as balance
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        WHERE c.reserve_number = '999999'
        GROUP BY c.reserve_number, c.total_amount_due
    """)
    
    balance = db_cursor.fetchone()[0]
    assert balance == Decimal("-50.00")  # Customer credit

def test_date_boundary_year_end(db_cursor, cleanup_test_data):
    """Test charter on year boundary (Dec 31 → Jan 1)."""
    db_cursor.execute("""
        INSERT INTO charters (reserve_number, charter_date, total_amount_due)
        VALUES ('999999', '2025-12-31', %s)
    """, (Decimal("500.00"),))
    
    db_cursor.execute("""
        SELECT charter_date FROM charters WHERE reserve_number = '999999'
    """)
    
    charter_date = db_cursor.fetchone()[0]
    assert charter_date.year == 2025
    assert charter_date.month == 12
    assert charter_date.day == 31
