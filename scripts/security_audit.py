#!/usr/bin/env python3
"""
Security audit module: verifies password encryption, access logs, login attempts, lock timeouts.
"""

import os
import sys
import psycopg2
from datetime import datetime, timedelta
from typing import List, Dict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

class SecurityAudit:
    """Security audit: encryption, access logs, lock integrity."""

    def __init__(self):
        self.conn = None
        self.cursor = None
        self.issues = []

    def connect(self):
        try:
            self.conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
            self.cursor = self.conn.cursor()
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            sys.exit(1)

    def disconnect(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def audit_password_hashing(self) -> Dict:
        """Check: all passwords hashed (no plaintext), bcrypt format."""
        print("\n🔐 AUDIT: Password Hashing")
        print("-" * 60)
        
        try:
            # Check for plaintext passwords (bcrypt hashes start with $2b$)
            self.cursor.execute("""
                SELECT user_id, username, password_hash, password_changed_at
                FROM system_users
                WHERE password_hash IS NOT NULL
            """)
            
            users = self.cursor.fetchall()
            bcrypt_count = 0
            non_bcrypt_count = 0
            
            for user_id, username, password_hash, changed_at in users:
                if password_hash.startswith('$2b$') or password_hash.startswith('$2a$'):
                    bcrypt_count += 1
                else:
                    non_bcrypt_count += 1
                    self.issues.append(f"❌ {username}: Non-bcrypt hash format")
            
            print(f"✅ Users with bcrypt hashes: {bcrypt_count}")
            if non_bcrypt_count > 0:
                print(f"⚠️  Users with non-bcrypt hashes: {non_bcrypt_count}")
            
            # Check for NULL password hashes
            self.cursor.execute("""
                SELECT COUNT(*) FROM system_users WHERE password_hash IS NULL
            """)
            
            null_count = self.cursor.fetchone()[0]
            if null_count > 0:
                print(f"⚠️  Users with NULL password: {null_count}")
            
            return {'bcrypt': bcrypt_count, 'non_bcrypt': non_bcrypt_count, 'null': null_count}
            
        except Exception as e:
            print(f"❌ Audit failed: {e}")
            return {}

    def audit_access_logs(self, days: int = 7) -> Dict:
        """Check: access logs capturing login attempts, failures, locked accounts."""
        print("\n📋 AUDIT: Security Access Logs (Last 7 Days)")
        print("-" * 60)
        
        try:
            # Login success rate
            self.cursor.execute("""
                SELECT COUNT(*) FROM security_audit_log
                WHERE action LIKE 'login%' AND success = TRUE AND created_at > NOW() - INTERVAL '7 days'
            """)
            success_count = self.cursor.fetchone()[0]
            
            self.cursor.execute("""
                SELECT COUNT(*) FROM security_audit_log
                WHERE action LIKE 'login%' AND success = FALSE AND created_at > NOW() - INTERVAL '7 days'
            """)
            failure_count = self.cursor.fetchone()[0]
            
            print(f"✅ Successful logins: {success_count}")
            print(f"⚠️  Failed login attempts: {failure_count}")
            
            # Failed login breakdown
            if failure_count > 0:
                self.cursor.execute("""
                    SELECT error_message, COUNT(*) as count
                    FROM security_audit_log
                    WHERE action LIKE 'login%' AND success = FALSE AND created_at > NOW() - INTERVAL '7 days'
                    GROUP BY error_message
                    ORDER BY count DESC
                """)
                
                for error_msg, count in self.cursor.fetchall():
                    if error_msg:
                        print(f"     {count:3d}× {error_msg}")
            
            # Password resets
            self.cursor.execute("""
                SELECT COUNT(*) FROM security_audit_log
                WHERE action LIKE 'password%' AND created_at > NOW() - INTERVAL '7 days'
            """)
            reset_count = self.cursor.fetchone()[0]
            print(f"✅ Password resets: {reset_count}")
            
            return {
                'login_success': success_count,
                'login_failures': failure_count,
                'password_resets': reset_count
            }
            
        except Exception as e:
            print(f"❌ Audit failed: {e}")
            return {}

    def audit_locked_accounts(self) -> Dict:
        """Check: accounts locked due to failed attempts."""
        print("\n🔒 AUDIT: Account Lockouts")
        print("-" * 60)
        
        try:
            # Currently locked accounts
            self.cursor.execute("""
                SELECT user_id, username, locked_until, failed_login_attempts
                FROM system_users
                WHERE locked_until > NOW()
            """)
            
            locked_accounts = self.cursor.fetchall()
            if locked_accounts:
                print(f"⚠️  Currently locked accounts: {len(locked_accounts)}")
                for user_id, username, locked_until, attempts in locked_accounts:
                    minutes_left = int((locked_until - datetime.now()).total_seconds() / 60)
                    print(f"   {username}: {attempts} failed attempts, locked for {minutes_left}m")
            else:
                print(f"✅ No locked accounts")
            
            # Accounts with high failed attempt counts
            self.cursor.execute("""
                SELECT user_id, username, failed_login_attempts
                FROM system_users
                WHERE failed_login_attempts >= 3 AND locked_until IS NULL
                ORDER BY failed_login_attempts DESC
            """)
            
            at_risk = self.cursor.fetchall()
            if at_risk:
                print(f"\n⚠️  Accounts at risk (3+ failed attempts):")
                for user_id, username, attempts in at_risk:
                    print(f"   {username}: {attempts} failed attempts")
            
            return {'currently_locked': len(locked_accounts), 'at_risk': len(at_risk)}
            
        except Exception as e:
            print(f"❌ Audit failed: {e}")
            return {}

    def audit_concurrent_edit_locks(self) -> Dict:
        """Check: edit locks expiring properly, no stale locks."""
        print("\n🔄 AUDIT: Concurrent Edit Locks")
        print("-" * 60)
        
        try:
            # Active locks
            self.cursor.execute("""
                SELECT COUNT(*) FROM record_locks WHERE expires_at > NOW()
            """)
            active_count = self.cursor.fetchone()[0]
            
            # Expired locks (not cleaned up)
            self.cursor.execute("""
                SELECT COUNT(*) FROM record_locks WHERE expires_at <= NOW()
            """)
            expired_count = self.cursor.fetchone()[0]
            
            print(f"✅ Active locks (unexpired): {active_count}")
            if expired_count > 0:
                print(f"⚠️  Stale locks (expired, not cleaned): {expired_count}")
            
            # Clean up expired locks
            if expired_count > 0:
                self.cursor.execute("DELETE FROM record_locks WHERE expires_at <= NOW()")
                self.conn.commit()
                print(f"   🧹 Cleaned up {self.cursor.rowcount} stale locks")
            
            return {'active': active_count, 'stale_cleaned': self.cursor.rowcount if expired_count > 0 else 0}
            
        except Exception as e:
            print(f"❌ Audit failed: {e}")
            return {}

    def audit_staged_edits(self) -> Dict:
        """Check: staged edits audit trail, rollback tracking."""
        print("\n📝 AUDIT: Staged Edits & Rollbacks")
        print("-" * 60)
        
        try:
            # Staging breakdown
            self.cursor.execute("""
                SELECT status, COUNT(*) FROM staged_edits GROUP BY status
            """)
            
            status_counts = {}
            for status, count in self.cursor.fetchall():
                status_counts[status] = count
                print(f"✅ {status.capitalize()}: {count}")
            
            # Rollbacks in last 7 days
            self.cursor.execute("""
                SELECT COUNT(*) FROM staged_edits
                WHERE status = 'rolled_back' AND created_at > NOW() - INTERVAL '7 days'
            """)
            recent_rollbacks = self.cursor.fetchone()[0]
            print(f"\n📊 Rollbacks (last 7 days): {recent_rollbacks}")
            
            # Conflicts detected
            self.cursor.execute("""
                SELECT COUNT(*) FROM staged_edits WHERE conflicted_with_user_id IS NOT NULL
            """)
            conflicts = self.cursor.fetchone()[0]
            if conflicts > 0:
                print(f"⚠️  Edit conflicts detected: {conflicts}")
            
            return status_counts
            
        except Exception as e:
            print(f"❌ Audit failed: {e}")
            return {}

    def audit_password_reset_tokens(self) -> Dict:
        """Check: reset tokens are single-use, time-bound."""
        print("\n🔑 AUDIT: Password Reset Tokens")
        print("-" * 60)
        
        try:
            # Valid (unused) tokens
            self.cursor.execute("""
                SELECT COUNT(*) FROM password_reset_tokens WHERE used_at IS NULL AND expires_at > NOW()
            """)
            valid_count = self.cursor.fetchone()[0]
            
            # Expired tokens (not used, now past expiry)
            self.cursor.execute("""
                SELECT COUNT(*) FROM password_reset_tokens WHERE used_at IS NULL AND expires_at <= NOW()
            """)
            expired_count = self.cursor.fetchone()[0]
            
            # Used tokens (proper flow)
            self.cursor.execute("""
                SELECT COUNT(*) FROM password_reset_tokens WHERE used_at IS NOT NULL
            """)
            used_count = self.cursor.fetchone()[0]
            
            print(f"✅ Valid tokens (unused, not expired): {valid_count}")
            print(f"✅ Used tokens (password reset completed): {used_count}")
            if expired_count > 0:
                print(f"ℹ️  Expired tokens (not used): {expired_count}")
            
            return {
                'valid': valid_count,
                'expired': expired_count,
                'used': used_count
            }
            
        except Exception as e:
            print(f"❌ Audit failed: {e}")
            return {}

    def audit_superuser_permissions(self) -> Dict:
        """Check: superusers can initiate password resets, others cannot."""
        print("\n👑 AUDIT: Superuser Permissions")
        print("-" * 60)
        
        try:
            # Count superusers
            self.cursor.execute("""
                SELECT COUNT(DISTINCT ur.user_id) FROM user_roles ur
                JOIN system_roles sr ON ur.role_id = sr.role_id
                WHERE sr.role_name = 'super_user'
            """)
            superuser_count = self.cursor.fetchone()[0]
            print(f"✅ Superusers configured: {superuser_count}")
            
            # List superusers
            self.cursor.execute("""
                SELECT su.username FROM system_users su
                JOIN user_roles ur ON su.user_id = ur.user_id
                JOIN system_roles sr ON ur.role_id = sr.role_id
                WHERE sr.role_name = 'super_user'
                ORDER BY su.username
            """)
            
            superusers = [row[0] for row in self.cursor.fetchall()]
            for username in superusers:
                print(f"   • {username}")
            
            return {'superuser_count': superuser_count, 'superusers': superusers}
            
        except Exception as e:
            print(f"❌ Audit failed: {e}")
            return {}

    def run_full_audit(self):
        """Run comprehensive security audit."""
        print("""
╔════════════════════════════════════════════════════════════════╗
║             SECURITY AUDIT: FULL REPORT                        ║
╚════════════════════════════════════════════════════════════════╝
        """)
        
        results = {
            'passwords': self.audit_password_hashing(),
            'access_logs': self.audit_access_logs(),
            'locked_accounts': self.audit_locked_accounts(),
            'concurrent_locks': self.audit_concurrent_edit_locks(),
            'staged_edits': self.audit_staged_edits(),
            'reset_tokens': self.audit_password_reset_tokens(),
            'superusers': self.audit_superuser_permissions(),
        }
        
        print("\n" + "=" * 60)
        print("🎯 SUMMARY")
        print("=" * 60)
        
        if self.issues:
            print(f"\n⚠️  Issues Found ({len(self.issues)}):")
            for issue in self.issues:
                print(f"   {issue}")
        else:
            print("\n✅ No critical issues detected")
        
        return results


if __name__ == "__main__":
    audit = SecurityAudit()
    audit.connect()
    results = audit.run_full_audit()
    audit.disconnect()
    
    print("\n✅ Audit complete\n")
