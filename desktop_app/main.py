"""
Arrow Limousine Management System - Desktop Application (PyQt6)
Form-based UI with tab navigation, auto-fill, print, drill-down reports

CRITICAL BUSINESS RULES IMPLEMENTED:
- reserve_number is ALWAYS the business key for charter-payment matching
- GST is INCLUDED in gross amounts (Alberta 5% GST)
- Always commit database changes (conn.commit())
            logger.error("Database initialization error: %s", e)
- Protected patterns: recurring payments, NSF charges, inter-account transfers
"""

import os
import sys

# Fix Windows console encoding for unicode (emoji support)
if sys.platform == "win32":
    import io
    # Only wrap if sys.stdout/sys.stderr are not None and have 'buffer' attribute
    if getattr(sys, "stdout", None) is not None and hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if getattr(sys, "stderr", None) is not None and hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from dotenv import load_dotenv

# Load environment variables from .env file FIRST
load_dotenv()

# App-wide logging
import logging

try:
    from app_logger import install_excepthook, setup_logging
except ModuleNotFoundError:
    from app_logger import install_excepthook, setup_logging

_root_logger = setup_logging()
install_excepthook(_root_logger)
logger = logging.getLogger(__name__)

import binascii
import hashlib
import hmac
from datetime import datetime

from PyQt6.QtCore import QEvent, QSettings, Qt, QTimer
from PyQt6.QtGui import (
    QAction,
    QKeySequence,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

# Add current directory and project root to path for module imports
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, os.pardir))
for path_candidate in (current_dir, project_root):
    if path_candidate not in sys.path:
        sys.path.insert(0, path_candidate)

# Database utilities
# Accounting-focused reports
from asset_management_widget import AssetManagementWidget
from charter_form_widget import CharterFormWidget
from db_connection import DatabaseConnection
from enhanced_banking_manager import EnhancedBankingManager
from enhanced_receipts_manager import EnhancedReceiptsManager
from nsf_pair_manager_widget import NsfPairManagerWidget

try:
    from report_management_widget import ReportManagementWidget
except ImportError:
    from report_explorer_widget import ReportExplorerWidget

    class ReportManagementWidget(ReportExplorerWidget):
        def __init__(self, db=None) -> None:
            super().__init__()
# AI Copilot
from copilot_widget import CopilotWidget
from crystal_reports_widget import CrystalReportsWidget

# Dashboard widget classes are imported lazily inside launch_dashboard_from_menu()
# and individual factory methods — keeps ~8 heavy modules off the startup path.
from dashboards_analytics import CustomReportBuilderWidget

