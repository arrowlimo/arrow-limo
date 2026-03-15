"""
Database Connection Diagnostic Tool
Helps diagnose PostgreSQL connection issues
"""

import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("═" * 70)
print(" PostgreSQL Connection Diagnostic")
print("═" * 70)
print()

# Check environment variables
print("1. Environment Variables Check:")
print(f"   DB_HOST     = {os.getenv('DB_HOST', 'NOT SET')}")
print(f"   DB_PORT     = {os.getenv('DB_PORT', 'NOT SET')}")
print(f"   DB_NAME     = {os.getenv('DB_NAME', 'NOT SET')}")
print(f"   DB_USER     = {os.getenv('DB_USER', 'NOT SET')}")
password = os.getenv('DB_PASSWORD', '')
if password:
    print(f"   DB_PASSWORD = {'*' * len(password)} (length: {len(password)})")
else:
    print(f"   DB_PASSWORD = NOT SET or EMPTY")
print()

# Try to connect
print("2. Testing Connection:")
print(f"   Attempting to connect to PostgreSQL...")
print()

try:
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', '5432')),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '')
    )
    
    cur = conn.cursor()
    cur.execute("SELECT version();")
    version = cur.fetchone()[0]
    
    print("   ✅ CONNECTION SUCCESSFUL!")
    print(f"   PostgreSQL Version: {version[:50]}...")
    print()
    
    cur.close()
    conn.close()
    
except psycopg2.OperationalError as e:
    error_msg = str(e)
    print("   ❌ CONNECTION FAILED!")
    print(f"   Error: {error_msg}")
    print()
    
    if "password authentication failed" in error_msg:
        print("   DIAGNOSIS: Password Authentication Failed")
        print()
        print("   Possible causes:")
        print("   1. Password in .env file is incorrect")
        print("   2. PostgreSQL user 'postgres' password is different")
        print("   3. PostgreSQL pg_hba.conf is not configured for password auth")
        print()
        print("   SOLUTIONS:")
        print()
        print("   Option A: Reset PostgreSQL password to match .env file")
        print("   ----------------------------------------------------------")
        print("   Run this in PowerShell as Administrator:")
        print()
        print('   psql -U postgres -c "ALTER USER postgres WITH PASSWORD \'YourPassword\';"')
        print()
        print("   Option B: Update .env file with correct password")
        print("   --------------------------------------------------")
        print("   Edit l:\\limo\\.env file and update DB_PASSWORD=")
        print()
        print("   Option C: Use Windows Integrated Authentication")
        print("   -------------------------------------------------")
        print("   Run: l:\\limo\\SETUP_WINDOWS_INTEGRATED_AUTH.ps1")
        print()
        
    elif "could not connect to server" in error_msg or "Connection refused" in error_msg:
        print("   DIAGNOSIS: PostgreSQL Server Not Running")
        print()
        print("   SOLUTION: Start PostgreSQL service")
        print("   Run in PowerShell as Administrator:")
        print()
        print("   Start-Service postgresql-x64-17")
        print()
        
    else:
        print(f"   Unknown error: {error_msg}")
        print()

except Exception as e:
    print(f"   ❌ UNEXPECTED ERROR: {e}")
    print()

print("═" * 70)
print()
input("Press Enter to exit...")
