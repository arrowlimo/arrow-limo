"""Pytest configuration and shared fixtures."""

import os

import pytest
import psycopg2
from decimal import Decimal
from datetime import date

DEFAULT_DB_CONFIG = {
    "host": os.getenv("TEST_DB_HOST", os.getenv("LOCAL_DB_HOST", "localhost")),
    "database": os.getenv("TEST_DB_NAME", "almsdata_test"),
    "user": os.getenv("TEST_DB_USER", os.getenv("LOCAL_DB_USER", "postgres")),
    "password": os.getenv(
        "TEST_DB_PASSWORD",
        os.getenv("LOCAL_DB_PASSWORD", "ArrowLimousine"),
    ),
}


def _connect_test_db():
    """Connect to the preferred test DB, falling back to local almsdata if needed."""
    try:
        return psycopg2.connect(**DEFAULT_DB_CONFIG)
    except psycopg2.OperationalError as exc:
        message = str(exc)
        if DEFAULT_DB_CONFIG["database"] != "almsdata_test":
            raise
        if 'database "almsdata_test" does not exist' not in message:
            raise

        fallback_config = {**DEFAULT_DB_CONFIG, "database": "almsdata"}
        return psycopg2.connect(**fallback_config)

@pytest.fixture(scope="session")
def db_connection():
    """Create database connection for test session."""
    conn = _connect_test_db()
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
    db_cursor.connection.rollback()
    # Delete test records
    db_cursor.execute("DELETE FROM payments WHERE reserve_number = '999999'")
    db_cursor.execute("DELETE FROM charters WHERE reserve_number = '999999'")
