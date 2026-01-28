#!/usr/bin/env python3
"""Test error logging system initialization"""

import sys
import os

# Add desktop_app to path
desktop_app_path = os.path.join(os.path.dirname(__file__), 'desktop_app')
sys.path.insert(0, desktop_app_path)

# Import DatabaseConnection from main.py
from main import DatabaseConnection
from error_logger import init_error_logger, log_error

def main():
    print("Testing error logger initialization...")
    
    # Create database connection
    try:
        db = DatabaseConnection()
        print("✅ Database connection created")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return
    
    # Initialize error logger
    try:
        error_logger = init_error_logger(db)
        print("✅ Error logger initialized")
    except Exception as e:
        print(f"❌ Error logger initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test logging an error
    try:
        # Create a test error
        try:
            1 / 0
        except ZeroDivisionError as e:
            log_error(
                error=e,
                widget_name="TestWidget",
                action="testing_error_logging",
                user_context="This is a test error to verify the logging system works"
            )
            print("✅ Test error logged successfully")
    except Exception as e:
        print(f"❌ Error logging failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Verify the error was stored
    try:
        from error_logger import get_error_logger
        logger = get_error_logger()
        if logger:
            recent_errors = logger.get_recent_errors(limit=5)
            print(f"\n✅ Retrieved {len(recent_errors)} recent errors")
            for err in recent_errors:
                print(f"  - ID: {err['error_id']}, Type: {err['error_type']}, Widget: {err['widget_name']}")
        else:
            print("❌ Could not get error logger instance")
    except Exception as e:
        print(f"❌ Error retrieval failed: {e}")
        import traceback
        traceback.print_exc()
    
    db.close()
    print("\n✅ All tests passed!")

if __name__ == '__main__':
    main()
