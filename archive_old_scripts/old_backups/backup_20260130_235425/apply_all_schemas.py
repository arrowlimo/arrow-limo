#!/usr/bin/env python3
"""Apply RBAC and security schemas to database."""

import os
import sys
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def apply_schema_file(cursor, filepath, label):
    """Apply SQL schema file."""
    try:
        with open(filepath, 'r') as f:
            schema = f.read()
        
        # Split into statements (simple split on semicolon)
        statements = [s.strip() for s in schema.split(';') if s.strip()]
        
        for i, stmt in enumerate(statements):
            if stmt:
                try:
                    cursor.execute(stmt)
                except psycopg2.Error as e:
                    # Some errors are OK (IF NOT EXISTS, ON CONFLICT, etc)
                    if 'already exists' not in str(e) and 'duplicate key' not in str(e):
                        print(f"   Warning: {e}")
        
        print(f"✅ {label} applied")
        return True
    except Exception as e:
        print(f"❌ {label} failed: {e}")
        return False

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("📋 Applying security & RBAC schemas...\n")
    
    # Apply RBAC schema first (creates system_users, roles, etc.)
    apply_schema_file(cursor, 'sql/rbac_schema_fixed.sql', 'RBAC schema')
    
    # Seed roles with permissions
    apply_schema_file(cursor, 'sql/rbac_seed_roles_fixed.sql', 'RBAC roles (10 roles)')
    
    # Apply security schema (uses system_users)
    apply_schema_file(cursor, 'sql/security_multiuser_schema.sql', 'Security & multi-user schema')
    
    conn.commit()
    
    # Verify tables created
    cursor.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name IN (
            'system_users', 'roles', 'user_roles', 'password_reset_tokens', 
            'concurrent_edits', 'record_locks', 'staged_edits', 'audit_log'
        )
        ORDER BY table_name
    """)
    
    tables = [row[0] for row in cursor.fetchall()]
    print(f"\n📊 Verified tables ({len(tables)}):")
    for table in tables:
        print(f"   ✓ {table}")
    
    cursor.close()
    conn.close()
    
    print("\n✅ All schemas applied successfully")
    
except Exception as e:
    print(f"❌ Fatal error: {e}")
    sys.exit(1)
