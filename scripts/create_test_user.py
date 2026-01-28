"""
Create test user for login system testing
"""

import os
import sys
import psycopg2
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from desktop_app.login_manager import LoginManager

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

try:
    # Connect to database
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Create LoginManager
    login_mgr = LoginManager()
    
    # Check if admin user exists
    cur.execute("SELECT user_id FROM users WHERE username = %s", ('admin',))
    admin_exists = cur.fetchone()
    
    if admin_exists:
        print("✓ Admin user already exists")
    else:
        # Create admin user
        user_id = login_mgr.create_user(
            username='admin',
            email='admin@arrowlimousine.local',
            password='TestPassword123!',  # CHANGE THIS IN PRODUCTION
            role='admin',
            permissions={
                'dashboard': True,
                'reports': True,
                'charters': True,
                'payments': True,
                'employees': True,
                'vehicles': True,
                'settings': True
            }
        )
        print(f"✓ Created admin user (ID: {user_id})")
        print(f"  Username: admin")
        print(f"  Password: TestPassword123!")
    
    # Create demo user
    cur.execute("SELECT user_id FROM users WHERE username = %s", ('demo',))
    demo_exists = cur.fetchone()
    
    if demo_exists:
        print("✓ Demo user already exists")
    else:
        user_id = login_mgr.create_user(
            username='demo',
            email='demo@arrowlimousine.local',
            password='DemoPassword123!',
            role='user',
            permissions={
                'dashboard': True,
                'reports': True,
                'charters': False,
                'payments': False,
                'employees': False,
                'vehicles': False,
                'settings': False
            }
        )
        print(f"✓ Created demo user (ID: {user_id})")
        print(f"  Username: demo")
        print(f"  Password: DemoPassword123!")
    
    cur.close()
    conn.close()
    
    print("\n✓ Test users created successfully!")
    print("\nUse these credentials to test login:")
    print("  Admin: admin / TestPassword123!")
    print("  Demo: demo / DemoPassword123!")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
