#!/usr/bin/env python3
"""
Password security management with bcrypt hashing and multi-user support.
Includes user creation, password reset authorization (superuser-only), and security auditing.
"""

import os
import sys
import bcrypt
import secrets
import hashlib
import psycopg2
from datetime import datetime, timedelta
from typing import Optional, Tuple

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

class PasswordManager:
    """Password hashing, verification, reset workflow."""

    @staticmethod
    def hash_password(password: str, salt_rounds: int = 12) -> str:
        """Hash password using bcrypt. NOT stored plaintext."""
        salt = bcrypt.gensalt(rounds=salt_rounds)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify password against bcrypt hash."""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

    @staticmethod
    def generate_reset_token() -> str:
        """Generate secure 32-byte random token for password resets."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_reset_token(token: str) -> str:
        """Hash reset token before storing (one-way)."""
        return hashlib.sha256(token.encode('utf-8')).hexdigest()


class UserSecurityManager:
    """User account management with password security and authorization."""

    def __init__(self):
        self.conn = None
        self.cursor = None

    def connect(self):
        """Connect to database."""
        try:
            self.conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            self.cursor = self.conn.cursor()
            print(f"✅ Connected to {DB_NAME}")
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            sys.exit(1)

    def disconnect(self):
        """Disconnect from database."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def create_user_with_password(self, username: str, password: str, role: str) -> bool:
        """Create user account with hashed password and assign role."""
        try:
            password_hash = PasswordManager.hash_password(password)
            
            # Insert user into system_users
            self.cursor.execute("""
                INSERT INTO system_users (username, email, full_name, is_active, password_hash, password_changed_at, created_at, updated_at)
                VALUES (%s, %s, %s, TRUE, %s, NOW(), NOW(), NOW())
                ON CONFLICT (username) DO UPDATE 
                SET password_hash = %s, password_changed_at = NOW(), is_active = TRUE, updated_at = NOW()
                RETURNING user_id
            """, (username, f"{username}@arrowlimousine.com", username.title(), password_hash, password_hash))
            
            user_id = self.cursor.fetchone()[0]
            self.conn.commit()
            
            # Assign role
            self.cursor.execute("""
                INSERT INTO user_roles (user_id, role_id, assigned_at)
                SELECT %s, sr.role_id, NOW()
                FROM system_roles sr WHERE sr.role_name = %s
                ON CONFLICT (user_id, role_id) DO NOTHING
            """, (user_id, role))
            
            self.conn.commit()
            print(f"✅ Created user: {username} with role: {role}")
            return True
            
        except Exception as e:
            self.conn.rollback()
            print(f"❌ User creation failed: {e}")
            return False

    def request_password_reset(self, requesting_user_id: int, target_user_id: int) -> Optional[str]:
        """
        Generate password reset token (superuser-only authorization).
        requesting_user_id: user requesting the reset
        target_user_id: user whose password needs reset
        """
        try:
            # Verify requesting user is superuser
            self.cursor.execute("""
                SELECT ur.user_id FROM user_roles ur
                JOIN roles r ON ur.role_id = r.role_id
                WHERE ur.user_id = %s AND r.role_name = 'super_user'
            """, (requesting_user_id,))
            
            if not self.cursor.fetchone():
                print(f"❌ Unauthorized: Only superuser can initiate password resets")
                return None
            
            # Generate reset token
            reset_token = PasswordManager.generate_reset_token()
            token_hash = PasswordManager.hash_reset_token(reset_token)
            
            # Store token with 15-minute expiry
            self.cursor.execute("""
                INSERT INTO password_reset_tokens (user_id, reset_token, expires_at)
                VALUES (%s, %s, NOW() + INTERVAL '15 minutes')
                RETURNING id
            """, (target_user_id, token_hash))
            
            token_id = self.cursor.fetchone()[0]
            self.conn.commit()
            
            # Get target username for logging
            self.cursor.execute("SELECT username FROM system_users WHERE user_id = %s", (target_user_id,))
            target_username = self.cursor.fetchone()[0]
            
            # Audit log
            self.cursor.execute("""
                INSERT INTO security_audit_log (user_id, action, success)
                VALUES (%s, 'password_reset_requested_for_' || %s, TRUE)
            """, (requesting_user_id, target_username))
            self.conn.commit()
            
            print(f"✅ Password reset token generated for {target_username} (expires in 15 min)")
            print(f"   Token: {reset_token[:20]}...")
            return reset_token
            
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Reset token generation failed: {e}")
            return None

    def confirm_password_reset(self, reset_token: str, new_password: str) -> bool:
        """Confirm password reset using token (user-initiated)."""
        try:
            token_hash = PasswordManager.hash_reset_token(reset_token)
            
            # Find valid token
            self.cursor.execute("""
                SELECT pt.user_id FROM password_reset_tokens pt
                WHERE pt.reset_token = %s AND pt.expires_at > NOW() AND pt.used_at IS NULL
            """, (token_hash,))
            
            result = self.cursor.fetchone()
            if not result:
                print(f"❌ Invalid or expired reset token")
                return False
            
            user_id = result[0]
            
            # Hash new password
            password_hash = PasswordManager.hash_password(new_password)
            
            # Update user password and mark token as used
            self.cursor.execute("""
                UPDATE system_users SET password_hash = %s, password_changed_at = NOW()
                WHERE user_id = %s
            """, (password_hash, user_id))
            
            self.cursor.execute("""
                UPDATE password_reset_tokens SET used_at = NOW()
                WHERE reset_token = %s
            """, (token_hash,))
            
            self.conn.commit()
            
            self.cursor.execute("SELECT username FROM system_users WHERE user_id = %s", (user_id,))
            username = self.cursor.fetchone()[0]
            
            print(f"✅ Password reset confirmed for {username}")
            return True
            
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Password reset confirmation failed: {e}")
            return False

    def verify_login(self, username: str, password: str) -> Tuple[bool, Optional[int]]:
        """Verify username/password and update login timestamp."""
        try:
            self.cursor.execute("""
                SELECT user_id, password_hash, locked_until FROM system_users WHERE username = %s
            """, (username,))
            
            result = self.cursor.fetchone()
            if not result:
                self.cursor.execute("""
                    INSERT INTO security_audit_log (user_id, action, success, error_message)
                    VALUES (NULL, 'login_failed_unknown_user_' || %s, FALSE, 'User not found')
                """, (username,))
                self.conn.commit()
                print(f"❌ User {username} not found")
                return False, None
            
            user_id, password_hash, locked_until = result
            
            # Check account lockout
            if locked_until and locked_until > datetime.now():
                minutes_remaining = int((locked_until - datetime.now()).total_seconds() / 60)
                print(f"❌ Account locked. Try again in {minutes_remaining} minutes")
                return False, None
            
            # Verify password
            if not PasswordManager.verify_password(password, password_hash):
                self.cursor.execute("""
                    UPDATE system_users SET failed_login_attempts = failed_login_attempts + 1
                    WHERE user_id = %s
                """, (user_id,))
                
                # Lock after 5 failed attempts
                self.cursor.execute("""
                    SELECT failed_login_attempts FROM system_users WHERE user_id = %s
                """, (user_id,))
                
                attempts = self.cursor.fetchone()[0]
                if attempts >= 5:
                    self.cursor.execute("""
                        UPDATE system_users SET locked_until = NOW() + INTERVAL '15 minutes'
                        WHERE user_id = %s
                    """, (user_id,))
                    print(f"❌ Invalid password (attempt {attempts}). Account locked for 15 minutes")
                else:
                    print(f"❌ Invalid password (attempt {attempts}/5)")
                
                self.cursor.execute("""
                    INSERT INTO security_audit_log (user_id, action, success, error_message)
                    VALUES (%s, 'login_failed_invalid_password', FALSE, 'Password mismatch')
                """, (user_id,))
                self.conn.commit()
                return False, None
            
            # Success: reset failed attempts and update last login
            self.cursor.execute("""
                UPDATE system_users SET failed_login_attempts = 0, last_login = NOW()
                WHERE user_id = %s
            """, (user_id,))
            
            self.cursor.execute("""
                INSERT INTO security_audit_log (user_id, action, success)
                VALUES (%s, 'login_success', TRUE)
            """, (user_id,))
            
            self.conn.commit()
            print(f"✅ Login successful: {username}")
            return True, user_id
            
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Login verification failed: {e}")
            return False, None


def setup_initial_users():
    """Create 4 initial users: 2 superusers, 2 drivers."""
    manager = UserSecurityManager()
    manager.connect()
    
    users = [
        ("paulr", "halarin", "super_user"),
        ("matt", "dispatch", "super_user"),
        ("david", "richard", "driver"),
        ("mikerichards", "mikerichard", "driver"),
    ]
    
    print("\n📋 Setting up 4 initial user accounts...\n")
    for username, password, role in users:
        manager.create_user_with_password(username, password, role)
    
    manager.disconnect()
    print("\n✅ All users created successfully\n")
    print("📝 Credentials:")
    for username, password, role in users:
        print(f"   {username:<15} / {password:<15} ({role})")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "setup":
            setup_initial_users()
        elif sys.argv[1] == "verify-login":
            if len(sys.argv) < 4:
                print("Usage: python security_manager.py verify-login <username> <password>")
                sys.exit(1)
            username, password = sys.argv[2], sys.argv[3]
            manager = UserSecurityManager()
            manager.connect()
            success, user_id = manager.verify_login(username, password)
            manager.disconnect()
            sys.exit(0 if success else 1)
    else:
        print("""
╔════════════════════════════════════════════════════════════════╗
║           PASSWORD SECURITY & USER MANAGEMENT                  ║
╚════════════════════════════════════════════════════════════════╝

Usage:
  python security_manager.py setup                  # Create 4 initial users
  python security_manager.py verify-login <user> <pw>  # Test login credentials

Features:
  ✓ bcrypt password hashing (12 rounds)
  ✓ Superuser-only password reset authorization
  ✓ 15-minute password reset tokens
  ✓ Account lockout after 5 failed login attempts
  ✓ Audit logging of all login attempts
        """)
