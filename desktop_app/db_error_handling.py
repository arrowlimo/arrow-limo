"""
Database Error Handling Utilities
Provides standardized error handling patterns for database operations
"""

import functools
import logging
from collections.abc import Callable
from typing import Any

import psycopg2

try:
    from PyQt6.QtCore import QCoreApplication, Qt
    from PyQt6.QtWidgets import QApplication
except Exception:  # pragma: no cover - non-Qt contexts
    QApplication = None
    QCoreApplication = None
    Qt = None

# Setup logger
logger = logging.getLogger(__name__)

_busy_cursor_depth = 0


def _begin_busy_cursor() -> bool:
    """Show wait cursor for nested DB operations in desktop UI contexts."""
    global _busy_cursor_depth
    if QApplication is None or Qt is None:
        return False

    app = QApplication.instance()
    if app is None:
        return False

    try:
        if _busy_cursor_depth == 0:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            if QCoreApplication is not None:
                QCoreApplication.processEvents()
        _busy_cursor_depth += 1
        return True
    except Exception:
        return False


def _end_busy_cursor(started: bool) -> None:
    """Restore wait cursor after nested DB operation completes."""
    global _busy_cursor_depth
    if not started or QApplication is None:
        return

    try:
        if _busy_cursor_depth > 0:
            _busy_cursor_depth -= 1
        if _busy_cursor_depth == 0:
            QApplication.restoreOverrideCursor()
            if QCoreApplication is not None:
                QCoreApplication.processEvents()
    except Exception as _e:
        logger.debug('Suppressed: %s', _e)
def db_operation(
    func: Callable = None,
    *,
    rollback_on_error: bool = True,
    close_cursor: bool = True,
    log_errors: bool = True,
) -> Callable:
    """
    Decorator to add comprehensive error handling to database operations.

    Args:
        rollback_on_error: Call conn.rollback() on exceptions
        close_cursor: Close cursor in finally block
        log_errors: Log exceptions before re-raising

    Usage:
        @db_operation
        def my_db_query(self):
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM table")
            return cur.fetchall()
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> Any:
            conn = None
            cur = None

            # Try to find connection from args/kwargs or self
            if args and hasattr(args[0], "conn"):
                conn = args[0].conn
            elif args and hasattr(args[0], "db"):
                db = args[0].db
                conn = db.connection if hasattr(db, "connection") else db
            elif "conn" in kwargs:
                conn = kwargs["conn"]

            try:
                result = fn(*args, **kwargs)

                # Auto-commit if connection available
                if conn and hasattr(conn, "commit"):
                    try:
                        conn.commit()
                    except Exception as _e:
                        logger.debug('Suppressed: %s', _e)  # Some operations don't need commit

                return result

            except psycopg2.Error as e:
                if log_errors:
                    logger.error(f"Database error in {fn.__name__}: {e}")

                if rollback_on_error and conn:
                    try:
                        conn.rollback()
                    except Exception as rb_err:
                        if log_errors:
                            logger.error(f"Rollback failed: {rb_err}")

                raise

            except Exception as e:
                if log_errors:
                    logger.error(f"Error in {fn.__name__}: {e}")
                raise

            finally:
                if close_cursor and cur:
                    try:
                        cur.close()
                    except Exception as _e:
                        logger.debug('Suppressed: %s', _e)
        return wrapper

    if func is None:
        return decorator
    return decorator(func)


def safe_execute(
    cursor,
    query: str,
    params: tuple | None = None,
    conn=None,
    operation_name: str = "database operation",
) -> Any | None:
    """
    Safely execute a database query with error handling.

    Args:
        cursor: Database cursor
        query: SQL query with %s placeholders
        params: Query parameters
        conn: Connection for rollback
        operation_name: Description for error messages

    Returns:
        Query result or None on error

    Example:
        cur = conn.cursor()
        result = safe_execute(
            cur,
            "SELECT * FROM users WHERE id = %s",
            (user_id,),
            conn,
            "fetch user"
        )
    """
    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        return cursor

    except psycopg2.Error as e:
        logger.error(f"Database error during {operation_name}: {e}")
        logger.debug(f"Query: {query[:200]}")

        if conn:
            try:
                conn.rollback()
            except Exception as rb_err:
                logger.error(f"Rollback failed: {rb_err}")

        # Check for connection errors and provide helpful message
        error_str = str(e).lower()
        if (
            ("connection" in error_str and "closed" in error_str)
            or ("server closed" in error_str)
            or ("connection refused" in error_str)
        ):
            # Connection error - enhance the message
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(
                None,
                "Database Connection Error",
                f"❌ Cannot save: Database connection was lost.\n\n"
                f"The connection to the database is no longer available.\n"
                f"Please check if PostgreSQL is running and restart the"
                f"application.\n\n"
                f"Technical details: {e}",
            )

        raise

    except Exception as e:
        logger.error(f"Unexpected error during {operation_name}: {e}")
        raise


def safe_commit(conn, operation_name: str = "commit") -> bool:
    """
    Safely commit a transaction with error handling.

    Args:
        conn: Database connection
        operation_name: Description for error messages

    Returns:
        True if successful, False on error
    """
    try:
        conn.commit()
        return True
    except psycopg2.Error as e:
        logger.error(f"Commit failed during {operation_name}: {e}")
        try:
            conn.rollback()
        except Exception as rb_err:
            logger.error(f"Rollback after commit failure: {rb_err}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during commit: {e}")
        return False


def safe_rollback(conn, operation_name: str = "rollback") -> bool:
    """
    Safely rollback a transaction with error handling.

    Args:
        conn: Database connection
        operation_name: Description for error messages

    Returns:
        True if successful, False on error
    """
    try:
        conn.rollback()
        return True
    except Exception as e:
        logger.error(f"Rollback failed during {operation_name}: {e}")
        return False


def table_exists(conn, table_name: str, schema: str = "public") -> bool:
    """Return True when a table exists in the current database schema."""
    try:
        with DatabaseContext(conn, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = %s
                      AND table_name = %s
                )
                """,
                (schema, table_name),
            )
            return bool(cur.fetchone()[0])
    except Exception as e:
        logger.debug(
            "table_exists check failed for %s.%s: %s",
            schema,
            table_name,
            e,
        )
        return False


