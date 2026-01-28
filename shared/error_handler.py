"""
Shared error handling utilities for consistent exception management.
"""

import logging
from functools import wraps
from typing import Optional, Callable


logger = logging.getLogger(__name__)


def handle_db_error(func: Callable):
    """Decorator for database operation error handling."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Database error in {func.__name__}: {e}")
            raise
    return wrapper


def safe_query_execution(query: str, params: Optional[tuple] = None, default=None):
    """Execute query with fallback on error."""
    try:
        from shared.db_utils import execute_query
        return execute_query(query, params)
    except Exception as e:
        logger.warning(f"Query failed, using default: {e}")
        return default


def format_error_message(exception: Exception, context: str = "") -> str:
    """Format exception for user-facing error messages."""
    msg = str(exception)
    if context:
        msg = f"{context}: {msg}"
    return msg
