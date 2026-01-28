"""
Setup real users with credentials and roles
"""

import os
import sys
import psycopg2
import psycopg2.extras
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from desktop_app.login_manager import LoginManager

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

users_to_create = [
    {
        'username': 'paulr',
        'email': 'paulr@arrowlimousine.local',
        'password': 'halarin2026',
        'role': 'superuser',
        'permissions': {
            'dashboard': True,
            'reports': True,
            'charters': True,
            'payments': True,
            'employees': True,
            'vehicles': True,
            'settings': True,
            'admin': True
        }
    },
    {
        'username': 'matt',
        'email': 'matt@arrowlimousine.local',
        'password': 'dispatcher1',
        'role': 'admin',
        'permissions': {
            'dashboard': True,
            'reports': True,
            'charters': True,
            'payments': True,
            'employees': True,
            'vehicles': True,
            'settings': True
        }
    },
    {
        'username': 'david',
        'email': 'david@arrowlimousine.local',
        'password': 'richard2026',
        'role': 'superuser',
        'permissions': {
            'dashboard': True,
            'reports': True,
            'charters': True,
            'payments': True,
            'employees': True,
            'vehicles': True,
            'settings': True,
            'admin': True
        }
    },
    {
        'username': 'mike_richard',
        'email': 'mike_richard@arrowlimousine.local',
        'password': 'chauffeur',
        'role': 'driver',
        'permissions': {
            'dashboard': True,
            'charters': True,
            'reports': False,
            'payments': False,
            'employees': False,
            'vehicles': False,
            'settings': False
        }
    },
    {
        'username': 'accountant',
        'email': 'accountant@arrowlimousine.local',
        'password': '2025ArrowLimo',
        'role': 'accountant',
        'permissions': {
            'dashboard': True,
            'reports': True,
            'payments': True,
            'charters': True,
            'employees': False,
            'vehicles': False,
            'settings': False
        }
    }
]

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    login_mgr = LoginManager()
    
    print("=" * 70)
    print("SETTING UP REAL USERS WITH CREDENTIALS")
    print("=" * 70)
    
    for user_data in users_to_create:
        username = user_data['username']
        email = user_data['email']
        password = user_data['password']
        role = user_data['role']
        permissions = user_data['permissions']
        
        # Check if user exists
        cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
        existing = cur.fetchone()
        
        if existing:
            # Update existing user
            password_hash = login_mgr.hash_password(password)
            cur.execute(
                """UPDATE users 
                   SET email = %s, password_hash = %s, role = %s, 
                       permissions = %s, status = 'active'
                   WHERE username = %s""",
                (email, password_hash, role, psycopg2.extras.Json(permissions), username)
            )
            conn.commit()
            print(f"✓ Updated: {username} ({role})")
        else:
            # Create new user
            user_id = login_mgr.create_user(username, email, password, role, permissions)
            print(f"✓ Created: {username} ({role}) - ID: {user_id}")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 70)
    print("TEST CREDENTIALS:")
    print("=" * 70)
    for user_data in users_to_create:
        print(f"  {user_data['username']:15} / {user_data['password']:20} ({user_data['role']})")
    print("=" * 70)
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
