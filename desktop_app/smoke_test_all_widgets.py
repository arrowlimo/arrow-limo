"""
Smoke Test for Desktop App - Core Widgets
Verifies selected widgets import and instantiate (requires QApplication)
"""

import os
import sys
import psycopg2
from datetime import datetime
from PyQt6.QtWidgets import QApplication

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BOLD = '\033[1m'

class DatabaseConnection:
    """Simple DB wrapper for testing"""
    def __init__(self):
        try:
            self.connection = psycopg2.connect(
                host='localhost',
                database='almsdata',
                user='postgres',
                password='***REMOVED***'
            )
            print(f"{GREEN}✅ Database connection successful{RESET}")
        except Exception as e:
            print(f"{RED}❌ Database connection failed: {e}{RESET}")
            sys.exit(1)

    def get_cursor(self):
        return self.connection.cursor()

def test_widget_import(widget_name, import_statement):
    """Test if a widget imports successfully"""
    try:
        exec(import_statement)
        print(f"{GREEN}✅ {widget_name}: Import successful{RESET}")
        return True
    except Exception as e:
        print(f"{RED}❌ {widget_name}: Import failed - {e}{RESET}")
        return False

def test_widget_instantiation(widget_name, import_stmt, class_name, db, use_db):
    """Test if a widget can be instantiated"""
    try:
        exec(import_stmt, globals())
        WidgetClass = globals()[class_name]
        widget = WidgetClass(db) if use_db else WidgetClass()
        print(f"{GREEN}✅ {widget_name}: Instantiation successful{RESET}")
        return True
    except Exception as e:
        print(f"{RED}❌ {widget_name}: Instantiation failed - {e}{RESET}")
        return False

def main():
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}ARROW LIMOUSINE - DESKTOP APP SMOKE TEST{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Ensure desktop_app on path
    here = os.path.abspath(os.path.dirname(__file__))
    root = os.path.abspath(os.path.join(here, os.pardir))
    for path_candidate in (here, root):
        if path_candidate not in sys.path:
            sys.path.insert(0, path_candidate)

    # Initialize QApplication (required before QWidget)
    app = QApplication(sys.argv)

    # Initialize database
    db = DatabaseConnection()

    # Test cases
    widgets = [
        {
            "name": "Mega Menu Navigator",
            "import": "from mega_menu_widget import MegaMenuWidget",
            "class": "MegaMenuWidget",
            "use_db": False
        },
        {
            "name": "Report Explorer",
            "import": "from report_explorer_widget import ReportExplorerWidget",
            "class": "ReportExplorerWidget",
            "use_db": False
        },
        {
            "name": "Employee Management",
            "import": "from employee_management_widget import EmployeeManagementWidget",
            "class": "EmployeeManagementWidget",
            "use_db": True
        },
        {
            "name": "Vehicle Management",
            "import": "from vehicle_management_widget import VehicleManagementWidget",
            "class": "VehicleManagementWidget",
            "use_db": True
        },
        {
            "name": "Dispatch Management",
            "import": "from dispatch_management_widget import DispatchManagementWidget",
            "class": "DispatchManagementWidget",
            "use_db": True
        },
        {
            "name": "Document Management",
            "import": "from document_management_widget import DocumentManagementWidget",
            "class": "DocumentManagementWidget",
            "use_db": True
        },
        {
            "name": "Admin Management",
            "import": "from admin_management_widget import AdminManagementWidget",
            "class": "AdminManagementWidget",
            "use_db": True
        },
        {
            "name": "Fleet Management",
            "import": "from dashboard_classes import FleetManagementWidget",
            "class": "FleetManagementWidget",
            "use_db": True
        },
        {
            "name": "Financial Dashboard",
            "import": "from dashboard_classes import FinancialDashboardWidget",
            "class": "FinancialDashboardWidget",
            "use_db": True
        },
        {
            "name": "ROE Form Widget",
            "import": "from roe_form_widget import ROEFormWidget",
            "class": "ROEFormWidget",
            "use_db": True
        },
    ]

    passed = 0
    failed = 0

    print(f"{BOLD}Phase 1: Import Tests{RESET}")
    print("-" * 60)
    for widget in widgets:
        if test_widget_import(widget["name"], widget["import"]):
            passed += 1
        else:
            failed += 1
    print()

    print(f"{BOLD}Phase 2: Instantiation Tests{RESET}")
    print("-" * 60)
    for widget in widgets:
        if test_widget_instantiation(widget["name"], widget["import"], widget["class"], db, widget.get("use_db", True)):
            passed += 1
        else:
            failed += 1
    print()

    # Summary
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}TEST SUMMARY{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    total = passed + failed
    print(f"Total Tests: {total}")
    print(f"{GREEN}Passed: {passed}{RESET}")
    print(f"{RED}Failed: {failed}{RESET}")

    if failed == 0:
        print(f"\n{GREEN}{BOLD}🎉 ALL TESTS PASSED!{RESET}")
        app.quit()
        return 0
    else:
        print(f"\n{RED}{BOLD}⚠️ SOME TESTS FAILED - SEE ABOVE FOR DETAILS{RESET}")
        app.quit()
        return 1

if __name__ == "__main__":
    sys.exit(main())
