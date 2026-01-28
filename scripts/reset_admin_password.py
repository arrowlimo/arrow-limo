"""
Reset admin password
"""

import os
import sys
import psycopg2
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from desktop_app.login_manager import LoginManager

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    login_mgr = LoginManager()
    
    # Hash the password
    password_hash = login_mgr.hash_password('TestPassword123!')
    
    # Update admin user
    cur.execute(
        "UPDATE users SET password_hash = %s WHERE username = %s",
        (password_hash, 'admin')
    )
    conn.commit()
    
    print(f"✓ Reset admin password")
    print(f"  Username: admin")
    print(f"  Password: TestPassword123!")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