class DatabaseContext:
    """
    Context manager for database operations with automatic cleanup.

    Usage:
        with DatabaseContext(conn) as cur:
            cur.execute("SELECT * FROM table")
            return cur.fetchall()
        # Auto-commits on success, auto-rollbacks on exception
    """

    def __init__(
        self, conn, auto_commit: bool = True, auto_rollback: bool = True
    ) -> None:
        self.conn = conn
        self.cursor = None
        self.auto_commit = auto_commit
        self.auto_rollback = auto_rollback
        self.exception_occurred = False
        self._busy_cursor_started = False

    def __enter__(self) -> object:
        self._busy_cursor_started = _begin_busy_cursor()
        try:
            self.cursor = self.conn.cursor()
            return self.cursor
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            err = str(e).lower()
            if any(k in err for k in ("ssl", "closed", "connection")):
                logger.warning(f"DB connection dropped, reconnecting: {e}")
                if hasattr(self.conn, "_reconnect"):
                    self.conn._reconnect()
                    self.cursor = self.conn.cursor()
                    return self.cursor
            logger.error(f"Failed to create cursor: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to create cursor: {e}")
            _end_busy_cursor(self._busy_cursor_started)
            self._busy_cursor_started = False
            raise

    def __exit__(self, exc_type, exc_val, exc_tb) -> object:
        try:
            if exc_type is not None:
                # Exception occurred
                self.exception_occurred = True
                if self.auto_rollback:
                    try:
                        self.conn.rollback()
                        logger.debug(
                            "Transaction rolled back due to exception"
                        )
                    except Exception as e:
                        logger.error(f"Rollback failed: {e}")
            else:
                # Success
                if self.auto_commit:
                    try:
                        self.conn.commit()
                        logger.debug("Transaction committed")
                    except Exception as e:
                        logger.error(f"Commit failed: {e}")
                        try:
                            self.conn.rollback()
                        except Exception as _e:
                            logger.debug('Suppressed: %s', _e)
                        raise
        finally:
            if self.cursor:
                try:
                    self.cursor.close()
                except Exception as e:
                    logger.debug(f"Cursor close failed: {e}")
            _end_busy_cursor(self._busy_cursor_started)
            self._busy_cursor_started = False

        return False  # Re-raise exceptions


