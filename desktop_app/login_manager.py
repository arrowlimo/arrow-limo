"""
Login Manager: Database-backed authentication with hashing & session management
Handles: credential validation, password hashing, role checks, activity tracking
"""

import os
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Tuple

import psycopg2
import bcrypt


class AuthenticationError(Exception):
    """Raised when authentication fails"""
    pass


class AccountLockedError(AuthenticationError):
    """Raised when account is locked due to failed login attempts"""
    pass


class LoginManager:
    """Database-backed login system with bcrypt hashing and role enforcement"""
    
    # Security settings
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15
    SESSION_TIMEOUT_MINUTES = 30
    PASSWORD_MIN_LENGTH = 8
    
    def __init__(self):
        """Initialize database connection"""
        self.db_host = os.environ.get('DB_HOST', 'localhost')
        self.db_port = int(os.environ.get('DB_PORT', 5432))
        self.db_name = os.environ.get('DB_NAME', 'almsdata')
        self.db_user = os.environ.get('DB_USER', 'postgres')
        self.db_password = os.environ.get('DB_PASSWORD', '***REMOVED***')
        self.db_sslmode = os.environ.get('DB_SSLMODE', 'prefer')
        self.token_file = Path.home() / '.limo_auth_token'
    
    def _get_connection(self):
        """Create database connection"""
        return psycopg2.connect(
            host=self.db_host,
            port=self.db_port,
            dbname=self.db_name,
            user=self.db_user,
            password=self.db_password,
            sslmode=self.db_sslmode
        )
    
    def authenticate(self, username: str, password: str, ip_address: str = '127.0.0.1') -> Dict:
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
        if ip_address.lower() == 'localhost':
            ip_address = '127.0.0.1'
        
        username = username.strip()
        if not username or not password:
            raise AuthenticationError('Username and password required')
        
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            # Check if account is locked
            cur.execute('''
                SELECT user_id, locked_until 
                FROM users 
                WHERE username = %s
            ''', (username,))
            
            user_row = cur.fetchone()
            if not user_row:
                raise AuthenticationError('Invalid username or password')
            
            user_id, locked_until = user_row
            
            if locked_until and locked_until > datetime.now():
                minutes_left = int((locked_until - datetime.now()).total_seconds() / 60)
                raise AccountLockedError(f'Account locked. Try again in {minutes_left} minutes')
            
            # Get user credentials
            cur.execute('''
                SELECT user_id, username, email, password_hash, role, status, 
                       permissions, failed_login_attempts, session_version
                FROM users 
                WHERE username = %s
            ''', (username,))
            
            user = cur.fetchone()
            if not user:
                raise AuthenticationError('Invalid username or password')
            
            uid, uname, email, pwd_hash, role, status, perms, failed_attempts, sess_ver = user
            
            # Check status
            if status and status.lower() != 'active':
                raise AuthenticationError(f'Account is {status}')
            
            # Verify password
            if not pwd_hash or not bcrypt.checkpw(password.encode('utf-8'), pwd_hash.encode('utf-8')):
                # Increment failed attempts
                failed_attempts = (failed_attempts or 0) + 1
                if failed_attempts >= self.MAX_FAILED_ATTEMPTS:
                    locked_until = datetime.now() + timedelta(minutes=self.LOCKOUT_DURATION_MINUTES)
                    cur.execute('''
                        UPDATE users 
                        SET failed_login_attempts = %s, locked_until = %s, updated_at = NOW()
                        WHERE user_id = %s
                    ''', (failed_attempts, locked_until, uid))
                    conn.commit()
                    raise AccountLockedError(f'Account locked after {self.MAX_FAILED_ATTEMPTS} failed attempts')
                else:
                    cur.execute('''
                        UPDATE users 
                        SET failed_login_attempts = %s, updated_at = NOW()
                        WHERE user_id = %s
                    ''', (failed_attempts, uid))
                    conn.commit()
                    raise AuthenticationError('Invalid username or password')
            
            # Login successful: reset failed attempts and update last_login
            cur.execute('''
                UPDATE users 
                SET failed_login_attempts = 0, 
                    locked_until = NULL,
                    last_login = NOW(),
                    last_ip = %s,
                    last_activity = NOW(),
                    updated_at = NOW()
                WHERE user_id = %s
            ''', (ip_address, uid))
            conn.commit()
            
            # Parse permissions JSON
            permissions = {}
            if perms:
                try:
                    permissions = json.loads(perms) if isinstance(perms, str) else perms
                except:
                    try:
                        self.db.rollback()
                    except:
                        pass
                    permissions = {}
            
            # Return auth user dict
            auth_user = {
                'user_id': uid,
                'username': uname,
                'email': email,
                'role': role or 'user',
                'permissions': permissions,
                'session_version': sess_ver or 1,
                'login_time': datetime.now()
            }
            
            return auth_user
            
        finally:
            cur.close()
            conn.close()
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        if len(password) < self.PASSWORD_MIN_LENGTH:
            raise ValueError(f'Password must be at least {self.PASSWORD_MIN_LENGTH} characters')
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
    
    def create_user(self, username: str, email: str, password: str, role: str = 'user', 
                   permissions: Optional[Dict] = None) -> int:
        """Create new user in database"""
        username = username.strip()
        email = email.strip()
        
        if not username or not email or not password:
            raise ValueError('Username, email, and password required')
        
        if len(password) < self.PASSWORD_MIN_LENGTH:
            raise ValueError(f'Password must be at least {self.PASSWORD_MIN_LENGTH} characters')
        
        pwd_hash = self.hash_password(password)
        perms_json = json.dumps(permissions or {})
        
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute('''
                INSERT INTO users (username, email, password_hash, role, status, 
                                 permissions, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING user_id
            ''', (username, email, pwd_hash, role, 'active', perms_json))
            
            user_id = cur.fetchone()[0]
            conn.commit()
            return user_id
            
        finally:
            cur.close()
            conn.close()
    
    def update_last_activity(self, user_id: int, ip_address: str = '127.0.0.1') -> None:
        """Update user's last activity timestamp"""
        # Convert 'localhost' to 127.0.0.1 for inet column
        if ip_address.lower() == 'localhost':
            ip_address = '127.0.0.1'
        
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute('''
                UPDATE users 
                SET last_activity = NOW(), last_ip = %s, updated_at = NOW()
                WHERE user_id = %s
            ''', (ip_address, user_id))
            conn.commit()
        finally:
            cur.close()
            conn.close()
    
    def save_remember_token(self, user_id: int, token_expiry_days: int = 30) -> None:
        """Save remember-me token (not password!)"""
        token_hash = hashlib.sha256(
            f'{user_id}_{datetime.now().isoformat()}'.encode()
        ).hexdigest()
        
        token_data = {
            'user_id': user_id,
            'token_hash': token_hash,
            'expires': (datetime.now() + timedelta(days=token_expiry_days)).isoformat()
        }
        
        try:
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f)
            # Restrict file permissions to owner only
            os.chmod(self.token_file, 0o600)
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            print(f'Warning: Could not save remember token: {e}')
    
    def load_remember_token(self) -> Optional[int]:
        """Load and validate remember-me token"""
        if not self.token_file.exists():
            return None
        
        try:
            with open(self.token_file, 'r') as f:
                token_data = json.load(f)
            
            expires = datetime.fromisoformat(token_data.get('expires', ''))
            if expires > datetime.now():
                return token_data.get('user_id')
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
        conn = self._get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute('''
                SELECT user_id, username, email, role, status, permissions, session_version
                FROM users
                WHERE user_id = %s AND status = %s
            ''', (user_id, 'active'))
            
            row = cur.fetchone()
            if not row:
                return None
            
            uid, uname, email, role, status, perms, sess_ver = row
            permissions = {}
            if perms:
                try:
                    permissions = json.loads(perms) if isinstance(perms, str) else perms
                except:
                    try:
                        self.db.rollback()
                    except:
                        pass
                    pass
            
            return {
                'user_id': uid,
                'username': uname,
                'email': email,
                'role': role or 'user',
                'permissions': permissions,
                'session_version': sess_ver or 1,
                'login_time': datetime.now()
            }
        finally:
            cur.close()
            conn.close()
