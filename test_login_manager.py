import sys
sys.path.insert(0, 'L:\\limo\\desktop_app')

from login_manager import LoginManager, AuthenticationError, AccountLockedError

login_mgr = LoginManager()

# Test with test user
try:
    result = login_mgr.authenticate('test', 'test123')
    print(f"✅ Authentication successful: {result}")
except AuthenticationError as e:
    print(f"❌ Authentication error: {e}")
except AccountLockedError as e:
    print(f"❌ Account locked: {e}")
except Exception as e:
    print(f"❌ Unexpected error: {type(e).__name__}: {e}")

# Test with admin user
try:
    result = login_mgr.authenticate('admin', 'admin123')
    print(f"✅ Authentication successful: {result}")
except AuthenticationError as e:
    print(f"❌ Authentication error: {e}")
except AccountLockedError as e:
    print(f"❌ Account locked: {e}")
except Exception as e:
    print(f"❌ Unexpected error: {type(e).__name__}: {e}")
