#!/usr/bin/env python3
"""Quick login test script"""
import sys
sys.path.insert(0, r'l:\limo\desktop_app')
from login_manager import LoginManager, AuthenticationError, AccountLockedError

lm = LoginManager()

# Test 1: Correct credentials
print("[TEST 1] Testing paulr with correct password...")
try:
    user = lm.authenticate('paulr', 'TestPassword123!', '127.0.0.1')
    print("  [SUCCESS] paulr logged in")
    print(f"    User ID: {user['user_id']}")
    print(f"    Username: {user['username']}")
    print(f"    Role: {user['role']}")
except Exception as e:
    print(f"  [ERROR] {type(e).__name__}: {e}")

# Test 2: Wrong password
print("\n[TEST 2] Testing paulr with wrong password...")
try:
    user = lm.authenticate('paulr', 'wrongpassword', '127.0.0.1')
    print("  [ERROR] Should have failed!")
except AuthenticationError as e:
    print(f"  [EXPECTED] AuthenticationError: {e}")
except Exception as e:
    print(f"  [UNEXPECTED] {type(e).__name__}: {e}")

# Test 3: Non-existent user
print("\n[TEST 3] Testing non-existent user...")
try:
    user = lm.authenticate('nonexistent', 'password', '127.0.0.1')
    print("  [ERROR] Should have failed!")
except AuthenticationError as e:
    print(f"  [EXPECTED] AuthenticationError: {e}")
except Exception as e:
    print(f"  [UNEXPECTED] {type(e).__name__}: {e}")