# Dispatch, calendar, and drill-down widgets are imported inside their factory
# methods so they only load when that tab is first opened.
from error_logger import init_error_logger
from function_executor import FunctionExecutor
from llm_engine import LLMEngine
from rag_engine import KnowledgeRetriever
from report_explorer_widget import ReportExplorerWidget
from ui_standards import GridStandardsManager, install_replace_all_behavior
from year_end_management_widget import YearEndManagementWidget
from year_end_wizard_widget import YearEndWizardWidget


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored hash (pbkdf2_sha256 only).

    Stored format: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
    """
    if not stored_hash or password is None:
        return False

    if not stored_hash.startswith("pbkdf2_sha256$"):
        return False

    try:
        _, iteration_str, salt_hex, hash_hex = stored_hash.split("$", 3)
        iterations = int(iteration_str)
        salt = binascii.unhexlify(salt_hex)
        expected = binascii.unhexlify(hash_hex)
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iterations
        )
        return hmac.compare_digest(candidate, expected)
    except Exception:
        return False


# ============================================================================
# MAIN APPLICATION WINDOW
# ============================================================================


class MainWindow(QMainWindow):
    """Main application window with tab-based interface"""

    def __init__(
        self,
        db: DatabaseConnection | None = None,
        auth_user: dict | None = None,
    ) -> None:
        logger.debug("MainWindow.__init__ START")
        super().__init__()
        logger.debug("  1. super().__init__() OK")

        self.auth_user = auth_user or {}
        self._activity_event_types = {
            QEvent.Type.KeyPress,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.MouseMove,
            QEvent.Type.Wheel,
            QEvent.Type.FocusIn,
        }
        user_suffix = (
            f" - {self.auth_user.get('username')}"
            if self.auth_user.get("username")
            else ""
        )
        self.setWindowTitle(
            f"Arrow Limousine Management System (Desktop){user_suffix}"
        )
        self.setMinimumSize(1024, 700)
        self._loading_receipts = False
        self._current_receipt_filters = None

        # Initialize eHOS inspection forms directory
        try:
            inspections_dir = os.path.join(
                os.path.dirname(__file__), "..", "data", "inspections"
            )
            os.makedirs(inspections_dir, exist_ok=True)
        except Exception:
            pass  # Non-critical

        logger.warning("  2. Basic init OK")

        # Initialize database
        try:
            logger.debug("  3. Creating DatabaseConnection...")
            self.db = db if db else DatabaseConnection()
            logger.debug("  4. DatabaseConnection OK")
        except Exception as e:
            try:
                self.db.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            logger.warning(f"  ❌ Database Error: {e}")
            QMessageBox.critical(
                self, "Database Error", f"Cannot connect to database:\n{e}"
            )
            sys.exit(1)

        # Initialize error logging system
        try:
            logger.warning("  4.5. Initializing error logger...")
            self.error_logger = init_error_logger(self.db)
            logger.warning("  [OK] Error logging system initialized")
        except Exception as e:
            logger.warning("Error logger initialization failed: %s", e)
            # Non-fatal - app can continue without error logging

        logger.warning("  5. Creating central widget...")
        # Wrapper widget to host global search + tabs
        central = QWidget()
        central_layout = QVBoxLayout()
        central_layout.setContentsMargins(5, 5, 5, 5)
        central_layout.setSpacing(6)

        # Global search bar (multi-table)
        search_bar = QHBoxLayout()
        search_bar.setSpacing(6)
        search_label = QLabel("Global Search:")
        self.global_search_input = QLineEdit()
        self.global_search_input.setPlaceholderText(
            "Search receipts, charters, clients..."
        )
        self.global_search_button = QPushButton("Search")
        self.global_search_button.clicked.connect(self.global_search)
        self.columns_button = QPushButton("Columns")
        self.columns_button.clicked.connect(self.show_focused_grid_columns)
        self.reset_grid_layout_button = QPushButton("Reset Grid Layout")
        self.reset_grid_layout_button.clicked.connect(
            self.reset_focused_grid_layout
        )
        search_bar.addWidget(search_label)
        search_bar.addWidget(self.global_search_input, 1)
        search_bar.addWidget(self.global_search_button)
        search_bar.addWidget(self.columns_button)
        search_bar.addWidget(self.reset_grid_layout_button)
        central_layout.addLayout(search_bar)
        logger.warning("  6. Search bar OK")

        # Global UI behavior manager for all grids and input focus behavior.
        self.grid_standards = GridStandardsManager("ArrowLimo", "Desktop")

        # Create tab interface
        logger.warning("  7. Creating main QTabWidget...")
        self.tabs = QTabWidget()

        # Track which tabs have been loaded (for lazy loading)
        self._lazy_tab_factories = {
            "🚀 Operations": self.create_operations_parent_tab,
            "🚗 Fleet Management": self.create_fleet_people_parent_tab,
            "💰 Accounting & Finance": self.create_accounting_parent_tab,
            "🧮 Year-End Audit": self.create_year_end_audit_tab,
            "⚙️ Admin & Settings": self.create_admin_parent_tab,
        }
        self._tabs_loaded = set()
        self._tab_load_in_progress = set()
        self.tabs.currentChanged.connect(self._on_tab_changed)

        central_layout.addWidget(self.tabs)
        central.setLayout(central_layout)
        self.setCentralWidget(central)
        self.status_bar = QStatusBar()
        user_display = self.auth_user.get("username", "Guest")
        role_display = self.auth_user.get("role", "unknown")
        db_target = (os.getenv("DB_TARGET", "neon") or "neon").lower()
        if db_target == "local":
            mode_display = "Emergency Local"
        elif db_target == "web":
            mode_display = "Web"
        else:
            mode_display = "Cloud"
        self.status_bar.showMessage(
            f"{user_display} connected to {mode_display} | Role: "
            f"{role_display}"
        )
        self.setStatusBar(self.status_bar)

        # Initialize database connection monitor
        try:
            from db_connection_monitor import DatabaseConnectionMonitor

            logger.debug("  7.5. Initializing database connection monitor...")
            self.db_monitor = DatabaseConnectionMonitor(
                self.db, check_interval_ms=15000
            )
            self.db_monitor.connection_lost.connect(
                self._on_db_connection_lost
            )
            self.db_monitor.connection_restored.connect(
                self._on_db_connection_restored
            )
            self.db_monitor.status_changed.connect(self._on_db_status_changed)
            self.db_monitor.start_monitoring()
            logger.debug("  [OK] Database connection monitoring started")
        except Exception as e:
            logger.warning("Could not start connection monitoring: %s", e)
            # Non-fatal - app can continue without monitoring

        # Session timeout (defaults to 30 minutes, configurable via env)
        try:
            self._session_timeout_minutes = int(
                os.getenv("SESSION_TIMEOUT_MINUTES", "30")
            )
        except ValueError:
            self._session_timeout_minutes = 30

        self._last_activity = datetime.now()
        self._session_timer = QTimer()
        self._session_timer.timeout.connect(self._check_session_timeout)
        self._session_timer.start(60000)  # Check every minute

        # Track activity globally so child dialogs/forms reset inactivity
        # timeout.
        QApplication.instance().installEventFilter(self)

        # Add logout menu
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        
        settings_action = QAction("⚙️ Settings", self)
        settings_action.triggered.connect(self._open_user_settings)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        logout_action = QAction("Logout", self)
        logout_action.triggered.connect(self._logout)
        file_menu.addAction(logout_action)

        # Add Management menu with enhanced widgets
        management_menu = menubar.addMenu("Management")
        logger.warning("  ✓ Management menu created")

        receipts_mgr_action = QAction("📋 Enhanced Receipts Manager", self)
        receipts_mgr_action.triggered.connect(
            self._open_enhanced_receipts_manager
        )
        management_menu.addAction(receipts_mgr_action)
        logger.warning("  ✓ Receipts Manager action added")

        banking_mgr_action = QAction("🏦 Enhanced Banking Manager", self)
        banking_mgr_action.triggered.connect(
            self._open_enhanced_banking_manager
        )
        management_menu.addAction(banking_mgr_action)
        logger.warning("  ✓ Banking Manager action added")

        logger.warning("  8. Main tab widget created")

        # Removed: Navigator tab (Mega Menu) - users prefer direct management
        # tabs
        # Users said they look up management tabs directly rather than use the
        # menu navigator

        # Consolidated parent tabs with sub-tabs
        logger.warning("  9. Creating Operations tab (placeholder for lazy loading)...")
        try:
            # Create placeholder - real widgets created on first click
            placeholder = QLabel("Loading Operations widgets...")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabs.addTab(placeholder, "🚀 Operations")
            logger.debug("  10. Operations tab placeholder OK")
        except Exception:
            logger.exception("Operations tab initialization failed")
            raise

        logger.warning("  11. Creating Fleet Management tab...")
        try:
            placeholder = QLabel("Loading Fleet widgets...")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabs.addTab(placeholder, "🚗 Fleet Management")
            logger.debug("  12. Fleet Management tab OK")
        except Exception:
            logger.exception("Fleet Management tab initialization failed")
            raise

        logger.warning("  13. Creating Accounting tab (placeholder for lazy loading)...")
        try:
            # Create placeholder - real widgets created on first click
            placeholder = QLabel("Loading Accounting widgets...")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabs.addTab(placeholder, "💰 Accounting & Finance")
            logger.debug("  14. Accounting tab placeholder OK")
        except Exception:
            logger.exception("Accounting tab initialization failed")
            raise

        # Custom Report Builder - moved after Accounting as requested
        logger.warning("  15. Creating Custom Report Builder...")
        try:
            self.custom_report = CustomReportBuilderWidget(self.db)
            self.tabs.addTab(self.custom_report, "📊 Custom Reports")
            logger.debug("  15a. Custom Report Builder OK")
        except Exception as e:
            try:
                self.db.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            logger.error("Custom Report Builder initialization failed: %s", e)
            # Fallback to ReportExplorer if CustomReportBuilder fails
            try:
                self.report_explorer = ReportExplorerWidget()
                self.report_explorer.report_selected.connect(
                    self.launch_dashboard_from_menu
                )
                self.tabs.addTab(self.report_explorer, "📑 Reports")
                logger.debug("  16b. ReportExplorerWidget (fallback) OK")
            except Exception as e2:
                try:
                    self.db.rollback()
                except Exception as _e:
                    logger.debug('Suppressed: %s', _e)
                logger.error("ReportExplorer fallback initialization failed: %s", e2)

        # Crystal Reports
        logger.warning("  16c. Creating Crystal Reports tab...")
        try:
            self.crystal_reports = CrystalReportsWidget(self.db)
            self.tabs.addTab(self.crystal_reports, "💎 Crystal Reports")
            logger.debug("  16c. Crystal Reports OK")
        except Exception as e:
            try:
                self.db.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            logger.error("Crystal Reports initialization failed: %s", e)

        # Overdue Balance Aging Report
        logger.warning("  16d. Creating Overdue Balance Aging Report tab...")
        try:
            from overdue_balance_report import OverdueBalanceReportWidget
            self.overdue_report = OverdueBalanceReportWidget(self.db)
            self.tabs.addTab(self.overdue_report, "⚠️ Overdue Balances")
            logger.debug("  16d. Overdue Balance Report OK")
        except Exception as e:
            try:
                self.db.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            logger.error("Overdue Balance Report initialization failed: %s", e)

        logger.warning("  16d. Creating Year-End Audit tab (placeholder for lazy"
            "loading)...")
        try:
            placeholder = QLabel("Loading Year-End audit system...")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabs.addTab(placeholder, "🧮 Year-End Audit")
            logger.debug("  16d. Year-End Audit placeholder OK")
        except Exception as e:
            logger.error("Year-End Audit tab initialization failed: %s", e)

        logger.warning("  17. Creating Admin tab...")
        try:
            placeholder = QLabel("Loading Admin widgets...")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            admin_index = self.tabs.addTab(placeholder, "⚙️ Admin & Settings")
            allowed_admin_roles = {
                "admin",
                "management",
                "manager",
                "super_user",
            }
            if (
                self.auth_user
                and str(self.auth_user.get("role", "")).lower()
                not in allowed_admin_roles
            ):
                self.tabs.setTabEnabled(admin_index, False)
            logger.debug("  20. Admin tab OK")
        except Exception:
            try:
                self.db.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            logger.exception("Admin tab initialization failed")
            raise

        # Initialize AI Copilot Tab
        logger.warning("  21. Initializing AI Copilot...")
        try:
            self.rag_engine = KnowledgeRetriever()
            self.llm_engine = LLMEngine()
            self.function_executor = FunctionExecutor(user_role="analyst")

            self.copilot_widget = CopilotWidget(
                rag_engine=self.rag_engine,
                llm_engine=self.llm_engine,
                executor=self.function_executor,
            )
            self.tabs.addTab(self.copilot_widget, "🤖 AI Copilot")
            logger.debug("  21a. AI Copilot OK")
        except Exception as e:
            logger.warning("AI Copilot initialization error: %s", e)
            # Copilot is optional - don't crash if it fails
            try:
                error_label = QLabel(f"AI Copilot unavailable: {str(e)[:100]}")
                error_label.setStyleSheet("color: red;")
                self.tabs.addTab(error_label, "🤖 AI Copilot")
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
        # Connect browse reservations double-click to show booking form tab
        if hasattr(self, "enhanced_charter_widget") and hasattr(
            self, "operations_tabs"
        ):
            self.enhanced_charter_widget.show_booking_tab_signal.connect(
                self._on_show_booking_tab_requested
            )

        # ============================================================================
        # PHASE 1 UX UPGRADES - KEYBOARD SHORTCUTS
        # ============================================================================
        # Global keyboard shortcuts for power users
        QShortcut(
            QKeySequence("Ctrl+N"), self, self.new_receipt
        )  # New receipt
        QShortcut(QKeySequence("Ctrl+S"), self, self.save_current_form)  # Save
        QShortcut(QKeySequence("Ctrl+F"), self, self.open_find)  # Find
        QShortcut(QKeySequence("Ctrl+E"), self, self.export_table)  # Export
        QShortcut(QKeySequence("Ctrl+P"), self, self.print_document)  # Print
        QShortcut(
            QKeySequence("Ctrl+Z"), self, self.undo_action
        )  # Undo (stub)
        QShortcut(
            QKeySequence("Ctrl+D"), self, self.duplicate_record
        )  # Duplicate
        QShortcut(QKeySequence("Delete"), self, self.delete_record)  # Delete
        QShortcut(QKeySequence("F5"), self, self.refresh_data)  # Refresh
        QShortcut(
            QKeySequence("Ctrl+W"), self, self.close_current_tab
        )  # Close tab
        QShortcut(
            QKeySequence("Ctrl+F4"), self, self.close_current_tab
        )  # Close tab

        self.show()
        # Apply UI standards to initial widget tree.
        self._apply_global_ui_standards(self)
        # Silent auto-update check 3 seconds after startup
        try:
            from auto_updater import AutoUpdater
            _updater = AutoUpdater(parent_widget=self)
            from PyQt6.QtCore import QTimer as _QTimer
            _QTimer.singleShot(3000, lambda: _updater.check_for_updates(silent=True))
            self._auto_updater = _updater  # keep reference alive
        except Exception as _ue:
            logger.debug("Auto-updater init skipped: %s", _ue)

    # ============================================================================
    # LAZY LOADING - Load tab content only when first clicked
    # ============================================================================
    def _on_tab_changed(self, index: int) -> None:
        """Load tab content on first access (lazy loading)"""
        if index < 0:
            return

        tab_text = self.tabs.tabText(index)
        if tab_text not in self._lazy_tab_factories:
            return

        # Prevent re-entrant loads or repeat loads
        if (
            tab_text in self._tabs_loaded
            or tab_text in self._tab_load_in_progress
        ):
            return

        self._tab_load_in_progress.add(tab_text)
        logger.debug(f"[LOAD] Loading tab: {tab_text}")

        self.tabs.blockSignals(True)
        try:
            real_widget = self._lazy_tab_factories[tab_text]()
            self.tabs.removeTab(index)
            self.tabs.insertTab(index, real_widget, tab_text)
            self.tabs.setCurrentIndex(index)
            self._apply_global_ui_standards(real_widget)
            self._tabs_loaded.add(tab_text)
            logger.debug(f"[LOAD] {tab_text} loaded successfully")
        except Exception as e:
            logger.exception("Failed to load tab %s", tab_text)
            error_widget = QLabel(f"Error loading {tab_text}:\n{e!s}")
            error_widget.setStyleSheet("color: red; padding: 20px;")
            error_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabs.removeTab(index)
            self.tabs.insertTab(index, error_widget, tab_text)
            self.tabs.setCurrentIndex(index)
            self._tabs_loaded.add(tab_text)
        finally:
            self.tabs.blockSignals(False)
            self._tab_load_in_progress.discard(tab_text)

    # ============================================================================
    # KEYBOARD SHORTCUT HANDLERS
    # ============================================================================
    def new_receipt(self) -> None:
        """Ctrl+N: Create new receipt"""
        # Navigate to Receipts tab and clear form
        self.tabs.setCurrentIndex(2)  # Accounting tab
        QMessageBox.information(
            self,
            "New Receipt",
            "New receipt form ready\n[Focus on Receipt entry area]",
        )

    def save_current_form(self) -> None:
        """Ctrl+S: Save current form"""
        QMessageBox.information(
            self,
            "Save",
            "Saving current form...\n[Implementation context-specific]",
        )

    def export_table(self) -> None:
        """Ctrl+E: Export current table"""
        QMessageBox.information(
            self,
            "Export",
            "Exporting table to CSV...\n[Full implementation pending]",
        )

    def print_document(self) -> None:
        """Ctrl+P: Print current view - routes to appropriate print function"""
        current_tab = self.tabs.currentWidget()
        if not current_tab:
            QMessageBox.information(self, "Print", "No document to print")
            return

        # Determine what to print based on current tab
        tab_name = self.tabs.tabText(self.tabs.currentIndex())

        if "Charter" in tab_name or "Booking" in tab_name:
            # Show print options for charter
            reply = QMessageBox.question(
                self,
                "Print Charter",
                "What would you like to print?\n\n"
                "Click 'Yes' for Invoice\n"
                "Click 'No' for Confirmation",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.print_invoice()
            else:
                self.print_confirmation()
        elif "Quote" in tab_name:
            QMessageBox.information(
                self, "Print", "Use the Quote tab's Print Quote button"
            )
        elif "Beverage" in tab_name:
            QMessageBox.information(
                self, "Print", "Use beverage print options in the charter form"
            )
        else:
            QMessageBox.information(
                self,
                "Print",
                f"Printing for {tab_name} tab\n[Custom printing to be"
                f"implemented]",
            )

    def undo_action(self) -> None:
        """Ctrl+Z: Undo last action"""
        focus = QApplication.focusWidget()
        if focus and hasattr(focus, "undo"):
            try:
                focus.undo()
                return
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
        if self.grid_standards.undo_for_widget(focus):
            return

        QMessageBox.information(self, "Undo", "Nothing to undo.")

    def show_focused_grid_columns(self) -> None:
        """Open column visibility picker for the currently focused grid."""
        focus = QApplication.focusWidget()
        if not self.grid_standards.show_column_selector_for_widget(focus):
            QMessageBox.information(
                self,
                "Columns",
                "Focus a grid first, then click Columns.",
            )

    def reset_focused_grid_layout(self) -> None:
        """Reset the saved layout for the currently focused grid."""
        focus = QApplication.focusWidget()
        if not self.grid_standards.reset_layout_for_widget(focus):
            QMessageBox.information(
                self,
                "Reset Grid Layout",
                "Focus a grid first, then click Reset Grid Layout.",
            )

    def _apply_global_ui_standards(self, root_widget: QWidget) -> None:
        """Apply global grid and field-focus behavior to a widget subtree."""
        try:
            self.grid_standards.apply_to_widget(root_widget)
            install_replace_all_behavior(root_widget)
        except Exception as e:
            logger.warning("UI standards apply failed: %s", e)

    def duplicate_record(self) -> None:
        """Ctrl+D: Duplicate selected record"""
        QMessageBox.information(
            self,
            "Duplicate",
            "Duplicate record...\n[Full implementation pending]",
        )

    def delete_record(self) -> None:
        """Delete: Delete selected record"""
        reply = QMessageBox.question(
            self,
            "Delete",
            "Delete selected record? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(
                self,
                "Deleted",
                "Record deleted.\n[Full implementation pending]",
            )

    def close_current_tab(self) -> None:
        """Close the current tab via an explicit shortcut."""
        current = self.tabs.currentIndex()
        if current > 0:  # Don't close Navigator
            self.tabs.removeTab(current)

    def _check_session_timeout(self) -> None:
        """Check for session timeout based on global activity."""
        timeout_seconds = self._session_timeout_minutes * 60
        if (
            datetime.now() - self._last_activity
        ).total_seconds() > timeout_seconds:
            QMessageBox.warning(
                self,
                "Session Timeout",
                "Your session has timed out due to inactivity.",
            )
            self._logout()

    def _mark_activity(self) -> None:
        """Record user activity timestamp for session timeout checks."""
        self._last_activity = datetime.now()

    def eventFilter(self, obj, event) -> object:
        """Capture activity and provide global Enter-as-Tab navigation for"
        "form inputs."""

        if event.type() in self._activity_event_types:
            self._mark_activity()

        # Block scroll wheel from accidentally changing spinboxes / combos
        # while the user scrolls the page.  Only allow wheel changes once
        # the control has keyboard focus (i.e. the user clicked into it).
        if (event.type() == QEvent.Type.Wheel
                and isinstance(obj, (
                    QSpinBox, QDoubleSpinBox,
                    QDateEdit, QTimeEdit,
                    QComboBox,
                ))
                and not obj.hasFocus()):
            return True  # consume – don't change the control

        if event.type() == QEvent.Type.KeyPress and hasattr(event, "key"):
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                widget = (
                    obj
                    if isinstance(obj, QWidget)
                    else QApplication.focusWidget()
                )

                if widget and self._should_move_focus_on_enter(widget):
                    widget.focusNextChild()
                    return True

        return super().eventFilter(obj, event)

    def _should_move_focus_on_enter(self, widget: QWidget) -> bool:
        """Return True when Enter should act like Tab for the focused"
        "widget."""

        # Keep natural behavior for action controls and rich text editors.
        if isinstance(widget, (QPushButton, QTextEdit, QPlainTextEdit)):
            return False

        # Do not hijack Enter in table/list-like controls.
        if isinstance(widget, (QAbstractItemView, QTableWidget)):
            return False

        # If a combo dropdown is open, Enter should select from the popup
        # first.
        if isinstance(widget, QComboBox):
            try:
                if widget.view().isVisible():
                    return False
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            return True

        # Core line/form input controls should advance focus on Enter.
        if isinstance(
            widget, (QLineEdit, QDateEdit, QTimeEdit, QSpinBox, QDoubleSpinBox)
        ):
            return True

        # Fallback: if widget can take focus, treat Enter as move-next.
        return widget.focusPolicy() != Qt.FocusPolicy.NoFocus

    def _on_db_connection_lost(self) -> None:
        """Handler for database connection lost signal"""
        logger.warning("Database connection lost - user will see warning")
        # Update status bar with error
        self.status_bar.setStyleSheet(
            "background-color: #ffcccb; color: #8b0000;"
        )
        self.status_bar.showMessage(
            "❌ Database: Connection Lost - Cannot save or load data"
        )

    def _on_db_connection_restored(self) -> None:
        """Handler for database connection restored signal"""
        logger.info("Database connection restored")
        # Update status bar back to normal
        self.status_bar.setStyleSheet("")
        user_display = self.auth_user.get("username", "Guest")
        db_target = (os.getenv("DB_TARGET", "neon") or "neon").lower()
        if db_target == "local":
            mode_display = "Emergency Local"
        elif db_target == "web":
            mode_display = "Web"
        else:
            mode_display = "Cloud"
        self.status_bar.showMessage(
            f"✅ {user_display} connected to {mode_display}"
        )

        # Show success notification
        QMessageBox.information(
            self,
            "Connection Restored",
            "✅ Database connection has been restored.\n\nYou can now save and"
            "load data normally.",
        )

    def _on_db_status_changed(self, is_online, status_message) -> None:
        """Handler for any database status change"""
        if is_online:
            self.status_bar.setStyleSheet("")
            user_display = self.auth_user.get("username", "Guest")
            db_target = (os.getenv("DB_TARGET", "neon") or "neon").lower()
            if db_target == "local":
                mode_display = "Emergency Local"
            elif db_target == "web":
                mode_display = "Web"
            else:
                mode_display = "Cloud"
            self.status_bar.showMessage(
                f"{user_display} connected to {mode_display}"
            )
        else:
            self.status_bar.setStyleSheet(
                "background-color: #ffcccb; color: #8b0000;"
            )
            self.status_bar.showMessage("Connection issue - reconnecting")

    def _logout(self) -> None:
        """Logout and return to login screen"""
        reply = QMessageBox.question(
            self,
            "Logout",
            "Are you sure you want to logout?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.close()
            QApplication.quit()

    def _open_user_settings(self) -> None:
        """Open user settings dialog"""
        try:
            from user_settings_dialog import UserSettingsDialog
            
            dialog = UserSettingsDialog(self, self.auth_user, self.db)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to open settings:\n{e}"
            )

    def _open_enhanced_receipts_manager(self) -> None:
        """Open enhanced receipts management widget."""
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("Enhanced Receipts Manager")
            dialog.setGeometry(100, 100, 1400, 800)

            layout = QVBoxLayout(dialog)
            manager = EnhancedReceiptsManager(self.db, dialog)
            layout.addWidget(manager)

            dialog.exec()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to open receipts manager:\n{e}"
            )

    def _open_enhanced_banking_manager(self) -> None:
        """Open enhanced banking management widget."""
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("Enhanced Banking Manager")
            dialog.setGeometry(100, 100, 1400, 800)

            layout = QVBoxLayout(dialog)
            manager = EnhancedBankingManager(self.db, dialog)
            layout.addWidget(manager)

            dialog.exec()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to open banking manager:\n{e}"
            )

    def _on_show_booking_tab_requested(self, charter_data: dict) -> None:
        """Handle request to show booking form tab from charter lookup"""
        # Switch to the Booking/Charter tab, then to the Run Charter sub-tab
        if hasattr(self, "operations_tabs") and hasattr(
            self, "booking_tab_index"
        ):
            self.operations_tabs.setCurrentIndex(self.booking_tab_index)

            # Switch to "Run Charter" sub-tab (index 1) within Booking/Charter
            if hasattr(self, "booking_tab_widget"):
                self.booking_tab_widget.setCurrentIndex(
                    1
                )  # Switch to Run Charter tab

                # Load charter data into form if provided
                if hasattr(self, "charter_form") and charter_data:
                    charter_id = charter_data.get("charter_id")
                    if charter_id:
                        self.charter_form.load_charter(charter_id)

    def mousePressEvent(self, event) -> None:
        """Track user activity"""
        self._mark_activity()
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        """Track user activity"""
        self._mark_activity()
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        """Handle application shutdown gracefully - prevents crash on VS Code"
        "close"""

        try:
            # Stop session timer
            if hasattr(self, "_session_timer"):
                self._session_timer.stop()

            # Unregister global event filter
            app = QApplication.instance()
            if app:
                app.removeEventFilter(self)

            # Close database connections
            if hasattr(self, "db") and self.db:
                try:
                    self.db.close()
                except Exception as _e:
                    logger.debug('Suppressed: %s', _e)
            # Accept the close event
            event.accept()
            logger.warning("Application shutdown complete")
        except Exception as e:
            logger.warning("Warning during shutdown: %s", e)
            event.accept()  # Close anyway

    def safe_add_tab(
        self, tabs: QTabWidget, tab_widget: QWidget, tab_name: str
    ) -> None:
        """
        Safely add a tab with error handling.
        If widget creation fails, shows error message instead of crashing.
        """
        try:
            if tab_widget is None:
                raise ValueError(
                    f"Widget creation returned None for {tab_name}"
                )
            tabs.addTab(tab_widget, tab_name)
            self._apply_global_ui_standards(tab_widget)
        except Exception as e:
            # Create error label if widget fails
            error_label = QLabel(
                f"❌ Error loading {tab_name}:\n{str(e)[:100]}"
            )
            error_label.setStyleSheet(
                "color: red; font-weight: bold; padding: 20px;"
            )
            error_label.setWordWrap(True)
            tabs.addTab(error_label, tab_name)
            logger.warning(f"⚠️  Error loading {tab_name}: {e}")

    def launch_dashboard_from_menu(self, class_name: str, display_name: str) -> None:
        """Step 4: Signal handler to launch dashboard from mega menu"""
        try:
            import accountant_notes_widget
            import accounting_reports
            import beverage_reconciliation_widget
            import dashboards_analytics
            import dashboards_core
            import dashboards_customer
            import dashboards_ml
            import dashboards_operations
            import dashboards_optimization
            import dashboards_predictive
            import payroll_entry_widget
            import roe_form_widget
            import usage_telemetry_widget
            import wcb_rate_widget

            all_modules = [
                dashboards_core,
                dashboards_operations,
                dashboards_predictive,
                dashboards_optimization,
                dashboards_customer,
                dashboards_analytics,
                dashboards_ml,
                accounting_reports,
                accountant_notes_widget,
                beverage_reconciliation_widget,
                payroll_entry_widget,
                wcb_rate_widget,
                roe_form_widget,
                usage_telemetry_widget,
            ]

            widget_class = None
            for module in all_modules:
                widget_class = getattr(module, class_name, None)
                if widget_class:
                    break

            if widget_class:
                widget = widget_class(self.db)
                tab_idx = self.tabs.addTab(widget, display_name)
                self.tabs.setCurrentIndex(tab_idx)
                self._apply_global_ui_standards(widget)
                logger.debug(f"✅ Launched: {display_name} ({class_name})")
            else:
                QMessageBox.warning(
                    self,
                    "Widget Not Found",
                    f"Cannot find widget class: {class_name}",
                )
                logger.warning(f"❌ Widget not found: {class_name}")
        except Exception as e:
            try:
                self.db.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.critical(
                self, "Launch Error", f"Error launching {display_name}:\n{e}"
            )
            logger.warning(f"❌ Error launching {display_name}: {e}")

    def create_fleet_people_parent_tab(self) -> QWidget:
        """Consolidated Fleet & People: Vehicles, Employees"""
        parent = QWidget()
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()

        self._fleet_subtab_factories = {
            "🚐 Vehicles": self.create_vehicles_tab,
            "🚗 Fleet List": self.create_enhanced_vehicle_tab,
            "👔 Employees": self.create_employees_tab,
        }
        self._fleet_subtabs_loaded = set()
        self._fleet_subtabs_in_progress = set()

        for sub_tab_name in self._fleet_subtab_factories:
            placeholder = QLabel(f"Loading {sub_tab_name}...")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tabs.addTab(placeholder, sub_tab_name)

        tabs.currentChanged.connect(
            lambda idx: self._on_fleet_subtab_changed(tabs, idx)
        )

        # Eager-load first fleet sub-tab only
        self._on_fleet_subtab_changed(tabs, 0)

        layout.addWidget(tabs)
        return parent

    def _on_fleet_subtab_changed(self, tabs: QTabWidget, index: int) -> None:
        """Load Fleet sub-tab content on first access."""
        if index < 0:
            return

        tab_text = tabs.tabText(index)
        if tab_text not in self._fleet_subtab_factories:
            return

        if (
            tab_text in self._fleet_subtabs_loaded
            or tab_text in self._fleet_subtabs_in_progress
        ):
            return

        self._fleet_subtabs_in_progress.add(tab_text)
        tabs.blockSignals(True)
        try:
            real_widget = self._fleet_subtab_factories[tab_text]()
            tabs.removeTab(index)
            tabs.insertTab(index, real_widget, tab_text)
            tabs.setCurrentIndex(index)
            self._apply_global_ui_standards(real_widget)
            self._fleet_subtabs_loaded.add(tab_text)
        except Exception as e:
            logger.exception("Failed to load fleet sub-tab %s", tab_text)
            error_widget = QLabel(f"Error loading {tab_text}:\n{e!s}")
            error_widget.setStyleSheet("color: red; padding: 20px;")
            error_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tabs.removeTab(index)
            tabs.insertTab(index, error_widget, tab_text)
            tabs.setCurrentIndex(index)
            self._fleet_subtabs_loaded.add(tab_text)
        finally:
            tabs.blockSignals(False)
            self._fleet_subtabs_in_progress.discard(tab_text)

    def create_accounting_parent_tab(self) -> QWidget:
        """Consolidated Accounting & Finance: Receipts, Tax, Business,"
        "Financial Reports, Payroll"""

        parent = QWidget()
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        self.accounting_parent_tabs = tabs

        # Nested lazy-loading for Accounting sub-tabs.
        # This keeps open time fast and limits fault impact.
        self._accounting_subtab_factories = {
            "🎯 Accounting Hub": self.create_accounting_control_center_tab,
            "💰 Receipts & Invoices": (
                lambda: self.create_accounting_tab_with_parent(tabs)
            ),
            "📝 Accountant Notes": self.create_accountant_notes_tab,
            "📒 Check Book Management": self.create_checkbook_management_tab,
            "🏦 Enhanced Banking Manager": self.create_enhanced_banking_tab,
            "🧩 NSF Pair Manager": self.create_nsf_pair_manager_tab,
            "🧾 Enhanced Receipts Manager": self.create_enhanced_receipts_tab,
            "📋 Vendor Invoice Manager": self.create_vendor_invoice_tab,
            "💵 Payroll Entry": self.create_payroll_entry_tab,
            "🧮 Payroll Remittances": self.create_payroll_remittances_tab,
            "🏛️ Tax Management": self.create_tax_management_tab,
            "📋 T2 Corporate Tax": self.create_t2_data_entry_tab,
            "🛡️ WCB Rates": self.create_wcb_rates_tab,
            "🏢 Business Entity": self.create_business_entity_tab,
            "📦 Asset Inventory": lambda: AssetManagementWidget(),
            "📊 Financial Reports": self.create_reports_tab,
            "🍷 Beverage Revenue": self.create_beverage_accounting_tab,
            "🍷 Beverage Management": self.create_beverage_management_tab,
        }
        self._accounting_subtabs_loaded = set()
        self._accounting_subtabs_in_progress = set()

        for sub_tab_name in self._accounting_subtab_factories:
            placeholder = QLabel(f"Loading {sub_tab_name}...")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tabs.addTab(placeholder, sub_tab_name)

        tabs.currentChanged.connect(
            lambda idx: self._on_accounting_subtab_changed(tabs, idx)
        )

        # Eager-load first accounting sub-tab only
        self._on_accounting_subtab_changed(tabs, 0)

        layout.addWidget(tabs)
        return parent

    def _on_accounting_subtab_changed(self, tabs: QTabWidget, index: int) -> None:
        """Load Accounting sub-tab content on first access."""
        if index < 0:
            return

        tab_text = tabs.tabText(index)
        if tab_text not in self._accounting_subtab_factories:
            return

        if (
            tab_text in self._accounting_subtabs_loaded
            or tab_text in self._accounting_subtabs_in_progress
        ):
            return

        self._accounting_subtabs_in_progress.add(tab_text)
        tabs.blockSignals(True)
        try:
            real_widget = self._accounting_subtab_factories[tab_text]()
            tabs.removeTab(index)
            tabs.insertTab(index, real_widget, tab_text)
            tabs.setCurrentIndex(index)
            self._apply_global_ui_standards(real_widget)
            self._accounting_subtabs_loaded.add(tab_text)
        except Exception as e:
            logger.exception("Failed to load accounting sub-tab %s", tab_text)
            error_widget = QLabel(f"Error loading {tab_text}:\n{e!s}")
            error_widget.setStyleSheet("color: red; padding: 20px;")
            error_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tabs.removeTab(index)
            tabs.insertTab(index, error_widget, tab_text)
            tabs.setCurrentIndex(index)
            self._accounting_subtabs_loaded.add(tab_text)
        finally:
            tabs.blockSignals(False)
            self._accounting_subtabs_in_progress.discard(tab_text)

    def create_admin_parent_tab(self) -> QWidget:
        """Consolidated Admin: Settings and System Controls"""
        parent = QWidget()
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()

        self._admin_subtab_factories = {
            "⚙️ Admin Controls": self.create_admin_tab,
            "🔧 Settings": self.create_settings_tab,
            "🗄️ Table Browser": self.create_table_browser_tab,
        }
        self._admin_subtabs_loaded = set()
        self._admin_subtabs_in_progress = set()

        for sub_tab_name in self._admin_subtab_factories:
            placeholder = QLabel(f"Loading {sub_tab_name}...")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tabs.addTab(placeholder, sub_tab_name)

        tabs.currentChanged.connect(
            lambda idx: self._on_admin_subtab_changed(tabs, idx)
        )

        # Defer first sub-tab load to keep the parent Admin tab responsive.
        QTimer.singleShot(0, lambda: self._on_admin_subtab_changed(tabs, 0))

        layout.addWidget(tabs)
        return parent

    def _on_admin_subtab_changed(self, tabs: QTabWidget, index: int) -> None:
        """Load Admin sub-tab content on first access."""
        if index < 0:
            return

        tab_text = tabs.tabText(index)
        if tab_text not in self._admin_subtab_factories:
            return

        if (
            tab_text in self._admin_subtabs_loaded
            or tab_text in self._admin_subtabs_in_progress
        ):
            return

        self._admin_subtabs_in_progress.add(tab_text)
        tabs.blockSignals(True)
        try:
            real_widget = self._admin_subtab_factories[tab_text]()
            tabs.removeTab(index)
            tabs.insertTab(index, real_widget, tab_text)
            tabs.setCurrentIndex(index)
            self._apply_global_ui_standards(real_widget)
            self._admin_subtabs_loaded.add(tab_text)
        except Exception as e:
            logger.exception("Failed to load admin sub-tab %s", tab_text)
            error_widget = QLabel(f"Error loading {tab_text}:\n{e!s}")
            error_widget.setStyleSheet("color: red; padding: 20px;")
            error_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tabs.removeTab(index)
            tabs.insertTab(index, error_widget, tab_text)
            tabs.setCurrentIndex(index)
            self._admin_subtabs_loaded.add(tab_text)
        finally:
            tabs.blockSignals(False)
            self._admin_subtabs_in_progress.discard(tab_text)

    def create_operations_parent_tab(self) -> QWidget:
        """Consolidated Operations: Charters, Dispatch, Customers, Documents,"
        "Quotes"""

        parent = QWidget()
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        # Store reference for tab management
        self.operations_tabs = tabs

        # Dispatch is now PRIMARY (includes Dispatch Board, Booking, Quote,
        # Calendars)
        self.dispatch_tab_index = tabs.addTab(
            self.create_dispatch_tab(), "📡 Dispatch"
        )
        tabs.addTab(self.create_beverage_management_tab(), "🍷 Beverage Management")
        tabs.addTab(self.create_customers_tab(), "👥 Customers")
        tabs.addTab(self.create_documents_tab(), "📄 Documents")
        tabs.addTab(ReportManagementWidget(self.db), "📊 Reports & PDFs")

        layout.addWidget(tabs)
        return parent

    def create_charter_tab(self) -> QWidget:
        """Charter/booking management tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        self.charter_form = CharterFormWidget(self.db)
        layout.addWidget(self.charter_form)

        widget.setLayout(layout)
        return widget

    def on_unbooked_event_selected(self, event_data, dispatch_tabs) -> None:
        """Handle when unbooked calendar event is selected for booking"""
        try:
            from PyQt6.QtCore import QDate, QTime

            # Switch to "Run Charter" tab
            dispatch_tabs.setCurrentIndex(1)

            # Open new charter form with event data
            dialog = QDialog(self)
            dialog.setWindowTitle(f"New Charter - {event_data['client_name']}")
            dialog.setGeometry(100, 100, 1400, 800)

            form_layout = QVBoxLayout()
            charter_form = CharterFormWidget(
                self.db, charter_id=None, client_id=event_data["client_id"]
            )

            # Pre-fill with calendar event data
            if event_data.get("date"):
                date_obj = event_data["date"]
                if hasattr(charter_form, "charter_date"):
                    charter_form.charter_date.setDate(
                        QDate(date_obj.year, date_obj.month, date_obj.day)
                    )

            if event_data.get("time"):
                time_obj = event_data["time"]
                if hasattr(charter_form, "pickup_time"):
                    charter_form.pickup_time.setTime(
                        QTime(time_obj.hour, time_obj.minute)
                    )

            if event_data.get("driver"):
                if hasattr(charter_form, "driver_combo"):
                    for i in range(charter_form.driver_combo.count()):
                        if event_data[
                            "driver"
                        ] in charter_form.driver_combo.itemText(i):
                            charter_form.driver_combo.setCurrentIndex(i)
                            break

            if event_data.get("vehicle"):
                if hasattr(charter_form, "vehicle_combo"):
                    for i in range(charter_form.vehicle_combo.count()):
                        if event_data[
                            "vehicle"
                        ] in charter_form.vehicle_combo.itemText(i):
                            charter_form.vehicle_combo.setCurrentIndex(i)
                            break

            if event_data.get("notes"):
                if hasattr(charter_form, "dispatcher_notes_input"):
                    charter_form.dispatcher_notes_input.setPlainText(
                        event_data["notes"]
                    )

            # Parse and populate CC info from calendar event
            if event_data.get("cc_last4"):
                if hasattr(charter_form, "client_cc_checkbox"):
                    charter_form.client_cc_checkbox.setChecked(True)
                    charter_form.client_cc_last4.setText(
                        event_data["cc_last4"]
                    )

                    # If CC type is available, store in notes for reference
                    if event_data.get("cc_type"):
                        charter_form.dispatcher_notes_input.insertPlainText(
                            f"\n[CC on File: {event_data['cc_type']}"
                            f"****{event_data['cc_last4']}]"
                        )

            charter_form.saved.connect(lambda: dialog.close())
            form_layout.addWidget(charter_form)
            dialog.setLayout(form_layout)

            dialog.exec()
            # Refresh unbooked events list
            self.unbooked_calendar_widget.load_unbooked_events()

        except Exception as e:
            try:
                self.db.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.critical(
                self, "Error", f"Failed to create charter: {e}"
            )

    def create_customers_tab(self) -> QWidget:
        """Customer management tab - use enhanced client list widget"""
        from enhanced_client_widget import EnhancedClientListWidget
        return EnhancedClientListWidget(self.db)

    def create_vehicles_tab(self) -> QWidget:
        """Vehicle management tab with maintenance tracking"""
        from vehicle_management_widget import VehicleManagementWidget

        widget = QWidget()
        layout = QVBoxLayout()
        self.vehicles_widget = VehicleManagementWidget(self.db)
        layout.addWidget(self.vehicles_widget)
        widget.setLayout(layout)
        return widget

    def create_employees_tab(self) -> QWidget:
        """Employee management tab with HOS compliance"""
        from employee_management_widget import EmployeeManagementWidget

        widget = QWidget()
        layout = QVBoxLayout()
        self.employees_widget = EmployeeManagementWidget(self.db)
        layout.addWidget(self.employees_widget)
        widget.setLayout(layout)
        return widget

    def create_payroll_entry_tab(self) -> QWidget:
        """Manual payroll entry tab"""
        from payroll_entry_widget import PayrollEntryWidget

        widget = QWidget()
        layout = QVBoxLayout()
        self.payroll_entry_widget = PayrollEntryWidget(self.db)
        layout.addWidget(self.payroll_entry_widget)
        widget.setLayout(layout)
        return widget

    def create_payroll_remittances_tab(self) -> QWidget:
        """Monthly CRA/WCB remittance reconciliation tab."""
        from payroll_remittances_widget import PayrollRemittancesWidget

        widget = QWidget()
        layout = QVBoxLayout()
        self.payroll_remittances_widget = PayrollRemittancesWidget(self.db)
        layout.addWidget(self.payroll_remittances_widget)
        widget.setLayout(layout)
        return widget

    def create_vendor_invoice_tab(self) -> QWidget:
        """Vendor invoice management tab."""
        from vendor_invoice_manager import VendorInvoiceManager

        return VendorInvoiceManager(self.db)

    def create_vendor_management_tab(self) -> QWidget:
        """Vendor account browser — rename, delete, see linked receipts."""
        from vendor_management_widget import VendorManagementWidget

        return VendorManagementWidget(self.db)

    def create_checkbook_management_tab(self) -> QWidget:
        """Cheque register management for written, cleared, void, and NSF"
        "cheques."""

        from checkbook_management_widget import CheckBookManagementWidget

        return CheckBookManagementWidget(self.db.conn)

    def create_dispatch_tab(self) -> QWidget:
        """Dispatch Board and Run Charter are created eagerly.
        Calendars and other sub-tabs load on first click.
        """
        from dispatch_management_widget import DispatchManagementWidget

        widget = QWidget()
        layout = QVBoxLayout()
        dispatch_tabs = QTabWidget()
        self.dispatch_tabs_widget = dispatch_tabs

        # TAB 0: Dispatch Board (eager — main dispatcher view)
        self.dispatch_widget = DispatchManagementWidget(self.db)
        dispatch_tabs.addTab(self.dispatch_widget, "📋 Dispatch Board")

        # TAB 1: Run Charter (eager — bookings created here constantly)
        self.booking_widget = self.create_charter_tab()
        dispatch_tabs.addTab(self.booking_widget, "📝 Run Charter")

        # Auto-refresh dispatch list on charter save
        self.charter_form.saved.connect(
            lambda _cid: self.dispatch_widget._trigger_load()
        )

        # TABs 2-7: lazy placeholders
        self._dispatch_subtab_factories = {
            "📅 Calendar (Outlook Style)": self._create_outlook_calendar_subtab,
            "🗓️ Calendar (Table View)": self._create_dispatcher_calendar_subtab,
            "👤 Driver Calendar": self._create_driver_calendar_subtab,
            "🚐 Vehicle Booked Out": self._create_vehicle_booked_out_subtab,
            "🛒 Beverage Orders": self._create_beverage_dispatch_subtab,
            "📅 Unbooked Events": self._create_unbooked_calendar_subtab,
        }
        self._dispatch_subtabs_loaded: set = set()
        self._dispatch_subtabs_in_progress: set = set()

        for tab_name in self._dispatch_subtab_factories:
            placeholder = QLabel(f"Loading {tab_name}…")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dispatch_tabs.addTab(placeholder, tab_name)

        dispatch_tabs.currentChanged.connect(
            lambda idx: self._on_dispatch_subtab_changed(dispatch_tabs, idx)
        )
        dispatch_tabs.setCurrentIndex(0)

        layout.addWidget(dispatch_tabs)
        widget.setLayout(layout)
        return widget

    def _on_dispatch_subtab_changed(
        self, tabs: QTabWidget, index: int
    ) -> None:
        """Load Dispatch sub-tab on first click (index >= 2)."""
        if index < 2:
            return
        tab_text = tabs.tabText(index)
        if tab_text not in self._dispatch_subtab_factories:
            return
        if (
            tab_text in self._dispatch_subtabs_loaded
            or tab_text in self._dispatch_subtabs_in_progress
        ):
            return
        self._dispatch_subtabs_in_progress.add(tab_text)
        tabs.blockSignals(True)
        try:
            real_widget = self._dispatch_subtab_factories[tab_text]()
            tabs.removeTab(index)
            tabs.insertTab(index, real_widget, tab_text)
            tabs.setCurrentIndex(index)
            self._apply_global_ui_standards(real_widget)
            self._dispatch_subtabs_loaded.add(tab_text)
        except Exception as e:
            logger.exception("Failed to load dispatch sub-tab %s", tab_text)
            err = QLabel(f"Error loading {tab_text}:\n{e!s}")
            err.setStyleSheet("color: red; padding: 20px;")
            err.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tabs.removeTab(index)
            tabs.insertTab(index, err, tab_text)
            tabs.setCurrentIndex(index)
            self._dispatch_subtabs_loaded.add(tab_text)
        finally:
            tabs.blockSignals(False)
            self._dispatch_subtabs_in_progress.discard(tab_text)

    def _create_outlook_calendar_subtab(self) -> QWidget:
        from outlook_style_calendar_widget import OutlookStyleCalendarWidget
        self.outlook_calendar_widget = OutlookStyleCalendarWidget(self.db)
        return self.outlook_calendar_widget

    def _create_dispatcher_calendar_subtab(self) -> QWidget:
        from dispatcher_calendar_widget import DispatcherCalendarWidget
        self.dispatcher_calendar_widget = DispatcherCalendarWidget(self.db)
        return self.dispatcher_calendar_widget

    def _create_driver_calendar_subtab(self) -> QWidget:
        from driver_calendar_widget import DriverCalendarWidget
        self.driver_calendar_widget = DriverCalendarWidget(self.db)
        return self.driver_calendar_widget

    def _create_vehicle_booked_out_subtab(self) -> QWidget:
        from vehicle_booked_out_widget import VehicleBookedOutWidget
        self.vehicle_booked_out_widget = VehicleBookedOutWidget(self.db)
        return self.vehicle_booked_out_widget

    def _create_beverage_dispatch_subtab(self) -> QWidget:
        try:
            from beverage_dispatch_widget import BeverageDispatchWidget
            self.beverage_dispatch_widget = BeverageDispatchWidget(self.db)
            return self.beverage_dispatch_widget
        except Exception as _bev_err:
            lbl = QLabel(f"Beverage orders unavailable:\n{_bev_err}")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            return lbl

    def _create_unbooked_calendar_subtab(self) -> QWidget:
        from unbooked_calendar_report_widget import UnbookedCalendarReportWidget
        self.unbooked_calendar_widget = UnbookedCalendarReportWidget(self.db)
        self.unbooked_calendar_widget.booking_created.connect(
            lambda event: self.on_unbooked_event_selected(
                event, self.dispatch_tabs_widget
            )
        )
        return self.unbooked_calendar_widget

    def create_documents_tab(self) -> QWidget:
        """Document management and upload"""
        from document_management_widget import DocumentManagementWidget
        widget = QWidget()
        layout = QVBoxLayout()
        self.documents_widget = DocumentManagementWidget(self.db)
        layout.addWidget(self.documents_widget)
        widget.setLayout(layout)
        return widget

    def create_beverage_accounting_tab(self) -> QWidget:
        """Beverage cost vs revenue vs profit accounting report."""
        from beverage_accounting_widget import BeverageAccountingWidget
        return BeverageAccountingWidget(self.db)

    def create_admin_tab(self) -> QWidget:
        """Admin and system management"""
        from admin_management_widget import AdminManagementWidget

        widget = QWidget()
        layout = QVBoxLayout()
        self.admin_widget = AdminManagementWidget(self.db, auth_user=getattr(self, 'auth_user', None))
        layout.addWidget(self.admin_widget)
        widget.setLayout(layout)
        return widget

    def create_beverage_management_tab(self) -> QWidget:
        """Beverage management tab."""
        from beverage_management_widget import BeverageManagementWidget

        return BeverageManagementWidget(self.db)

    def create_enhanced_charter_tab(self) -> QWidget:
        """Enhanced charter list with drill-down capability"""
        from enhanced_charter_widget import EnhancedCharterListWidget
        widget = QWidget()
        layout = QVBoxLayout()
        self.enhanced_charter_widget = EnhancedCharterListWidget(self.db)
        layout.addWidget(self.enhanced_charter_widget)
        widget.setLayout(layout)
        return widget

    def create_enhanced_employee_tab(self) -> QWidget:
        """Enhanced employee list with comprehensive drill-down"""
        from enhanced_employee_widget import EnhancedEmployeeListWidget
        widget = QWidget()
        layout = QVBoxLayout()
        self.enhanced_employee_widget = EnhancedEmployeeListWidget(self.db)
        layout.addWidget(self.enhanced_employee_widget)
        widget.setLayout(layout)
        return widget

    def create_enhanced_vehicle_tab(self) -> QWidget:
        """Enhanced vehicle list with maintenance and cost tracking"""
        from enhanced_vehicle_widget import EnhancedVehicleListWidget
        widget = QWidget()
        layout = QVBoxLayout()
        self.enhanced_vehicle_widget = EnhancedVehicleListWidget(self.db)
        layout.addWidget(self.enhanced_vehicle_widget)
        widget.setLayout(layout)
        return widget

    def create_tax_management_tab(self) -> QWidget:
        """CRA Tax Management - Multi-year tax filing, payroll, GST, owner"
        "income tracking"""

        from tax_management_widget import TaxManagementWidget

        widget = QWidget()
        layout = QVBoxLayout()
        self.tax_management_widget = TaxManagementWidget(self.db)
        layout.addWidget(self.tax_management_widget)
        widget.setLayout(layout)
        return widget

    def create_t2_data_entry_tab(self) -> QWidget:
        """T2 Corporation Tax Return Data Entry - Historical data from paper"
        "forms"""

        from t2_data_entry_widget import T2DataEntryWidget

        widget = QWidget()
        layout = QVBoxLayout()
        self.t2_data_entry_widget = T2DataEntryWidget(self.db)
        layout.addWidget(self.t2_data_entry_widget)
        widget.setLayout(layout)
        return widget

    def create_wcb_rates_tab(self) -> QWidget:
        """WCB rates tab."""
        from wcb_rate_widget import WCBRateEntryWidget

        return WCBRateEntryWidget(self.db)

    def create_business_entity_tab(self) -> QWidget:
        """Business entity management - overall company view"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Add button to open business entity dialog
        header = QLabel("<h2>🏢 Business Entity Management</h2>")
        layout.addWidget(header)

        info_label = QLabel("""
        <p>Manage Arrow Limousine as a business entity:</p>
        <ul>
        <li>Company registration and legal documents</li>
        <li>Financial overview (P&L, balance sheet)</li>
        <li>Tax filings and compliance</li>
        <li>Business licenses and insurance policies</li>
        <li>Bank accounts and credit facilities</li>
        <li>Loans, assets, and vendor relationships</li>
        <li>Strategic planning and goals</li>
        </ul>
        """)
        layout.addWidget(info_label)

        open_btn = QPushButton("🏢 Open Business Management Dashboard")
        open_btn.setMinimumHeight(50)
        open_btn.setStyleSheet("font-size: 14px; font-weight: bold;")
        open_btn.clicked.connect(self.open_business_entity_dialog)
        layout.addWidget(open_btn)

        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def open_business_entity_dialog(self) -> None:
        """Open the business entity management dialog"""
        from business_entity_drill_down import BusinessEntityDialog

        dialog = BusinessEntityDialog(self.db, self)
        dialog.exec()

    def create_accounting_tab(self) -> QWidget:
        from accounting_receipts_widget import AccountingReceiptsWidget

        widget = QWidget()
        layout = QVBoxLayout()
        self.accounting_widget = AccountingReceiptsWidget(self.db)
        layout.addWidget(self.accounting_widget)
        widget.setLayout(layout)
        return widget

    def create_accounting_tab_with_parent(self, parent_tabs) -> QWidget:
        """Create accounting tab with parent tabs reference for navigation"""
        from accounting_receipts_widget import AccountingReceiptsWidget

        widget = QWidget()
        layout = QVBoxLayout()
        self.accounting_widget = AccountingReceiptsWidget(
            self.db, parent_tab_widget=parent_tabs
        )
        layout.addWidget(self.accounting_widget)
        widget.setLayout(layout)
        return widget

    def create_accountant_notes_tab(self) -> QWidget:
        """Year-by-year accountant working notes."""
        from accountant_notes_widget import AccountantNotesWidget

        return AccountantNotesWidget(self.db.conn)

    def create_accounting_control_center_tab(self) -> QWidget:
        """Single-screen accounting operating hub."""
        from accounting_control_center_widget import (
            AccountingControlCenterWidget,
        )

        return AccountingControlCenterWidget(self.db)

    def create_year_end_audit_tab(self) -> QWidget:
        """Year-end hub: Guided Wizard + legacy Audit Checks."""
        try:
            from PyQt6.QtWidgets import QTabWidget
            tabs = QTabWidget()

            # Step-by-step guided workflow (H&R Block style)
            auth = getattr(self, "auth_user", {"username": "system", "role": "admin"})
            wizard = YearEndWizardWidget(self.db, auth_user=auth)
            tabs.addTab(wizard, "🧭 Year-End Guided Wizard")

            # Legacy deep-audit checks
            legacy = YearEndManagementWidget(self.db)
            tabs.addTab(legacy, "🔎 Audit Checks (Advanced)")

            return tabs
        except Exception as e:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            error_label = QLabel(
                f"❌ Error loading Year-End tab:\n{e!s}"
            )
            error_label.setStyleSheet("color: red; padding: 20px;")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)
            logger.warning(f"Error creating Year-End tab: {e}")
            return widget

    def create_enhanced_banking_tab(self) -> QWidget:
        """Create Enhanced Banking Manager tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        try:
            banking_manager = EnhancedBankingManager(self.db, widget)
            self.enhanced_banking_manager = banking_manager
            layout.addWidget(banking_manager)
        except Exception as e:
            error_label = QLabel(
                f"❌ Error loading Enhanced Banking Manager:\n{e!s}"
            )
            error_label.setStyleSheet("color: red; padding: 20px;")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)
            logger.warning(f"Error creating Enhanced Banking Manager tab: {e}")

        widget.setLayout(layout)
        return widget

    def create_nsf_pair_manager_tab(self) -> QWidget:
        """Create NSF Pair Manager tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        try:
            nsf_manager = NsfPairManagerWidget(self.db, widget)
            layout.addWidget(nsf_manager)
        except Exception as e:
            error_label = QLabel(f"Error loading NSF Pair Manager:\n{e!s}")
            error_label.setStyleSheet("color: red; padding: 20px;")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)
            logger.warning(f"Error creating NSF Pair Manager tab: {e}")

        widget.setLayout(layout)
        return widget

    def navigate_to_top_tab(self, top_tab_name: str) -> bool:
        """Programmatically focus a top-level tab by text."""
        if not hasattr(self, "tabs"):
            return False
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == top_tab_name:
                self.tabs.setCurrentIndex(i)
                return True
        return False

    def navigate_to_accounting_subtab(self, sub_tab_name: str) -> bool:
        """Focus Accounting top tab, then a specific Accounting sub-tab."""
        if not self.navigate_to_top_tab("💰 Accounting & Finance"):
            return False
        if not hasattr(self, "accounting_parent_tabs"):
            return False
        for i in range(self.accounting_parent_tabs.count()):
            if self.accounting_parent_tabs.tabText(i) == sub_tab_name:
                self.accounting_parent_tabs.setCurrentIndex(i)
                return True
        return False

    def navigate_to_operations_subtab(self, sub_tab_name: str) -> bool:
        """Focus Operations top tab, then a specific Operations sub-tab."""
        if not self.navigate_to_top_tab("🚀 Operations"):
            return False
        if not hasattr(self, "operations_tabs"):
            return False
        for i in range(self.operations_tabs.count()):
            if self.operations_tabs.tabText(i) == sub_tab_name:
                self.operations_tabs.setCurrentIndex(i)
                return True
        return False

    def create_enhanced_receipts_tab(self) -> QWidget:
        """Create Enhanced Receipts Manager tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        try:
            receipts_manager = EnhancedReceiptsManager(self.db, widget)
            layout.addWidget(receipts_manager)
        except Exception as e:
            error_label = QLabel(
                f"❌ Error loading Enhanced Receipts Manager:\n{e!s}"
            )
            error_label.setStyleSheet("color: red; padding: 20px;")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)
            logger.warning(f"Error creating Enhanced Receipts Manager tab: {e}")

        widget.setLayout(layout)
        return widget

    def create_reports_tab(self) -> QWidget:
        """Reports & analytics tab with Phase 1, 2, 3 dashboards"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Create sub-tabs for different reports (11 total dashboards)
        report_tabs = QTabWidget()

        # Accountant-focused drill-down entry point
        from reports_widget import DrillDownReportWidget

        self.drilldown_widget = DrillDownReportWidget(self.db)
        report_tabs.addTab(self.drilldown_widget, "🔎 Drill-Down Reports")

        # ===== PHASE 1: CORE DASHBOARDS (4) =====
        # Fleet Management
        self.fleet_widget = FleetManagementWidget(self.db)
        report_tabs.addTab(self.fleet_widget, "🚐 Fleet Management")

        # Driver Performance
        self.driver_widget = DriverPerformanceWidget(self.db)
        report_tabs.addTab(self.driver_widget, "👤 Driver Performance")

        # Financial Dashboard
        self.financial_widget = FinancialDashboardWidget(self.db)
        report_tabs.addTab(self.financial_widget, "📈 Financial Reports")

        # Payment Reconciliation
        self.payment_widget = PaymentReconciliationWidget(self.db)
        report_tabs.addTab(self.payment_widget, "💳 Payment Reconciliation")

        # ===== PHASE 2: ADVANCED ANALYTICS (4) =====
        # Advanced Vehicle Analytics
        self.vehicle_analytics_widget = VehicleAnalyticsWidget(self.db)
        report_tabs.addTab(
            self.vehicle_analytics_widget, "🚗 Vehicle Analytics"
        )

        # Employee Payroll Audit
        self.payroll_audit_widget = EmployeePayrollAuditWidget(self.db)
        report_tabs.addTab(self.payroll_audit_widget, "👔 Payroll Audit")

        # QuickBooks Reconciliation
        self.qb_recon_widget = QuickBooksReconciliationWidget(self.db)
        report_tabs.addTab(self.qb_recon_widget, "📊 QB Reconciliation")

        # Charter Analytics
        self.charter_analytics_widget = CharterAnalyticsWidget(self.db)
        report_tabs.addTab(
            self.charter_analytics_widget, "📈 Charter Analytics"
        )

        # ===== PHASE 3: COMPLIANCE & BUDGET (3) =====
        # Compliance Tracking
        self.compliance_widget = ComplianceTrackingWidget(self.db)
        report_tabs.addTab(self.compliance_widget, "✅ Compliance")

        # Budget vs Actual
        self.budget_widget = BudgetAnalysisWidget(self.db)
        report_tabs.addTab(self.budget_widget, "💰 Budget vs Actual")

        # Insurance Tracking
        self.insurance_widget = InsuranceTrackingWidget(self.db)
        report_tabs.addTab(self.insurance_widget, "🛡️ Insurance")

        # ===== PHASE 4: FLEET MANAGEMENT (5) =====
        # Vehicle Fleet Cost Analysis
        self.fleet_cost_widget = VehicleFleetCostAnalysisWidget(self.db)
        report_tabs.addTab(self.fleet_cost_widget, "🚗 Fleet Cost Analysis")

        # Vehicle Maintenance Tracking
        self.maintenance_widget = VehicleMaintenanceTrackingWidget(self.db)
        report_tabs.addTab(self.maintenance_widget, "🔧 Maintenance Tracking")

        # Fuel Efficiency Tracking
        self.fuel_efficiency_widget = FuelEfficiencyTrackingWidget(self.db)
        report_tabs.addTab(self.fuel_efficiency_widget, "⛽ Fuel Efficiency")

        # Vehicle Utilization
        self.utilization_widget = VehicleUtilizationWidget(self.db)
        report_tabs.addTab(self.utilization_widget, "📊 Vehicle Utilization")

        # Fleet Age Analysis
        self.fleet_age_widget = FleetAgeAnalysisWidget(self.db)
        report_tabs.addTab(self.fleet_age_widget, "📈 Fleet Age Analysis")

        # ===== PHASE 5: EMPLOYEE/PAYROLL (5) =====
        # Driver Pay Analysis
        self.driver_pay_widget = DriverPayAnalysisWidget(self.db)
        report_tabs.addTab(self.driver_pay_widget, "💰 Driver Pay Analysis")

        # Employee Performance Metrics
        self.perf_metrics_widget = EmployeePerformanceMetricsWidget(self.db)
        report_tabs.addTab(self.perf_metrics_widget, "⭐ Performance Metrics")

        # Payroll Tax Compliance
        self.tax_compliance_widget = PayrollTaxComplianceWidget(self.db)
        report_tabs.addTab(self.tax_compliance_widget, "📋 Tax Compliance")

        # Driver Schedule Management
        self.schedule_widget = DriverScheduleManagementWidget(self.db)
        report_tabs.addTab(self.schedule_widget, "📅 Driver Schedule")

        # ===== PHASE 6: PAYMENTS & FINANCIAL (5) =====
        # Payment Reconciliation (Advanced)
        self.payment_adv_widget = PaymentReconciliationAdvancedWidget(self.db)
        report_tabs.addTab(self.payment_adv_widget, "💳 Payments (Advanced)")

        # AR Aging Dashboard
        self.ar_aging_widget = ARAgingDashboardWidget(self.db)
        report_tabs.addTab(self.ar_aging_widget, "📊 AR Aging")

        # Cash Flow Report
        self.cashflow_widget = CashFlowReportWidget(self.db)
        report_tabs.addTab(self.cashflow_widget, "💸 Cash Flow")

        # Profit & Loss Report
        self.pl_widget = ProfitLossReportWidget(self.db)
        report_tabs.addTab(self.pl_widget, "📊 Profit & Loss")

        # Charter Analytics (Advanced)
        self.charter_adv_widget = CharterAnalyticsAdvancedWidget(self.db)
        report_tabs.addTab(self.charter_adv_widget, "📈 Charter Analytics+")

        # ===== PHASE 7: CHARTER & CUSTOMER ANALYTICS (8) =====
        # Charter Management
        self.charter_mgmt_widget = CharterManagementDashboardWidget(self.db)
        report_tabs.addTab(self.charter_mgmt_widget, "📅 Charter Management")

        # Customer Lifetime Value
        self.clv_widget = CustomerLifetimeValueWidget(self.db)
        report_tabs.addTab(self.clv_widget, "💰 Customer LTV")

        # Charter Cancellation Analysis
        self.cancel_widget = CharterCancellationAnalysisWidget(self.db)
        report_tabs.addTab(self.cancel_widget, "📊 Cancellation Analysis")

        # Booking Lead Time
        self.leadtime_widget = BookingLeadTimeAnalysisWidget(self.db)
        report_tabs.addTab(self.leadtime_widget, "⏱️ Lead Time")

        # Customer Segmentation
        self.segment_widget = CustomerSegmentationWidget(self.db)
        report_tabs.addTab(self.segment_widget, "🎯 Segmentation")

        # Route Profitability
        self.route_widget = RouteProfitabilityWidget(self.db)
        report_tabs.addTab(self.route_widget, "🛣️ Route Profitability")

        # Geographic Distribution
        self.geo_widget = GeographicRevenueDistributionWidget(self.db)
        report_tabs.addTab(self.geo_widget, "🗺️ Geographic Revenue")

        # ===== PHASE 8: COMPLIANCE, MAINTENANCE, MONITORING (8) =====
        # HOS Compliance
        self.hos_widget = HosComplianceTrackingWidget(self.db)
        report_tabs.addTab(self.hos_widget, "⚖️ HOS Compliance")

        # Advanced Maintenance
        self.maint_adv_widget = AdvancedMaintenanceScheduleWidget(self.db)
        report_tabs.addTab(self.maint_adv_widget, "🔧 Maintenance (Advanced)")

        # Safety Incidents
        self.safety_widget = SafetyIncidentTrackingWidget(self.db)
        report_tabs.addTab(self.safety_widget, "⚠️ Safety Incidents")

        # Vendor Performance
        self.vendor_widget = VendorPerformanceWidget(self.db)
        report_tabs.addTab(self.vendor_widget, "🤝 Vendor Performance")

        # Real-Time Monitoring
        self.monitor_widget = RealTimeFleetMonitoringWidget(self.db)
        report_tabs.addTab(self.monitor_widget, "📡 Fleet Monitoring")

        # System Health
        self.health_widget = SystemHealthDashboardWidget(self.db)
        report_tabs.addTab(self.health_widget, "🏥 System Health")

        # Data Quality Audit
        self.quality_widget = DataQualityAuditWidget(self.db)
        report_tabs.addTab(self.quality_widget, "📋 Data Quality")

        # ===== PHASE 9: PREDICTIVE & ADVANCED ANALYTICS (15) =====
        # Demand Forecasting
        self.demand_widget = DemandForecastingWidget(self.db)
        report_tabs.addTab(self.demand_widget, "📈 Demand Forecasting")

        # Churn Prediction
        self.churn_widget = ChurnPredictionWidget(self.db)
        report_tabs.addTab(self.churn_widget, "⚠️ Churn Prediction")

        # Revenue Optimization
        self.revenue_opt_widget = RevenueOptimizationWidget(self.db)
        report_tabs.addTab(self.revenue_opt_widget, "💰 Revenue Optimization")

        # Customer Worth (RFM)
        self.customer_worth_widget = CustomerWorthWidget(self.db)
        report_tabs.addTab(
            self.customer_worth_widget, "⭐ Customer Worth (RFM)"
        )

        # Next Best Action
        self.nba_widget = NextBestActionWidget(self.db)
        report_tabs.addTab(self.nba_widget, "🎯 Next Best Action")

        # Seasonality Analysis
        self.seasonality_widget = SeasonalityAnalysisWidget(self.db)
        report_tabs.addTab(self.seasonality_widget, "📊 Seasonality")

        # Cost Behavior Analysis
        self.cost_behavior_widget = CostBehaviorAnalysisWidget(self.db)
        report_tabs.addTab(self.cost_behavior_widget, "💡 Cost Behavior")

        # Break-Even Analysis
        self.breakeven_widget = BreakEvenAnalysisWidget(self.db)
        report_tabs.addTab(self.breakeven_widget, "📊 Break-Even")

        # Email Campaign Performance
        self.email_widget = EmailCampaignPerformanceWidget(self.db)
        report_tabs.addTab(self.email_widget, "📧 Email Campaigns")

        # Customer Journey
        self.journey_widget = CustomerJourneyAnalysisWidget(self.db)
        report_tabs.addTab(self.journey_widget, "🛣️ Customer Journey")

        # Competitive Intelligence
        self.competitive_widget = CompetitiveIntelligenceWidget(self.db)
        report_tabs.addTab(self.competitive_widget, "🎯 Competitive Intel")

        # Regulatory Compliance
        self.regulatory_widget = RegulatoryComplianceTrackingWidget(self.db)
        report_tabs.addTab(self.regulatory_widget, "⚖️ Regulatory Compliance")

        # CRA Compliance Report
        self.cra_widget = CRAComplianceReportWidget(self.db)
        report_tabs.addTab(self.cra_widget, "📋 CRA Compliance")

        # Employee Productivity
        self.productivity_widget = EmployeeProductivityTrackingWidget(self.db)
        report_tabs.addTab(
            self.productivity_widget, "👥 Employee Productivity"
        )

        # Promotional Effectiveness
        self.promo_widget = PromotionalEffectivenessWidget(self.db)
        report_tabs.addTab(self.promo_widget, "🎁 Promotional Effectiveness")

        # ===== PHASE 10: REAL-TIME & ADVANCED CHARTS (13) =====
        # Real-Time Fleet Tracking
        self.realtime_tracking_widget = RealTimeFleetTrackingMapWidget(self.db)
        report_tabs.addTab(
            self.realtime_tracking_widget, "🗺️ Fleet Tracking Map"
        )

        # Live Dispatch Monitor
        self.dispatch_widget = LiveDispatchMonitorWidget(self.db)
        report_tabs.addTab(self.dispatch_widget, "📡 Live Dispatch")

        # Mobile Customer Portal
        self.mobile_customer_widget = MobileCustomerPortalWidget(self.db)
        report_tabs.addTab(self.mobile_customer_widget, "📱 Mobile Portal")

        # Mobile Driver Dashboard
        self.mobile_driver_widget = MobileDriverDashboardWidget(self.db)
        report_tabs.addTab(self.mobile_driver_widget, "🚗 Mobile Driver")

        # API Endpoint Performance
        self.api_perf_widget = APIEndpointPerformanceWidget(self.db)
        report_tabs.addTab(self.api_perf_widget, "⚙️ API Performance")

        # Third Party Integrations
        self.integration_widget = ThirdPartyIntegrationMonitorWidget(self.db)
        report_tabs.addTab(self.integration_widget, "🔗 Integrations")

        # Advanced Time Series
        self.timeseries_widget = AdvancedTimeSeriesChartWidget(self.db)
        report_tabs.addTab(self.timeseries_widget, "📊 Time Series")

        # Interactive Heatmap
        self.heatmap_widget = InteractiveHeatmapWidget(self.db)
        report_tabs.addTab(self.heatmap_widget, "🔥 Heatmap")

        # Comparative Analysis
        self.comparative_widget = ComparativeAnalysisChartWidget(self.db)
        report_tabs.addTab(self.comparative_widget, "🔄 Comparative Analysis")

        # Distribution Analysis
        self.distribution_widget = DistributionAnalysisChartWidget(self.db)
        report_tabs.addTab(self.distribution_widget, "📈 Distribution")

        # Correlation Matrix
        self.correlation_widget = CorrelationMatrixWidget(self.db)
        report_tabs.addTab(self.correlation_widget, "🔗 Correlation Matrix")

        # Automation Workflows
        self.automation_widget = AutomationWorkflowsWidget(self.db)
        report_tabs.addTab(self.automation_widget, "⚡ Automation")

        # Alert Management
        self.alerts_widget = AlertManagementWidget(self.db)
        report_tabs.addTab(self.alerts_widget, "🔔 Alerts")

        # ===== PHASE 11: ADVANCED SCHEDULING & OPTIMIZATION (12) =====
        # Driver Shift Optimization
        self.shift_opt_widget = DriverShiftOptimizationWidget(self.db)
        report_tabs.addTab(self.shift_opt_widget, "📅 Shift Optimization")

        # Route Scheduling
        self.route_sched_widget = RouteSchedulingWidget(self.db)
        report_tabs.addTab(self.route_sched_widget, "🛣️ Route Scheduling")

        # Vehicle Assignment Planner
        self.vehicle_assign_widget = VehicleAssignmentPlannerWidget(self.db)
        report_tabs.addTab(self.vehicle_assign_widget, "🚗 Vehicle Assignment")

        # Calendar Forecasting
        self.calendar_forecast_widget = CalendarForecasitngWidget(self.db)
        report_tabs.addTab(
            self.calendar_forecast_widget, "📆 Calendar Forecast"
        )

        # Break Compliance Schedule
        self.break_compliance_widget = BreakComplianceScheduleWidget(self.db)
        report_tabs.addTab(self.break_compliance_widget, "⏰ Break Compliance")

        # Maintenance Scheduling
        self.maint_sched_widget = MaintenanceSchedulingWidget(self.db)
        report_tabs.addTab(self.maint_sched_widget, "🔧 Maintenance Sched")

        # Crew Rotation Analysis
        self.crew_rotation_widget = CrewRotationAnalysisWidget(self.db)
        report_tabs.addTab(self.crew_rotation_widget, "👥 Crew Rotation")

        # Load Balancing
        self.load_balance_widget = LoadBalancingOptimizerWidget(self.db)
        report_tabs.addTab(self.load_balance_widget, "⚖️ Load Balancing")

        # Dynamic Pricing Schedule
        self.dyn_pricing_widget = DynamicPricingScheduleWidget(self.db)
        report_tabs.addTab(self.dyn_pricing_widget, "💰 Dynamic Pricing")

        # Historical Patterns
        self.hist_patterns_widget = HistoricalSchedulingPatternsWidget(self.db)
        report_tabs.addTab(self.hist_patterns_widget, "📊 Historical Patterns")

        # Predictive Scheduling
        self.pred_sched_widget = PredictiveSchedulingWidget(self.db)
        report_tabs.addTab(self.pred_sched_widget, "🤖 Predictive Schedule")

        # Capacity Utilization
        self.capacity_widget = CapacityUtilizationWidget(self.db)
        report_tabs.addTab(self.capacity_widget, "📦 Capacity Planning")

        # ===== PHASE 12: MULTI-PROPERTY MANAGEMENT (15) =====
        # Branch Consolidation
        self.branch_consol_widget = BranchLocationConsolidationWidget(self.db)
        report_tabs.addTab(
            self.branch_consol_widget, "🏢 Branch Consolidation"
        )

        # Inter-Branch Comparison
        self.inter_branch_widget = InterBranchPerformanceComparisonWidget(
            self.db
        )
        report_tabs.addTab(
            self.inter_branch_widget, "📊 Inter-Branch Comparison"
        )

        # Consolidated P&L
        self.consol_pl_widget = ConsolidatedProfitLossWidget(self.db)
        report_tabs.addTab(self.consol_pl_widget, "💰 Consolidated P&L")

        # Resource Allocation
        self.resource_alloc_widget = ResourceAllocationAcrossPropertiesWidget(
            self.db
        )
        report_tabs.addTab(
            self.resource_alloc_widget, "🔄 Resource Allocation"
        )

        # Cross-Branch Chartering
        self.cross_branch_widget = CrossBranchCharteringWidget(self.db)
        report_tabs.addTab(self.cross_branch_widget, "🚐 Cross-Branch")

        # Shared Vehicle Tracking
        self.shared_vehicle_widget = SharedVehicleTrackingWidget(self.db)
        report_tabs.addTab(self.shared_vehicle_widget, "🚗 Shared Vehicles")

        # Unified Inventory
        self.inventory_widget = UnifiedInventoryManagementWidget(self.db)
        report_tabs.addTab(self.inventory_widget, "📦 Unified Inventory")

        # Multi-Location Payroll
        self.multi_payroll_widget = MultiLocationPayrollWidget(self.db)
        report_tabs.addTab(
            self.multi_payroll_widget, "💳 Multi-Location Payroll"
        )

        # Territory Mapping
        self.territory_widget = TerritoryMappingWidget(self.db)
        report_tabs.addTab(self.territory_widget, "🗺️ Territory Mapping")

        # Market Overlap
        self.overlap_widget = MarketOverlapAnalysisWidget(self.db)
        report_tabs.addTab(self.overlap_widget, "📊 Market Overlap")

        # Regional Performance
        self.regional_widget = RegionalPerformanceMetricsWidget(self.db)
        report_tabs.addTab(self.regional_widget, "📈 Regional Performance")

        # Property-Level KPIs
        self.property_kpi_widget = PropertyLevelKPIWidget(self.db)
        report_tabs.addTab(self.property_kpi_widget, "📊 Property KPIs")

        # Franchise Integration
        self.franchise_widget = FranchiseIntegrationWidget(self.db)
        report_tabs.addTab(self.franchise_widget, "🏢 Franchise Integration")

        # License Tracking
        self.license_widget = LicenseTrackingWidget(self.db)
        report_tabs.addTab(self.license_widget, "📜 License Tracking")

        # Operations Consolidation
        self.ops_consol_widget = OperationsConsolidationWidget(self.db)
        report_tabs.addTab(
            self.ops_consol_widget, "⚙️ Operations Consolidation"
        )

        # Phase 13 tabs (18 widgets - Customer Portal Enhancements)

        # Self-Service Booking Portal
        self.booking_portal_widget = SelfServiceBookingPortalWidget(self.db)
        report_tabs.addTab(
            self.booking_portal_widget, "📱 Self-Service Booking"
        )

        # Trip History
        self.trip_history_widget = TripHistoryWidget(self.db)
        report_tabs.addTab(self.trip_history_widget, "📜 Trip History")

        # Invoice & Receipt Management
        self.invoice_widget = InvoiceReceiptManagementWidget(self.db)
        report_tabs.addTab(self.invoice_widget, "📄 Invoice Management")

        # Account Settings
        self.account_settings_widget = AccountSettingsWidget(self.db)
        report_tabs.addTab(self.account_settings_widget, "⚙️ Account Settings")

        # Loyalty Program Tracking
        self.loyalty_widget = LoyaltyProgramTrackingWidget(self.db)
        report_tabs.addTab(self.loyalty_widget, "🎁 Loyalty Program")

        # Referral Analytics
        self.referral_widget = ReferralAnalyticsWidget(self.db)
        report_tabs.addTab(self.referral_widget, "👥 Referral Analytics")

        # Subscription Management
        self.subscription_widget = SubscriptionManagementWidget(self.db)
        report_tabs.addTab(
            self.subscription_widget, "🔄 Subscription Management"
        )

        # Corporate Account Management
        self.corporate_widget = CorporateAccountManagementWidget(self.db)
        report_tabs.addTab(self.corporate_widget, "🏢 Corporate Accounts")

        # Recurring Booking Management
        self.recurring_widget = RecurringBookingManagementWidget(self.db)
        report_tabs.addTab(self.recurring_widget, "📅 Recurring Bookings")

        # Chat Integration
        self.chat_widget = ChatIntegrationWidget(self.db)
        report_tabs.addTab(self.chat_widget, "💬 Customer Chat")

        # Support Ticket Management
        self.support_widget = SupportTicketManagementWidget(self.db)
        report_tabs.addTab(self.support_widget, "🎫 Support Tickets")

        # Rating & Review Management
        self.rating_widget = RatingReviewManagementWidget(self.db)
        report_tabs.addTab(self.rating_widget, "⭐ Ratings & Reviews")

        # Saved Preferences
        self.preferences_widget = SavedPreferencesWidget(self.db)
        report_tabs.addTab(self.preferences_widget, "❤️ Saved Preferences")

        # Fleet Preferences
        self.fleet_pref_widget = FleetPreferencesWidget(self.db)
        report_tabs.addTab(self.fleet_pref_widget, "🚗 Fleet Preferences")

        # Driver Feedback
        self.driver_feedback_widget = DriverFeedbackWidget(self.db)
        report_tabs.addTab(self.driver_feedback_widget, "👤 Driver Feedback")

        # Customer Communications
        self.comms_widget = CustomerCommunicationsWidget(self.db)
        report_tabs.addTab(self.comms_widget, "📧 Communications")

        # Phase 14 tabs (15 widgets - Advanced Reporting)

        # Custom Report Builder
        self.custom_report_widget = CustomReportBuilderWidget(self.db)
        report_tabs.addTab(self.custom_report_widget, "🛠️ Custom Reports")

        # Executive Dashboard
        self.executive_widget = ExecutiveDashboardWidget(self.db)
        report_tabs.addTab(self.executive_widget, "👔 Executive Dashboard")

        # Budget vs Actual
        self.budget_widget = BudgetVsActualWidget(self.db)
        report_tabs.addTab(self.budget_widget, "💵 Budget vs Actual")

        # Trend Analysis
        self.trend_widget = TrendAnalysisWidget(self.db)
        report_tabs.addTab(self.trend_widget, "📊 Trend Analysis")

        # Anomaly Detection
        self.anomaly_widget = AnomalyDetectionWidget(self.db)
        report_tabs.addTab(self.anomaly_widget, "🚨 Anomaly Detection")

        # Segmentation Analysis
        self.segment_widget = SegmentationAnalysisWidget(self.db)
        report_tabs.addTab(self.segment_widget, "📍 Segmentation Analysis")

        # Competitive Analysis
        self.competitive_widget = CompetitiveAnalysisWidget(self.db)
        report_tabs.addTab(self.competitive_widget, "⚔️ Competitive Analysis")

        # Operational Metrics
        self.operational_widget = OperationalMetricsWidget(self.db)
        report_tabs.addTab(self.operational_widget, "📈 Operational Metrics")

        # Data Quality Report
        self.quality_widget = DataQualityReportWidget(self.db)
        report_tabs.addTab(self.quality_widget, "✅ Data Quality")

        # ROI Analysis
        self.roi_widget = ROIAnalysisWidget(self.db)
        report_tabs.addTab(self.roi_widget, "💰 ROI Analysis")

        # Forecasting
        self.forecast_widget = ForecastingWidget(self.db)
        report_tabs.addTab(self.forecast_widget, "🔮 Forecasting")

        # Report Scheduler
        self.scheduler_widget = ReportSchedulerWidget(self.db)
        report_tabs.addTab(self.scheduler_widget, "📅 Report Scheduler")

        # Compliance Reporting
        self.compliance_widget = ComplianceReportingWidget(self.db)
        report_tabs.addTab(self.compliance_widget, "📋 Compliance Reporting")

        # Export Management
        self.export_widget = ExportManagementWidget(self.db)
        report_tabs.addTab(self.export_widget, "💾 Export Management")

        # Audit Trail
        self.audit_widget = AuditTrailWidget(self.db)
        report_tabs.addTab(self.audit_widget, "🔐 Audit Trail")

        # Phase 15 tabs (10 widgets - ML Integration)

        # Demand Forecasting ML
        self.demand_ml_widget = DemandForecastingMLWidget(self.db)
        report_tabs.addTab(self.demand_ml_widget, "🤖 Demand Forecasting ML")

        # Churn Prediction ML
        self.churn_ml_widget = ChurnPredictionMLWidget(self.db)
        report_tabs.addTab(self.churn_ml_widget, "⚠️ Churn Prediction ML")

        # Pricing Optimization ML
        self.pricing_ml_widget = PricingOptimizationMLWidget(self.db)
        report_tabs.addTab(
            self.pricing_ml_widget, "💲 Pricing Optimization ML"
        )

        # Customer Clustering ML
        self.cluster_ml_widget = CustomerClusteringMLWidget(self.db)
        report_tabs.addTab(self.cluster_ml_widget, "👥 Customer Clustering ML")

        # Anomaly Detection ML
        self.anomaly_ml_widget = AnomalyDetectionMLWidget(self.db)
        report_tabs.addTab(self.anomaly_ml_widget, "🚨 Anomaly Detection ML")

        # Recommendation Engine ML
        self.rec_ml_widget = RecommendationEngineWidget(self.db)
        report_tabs.addTab(self.rec_ml_widget, "🎯 Recommendation Engine ML")

        # Resource Optimization ML
        self.resource_ml_widget = ResourceOptimizationMLWidget(self.db)
        report_tabs.addTab(
            self.resource_ml_widget, "⚡ Resource Optimization ML"
        )

        # Marketing Optimization ML
        self.marketing_ml_widget = MarketingMLWidget(self.db)
        report_tabs.addTab(
            self.marketing_ml_widget, "📢 Marketing Optimization ML"
        )

        # Model Performance
        self.model_perf_widget = ModelPerformanceWidget(self.db)
        report_tabs.addTab(self.model_perf_widget, "📊 Model Performance")

        # Predictive Maintenance ML
        self.predict_maint_widget = PredictiveMaintenanceMLWidget(self.db)
        report_tabs.addTab(
            self.predict_maint_widget, "🔧 Predictive Maintenance ML"
        )

        layout.addWidget(report_tabs)
        widget.setLayout(layout)
        return widget

    def create_settings_tab(self) -> QWidget:
        """Settings tab (stub)"""
        widget = QWidget()
        layout = QVBoxLayout()

        info = QLabel("""
        <h3>Arrow Limousine Management System</h3>
        <p><b>Version:</b> 1.0 (Desktop)</p>
        <p><b>Database:</b> PostgreSQL (almsdata)</p>
        <p><b>Framework:</b> PyQt6</p>

        <h4>Keyboard Shortcuts:</h4>
        <ul>
        <li><b>Ctrl+S</b> - Save current form</li>
        <li><b>Ctrl+N</b> - New charter</li>
        <li><b>Ctrl+P</b> - Print document</li>
        <li><b>Ctrl+F</b> - Find/Search</li>
        <li><b>F5</b> - Refresh data</li>
        </ul>

        <h4>Business Rules Implemented:</h4>
        <ul>
        <li>✅ reserve_number is business key for charter-payment matching</li>
        <li>✅ GST is tax-included (5% Alberta rate)</li>
        <li>✅ All database changes auto-committed</li>
        <li>✅ Duplicate prevention on imports</li>
        <li>✅ Protected receipt patterns preserved</li>
        </ul>>
        """)
        layout.addWidget(info)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_table_browser_tab(self) -> QWidget:
        """Admin Table Browser — full read/write access to every DB table."""
        from admin_table_browser_widget import AdminTableBrowserWidget
        return AdminTableBrowserWidget(self.db)

    def refresh_data(self) -> None:
        """Refresh all displayed data (F5)"""
        QMessageBox.information(
            self, "Refresh", "Data refreshed\n[Full implementation pending]"
        )

    def open_find(self) -> None:
        """Open find/search dialog (Ctrl+F)"""
        text, ok = QInputDialog.getText(self, "Find", "Search for:")
        if ok and text:
            QMessageBox.information(
                self,
                "Search",
                f'Searching for "{text}"\n[Full implementation pending]',
            )

    def global_search(self) -> None:
        """Global search across receipts, charters, and clients"""
        query = self.global_search_input.text().strip()
        if len(query) < 2:
            QMessageBox.information(
                self, "Search", "Enter at least 2 characters to search"
            )
            return

        pattern = f"%{query}%"
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except Exception:
                try:
                    self.db.rollback()
                except Exception as _e:
                    logger.debug('Suppressed: %s', _e)
            cur = self.db.get_cursor()

            cur.execute(
                """
                SELECT id as receipt_id, receipt_date, vendor_name,
                description, gross_amount
                FROM receipts
                WHERE vendor_name ILIKE %s OR description ILIKE %s
                ORDER BY receipt_date DESC NULLS LAST
                LIMIT 50
                """,
                (pattern, pattern),
            )
            receipts = cur.fetchall()

            cur.execute(
                """
                SELECT c.charter_id, c.reserve_number, c.charter_date,
                       COALESCE(
                           cl.company_name,
                           cl.client_name,
                           c.client_display_name,
                           'Unknown'
                       ) AS client_display_name,
                       c.booking_notes
                FROM charters c
                LEFT JOIN clients cl ON c.client_id = cl.client_id
                WHERE COALESCE(c.reserve_number,'') ILIKE %s
                    OR COALESCE(c.booking_notes,'') ILIKE %s
                ORDER BY c.charter_date DESC NULLS LAST
                LIMIT 50
                """,
                (pattern, pattern),
            )
            charters = cur.fetchall()

            cur.execute(
                """
                SELECT client_id, client_name, primary_phone, email
                FROM clients
                WHERE client_name ILIKE %s OR primary_phone ILIKE %s OR email
                ILIKE %s
                ORDER BY client_name
                LIMIT 50
                """,
                (pattern, pattern, pattern),
            )
            clients = cur.fetchall()

            cur.close()

            self._show_global_results(query, receipts, charters, clients)
        except Exception as e:
            try:
                self.db.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.critical(self, "Search Failed", f"Search error: {e}")

    def _show_global_results(self, query: str, receipts, charters, clients) -> None:
        """Render search results in a tabbed dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Search Results: {query}")
        layout = QVBoxLayout()

        summary = QLabel(
            f"Receipts: {len(receipts)} | Charters: {len(charters)} |"
            f"Clients: {len(clients)}"
        )
        layout.addWidget(summary)

        tabs = QTabWidget()
        tabs.addTab(
            self._build_results_table(
                ["Date", "Vendor", "Description", "Amount", "ID"],
                [
                    [
                        (r[1] or ""),
                        (r[2] or ""),
                        (r[3] or ""),
                        f"{r[4]:,.2f}" if r[4] is not None else "",
                        str(r[0]),
                    ]
                    for r in receipts
                ],
            ),
            "Receipts",
        )
        tabs.addTab(
            self._build_results_table(
                ["Date", "Reserve #", "Client", "Notes", "ID"],
                [
                    [
                        (c[2] or ""),
                        (c[1] or ""),
                        (c[3] or ""),
                        (c[4] or ""),
                        str(c[0]),
                    ]
                    for c in charters
                ],
            ),
            "Charters",
        )
        tabs.addTab(
            self._build_results_table(
                ["Name", "Phone", "Email", "ID"],
                [
                    [
                        (cl[1] or ""),
                        (cl[2] or ""),
                        (cl[3] or ""),
                        str(cl[0]),
                    ]
                    for cl in clients
                ],
            ),
            "Clients",
        )

        layout.addWidget(tabs)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dialog.setLayout(layout)
        dialog.resize(900, 500)
        dialog.exec()

    def _build_results_table(self, headers, rows) -> object:
        """Helper to create read-only results tables"""
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(rows))

        for row_idx, row_data in enumerate(rows):
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row_idx, col_idx, item)

        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        return table


# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

from login_dialog import LoginDialog


def minimize_terminal() -> None:
    """Minimize the PowerShell terminal window to taskbar"""
    try:
        import ctypes

        # Get current console window
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32

        # Find and minimize PowerShell window
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE = 6
    except Exception:
        pass  # Silent fail if not on Windows or if window ops fail


def set_active_db(target) -> None:
    """Set active database target (called by LoginDialog when user changes"
    "DB)"""

    global ACTIVE_DB_TARGET, OFFLINE_READONLY, ACTIVE_DB_CONFIG
    ACTIVE_DB_TARGET = (target or "neon").lower().strip()
    OFFLINE_READONLY = False  # Allow read-write access to local database

    # Normalize local DB env if needed
    if ACTIVE_DB_TARGET == "local":
        os.environ["DB_HOST"] = os.environ.get("LOCAL_DB_HOST", "localhost")
        os.environ["DB_PORT"] = os.environ.get("LOCAL_DB_PORT", "5432")
        os.environ["DB_NAME"] = os.environ.get("LOCAL_DB_NAME", "almsdata")
        os.environ["DB_USER"] = os.environ.get("LOCAL_DB_USER", "postgres")
        os.environ["DB_PASSWORD"] = os.environ.get(
            "LOCAL_DB_PASSWORD", os.environ.get("DB_PASSWORD", "")
        )
        os.environ["DB_SSLMODE"] = os.environ.get("LOCAL_DB_SSLMODE", "")

    # Rebuild config from environment (set by LoginDialog/LoginManager)
    ACTIVE_DB_CONFIG = {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", 5432)),
        "database": os.environ.get("DB_NAME", "almsdata"),
        "user": os.environ.get("DB_USER", "postgres"),
        "password": os.environ.get("DB_PASSWORD"),
        "sslmode": os.environ.get("DB_SSLMODE", None),
    }

    # Record active DB target for auditability
    os.environ["DB_TARGET"] = ACTIVE_DB_TARGET
    try:
        from datetime import datetime
        from pathlib import Path

        log_path = Path(__file__).resolve().parents[1] / "db_target.log"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = (
            f"[{ts}] ACTIVE_DB_TARGET={ACTIVE_DB_TARGET} "
            f"host={ACTIVE_DB_CONFIG.get('host')} "
            f"db={ACTIVE_DB_CONFIG.get('database')} "
            f"user={ACTIVE_DB_CONFIG.get('user')} "
            f"sslmode={ACTIVE_DB_CONFIG.get('sslmode') or 'none'}"
        )
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
        logger.debug(f"[DB TARGET] {msg}")
    except Exception as _e:
        logger.debug('Suppressed: %s', _e)
