"""
Login Manager: Database-backed authentication with hashing & session management
Handles: credential validation, password hashing, role checks,
activity tracking
"""

import hashlib
import hmac
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv

def _load_runtime_env() -> None:
    """Load environment files from common source/exe locations."""
    candidates = []

    this_file = Path(__file__).resolve()
    candidates.extend(
        [
            this_file.parents[1] / ".env",
            this_file.parents[1] / ".env.neon",
        ]
    )

    cwd = Path.cwd().resolve()
    candidates.extend(
        [
            cwd / ".env",
            cwd / ".env.neon",
            cwd.parent / ".env",
            cwd.parent / ".env.neon",
            Path("L:/limo/.env"),
            Path("L:/limo/.env.neon"),
            Path("L:/Confirmation/.env"),
            Path("L:/Confirmation/.env.neon"),
        ]
    )

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend(
            [
                exe_dir / ".env",
                exe_dir / ".env.neon",
                exe_dir.parent / ".env",
                exe_dir.parent / ".env.neon",
            ]
        )

    seen = set()
    for env_path in candidates:
        env_key = str(env_path).lower()
        if env_key in seen:
            continue
        seen.add(env_key)
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)


_load_runtime_env()

try:
    import bcrypt  # noqa: E402
except Exception:  # pragma: no cover - optional dependency fallback
    bcrypt = None
import psycopg2  # noqa: E402

try:  # noqa: E402
    # Package import path (desktop_app.*) used by some entry points.
    from desktop_app.db_error_handling import DatabaseContext
