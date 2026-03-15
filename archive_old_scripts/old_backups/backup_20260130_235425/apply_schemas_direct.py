#!/usr/bin/env python3
"""Apply schemas directly via psycopg2 without splitting."""

import os
import sys
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("📋 Applying schemas...\n")
    
    # 1) RBAC schema
    print("Applying RBAC schema...")
    with open('sql/rbac_schema_fixed.sql', 'r') as f:
        cursor.execute(f.read())
    conn.commit()
    print("✅ RBAC schema applied")
    
    # 2) RBAC roles and permissions
    print("\nApplying RBAC roles and permissions...")
    with open('sql/rbac_seed_roles_fixed.sql', 'r') as f:
        cursor.execute(f.read())
    conn.commit()
    print("✅ RBAC roles applied")
    
    # 3) Security schema
    print("\nApplying security and multi-user schema...")
    with open('sql/security_multiuser_schema.sql', 'r') as f:
        cursor.execute(f.read())
    conn.commit()
    print("✅ Security schema applied")
    
    # Verify tables
    cursor.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name IN (
            'system_users', 'system_roles', 'permissions', 'user_roles', 'role_permissions',
            'user_scopes', 'password_reset_tokens', 'concurrent_edits', 'record_locks', 
            'staged_edits', 'audit_log'
        )
        ORDER BY table_name
    """)
    
    tables = [row[0] for row in cursor.fetchall()]
    print(f"\n📊 Verified tables ({len(tables)}):")
    for table in sorted(tables):
        print(f"   ✓ {table}")
    
    cursor.close()
    conn.close()
    
    print("\n✅ All schemas applied successfully\n")
    
except psycopg2.Error as e:
    print(f"❌ Database error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
