#!/usr/bin/env python3
"""
Multi-user concurrent edit detection and staging system.
Prevents "file in use" conflicts, enables edit rollback on conflict.
"""

import os
import sys
import json
import psycopg2
from datetime import datetime
from typing import Optional, Dict, List, Tuple

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

class ConcurrentEditManager:
    """Manages multi-user edits, locks, staging, and conflict resolution."""

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

    def check_record_available(self, module: str, record_type: str, record_id: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check if record is available for editing.
        Returns: (is_available, locked_by_username, message)
        """
        try:
            self.cursor.execute("""
                SELECT rl.locked_by_user_id, su.username, rl.expires_at
                FROM record_locks rl
                JOIN system_users su ON rl.locked_by_user_id = su.user_id
                WHERE rl.module = %s AND rl.record_type = %s AND rl.record_id = %s
                  AND rl.expires_at > NOW()
            """, (module, record_type, record_id))
            
            result = self.cursor.fetchone()
            if result:
                locked_user_id, locked_username, expires_at = result
                minutes_left = max(1, int((expires_at - datetime.now()).total_seconds() / 60))
                message = f"Record in use by {locked_username}. Try again in {minutes_left} minute(s)."
                return False, locked_username, message
            else:
                return True, None, "OK"
                
        except Exception as e:
            print(f"❌ Availability check failed: {e}")
            return False, None, f"Error: {e}"

    def acquire_lock(self, user_id: int, module: str, record_type: str, record_id: str) -> bool:
        """Acquire edit lock on record (10-minute timeout)."""
        try:
            self.cursor.execute("""
                INSERT INTO record_locks (module, record_type, record_id, locked_by_user_id, expires_at)
                VALUES (%s, %s, %s, %s, NOW() + INTERVAL '10 minutes')
                ON CONFLICT (module, record_type, record_id) DO NOTHING
            """, (module, record_type, record_id, user_id))
            
            if self.cursor.rowcount == 0:
                # Lock already exists - check if ours
                self.cursor.execute("""
                    SELECT locked_by_user_id FROM record_locks
                    WHERE module = %s AND record_type = %s AND record_id = %s
                """, (module, record_type, record_id))
                
                result = self.cursor.fetchone()
                if result and result[0] == user_id:
                    # Refresh our lock timeout
                    self.cursor.execute("""
                        UPDATE record_locks
                        SET expires_at = NOW() + INTERVAL '10 minutes', last_activity = NOW()
                        WHERE module = %s AND record_type = %s AND record_id = %s
                          AND locked_by_user_id = %s
                    """, (module, record_type, record_id, user_id))
                    self.conn.commit()
                    return True
                else:
                    return False
            else:
                self.conn.commit()
                return True
                
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Lock acquisition failed: {e}")
            return False

    def release_lock(self, user_id: int, module: str, record_type: str, record_id: str) -> bool:
        """Release edit lock on record."""
        try:
            self.cursor.execute("""
                UPDATE record_locks
                SET checked_in_at = NOW()
                WHERE module = %s AND record_type = %s AND record_id = %s
                  AND locked_by_user_id = %s
            """, (module, record_type, record_id, user_id))
            
            self.cursor.execute("""
                DELETE FROM record_locks
                WHERE module = %s AND record_type = %s AND record_id = %s
                  AND locked_by_user_id = %s
            """, (module, record_type, record_id, user_id))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Lock release failed: {e}")
            return False

    def stage_edit(self, user_id: int, module: str, record_type: str, record_id: str, 
                   table_name: str, original_values: Dict, staged_values: Dict) -> Optional[int]:
        """
        Create a staged edit proposal.
        User proposes changes; they go to staging table, not applied to live table yet.
        """
        try:
            self.cursor.execute("""
                INSERT INTO staged_edits 
                  (user_id, module, record_type, record_id, table_name, original_values, staged_values, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', NOW())
                RETURNING id
            """, (user_id, module, record_type, record_id, table_name, 
                  json.dumps(original_values), json.dumps(staged_values)))
            
            staging_id = self.cursor.fetchone()[0]
            self.conn.commit()
            
            self.cursor.execute("SELECT username FROM system_users WHERE user_id = %s", (user_id,))
            username = self.cursor.fetchone()[0]
            
            print(f"✅ Edit staged by {username} (staging_id={staging_id})")
            return staging_id
            
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Stage edit failed: {e}")
            return None

    def commit_staged_edit(self, staging_id: int, user_id: int) -> bool:
        """
        Commit a staged edit to live table.
        Only succeeds if no conflict (no other user edited same record since lock was acquired).
        """
        try:
            # Get staged edit
            self.cursor.execute("""
                SELECT module, record_type, record_id, table_name, staged_values, original_values
                FROM staged_edits
                WHERE id = %s AND user_id = %s
            """, (staging_id, user_id))
            
            result = self.cursor.fetchone()
            if not result:
                print(f"❌ Staged edit {staging_id} not found or not owned by user")
                return False
            
            module, record_type, record_id, table_name, staged_json, original_json = result
            
            # Check if lock still held by this user
            self.cursor.execute("""
                SELECT locked_by_user_id FROM record_locks
                WHERE module = %s AND record_type = %s AND record_id = %s
            """, (module, record_type, record_id))
            
            lock_result = self.cursor.fetchone()
            if lock_result and lock_result[0] != user_id:
                print(f"❌ Lock released or owned by another user. Conflict detected. Rolling back.")
                self._rollback_staged_edit(staging_id, "conflicted")
                return False
            
            # Apply changes to live table
            staged_values = json.loads(staged_json)
            set_clause = ", ".join([f"{k} = %s" for k in staged_values.keys()])
            values = list(staged_values.values()) + [record_id]
            
            query = f"UPDATE {table_name} SET {set_clause} WHERE id = %s"
            self.cursor.execute(query, values)
            
            # Mark staged edit as committed
            self.cursor.execute("""
                UPDATE staged_edits SET status = 'committed', committed_at = NOW()
                WHERE id = %s
            """, (staging_id,))
            
            self.conn.commit()
            
            self.cursor.execute("SELECT username FROM system_users WHERE user_id = %s", (user_id,))
            username = self.cursor.fetchone()[0]
            print(f"✅ Staged edit committed by {username} (staging_id={staging_id})")
            return True
            
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Commit staged edit failed: {e}")
            return False

    def rollback_staged_edit(self, staging_id: int, user_id: int, reason: str = "user_requested") -> bool:
        """Rollback a staged edit (discard proposed changes)."""
        try:
            self.cursor.execute("""
                UPDATE staged_edits SET status = 'rolled_back'
                WHERE id = %s AND user_id = %s
            """, (staging_id, user_id))
            
            self.conn.commit()
            print(f"✅ Staged edit rolled back (staging_id={staging_id}, reason={reason})")
            return True
            
        except Exception as e:
            self.conn.rollback()
            print(f"❌ Rollback failed: {e}")
            return False

    def _rollback_staged_edit(self, staging_id: int, reason: str = "conflict") -> bool:
        """Internal: rollback without user_id check."""
        try:
            self.cursor.execute("""
                UPDATE staged_edits SET status = %s
                WHERE id = %s
            """, ("rolled_back", staging_id))
            
            self.conn.commit()
            return True
        except:
            return False

    def list_active_locks(self) -> List[Dict]:
        """List all active record locks (admin view)."""
        try:
            self.cursor.execute("""
                SELECT rl.module, rl.record_type, rl.record_id, su.username, rl.locked_at, rl.expires_at
                FROM record_locks rl
                JOIN system_users su ON rl.locked_by_user_id = su.user_id
                WHERE rl.expires_at > NOW()
                ORDER BY rl.locked_at DESC
            """)
            
            locks = []
            for row in self.cursor.fetchall():
                module, record_type, record_id, username, locked_at, expires_at = row
                locks.append({
                    'module': module,
                    'record_type': record_type,
                    'record_id': record_id,
                    'locked_by': username,
                    'locked_at': str(locked_at),
                    'expires_at': str(expires_at)
                })
            
            return locks
            
        except Exception as e:
            print(f"❌ Failed to list locks: {e}")
            return []

    def list_staged_edits(self, status: str = 'pending') -> List[Dict]:
        """List staged edits by status (pending, committed, rolled_back)."""
        try:
            self.cursor.execute("""
                SELECT se.id, se.user_id, su.username, se.module, se.record_type, se.record_id,
                       se.created_at, se.status
                FROM staged_edits se
                JOIN system_users su ON se.user_id = su.user_id
                WHERE se.status = %s
                ORDER BY se.created_at DESC
            """, (status,))
            
            edits = []
            for row in self.cursor.fetchall():
                staging_id, user_id, username, module, record_type, record_id, created_at, status = row
                edits.append({
                    'staging_id': staging_id,
                    'user_id': user_id,
                    'username': username,
                    'module': module,
                    'record_type': record_type,
                    'record_id': record_id,
                    'created_at': str(created_at),
                    'status': status
                })
            
            return edits
            
        except Exception as e:
            print(f"❌ Failed to list staged edits: {e}")
            return []


if __name__ == "__main__":
    manager = ConcurrentEditManager()
    manager.connect()
    
    print("""
╔════════════════════════════════════════════════════════════════╗
║        CONCURRENT EDIT MANAGEMENT (Active Locks/Staging)       ║
╚════════════════════════════════════════════════════════════════╝
    """)
    
    print("\n📋 Active Record Locks:")
    locks = manager.list_active_locks()
    if locks:
        for lock in locks:
            print(f"   [{lock['module']}] {lock['record_type']} {lock['record_id']}")
            print(f"      Locked by: {lock['locked_by']}")
            print(f"      Expires: {lock['expires_at']}")
    else:
        print("   (none)")
    
    print("\n📋 Pending Staged Edits:")
    edits = manager.list_staged_edits('pending')
    if edits:
        for edit in edits:
            print(f"   [#{edit['staging_id']}] {edit['username']} → {edit['record_type']} {edit['record_id']}")
            print(f"      Module: {edit['module']}, Created: {edit['created_at']}")
    else:
        print("   (none)")
    
    manager.disconnect()