except Exception:  # pragma: no cover - fallback for top-level module execution
    # Direct module import path when running from desktop_app/ as cwd.
    from db_error_handling import DatabaseContext

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when authentication fails"""


class AccountLockedError(AuthenticationError):
    """Raised when account is locked due to failed login attempts"""


class LoginManager:
    """Database-backed login system with bcrypt hashing and role enforcement"""

    # Security settings
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15
    SESSION_TIMEOUT_MINUTES = 30
    PASSWORD_MIN_LENGTH = 7
    PBKDF2_ITERATIONS = 260000

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify bcrypt and legacy PBKDF2 password hashes."""
        if not stored_hash:
            return False

        try:
            if stored_hash.startswith("pbkdf2_sha256$"):
                _, iterations, salt_hex, digest_hex = stored_hash.split("$", 3)
                computed = hashlib.pbkdf2_hmac(
                    "sha256",
                    password.encode("utf-8"),
                    bytes.fromhex(salt_hex),
                    int(iterations),
                ).hex()
                return hmac.compare_digest(computed, digest_hex)

            # bcrypt hash format, requires bcrypt module.
            if stored_hash.startswith("$2") and bcrypt is None:
                logger.error(
                    "bcrypt hash encountered but bcrypt module is unavailable"
                )
                return False

            return bcrypt.checkpw(
                password.encode("utf-8"), stored_hash.encode("utf-8")
            )
        except Exception:
            return False

    def __init__(self):
        """Initialize database connection"""
        self.token_file = Path.home() / ".limo_auth_token"
        self._refresh_db_config()

    def _refresh_db_config(self):
        """Refresh database configuration from environment variables"""
        self.db_host = os.environ.get("DB_HOST", "localhost")
        self.db_port = int(os.environ.get("DB_PORT", 5432))
        self.db_name = os.environ.get("DB_NAME", "almsdata")
        self.db_user = os.environ.get("DB_USER", "postgres")
        self.db_password = os.environ.get("DB_PASSWORD", "")
        sslmode = os.environ.get("DB_SSLMODE", "prefer")
        self.db_sslmode = sslmode.strip() or "prefer"

    def _get_connection(self):
        """Create database connection - refresh config first"""
        self._refresh_db_config()  # Always get latest env vars
        return psycopg2.connect(
            host=self.db_host,
            port=self.db_port,
            dbname=self.db_name,
            user=self.db_user,
            password=self.db_password,
            sslmode=self.db_sslmode,
        )

    def authenticate(
        self, username: str, password: str, ip_address: str = "127.0.0.1"
    ) -> Dict:
        """
        Authenticate user credentials against database

        Args:
            username: Username
            password: Plain-text password
            ip_address: IP address of login attempt

        Returns:
            Dict with user_id, username, role, permissions

        Raises:
            AuthenticationError: Invalid credentials
            AccountLockedError: Account locked due to failed attempts
        """
        # Convert 'localhost' to 127.0.0.1 for inet column
        if ip_address.lower() == "localhost":
            ip_address = "127.0.0.1"

        username = username.strip()
        if not username or not password:
            raise AuthenticationError("Username and password required")

        try:
            with DatabaseContext(
                self._get_connection(), auto_commit=False
            ) as cur:
                # Check if account is locked
                cur.execute(
                    """
                    SELECT user_id, locked_until
                    FROM users
                    WHERE username = %s
                """,
                    (username,),
                )

                user_row = cur.fetchone()
                if not user_row:
                    raise AuthenticationError("Invalid username or password")

                user_id, locked_until = user_row

                if locked_until and locked_until > datetime.now():
                    minutes_left = int(
                        (locked_until - datetime.now()).total_seconds() / 60
                    )
                    raise AccountLockedError(
                        f"Account locked. Try again in {minutes_left} minutes"
                    )

                # Get user credentials
                cur.execute(
                    """
                    SELECT user_id, username, email, password_hash, role,
                    status,
                           permissions, failed_login_attempts, session_version
                    FROM users
                    WHERE username = %s
                """,
                    (username,),
                )

                user = cur.fetchone()
                if not user:
                    raise AuthenticationError("Invalid username or password")

                (
                    uid,
                    uname,
                    email,
                    pwd_hash,
                    role,
                    status,
                    perms,
                    failed_attempts,
                    sess_ver,
                ) = user

                # Check status
                if status and status.lower() != "active":
                    raise AuthenticationError(f"Account is {status}")

                # Verify password
                pwd_check_result = self._verify_password(password, pwd_hash)
                
                # PASSWORD IS WRONG - handle failure
                if not pwd_hash or not pwd_check_result:
                    # Increment failed attempts
                    failed_attempts = (failed_attempts or 0) + 1
                    locked_until = None
                    if failed_attempts >= self.MAX_FAILED_ATTEMPTS:
                        locked_until = datetime.now() + timedelta(
                            minutes=self.LOCKOUT_DURATION_MINUTES
                        )

                    # Update DB with failed attempt
                    with DatabaseContext(
                        self._get_connection(), auto_commit=True
                    ) as cur:
                        if locked_until:
                            cur.execute(
                                """
                                UPDATE users
                                SET failed_login_attempts = %s, locked_until = %s,
                                updated_at = NOW()
                                WHERE user_id = %s
                            """,
                                (failed_attempts, locked_until, uid),
                            )
                            raise AccountLockedError(
                                f"Account locked after {self.MAX_FAILED_ATTEMPTS} "
                                f"failed attempts"
                            )
                        else:
                            cur.execute(
                                """
                                UPDATE users
                                SET failed_login_attempts = %s, updated_at = NOW()
                                WHERE user_id = %s
                            """,
                                (failed_attempts, uid),
                            )
                            raise AuthenticationError("Invalid username or password")

            # PASSWORD IS CORRECT - Login successful: reset failed attempts and update last_login
            with DatabaseContext(
                self._get_connection(), auto_commit=True
            ) as cur:
                cur.execute(
                    """
                    UPDATE users
                    SET failed_login_attempts = 0,
                        locked_until = NULL,
                        last_login = NOW(),
                        last_ip = %s,
                        last_activity = NOW(),
                        updated_at = NOW()
                    WHERE user_id = %s
                """,
                    (ip_address, uid),
                )

            # Parse permissions JSON
            permissions = {}
            if perms:
                try:
                    permissions = (
                        json.loads(perms) if isinstance(perms, str) else perms
                    )
                except Exception:
                    logger.error("Failed to parse permissions JSON")
                    permissions = {}

            # Return auth user dict
            auth_user = {
                "user_id": uid,
                "username": uname,
                "email": email,
                "role": role or "user",
                "permissions": permissions,
                "session_version": sess_ver or 1,
                "login_time": datetime.now(),
            }

            return auth_user

        except (AuthenticationError, AccountLockedError):
            raise
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise AuthenticationError(f"Authentication failed: {e}")  # noqa: B904

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt when available, else PBKDF2."""
        if len(password) < self.PASSWORD_MIN_LENGTH:
            raise ValueError(
                f"Password must be at least {self.PASSWORD_MIN_LENGTH}"
                f"characters"
            )
        if bcrypt is not None:
            return bcrypt.hashpw(
                password.encode("utf-8"), bcrypt.gensalt(rounds=12)
            ).decode("utf-8")

        # Fallback keeps app usable even if bcrypt wheel is missing.
        salt = os.urandom(16).hex()
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            self.PBKDF2_ITERATIONS,
        ).hex()
        logger.warning("bcrypt unavailable, using PBKDF2 password hashing")
        return f"pbkdf2_sha256${self.PBKDF2_ITERATIONS}${salt}${digest}"

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: str = "user",
        permissions: Optional[Dict] = None,
    ) -> int:
        """Create new user in database"""
        username = username.strip()
        email = email.strip()

        if not username or not email or not password:
            raise ValueError("Username, email, and password required")

        if len(password) < self.PASSWORD_MIN_LENGTH:
            raise ValueError(
                f"Password must be at least {self.PASSWORD_MIN_LENGTH}"
                f"characters"
            )

        pwd_hash = self.hash_password(password)
        perms_json = json.dumps(permissions or {})

        try:
            with DatabaseContext(
                self._get_connection(), auto_commit=True
            ) as cur:
                cur.execute(
                    """
                    INSERT INTO users (username, email, password_hash, role,
                    status,
                                     permissions, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                    RETURNING user_id
                """,
                    (username, email, pwd_hash, role, "active", perms_json),
                )

                user_id = cur.fetchone()[0]
                return user_id
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            raise

    def update_last_activity(
        self, user_id: int, ip_address: str = "127.0.0.1"
    ) -> None:
        """Update user's last activity timestamp"""
        # Convert 'localhost' to 127.0.0.1 for inet column
        if ip_address.lower() == "localhost":
            ip_address = "127.0.0.1"

        try:
            with DatabaseContext(
                self._get_connection(), auto_commit=True
            ) as cur:
                cur.execute(
                    """
                    UPDATE users
                    SET last_activity = NOW(), last_ip = %s, updated_at = NOW()
                    WHERE user_id = %s
                """,
                    (ip_address, user_id),
                )
        except Exception as e:
            logger.error(f"Failed to update last activity: {e}")

    def save_remember_token(
        self, user_id: int, token_expiry_days: int = 30
    ) -> None:
        """Save remember-me token (not password!)"""
        token_hash = hashlib.sha256(
            f"{user_id}_{datetime.now().isoformat()}".encode()
        ).hexdigest()

        token_data = {
            "user_id": user_id,
            "token_hash": token_hash,
            "expires": (
                datetime.now() + timedelta(days=token_expiry_days)
            ).isoformat(),
        }

        try:
            with open(self.token_file, "w") as f:
                json.dump(token_data, f)
            # Restrict file permissions to owner only
            os.chmod(self.token_file, 0o600)
        except Exception as e:
            print(f"Warning: Could not save remember token: {e}")

    def load_remember_token(self) -> Optional[int]:
        """Load and validate remember-me token"""
        if not self.token_file.exists():
            return None

        try:
            with open(self.token_file, "r") as f:
                token_data = json.load(f)

            expires = datetime.fromisoformat(token_data.get("expires", ""))
            if expires > datetime.now():
                return token_data.get("user_id")
            else:
                self.token_file.unlink()  # Delete expired token
                return None
        except Exception:
            return None

    def clear_remember_token(self) -> None:
        """Clear saved remember-me token"""
        if self.token_file.exists():
            try:
                self.token_file.unlink()
            except Exception:
                pass

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Fetch user by ID (for remember-me restoration)"""
        try:
            with DatabaseContext(
                self._get_connection(), auto_commit=False
            ) as cur:
                cur.execute(
                    """
                    SELECT user_id, username, email, role, status, permissions,
                    session_version
                    FROM users
                    WHERE user_id = %s AND status = %s
                """,
                    (user_id, "active"),
                )

                row = cur.fetchone()
                if not row:
                    return None

                uid, uname, email, role, status, perms, sess_ver = row
                permissions = {}
                if perms:
                    try:
                        permissions = (
                            json.loads(perms)
                            if isinstance(perms, str)
                            else perms
                        )
                    except Exception:
                        logger.error("Failed to parse permissions JSON")

                return {
                    "user_id": uid,
                    "username": uname,
                    "email": email,
                    "role": role or "user",
                    "permissions": permissions,
                    "session_version": sess_ver or 1,
                    "login_time": datetime.now(),
                }
        except Exception as e:
            logger.error(f"Failed to get user by ID: {e}")
            return None