# Global DB target configuration (configurable by deployment profile)
ACTIVE_DB_TARGET = (
    os.getenv("ALMS_DEFAULT_DB_TARGET", "neon").lower().strip() or "neon"
)
OFFLINE_READONLY = False
ACTIVE_DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 5432)),
    "database": os.environ.get("DB_NAME", "almsdata"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD"),
    "sslmode": os.environ.get("DB_SSLMODE", None),
}


def _resolve_display_theme(auth_user: dict | None) -> str:
    permissions = (auth_user or {}).get("permissions") or {}
    if isinstance(permissions, dict):
        theme_name = permissions.get("display_theme")
        if theme_name:
            return str(theme_name).strip().lower()

    username = (auth_user or {}).get("username", "")
    if username:
        settings = QSettings("ArrowLimousine", "ALMS")
        fallback = settings.value(f"users/{username}/display_theme", "default")
        return str(fallback or "default").strip().lower()

    return "default"


def _build_display_theme_stylesheet(theme_name: str) -> str:
    if theme_name == "soft_blue":
        return """
            QMainWindow, QWidget {
                background-color: #eaf4ff;
                color: #16324f;
            }
            QTabWidget::pane {
                background-color: #f5faff;
                border: 1px solid #b9d6f2;
            }
            QGroupBox {
                background-color: #f5faff;
                border: 1px solid #b9d6f2;
                margin-top: 10px;
                padding-top: 4px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                color: #16324f;
                background-color: #eaf4ff;
            }
            QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QDateEdit,
            QSpinBox, QDoubleSpinBox, QTimeEdit, QTableWidget {
                background-color: #ffffff;
                color: #16324f;
                border: 1px solid #8fb6de;
                selection-background-color: #5f9ed6;
                selection-color: #ffffff;
            }
            QPushButton {
                background-color: #5f9ed6;
                color: #ffffff;
                border: 1px solid #3f7fb7;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #4a8bc5;
            }
            QHeaderView::section {
                background-color: #d8eafc;
                color: #16324f;
                border: 1px solid #aac8e6;
            }
        """
    if theme_name == "light_gray":
        return """
            QMainWindow, QWidget {
                background-color: #f2f4f7;
                color: #1f2933;
            }
            QTabWidget::pane {
                background-color: #f7f8fa;
                border: 1px solid #cfd8e3;
            }
            QGroupBox {
                background-color: #f7f8fa;
                border: 1px solid #cfd8e3;
                margin-top: 10px;
                padding-top: 4px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                color: #1f2933;
                background-color: #f2f4f7;
            }
            QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QDateEdit,
            QSpinBox, QDoubleSpinBox, QTimeEdit, QTableWidget {
                background-color: #ffffff;
                color: #1f2933;
                border: 1px solid #c8d1dc;
            }
            QPushButton {
                background-color: #64748b;
                color: #ffffff;
                border: 1px solid #475569;
                padding: 4px 10px;
            }
        """
    return ""