# Convenience function for quick database operations
def execute_query(
    conn,
    query: str,
    params: tuple | None = None,
    fetch: str = "all",
    commit: bool = False,
) -> Any | None:
    """
    Execute a query with full error handling.

    Args:
        conn: Database connection
        query: SQL query
        params: Query parameters
        fetch: 'all', 'one', 'many', or None
        commit: Whether to commit after execution

    Returns:
        Query results based on fetch parameter

    Example:
        results = execute_query(
            conn,
            "SELECT * FROM users WHERE active = %s",
            (True,),
            fetch='all',
            commit=False
        )
    """
    try:
        with DatabaseContext(conn, auto_commit=commit) as cur:
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)

            if fetch == "all":
                return cur.fetchall()
            elif fetch == "one":
                return cur.fetchone()
            elif fetch == "many":
                return cur.fetchmany()
            else:
                return None

    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        logger.debug(f"Query: {query[:200]}")
        raise


def is_connection_error(exception) -> object:
    """
    Check if an exception is a database connection error.

    Args:
        exception: The exception to check

    Returns:
        bool: True if it's a connection error
    """
    if not isinstance(
        exception, (psycopg2.OperationalError, psycopg2.InterfaceError)
    ):
        return False

    error_str = str(exception).lower()
    connection_keywords = [
        "connection",
        "closed",
        "refused",
        "timeout",
        "unreachable",
    ]
    return any(keyword in error_str for keyword in connection_keywords)


def get_friendly_error_message(exception) -> object:
    """
    Convert a database exception into a user-friendly error message.

    Args:
        exception: The exception to convert

    Returns:
        str: User-friendly error message
    """
    error_str = str(exception).lower()

    if "connection" in error_str and "closed" in error_str:
        return (
            "❌ Cannot save: Database connection is closed.\n\n"
            "The database connection was lost. This usually happens when:\n"
            " • PostgreSQL service stopped\n"
            " • Network connection was interrupted\n"
            " • Database server restarted\n\n"
            "Please restart the application or check your database connection."
        )
    elif "connection refused" in error_str or "could not connect" in error_str:
        return (
            "❌ Cannot connect to database server.\n\n"
            "The database server is not responding. Please check:\n"
            " • Is PostgreSQL service running?\n"
            " • Is the server address correct?\n"
            " • Is your network connection working?\n"
        )
    elif "timeout" in error_str or "timed out" in error_str:
        return (
            "❌ Database operation timed out.\n\n"
            "The database took too long to respond. This could be due to:\n"
            " • Network issues\n"
            " • Server overload\n"
            " • Long-running queries\n\n"
            "Please try again."
        )
    elif "authentication failed" in error_str or "password" in error_str:
        return (
            "❌ Database authentication failed.\n\n"
            "Could not authenticate with the database. Please check:\n"
            " • Username and password are correct\n"
            " • Database user has proper permissions\n"
        )
    else:
        # Return original error with a friendly prefix
        return f"❌ Database error:\n\n{exception}"


def show_connection_error(parent=None, exception=None) -> None:
    """
    Show a user-friendly dialog for connection errors.

    Args:
        parent: Parent widget for the dialog
        exception: The exception that occurred (optional)
    """
    from PyQt6.QtWidgets import QMessageBox

    if exception:
        message = get_friendly_error_message(exception)
    else:
        message = (
            "❌ Database connection error.\n\n"
            "Cannot communicate with the database.\n"
            "Please check your connection and restart the application."
        )

    QMessageBox.critical(parent, "Database Connection Error", message)


__all__ = [
    "DatabaseContext",
    "db_operation",
    "execute_query",
    "get_friendly_error_message",
    "is_connection_error",
    "safe_commit",
    "safe_execute",
    "safe_rollback",
    "show_connection_error",
]
