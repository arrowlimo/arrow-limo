"""
Database connection manager with auto-reconnect and transaction safety.

Features:
- Auto-reconnect on connection loss
- Transaction status recovery
- Connection pooling support
- Statement timeout protection
- Windows SSPI authentication support
"""

import logging
import os
import sys

import psycopg2
from db_error_handling import DatabaseContext
from psycopg2 import extensions

logger = logging.getLogger(__name__)


def _is_pooler_host(host: str) -> bool:
    """Return True when host appears to be a pooled Pg endpoint (e.g. Neon"
    "pooler)."""

    normalized = (host or "").strip().lower()
    return "-pooler." in normalized or ".pooler." in normalized


class DatabaseConnection:
    """PostgreSQL database connection manager with transaction safety"""

    def __init__(self, config) -> None:
        """
        Initialize database connection.

        Args:
            config: Dictionary with keys: host, port, database, user, password,
            sslmode
        """
        self.config = config
        self.conn = None
        self._connect()

    def _connect(self) -> None:
        """Establish database connection"""
        try:
            cfg = self.config
            # Build connection kwargs, excluding empty sslmode
            conn_kwargs = {
                "host": cfg["host"],
                "port": cfg["port"],
                "database": cfg["database"],
                "user": cfg["user"],
            }

            # Windows integrated authentication (SSPI) support
            # Use SSPI if no password and connecting to localhost on Windows
            password = cfg.get("password", "")
            is_localhost = cfg["host"] in ("localhost", "127.0.0.1", "::1")

            if password:
                conn_kwargs["password"] = password
            elif is_localhost and sys.platform == "win32":
                # Use Windows integrated authentication
                conn_kwargs["gssencmode"] = "disable"
                print(
                    "[DB] Using Windows integrated authentication (SSPI)",
                    flush=True,
                )
            else:
                # Empty password - let pgsql handle it
                conn_kwargs["password"] = ""

            sslmode = cfg.get("sslmode")
            if sslmode:  # Only add sslmode if it's not empty/None
                conn_kwargs["sslmode"] = sslmode

            # Add timeout protection (prevents connection hangs)
            connect_timeout = os.getenv("DB_CONNECT_TIMEOUT", "30")
            conn_kwargs["connect_timeout"] = int(connect_timeout)

            # Add statement timeout via PostgreSQL options unless disabled or
            # incompatible
            disable_startup_options = (
                os.getenv("DB_DISABLE_STARTUP_OPTIONS", "0") == "1"
            )
            if _is_pooler_host(cfg["host"]):
                disable_startup_options = True

            if not disable_startup_options:
                statement_timeout = os.getenv("DB_STATEMENT_TIMEOUT", "300")
                stmt_timeout_ms = int(statement_timeout) * 1000
                conn_kwargs["options"] = (
                    f"-c statement_timeout={stmt_timeout_ms}"
                )

            # Add keepalive settings (prevents idle connection drops on cloud
            # DBs)
            # Always enable for pooler/cloud hosts; opt-in for local via
            # DB_KEEPALIVES=1
            use_keepalives = (
                _is_pooler_host(cfg["host"])
                or os.getenv("DB_KEEPALIVES", "0") == "1"
            )
            if use_keepalives:
                conn_kwargs["keepalives"] = 1
                conn_kwargs["keepalives_idle"] = int(
                    os.getenv("DB_KEEPALIVES_IDLE", "30")
                )
                conn_kwargs["keepalives_interval"] = int(
                    os.getenv("DB_KEEPALIVES_INTERVAL", "10")
                )
                conn_kwargs["keepalives_count"] = int(
                    os.getenv("DB_KEEPALIVES_COUNT", "5")
                )

            attempts = [conn_kwargs]

            # Local Windows fallback strategy:
            # 1) localhost -> 127.0.0.1 (same auth)
            # 2) SSPI/no-password on localhost
            # 3) SSPI/no-password on 127.0.0.1
            if is_localhost and cfg["host"] == "localhost":
                ipv4_kwargs = dict(conn_kwargs)
                ipv4_kwargs["host"] = "127.0.0.1"
                attempts.append(ipv4_kwargs)

            if is_localhost and password and sys.platform == "win32":
                sspi_kwargs = dict(conn_kwargs)
                sspi_kwargs.pop("password", None)
                sspi_kwargs["gssencmode"] = "disable"
                attempts.append(sspi_kwargs)

                if cfg["host"] == "localhost":
                    sspi_ipv4_kwargs = dict(sspi_kwargs)
                    sspi_ipv4_kwargs["host"] = "127.0.0.1"
                    attempts.append(sspi_ipv4_kwargs)

            last_error = None
            for index, kwargs in enumerate(attempts, start=1):
                try:
                    self.conn = psycopg2.connect(**kwargs)
                    self.conn.autocommit = False
                    if index > 1:
                        print(
                            f"[DB] Connected using fallback attempt {index} ",
                            flush=True,
                        )
                    return
                except psycopg2.Error as err:
                    last_error = err

            raise last_error

        except psycopg2.Error as e:
            raise Exception(f"Database connection failed: {e}")

    def _get_cursor(self) -> object:
        """Get database cursor with auto-reconnect"""
        # Check if connection is still open
        if self.conn.closed:
            print("[DB] Connection was closed, reconnecting...", flush=True)
            self._reconnect()

        # Auto-recover from aborted transactions to prevent cascade
        try:
            status = self.conn.get_transaction_status()
            if status == extensions.TRANSACTION_STATUS_INERROR:
                # Silently cleanup error state - this is normal after query
                # errors
                self.conn.rollback()
            elif status == extensions.TRANSACTION_STATUS_ACTIVE:
                # Transaction is active - rollback to start fresh
                self.conn.rollback()
        except Exception:
            # Transaction status check failed, attempt cleanup
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
        try:
            return self.conn.cursor()
        except psycopg2.OperationalError as e:
            if "connection" in str(e).lower() and "closed" in str(e).lower():
                print(
                    "[DB] Connection closed, attempting reconnect...",
                    flush=True,
                )
                self._reconnect()
                return self.conn.cursor()
            raise

    def get_cursor(self) -> object:
        """Public cursor accessor for compatibility"""
        return self._get_cursor()

    def _reconnect(self) -> None:
        """Reconnect to database after connection closes"""
        try:
            cfg = self.config
            conn_kwargs = {
                "host": cfg["host"],
                "port": cfg["port"],
                "database": cfg["database"],
                "user": cfg["user"],
            }

            # Windows integrated authentication (SSPI) support
            password = cfg.get("password", "")
            is_localhost = cfg["host"] in ("localhost", "127.0.0.1", "::1")

            if password:
                conn_kwargs["password"] = password
            elif is_localhost and sys.platform == "win32":
                conn_kwargs["gssencmode"] = "disable"
            else:
                conn_kwargs["password"] = ""

            sslmode = cfg.get("sslmode")
            if sslmode:
                conn_kwargs["sslmode"] = sslmode

            # Add timeout protection (prevents connection hangs)
            connect_timeout = os.getenv("DB_CONNECT_TIMEOUT", "30")
            conn_kwargs["connect_timeout"] = int(connect_timeout)

            # Add keepalive settings (prevents idle connection drops on cloud
            # DBs)
            # Always enable for pooler/cloud hosts; opt-in for local via
            # DB_KEEPALIVES=1
            use_keepalives = (
                _is_pooler_host(cfg["host"])
                or os.getenv("DB_KEEPALIVES", "0") == "1"
            )
            if use_keepalives:
                conn_kwargs["keepalives"] = 1
                conn_kwargs["keepalives_idle"] = int(
                    os.getenv("DB_KEEPALIVES_IDLE", "30")
                )
                conn_kwargs["keepalives_interval"] = int(
                    os.getenv("DB_KEEPALIVES_INTERVAL", "10")
                )
                conn_kwargs["keepalives_count"] = int(
                    os.getenv("DB_KEEPALIVES_COUNT", "5")
                )

            self.conn = psycopg2.connect(**conn_kwargs)
            self.conn.autocommit = False
            print("[DB] Reconnection successful", flush=True)
        except Exception as e:
            logger.error("[DB ERROR] Reconnection failed: %s", e)
            raise

    def cursor(self) -> object:
        """Alias for get_cursor() - provides backward compatibility with code"
        "using .cursor()"""

        return self._get_cursor()

    def commit(self) -> None:
        """Commit transaction - ALWAYS call this after modifications"""
        self.conn.commit()

    def rollback(self) -> None:
        """Rollback transaction on error"""
        self.conn.rollback()

    def safe_scalar(self, sql, params=(), default=0.0) -> object:
        """Execute a scalar SELECT safely: rollback on error and return
        default.

        Args:
            sql: SQL query returning a single row/column
            params: Query parameters tuple
            default: Value to return on error or NULL

        Returns:
            Float value or default on error/NULL
        """
        try:
            with DatabaseContext(self, auto_commit=False) as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
            if not row or row[0] is None:
                return default
            try:
                return float(row[0])
            except (ValueError, TypeError):
                return default
        except Exception as e:
            logger.error(f"safe_scalar failed: {e}")
            return default

    def safe_query(self, sql, params=()) -> object:
        """Execute a SELECT and return all rows safely: rollback on error and
        return empty list.

        Args:
            sql: SQL query
            params: Query parameters tuple

        Returns:
            List of result tuples or [] on error
        """
        try:
            with DatabaseContext(self, auto_commit=False) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
            return rows
        except Exception as e:
            logger.error(f"safe_query failed: {e}")
            return []

    def close(self) -> None:
        """Close database connection"""
        if self.conn:
            self.conn.close()