def _apply_display_theme(app: QApplication, auth_user: dict | None) -> None:
    theme_name = _resolve_display_theme(auth_user)
    app.setStyleSheet(_build_display_theme_stylesheet(theme_name))


def main() -> None:
    """Main application entry point"""
    try:
        # Minimize terminal first
        minimize_terminal()

        # Auto-start PostgreSQL if not running (Windows only, local mode only)
        import platform

        if platform.system() == "Windows" and ACTIVE_DB_TARGET == "local":
            try:
                import subprocess

                # Check if PostgreSQL 17 is running
                result = subprocess.run(
                    [
                        "powershell",
                        "-Command",
                        "Get-Service postgresql-x64-17 | Select-Object"
                        "-ExpandProperty Status",
                    ],
                    capture_output=True,
                    encoding="utf-8",
                    errors="ignore",
                    timeout=5,
                )
                if "Stopped" in result.stdout:
                    logger.debug("[INFO] PostgreSQL is stopped, attempting to start...")
                    # Try to start PostgreSQL
                    subprocess.Popen(
                        [
                            "powershell",
                            "-Command",
                            "Start-Service -Name postgresql-x64-17"
                            "-ErrorAction SilentlyContinue",
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    import time

                    time.sleep(3)  # Wait for PostgreSQL to start
                    logger.debug("[INFO] PostgreSQL startup initiated")
            except Exception as e:
                logger.warning("Could not auto-start PostgreSQL: %s", e)

        # Qt 6: PassThrough lets 125 % display scale stay as 1.25 instead of
        # being rounded to 1.0 or 2.0, which would squish or balloon every
        # fixed-pixel value in the form layout.
        os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")

        app = QApplication(sys.argv)
        app.setStyle("Fusion")  # Modern look

        # Force 24-hour time display on all QTimeEdit widgets regardless of
        # the Windows system locale (which may default to 12hr on US installs).
        from PyQt6.QtCore import QLocale
        QLocale.setDefault(QLocale(QLocale.Language.English, QLocale.Country.UnitedKingdom))

        # Initialize DB target and propagate env for login manager
        set_active_db(ACTIVE_DB_TARGET)

        # Check for auto-login (local development mode)
        auto_login = os.getenv("AUTO_LOGIN", "false").lower() in (
            "true",
            "1",
            "yes",
        )
        auto_login_user = os.getenv("AUTO_LOGIN_USER", "admin")

        if auto_login:
            logger.warning(f"AUTO_LOGIN enabled - logging in as {auto_login_user} ")
            # Create default auth user for auto-login
            auth_user = {
                "username": auto_login_user,
                "role": "admin",
                "employee_id": 0,
                "permissions": {},
            }
        else:
            # Show login dialog
            login_dialog = LoginDialog(
                active_db_target=ACTIVE_DB_TARGET,
                set_db_callback=set_active_db,
            )

            if login_dialog.exec() == QDialog.DialogCode.Accepted:
                # User authenticated successfully
                auth_user = login_dialog.auth_user

                # Refresh DB config after login in case credentials were
                # entered
                set_active_db(login_dialog.active_db_target)
            else:
                # User cancelled login
                sys.exit(0)

        # Launch main window
        db = DatabaseConnection(ACTIVE_DB_CONFIG)
        _apply_display_theme(app, auth_user)
        window = MainWindow(db=db, auth_user=auth_user)

        # Annotate window title with active DB target
        try:
            base_title = window.windowTitle()
            username = (auth_user or {}).get("username", "user")
            target = (os.getenv("DB_TARGET", "neon") or "neon").lower()
            if target == "local":
                mode_label = f"{username} connected to Emergency Local"
            elif target == "web":
                mode_label = f"{username} connected to Web"
            else:
                mode_label = f"{username} connected to Cloud"
            if auto_login:
                mode_label += " [AUTO-LOGIN]"
            window.setWindowTitle(f"{base_title} [{mode_label}]")
        except Exception as _e:
            logger.debug('Suppressed: %s', _e)
        window.showMaximized()
        sys.exit(app.exec())
    except Exception:
        logger.exception("Fatal error in main")
        sys.exit(1)


if __name__ == "__main__":
    main()
