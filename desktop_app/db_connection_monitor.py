"""
Database Connection Monitor for Desktop Application

Provides real-time monitoring of database connection health and displays
warnings when the connection is lost. This prevents confusing error messages
like "connection already closed" by proactively detecting and reporting
connection issues.
"""

import logging

import psycopg2
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)


class DatabaseConnectionMonitor(QObject):
    """Monitor database connection health and emit signals on status changes"""

    # Signals
    connection_lost = pyqtSignal()  # Emitted when connection is lost
    connection_restored = pyqtSignal()  # Emitted when connection is restored
    # Emitted on any status change (online, message)
    status_changed = pyqtSignal(bool, str)

    def __init__(self, db_connection, check_interval_ms=15000, parent=None) -> None:
        """
        Initialize the connection monitor.

        Args:
            db_connection: DatabaseConnection instance to monitor
            check_interval_ms: How often to check connection (default: 15
            seconds)
            parent: Qt parent object
        """
        super().__init__(parent)
        self.db = db_connection
        self.check_interval_ms = check_interval_ms
        self.is_online = True  # Assume online at start
        self.last_error = None
        self.warning_shown = False  # Track if warning dialog has been shown

        # Setup timer for periodic checks
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_connection)

    def start_monitoring(self) -> None:
        """Start periodic connection health checks"""
        logger.info(
            f"Starting database connection monitoring (interval:"
            f"{self.check_interval_ms}ms)"
        )
        self.check_connection()  # Initial check
        self.timer.start(self.check_interval_ms)

    def stop_monitoring(self) -> None:
        """Stop monitoring"""
        logger.info("Stopping database connection monitoring")
        self.timer.stop()

    def check_connection(self) -> None:
        """
        Check if database connection is alive by running a simple query.
        Emits signals if status changes.
        """
        try:
            # Try a simple query — use get_cursor() so auto-reconnect fires
            cur = self.db.get_cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()

            # Connection is good
            if not self.is_online:
                # Connection was restored
                logger.info("✅ Database connection restored")
                self.is_online = True
                self.warning_shown = False
                self.last_error = None
                self.connection_restored.emit()
                self.status_changed.emit(True, "Database connection restored")

        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            # Connection error - check if connection is closed
            error_msg = str(e).lower()

            if self.is_online:
                # Connection just went down
                logger.error(f"❌ Database connection lost: {e}")
                self.is_online = False
                self.last_error = str(e)
                self.connection_lost.emit()

                # Provide user-friendly message
                if "closed" in error_msg or "connection" in error_msg:
                    status_msg = (
                        "Database connection closed - Cannot save or load data"
                    )
                elif "refused" in error_msg:
                    status_msg = (
                        "Database server not responding - "
                        "Check if PostgreSQL is running"
                    )
                elif "timeout" in error_msg:
                    status_msg = (
                        "Database connection timeout - "
                        "Server may be unreachable"
                    )
                else:
                    status_msg = f"Database connection lost: {e}"

                self.status_changed.emit(False, status_msg)

                # Show warning dialog once
                if not self.warning_shown:
                    self._show_connection_warning(status_msg)
                    self.warning_shown = True

        except Exception as e:
            # Reconnect attempt failed or other unexpected error — treat as
            # offline so status bar and warning dialog are updated correctly
            logger.warning(f"Connection check error: {e}")
            if self.is_online:
                self.is_online = False
                self.last_error = str(e)
                self.connection_lost.emit()
                status_msg = "Database connection lost - Cannot save or load data"
                self.status_changed.emit(False, status_msg)
                if not self.warning_shown:
                    self._show_connection_warning(status_msg)
                    self.warning_shown = True

    def _show_connection_warning(self, message) -> None:
        """Show a warning dialog to the user"""
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("Database Connection Lost")
        msg_box.setText("⚠️ Cannot connect to the database")
        msg_box.setInformativeText(
            f"{message} \n\n"
            "You will not be able to save or load data until the connection"
            "is restored.\n\n"
            "Possible solutions:\n"
            " • Check if PostgreSQL service is running\n"
            " • Verify network connection (if using cloud database)\n"
            " • Restart the application\n"
        )
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()

    def get_status_message(self) -> object:
        """Get current connection status as a string"""
        if self.is_online:
            return "✅ Database: Connected"
        else:
            return f"❌ Database: {self.last_error or 'Disconnected'}"


def enhance_error_message(exception) -> object:
    """
    Convert a database exception into a user-friendly error message.

    Args:
        exception: The exception to enhance

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
            "Please check your database connection and try again."
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


def wrap_db_operation(operation_func) -> object:
    """
    Decorator to wrap database operations with enhanced error handling.

    Usage:
        @wrap_db_operation
        def save_data(self):
            # database operations here
            pass
    """

    def wrapper(*args, **kwargs) -> object:
        try:
            return operation_func(*args, **kwargs)
        except (
            psycopg2.OperationalError,
            psycopg2.InterfaceError,
            psycopg2.Error,
        ) as e:
            # Show user-friendly error message
            friendly_msg = enhance_error_message(e)
            QMessageBox.critical(None, "Database Error", friendly_msg)
            raise  # Re-raise for logging purposes
        except Exception as e:
            # Unexpected error - show original
            QMessageBox.critical(
                None, "Error", f"An unexpected error occurred:\n\n{e}"
            )
            raise

    return wrapper
