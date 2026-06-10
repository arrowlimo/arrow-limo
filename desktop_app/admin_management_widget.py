"""
Admin & User Management Widget
System administration, user management, settings, and backups
Ported from frontend/src/views/Admin.vue
"""

import csv
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import psycopg2
from db_error_handling import DatabaseContext
from login_manager import LoginManager

_APP_ROOT = (
    Path(sys.executable).parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent.parent
)

from PyQt6.QtCore import QSettings, Qt, QTimer
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

APP_VERSION = "1.1.0"
APP_BUILD_DATE = "2026-05-26"


def _get_build_info() -> dict:
    """Return version, install path, and last-install timestamp from manifest."""
    manifest = _APP_ROOT / "file_manifest.sha256"
    last_updated = "unknown"
    file_count = "—"
    if manifest.exists():
        try:
            mtime = datetime.fromtimestamp(manifest.stat().st_mtime)
            last_updated = mtime.strftime("%Y-%m-%d  %H:%M")
            lines = [l for l in manifest.read_text(errors="replace").splitlines() if l.strip()]
            file_count = str(len(lines))
        except Exception as _e:
            logger.debug('Suppressed: %s', _e)
    # Read installed version from version.txt (written by publish_to_dropbox.ps1)
    installed_version = APP_VERSION
    try:
        vfile = _APP_ROOT / "version.txt"
        if vfile.exists():
            installed_version = vfile.read_text(errors="replace").strip() or APP_VERSION
    except Exception as _e:
        logger.debug('Suppressed: %s', _e)
    # Check what version is available in Dropbox deploy folder
    available_version = "— (Dropbox not reachable)"
    try:
        import json as _json
        dropbox_manifest = Path(r"C:\Users\info\Dropbox\limo_deploy\update_manifest.json")
        if dropbox_manifest.exists():
            data = _json.loads(dropbox_manifest.read_text())
            available_version = data.get("latest_version", "—")
    except Exception as _e:
        logger.debug('Suppressed: %s', _e)
    return {
        "version": installed_version,
        "build_date": APP_BUILD_DATE,
        "install_path": str(_APP_ROOT),
        "last_updated": last_updated,
        "file_count": file_count,
        "available_version": available_version,
    }


def _is_users_email_unique_violation(error: psycopg2.Error) -> bool:
    constraint_name = (
        getattr(getattr(error, "diag", None), "constraint_name", "") or ""
    )
    if constraint_name == "users_email_key":
        return True
    message = str(error).lower()
    return "users_email_key" in message and "unique constraint" in message


