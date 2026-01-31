#!/usr/bin/env python3
"""
Diagnostic tool for web service database connection issues
Checks if environment variables are properly configured
"""

import os
import sys
from pathlib import Path

def check_db_config():
    """Check database configuration"""
    
    print("\n" + "="*70)
    print("🔍 DATABASE CONNECTION CONFIGURATION DIAGNOSTIC")
    print("="*70 + "\n")
    
    # Check environment variables
    vars_to_check = [
        'DB_HOST',
        'DB_PORT',
        'DB_NAME',
        'DB_USER',
        'DB_PASSWORD',
        'DB_SSLMODE',
    ]
    
    print("📋 Environment Variables Status:\n")
    
    found_any = False
    for var in vars_to_check:
        value = os.environ.get(var)
        if value:
            # Hide password
            if 'PASSWORD' in var:
                display = '●' * len(value)
            else:
                display = value
            
            print(f"  ✅ {var:20} = {display}")
            found_any = True
        else:
            print(f"  ❌ {var:20} = <NOT SET>")
    
    if not found_any:
        print("  ⚠️  NO DATABASE VARIABLES SET!")
    
    # Check .env file
    print("\n📄 Checking .env file:\n")
    
    env_file = Path('.env')
    if env_file.exists():
        print(f"  ✅ .env file found at: {env_file.absolute()}")
        
        with open(env_file, 'r') as f:
            content = f.read()
            
        required_keys = ['DB_HOST', 'DB_NAME', 'DB_USER']
        
        for key in required_keys:
            if key in content:
                print(f"     ✅ Contains {key}")
            else:
                print(f"     ❌ Missing {key}")
    else:
        print(f"  ❌ .env file NOT found")
        print(f"     Expected location: {env_file.absolute()}")
    
    # Connection test
    print("\n🧪 Connection Test:\n")
    
    try:
        import psycopg2
        
        # Get connection params
        host = os.environ.get('DB_HOST', 'localhost')
        port = int(os.environ.get('DB_PORT', 5432))
        database = os.environ.get('DB_NAME', 'almsdata')
        user = os.environ.get('DB_USER', 'postgres')
        password = os.environ.get('DB_PASSWORD')
        sslmode = os.environ.get('DB_SSLMODE')
        
        print(f"  Attempting connection to: {user}@{host}:{port}/{database}")
        
        if not password:
            print("  ⚠️  WARNING: No password found - connection will likely fail")
        
        conn_kwargs = {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password,
        }
        
        if sslmode:
            conn_kwargs['sslmode'] = sslmode
        
        conn = psycopg2.connect(**conn_kwargs)
        cur = conn.cursor()
        
        cur.execute("SELECT version();")
        result = cur.fetchone()
        
        print(f"\n  ✅ CONNECTION SUCCESSFUL!")
        print(f"     PostgreSQL: {result[0][:60]}...\n")
        
        cur.close()
        conn.close()
        
        return True
        
    except psycopg2.OperationalError as e:
        print(f"\n  ❌ CONNECTION FAILED!")
        print(f"     Error: {e}\n")
        return False
    except Exception as e:
        print(f"\n  ❌ ERROR: {e}\n")
        return False

def check_web_service_config():
    """Check if web service (Render) is properly configured"""
    
    print("🌐 WEB SERVICE (RENDER) CONFIGURATION:\n")
    
    print("  For web service to connect to Neon, you must:")
    print("  1. Set environment variables in Render dashboard")
    print("  2. Environment > Environment Variables")
    print("  3. Add these variables:\n")
    
    vars_needed = {
        'DB_HOST': 'ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech',
        'DB_PORT': '5432',
        'DB_NAME': 'neondb',
        'DB_USER': 'neondb_owner',
        'DB_PASSWORD': 'npg_rlL0yK9pvfCW',
        'DB_SSLMODE': 'require',
    }
    
    for var, example in vars_needed.items():
        if 'PASSWORD' in var:
            display = '●' * len(example)
        else:
            display = example
        
        print(f"     {var} = {display}")
    
    print("\n  ⚠️  DO NOT use .env file on web service!")
    print("     - .env is git-ignored and not deployed")
    print("     - Use Render Environment Variables instead")
    print("     - These are set in dashboard, not in code\n")

if __name__ == '__main__':
    ok = check_db_config()
    
    print("="*70)
    check_web_service_config()
    print("="*70 + "\n")
    
    if ok:
        print("✅ Local database connection OK")
        print("💡 For web service, set environment variables in Render dashboard\n")
        sys.exit(0)
    else:
        print("❌ Local database connection FAILED")
        print("💡 Check error above and verify database is running\n")
        sys.exit(1)
