import sys
sys.path.insert(0, 'L:\\limo\\desktop_app')

print("Testing desktop app imports and widget loading...")

try:
    from main import MainWindow
    print("✅ MainWindow imported successfully")
except Exception as e:
    print(f"❌ MainWindow import failed: {e}")
    sys.exit(1)

try:
    from advanced_mega_menu_widget import MegaMenuWidget
    print("✅ MegaMenuWidget imported successfully")
except Exception as e:
    print(f"❌ MegaMenuWidget import failed: {e}")
    sys.exit(1)

# Test database connection
try:
    from database_connection import DatabaseConnection
    db = DatabaseConnection()
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM charters")
        count = cur.fetchone()[0]
        print(f"✅ Database connected - {count} charters in database")
except Exception as e:
    print(f"❌ Database connection failed: {e}")
    sys.exit(1)

print("\n✅ All prerequisites verified - app is ready to launch")
print("\nNext step: Open the app and test widgets via Navigator menu")