class AdminManagementWidget(QWidget):
    def __init__(self, db, auth_user=None) -> None:
        super().__init__()
        self.db = db
        self.login_manager = LoginManager()
        self._current_username = (
            auth_user.get("username", "system") if auth_user else "system"
        )
        self.init_ui()

    def init_ui(self) -> None:
        """Initialize admin dashboard UI"""
        layout = QVBoxLayout()

        # Tab widget for different admin sections
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_overview_tab(), "📊 Overview")
        self.tabs.addTab(self._create_users_tab(), "👥 Users")
        self.tabs.addTab(self._create_settings_tab(), "⚙️ Settings")
        self.tabs.addTab(self._create_run_types_tab(), "🏃 Run Types")
        self.tabs.addTab(self._create_route_event_types_tab(), "🛣️ Route Events")
        self.tabs.addTab(self._create_vehicle_types_tab(), "🚌 Vehicle Types")
        self.tabs.addTab(self._create_charge_defaults_tab(), "💵 Charge Defaults")
        self.tabs.addTab(self._create_audit_tab(), "📋 Audit Log")
        self.tabs.addTab(self._create_backup_tab(), "💾 Backup & Restore")
        self.tabs.addTab(self._create_error_log_tab(), "🐛 Error Log")

        layout.addWidget(self.tabs)
        self.setLayout(layout)

    def _create_overview_tab(self) -> object:
        """Create the Overview tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        # System statistics
        stats_group = QGroupBox("System Statistics")
        stats_layout = QFormLayout()

        total_bookings = QLineEdit()
        total_bookings.setReadOnly(True)
        total_customers = QLineEdit()
        total_customers.setReadOnly(True)
        total_employees = QLineEdit()
        total_employees.setReadOnly(True)
        monthly_revenue = QLineEdit()
        monthly_revenue.setReadOnly(True)
        active_vehicles = QLineEdit()
        active_vehicles.setReadOnly(True)

        stats_layout.addRow("Total Bookings", total_bookings)
        stats_layout.addRow("Total Customers", total_customers)
        stats_layout.addRow("Total Employees", total_employees)
        stats_layout.addRow("Monthly Revenue", monthly_revenue)
        stats_layout.addRow("Active Vehicles", active_vehicles)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # Recent activity
        activity_group = QGroupBox("Recent System Activity")
        activity_layout = QVBoxLayout()

        self.activity_table = QTableWidget()
        self.activity_table.setColumnCount(4)
        self.activity_table.setHorizontalHeaderLabels(
            ["Timestamp", "User", "Action", "Details"]
        )
        self.activity_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        activity_layout.addWidget(self.activity_table)

        activity_group.setLayout(activity_layout)
        layout.addWidget(activity_group)

        # Load statistics
        self._load_overview_stats(
            total_bookings,
            total_customers,
            total_employees,
            monthly_revenue,
            active_vehicles,
        )

        # Build / version information
        build_info = _get_build_info()
        build_group = QGroupBox("Build Information")
        build_layout = QFormLayout()

        for label, value in [
            ("Installed Version", build_info["version"]),
            ("Available Version", build_info["available_version"]),
            ("Build Date",        build_info["build_date"]),
            ("Install Path",      build_info["install_path"]),
            ("Last Install Update", build_info["last_updated"]),
            ("Manifest Files",    build_info["file_count"]),
        ]:
            field = QLineEdit(value)
            field.setReadOnly(True)
            # Highlight if installed is behind available
            if label == "Available Version" and value not in ("\u2014", "\u2014 (Dropbox not reachable)"):
                inst = build_info["version"]
                if value != inst:
                    field.setStyleSheet("background: #fff3cd; color: #7b4f00; font-weight: bold;")
                else:
                    field.setStyleSheet("background: #d4edda; color: #155724; font-weight: bold;")
            build_layout.addRow(label, field)

        build_group.setLayout(build_layout)
        layout.addWidget(build_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def _create_users_tab(self) -> object:
        """Create the Users tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        # User list
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(6)
        self.users_table.setHorizontalHeaderLabels(
            ["Username", "Email", "Role", "Department", "Status", "Last Login"]
        )
        self.users_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.users_table.itemSelectionChanged.connect(self.load_selected_user)
        layout.addWidget(self.users_table)

        # User form
        form_group = QGroupBox("User Management")
        form_layout = QFormLayout()

        self.user_username = QLineEdit()
        self.user_email = QLineEdit()
        self.user_password = QLineEdit()
        self.user_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.user_role = QComboBox()
        self.user_role.addItems(
            ["admin", "dispatcher", "driver", "accountant", "viewer"]
        )
        self.user_department = QComboBox()
        self.user_department.addItems(
            ["operations", "dispatch", "accounting", "management", "admin"]
        )
        self.user_display_theme = QComboBox()
        self.user_display_theme.addItem("System Default", "default")
        self.user_display_theme.addItem("Soft Blue", "soft_blue")
        self.user_display_theme.addItem("Light Gray", "light_gray")
        self.user_status = QComboBox()
        self.user_status.addItems(["active", "inactive", "suspended"])

        button_layout = QHBoxLayout()
        add_btn = QPushButton("➕ Add User")
        add_btn.clicked.connect(self.add_user)
        update_btn = QPushButton("💾 Update")
        update_btn.clicked.connect(self.update_user)
        delete_btn = QPushButton("🗑️ Delete")
        delete_btn.clicked.connect(self.delete_user)
        button_layout.addWidget(add_btn)
        button_layout.addWidget(update_btn)
        button_layout.addWidget(delete_btn)
        button_layout.addStretch()

        form_layout.addRow("Username*", self.user_username)
        form_layout.addRow("Email*", self.user_email)
        form_layout.addRow("Password (new or reset)", self.user_password)
        form_layout.addRow("Role / Access", self.user_role)
        form_layout.addRow("Department", self.user_department)
        form_layout.addRow("Display Theme", self.user_display_theme)
        form_layout.addRow("Status", self.user_status)
        form_layout.addRow(button_layout)

        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        self.load_users()
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def _hash_password(self, password: str) -> str:
        """Generate an application-compatible password hash."""
        try:
            return self.login_manager.hash_password(password)
        except Exception as e:
            raise RuntimeError(f"Password hashing failed: {e}")

    def _parse_permissions(self, permissions) -> dict:
        if not permissions:
            return {}
        if isinstance(permissions, dict):
            return dict(permissions)
        if isinstance(permissions, str):
            try:
                parsed = json.loads(permissions)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    def _current_theme_value(self) -> str:
        value = self.user_display_theme.currentData()
        return str(value or "default")

    def _set_display_theme(self, theme_name: str) -> None:
        theme_name = (theme_name or "default").strip().lower()
        index = self.user_display_theme.findData(theme_name)
        if index < 0:
            index = self.user_display_theme.findData("default")
        self.user_display_theme.setCurrentIndex(max(index, 0))

    def _build_permissions_payload(self, existing_permissions=None) -> str:
        permissions = self._parse_permissions(existing_permissions)
        permissions["department"] = self.user_department.currentText()
        permissions["display_theme"] = self._current_theme_value()
        return json.dumps(permissions)

    def _log_audit(self, action: str, details: str) -> None:
        """Best-effort audit logger. Fails silently to avoid blocking UI."""
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                try:
                    cur.execute(
                        (
                            "INSERT INTO security_audit "
                            "(username, action, details, created_at) "
                            "VALUES (%s, %s, %s, NOW())"
                        ),
                        (self._current_username, action, details),
                    )
                    return
                except Exception as e:
                    logger.debug(
                        "security_audit created_at insert failed; "
                        "retrying fallback insert: %s",
                        e,
                    )
                cur.execute(
                    (
                        "INSERT INTO security_audit "
                        "(username, action, details) VALUES (%s, %s, %s)"
                    ),
                    (self._current_username, action, details),
                )
        except Exception as e:
            # swallow audit errors to avoid blocking UI
            logger.debug(f"Audit logging failed: {e}")

    def _create_settings_tab(self) -> object:
        """Create the Settings tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        settings_group = QGroupBox("System Settings")
        settings_layout = QFormLayout()

        self.company_name = QLineEdit()
        self.company_phone = QLineEdit()
        self.company_email = QLineEdit()
        self.company_email.setPlaceholderText("admin@company.com")
        self.timezone = QComboBox()
        self.timezone.addItems(["UTC", "EST", "CST", "MST", "PST"])
        self.backup_schedule = QComboBox()
        self.backup_schedule.addItems(["Never", "Daily", "Weekly", "Monthly"])
        self.auto_backup = QCheckBox("Enable automatic backups")

        save_btn = QPushButton("💾 Save Settings")
        save_btn.clicked.connect(self.save_settings)

        settings_layout.addRow("Company Name", self.company_name)
        settings_layout.addRow("Company Phone", self.company_phone)
        settings_layout.addRow("Company Email", self.company_email)
        settings_layout.addRow("Timezone", self.timezone)
        settings_layout.addRow("Backup Schedule", self.backup_schedule)
        settings_layout.addRow("", self.auto_backup)
        settings_layout.addRow(save_btn)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        self.load_settings()
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def _create_audit_tab(self) -> object:
        """Create the Audit Log tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Audit log table
        self.audit_table = QTableWidget()
        self.audit_table.setColumnCount(5)
        self.audit_table.setHorizontalHeaderLabels(
            ["Timestamp", "User", "Table", "Action", "Details"]
        )
        self.audit_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.audit_table)

        # Filter buttons
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        self.audit_filter_action = QComboBox()
        self.audit_filter_action.addItems(
            [
                "All",
                "add_user",
                "update_user",
                "delete_user",
                "backup",
                "restore",
            ]
        )
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_audit_log)
        filter_layout.addWidget(self.audit_filter_action)
        filter_layout.addWidget(refresh_btn)
        clear_btn = QPushButton("Clear Audit Log")
        clear_btn.clicked.connect(self.clear_audit_log)
        export_btn = QPushButton("📊 Export Log")
        export_btn.clicked.connect(self.export_audit_log)
        filter_layout.addWidget(clear_btn)
        filter_layout.addWidget(export_btn)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        widget.setLayout(layout)
        # Initial load
        self.load_audit_log()
        return widget

    def _create_backup_tab(self) -> object:
        """Create the Backup & Restore tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        backup_group = QGroupBox("Database Backup & Restore")
        backup_layout = QVBoxLayout()

        info_label = QLabel(
            "⚠️ Backup operations should be done carefully. "
            "Always keep backups of important data."
        )
        info_label.setStyleSheet("color: #ff9800; font-weight: bold;")
        backup_layout.addWidget(info_label)

        button_layout = QHBoxLayout()
        backup_btn = QPushButton("💾 Create Backup")
        backup_btn.clicked.connect(self.create_backup)
        restore_btn = QPushButton("⬅️ Restore from Backup")
        restore_btn.clicked.connect(self.restore_backup)
        download_btn = QPushButton("⬇️ Download Latest Backup")
        download_btn.clicked.connect(self.download_backup)
        button_layout.addWidget(backup_btn)
        button_layout.addWidget(restore_btn)
        button_layout.addWidget(download_btn)
        button_layout.addStretch()
        backup_layout.addLayout(button_layout)

        backup_group.setLayout(backup_layout)
        layout.addWidget(backup_group)

        # Backup history
        history_group = QGroupBox("Backup History")
        history_layout = QVBoxLayout()

        self.backups_table = QTableWidget()
        self.backups_table.setColumnCount(4)
        self.backups_table.setHorizontalHeaderLabels(
            ["Backup Time", "Size", "Type", "Status"]
        )
        self.backups_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        history_layout.addWidget(self.backups_table)

        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    # Implementation methods

    def _load_overview_stats(
        self,
        bookings_field,
        customers_field,
        employees_field,
        revenue_field,
        vehicles_field,
    ) -> None:
        """Load overview statistics"""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("SELECT COUNT(*) FROM charters")
                bookings_field.setText(str(cur.fetchone()[0]))

                cur.execute("SELECT COUNT(*) FROM clients")
                customers_field.setText(str(cur.fetchone()[0]))

                cur.execute("SELECT COUNT(*) FROM employees")
                employees_field.setText(str(cur.fetchone()[0]))

                # Monthly revenue (PostgreSQL syntax)
                cur.execute("""
                    SELECT COALESCE(SUM(total_amount_due), 0)
                    FROM charters
                    WHERE DATE_TRUNC('month', charter_date)
                        = DATE_TRUNC('month', CURRENT_DATE)
                    """)
                revenue = cur.fetchone()[0]
                revenue_field.setText(
                    f"${revenue:,.2f}" if revenue else "$0.00"
                )

                cur.execute(
                    "SELECT COUNT(*) FROM vehicles "
                    "WHERE operational_status = 'Active'"
                )
                vehicles_field.setText(str(cur.fetchone()[0]))

        except Exception as e:
            logger.error(f"Failed to load overview stats: {e}")

    def load_users(self) -> None:
        """Load users from database"""
        try:
            users_columns = self._get_users_table_columns()
            with DatabaseContext(self.db, auto_commit=False) as cur:
                if "department" in users_columns:
                    cur.execute("""
                        SELECT username, email, role, department, status,
                            last_login, permissions
                        FROM users
                        ORDER BY username
                        LIMIT 100
                        """)
                else:
                    cur.execute("""
                        SELECT username, email, role, status,
                            last_login, permissions
                        FROM users
                        ORDER BY username
                        LIMIT 100
                        """)
                users = cur.fetchall()
            # Adjust columns to available fields
            self.users_table.setRowCount(len(users))
            for row_idx, user_row in enumerate(users):
                if "department" in users_columns:
                    (
                        username,
                        email,
                        role,
                        department,
                        status,
                        last_login,
                        permissions,
                    ) = user_row
                else:
                    (
                        username,
                        email,
                        role,
                        status,
                        last_login,
                        permissions,
                    ) = user_row
                    department = None

                permissions_dict = self._parse_permissions(permissions)
                dept = (
                    department
                    or permissions_dict.get("department")
                    or self._infer_department(role, permissions_dict)
                )
                theme_name = permissions_dict.get("display_theme", "default")
                self.users_table.setItem(
                    row_idx, 0, QTableWidgetItem(username or "")
                )
                self.users_table.setItem(
                    row_idx, 1, QTableWidgetItem(email or "")
                )
                self.users_table.setItem(
                    row_idx, 2, QTableWidgetItem(role or "")
                )
                dept_item = QTableWidgetItem(dept or "")
                dept_item.setData(Qt.ItemDataRole.UserRole, permissions_dict)
                dept_item.setData(Qt.ItemDataRole.UserRole + 1, theme_name)
                self.users_table.setItem(row_idx, 3, dept_item)
                self.users_table.setItem(
                    row_idx, 4, QTableWidgetItem(status or "")
                )
                self.users_table.setItem(
                    row_idx, 5, QTableWidgetItem(str(last_login or ""))
                )
        except Exception as e:
            logger.error(f"Failed to load users: {e}")

    def load_selected_user(self) -> None:
        """Load selected user data"""
        selected = self.users_table.selectedItems()
        if selected:
            row = self.users_table.row(selected[0])
            self.user_username.setText(self.users_table.item(row, 0).text())
            self.user_email.setText(self.users_table.item(row, 1).text())
            self.user_role.setCurrentText(self.users_table.item(row, 2).text())
            dept_item = self.users_table.item(row, 3)
            dept_val = dept_item.text() if dept_item else "operations"
            if dept_val in [
                "operations",
                "dispatch",
                "accounting",
                "management",
                "admin",
            ]:
                self.user_department.setCurrentText(dept_val)
            else:
                self.user_department.setCurrentText("operations")
            theme_name = (
                dept_item.data(Qt.ItemDataRole.UserRole + 1)
                if dept_item is not None
                else "default"
            )
            self._set_display_theme(theme_name)
            self.user_status.setCurrentText(
                self.users_table.item(row, 4).text()
            )
            self.user_password.clear()

    def add_user(self) -> None:
        """Add new user"""
        # Validation
        if not self.user_username.text().strip():
            QMessageBox.warning(
                self, "Missing Fields", "Username is required."
            )
            self.user_username.setFocus()
            return

        if not self.user_email.text().strip():
            QMessageBox.warning(self, "Missing Fields", "Email is required.")
            self.user_email.setFocus()
            return

        try:
            users_columns = self._get_users_table_columns()
            with DatabaseContext(self.db, auto_commit=True) as cur:
                # Check if username already exists
                cur.execute(
                    "SELECT user_id FROM users WHERE username = %s",
                    (self.user_username.text().strip(),),
                )
                if cur.fetchone():
                    QMessageBox.warning(
                        self,
                        "Duplicate Username",
                        "Username already exists. Please choose another.",
                    )
                    return

                # Determine password (provided or default)
                provided_password = self.user_password.text().strip()
                password_plain = (
                    provided_password if provided_password else "changeme123"
                )
                password_hash = self._hash_password(password_plain)
                permissions_payload = self._build_permissions_payload()

                # Handle schema variants where users.department is unavailable.
                if "department" in users_columns and "permissions" in users_columns:
                    cur.execute(
                        """
                        INSERT INTO users (
                            username, email, role,
                            department, status, password_hash, permissions
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING user_id
                    """,
                        (
                            self.user_username.text().strip(),
                            self.user_email.text().strip(),
                            self.user_role.currentText(),
                            self.user_department.currentText(),
                            self.user_status.currentText(),
                            password_hash,
                            permissions_payload,
                        ),
                    )
                elif "department" in users_columns:
                    cur.execute(
                        """
                        INSERT INTO users (
                            username, email, role,
                            department, status, password_hash
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING user_id
                    """,
                        (
                            self.user_username.text().strip(),
                            self.user_email.text().strip(),
                            self.user_role.currentText(),
                            self.user_department.currentText(),
                            self.user_status.currentText(),
                            password_hash,
                        ),
                    )
                elif "permissions" in users_columns:
                    permissions_payload = json.dumps(
                        {"department": self.user_department.currentText()}
                    )
                    cur.execute(
                        """
                        INSERT INTO users (
                            username, email, role, status,
                            password_hash, permissions
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING user_id
                    """,
                        (
                            self.user_username.text().strip(),
                            self.user_email.text().strip(),
                            self.user_role.currentText(),
                            self.user_status.currentText(),
                            password_hash,
                            permissions_payload,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO users (
                            username, email, role, status,
                            password_hash
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING user_id
                    """,
                        (
                            self.user_username.text().strip(),
                            self.user_email.text().strip(),
                            self.user_role.currentText(),
                            self.user_status.currentText(),
                            password_hash,
                        ),
                    )

                new_user_id = cur.fetchone()[0]

            if provided_password:
                msg = f"User created successfully!\n\nUser ID: {new_user_id}"
            else:
                msg = (
                    f"User created successfully!\n\nUser ID: {new_user_id}\n\n"
                    "Default password: changeme123\n"
                    "(User should change on first login)"
                )
            QMessageBox.information(self, "Success", msg)
            username = self.user_username.text().strip()
            self._log_audit(
                "add_user", f"username={username} id={new_user_id}"
            )

            # Clear form and reload
            self.user_username.setText("")
            self.user_email.setText("")
            self.user_password.setText("")
            self.load_users()

        except psycopg2.Error as e:
            if _is_users_email_unique_violation(e):
                error_msg = (
                    "This database still enforces unique user emails. "
                    "Apply "
                    "migrations/004_allow_duplicate_user_emails.sql "
                    "on the target database "
                    "to allow shared work email addresses."
                )
            else:
                error_msg = (
                    e.diag.message_primary if hasattr(e, "diag") else str(e)
                )
            logger.error(f"Failed to add user: {error_msg}")
            QMessageBox.critical(
                self, "Database Error", f"Failed to add user:\n\n{error_msg}"
            )
        except Exception as e:
            logger.error(f"Failed to add user: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to add user:\n\n{e!s}"
            )

    def update_user(self) -> None:
        """Update selected user"""
        row = self.users_table.currentRow()
        if row < 0:
            QMessageBox.warning(
                self, "No Selection", "Please select a user to update."
            )
            return

        try:
            # Use original username from the selected row as identifier
            original_username = self.users_table.item(row, 0).text()
            users_columns = self._get_users_table_columns()
            new_password = self.user_password.text().strip()
            password_hash = self._hash_password(new_password) if new_password else None
            dept_item = self.users_table.item(row, 3)
            existing_permissions = (
                dept_item.data(Qt.ItemDataRole.UserRole)
                if dept_item is not None
                else {}
            )
            permissions_payload = self._build_permissions_payload(existing_permissions)

            with DatabaseContext(self.db, auto_commit=True) as cur:
                if (
                    "department" in users_columns
                    and "permissions" in users_columns
                    and password_hash
                ):
                    cur.execute(
                        """
                        UPDATE users
                        SET username = %s, email = %s,
                            role = %s, department = %s, status = %s,
                            password_hash = %s, permissions = %s
                        WHERE username = %s
                    """,
                        (
                            self.user_username.text().strip(),
                            self.user_email.text().strip(),
                            self.user_role.currentText(),
                            self.user_department.currentText(),
                            self.user_status.currentText(),
                            password_hash,
                            permissions_payload,
                            original_username,
                        ),
                    )
                elif "department" in users_columns and "permissions" in users_columns:
                    cur.execute(
                        """
                        UPDATE users
                        SET username = %s, email = %s,
                            role = %s, department = %s, status = %s,
                            permissions = %s
                        WHERE username = %s
                    """,
                        (
                            self.user_username.text().strip(),
                            self.user_email.text().strip(),
                            self.user_role.currentText(),
                            self.user_department.currentText(),
                            self.user_status.currentText(),
                            permissions_payload,
                            original_username,
                        ),
                    )
                elif "department" in users_columns and password_hash:
                    cur.execute(
                        """
                        UPDATE users
                        SET username = %s, email = %s,
                            role = %s, department = %s, status = %s,
                            password_hash = %s
                        WHERE username = %s
                    """,
                        (
                            self.user_username.text().strip(),
                            self.user_email.text().strip(),
                            self.user_role.currentText(),
                            self.user_department.currentText(),
                            self.user_status.currentText(),
                            password_hash,
                            original_username,
                        ),
                    )
                elif "department" in users_columns:
                    cur.execute(
                        """
                        UPDATE users
                        SET username = %s, email = %s,
                            role = %s, department = %s, status = %s
                        WHERE username = %s
                    """,
                        (
                            self.user_username.text().strip(),
                            self.user_email.text().strip(),
                            self.user_role.currentText(),
                            self.user_department.currentText(),
                            self.user_status.currentText(),
                            original_username,
                        ),
                    )
                elif "permissions" in users_columns and password_hash:
                    cur.execute(
                        """
                        UPDATE users
                        SET username = %s, email = %s, role = %s, status = %s,
                            password_hash = %s, permissions = %s
                        WHERE username = %s
                    """,
                        (
                            self.user_username.text().strip(),
                            self.user_email.text().strip(),
                            self.user_role.currentText(),
                            self.user_status.currentText(),
                            password_hash,
                            permissions_payload,
                            original_username,
                        ),
                    )
                elif "permissions" in users_columns:
                    cur.execute(
                        """
                        UPDATE users
                        SET username = %s, email = %s, role = %s, status = %s,
                            permissions = %s
                        WHERE username = %s
                    """,
                        (
                            self.user_username.text().strip(),
                            self.user_email.text().strip(),
                            self.user_role.currentText(),
                            self.user_status.currentText(),
                            permissions_payload,
                            original_username,
                        ),
                    )
                elif password_hash:
                    cur.execute(
                        """
                        UPDATE users
                        SET username = %s, email = %s, role = %s, status = %s,
                            password_hash = %s
                        WHERE username = %s
                    """,
                        (
                            self.user_username.text().strip(),
                            self.user_email.text().strip(),
                            self.user_role.currentText(),
                            self.user_status.currentText(),
                            password_hash,
                            original_username,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE users
                        SET username = %s, email = %s, role = %s, status = %s
                        WHERE username = %s
                    """,
                        (
                            self.user_username.text().strip(),
                            self.user_email.text().strip(),
                            self.user_role.currentText(),
                            self.user_status.currentText(),
                            original_username,
                        ),
                    )

            QMessageBox.information(
                self,
                "Success",
                f"User '{original_username}' updated successfully",
            )
            self._log_audit("update_user", f"username={original_username}")
            self.load_users()

        except psycopg2.Error as e:
            if _is_users_email_unique_violation(e):
                error_msg = (
                    "This database still enforces unique user emails. "
                    "Apply "
                    "migrations/004_allow_duplicate_user_emails.sql "
                    "on the target database "
                    "to allow shared work email addresses."
                )
            else:
                error_msg = (
                    e.diag.message_primary if hasattr(e, "diag") else str(e)
                )
            logger.error(f"Failed to update user: {error_msg}")
            QMessageBox.critical(
                self,
                "Database Error",
                f"Failed to update user:\n\n{error_msg}",
            )
        except Exception as e:
            logger.error(f"Failed to update user: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to update user:\n\n{e!s}"
            )

    def delete_user(self) -> None:
        """Delete selected user"""
        row = self.users_table.currentRow()
        if row < 0:
            QMessageBox.warning(
                self, "No Selection", "Please select a user to delete."
            )
            return

        username = self.users_table.item(row, 0).text()

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            (
                f"Delete user '{username}'?\n\n"
                "(This will set status to 'inactive', not hard delete)"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                # Soft delete: set status to inactive
                cur.execute(
                    """
                    UPDATE users
                    SET status = 'inactive', updated_at = NOW()
                    WHERE username = %s
                """,
                    (username,),
                )

            QMessageBox.information(
                self, "Success", f"User '{username}' has been deactivated"
            )
            self._log_audit("delete_user", f"username={username}")
            self.load_users()

        except psycopg2.Error as e:
            error_msg = (
                e.diag.message_primary if hasattr(e, "diag") else str(e)
            )
            logger.error(f"Failed to delete user: {error_msg}")
            QMessageBox.critical(
                self,
                "Database Error",
                f"Failed to delete user:\n\n{error_msg}",
            )
        except Exception as e:
            logger.error(f"Failed to delete user: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to delete user:\n\n{e!s}"
            )

    def load_settings(self) -> None:
        """Load system settings from QSettings (persisted across sessions)."""
        s = QSettings("ArrowLimousine", "ALMS")
        self.company_name.setText(s.value("company/name", "Arrow Limousine"))
        self.company_phone.setText(s.value("company/phone", ""))
        self.company_email.setText(
            s.value("company/email", "info@arrowlimousine.ca")
        )
        self.timezone.setCurrentText(s.value("company/timezone", "MST"))
        self.backup_schedule.setCurrentText(
            s.value("backup/schedule", "Daily")
        )
        auto = s.value("backup/auto_enabled", "true")
        self.auto_backup.setChecked(str(auto).lower() in ("true", "1", "yes"))
        # Start auto-backup timer based on loaded settings
        self._setup_auto_backup_timer()

    def save_settings(self) -> None:
        """Persist system settings and (re)configure auto-backup timer."""
        s = QSettings("ArrowLimousine", "ALMS")
        s.setValue("company/name", self.company_name.text())
        s.setValue("company/phone", self.company_phone.text())
        s.setValue("company/email", self.company_email.text())
        s.setValue("company/timezone", self.timezone.currentText())
        s.setValue("backup/schedule", self.backup_schedule.currentText())
        s.setValue("backup/auto_enabled", self.auto_backup.isChecked())
        self._setup_auto_backup_timer()
        QMessageBox.information(
            self, "Settings Saved", "System settings updated successfully."
        )

    def _setup_auto_backup_timer(self) -> None:
        """Create or reconfigure the auto-backup QTimer."""
        # Stop existing timer if any
        if hasattr(self, "_backup_timer") and self._backup_timer is not None:
            self._backup_timer.stop()
            self._backup_timer = None

        if not self.auto_backup.isChecked():
            return
        schedule = self.backup_schedule.currentText()
        if schedule == "Never":
            return

        interval_map = {"Daily": 1, "Weekly": 7, "Monthly": 30}
        days = interval_map.get(schedule, 1)

        # Check immediately whether a backup is overdue, then poll hourly
        self._backup_interval_days = days
        self._check_and_run_auto_backup()

        # Re-check every hour
        self._backup_timer = QTimer(self)
        self._backup_timer.timeout.connect(self._check_and_run_auto_backup)
        self._backup_timer.start(60 * 60 * 1000)  # 1 hour in ms

    def _check_and_run_auto_backup(self) -> None:
        """Run backup if the configured interval has elapsed since last run."""
        s = QSettings("ArrowLimousine", "ALMS")
        last_backup_str = s.value("backup/last_auto_backup", "")
        days = getattr(self, "_backup_interval_days", 1)
        if last_backup_str:
            try:
                last_dt = datetime.fromisoformat(last_backup_str)
                elapsed = (datetime.now() - last_dt).total_seconds()
                if elapsed < days * 86400:
                    return  # Not yet due
            except ValueError:
                pass  # Bad stored value — run anyway
        self._run_auto_backup()

    def _run_auto_backup(self) -> None:
        """Silently run pg_dump and update last-backup timestamp."""
        try:
            skip_reason = None
            db_target = (
                os.environ.get("DB_TARGET")
                or os.environ.get("ALMS_DEFAULT_DB_TARGET")
                or ""
            ).strip().lower()
            db_host = os.environ.get("DB_HOST", "localhost")
            if os.environ.get("ALMS_SKIP_AUTO_BACKUP") == "1":
                skip_reason = "automation requested skip"
            elif db_target == "neon" or "neon.tech" in db_host.lower():
                skip_reason = "remote Neon target is not backed up from UI"
            if skip_reason:
                logger.info(f"Auto-backup skipped: {skip_reason}")
                return

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = r"L:\limo\backups"
            os.makedirs(backup_dir, exist_ok=True)
            out_file = os.path.join(backup_dir, f"almsdata_auto_{ts}.sql")
            db_port = str(os.environ.get("DB_PORT", "5432"))
            db_name = os.environ.get("DB_NAME", "almsdata")
            db_user = os.environ.get("DB_USER", "postgres")
            db_password = os.environ.get("DB_PASSWORD", "")
            cmd = [
                "pg_dump", "-h", db_host, "-p", db_port,
                "-U", db_user, "-d", db_name, "-f", out_file,
            ]
            env = os.environ.copy()
            if db_password:
                env["PGPASSWORD"] = db_password
            result = subprocess.run(
                cmd, env=env, capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                QSettings("ArrowLimousine", "ALMS").setValue(
                    "backup/last_auto_backup", datetime.now().isoformat()
                )
                logger.info(f"Auto-backup completed: {out_file}")
            else:
                logger.warning(
                    f"Auto-backup pg_dump failed: {result.stderr[:200]}"
                )
        except FileNotFoundError:
            logger.warning("Auto-backup skipped: pg_dump not found in PATH")
        except Exception as e:
            logger.error(f"Auto-backup error: {e}")

    def _infer_department(self, role: str, permissions) -> str:
        """Infer department from role/permissions text.
        Simple heuristic mapping; keeps UI consistent without changing schema.
        """
        role = (role or "").lower()
        # Normalize permissions into a lowercase searchable string
        if permissions is None:
            text = ""
        elif isinstance(permissions, str):
            text = permissions.lower()
        elif isinstance(permissions, (list, tuple, set)):
            try:
                text = ",".join([str(p).lower() for p in permissions])
            except Exception:
                text = str(permissions).lower()
        elif isinstance(permissions, dict):
            try:
                text = ",".join(
                    [f"{k}:{v}" for k, v in permissions.items()]
                ).lower()
            except Exception:
                text = str(permissions).lower()
        else:
            text = str(permissions).lower()
        if "dispatch" in text or role == "dispatcher":
            return "dispatch"
        if "account" in text or role in ("accountant", "accounting"):
            return "accounting"
        if (
            role in ("admin", "manager", "management")
            or "admin" in text
            or "manage" in text
        ):
            return "admin" if role == "admin" or "admin" in text else "management"
        if (
            role in ("driver", "operations")
            or "driver" in text
            or "ops" in text
        ):
            return "operations"
        return "operations"

    def _get_users_table_columns(self) -> set:
        """Inspect users columns so CRUD adapts to schema differences."""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'users'
                    """)
                return {row[0] for row in cur.fetchall()}
        except Exception as e:
            logger.warning(f"Could not inspect users table columns: {e}")
            return set()

    def clear_audit_log(self) -> None:
        """Clear audit log"""
        reply = QMessageBox.question(
            self,
            "Confirm",
            "Clear audit log?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                try:
                    cur.execute("DELETE FROM security_audit")
                except Exception:
                    cur.execute("TRUNCATE TABLE security_audit")
            QMessageBox.information(self, "Success", "Audit log cleared.")
            self.load_audit_log()
        except Exception as e:
            logger.error(f"Failed to clear audit log: {e}")
            QMessageBox.warning(
                self, "Error", f"Failed to clear audit log: {e}"
            )

    def export_audit_log(self) -> None:
        """Export audit log"""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Audit Log", "", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    "SELECT created_at, action, details FROM security_audit "
                    "ORDER BY created_at DESC LIMIT 1000"
                )
                rows = cur.fetchall()

            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Action", "Details"])
                for r in rows:
                    writer.writerow([str(r[0] or ""), r[1] or "", r[2] or ""])
            QMessageBox.information(
                self, "Success", f"Audit log exported to {path}"
            )
        except Exception as e:
            logger.error(f"Failed to export audit log: {e}")
            QMessageBox.warning(self, "Error", f"Failed to export: {e}")

    def _ensure_security_audit_table(self) -> None:
        """Create security_audit table if it doesn't exist."""
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS security_audit (
                        audit_id SERIAL PRIMARY KEY,
                        username TEXT,
                        action TEXT,
                        details TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                # Add username column to existing tables that predate the schema
                cur.execute("""
                    ALTER TABLE security_audit
                    ADD COLUMN IF NOT EXISTS username TEXT
                """)
        except Exception as e:
            logger.debug("Unable to ensure security_audit table: %s", e)

    def load_audit_log(self) -> None:
        """Load audit entries into table with optional action filter."""
        self._ensure_security_audit_table()
        try:
            action_filter = None
            if hasattr(self, "audit_filter_action"):
                val = self.audit_filter_action.currentText()
                action_filter = None if val == "All" else val

            with DatabaseContext(self.db, auto_commit=False) as cur:
                if action_filter:
                    cur.execute(
                        "SELECT created_at, username, action, details "
                        "FROM security_audit "
                        "WHERE action = %s "
                        "ORDER BY created_at DESC "
                        "LIMIT 500",
                        (action_filter,),
                    )
                else:
                    cur.execute(
                        "SELECT created_at, username, action, details "
                        "FROM security_audit "
                        "ORDER BY created_at DESC "
                        "LIMIT 500"
                    )
                rows = cur.fetchall()

            self.audit_table.setRowCount(len(rows))
            for i, (ts, uname, act, det) in enumerate(rows):
                self.audit_table.setItem(i, 0, QTableWidgetItem(str(ts or "")))
                self.audit_table.setItem(
                    i, 1, QTableWidgetItem(str(uname or "system"))
                )
                self.audit_table.setItem(
                    i,
                    2,
                    QTableWidgetItem(
                        "users"
                        if act in ("add_user", "update_user", "delete_user")
                        else "system"
                    ),
                )
                self.audit_table.setItem(
                    i, 3, QTableWidgetItem(str(act or ""))
                )
                # Convert details to string if it's a dict or other type
                detail_str = (
                    str(det) if not isinstance(det, str) else (det or "")
                )
                self.audit_table.setItem(i, 4, QTableWidgetItem(detail_str))
        except Exception as e:
            if "security_audit" in str(e) or "does not exist" in str(e):
                logger.debug(f"Audit log table not available: {e}")
            else:
                logger.error(f"Failed to load audit log: {e}")
            # Show empty table on error
            self.audit_table.setRowCount(0)

    def _get_db_target_from_env(self) -> object:
        """Return active DB target from environment variables."""
        return {
            "host": os.environ.get("DB_HOST", "localhost"),
            "port": str(os.environ.get("DB_PORT", "5432")),
            "name": os.environ.get("DB_NAME", "almsdata"),
            "user": os.environ.get("DB_USER", "postgres"),
            "password": os.environ.get("DB_PASSWORD", ""),
            "sslmode": os.environ.get("DB_SSLMODE", "prefer"),
        }

    def _build_pg_env(self, db_target) -> object:
        """Build process environment for pg_dump/psql/pg_restore."""
        env = os.environ.copy()
        db_password = db_target.get("password", "")
        if db_password:
            env["PGPASSWORD"] = db_password
        else:
            env.pop("PGPASSWORD", None)

        db_sslmode = db_target.get("sslmode", "")
        if db_sslmode:
            env["PGSSLMODE"] = db_sslmode
        return env

    def _build_restore_command(self, backup_path, db_target) -> object:
        """Build restore command based on selected backup extension."""
        host = db_target["host"]
        port = db_target["port"]
        user = db_target["user"]
        name = db_target["name"]

        if backup_path.endswith(".sql"):
            return [
                "psql",
                "-h",
                host,
                "-p",
                port,
                "-U",
                user,
                "-d",
                name,
                "-f",
                backup_path,
                "--no-password",
            ]

        return [
            "pg_restore",
            "-h",
            host,
            "-p",
            port,
            "-U",
            user,
            "-d",
            name,
            "--clean",
            "--if-exists",
            backup_path,
            "--no-password",
        ]

    def create_backup(self) -> None:
        """Create database backup"""
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = str(_APP_ROOT / "backups")
        os.makedirs(backup_dir, exist_ok=True)
        backup_file = os.path.join(
            backup_dir, f"almsdata_backup_{timestamp}.sql"
        )

        try:
            db_target = self._get_db_target_from_env()
            db_host = db_target["host"]
            db_port = db_target["port"]
            db_name = db_target["name"]
            db_user = db_target["user"]

            # Execute pg_dump - use command as list for security.
            cmd = [
                "pg_dump",
                "-h",
                db_host,
                "-p",
                db_port,
                "-U",
                db_user,
                "-d",
                db_name,
                "-f",
                backup_file,
            ]
            env = self._build_pg_env(db_target)

            result = subprocess.run(
                cmd, env=env, capture_output=True, text=True
            )

            if result.returncode == 0:
                file_size_mb = os.path.getsize(backup_file) / (1024 * 1024)
                QMessageBox.information(
                    self,
                    "Backup Complete",
                    "Database backup created successfully!\n\n"
                    f"File: {backup_file}\n"
                    f"Size: {file_size_mb:.2f} MB\n"
                    f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                )
            else:
                error_msg = result.stderr if result.stderr else "Unknown error"
                auth_hint = ""
                if "password authentication failed" in error_msg.lower():
                    auth_hint = (
                        "\n\nAuthentication failed for backup connection. "
                        "Check DB_USER/DB_PASSWORD in your .env or "
                        "selected DB target."
                    )
                QMessageBox.critical(
                    self,
                    "Backup Failed",
                    (
                        f"pg_dump failed:\n\n{error_msg}\n\n"
                        "Connection target: "
                        f"{db_host}:{db_port}/{db_name} as {db_user}"
                        f"{auth_hint}\n\n"
                        "Make sure PostgreSQL is installed and pg_dump "
                        "is in your system PATH.\n"
                        "You can also add PostgreSQL\\bin to your PATH "
                        "environment variable."
                    ),
                )
        except FileNotFoundError:
            QMessageBox.critical(
                self,
                "pg_dump Not Found",
                "Could not find pg_dump command.\n\n"
                "PostgreSQL tools must be installed and in system PATH.\n\n"
                "Typical locations:\n"
                "• C:\\Program Files\\PostgreSQL\\16\\bin\n"
                "• C:\\Program Files\\PostgreSQL\\15\\bin\n\n"
                "Add the bin folder to your system PATH environment variable.",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Backup failed:\n\n{e!s}\n\n"
                f"Backup folder: {backup_dir}\n"
                "Make sure you have write permissions.",
            )

    def restore_backup(self) -> None:
        """Restore from backup"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Backup",
            str(_APP_ROOT / "backups"),
            "Database Files (*.dump *.sql);;All Files (*.*)",
        )

        if not path:
            return

        # Confirm restore
        reply = QMessageBox.question(
            self,
            "Confirm Restore",
            "⚠️ WARNING: This will OVERWRITE the current database!\n\n"
            f"Restore from:\n{path}\n\n"
            "All current data will be replaced with backup data.\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            db_target = self._get_db_target_from_env()
            cmd = self._build_restore_command(path, db_target)
            env = self._build_pg_env(db_target)

            result = subprocess.run(
                cmd, env=env, capture_output=True, text=True
            )

            if result.returncode == 0:
                QMessageBox.information(
                    self,
                    "Restore Complete",
                    "Database restored successfully!\n\n"
                    f"From: {os.path.basename(path)}\n\n"
                    "⚠️ Application should be restarted to reload data.",
                )
            else:
                QMessageBox.critical(
                    self,
                    "Restore Failed",
                    f"Database restore failed:\n\n{result.stderr[:500]}",
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Restore failed:\n\n{e!s}")

    def download_backup(self) -> None:
        """Open the backups folder so the user can copy the latest backup."""
        import subprocess as _sp
        backup_dir = r"L:\limo\backups"
        os.makedirs(backup_dir, exist_ok=True)
        try:
            _sp.Popen(["explorer", backup_dir])
        except Exception as e:
            QMessageBox.information(
                self, "Backups Folder", f"Backups are stored at:\n{backup_dir}"
                f"\n\nCould not open Explorer: {e}"
            )

    def _create_route_event_types_tab(self) -> object:
        """Create the Route Event Types manager tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("<b>Manage Route Event Types</b>"))
        layout.addWidget(QLabel(
            "Define the event labels shown on run sheets and route tables. "
            "Event Code is the internal key used by routes."
        ))

        self.route_event_types_table = QTableWidget()
        self.route_event_types_table.setColumnCount(4)
        self.route_event_types_table.setHorizontalHeaderLabels(
            ["Event Code", "Label", "Active", "Display Order"]
        )
        hh = self.route_event_types_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.route_event_types_table)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("➕ Add New")
        add_btn.clicked.connect(self._add_route_event_type)
        btn_layout.addWidget(add_btn)

        del_btn = QPushButton("🗑️ Delete Selected")
        del_btn.clicked.connect(self._delete_route_event_type)
        btn_layout.addWidget(del_btn)

        save_btn = QPushButton("💾 Save Changes")
        save_btn.clicked.connect(self._save_route_event_types)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()
        widget.setLayout(layout)
        self._load_route_event_types()
        return widget

    def _load_route_event_types(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT event_type_id, event_code, event_name,
                           is_active, display_order
                    FROM route_event_types
                    ORDER BY display_order, event_type_id
                """)
                rows = cur.fetchall()
            self.route_event_types_table.setRowCount(len(rows))
            for row_idx, (eid, code, name, active, order) in enumerate(rows):
                code_item = QTableWidgetItem(code or "")
                self.route_event_types_table.setItem(row_idx, 0, code_item)
                code_item.setData(Qt.ItemDataRole.UserRole, eid)

                name_item = QTableWidgetItem(name or "")
                self.route_event_types_table.setItem(row_idx, 1, name_item)

                active_item = QTableWidgetItem()
                active_item.setCheckState(
                    Qt.CheckState.Checked if active else Qt.CheckState.Unchecked
                )
                self.route_event_types_table.setItem(row_idx, 2, active_item)

                order_item = QTableWidgetItem(str(order or ""))
                self.route_event_types_table.setItem(row_idx, 3, order_item)
        except Exception as e:
            logger.error(f"Failed to load route event types: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load route event types: {e}")

    def _add_route_event_type(self) -> None:
        row = self.route_event_types_table.rowCount()
        self.route_event_types_table.insertRow(row)
        code_item = QTableWidgetItem("")
        code_item.setData(Qt.ItemDataRole.UserRole, None)  # new row — no DB id yet
        self.route_event_types_table.setItem(row, 0, code_item)
        self.route_event_types_table.setItem(row, 1, QTableWidgetItem(""))
        active_item = QTableWidgetItem()
        active_item.setCheckState(Qt.CheckState.Checked)
        self.route_event_types_table.setItem(row, 2, active_item)
        self.route_event_types_table.setItem(row, 3, QTableWidgetItem("999"))

    def _delete_route_event_type(self) -> None:
        selected = self.route_event_types_table.selectedIndexes()
        if not selected:
            QMessageBox.warning(self, "Warning", "Select a row to delete.")
            return
        if QMessageBox.question(self, "Confirm", "Delete selected event type?") \
                == QMessageBox.StandardButton.Yes:
            self.route_event_types_table.removeRow(selected[0].row())

    def _save_route_event_types(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                ids_in_ui = []
                for row in range(self.route_event_types_table.rowCount()):
                    code_item  = self.route_event_types_table.item(row, 0)
                    name_item  = self.route_event_types_table.item(row, 1)
                    active_item = self.route_event_types_table.item(row, 2)
                    order_item = self.route_event_types_table.item(row, 3)

                    code = code_item.text().strip() if code_item else ""
                    name = name_item.text().strip() if name_item else ""
                    active = (active_item.checkState() == Qt.CheckState.Checked
                              if active_item else True)
                    try:
                        order = int(order_item.text()) if order_item and order_item.text() else 999
                    except Exception:
                        order = 999

                    if not code:
                        continue

                    eid = code_item.data(Qt.ItemDataRole.UserRole) if code_item else None

                    if eid:
                        cur.execute("""
                            UPDATE route_event_types
                            SET event_code=%s, event_name=%s,
                                is_active=%s, display_order=%s
                            WHERE event_type_id=%s
                        """, (code, name, active, order, eid))
                        ids_in_ui.append(eid)
                    else:
                        cur.execute("""
                            INSERT INTO route_event_types
                              (event_code, event_name, clock_action,
                               affects_billing, is_active, display_order)
                            VALUES (%s, %s, 'none', false, %s, %s)
                            ON CONFLICT (event_code) DO UPDATE
                              SET event_name=EXCLUDED.event_name,
                                  is_active=EXCLUDED.is_active,
                                  display_order=EXCLUDED.display_order
                            RETURNING event_type_id
                        """, (code, name, active, order))
                        new_row = cur.fetchone()
                        if new_row:
                            ids_in_ui.append(new_row[0])

                # Delete rows removed in UI
                if ids_in_ui:
                    cur.execute(
                        "DELETE FROM route_event_types WHERE event_type_id != ALL(%s)",
                        (ids_in_ui,)
                    )
                self.db.commit()
            QMessageBox.information(self, "Success", "Route event types saved.")
            self._load_route_event_types()
        except Exception as e:
            logger.error(f"Failed to save route event types: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save route event types: {e}")

    # ─────────────────── Run Types Tab ───────────────────

    def _create_run_types_tab(self) -> object:
        """Create the Run Types manager tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Title
        layout.addWidget(QLabel("<b>Manage Charter Run Types</b>"))
        layout.addWidget(
            QLabel("Edit run types for Charter and Route selection")
        )

        # Table for run types
        self.run_types_table = QTableWidget()
        self.run_types_table.setColumnCount(3)
        self.run_types_table.setHorizontalHeaderLabels(
            ["Run Type", "Active", "Display Order"]
        )
        self.run_types_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.run_types_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.run_types_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(self.run_types_table)

        # Buttons
        button_layout = QHBoxLayout()
        add_btn = QPushButton("➕ Add New Run Type")
        add_btn.clicked.connect(self._add_run_type)
        button_layout.addWidget(add_btn)

        delete_btn = QPushButton("🗑️ Delete Selected")
        delete_btn.clicked.connect(self._delete_run_type)
        button_layout.addWidget(delete_btn)

        save_btn = QPushButton("💾 Save Changes")
        save_btn.clicked.connect(self._save_run_types)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)
        layout.addStretch()

        widget.setLayout(layout)
        self._load_run_types()
        return widget

    def _load_run_types(self) -> None:
        """Load run types from database into table"""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT run_type_name, is_active, display_order
                    FROM charter_run_types
                    ORDER BY display_order, run_type_name
                """)
                rows = cur.fetchall()

            self.run_types_table.setRowCount(len(rows))

            for row_idx, (name, active, order) in enumerate(rows):
                # Run Type name
                name_item = QTableWidgetItem(name)
                self.run_types_table.setItem(row_idx, 0, name_item)

                # Active checkbox
                active_item = QTableWidgetItem()
                active_item.setCheckState(
                    Qt.CheckState.Checked
                    if active
                    else Qt.CheckState.Unchecked
                )
                self.run_types_table.setItem(row_idx, 1, active_item)

                # Display order
                order_item = QTableWidgetItem(str(order or ""))
                self.run_types_table.setItem(row_idx, 2, order_item)

                # Store name for delete operations (use run_type_name as key
                # since no id column)
                name_item.setData(Qt.ItemDataRole.UserRole, name)

        except Exception as e:
            logger.error(f"Failed to load run types: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to load run types: {e}"
            )

    def _add_run_type(self) -> None:
        """Add a new run type row"""
        row = self.run_types_table.rowCount()
        self.run_types_table.insertRow(row)

        # New row defaults
        name_item = QTableWidgetItem("")
        self.run_types_table.setItem(row, 0, name_item)

        active_item = QTableWidgetItem()
        active_item.setCheckState(Qt.CheckState.Checked)
        self.run_types_table.setItem(row, 1, active_item)

        order_item = QTableWidgetItem("999")
        self.run_types_table.setItem(row, 2, order_item)

        # Mark as new (no ID stored)
        name_item.setData(Qt.ItemDataRole.UserRole, None)

    def _delete_run_type(self) -> None:
        """Delete selected run type"""
        selected = self.run_types_table.selectedIndexes()
        if not selected:
            QMessageBox.warning(
                self, "Warning", "Please select a run type to delete"
            )
            return

        if (
            QMessageBox.question(self, "Confirm", "Delete selected run type?")
            == QMessageBox.StandardButton.Yes
        ):
            row = selected[0].row()
            self.run_types_table.removeRow(row)

    def _save_run_types(self) -> None:
        """Save run type changes to database"""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                # Disable foreign key checks temporarily
                cur.execute("SET CONSTRAINTS ALL DEFERRED")

                names_in_ui = []
                seen_names = set()

                for row in range(self.run_types_table.rowCount()):
                    name_item = self.run_types_table.item(row, 0)
                    active_item = self.run_types_table.item(row, 1)
                    order_item = self.run_types_table.item(row, 2)
                    name = name_item.text().strip() if name_item else ""
                    active = (
                        active_item.checkState() == Qt.CheckState.Checked
                        if active_item else True
                    )
                    try:
                        order = (
                            int(order_item.text())
                            if order_item and order_item.text()
                            else 999
                        )
                    except Exception:
                        order = 999

                    if not name:
                        continue

                    if name.lower() in seen_names:
                        raise ValueError(
                            f"Duplicate run type in grid: {name}"
                        )
                    seen_names.add(name.lower())
                    names_in_ui.append(name)

                    original_name = (
                        name_item.data(Qt.ItemDataRole.UserRole)
                        if name_item else None
                    )

                    if original_name:
                        # Update existing row (supports rename + values).
                        cur.execute(
                            """
                            UPDATE charter_run_types
                            SET run_type_name = %s,
                                is_active = %s,
                                display_order = %s
                            WHERE run_type_name = %s
                        """,
                            (name, active, order, original_name),
                        )
                    else:
                        # Insert new, or update if name already exists.
                        cur.execute(
                            """
                            INSERT INTO charter_run_types (
                                run_type_name, is_active, display_order
                            )
                            VALUES (%s, %s, %s)
                            ON CONFLICT (run_type_name)
                            DO UPDATE SET
                                is_active = EXCLUDED.is_active,
                                display_order = EXCLUDED.display_order
                        """,
                            (name, active, order),
                        )

                # Remove rows deleted in the UI.
                if names_in_ui:
                    cur.execute(
                        """
                        DELETE FROM charter_run_types
                        WHERE NOT (run_type_name = ANY(%s))
                        """,
                        (names_in_ui,),
                    )
                else:
                    cur.execute("DELETE FROM charter_run_types")

                self.db.connection.commit()

            QMessageBox.information(
                self, "Success", "Run types saved successfully"
            )
            self._load_run_types()
        except Exception as e:
            logger.error(f"Failed to save run types: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to save run types: {e}"
            )

    # ─────────────────── Vehicle Types Tab ───────────────────

    def _vehicle_pricing_table_columns(self) -> object:
        """Return available columns for vehicle_pricing_defaults table."""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema='public'
                      AND table_name='vehicle_pricing_defaults'
                    """
                )
                return {str(r[0]) for r in (cur.fetchall() or []) if r and r[0]}
        except Exception:
            return set()

    def _vehicle_pricing_rate_columns(self, cols) -> object:
        """Map UI rate fields to concrete DB column names for this schema."""
        return {
            "hourly": "hourly_rate" if "hourly_rate" in cols else None,
            "package": (
                "hourly_package"
                if "hourly_package" in cols
                else ("package_rate" if "package_rate" in cols else None)
            ),
            "daily": "daily_rate" if "daily_rate" in cols else None,
            "standby": "standby_rate" if "standby_rate" in cols else None,
        }

    def _vehicle_pricing_display_order_column(self, cols) -> object:
        """Return column used to persist Requested Vehicle Type display order."""
        if "vehicle_type_display_order" in cols:
            return "vehicle_type_display_order"
        if "display_order" in cols:
            return "display_order"
        return None

    def _ensure_vehicle_pricing_display_order_column(self, cols) -> object:
        """Ensure vehicle_pricing_defaults has a display-order column."""
        order_col = self._vehicle_pricing_display_order_column(cols)
        if order_col:
            return order_col

        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                "ALTER TABLE vehicle_pricing_defaults "
                "ADD COLUMN IF NOT EXISTS vehicle_type_display_order INTEGER"
            )

        cols.add("vehicle_type_display_order")
        return "vehicle_type_display_order"

    def _create_vehicle_types_tab(self) -> object:
        """Manage requested vehicle types and their pricing defaults."""
        widget = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("<b>Manage Vehicle Types & Pricing Defaults</b>"))
        layout.addWidget(
            QLabel("Add or remove vehicle types that appear in the Requested "
                   "Vehicle Type dropdown on the charter form.")
        )

        self.vehicle_types_table = QTableWidget()
        self.vehicle_types_table.setColumnCount(5)
        self.vehicle_types_table.setHorizontalHeaderLabels(
            ["Vehicle Type", "Hourly Rate", "Package Rate", "Daily Rate",
             "Standby Rate"]
        )
        self.vehicle_types_table.setMinimumHeight(460)
        self.vehicle_types_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.vehicle_types_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.vehicle_types_table.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        self.vehicle_types_table.setDragEnabled(True)
        self.vehicle_types_table.setAcceptDrops(True)
        self.vehicle_types_table.viewport().setAcceptDrops(True)
        self.vehicle_types_table.setDropIndicatorShown(True)
        self.vehicle_types_table.setDefaultDropAction(Qt.DropAction.MoveAction)
        hdr = self.vehicle_types_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 5):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.vehicle_types_table, 1)
        layout.addWidget(QLabel(
            "Tip: drag and drop rows to reorder vehicle size display in Charter."
        ))

        btn_row = QHBoxLayout()
        add_btn = QPushButton("➕ Add Vehicle Type")
        add_btn.clicked.connect(self._add_vehicle_type_row)
        btn_row.addWidget(add_btn)

        del_btn = QPushButton("🗑️ Delete Selected")
        del_btn.clicked.connect(self._delete_vehicle_type_row)
        btn_row.addWidget(del_btn)

        move_up_btn = QPushButton("⬆ Move Up")
        move_up_btn.clicked.connect(lambda: self._move_vehicle_type_row(-1))
        btn_row.addWidget(move_up_btn)

        move_down_btn = QPushButton("⬇ Move Down")
        move_down_btn.clicked.connect(lambda: self._move_vehicle_type_row(1))
        btn_row.addWidget(move_down_btn)

        save_btn = QPushButton("💾 Save Changes")
        save_btn.clicked.connect(self._save_vehicle_types)
        btn_row.addWidget(save_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)
        widget.setLayout(layout)

        self._load_vehicle_types()
        return widget

    def _load_vehicle_types(self) -> None:
        """Load vehicle types from vehicle_pricing_defaults."""
        try:
            cols = self._vehicle_pricing_table_columns()
            if not cols:
                raise RuntimeError(
                    "vehicle_pricing_defaults table was not found in this database."
                )
            rates = self._vehicle_pricing_rate_columns(cols)
            order_col = self._vehicle_pricing_display_order_column(cols)

            select_parts = ["vehicle_type"]
            for key in ("hourly", "package", "daily", "standby"):
                col = rates.get(key)
                if col:
                    select_parts.append(f"COALESCE({col}, 0)")
                else:
                    select_parts.append("0")

            where_parts = ["vehicle_type IS NOT NULL", "vehicle_type != ''"]
            if "charter_type_code" in cols:
                # Vehicle Types tab manages generic defaults rows only.
                where_parts.append("COALESCE(charter_type_code, '') = ''")

            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    f"""
                    SELECT {', '.join(select_parts)}
                    FROM vehicle_pricing_defaults
                    WHERE {' AND '.join(where_parts)}
                    ORDER BY {
                        f"COALESCE({order_col}, 2147483647), vehicle_type"
                        if order_col else "vehicle_type"
                    }
                    """
                )
                rows = cur.fetchall()

            self.vehicle_types_table.setRowCount(len(rows))
            for r, (vtype, hourly, pkg, daily, standby) in enumerate(rows):
                self.vehicle_types_table.setItem(r, 0, QTableWidgetItem(vtype))
                self.vehicle_types_table.setItem(
                    r, 1, QTableWidgetItem(f"{float(hourly):.2f}"))
                self.vehicle_types_table.setItem(
                    r, 2, QTableWidgetItem(f"{float(pkg):.2f}"))
                self.vehicle_types_table.setItem(
                    r, 3, QTableWidgetItem(f"{float(daily):.2f}"))
                self.vehicle_types_table.setItem(
                    r, 4, QTableWidgetItem(f"{float(standby):.2f}"))
                self.vehicle_types_table.item(r, 0).setData(
                    Qt.ItemDataRole.UserRole, vtype)
        except Exception as e:
            logger.error(f"Failed to load vehicle types: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to load vehicle types: {e}")

    def _add_vehicle_type_row(self) -> None:
        """Insert a blank row for a new vehicle type."""
        row = self.vehicle_types_table.rowCount()
        self.vehicle_types_table.insertRow(row)
        for col, val in enumerate(["", "0.00", "0.00", "0.00", "0.00"]):
            self.vehicle_types_table.setItem(row, col, QTableWidgetItem(val))
        self.vehicle_types_table.item(row, 0).setData(
            Qt.ItemDataRole.UserRole, None)

    def _delete_vehicle_type_row(self) -> None:
        """Remove the selected vehicle type row."""
        selected = self.vehicle_types_table.selectedIndexes()
        if not selected:
            QMessageBox.warning(
                self, "Warning", "Please select a vehicle type to delete.")
            return
        if (QMessageBox.question(self, "Confirm", "Delete selected vehicle type?")
                == QMessageBox.StandardButton.Yes):
            self.vehicle_types_table.removeRow(selected[0].row())

    def _move_vehicle_type_row(self, direction: int) -> None:
        """Move selected vehicle type row up/down to set display order."""
        selected = self.vehicle_types_table.selectedIndexes()
        if not selected:
            QMessageBox.warning(
                self, "Warning", "Please select a vehicle type row to move.")
            return

        source_row = selected[0].row()
        target_row = source_row + direction
        if target_row < 0 or target_row >= self.vehicle_types_table.rowCount():
            return

        col_count = self.vehicle_types_table.columnCount()
        source_vals = []
        target_vals = []
        source_original = None
        target_original = None

        for col in range(col_count):
            src_item = self.vehicle_types_table.item(source_row, col)
            tgt_item = self.vehicle_types_table.item(target_row, col)
            source_vals.append(src_item.text() if src_item else "")
            target_vals.append(tgt_item.text() if tgt_item else "")
            if col == 0:
                source_original = (
                    src_item.data(Qt.ItemDataRole.UserRole) if src_item else None
                )
                target_original = (
                    tgt_item.data(Qt.ItemDataRole.UserRole) if tgt_item else None
                )

        for col in range(col_count):
            src_new = QTableWidgetItem(target_vals[col])
            tgt_new = QTableWidgetItem(source_vals[col])
            if col == 0:
                src_new.setData(Qt.ItemDataRole.UserRole, target_original)
                tgt_new.setData(Qt.ItemDataRole.UserRole, source_original)
            self.vehicle_types_table.setItem(source_row, col, src_new)
            self.vehicle_types_table.setItem(target_row, col, tgt_new)

        self.vehicle_types_table.setCurrentCell(target_row, 0)

    def _save_vehicle_types(self) -> object:
        """Persist vehicle type pricing to vehicle_pricing_defaults."""
        def _fval(item) -> object:
            try:
                return float((item.text() if item else "0").replace(",", ""))
            except Exception:
                return 0.0

        try:
            cols = self._vehicle_pricing_table_columns()
            if not cols:
                raise RuntimeError(
                    "vehicle_pricing_defaults table was not found in this database."
                )

            rate_cols = self._vehicle_pricing_rate_columns(cols)
            order_col = self._ensure_vehicle_pricing_display_order_column(cols)
            has_charter_type_code = "charter_type_code" in cols
            has_is_active = "is_active" in cols

            with DatabaseContext(self.db, auto_commit=False) as cur:
                names_in_ui = []
                display_index = 0
                for row in range(self.vehicle_types_table.rowCount()):
                    name = (self.vehicle_types_table.item(row, 0).text().strip()
                            if self.vehicle_types_table.item(row, 0) else "")
                    if not name:
                        continue
                    display_index += 1
                    names_in_ui.append(name)
                    hourly = _fval(self.vehicle_types_table.item(row, 1))
                    pkg = _fval(self.vehicle_types_table.item(row, 2))
                    daily = _fval(self.vehicle_types_table.item(row, 3))
                    standby = _fval(self.vehicle_types_table.item(row, 4))
                    original = (self.vehicle_types_table.item(row, 0).data(
                        Qt.ItemDataRole.UserRole) if self.vehicle_types_table.item(
                        row, 0) else None)

                    update_fields = ["vehicle_type = %s"]
                    update_vals = [name]
                    if rate_cols["hourly"]:
                        update_fields.append(f"{rate_cols['hourly']} = %s")
                        update_vals.append(hourly)
                    if rate_cols["package"]:
                        update_fields.append(f"{rate_cols['package']} = %s")
                        update_vals.append(pkg)
                    if rate_cols["daily"]:
                        update_fields.append(f"{rate_cols['daily']} = %s")
                        update_vals.append(daily)
                    if rate_cols["standby"]:
                        update_fields.append(f"{rate_cols['standby']} = %s")
                        update_vals.append(standby)
                    if order_col:
                        update_fields.append(f"{order_col} = %s")
                        update_vals.append(display_index)
                    if has_is_active:
                        update_fields.append("is_active = TRUE")

                    where_clause = "vehicle_type = %s"
                    where_vals = [name]
                    if has_charter_type_code:
                        where_clause += " AND COALESCE(charter_type_code, '') = ''"

                    cur.execute(
                        f"""
                        UPDATE vehicle_pricing_defaults
                        SET {', '.join(update_fields)}
                        WHERE {where_clause}
                        """,
                        tuple(update_vals + where_vals),
                    )

                    if cur.rowcount == 0:
                        insert_cols = ["vehicle_type"]
                        insert_vals = [name]
                        if has_charter_type_code:
                            insert_cols.append("charter_type_code")
                            insert_vals.append("")
                        if rate_cols["hourly"]:
                            insert_cols.append(rate_cols["hourly"])
                            insert_vals.append(hourly)
                        if rate_cols["package"]:
                            insert_cols.append(rate_cols["package"])
                            insert_vals.append(pkg)
                        if rate_cols["daily"]:
                            insert_cols.append(rate_cols["daily"])
                            insert_vals.append(daily)
                        if rate_cols["standby"]:
                            insert_cols.append(rate_cols["standby"])
                            insert_vals.append(standby)
                        if order_col:
                            insert_cols.append(order_col)
                            insert_vals.append(display_index)
                        if has_is_active:
                            insert_cols.append("is_active")
                            insert_vals.append(True)

                        placeholders = ", ".join(["%s"] * len(insert_cols))
                        cur.execute(
                            f"""
                            INSERT INTO vehicle_pricing_defaults
                                ({', '.join(insert_cols)})
                            VALUES ({placeholders})
                            """,
                            tuple(insert_vals),
                        )

                    # Handle rename: delete old name if it changed
                    if original and original != name:
                        if has_charter_type_code:
                            cur.execute(
                                "DELETE FROM vehicle_pricing_defaults "
                                "WHERE vehicle_type = %s "
                                "AND COALESCE(charter_type_code, '') = ''",
                                (original,),
                            )
                        else:
                            cur.execute(
                                "DELETE FROM vehicle_pricing_defaults "
                                "WHERE vehicle_type = %s",
                                (original,),
                            )

                # Remove deleted rows
                if names_in_ui:
                    if has_charter_type_code:
                        cur.execute(
                            "DELETE FROM vehicle_pricing_defaults "
                            "WHERE COALESCE(charter_type_code, '') = '' "
                            "AND vehicle_type != ALL(%s)",
                            (names_in_ui,),
                        )
                    else:
                        cur.execute(
                            "DELETE FROM vehicle_pricing_defaults "
                            "WHERE vehicle_type != ALL(%s)",
                            (names_in_ui,),
                        )
                else:
                    if has_charter_type_code:
                        cur.execute(
                            "DELETE FROM vehicle_pricing_defaults "
                            "WHERE COALESCE(charter_type_code, '') = ''"
                        )
                    else:
                        cur.execute("DELETE FROM vehicle_pricing_defaults")

                self.db.conn.commit()

            # Invalidate the per-instance pricing cache on all open CharterFormWidget
            # instances so the next load picks up the updated pricing from DB.
            try:
                from desktop_app.charter_form_widget import CharterFormWidget
                CharterFormWidget._pricing_defaults_cache.clear()
            except Exception as _ce:
                logger.debug("Suppressed: pricing cache clear: %s", _ce)

            QMessageBox.information(
                self, "Success", "Vehicle types saved successfully.")
            self._load_vehicle_types()
        except Exception as e:
            logger.error(f"Failed to save vehicle types: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to save vehicle types: {e}")

    # ─────────────────── Charge Defaults Tab ───────────────────

    def _charge_defaults_reserved_names(self) -> set[str]:
        """Charge defaults that should remain system-managed, not editable."""
        return {
            "charter charge",
            "service fee",
            "beverage",
            "beverage order",
            "gst",
        }

    def _is_reserved_charge_default(self, name: str) -> bool:
        lower_name = str(name or "").strip().lower()
        if not lower_name:
            return False
        if lower_name in self._charge_defaults_reserved_names():
            return True
        return "beverage" in lower_name

    def _ensure_charge_defaults_table(self) -> None:
        """Create charge defaults table if missing; migrate old column names."""
        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS charter_charge_defaults (
                    id SERIAL PRIMARY KEY,
                    charge_name VARCHAR(200) NOT NULL,
                    type_label VARCHAR(50) NOT NULL,
                    default_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
                    is_taxable BOOLEAN NOT NULL DEFAULT TRUE,
                    display_order INTEGER NOT NULL DEFAULT 0,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )
            # Migrate old column names created by earlier drill_down_widgets schema
            cur.execute(
                """
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='charter_charge_defaults'
                          AND column_name='description'
                    ) AND NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='charter_charge_defaults'
                          AND column_name='charge_name'
                    ) THEN
                        ALTER TABLE charter_charge_defaults
                            RENAME COLUMN description TO charge_name;
                    END IF;
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='charter_charge_defaults'
                          AND column_name='charge_type'
                    ) AND NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='charter_charge_defaults'
                          AND column_name='type_label'
                    ) THEN
                        ALTER TABLE charter_charge_defaults
                            RENAME COLUMN charge_type TO type_label;
                    END IF;
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='charter_charge_defaults'
                          AND column_name='default_price'
                    ) AND NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='charter_charge_defaults'
                          AND column_name='default_amount'
                    ) THEN
                        ALTER TABLE charter_charge_defaults
                            RENAME COLUMN default_price TO default_amount;
                    END IF;
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='charter_charge_defaults'
                          AND column_name='default_listed'
                    ) AND NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='charter_charge_defaults'
                          AND column_name='is_taxable'
                    ) THEN
                        ALTER TABLE charter_charge_defaults
                            RENAME COLUMN default_listed TO is_taxable;
                    END IF;
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='charter_charge_defaults'
                          AND column_name='sort_order'
                    ) AND NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='charter_charge_defaults'
                          AND column_name='display_order'
                    ) THEN
                        ALTER TABLE charter_charge_defaults
                            RENAME COLUMN sort_order TO display_order;
                    END IF;
                END$$
                """
            )
            cur.execute(
                """
                ALTER TABLE charter_charge_defaults
                ADD COLUMN IF NOT EXISTS charge_name VARCHAR(200)
                """
            )
            cur.execute(
                """
                ALTER TABLE charter_charge_defaults
                ADD COLUMN IF NOT EXISTS is_taxable BOOLEAN NOT NULL DEFAULT TRUE
                """
            )
            cur.execute(
                """
                ALTER TABLE charter_charge_defaults
                ADD COLUMN IF NOT EXISTS display_order INTEGER NOT NULL DEFAULT 0
                """
            )

    def _create_charge_defaults_tab(self) -> object:
        """Editable list of optional charter charge defaults."""
        widget = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("<b>Manage Optional Charter Charge Defaults</b>"))
        layout.addWidget(
            QLabel(
                "This list powers Add Charge options. Auto-calculated lines "
                "(Charter Charge, Service Fee, GST, Beverage) are excluded."
            )
        )

        self.charge_defaults_table = QTableWidget()
        self.charge_defaults_table.setColumnCount(4)
        self.charge_defaults_table.setHorizontalHeaderLabels(
            ["Charge Name", "Type", "Default Amount", "GST"]
        )
        self.charge_defaults_table.setMinimumHeight(420)
        self.charge_defaults_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.charge_defaults_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        hdr = self.charge_defaults_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.charge_defaults_table.setColumnWidth(1, 110)
        self.charge_defaults_table.setColumnWidth(2, 130)
        self.charge_defaults_table.setColumnWidth(3, 90)
        layout.addWidget(self.charge_defaults_table, 1)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("➕ Add Charge")
        add_btn.clicked.connect(self._add_charge_default_row)
        btn_row.addWidget(add_btn)

        del_btn = QPushButton("🗑️ Delete Selected")
        del_btn.clicked.connect(self._delete_charge_default_row)
        btn_row.addWidget(del_btn)

        move_up_btn = QPushButton("⬆ Move Up")
        move_up_btn.clicked.connect(lambda: self._move_charge_default_row(-1))
        btn_row.addWidget(move_up_btn)

        move_down_btn = QPushButton("⬇ Move Down")
        move_down_btn.clicked.connect(lambda: self._move_charge_default_row(1))
        btn_row.addWidget(move_down_btn)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._load_charge_defaults_admin)
        btn_row.addWidget(refresh_btn)

        save_btn = QPushButton("💾 Save Changes")
        save_btn.clicked.connect(self._save_charge_defaults_admin)
        btn_row.addWidget(save_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        widget.setLayout(layout)
        self._load_charge_defaults_admin()
        return widget

    def _load_charge_defaults_admin(self) -> None:
        """Load editable charge defaults excluding system-managed lines."""
        try:
            self._ensure_charge_defaults_table()
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT id, charge_name, type_label, default_amount,
                           COALESCE(is_taxable, TRUE)
                    FROM charter_charge_defaults
                    WHERE COALESCE(is_active, TRUE) = TRUE
                    ORDER BY display_order, id
                    """
                )
                rows = cur.fetchall() or []

            filtered_rows = [
                row for row in rows if not self._is_reserved_charge_default(row[1])
            ]

            self.charge_defaults_table.setRowCount(len(filtered_rows))
            for row_idx, (row_id, name, type_label, amount, is_taxable) in enumerate(filtered_rows):
                name_item = QTableWidgetItem(str(name or ""))
                name_item.setData(Qt.ItemDataRole.UserRole, row_id)
                self.charge_defaults_table.setItem(row_idx, 0, name_item)
                self.charge_defaults_table.setItem(
                    row_idx, 1, QTableWidgetItem(str(type_label or "Fixed"))
                )
                self.charge_defaults_table.setItem(
                    row_idx, 2, QTableWidgetItem(f"{float(amount or 0.0):.2f}")
                )
                self.charge_defaults_table.setItem(
                    row_idx,
                    3,
                    QTableWidgetItem("GST" if bool(is_taxable) else "No GST"),
                )
        except Exception as e:
            logger.error(f"Failed to load charge defaults: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to load charge defaults: {e}"
            )

    def _add_charge_default_row(self) -> None:
        """Insert a blank charge default row."""
        row = self.charge_defaults_table.rowCount()
        self.charge_defaults_table.insertRow(row)
        self.charge_defaults_table.setItem(row, 0, QTableWidgetItem(""))
        self.charge_defaults_table.setItem(row, 1, QTableWidgetItem("Fixed"))
        self.charge_defaults_table.setItem(row, 2, QTableWidgetItem("0.00"))
        self.charge_defaults_table.setItem(row, 3, QTableWidgetItem("GST"))
        self.charge_defaults_table.setCurrentCell(row, 0)

    def _delete_charge_default_row(self) -> None:
        """Delete selected charge default row from the grid."""
        selected = self.charge_defaults_table.selectedIndexes()
        if not selected:
            QMessageBox.warning(
                self, "Warning", "Please select a charge default to delete."
            )
            return
        if (
            QMessageBox.question(self, "Confirm", "Delete selected charge default?")
            == QMessageBox.StandardButton.Yes
        ):
            self.charge_defaults_table.removeRow(selected[0].row())

    def _move_charge_default_row(self, direction: int) -> None:
        """Move selected charge-default row up/down."""
        selected = self.charge_defaults_table.selectedIndexes()
        if not selected:
            QMessageBox.warning(
                self, "Warning", "Please select a charge row to move."
            )
            return

        source_row = selected[0].row()
        target_row = source_row + direction
        if target_row < 0 or target_row >= self.charge_defaults_table.rowCount():
            return

        col_count = self.charge_defaults_table.columnCount()
        source_vals = []
        target_vals = []
        source_id = None
        target_id = None
        for col in range(col_count):
            src_item = self.charge_defaults_table.item(source_row, col)
            tgt_item = self.charge_defaults_table.item(target_row, col)
            source_vals.append(src_item.text() if src_item else "")
            target_vals.append(tgt_item.text() if tgt_item else "")
            if col == 0:
                source_id = src_item.data(Qt.ItemDataRole.UserRole) if src_item else None
                target_id = tgt_item.data(Qt.ItemDataRole.UserRole) if tgt_item else None

        for col in range(col_count):
            src_new = QTableWidgetItem(target_vals[col])
            tgt_new = QTableWidgetItem(source_vals[col])
            if col == 0:
                src_new.setData(Qt.ItemDataRole.UserRole, target_id)
                tgt_new.setData(Qt.ItemDataRole.UserRole, source_id)
            self.charge_defaults_table.setItem(source_row, col, src_new)
            self.charge_defaults_table.setItem(target_row, col, tgt_new)

        self.charge_defaults_table.setCurrentCell(target_row, 0)

    def _save_charge_defaults_admin(self) -> None:
        """Save admin charge defaults while preserving system-managed lines."""
        try:
            self._ensure_charge_defaults_table()

            rows_to_save = []
            reserved_entries = []
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT charge_name, type_label, default_amount,
                           COALESCE(is_taxable, TRUE),
                           COALESCE(display_order, 0)
                    FROM charter_charge_defaults
                    WHERE COALESCE(is_active, TRUE) = TRUE
                    ORDER BY display_order, id
                    """
                )
                for name, type_label, amount, is_taxable, display_order in cur.fetchall() or []:
                    if self._is_reserved_charge_default(name):
                        reserved_entries.append(
                            (
                                str(name or "").strip(),
                                str(type_label or "Fixed").strip(),
                                float(amount or 0.0),
                                bool(is_taxable),
                                int(display_order or 0),
                            )
                        )

            seen_names = set()
            for row_idx in range(self.charge_defaults_table.rowCount()):
                name = (
                    self.charge_defaults_table.item(row_idx, 0).text().strip()
                    if self.charge_defaults_table.item(row_idx, 0)
                    else ""
                )
                type_label = (
                    self.charge_defaults_table.item(row_idx, 1).text().strip()
                    if self.charge_defaults_table.item(row_idx, 1)
                    else "Fixed"
                )
                amount_text = (
                    self.charge_defaults_table.item(row_idx, 2).text().strip()
                    if self.charge_defaults_table.item(row_idx, 2)
                    else "0.00"
                )
                gst_text = (
                    self.charge_defaults_table.item(row_idx, 3).text().strip().lower()
                    if self.charge_defaults_table.item(row_idx, 3)
                    else "gst"
                )

                if not name:
                    continue
                if self._is_reserved_charge_default(name):
                    continue

                key = name.lower()
                if key in seen_names:
                    raise ValueError(f"Duplicate charge name in grid: {name}")
                seen_names.add(key)

                try:
                    amount_value = float(amount_text.replace(",", "") or 0.0)
                except Exception:
                    amount_value = 0.0

                is_taxable = gst_text not in {
                    "no gst",
                    "nogst",
                    "no",
                    "n",
                    "false",
                    "0",
                    "exempt",
                }
                rows_to_save.append(
                    (name, type_label or "Fixed", amount_value, is_taxable)
                )

            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("DELETE FROM charter_charge_defaults")

                display_index = 0
                for name, type_label, amount_value, is_taxable, _order in reserved_entries:
                    display_index += 1
                    cur.execute(
                        """
                        INSERT INTO charter_charge_defaults (
                            charge_name, type_label, default_amount,
                            is_taxable, display_order, is_active, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, TRUE, NOW())
                        """,
                        (name, type_label, amount_value, is_taxable, display_index),
                    )

                for name, type_label, amount_value, is_taxable in rows_to_save:
                    display_index += 1
                    cur.execute(
                        """
                        INSERT INTO charter_charge_defaults (
                            charge_name, type_label, default_amount,
                            is_taxable, display_order, is_active, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, TRUE, NOW())
                        """,
                        (name, type_label, amount_value, is_taxable, display_index),
                    )

                self.db.conn.commit()

            QMessageBox.information(
                self, "Success", "Charge defaults saved successfully."
            )
            self._load_charge_defaults_admin()
        except Exception as e:
            try:
                self.db.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            logger.error(f"Failed to save charge defaults: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to save charge defaults: {e}"
            )

    def _create_error_log_tab(self) -> object:
        """Create the Error Log tab"""
        from error_log_viewer import ErrorLogViewer

        return ErrorLogViewer(self.db, self)
