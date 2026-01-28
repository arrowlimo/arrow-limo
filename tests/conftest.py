"""
Pytest configuration and shared fixtures.
"""
import pytest
import psycopg2
from decimal import Decimal
from datetime import date, datetime

# Database connection parameters
DB_CONFIG = {
    "host": "localhost",
    "database": "almsdata_test",  # Use separate test database
    "user": "postgres",
    "password": "***REMOVED***"
}

@pytest.fixture(scope="session")
def db_connection():
    """Create database connection for test session."""
    conn = psycopg2.connect(**DB_CONFIG)
    yield conn
    conn.close()

@pytest.fixture(scope="function")
def db_cursor(db_connection):
    """Create cursor with automatic rollback."""
    cursor = db_connection.cursor()
    yield cursor
    db_connection.rollback()  # Rollback after each test
    cursor.close()

@pytest.fixture
def sample_charter_data():
    """Sample charter data for testing."""
    return {
        "reserve_number": "999999",
        "charter_date": date(2026, 1, 22),
        "pickup_time": "14:30:00",
        "dropoff_time": "16:00:00",
        "pickup_location": "YYC Airport",
        "dropoff_location": "Banff",
        "total_amount_due": Decimal("450.00"),
        "status": "assigned"
    }

@pytest.fixture
def sample_payment_data():
    """Sample payment data for testing."""
    return {
        "reserve_number": "999999",
        "amount": Decimal("450.00"),
        "payment_date": date(2026, 1, 22),
        "payment_method": "cash"
    }

@pytest.fixture
def cleanup_test_data(db_cursor):
    """Cleanup test data after tests."""
    yield
    # Delete test records
    db_cursor.execute("DELETE FROM payments WHERE reserve_number = '999999'")
    db_cursor.execute("DELETE FROM charters WHERE reserve_number = '999999'")
