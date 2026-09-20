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
import re
import sys
import unicodedata

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

# Add current directory and project root to path for module imports before
# loading package-local modules.
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, os.pardir))
for path_candidate in (current_dir, project_root):
    if path_candidate not in sys.path:
        sys.path.insert(0, path_candidate)

# App-wide logging
import logging

try:
    from desktop_app.app_logger import install_excepthook, setup_logging
except ModuleNotFoundError:
    try:
        from app_logger import install_excepthook, setup_logging
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Unable to import app_logger from either the package or the "
            "project root."
        ) from exc

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
    QColor,
    QFont,
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
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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

# Keep database module import lightweight at startup. Heavy UI/report modules are
# lazy-loaded after login so the login dialog appears faster.
from db_connection import DatabaseConnection


_MAIN_DEPS_LOADED = False


def _load_main_window_dependencies() -> None:
    """Load heavy runtime modules only when launching the main window."""
    global _MAIN_DEPS_LOADED
    global AssetManagementWidget
    global CharterFormWidget
    global EnhancedBankingManager
    global EnhancedReceiptsManager
    global NsfPairManagerWidget
    global ReportManagementWidget
    global CopilotWidget
    global CrystalReportsWidget
    global CustomReportBuilderWidget
    global init_error_logger
    global FunctionExecutor
    global KnowledgeRetriever
    global ReportExplorerWidget
    global GridStandardsManager
    global create_page_header
    global install_replace_all_behavior
    global YearEndManagementWidget
    global YearEndWizardWidget

    if _MAIN_DEPS_LOADED:
        return

    from asset_management_widget import AssetManagementWidget
    from charter_form_widget import CharterFormWidget
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

    from copilot_widget import CopilotWidget
    from crystal_reports_widget import CrystalReportsWidget
    from dashboards_analytics import CustomReportBuilderWidget
    from error_logger import init_error_logger
    from function_executor import FunctionExecutor
    from rag_engine import KnowledgeRetriever
    from report_explorer_widget import ReportExplorerWidget
    from ui_standards import (
        GridStandardsManager,
        create_page_header,
        install_replace_all_behavior,
    )
    from year_end_management_widget import YearEndManagementWidget
    from year_end_wizard_widget import YearEndWizardWidget

    _MAIN_DEPS_LOADED = True


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
        _load_main_window_dependencies()
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
            f"Arrow Limousine Desktop System{user_suffix}"
        )
        self.setMinimumSize(1024, 700)
        current_year = datetime.now().year
        self._app_scope = {
            "domain": "all",
            "year_mode": "range",
            "year_start": current_year - 1,
            "year_end": current_year + 1,
        }
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

        logger.info("  2. Basic init OK")

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
            logger.info("  4.5. Initializing error logger...")
            self.error_logger = init_error_logger(self.db)
            logger.info("  [OK] Error logging system initialized")
        except Exception as e:
            logger.warning("Error logger initialization failed: %s", e)
            # Non-fatal - app can continue without error logging

        logger.info("  5. Creating central widget...")
        # Wrapper widget to host global search + tabs
        central = QWidget()
        central.setObjectName("mainCentralWidget")
        central.setStyleSheet(
            "QWidget#mainCentralWidget { background: #e8eef5; }"
        )
        central_layout = QVBoxLayout()
        central_layout.setContentsMargins(5, 5, 5, 5)
        central_layout.setSpacing(6)

        # Global search bar (multi-table)
        self.search_bar_widget = QWidget()
        search_bar = QHBoxLayout(self.search_bar_widget)
        search_bar.setContentsMargins(0, 0, 0, 0)
        search_bar.setSpacing(6)
        search_label = QLabel("Global Search:")
        self.global_search_input = QLineEdit()
        self.global_search_input.setPlaceholderText(
            "Search receipts, charters, clients, or sections (e.g. year end)..."
        )
        self.global_search_input.returnPressed.connect(self.global_search)
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
        central_layout.addWidget(self.search_bar_widget)
        logger.info("  6. Search bar OK")

        # Global UI behavior manager for all grids and input focus behavior.
        self.grid_standards = GridStandardsManager("ArrowLimo", "Desktop")

        # Create tab interface
        logger.info("  7. Creating main QTabWidget...")
        self.tabs = QTabWidget()
        self._focus_mode = False

        # Track which tabs have been loaded (for lazy loading)
        self._lazy_tab_factories = {
            "🚀 Operations": self.create_operations_parent_tab,
            "🚗 Fleet & People": self.create_fleet_people_parent_tab,
            "💰 Accounting & Finance": self.create_accounting_parent_tab,
            "🧮 Year-End Audit": self.create_year_end_audit_tab,
            "⚙️ Admin & Settings": self.create_admin_parent_tab,
        }
        self._tabs_loaded = set()
        self._tab_load_in_progress = set()
        self._lazy_loading_ready = False
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
        self._close_return_context = None
        self._close_return_button = QPushButton()
        self._close_return_button.setVisible(False)
        self._close_return_button.setStyleSheet(
            "background: #2563eb; color: white; font-weight: bold; padding: 3px 9px;"
        )
        self._close_return_button.clicked.connect(
            self._return_to_close_management
        )
        self.status_bar.addPermanentWidget(self._close_return_button)

        self._close_later_button = QPushButton("Later")
        self._close_later_button.setVisible(False)
        self._close_later_button.setToolTip(
            "Dismiss the return reminder and continue working"
        )
        self._close_later_button.clicked.connect(
            self.clear_close_return_context
        )
        self.status_bar.addPermanentWidget(self._close_later_button)
        self.setStatusBar(self.status_bar)
        self._restore_close_return_context()

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
            periodic_db_checks = (
                os.getenv("DB_TARGET", "neon").lower().strip() == "local"
            )
            self.db_monitor.start_monitoring(periodic=periodic_db_checks)
            logger.debug(
                "  [OK] Database connection monitoring initialized "
                "(periodic=%s)",
                periodic_db_checks,
            )
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

        view_menu = menubar.addMenu("View")
        self.focus_mode_action = QAction(
            "Focus Mode (Hide Navigation)",
            self,
        )
        self.focus_mode_action.setCheckable(True)
        self.focus_mode_action.setShortcut("Ctrl+Shift+F")
        self.focus_mode_action.setStatusTip(
            "Hide search, tab rows, and the status bar to maximize workspace"
        )
        self.focus_mode_action.toggled.connect(self._set_focus_mode)
        view_menu.addAction(self.focus_mode_action)

        # Passive update CTA (top-right): only appears when a newer version is detected.
        self._update_notice_button = QPushButton("Update Required")
        self._update_notice_button.setVisible(False)
        self._update_notice_button.setStyleSheet(
            "QPushButton {"
            " background-color: #d98f00; color: white; font-weight: bold;"
            " padding: 3px 10px; border-radius: 3px;"
            "}"
            "QPushButton:hover { background-color: #c57f00; }"
        )
        self._update_notice_button.clicked.connect(self._on_update_required_clicked)
        menubar.setCornerWidget(self._update_notice_button, Qt.Corner.TopRightCorner)
        self._pending_update_info = None

        # Quick access menu for high-frequency accounting tools.
        management_menu = menubar.addMenu("Quick Access")
        logger.info("  ✓ Quick Access menu created")

        receipts_mgr_action = QAction("📋 Enhanced Receipts", self)
        receipts_mgr_action.triggered.connect(
            self._open_enhanced_receipts_manager
        )
        management_menu.addAction(receipts_mgr_action)
        logger.info("  ✓ Enhanced Receipts action added")

        banking_mgr_action = QAction("🏦 Enhanced Banking", self)
        banking_mgr_action.triggered.connect(
            self._open_enhanced_banking_manager
        )
        management_menu.addAction(banking_mgr_action)
        logger.info("  ✓ Enhanced Banking action added")

        logger.info("  8. Main tab widget created")

        # Main launcher tab controls section/year scope for this session.
        self.main_workspace_tab = self.create_workspace_launcher_tab()
        self.tabs.addTab(self.main_workspace_tab, "🏠 Main")

        self._active_section_tab_text = ""
        self._lazy_loading_ready = True
        self._apply_initial_scope_tab_focus()

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
        QTimer.singleShot(800, self._show_post_update_success_once)
        # Startup + periodic passive update checks (no popup interruption).
        try:
            from auto_updater import AutoUpdater
            _updater = AutoUpdater(
                parent_widget=self,
                on_update_available=self._on_update_available_passive,
            )
            from PyQt6.QtCore import QTimer as _QTimer

            _QTimer.singleShot(3000, self._run_passive_update_check)
            self._update_check_timer = _QTimer(self)
            self._update_check_timer.setInterval(30 * 60 * 1000)
            self._update_check_timer.timeout.connect(self._run_passive_update_check)
            self._update_check_timer.start()
            self._auto_updater = _updater  # keep reference alive
        except Exception as _ue:
            logger.debug("Auto-updater init skipped: %s", _ue)

    def _run_passive_update_check(self) -> None:
        """Check for updates without showing popup dialogs."""
        updater = getattr(self, "_auto_updater", None)
        if updater is None:
            return
        updater.check_for_updates(silent=True, passive=True)

    def _on_update_available_passive(self, update_info: dict) -> None:
        """Show non-blocking top update CTA as soon as a new version is detected."""
        self._pending_update_info = dict(update_info or {})
        btn = getattr(self, "_update_notice_button", None)
        if btn is None:
            return

        version = str(self._pending_update_info.get("version") or "").strip()
        changelog = self._pending_update_info.get("changelog") or []
        fix_count = len(changelog) if isinstance(changelog, list) else 0

        if version:
            if fix_count >= 2:
                btn.setText(f"Update Required (v{version}, {fix_count} fixes)")
            else:
                btn.setText(f"Update Required (v{version})")
        else:
            btn.setText("Update Required")
        btn.setToolTip("New version available. Click when ready to update.")
        btn.setVisible(True)

    def _on_update_required_clicked(self) -> None:
        """Open updater flow on demand from the top update button."""
        updater = getattr(self, "_auto_updater", None)
        if updater is None:
            return
        updater.start_update(getattr(self, "_pending_update_info", None))

    def _show_post_update_success_once(self) -> None:
        """Show one-time completion notice written by update_dispatcher.ps1."""
        notice_candidates = []

        if getattr(sys, "frozen", False):
            install_root = os.path.dirname(sys.executable)
            notice_candidates.append(
                os.path.join(
                    install_root,
                    "_install_reports",
                    "post_update_notice.txt",
                )
            )

        notice_candidates.append(
            os.path.join(project_root, "_install_reports", "post_update_notice.txt")
        )

        seen = set()
        for notice_path in notice_candidates:
            key = notice_path.lower()
            if key in seen:
                continue
            seen.add(key)

            if not os.path.exists(notice_path):
                continue

            try:
                version = "unknown"
                with open(notice_path, encoding="utf-8") as notice_file:
                    loaded_version = notice_file.read().strip()
                    if loaded_version:
                        version = loaded_version

                try:
                    os.remove(notice_path)
                except Exception as remove_err:
                    logger.warning(
                        "Could not clear post-update notice marker %s: %s",
                        notice_path,
                        remove_err,
                    )

                QMessageBox.information(
                    self,
                    "Update Complete",
                    (
                        "Winner Winner Chicken Dinner\n"
                        f"Update to version {version} completed."
                    ),
                )
                return
            except Exception as notice_err:
                logger.warning(
                    "Failed to process post-update notice marker %s: %s",
                    notice_path,
                    notice_err,
                )

    # ============================================================================
    # LAZY LOADING - Load tab content only when first clicked
    # ============================================================================
    def _set_focus_mode(self, enabled: bool) -> None:
        """Expand the active workspace by hiding navigation chrome."""
        self._focus_mode = enabled
        self.search_bar_widget.setVisible(not enabled)
        self.status_bar.setVisible(not enabled)
        for tab_widget in self.findChildren(QTabWidget):
            tab_widget.tabBar().setVisible(not enabled)
        self.focus_mode_action.setText(
            "Exit Focus Mode (Show Navigation)"
            if enabled
            else "Focus Mode (Hide Navigation)"
        )

    def set_close_return_context(
        self,
        period_type: str,
        period_key: str,
        task_key: str,
    ) -> None:
        """Show persistent Return/Later controls after a checklist handoff."""
        self._close_return_context = {
            "period_type": period_type,
            "period_key": period_key,
            "task_key": task_key,
        }
        settings = QSettings("ArrowLimo", "Desktop")
        settings.beginGroup("close_return")
        settings.setValue("period_type", period_type)
        settings.setValue("period_key", period_key)
        settings.setValue("task_key", task_key)
        settings.endGroup()

        close_name = "Month-End" if period_type == "month" else "Year-End"
        self._close_return_button.setText(
            f"↩ Return to {close_name} {period_key}"
        )
        self._close_return_button.setVisible(True)
        self._close_later_button.setVisible(True)

    def _restore_close_return_context(self) -> None:
        """Restore an unfinished checklist handoff after reopening the app."""
        settings = QSettings("ArrowLimo", "Desktop")
        settings.beginGroup("close_return")
        period_type = settings.value("period_type", "", type=str)
        period_key = settings.value("period_key", "", type=str)
        task_key = settings.value("task_key", "", type=str)
        settings.endGroup()
        if period_type in {"month", "year"} and period_key and task_key:
            self.set_close_return_context(period_type, period_key, task_key)

    def clear_close_return_context(self, *_args) -> None:
        """Dismiss the return reminder and continue in the current module."""
        self._close_return_context = None
        QSettings("ArrowLimo", "Desktop").remove("close_return")
        self._close_return_button.setVisible(False)
        self._close_later_button.setVisible(False)

    def _return_to_close_management(self) -> None:
        """Return to the month/year checklist that opened the current module."""
        context = self._close_return_context
        if not context:
            return
        tab_name = (
            "📆 Month-End Close"
            if context["period_type"] == "month"
            else "🗓️ Year-End Close"
        )
        if not self.navigate_to_accounting_subtab(tab_name):
            QMessageBox.warning(
                self,
                "Return to Close",
                f"Could not open {tab_name}.",
            )
            return
        widget_name = (
            "month_end_close_widget"
            if context["period_type"] == "month"
            else "year_end_close_widget"
        )
        widget = getattr(self, widget_name, None)
        if widget is not None:
            widget.set_period_key(context["period_key"])

    def _on_tab_changed(self, index: int) -> None:
        """Load tab content on first access (lazy loading)"""
        if not self._lazy_loading_ready:
            return
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
            if self._focus_mode:
                QTimer.singleShot(0, lambda: self._set_focus_mode(True))

    # ============================================================================
    # KEYBOARD SHORTCUT HANDLERS
    # ============================================================================
    def new_receipt(self) -> None:
        """Ctrl+N: Create new receipt"""
        # Navigate to Receipts tab and clear form
        self.navigate_to_top_tab("💰 Accounting & Finance")
        QMessageBox.information(
            self,
            "New Receipt",
            "New receipt form ready\n[Focus on Receipt entry area]",
        )

    def _prompt_startup_scope(self) -> None:
        """Collect startup domain/year scope to reduce initial workload."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Startup Load Scope")
        dialog.setModal(True)
        dialog.setMinimumWidth(440)

        layout = QVBoxLayout(dialog)

        intro = QLabel(
            "Choose what to focus on for this session.\n"
            "This limits what loads immediately and sets default year scope."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        domain_label = QLabel("Start In Domain:")
        domain_combo = QComboBox()
        domain_combo.addItem("All Domains", "all")
        domain_combo.addItem("Operations", "operations")
        domain_combo.addItem("Fleet", "fleet")
        domain_combo.addItem("Accounting", "accounting")
        layout.addWidget(domain_label)
        layout.addWidget(domain_combo)

        year_mode_label = QLabel("Working Years:")
        year_mode_combo = QComboBox()
        year_mode_combo.addItem("Current + Last Year", "current_plus_last")
        year_mode_combo.addItem("Current Year Only", "current")
        year_mode_combo.addItem("All Years", "all")
        year_mode_combo.addItem("Custom Range", "custom")
        layout.addWidget(year_mode_label)
        layout.addWidget(year_mode_combo)

        custom_row = QHBoxLayout()
        custom_start = QSpinBox()
        custom_end = QSpinBox()
        now_year = datetime.now().year
        custom_start.setRange(2010, 2035)
        custom_end.setRange(2010, 2035)
        custom_start.setValue(now_year - 1)
        custom_end.setValue(now_year)
        custom_start.setEnabled(False)
        custom_end.setEnabled(False)
        custom_row.addWidget(QLabel("From:"))
        custom_row.addWidget(custom_start)
        custom_row.addSpacing(12)
        custom_row.addWidget(QLabel("To:"))
        custom_row.addWidget(custom_end)
        custom_row.addStretch(1)
        layout.addLayout(custom_row)

        def _toggle_custom_years() -> None:
            is_custom = year_mode_combo.currentData() == "custom"
            custom_start.setEnabled(is_custom)
            custom_end.setEnabled(is_custom)

        year_mode_combo.currentIndexChanged.connect(_toggle_custom_years)

        buttons = QHBoxLayout()
        continue_btn = QPushButton("Continue")
        continue_btn.clicked.connect(dialog.accept)
        default_btn = QPushButton("Use Defaults")
        default_btn.clicked.connect(dialog.reject)
        buttons.addStretch(1)
        buttons.addWidget(default_btn)
        buttons.addWidget(continue_btn)
        layout.addLayout(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        year_mode = str(year_mode_combo.currentData())
        year_start = now_year - 1
        year_end = now_year
        if year_mode == "current":
            year_start = now_year
            year_end = now_year
        elif year_mode == "all":
            year_start = 2010
            year_end = now_year
        elif year_mode == "custom":
            year_start = int(custom_start.value())
            year_end = int(custom_end.value())
            if year_start > year_end:
                year_start, year_end = year_end, year_start

        self._app_scope = {
            "domain": str(domain_combo.currentData()),
            "year_mode": year_mode,
            "year_start": year_start,
            "year_end": year_end,
        }

    def get_working_year_scope(self) -> tuple[int, int]:
        """Return the selected startup year range for data filters."""
        return (
            int(self._app_scope.get("year_start", datetime.now().year - 1)),
            int(self._app_scope.get("year_end", datetime.now().year)),
        )

    def create_workspace_launcher_tab(self) -> QWidget:
        """Main launcher tab with hierarchical icon drill-down navigation."""
        widget = QWidget()
        widget.setObjectName("workspaceLauncher")
        widget.setStyleSheet(
            "QWidget#workspaceLauncher { background: #e8eef5; }"
        )
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = QLabel("Session Workspace")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Open one section at a time to reduce memory usage. "
            "Use the full menu list below to open any section directly."
        )
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        year_row = QHBoxLayout()
        year_row.addWidget(QLabel("Working Years:"))
        year_row.addWidget(QLabel("From:"))
        self.main_custom_year_start = QSpinBox()
        self.main_custom_year_start.setRange(2010, 2035)
        self.main_custom_year_start.setValue(datetime.now().year - 1)
        year_row.addWidget(self.main_custom_year_start)
        year_row.addWidget(QLabel("To:"))
        self.main_custom_year_end = QSpinBox()
        self.main_custom_year_end.setRange(2010, 2035)
        self.main_custom_year_end.setValue(datetime.now().year + 1)
        year_row.addWidget(self.main_custom_year_end)
        self.main_current_year_btn = QPushButton("Current")
        self.main_current_year_btn.clicked.connect(
            self._set_main_year_range_current
        )
        year_row.addWidget(self.main_current_year_btn)
        year_row.addStretch(1)
        layout.addLayout(year_row)

        self._main_nav_selection = {
            "domain": None,
            "sub_tab": None,
            "sub_sub_tab": None,
            "deep_tab": None,
        }
        self._menu_nav_request_id = 0
        self._main_menu_collapsed_domains: set[str] = set()

        toolbar_row = QHBoxLayout()
        toolbar_row.addStretch(1)
        self.main_menu_toggle_all_btn = QPushButton("▲ Collapse All")
        self.main_menu_toggle_all_btn.setToolTip(
            "Collapse or expand every section below to save screen space"
        )
        self.main_menu_toggle_all_btn.clicked.connect(
            self._toggle_all_main_menu_domains
        )
        toolbar_row.addWidget(self.main_menu_toggle_all_btn)
        layout.addLayout(toolbar_row)

        self.main_full_menu_scroll = QScrollArea()
        self.main_full_menu_scroll.setWidgetResizable(True)
        self.main_full_menu_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.main_full_menu_scroll.setStyleSheet(
            "QScrollArea { background: #e8eef5; border: 0; }"
            "QScrollArea > QWidget > QWidget { background: #e8eef5; }"
        )
        self.main_full_menu_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.main_full_menu_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.main_full_menu_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.main_full_menu_columns_panel = QWidget()
        self.main_full_menu_columns_panel.setObjectName("mainMenuPanel")
        self.main_full_menu_columns_panel.setAutoFillBackground(True)
        self.main_full_menu_columns_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self.main_full_menu_columns_panel.setMinimumWidth(0)
        self.main_full_menu_columns_panel.setStyleSheet(
            "QWidget#mainMenuPanel { background: #e8eef5; border-radius: 0px; }"
        )
        self.main_full_menu_columns_layout = QHBoxLayout(
            self.main_full_menu_columns_panel
        )
        self.main_full_menu_columns_layout.setContentsMargins(10, 10, 10, 10)
        self.main_full_menu_columns_layout.setSpacing(12)
        self.main_full_menu_scroll.setWidget(self.main_full_menu_columns_panel)

        layout.addWidget(self.main_full_menu_scroll, 1)

        self._render_full_open_menu_list()
        return widget

    def _render_full_open_menu_list(self) -> None:
        """Render all navigation targets as expanded domain columns."""
        while self.main_full_menu_columns_layout.count():
            item = self.main_full_menu_columns_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        structure = self._main_navigation_structure()
        longest_column_height = 0
        for domain_key, domain_meta in structure.items():
            column_widget = QWidget()
            column_widget.setMinimumWidth(220)
            column_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred,
            )
            column_layout = QVBoxLayout(column_widget)
            column_layout.setContentsMargins(0, 0, 0, 0)
            column_layout.setSpacing(6)

            is_collapsed = domain_key in self._main_menu_collapsed_domains

            header_row = QHBoxLayout()
            header = QLabel(domain_meta.get("label", domain_key))
            header.setStyleSheet(
                "font-weight: bold; color: #1f2937; font-size: 11pt;"
            )
            header_row.addWidget(header)
            header_row.addStretch(1)
            toggle_btn = QPushButton("▶" if is_collapsed else "▼")
            toggle_btn.setToolTip("Expand" if is_collapsed else "Collapse")
            toggle_btn.setFixedWidth(28)
            toggle_btn.setStyleSheet(
                "QPushButton { border: none; font-weight: bold; }"
            )
            toggle_btn.clicked.connect(
                lambda _=False, dk=domain_key: self._toggle_main_menu_domain(dk)
            )
            header_row.addWidget(toggle_btn)
            column_layout.addLayout(header_row)

            links = QListWidget()
            links.setMinimumWidth(180)
            links.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred,
            )
            links.setFrameShape(QFrame.Shape.NoFrame)
            links.setStyleSheet(
                "QListWidget { font-size: 10.5pt; }"
                " QListWidget::item { padding: 3px 2px; }"
            )
            links.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            links.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            links.setUniformItemSizes(True)
            links.itemDoubleClicked.connect(
                self._on_full_menu_link_item_activated
            )
            links.itemActivated.connect(self._on_full_menu_link_item_activated)
            links.itemClicked.connect(self._on_full_menu_link_item_activated)

            self._populate_full_menu_domain_links(
                links,
                domain_key,
                domain_meta.get("subtabs", {}),
                [],
            )
            self._fit_full_menu_links_height(links)
            links.setVisible(not is_collapsed)
            column_layout.addWidget(links)
            self.main_full_menu_columns_layout.addWidget(
                column_widget,
                1,
                Qt.AlignmentFlag.AlignTop,
            )

            column_height = column_widget.sizeHint().height()
            if column_height > longest_column_height:
                longest_column_height = column_height

        if longest_column_height > 0:
            self.main_full_menu_columns_panel.setMinimumHeight(
                longest_column_height + 14
            )
            self.main_full_menu_columns_panel.setMaximumHeight(
                16777215
            )

    def _toggle_main_menu_domain(self, domain_key: str) -> None:
        """Expand/collapse a single Main-tab domain column."""
        if domain_key in self._main_menu_collapsed_domains:
            self._main_menu_collapsed_domains.discard(domain_key)
        else:
            self._main_menu_collapsed_domains.add(domain_key)
        self._render_full_open_menu_list()

    def _toggle_all_main_menu_domains(self) -> None:
        """Collapse every domain column if any are expanded, else expand all."""
        structure = self._main_navigation_structure()
        all_keys = set(structure.keys())
        if self._main_menu_collapsed_domains == all_keys:
            self._main_menu_collapsed_domains = set()
        else:
            self._main_menu_collapsed_domains = set(all_keys)
        self.main_menu_toggle_all_btn.setText(
            "▼ Expand All"
            if self._main_menu_collapsed_domains
            else "▲ Collapse All"
        )
        self._render_full_open_menu_list()

    def _populate_full_menu_domain_links(
        self,
        links: QListWidget,
        domain_key: str,
        nodes: dict,
        path_parts: list[str],
    ) -> None:
        """Populate one domain column as plain indented link rows."""
        for name, node in nodes.items():
            current = list(path_parts)
            current.append(name)
            depth = max(0, len(current) - 1)
            indent = "  " * depth
            prefix = "• " if depth == 0 else "↳ "
            item = QListWidgetItem(f"{indent}{prefix}{name}")
            item.setData(Qt.ItemDataRole.UserRole, (domain_key, tuple(current)))
            if self._is_most_used_path(domain_key, tuple(current)):
                item.setForeground(QColor("#0b6b2d"))
                bold_font = QFont()
                bold_font.setBold(True)
                item.setFont(bold_font)
            links.addItem(item)

            child_nodes = node.get("subtabs", {}) if isinstance(node, dict) else {}
            if child_nodes:
                self._populate_full_menu_domain_links(
                    links,
                    domain_key,
                    child_nodes,
                    current,
                )

    def _on_full_menu_link_item_activated(self, item: QListWidgetItem) -> None:
        """Open selected path from mega-menu text links."""
        payload = item.data(Qt.ItemDataRole.UserRole)
        if not payload:
            return
        domain_key, path_parts = payload
        self._open_full_menu_path(domain_key, path_parts)

    def _is_most_used_path(
        self, domain_key: str, path_parts: tuple[str, ...]
    ) -> bool:
        """Return True when a path is in the visual most-used set."""
        most_used_paths = {
            ("operations", ("📡 Dispatch", "📋 Dispatch Board")),
            ("operations", ("📡 Dispatch", "📝 Run Charter")),
            ("operations", ("💳 Client Payments",)),
            ("accounting", ("📅 Close Management", "📆 Month-End Close")),
            ("accounting", ("💰 Receipts & Invoices",)),
            ("operations", ("✅ Close Control Center",)),
            ("fleet", ("🚗 Fleet List",)),
            ("admin", ("⚙️ Admin Controls",)),
            ("operations", ("📊 Reports & PDFs",)),
        }
        return (domain_key, path_parts) in most_used_paths

    def _fit_full_menu_links_height(self, links: QListWidget) -> None:
        """Fit a column list to all rows so it never shows internal scrollbars."""
        rows = links.count()
        if rows <= 0:
            return

        row_height = links.sizeHintForRow(0)
        if row_height <= 0:
            row_height = 22

        target_height = (links.frameWidth() * 2) + (rows * row_height) + 6
        links.setMinimumHeight(target_height)
        links.setMaximumHeight(target_height)

    def _collect_full_menu_targets(
        self,
        domain_key: str,
        nodes: dict,
        path_parts: list[str],
    ) -> list[list[str]]:
        """Collect every reachable menu path under a domain."""
        targets = []
        for name, node in nodes.items():
            current = list(path_parts)
            current.append(name)
            targets.append(current)
            child_nodes = node.get("subtabs", {}) if isinstance(node, dict) else {}
            if child_nodes:
                targets.extend(
                    self._collect_full_menu_targets(domain_key, child_nodes, current)
                )
        return targets

    def _open_full_menu_path(self, domain_key: str, path_parts: tuple[str, ...]) -> None:
        """Open a selected path from the full open mini menu list."""
        sub_tab = path_parts[0] if len(path_parts) >= 1 else None
        sub_sub_tab = path_parts[1] if len(path_parts) >= 2 else None
        deep_tab = path_parts[2] if len(path_parts) >= 3 else None

        self._main_nav_selection = {
            "domain": domain_key,
            "sub_tab": sub_tab,
            "sub_sub_tab": sub_sub_tab,
            "deep_tab": deep_tab,
        }
        self._open_menu_target(domain_key, sub_tab, sub_sub_tab, deep_tab)

    def _main_navigation_structure(self) -> dict:
        """Navigation model used by Main dropdown launcher."""
        return {
            "operations": {
                "label": "🚀 Operations",
                "subtabs": {
                    "📡 Dispatch": {
                        "subtabs": {
                            "📋 Dispatch Board": {},
                            "📝 Run Charter": {},
                            "👷 Staff Work Schedule": {},
                            "📅 Calendar (Outlook Style)": {},
                            "🗓️ Calendar (Table View)": {},
                            "👤 Driver Calendar": {},
                            "🚐 Vehicle Booked Out": {},
                            "🛒 Beverage Orders": {},
                            "📅 Unbooked Events": {},
                        }
                    },
                    "🍷 Beverage": {},
                    "👥 Customers": {},
                    "💳 Client Payments": {},
                    "📄 Documents": {},
                    "✅ Close Control Center": {},
                    "📊 Reports & PDFs": {
                        "subtabs": {
                            name: {}
                            for name in self._report_section_factory_map()
                        }
                    },
                },
            },
            "fleet": {
                "label": "🚗 Fleet & People",
                "subtabs": {
                    "🚐 Vehicles": {
                        "subtabs": {
                            "🆔 Identification": {},
                            "📊 Status & Specs": {},
                            "🔧 Maintenance": {},
                            "🛢️ Fluids & Parts": {},
                            "🛡️ Insurance & Registration": {},
                            "💲 Purchase & Lifecycle": {},
                            "📑 Lease Compliance": {},
                            "📄 Documents": {},
                        }
                    },
                    "🚗 Fleet List": {},
                    "👔 Employees": {
                        "subtabs": {
                            "📝 Basic Info": {},
                            "💼 Classifications": {},
                            "⚖️ HOS Compliance": {},
                            "💰 Payroll": {},
                            "🎓 Training": {},
                            "📄 Qualifications & Documents": {},
                        }
                    },
                },
            },
            "accounting": {
                "label": "💰 Accounting & Finance",
                "subtabs": {
                    "📅 Close Management": {
                        "subtabs": {
                            "📆 Month-End Close": {},
                            "🗓️ Year-End Close": {},
                        }
                    },
                    "🗂️ Daily Work": {
                        "subtabs": {
                            "🎯 Accounting Hub": {},
                            "💰 Receipts & Invoices": {},
                            "📝 Accountant Notes": {},
                            "📋 Vendor Invoices": {},
                            "🧾 Enhanced Receipts": {},
                            "💳 Payment Linker": {},
                        }
                    },
                    "🏦 Banking & Cash": {
                        "subtabs": {
                            "📒 Check Book": {},
                            "🏦 Enhanced Banking": {},
                            "🧩 NSF Pairs": {},
                            "🏦 Staff Loan Account": {},
                        }
                    },
                    "👔 Payroll & Tax": {
                        "subtabs": {
                            "💵 Payroll Entry": {},
                            "🧮 Payroll Remittances": {},
                            "🏛️ Tax": {},
                            "📋 T2 Corporate Tax": {},
                            "🛡️ WCB Rates": {},
                        }
                    },
                    "📊 Compliance & Reports": {
                        "subtabs": {
                            "🧪 Audit": {},
                            "🏢 Business Entity": {},
                            "📦 Asset Inventory": {},
                            "📊 Financial Reports": {},
                            "🍷 Beverage Revenue": {},
                            "🍷 Beverage": {},
                        }
                    },
                },
            },
            "year_end": {
                "label": "🧮 Year-End Audit",
                "subtabs": {
                    "🧭 Year-End Guided Wizard": {},
                    "🔎 Audit Checks (Advanced)": {},
                },
            },
            "admin": {
                "label": "⚙️ Admin & Settings",
                "subtabs": {
                    "⚙️ Admin Controls": {},
                    "🔧 Settings": {},
                    "🗄️ Table Browser": {},
                },
            },
        }

    def _set_main_year_range_current(self) -> None:
        """Set Main working years to last year through next year."""
        now_year = datetime.now().year
        self.main_custom_year_start.setValue(now_year - 1)
        self.main_custom_year_end.setValue(now_year + 1)

    def _update_scope_from_main_tab_controls(self) -> None:
        """Persist year/domain scope selected on the Main tab."""
        domain = self._main_nav_selection.get("domain") or str(
            self._app_scope.get("domain", "all")
        )
        year_mode = "range"
        year_start = int(self.main_custom_year_start.value())
        year_end = int(self.main_custom_year_end.value())
        if year_start > year_end:
            year_start, year_end = year_end, year_start

        self._app_scope = {
            "domain": domain,
            "year_mode": year_mode,
            "year_start": year_start,
            "year_end": year_end,
        }

    def _open_menu_target(
        self,
        domain: str,
        sub_tab: str | None = None,
        sub_sub_tab: str | None = None,
        deep_tab: str | None = None,
    ) -> None:
        """Open selected domain from Main menu and optionally drill into sub-tab."""
        self._menu_nav_request_id += 1
        request_id = self._menu_nav_request_id

        self._app_scope["domain"] = domain
        self._update_scope_from_main_tab_controls()
        target_tab = {
            "operations": "🚀 Operations",
            "fleet": "🚗 Fleet & People",
            "accounting": "💰 Accounting & Finance",
            "year_end": "🧮 Year-End Audit",
            "admin": "⚙️ Admin & Settings",
        }.get(domain, "🚀 Operations")
        self._open_single_section_tab(target_tab)

        if not sub_tab:
            return

        if domain == "accounting":
            self._deferred_menu_navigation(
                self.navigate_to_accounting_subtab,
                deep_tab or sub_sub_tab or sub_tab,
                request_id=request_id,
            )
        elif domain == "operations":
            if sub_tab == "📡 Dispatch" and sub_sub_tab:
                self._deferred_menu_navigation(
                    lambda tab_name, rid=request_id: self._navigate_to_dispatch_subtab(
                        tab_name,
                        nav_request_id=rid,
                    ),
                    deep_tab or sub_sub_tab,
                    request_id=request_id,
                )
            elif sub_tab == "📝 Run Charter":
                self._deferred_menu_navigation(
                    lambda tab_name, rid=request_id: self._navigate_to_dispatch_subtab(
                        tab_name,
                        nav_request_id=rid,
                    ),
                    "📝 Run Charter",
                    request_id=request_id,
                )
            elif sub_tab == "📊 Reports & PDFs" and sub_sub_tab:
                self._deferred_menu_navigation(
                    lambda tab_name, rid=request_id: self._navigate_to_reports_subtab(
                        tab_name,
                        nav_request_id=rid,
                    ),
                    sub_sub_tab,
                    request_id=request_id,
                )
            else:
                self._deferred_menu_navigation(
                    self.navigate_to_operations_subtab,
                    sub_tab,
                    request_id=request_id,
                )
        elif domain == "fleet":
            if sub_tab in ("🚐 Vehicles", "👔 Employees") and sub_sub_tab:
                self._deferred_menu_navigation(
                    lambda tab_name, rid=request_id, parent=sub_tab: self._navigate_to_fleet_inner_subtab(
                        parent,
                        tab_name,
                        nav_request_id=rid,
                    ),
                    sub_sub_tab,
                    request_id=request_id,
                )
            else:
                self._deferred_menu_navigation(
                    self._navigate_to_fleet_subtab,
                    sub_tab,
                    request_id=request_id,
                )
        elif domain == "admin":
            self._deferred_menu_navigation(
                self._navigate_to_admin_subtab,
                sub_tab,
                request_id=request_id,
            )
        elif domain == "year_end":
            self._deferred_menu_navigation(
                self._navigate_to_year_end_subtab,
                sub_tab,
                request_id=request_id,
            )

    def _deferred_menu_navigation(
        self,
        navigate_fn,
        tab_name: str,
        retries: int = 120,
        delay_ms: int = 120,
        request_id: int | None = None,
    ) -> None:
        """Retry menu navigation briefly while lazy-loaded tabs initialize."""
        active_request_id = getattr(self, "_menu_nav_request_id", 0)
        if request_id is not None and request_id != active_request_id:
            return

        if navigate_fn(tab_name):
            return
        if retries <= 0:
            logger.warning("Menu navigation failed for tab: %s", tab_name)
            return
        QTimer.singleShot(
            delay_ms,
            lambda fn=navigate_fn, name=tab_name, r=retries - 1, d=delay_ms: (
                self._deferred_menu_navigation(
                    fn,
                    name,
                    r,
                    d,
                    request_id=request_id,
                )
            ),
        )

    def _open_run_charter_from_main(self, retries: int = 4) -> None:
        """Open Operations > Dispatch, then focus Dispatch's Run Charter sub-tab."""
        if not self.navigate_to_operations_subtab("📡 Dispatch"):
            return

        dispatch_tabs = getattr(self, "dispatch_tabs_widget", None)
        if dispatch_tabs is None:
            if retries > 0:
                QTimer.singleShot(
                    120,
                    lambda r=retries - 1: self._open_run_charter_from_main(r),
                )
            return

        if dispatch_tabs.count() > 1:
            dispatch_tabs.setCurrentIndex(1)

    def _navigate_to_dispatch_subtab(
        self,
        sub_tab_name: str,
        retries: int = 4,
        nav_request_id: int | None = None,
    ) -> bool:
        """Open Operations > Dispatch and focus a Dispatch nested sub-tab."""
        active_request_id = getattr(self, "_menu_nav_request_id", 0)
        if nav_request_id is not None and nav_request_id != active_request_id:
            return False

        if not self.navigate_to_operations_subtab("📡 Dispatch"):
            return False

        dispatch_tabs = getattr(self, "dispatch_tabs_widget", None)
        if dispatch_tabs is None:
            if retries > 0:
                QTimer.singleShot(
                    120,
                    lambda r=retries - 1, s=sub_tab_name, req=nav_request_id: self._navigate_to_dispatch_subtab(
                        s,
                        r,
                        req,
                    ),
                )
            return False

        for i in range(dispatch_tabs.count()):
            if dispatch_tabs.tabText(i) == sub_tab_name:
                if i >= 2:
                    self._on_dispatch_subtab_changed(dispatch_tabs, i)
                dispatch_tabs.setCurrentIndex(i)
                return True
        return False

    def _navigate_to_reports_subtab(
        self,
        sub_tab_name: str,
        retries: int = 4,
        nav_request_id: int | None = None,
    ) -> bool:
        """Open Operations > Reports & PDFs and focus one drill-down report tab."""
        active_request_id = getattr(self, "_menu_nav_request_id", 0)
        if nav_request_id is not None and nav_request_id != active_request_id:
            return False

        if not self.navigate_to_operations_subtab("📊 Reports & PDFs"):
            return False

        report_tabs = getattr(self, "report_tabs_widget", None)
        if report_tabs is None:
            if retries > 0:
                QTimer.singleShot(
                    120,
                    lambda r=retries - 1, s=sub_tab_name, req=nav_request_id: self._navigate_to_reports_subtab(
                        s,
                        r,
                        req,
                    ),
                )
            return False

        for i in range(report_tabs.count()):
            if report_tabs.tabText(i) == sub_tab_name:
                report_tabs.setCurrentIndex(i)
                self._on_report_section_changed(i)
                return True
        return False

    def _navigate_to_fleet_subtab(self, sub_tab_name: str) -> bool:
        if not hasattr(self, "fleet_parent_tabs"):
            return False
        for i in range(self.fleet_parent_tabs.count()):
            if self.fleet_parent_tabs.tabText(i) == sub_tab_name:
                self.fleet_parent_tabs.setCurrentIndex(i)
                self._on_fleet_subtab_changed(self.fleet_parent_tabs, i)
                return True
        return False

    def _navigate_to_fleet_inner_subtab(
        self,
        parent_sub_tab_name: str,
        inner_tab_name: str,
        retries: int = 4,
        nav_request_id: int | None = None,
    ) -> bool:
        """Open Fleet & People > Vehicles/Employees and focus a nested
        drill-down detail tab (e.g. Maintenance, Lease Compliance,
        Training) inside that widget's own tab bar."""
        active_request_id = getattr(self, "_menu_nav_request_id", 0)
        if nav_request_id is not None and nav_request_id != active_request_id:
            return False

        if not self._navigate_to_fleet_subtab(parent_sub_tab_name):
            return False

        inner_widget = None
        if parent_sub_tab_name == "🚐 Vehicles":
            inner_widget = getattr(self, "vehicles_widget", None)
        elif parent_sub_tab_name == "👔 Employees":
            inner_widget = getattr(self, "employees_widget", None)

        inner_tabs = None
        if inner_widget is not None:
            inner_tabs = getattr(inner_widget, "tabs", None) or getattr(
                inner_widget, "form_tabs", None
            )

        if inner_tabs is None:
            if retries > 0:
                QTimer.singleShot(
                    120,
                    lambda r=retries - 1, p=parent_sub_tab_name, t=inner_tab_name, req=nav_request_id: self._navigate_to_fleet_inner_subtab(
                        p,
                        t,
                        r,
                        req,
                    ),
                )
            return False

        for i in range(inner_tabs.count()):
            if inner_tabs.tabText(i) == inner_tab_name:
                inner_tabs.setCurrentIndex(i)
                return True
        return False

    def _navigate_to_admin_subtab(self, sub_tab_name: str) -> bool:
        tabs = getattr(self, "admin_parent_tabs", None)
        if tabs is None:
            return False
        for i in range(tabs.count()):
            if tabs.tabText(i) == sub_tab_name:
                tabs.setCurrentIndex(i)
                self._on_admin_subtab_changed(tabs, i)
                return True
        return False

    def _navigate_to_year_end_subtab(self, sub_tab_name: str) -> bool:
        tabs = getattr(self, "year_end_tabs", None)
        if tabs is None:
            return False
        for i in range(tabs.count()):
            if tabs.tabText(i) == sub_tab_name:
                tabs.setCurrentIndex(i)
                return True
        return False

    def _open_single_section_tab(self, target_tab: str) -> bool:
        """Keep only Main + selected section tab visible/loaded."""
        if target_tab not in self._lazy_tab_factories:
            return False

        # Remove previous active section tab and release widget memory.
        for i in range(self.tabs.count() - 1, -1, -1):
            tab_text = self.tabs.tabText(i)
            if tab_text in self._lazy_tab_factories:
                old_widget = self.tabs.widget(i)
                self.tabs.removeTab(i)
                if old_widget is not None:
                    old_widget.deleteLater()
                self._tabs_loaded.discard(tab_text)
                self._tab_load_in_progress.discard(tab_text)

        placeholder = QLabel(f"Loading {target_tab}...")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        section_index = self.tabs.addTab(placeholder, target_tab)
        self._active_section_tab_text = target_tab
        self.tabs.setCurrentIndex(section_index)
        return True

    def _apply_initial_scope_tab_focus(self) -> None:
        """Always start on Main tab to avoid eager heavy loads on open."""
        self.tabs.setCurrentIndex(0)

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
            self._compact_non_run_charter_tabs(root_widget)
        except Exception as e:
            logger.warning("UI standards apply failed: %s", e)

    def _compact_non_run_charter_tabs(self, root_widget: QWidget) -> None:
        """Tighten tab chrome everywhere while leaving Run Charter alone."""
        try:
            tab_widgets = root_widget.findChildren(QTabWidget)
            for tab_widget in tab_widgets:
                has_run_charter_tab = any(
                    "run charter" in tab_widget.tabText(index).lower()
                    for index in range(tab_widget.count())
                )
                if has_run_charter_tab:
                    continue
                tab_widget.setUsesScrollButtons(False)
                tab_widget.setStyleSheet(
                    "QTabWidget::pane { border: 1px solid #d0d7de; margin-top: 2px; } "
                    "QTabBar::tab { padding: 4px 8px; min-height: 18px; max-height: 22px; "
                    "font-size: 10px; font-weight: bold; } "
                    "QTabBar::tab:selected { background: #eaf3ff; }"
                )
                if tab_widget.minimumHeight() < 220:
                    tab_widget.setMinimumHeight(220)
        except Exception as e:
            logger.debug("Compact desk tab layout skipped: %s", e)

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
            idle_seconds = (
                datetime.now() - self._last_activity
            ).total_seconds()
            self._mark_activity()
            if (
                idle_seconds >= 300
                and hasattr(self, "db_monitor")
                and not self.db_monitor.timer.isActive()
            ):
                self.db_monitor.check_connection()

        # Block scroll wheel from changing value controls anywhere in the app.
        # Page scrolling still works on containers; only direct value widgets
        # are protected.
        if event.type() == QEvent.Type.Wheel and isinstance(
            obj, (QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit, QComboBox)
        ):
            return True  # consume – don't change the control

        # Standardize every dollar-value QDoubleSpinBox to behave like the
        # Add Receipt "Amount" field: select the whole value on focus/click
        # so typing "60" or "31.63" replaces it instead of appending digits
        # onto the existing value (which is what caused 60.00 -> 6000.00 or
        # 31.63 -> 313163.63 style corruption). selectAll() lives on the
        # spin box's internal QLineEdit, not on QDoubleSpinBox itself.
        if (
            event.type() in (QEvent.Type.FocusIn, QEvent.Type.MouseButtonPress)
            and isinstance(obj, QDoubleSpinBox)
        ):
            line_edit = obj.lineEdit()
            if line_edit is not None:
                QTimer.singleShot(0, line_edit.selectAll)

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

        # Keep restore handling non-blocking; status bar already reports
        # recovery without interrupting active data entry workflows.

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
            dialog.setWindowTitle("Enhanced Receipts")
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
            dialog.setWindowTitle("Enhanced Banking")
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
        self.fleet_parent_tabs = tabs

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

        tabs.tabBarClicked.connect(
            lambda idx: self._on_fleet_subtab_changed(tabs, idx)
        )

        QTimer.singleShot(
            0,
            lambda t=tabs: self._on_fleet_subtab_changed(
                t,
                t.currentIndex(),
            ),
        )

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

        # Nested lazy-loading for Accounting grouped sub-tabs.
        self._accounting_subtab_factories = {
            "🎯 Accounting Hub": self.create_accounting_control_center_tab,
            "📆 Month-End Close": self.create_month_end_close_tab,
            "🗓️ Year-End Close": self.create_year_end_close_tab,
            "💰 Receipts & Invoices": (
                lambda: self.create_accounting_tab_with_parent(tabs)
            ),
            "📝 Accountant Notes": self.create_accountant_notes_tab,
            "📋 Vendor Invoices": self.create_vendor_invoice_tab,
            "🧾 Enhanced Receipts": self.create_enhanced_receipts_tab,
            "💳 Payment Linker": self.create_payment_linker_tab,
            "📒 Check Book": self.create_checkbook_management_tab,
            "🏦 Enhanced Banking": self.create_enhanced_banking_tab,
            "🧩 NSF Pairs": self.create_nsf_pair_manager_tab,
            "🏦 Staff Loan Account": self.create_staff_loan_account_tab,
            "💵 Payroll Entry": self.create_payroll_entry_tab,
            "🧮 Payroll Remittances": self.create_payroll_remittances_tab,
            "🏛️ Tax": self.create_tax_management_tab,
            "📋 T2 Corporate Tax": self.create_t2_data_entry_tab,
            "🛡️ WCB Rates": self.create_wcb_rates_tab,
            "🧪 Audit": self.create_audit_management_tab,
            "🏢 Business Entity": self.create_business_entity_tab,
            "📦 Asset Inventory": lambda: AssetManagementWidget(),
            "📊 Financial Reports": self.create_reports_tab,
            "🍷 Beverage Revenue": self.create_beverage_accounting_tab,
            "🍷 Beverage": self.create_beverage_management_tab,
        }
        self._accounting_subtab_aliases = {
            "🧪 Audit Management": "🧪 Audit",
            "📒 Check Book Management": "📒 Check Book",
            "🏦 Enhanced Banking Manager": "🏦 Enhanced Banking",
            "🧩 NSF Pair Manager": "🧩 NSF Pairs",
            "🧾 Enhanced Receipts Manager": "🧾 Enhanced Receipts",
            "📋 Vendor Invoice Manager": "📋 Vendor Invoices",
            "🏛️ Tax Management": "🏛️ Tax",
            "🍷 Beverage Management": "🍷 Beverage",
        }

        self._accounting_group_layout = {
            "📅 Close Management": [
                "📆 Month-End Close",
                "🗓️ Year-End Close",
            ],
            "🗂️ Daily Work": [
                "🎯 Accounting Hub",
                "💰 Receipts & Invoices",
                "📝 Accountant Notes",
                "📋 Vendor Invoices",
                "🧾 Enhanced Receipts",
                "💳 Payment Linker",
            ],
            "🏦 Banking & Cash": [
                "📒 Check Book",
                "🏦 Enhanced Banking",
                "🧩 NSF Pairs",
                "🏦 Staff Loan Account",
            ],
            "👔 Payroll & Tax": [
                "💵 Payroll Entry",
                "🧮 Payroll Remittances",
                "🏛️ Tax",
                "📋 T2 Corporate Tax",
                "🛡️ WCB Rates",
            ],
            "📊 Compliance & Reports": [
                "🧪 Audit",
                "🏢 Business Entity",
                "📦 Asset Inventory",
                "📊 Financial Reports",
                "🍷 Beverage Revenue",
                "🍷 Beverage",
            ],
        }
        self._accounting_subtab_to_group = {}
        self._accounting_group_tabs = {}
        self._accounting_subtabs_loaded = set()
        self._accounting_subtabs_in_progress = set()

        for group_name, sub_tabs in self._accounting_group_layout.items():
            group_tabs = QTabWidget()
            self._accounting_group_tabs[group_name] = group_tabs
            for sub_tab_name in sub_tabs:
                self._accounting_subtab_to_group[sub_tab_name] = group_name
                placeholder = QLabel(f"Loading {sub_tab_name}...")
                placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                group_tabs.addTab(placeholder, sub_tab_name)
            group_tabs.tabBarClicked.connect(
                lambda idx, t=group_tabs: self._on_accounting_subtab_changed(t, idx)
            )
            QTimer.singleShot(
                0,
                lambda t=group_tabs: self._on_accounting_subtab_changed(
                    t,
                    t.currentIndex(),
                ),
            )
            tabs.addTab(group_tabs, group_name)

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
        self.admin_parent_tabs = tabs

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

        # Also load when the same tab is clicked (currentChanged won't fire).
        tabs.tabBarClicked.connect(
            lambda idx: self._on_admin_subtab_changed(tabs, idx)
        )

        QTimer.singleShot(
            0,
            lambda t=tabs: self._on_admin_subtab_changed(
                t,
                t.currentIndex(),
            ),
        )

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
        """Consolidated Operations with lazy-loaded sub-tabs."""

        parent = QWidget()
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        self.operations_tabs = tabs

        self._operations_subtab_factories = {
            "📡 Dispatch": self.create_dispatch_tab,
            "🍷 Beverage": self.create_beverage_management_tab,
            "👥 Customers": self.create_customers_tab,
            "💳 Client Payments": (
                self.create_client_payment_management_tab
            ),
            "📄 Documents": self.create_documents_tab,
            "✅ Close Control Center": self.create_close_control_center_tab,
            "📊 Reports & PDFs": lambda: ReportManagementWidget(self.db),
        }
        self._operations_subtabs_loaded = set()
        self._operations_subtabs_in_progress = set()

        for sub_tab_name in self._operations_subtab_factories:
            placeholder = QLabel(f"Loading {sub_tab_name}...")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tabs.addTab(placeholder, sub_tab_name)

        tabs.tabBarClicked.connect(
            lambda idx: self._on_operations_subtab_changed(tabs, idx)
        )

        self.dispatch_tab_index = 0
        self.booking_tab_index = 0

        QTimer.singleShot(
            0,
            lambda t=tabs: self._on_operations_subtab_changed(
                t,
                t.currentIndex(),
            ),
        )

        layout.addWidget(tabs)
        return parent

    def _on_operations_subtab_changed(self, tabs: QTabWidget, index: int) -> None:
        """Load Operations sub-tab content on first access."""
        if index < 0:
            return

        tab_text = tabs.tabText(index)
        if tab_text not in self._operations_subtab_factories:
            return

        if (
            tab_text in self._operations_subtabs_loaded
            or tab_text in self._operations_subtabs_in_progress
        ):
            return

        self._operations_subtabs_in_progress.add(tab_text)
        tabs.blockSignals(True)
        try:
            real_widget = self._operations_subtab_factories[tab_text]()
            tabs.removeTab(index)
            tabs.insertTab(index, real_widget, tab_text)
            tabs.setCurrentIndex(index)
            self._apply_global_ui_standards(real_widget)
            self._operations_subtabs_loaded.add(tab_text)
        except Exception as e:
            logger.exception("Failed to load operations sub-tab %s", tab_text)
            error_widget = QLabel(f"Error loading {tab_text}:\n{e!s}")
            error_widget.setStyleSheet("color: red; padding: 20px;")
            error_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tabs.removeTab(index)
            tabs.insertTab(index, error_widget, tab_text)
            tabs.setCurrentIndex(index)
            self._operations_subtabs_loaded.add(tab_text)
        finally:
            tabs.blockSignals(False)
            self._operations_subtabs_in_progress.discard(tab_text)

    def create_close_control_center_tab(self) -> QWidget:
        """Operations control checks for daily/month-end close readiness."""
        from close_control_center_widget import CloseControlCenterWidget

        self.close_control_center_widget = CloseControlCenterWidget(self.db)
        return self.close_control_center_widget

    def create_charter_tab(self) -> QWidget:
        """Charter/booking management tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        self.charter_form = CharterFormWidget(self.db)
        self._ensure_payroll_refresh_hook()
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

    def create_client_payment_management_tab(self) -> QWidget:
        """Client payment workflow tab with direct access to payments."""
        from enhanced_client_widget import EnhancedClientListWidget

        return EnhancedClientListWidget(self.db, payment_mode=True)

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
        self._apply_year_scope_to_widget(self.payroll_entry_widget)
        self._ensure_payroll_refresh_hook()
        layout.addWidget(self.payroll_entry_widget)
        widget.setLayout(layout)
        return widget

    def _apply_year_scope_to_widget(self, widget) -> None:
        """Apply selected startup year scope to compatible widgets."""
        try:
            _start_year, end_year = self.get_working_year_scope()

            if hasattr(widget, "year_spin"):
                widget.year_spin.setValue(int(end_year))

            if hasattr(widget, "year_combo"):
                year_text = str(int(end_year))
                idx = widget.year_combo.findText(year_text)
                if idx >= 0:
                    widget.year_combo.setCurrentIndex(idx)
        except Exception as exc:
            logger.debug("Suppressed year scope apply error: %s", exc)

    def _ensure_payroll_refresh_hook(self) -> None:
        """Connect charter saves to payroll refresh once."""

        if getattr(self, "_charter_payroll_refresh_connected", False):
            return
        if not hasattr(self, "charter_form"):
            return

        self.charter_form.saved.connect(self._refresh_payroll_views_from_charter)
        self._charter_payroll_refresh_connected = True

    def _refresh_payroll_views_from_charter(self, *_args) -> None:
        """Refresh payroll views after charter edits change approved hours or gratuity."""

        widget = getattr(self, "payroll_entry_widget", None)
        if not widget:
            return

        try:
            widget._load_pay_printout()
        except Exception as exc:
            logger.debug("Suppressed payroll printout refresh after charter save: %s", exc)

        for refresh_name in (
            "_load_monthly_remittance_summary",
            "_refresh_pay_ledger",
            "_load_ytd_totals",
        ):
            refresh = getattr(widget, refresh_name, None)
            if callable(refresh):
                try:
                    refresh()
                except Exception as exc:
                    logger.debug("Suppressed payroll refresh %s after charter save: %s", refresh_name, exc)

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
            "👷 Staff Work Schedule": self._create_employee_work_schedule_subtab,
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
            lambda idx: self._on_dispatch_tab_changed(dispatch_tabs, idx)
        )
        dispatch_tabs.setCurrentIndex(0)

        layout.addWidget(dispatch_tabs)
        widget.setLayout(layout)
        return widget

    def _on_dispatch_tab_changed(self, tabs: QTabWidget, index: int) -> None:
        """Keep dispatch board fresh and lazy-load secondary sub-tabs."""
        if index == 0 and hasattr(self, "dispatch_widget"):
            try:
                self.dispatch_widget._trigger_load()
            except Exception as e:
                logger.debug("Dispatch board refresh on tab switch skipped: %s", e)
        self._on_dispatch_subtab_changed(tabs, index)

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

    def _create_employee_work_schedule_subtab(self) -> QWidget:
        from employee_work_schedule_widget import EmployeeWorkScheduleWidget

        self.employee_work_schedule_widget = EmployeeWorkScheduleWidget(self.db)
        return self.employee_work_schedule_widget

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

    def create_payment_linker_tab(self) -> QWidget:
        """Payment Linker - manual assignment of orphaned payments to charters."""
        from payment_linker_widget import PaymentLinkerWidget
        return PaymentLinkerWidget(self.db)

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

    def create_audit_management_tab(self) -> QWidget:
        """Centralized audit findings + resolutions for CRA/payroll/banking."""
        from audit_management_widget import AuditManagementWidget

        widget = QWidget()
        layout = QVBoxLayout()
        self.audit_management_widget = AuditManagementWidget(
            self.db,
            auth_user=getattr(self, "auth_user", {}),
        )
        layout.addWidget(self.audit_management_widget)
        widget.setLayout(layout)
        return widget

    def create_staff_loan_account_tab(self) -> QWidget:
        """Unified non-owner staff loan ledger and balance-forward workflow."""
        from staff_loan_account_widget import StaffLoanAccountWidget

        widget = QWidget()
        layout = QVBoxLayout()
        self.staff_loan_account_widget = StaffLoanAccountWidget(
            self.db,
            auth_user=getattr(self, "auth_user", {}),
        )
        layout.addWidget(self.staff_loan_account_widget)
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
        """Business entity overview - overall company view"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Add button to open business entity dialog
        header = QLabel("<h2>🏢 Business Entity</h2>")
        layout.addWidget(header)

        info_label = QLabel("""
        <p>Configure Arrow Limousine as a business entity:</p>
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

        open_btn = QPushButton("🏢 Open Business Entity Dashboard")
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
        widget = AccountingControlCenterWidget(self.db)
        self._apply_year_scope_to_widget(widget)
        return widget

    def create_month_end_close_tab(self) -> QWidget:
        """Create the persistent month-end close management checklist."""
        from period_close_management_widget import PeriodCloseManagementWidget

        self.month_end_close_widget = PeriodCloseManagementWidget(
            self.db,
            "month",
            main_window=self,
        )
        return self.month_end_close_widget

    def create_year_end_close_tab(self) -> QWidget:
        """Create the persistent year-end close management checklist."""
        from period_close_management_widget import PeriodCloseManagementWidget

        self.year_end_close_widget = PeriodCloseManagementWidget(
            self.db,
            "year",
            main_window=self,
        )
        return self.year_end_close_widget

    def create_year_end_audit_tab(self) -> QWidget:
        """Year-end hub: Guided Wizard + legacy Audit Checks."""
        try:
            from PyQt6.QtWidgets import QTabWidget
            tabs = QTabWidget()
            self.year_end_tabs = tabs

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
        """Create Enhanced Banking tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        try:
            banking_manager = EnhancedBankingManager(self.db, widget)
            self.enhanced_banking_manager = banking_manager
            layout.addWidget(banking_manager)
        except Exception as e:
            error_label = QLabel(
                f"❌ Error loading Enhanced Banking:\n{e!s}"
            )
            error_label.setStyleSheet("color: red; padding: 20px;")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)
            logger.warning(f"Error creating Enhanced Banking tab: {e}")

        widget.setLayout(layout)
        return widget

    def create_nsf_pair_manager_tab(self) -> QWidget:
        """Create NSF Pairs tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        try:
            nsf_manager = NsfPairManagerWidget(self.db, widget)
            layout.addWidget(nsf_manager)
        except Exception as e:
            error_label = QLabel(f"Error loading NSF Pairs:\n{e!s}")
            error_label.setStyleSheet("color: red; padding: 20px;")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)
            logger.warning(f"Error creating NSF Pairs tab: {e}")

        widget.setLayout(layout)
        return widget

    def navigate_to_top_tab(self, top_tab_name: str) -> bool:
        """Programmatically focus a top-level tab by text."""
        if not hasattr(self, "tabs"):
            return False
        legacy_top_tab_aliases = {
            "🚗 Fleet Management": "🚗 Fleet & People",
        }
        top_tab_name = legacy_top_tab_aliases.get(top_tab_name, top_tab_name)

        has_existing_tab = False
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == top_tab_name:
                has_existing_tab = True
                break

        if top_tab_name in self._lazy_tab_factories and not has_existing_tab:
            self._open_single_section_tab(top_tab_name)

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

        canonical_name = getattr(self, "_accounting_subtab_aliases", {}).get(
            sub_tab_name,
            sub_tab_name,
        )
        group_name = getattr(self, "_accounting_subtab_to_group", {}).get(canonical_name)
        if not group_name:
            return False

        group_tabs = getattr(self, "_accounting_group_tabs", {}).get(group_name)
        if group_tabs is None:
            return False

        for group_idx in range(self.accounting_parent_tabs.count()):
            if self.accounting_parent_tabs.tabText(group_idx) == group_name:
                self.accounting_parent_tabs.setCurrentIndex(group_idx)
                break
        else:
            return False

        for sub_idx in range(group_tabs.count()):
            if group_tabs.tabText(sub_idx) == canonical_name:
                group_tabs.setCurrentIndex(sub_idx)
                self._on_accounting_subtab_changed(group_tabs, sub_idx)
                return True
        return False

    def navigate_to_fleet_subtab(self, sub_tab_name: str) -> bool:
        """Focus Fleet & People, then a specific fleet sub-tab."""
        if not self.navigate_to_top_tab("🚗 Fleet & People"):
            return False
        if not hasattr(self, "fleet_parent_tabs"):
            return False
        for index in range(self.fleet_parent_tabs.count()):
            if self.fleet_parent_tabs.tabText(index) == sub_tab_name:
                self.fleet_parent_tabs.setCurrentIndex(index)
                self._on_fleet_subtab_changed(self.fleet_parent_tabs, index)
                return True
        return False

    def navigate_to_operations_subtab(self, sub_tab_name: str) -> bool:
        """Focus Operations top tab, then a specific Operations sub-tab."""
        if not self.navigate_to_top_tab("🚀 Operations"):
            return False
        if not hasattr(self, "operations_tabs"):
            return False
        legacy_operation_aliases = {
            "💳 Client Payment Management": "💳 Client Payments",
        }
        sub_tab_name = legacy_operation_aliases.get(sub_tab_name, sub_tab_name)
        for i in range(self.operations_tabs.count()):
            if self.operations_tabs.tabText(i) == sub_tab_name:
                self.operations_tabs.setCurrentIndex(i)
                self._on_operations_subtab_changed(self.operations_tabs, i)
                return True
        return False

    def create_enhanced_receipts_tab(self) -> QWidget:
        """Create Enhanced Receipts tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        try:
            receipts_manager = EnhancedReceiptsManager(self.db, widget)
            layout.addWidget(receipts_manager)
        except Exception as e:
            error_label = QLabel(
                f"❌ Error loading Enhanced Receipts:\n{e!s}"
            )
            error_label.setStyleSheet("color: red; padding: 20px;")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)
            logger.warning(f"Error creating Enhanced Receipts tab: {e}")

        widget.setLayout(layout)
        return widget

    def create_reports_tab(self) -> QWidget:
        """Reports & analytics tab with Phase 1, 2, 3 dashboards"""
        import importlib

        report_modules = (
            "dashboard_classes",
            "dashboards_phase2_phase3",
            "dashboards_phase4_5_6",
            "dashboards_phase7_8",
            "dashboards_phase9",
            "dashboards_phase10",
            "dashboards_phase11",
            "dashboards_phase12",
            "dashboards_phase13",
            "dashboards_phase14",
            "dashboards_phase15",
        )
        for module_name in report_modules:
            module = importlib.import_module(module_name)
            for class_name in dir(module):
                if class_name.endswith("Widget"):
                    globals().setdefault(class_name, getattr(module, class_name))

        widget = QWidget()
        layout = QVBoxLayout()

        report_tabs = QTabWidget()
        self.report_tabs_widget = report_tabs
        self._report_section_factories = self._report_section_factory_map()
        self._build_reports_tab_body(widget, layout, report_tabs)
        return widget

    def _report_section_factory_map(self) -> dict:
        """Ordered map of every Reports & PDFs drill-down tab name -> factory.

        Kept as a single source of truth so the mega-menu navigation
        structure (`_main_navigation_structure`) can list the same names
        without instantiating any widgets.
        """
        return {
            "🔎 Drill-Down Reports": lambda: __import__(
                "reports_widget", fromlist=["DrillDownReportWidget"]
            ).DrillDownReportWidget(self.db),
            "🚐 Fleet Operations": lambda: FleetManagementWidget(self.db),
            "👤 Driver Performance": lambda: DriverPerformanceWidget(self.db),
            "📈 Financial Reports": lambda: FinancialDashboardWidget(self.db),
            "💳 Payment Reconciliation": lambda: PaymentReconciliationWidget(self.db),
            "🚗 Vehicle Analytics": lambda: VehicleAnalyticsWidget(self.db),
            "👔 Payroll Audit": lambda: EmployeePayrollAuditWidget(self.db),
            "📊 QB Reconciliation": lambda: QuickBooksReconciliationWidget(self.db),
            "📈 Charter Analytics": lambda: CharterAnalyticsWidget(self.db),
            "✅ Compliance": lambda: ComplianceTrackingWidget(self.db),
            "💰 Budget vs Actual": lambda: BudgetAnalysisWidget(self.db),
            "🛡️ Insurance": lambda: InsuranceTrackingWidget(self.db),
            "🚗 Fleet Cost Analysis": lambda: VehicleFleetCostAnalysisWidget(self.db),
            "🔧 Maintenance Tracking": lambda: VehicleMaintenanceTrackingWidget(self.db),
            "⛽ Fuel Efficiency": lambda: FuelEfficiencyTrackingWidget(self.db),
            "📊 Vehicle Utilization": lambda: VehicleUtilizationWidget(self.db),
            "📈 Fleet Age Analysis": lambda: FleetAgeAnalysisWidget(self.db),
            "💰 Driver Pay Analysis": lambda: DriverPayAnalysisWidget(self.db),
            "⭐ Performance Metrics": lambda: EmployeePerformanceMetricsWidget(self.db),
            "📋 Tax Compliance": lambda: PayrollTaxComplianceWidget(self.db),
            "📅 Driver Schedule": lambda: DriverScheduleManagementWidget(self.db),
            "💳 Payments (Advanced)": lambda: PaymentReconciliationAdvancedWidget(self.db),
            "📊 AR Aging": lambda: ARAgingDashboardWidget(self.db),
            "💸 Cash Flow": lambda: CashFlowReportWidget(self.db),
            "📊 Profit & Loss": lambda: ProfitLossReportWidget(self.db),
            "📉 Operating Breakdown": lambda: __import__(
                "accounting_reports", fromlist=["WeeklyOperatingDashboardWidget"]
            ).WeeklyOperatingDashboardWidget(self.db),
            "📈 Charter Analytics+": lambda: CharterAnalyticsAdvancedWidget(self.db),
            "📅 Charter Ops": lambda: CharterManagementDashboardWidget(self.db),
            "💰 Customer LTV": lambda: CustomerLifetimeValueWidget(self.db),
            "📊 Cancellation Analysis": lambda: CharterCancellationAnalysisWidget(self.db),
            "⏱️ Lead Time": lambda: BookingLeadTimeAnalysisWidget(self.db),
            "🎯 Segmentation": lambda: CustomerSegmentationWidget(self.db),
            "🛣️ Route Profitability": lambda: RouteProfitabilityWidget(self.db),
            "🗺️ Geographic Revenue": lambda: GeographicRevenueDistributionWidget(self.db),
            "⚖️ HOS Compliance": lambda: HosComplianceTrackingWidget(self.db),
            "🔧 Maintenance (Advanced)": lambda: AdvancedMaintenanceScheduleWidget(self.db),
            "⚠️ Safety Incidents": lambda: SafetyIncidentTrackingWidget(self.db),
            "🤝 Vendor Performance": lambda: VendorPerformanceWidget(self.db),
            "📡 Fleet Monitoring": lambda: RealTimeFleetMonitoringWidget(self.db),
            "🏥 System Health": lambda: SystemHealthDashboardWidget(self.db),
            "📋 Data Quality": lambda: DataQualityAuditWidget(self.db),
            "📈 Demand Forecasting": lambda: DemandForecastingWidget(self.db),
            "⚠️ Churn Prediction": lambda: ChurnPredictionWidget(self.db),
            "💰 Revenue Optimization": lambda: RevenueOptimizationWidget(self.db),
            "⭐ Customer Worth (RFM)": lambda: CustomerWorthWidget(self.db),
            "🎯 Next Best Action": lambda: NextBestActionWidget(self.db),
            "📊 Seasonality": lambda: SeasonalityAnalysisWidget(self.db),
            "💡 Cost Behavior": lambda: CostBehaviorAnalysisWidget(self.db),
            "📊 Break-Even": lambda: BreakEvenAnalysisWidget(self.db),
            "📧 Email Campaigns": lambda: EmailCampaignPerformanceWidget(self.db),
            "🛣️ Customer Journey": lambda: CustomerJourneyAnalysisWidget(self.db),
            "🎯 Competitive Intel": lambda: CompetitiveIntelligenceWidget(self.db),
            "⚖️ Regulatory Compliance": lambda: RegulatoryComplianceTrackingWidget(self.db),
            "📋 CRA Compliance": lambda: CRAComplianceReportWidget(self.db),
            "👥 Employee Productivity": lambda: EmployeeProductivityTrackingWidget(self.db),
            "🎁 Promotional Effectiveness": lambda: PromotionalEffectivenessWidget(self.db),
            "🗺️ Fleet Tracking Map": lambda: RealTimeFleetTrackingMapWidget(self.db),
            "📡 Live Dispatch": lambda: LiveDispatchMonitorWidget(self.db),
            "📱 Mobile Portal": lambda: MobileCustomerPortalWidget(self.db),
            "🚗 Mobile Driver": lambda: MobileDriverDashboardWidget(self.db),
            "⚙️ API Performance": lambda: APIEndpointPerformanceWidget(self.db),
            "🔗 Integrations": lambda: ThirdPartyIntegrationMonitorWidget(self.db),
            "📊 Time Series": lambda: AdvancedTimeSeriesChartWidget(self.db),
            "🔥 Heatmap": lambda: InteractiveHeatmapWidget(self.db),
            "🔄 Comparative Analysis": lambda: ComparativeAnalysisChartWidget(self.db),
            "📈 Distribution": lambda: DistributionAnalysisChartWidget(self.db),
            "🔗 Correlation Matrix": lambda: CorrelationMatrixWidget(self.db),
            "⚡ Automation": lambda: AutomationWorkflowsWidget(self.db),
            "🔔 Alerts": lambda: AlertManagementWidget(self.db),
            "📅 Shift Optimization": lambda: DriverShiftOptimizationWidget(self.db),
            "🛣️ Route Scheduling": lambda: RouteSchedulingWidget(self.db),
            "🚗 Vehicle Assignment": lambda: VehicleAssignmentPlannerWidget(self.db),
            "📆 Calendar Forecast": lambda: CalendarForecasitngWidget(self.db),
            "⏰ Break Compliance": lambda: BreakComplianceScheduleWidget(self.db),
            "🔧 Maintenance Sched": lambda: MaintenanceSchedulingWidget(self.db),
            "👥 Crew Rotation": lambda: CrewRotationAnalysisWidget(self.db),
            "⚖️ Load Balancing": lambda: LoadBalancingOptimizerWidget(self.db),
            "💰 Dynamic Pricing": lambda: DynamicPricingScheduleWidget(self.db),
            "📊 Historical Patterns": lambda: HistoricalSchedulingPatternsWidget(self.db),
            "🤖 Predictive Schedule": lambda: PredictiveSchedulingWidget(self.db),
            "📦 Capacity Planning": lambda: CapacityUtilizationWidget(self.db),
            "🏢 Branch Consolidation": lambda: BranchLocationConsolidationWidget(self.db),
            "📊 Inter-Branch Comparison": lambda: InterBranchPerformanceComparisonWidget(self.db),
            "💰 Consolidated P&L": lambda: ConsolidatedProfitLossWidget(self.db),
            "🔄 Resource Allocation": lambda: ResourceAllocationAcrossPropertiesWidget(self.db),
            "🚐 Cross-Branch": lambda: CrossBranchCharteringWidget(self.db),
            "🚗 Shared Vehicles": lambda: SharedVehicleTrackingWidget(self.db),
            "📦 Unified Inventory": lambda: UnifiedInventoryManagementWidget(self.db),
            "💳 Multi-Location Payroll": lambda: MultiLocationPayrollWidget(self.db),
            "🗺️ Territory Mapping": lambda: TerritoryMappingWidget(self.db),
            "📊 Market Overlap": lambda: MarketOverlapAnalysisWidget(self.db),
            "📈 Regional Performance": lambda: RegionalPerformanceMetricsWidget(self.db),
            "📊 Property KPIs": lambda: PropertyLevelKPIWidget(self.db),
            "🏢 Franchise Integration": lambda: FranchiseIntegrationWidget(self.db),
            "📜 License Tracking": lambda: LicenseTrackingWidget(self.db),
            "⚙️ Operations Consolidation": lambda: OperationsConsolidationWidget(self.db),
            "📱 Self-Service Booking": lambda: SelfServiceBookingPortalWidget(self.db),
            "📜 Trip History": lambda: TripHistoryWidget(self.db),
            "📄 Invoices": lambda: InvoiceReceiptManagementWidget(self.db),
            "⚙️ Account Settings": lambda: AccountSettingsWidget(self.db),
            "🎁 Loyalty Program": lambda: LoyaltyProgramTrackingWidget(self.db),
            "👥 Referral Analytics": lambda: ReferralAnalyticsWidget(self.db),
            "🔄 Subscriptions": lambda: SubscriptionManagementWidget(self.db),
            "🏢 Corporate Accounts": lambda: CorporateAccountManagementWidget(self.db),
            "📅 Recurring Bookings": lambda: RecurringBookingManagementWidget(self.db),
            "💬 Customer Chat": lambda: ChatIntegrationWidget(self.db),
            "🎫 Support Tickets": lambda: SupportTicketManagementWidget(self.db),
            "⭐ Ratings & Reviews": lambda: RatingReviewManagementWidget(self.db),
            "❤️ Saved Preferences": lambda: SavedPreferencesWidget(self.db),
            "🚗 Fleet Preferences": lambda: FleetPreferencesWidget(self.db),
            "👤 Driver Feedback": lambda: DriverFeedbackWidget(self.db),
            "📧 Communications": lambda: CustomerCommunicationsWidget(self.db),
            "🛠️ Custom Reports": lambda: CustomReportBuilderWidget(self.db),
            "👔 Executive Dashboard": lambda: ExecutiveDashboardWidget(self.db),
            "💵 Budget vs Actual": lambda: BudgetVsActualWidget(self.db),
            "📊 Trend Analysis": lambda: TrendAnalysisWidget(self.db),
            "🚨 Anomaly Detection": lambda: AnomalyDetectionWidget(self.db),
            "📍 Segmentation Analysis": lambda: SegmentationAnalysisWidget(self.db),
            "⚔️ Competitive Analysis": lambda: CompetitiveAnalysisWidget(self.db),
            "📈 Operational Metrics": lambda: OperationalMetricsWidget(self.db),
            "✅ Data Quality": lambda: DataQualityReportWidget(self.db),
            "💰 ROI Analysis": lambda: ROIAnalysisWidget(self.db),
            "🔮 Forecasting": lambda: ForecastingWidget(self.db),
            "📅 Report Scheduler": lambda: ReportSchedulerWidget(self.db),
            "📋 Compliance Reporting": lambda: ComplianceReportingWidget(self.db),
            "💾 Exports": lambda: ExportManagementWidget(self.db),
            "🔐 Audit Trail": lambda: AuditTrailWidget(self.db),
            "🤖 Demand Forecasting ML": lambda: DemandForecastingMLWidget(self.db),
            "⚠️ Churn Prediction ML": lambda: ChurnPredictionMLWidget(self.db),
            "💲 Pricing Optimization ML": lambda: PricingOptimizationMLWidget(self.db),
            "👥 Customer Clustering ML": lambda: CustomerClusteringMLWidget(self.db),
            "🚨 Anomaly Detection ML": lambda: AnomalyDetectionMLWidget(self.db),
            "🎯 Recommendation Engine ML": lambda: RecommendationEngineWidget(self.db),
            "⚡ Resource Optimization ML": lambda: ResourceOptimizationMLWidget(self.db),
            "📢 Marketing Optimization ML": lambda: MarketingMLWidget(self.db),
            "📊 Model Performance": lambda: ModelPerformanceWidget(self.db),
            "🔧 Predictive Maintenance ML": lambda: PredictiveMaintenanceMLWidget(self.db),
        }

    def _build_reports_tab_body(
        self, widget: QWidget, layout: QVBoxLayout, report_tabs: QTabWidget
    ) -> None:
        """Populate the Reports & PDFs tab with lazy-loaded drill-down sections."""
        self._report_sections_loaded = set()
        self._report_sections_in_progress = set()

        for tab_name in self._report_section_factories:
            placeholder = QLabel(f"Loading {tab_name}...")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            report_tabs.addTab(placeholder, tab_name)

        report_tabs.currentChanged.connect(self._on_report_section_changed)
        report_tabs.tabBarClicked.connect(self._on_report_section_changed)
        QTimer.singleShot(0, lambda: self._on_report_section_changed(0))

        layout.addWidget(report_tabs)
        widget.setLayout(layout)

    def _on_report_section_changed(self, index: int) -> None:
        """Create report sub-tabs on demand to avoid heavy startup loads."""
        if index < 0:
            return

        report_tabs = self.sender()
        if report_tabs is None:
            return

        tab_text = report_tabs.tabText(index)
        if tab_text not in self._report_section_factories:
            return
        if (
            tab_text in self._report_sections_loaded
            or tab_text in self._report_sections_in_progress
        ):
            return

        self._report_sections_in_progress.add(tab_text)
        report_tabs.blockSignals(True)
        try:
            widget = self._report_section_factories[tab_text]()
            report_tabs.removeTab(index)
            report_tabs.insertTab(index, widget, tab_text)
            report_tabs.setCurrentIndex(index)
            self._report_sections_loaded.add(tab_text)
        except Exception as e:
            logger.exception("Failed to load Reports section %s", tab_text)
            error_widget = QLabel(f"Error loading {tab_text}:\n{e!s}")
            error_widget.setStyleSheet("color: red; padding: 20px;")
            error_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            report_tabs.removeTab(index)
            report_tabs.insertTab(index, error_widget, tab_text)
            report_tabs.setCurrentIndex(index)
            self._report_sections_loaded.add(tab_text)
        finally:
            report_tabs.blockSignals(False)
            self._report_sections_in_progress.discard(tab_text)

    def create_settings_tab(self) -> QWidget:
        """Settings tab (stub)"""
        widget = QWidget()
        layout = QVBoxLayout()

        app_version = "1.0.0"
        try:
            version_path = os.path.join(project_root, "version.txt")
            if os.path.exists(version_path):
                with open(version_path, encoding="utf-8") as vf:
                    app_version = vf.read().strip() or app_version
        except Exception as e:
            logger.warning("Failed to read version.txt for settings tab: %s", e)

        info = QLabel(f"""
        <h3>Arrow Limousine Desktop System</h3>
        <p><b>Version:</b> {app_version} (Desktop)</p>
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
                SELECT receipt_id, receipt_date, vendor_name,
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

            nav_targets = self._search_navigation_targets(query)
            auto_target = self._find_exact_navigation_target(query, nav_targets)
            if auto_target:
                self._open_full_menu_path(
                    auto_target["domain"],
                    tuple(auto_target["path_parts"]),
                )
                self.status_bar.showMessage(
                    f"Opened: {auto_target['path_text']}",
                    6000,
                )
                return

            self._show_global_results(
                query,
                receipts,
                charters,
                clients,
                nav_targets,
            )
        except Exception as e:
            try:
                self.db.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.critical(self, "Search Failed", f"Search error: {e}")

    def _normalize_search_text(self, text: str) -> str:
        """Normalize labels/text so fuzzy search handles emoji and punctuation."""
        cleaned = unicodedata.normalize("NFKD", str(text or ""))
        cleaned = "".join(ch for ch in cleaned if not unicodedata.combining(ch))
        cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", cleaned).strip().lower()
        return cleaned

    def _navigation_search_aliases(self) -> dict[str, list[str]]:
        """Aliases so users can find sections using plain language terms."""
        return {
            "year_end": ["year end", "year-end", "audit", "wizard"],
            "accounting": ["finance", "receipt", "invoice", "tax"],
            "operations": ["booking", "dispatch", "calendar", "charter"],
            "fleet": ["vehicles", "employees", "fleet"],
            "admin": ["settings", "table browser", "admin"],
        }

    def _score_navigation_target(
        self,
        blob_norm: str,
        leaf_norm: str,
        q_norm: str,
        query_tokens: list[str],
    ) -> int:
        """Compute relevance score for one navigation target."""
        score = 0
        if q_norm in blob_norm:
            score += 200
        for token in query_tokens:
            if token in blob_norm:
                score += 30
        if score == 0:
            return 0
        if blob_norm.startswith(q_norm):
            score += 40
        if leaf_norm.startswith(q_norm):
            score += 25
        return score

    def _build_navigation_search_rows(
        self,
        domain_key: str,
        domain_label: str,
        path_parts_list: list[list[str]],
        aliases: list[str],
        q_norm: str,
        query_tokens: list[str],
    ) -> list[dict]:
        """Build scored rows for all paths in one menu domain."""
        rows = []
        for path_parts in path_parts_list:
            path_text = " > ".join([domain_label, *path_parts])
            blob_norm = self._normalize_search_text(
                " ".join([domain_label, *path_parts, *aliases])
            )
            leaf_norm = self._normalize_search_text(path_parts[-1])
            score = self._score_navigation_target(
                blob_norm,
                leaf_norm,
                q_norm,
                query_tokens,
            )
            if score <= 0:
                continue
            rows.append(
                {
                    "domain": domain_key,
                    "path_parts": path_parts,
                    "path_text": path_text,
                    "score": score,
                }
            )
        return rows

    def _search_navigation_targets(self, query: str) -> list[dict]:
        """Search the Main launcher menu targets and rank likely destinations."""
        q_norm = self._normalize_search_text(query)
        if not q_norm:
            return []

        query_tokens = [tok for tok in q_norm.split(" ") if tok]
        if not query_tokens:
            return []

        structure = self._main_navigation_structure()
        aliases_by_domain = self._navigation_search_aliases()
        candidates = []

        for domain_key, domain_meta in structure.items():
            domain_label = str(domain_meta.get("label", domain_key))
            aliases = aliases_by_domain.get(domain_key, [])
            path_parts_list = self._collect_full_menu_targets(
                domain_key,
                domain_meta.get("subtabs", {}),
                [],
            )
            candidates.extend(
                self._build_navigation_search_rows(
                    domain_key,
                    domain_label,
                    path_parts_list,
                    aliases,
                    q_norm,
                    query_tokens,
                )
            )

        candidates.sort(key=lambda row: (-row["score"], len(row["path_parts"]), row["path_text"]))
        return candidates[:30]

    def _find_exact_navigation_target(self, query: str, nav_targets: list[dict]) -> dict | None:
        """Open directly when query is clearly an exact section target."""
        q_norm = self._normalize_search_text(query)
        q_norm = re.sub(r"^(open|go|goto|launch)\s+", "", q_norm).strip()
        if not q_norm:
            return None

        for target in nav_targets:
            leaf = self._normalize_search_text(target["path_parts"][-1])
            full = self._normalize_search_text(target["path_text"])
            if q_norm == leaf or q_norm == full:
                return target
        return None

    def _open_section_target(self, target: dict) -> None:
        """Open a navigation search target."""
        self._open_full_menu_path(
            target["domain"],
            tuple(target["path_parts"]),
        )

    def _build_sections_results_widget(self, dialog: QDialog, nav_targets) -> QWidget:
        """Build sections results tab with open-on-double-click behavior."""
        sections_table = QTableWidget()
        sections_table.setColumnCount(2)
        sections_table.setHorizontalHeaderLabels(["Section", "Open"])
        sections_table.setRowCount(len(nav_targets))
        for idx, target in enumerate(nav_targets):
            section_item = QTableWidgetItem(str(target["path_text"]))
            section_item.setFlags(
                section_item.flags() & ~Qt.ItemFlag.ItemIsEditable
            )
            section_item.setData(Qt.ItemDataRole.UserRole, target)
            sections_table.setItem(idx, 0, section_item)

            open_hint = QTableWidgetItem("Double-click row to open")
            open_hint.setFlags(open_hint.flags() & ~Qt.ItemFlag.ItemIsEditable)
            sections_table.setItem(idx, 1, open_hint)

        sections_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        sections_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        sections_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        def _open_selected_section() -> None:
            row = sections_table.currentRow()
            if row < 0:
                return
            item = sections_table.item(row, 0)
            if item is None:
                return
            target = item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(target, dict):
                return
            self._open_section_target(target)
            dialog.accept()

        sections_table.itemDoubleClicked.connect(
            lambda _item: _open_selected_section()
        )

        open_btn = QPushButton("Open Selected Section")
        open_btn.clicked.connect(_open_selected_section)
        sections_panel = QWidget()
        sections_layout = QVBoxLayout(sections_panel)
        sections_layout.setContentsMargins(0, 0, 0, 0)
        sections_layout.addWidget(sections_table)
        sections_layout.addWidget(open_btn)
        return sections_panel

    def _show_global_results(
        self,
        query: str,
        receipts,
        charters,
        clients,
        nav_targets,
    ) -> None:
        """Render search results in a tabbed dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Search Results: {query}")
        layout = QVBoxLayout()

        summary = QLabel(
            f"Receipts: {len(receipts)} | Charters: {len(charters)} |"
            f"Clients: {len(clients)} | Sections: {len(nav_targets)}"
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

        tabs.addTab(
            self._build_sections_results_widget(dialog, nav_targets),
            "Sections",
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
    background_color = "#e8eef5"
    surface_color = "#edf4fb"
    border_color = "#cbd5e1"
    text_color = "#1f2937"
    title_background_color = background_color
    button_background_color = "#dbe3ef"
    button_hover_color = "#cfdae8"
    button_text_color = "#1f2937"
    header_section_background_color = "#d8eafc"

    if theme_name == "soft_blue":
        background_color = "#eaf4ff"
        surface_color = "#f5faff"
        border_color = "#b9d6f2"
        text_color = "#16324f"
        title_background_color = background_color
        button_background_color = "#5f9ed6"
        button_hover_color = "#4a8bc5"
        button_text_color = "#ffffff"
        header_section_background_color = "#d8eafc"
    if theme_name == "light_gray":
        background_color = "#f2f4f7"
        surface_color = "#f7f8fa"
        border_color = "#cfd8e3"
        text_color = "#1f2933"
        title_background_color = background_color
        button_background_color = "#64748b"
        button_hover_color = "#55657a"
        button_text_color = "#ffffff"
        header_section_background_color = "#e0e6ee"

    return f"""
        QMainWindow, QWidget {{
            background-color: {background_color};
            color: {text_color};
        }}
        QTabWidget::pane {{
            background-color: {surface_color};
            border: 1px solid {border_color};
        }}
        QGroupBox, QFrame {{
            background-color: {surface_color};
            border: 1px solid {border_color};
            border-radius: 8px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
            color: {text_color};
            background-color: {title_background_color};
        }}
        QScrollArea {{
            background-color: {background_color};
            border: 0;
        }}
        QScrollArea > QWidget > QWidget {{
            background-color: {background_color};
        }}
        QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QDateEdit,
        QSpinBox, QDoubleSpinBox, QTimeEdit, QTableWidget {{
            background-color: #ffffff;
            color: {text_color};
            border: 1px solid #c8d1dc;
            selection-background-color: #5f9ed6;
            selection-color: #ffffff;
        }}
        QPushButton {{
            background-color: {button_background_color};
            color: {button_text_color};
            border: 1px solid {border_color};
            padding: 4px 10px;
        }}
        QPushButton:hover {{
            background-color: {button_hover_color};
        }}
        QHeaderView::section {{
            background-color: {header_section_background_color};
            color: {text_color};
            border: 1px solid {border_color};
        }}
    """


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
        from friendly_input_behavior import install_friendly_input_behavior

        install_friendly_input_behavior(app)

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

        # Load heavy desktop modules only after login succeeds.
        _load_main_window_dependencies()

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
