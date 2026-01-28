"""
Shared utilities package for consistent code patterns across the app.
"""

from .db_utils import get_db_connection, db_cursor, execute_query, execute_update
from .currency_utils import calculate_gst, round_currency, format_currency, validate_currency
from .date_utils import parse_date, format_date, date_range, business_days_between
from .error_handler import handle_db_error, safe_query_execution, format_error_message

__all__ = [
    'get_db_connection', 'db_cursor', 'execute_query', 'execute_update',
    'calculate_gst', 'round_currency', 'format_currency', 'validate_currency',
    'parse_date', 'format_date', 'date_range', 'business_days_between',
    'handle_db_error', 'safe_query_execution', 'format_error_message',
]
