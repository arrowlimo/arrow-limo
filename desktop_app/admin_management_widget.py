"""
Admin & User Management Widget
System administration, user management, settings, and backups
Ported from frontend/src/views/Admin.vue
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QComboBox, QTabWidget, QTextEdit,
    QSpinBox, QCheckBox, QFileDialog
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor
import psycopg2
from datetime import datetime
import subprocess
import os
import hashlib
import binascii


class AdminManagementWidget(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()

    def init_ui(self):
        """Initialize admin dashboard UI"""
        layout = QVBoxLayout()

        # Tab widget for different admin sections
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_overview_tab(), "📊 Overview")
        self.tabs.addTab(self._create_users_tab(), "👥 Users")
        self.tabs.addTab(self._create_settings_tab(), "⚙️ Settings")
        self.tabs.addTab(self._create_run_types_tab(), "🏃 Run Types")
        self.tabs.addTab(self._create_audit_tab(), "📋 Audit Log")
        self.tabs.addTab(self._create_backup_tab(), "💾 Backup & Restore")
        self.tabs.addTab(self._create_error_log_tab(), "🐛 Error Log")

        layout.addWidget(self.tabs)
        self.setLayout(layout)

    def _create_overview_tab(self):
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
        self.activity_table.setHorizontalHeaderLabels(["Timestamp", "User", "Action", "Details"])
        self.activity_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        activity_layout.addWidget(self.activity_table)

        activity_group.setLayout(activity_layout)
        layout.addWidget(activity_group)

        # Load statistics
        self._load_overview_stats(total_bookings, total_customers, total_employees, monthly_revenue, active_vehicles)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def _create_users_tab(self):
        """Create the Users tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        # User list
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(6)
        self.users_table.setHorizontalHeaderLabels(["Username", "Email", "Role", "Department", "Status", "Last Login"])
        self.users_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
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
        self.user_role.addItems(["admin", "dispatcher", "driver", "accountant", "viewer"])
        self.user_department = QComboBox()
        self.user_department.addItems(["operations", "dispatch", "accounting", "management"])
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
        form_layout.addRow("Password (if new)", self.user_password)
        form_layout.addRow("Role", self.user_role)
        form_layout.addRow("Department", self.user_department)
        form_layout.addRow("Status", self.user_status)
        form_layout.addRow(button_layout)

        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        self.load_users()
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def _hash_password(self, password: str, iterations: int = 100_000) -> str:
        """Generate a PBKDF2-SHA256 password hash (salted)."""
        try:
            salt = os.urandom(16)
            dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
            return f"pbkdf2_sha256${iterations}${binascii.hexlify(salt).decode()}${binascii.hexlify(dk).decode()}"
        except Exception as e:
            raise RuntimeError(f"Password hashing failed: {e}")

    def _log_audit(self, action: str, details: str):
        """Best-effort audit logger. Fails silently to avoid blocking UI."""
        try:
            cur = self.db.get_cursor()
            try:
                cur.execute(
                    "INSERT INTO security_audit (action, details, created_at) VALUES (%s, %s, NOW())",
                    (action, details)
                )
                self.db.commit()
                return
            except Exception:
                pass
            try:
                cur.execute(
                    "INSERT INTO security_audit (action, details) VALUES (%s, %s)",
                    (action, details)
                )
                self.db.commit()
            except Exception:
                # swallow audit errors
                try:
                    self.db.rollback()
                except Exception:
                    pass
        except Exception:
            pass

    def _create_settings_tab(self):
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

    def _create_audit_tab(self):
        """Create the Audit Log tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Audit log table
        self.audit_table = QTableWidget()
        self.audit_table.setColumnCount(5)
        self.audit_table.setHorizontalHeaderLabels(["Timestamp", "User", "Table", "Action", "Details"])
        self.audit_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.audit_table)

        # Filter buttons
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        self.audit_filter_action = QComboBox()
        self.audit_filter_action.addItems(["All", "add_user", "update_user", "delete_user", "backup", "restore"])
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

    def _create_backup_tab(self):
        """Create the Backup & Restore tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        backup_group = QGroupBox("Database Backup & Restore")
        backup_layout = QVBoxLayout()

        info_label = QLabel("⚠️ Backup operations should be done carefully. Always keep backups of important data.")
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
        self.backups_table.setHorizontalHeaderLabels(["Backup Time", "Size", "Type", "Status"])
        self.backups_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        history_layout.addWidget(self.backups_table)

        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    # Implementation methods

    def _load_overview_stats(self, bookings_field, customers_field, employees_field, revenue_field, vehicles_field):
        """Load overview statistics"""
        try:
            cur = self.db.get_cursor()

            cur.execute("SELECT COUNT(*) FROM charters")
            bookings_field.setText(str(cur.fetchone()[0]))

            cur.execute("SELECT COUNT(*) FROM clients")
            customers_field.setText(str(cur.fetchone()[0]))

            cur.execute("SELECT COUNT(*) FROM employees")
            employees_field.setText(str(cur.fetchone()[0]))

            # Monthly revenue (PostgreSQL syntax)
            cur.execute(
                """
                SELECT COALESCE(SUM(total_amount_due), 0)
                FROM charters
                WHERE DATE_TRUNC('month', charter_date) = DATE_TRUNC('month', CURRENT_DATE)
                """
            )
            revenue = cur.fetchone()[0]
            revenue_field.setText(f"${revenue:,.2f}" if revenue else "$0.00")

            cur.execute("SELECT COUNT(*) FROM vehicles WHERE operational_status = 'Active'")
            vehicles_field.setText(str(cur.fetchone()[0]))

        except Exception as e:
            # Ensure aborted transactions don't cascade to other widgets
            try:
                self.db.rollback()
            except Exception:
                pass
            print(f"Overview stats error: {e}")

    def load_users(self):
        """Load users from database"""
        try:
            cur = self.db.get_cursor()
            cur.execute(
                """
                SELECT username, email, role, status, last_login, permissions
                FROM users
                ORDER BY username
                LIMIT 100
                """
            )
            users = cur.fetchall()
            # Adjust columns to available fields
            self.users_table.setRowCount(len(users))
            for row_idx, (username, email, role, status, last_login, permissions) in enumerate(users):
                dept = self._infer_department(role, permissions)
                self.users_table.setItem(row_idx, 0, QTableWidgetItem(username or ""))
                self.users_table.setItem(row_idx, 1, QTableWidgetItem(email or ""))
                self.users_table.setItem(row_idx, 2, QTableWidgetItem(role or ""))
                self.users_table.setItem(row_idx, 3, QTableWidgetItem(dept))
                self.users_table.setItem(row_idx, 4, QTableWidgetItem(status or ""))
                self.users_table.setItem(row_idx, 5, QTableWidgetItem(str(last_login or "")))
        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
            print(f"Load users error: {e}")

    def load_selected_user(self):
        """Load selected user data"""
        selected = self.users_table.selectedItems()
        if selected:
            row = self.users_table.row(selected[0])
            self.user_username.setText(self.users_table.item(row, 0).text())
            self.user_email.setText(self.users_table.item(row, 1).text())
            self.user_role.setCurrentText(self.users_table.item(row, 2).text())
            # Map displayed department back to a reasonable default
            dept_val = self.users_table.item(row, 3).text()
            if dept_val in ["operations", "dispatch", "accounting", "management"]:
                self.user_department.setCurrentText(dept_val)
            else:
                self.user_department.setCurrentText("operations")
            self.user_status.setCurrentText(self.users_table.item(row, 4).text())

    def add_user(self):
        """Add new user"""
        # Validation
        if not self.user_username.text().strip():
            QMessageBox.warning(self, "Missing Fields", "Username is required.")
            self.user_username.setFocus()
            return
        
        if not self.user_email.text().strip():
            QMessageBox.warning(self, "Missing Fields", "Email is required.")
            self.user_email.setFocus()
            return
        
        try:
            cur = self.db.get_cursor()
            
            # Check if username already exists
            cur.execute("SELECT user_id FROM users WHERE username = %s", (self.user_username.text().strip(),))
            if cur.fetchone():
                QMessageBox.warning(self, "Duplicate Username", "Username already exists. Please choose another.")
                return
            
            # Determine password (provided or default)
            provided_password = self.user_password.text().strip()
            password_plain = provided_password if provided_password else "changeme123"
            password_hash = self._hash_password(password_plain)

            # Insert new user
            cur.execute("""
                INSERT INTO users (username, email, role, department, status, password_hash)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING user_id
            """, (
                self.user_username.text().strip(),
                self.user_email.text().strip(),
                self.user_role.currentText(),
                self.user_department.currentText(),
                self.user_status.currentText(),
                password_hash
            ))
            
            new_user_id = cur.fetchone()[0]
            self.db.commit()
            
            if provided_password:
                msg = f"User created successfully!\n\nUser ID: {new_user_id}"
            else:
                msg = (
                    f"User created successfully!\n\nUser ID: {new_user_id}\n\n"
                    f"Default password: changeme123\n(User should change on first login)"
                )
            QMessageBox.information(self, "Success", msg)
            self._log_audit("add_user", f"username={self.user_username.text().strip()} id={new_user_id}")
            
            # Clear form and reload
            self.user_username.setText("")
            self.user_email.setText("")
            self.user_password.setText("")
            self.load_users()
            
        except psycopg2.Error as e:
            self.db.rollback()
            QMessageBox.critical(self, "Database Error", f"Failed to add user:\n\n{e.diag.message_primary if hasattr(e, 'diag') else str(e)}")
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Error", f"Failed to add user:\n\n{str(e)}")

    def update_user(self):
        """Update selected user"""
        row = self.users_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a user to update.")
            return
        
        try:
            # Use original username from the selected row as identifier
            original_username = self.users_table.item(row, 0).text()
            
            cur = self.db.get_cursor()
            cur.execute("""
                UPDATE users 
                SET username = %s, email = %s, role = %s, department = %s, status = %s
                WHERE username = %s
            """, (
                self.user_username.text().strip(),
                self.user_email.text().strip(),
                self.user_role.currentText(),
                self.user_department.currentText(),
                self.user_status.currentText(),
                original_username
            ))
            
            self.db.commit()
            QMessageBox.information(self, "Success", f"User '{original_username}' updated successfully")
            self._log_audit("update_user", f"username={original_username}")
            self.load_users()
            
        except psycopg2.Error as e:
            self.db.rollback()
            QMessageBox.critical(self, "Database Error", f"Failed to update user:\n\n{e.diag.message_primary if hasattr(e, 'diag') else str(e)}")
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Error", f"Failed to update user:\n\n{str(e)}")

    def delete_user(self):
        """Delete selected user"""
        row = self.users_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a user to delete.")
            return
        
        username = self.users_table.item(row, 0).text()
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete user '{username}'?\n\n(This will set status to 'inactive', not hard delete)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.No:
            return
        
        try:
            cur = self.db.get_cursor()
            
            # Soft delete: set status to inactive
            cur.execute("""
                UPDATE users 
                SET status = 'inactive', updated_at = NOW()
                WHERE username = %s
            """, (username,))
            
            self.db.commit()
            QMessageBox.information(self, "Success", f"User '{username}' has been deactivated")
            self._log_audit("delete_user", f"username={username}")
            self.load_users()
            
        except psycopg2.Error as e:
            self.db.rollback()
            QMessageBox.critical(self, "Database Error", f"Failed to delete user:\n\n{e.diag.message_primary if hasattr(e, 'diag') else str(e)}")
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Error", f"Failed to delete user:\n\n{str(e)}")

    def load_settings(self):
        """Load system settings"""
        self.company_name.setText("Arrow Limousine")
        self.company_phone.setText("")
        self.company_email.setText("info@arrowlimousine.ca")
        self.timezone.setCurrentText("MST")
        self.backup_schedule.setCurrentText("Daily")

    def save_settings(self):
        """Save system settings"""
        QMessageBox.information(self, "Settings Saved", "System settings updated successfully.")

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
                text = ",".join([f"{k}:{v}" for k, v in permissions.items()]).lower()
            except Exception:
                text = str(permissions).lower()
        else:
            text = str(permissions).lower()
        if "dispatch" in text or role == "dispatcher":
            return "dispatch"
        if "account" in text or role in ("accountant", "accounting"):
            return "accounting"
        if role in ("admin", "manager", "management") or "admin" in text or "manage" in text:
            return "management"
        if role in ("driver", "operations") or "driver" in text or "ops" in text:
            return "operations"
        return "operations"

    def clear_audit_log(self):
        """Clear audit log"""
        reply = QMessageBox.question(self, "Confirm", "Clear audit log?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            cur = self.db.get_cursor()
            try:
                cur.execute("DELETE FROM security_audit")
            except Exception:
                cur.execute("TRUNCATE TABLE security_audit")
            self.db.commit()
            QMessageBox.information(self, "Success", "Audit log cleared.")
            self.load_audit_log()
        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
            QMessageBox.warning(self, "Error", f"Failed to clear audit log: {e}")

    def export_audit_log(self):
        """Export audit log"""
        path, _ = QFileDialog.getSaveFileName(self, "Save Audit Log", "", "CSV Files (*.csv)")
        if not path:
            return
        try:
            cur = self.db.get_cursor()
            cur.execute("SELECT created_at, action, details FROM security_audit ORDER BY created_at DESC LIMIT 1000")
            rows = cur.fetchall()
            import csv
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Action", "Details"])
                for r in rows:
                    writer.writerow([str(r[0] or ""), r[1] or "", r[2] or ""]) 
            QMessageBox.information(self, "Success", f"Audit log exported to {path}")
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.warning(self, "Error", f"Failed to export: {e}")

    def load_audit_log(self):
        """Load audit entries into table with optional action filter."""
        try:
            action_filter = None
            if hasattr(self, 'audit_filter_action'):
                val = self.audit_filter_action.currentText()
                action_filter = None if val == "All" else val
            cur = self.db.get_cursor()
            if action_filter:
                cur.execute(
                    "SELECT created_at, action, details FROM security_audit WHERE action = %s ORDER BY created_at DESC LIMIT 500",
                    (action_filter,)
                )
            else:
                cur.execute("SELECT created_at, action, details FROM security_audit ORDER BY created_at DESC LIMIT 500")
            rows = cur.fetchall()
            self.audit_table.setRowCount(len(rows))
            for i, (ts, act, det) in enumerate(rows):
                self.audit_table.setItem(i, 0, QTableWidgetItem(str(ts or "")))
                self.audit_table.setItem(i, 1, QTableWidgetItem("admin"))
                self.audit_table.setItem(i, 2, QTableWidgetItem("users" if act in ("add_user","update_user","delete_user") else "system"))
                self.audit_table.setItem(i, 3, QTableWidgetItem(act or ""))
                self.audit_table.setItem(i, 4, QTableWidgetItem(det or ""))
        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
            # Show empty table on error
            self.audit_table.setRowCount(0)

    def create_backup(self):
        """Create database backup"""
        import os
        import subprocess
        from datetime import datetime
        
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = "L:/limo/backups"
        os.makedirs(backup_dir, exist_ok=True)
        backup_file = os.path.join(backup_dir, f"almsdata_backup_{timestamp}.sql")
        
        try:
            # Execute pg_dump - use shell to find it automatically
            cmd = f'pg_dump -h localhost -U postgres -d almsdata -f "{backup_file}"'
            
            # Set PGPASSWORD environment variable
            env = os.environ.copy()
            env["PGPASSWORD"] = "***REMOVED***"
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True, shell=True)
            
            if result.returncode == 0:
                file_size_mb = os.path.getsize(backup_file) / (1024 * 1024)
                QMessageBox.information(
                    self, "Backup Complete",
                    f"Database backup created successfully!\n\n"
                    f"File: {backup_file}\n"
                    f"Size: {file_size_mb:.2f} MB\n"
                    f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
            else:
                error_msg = result.stderr if result.stderr else "Unknown error"
                QMessageBox.critical(
                    self, "Backup Failed",
                    f"pg_dump failed:\n\n{error_msg}\n\n"
                    f"Make sure PostgreSQL is installed and pg_dump is in your system PATH.\n"
                    f"You can also add PostgreSQL\\bin to your PATH environment variable."
                )
        except FileNotFoundError:
            QMessageBox.critical(
                self, "pg_dump Not Found",
                "Could not find pg_dump command.\n\n"
                "PostgreSQL tools must be installed and in system PATH.\n\n"
                "Typical locations:\n"
                "• C:\\Program Files\\PostgreSQL\\16\\bin\n"
                "• C:\\Program Files\\PostgreSQL\\15\\bin\n\n"
                "Add the bin folder to your system PATH environment variable."
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", 
                f"Backup failed:\n\n{str(e)}\n\n"
                f"Backup folder: {backup_dir}\n"
                f"Make sure you have write permissions."
            )

    def restore_backup(self):
        """Restore from backup"""
        import subprocess
        import os
        
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Backup", "L:/limo/backups", 
            "Database Files (*.dump *.sql);;All Files (*.*)"
        )
        
        if not path:
            return
        
        # Confirm restore
        reply = QMessageBox.question(
            self, "Confirm Restore",
            f"⚠️ WARNING: This will OVERWRITE the current database!\n\n"
            f"Restore from:\n{path}\n\n"
            f"All current data will be replaced with backup data.\n"
            f"Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.No:
            return
        
        try:
            # Execute psql to restore (for .sql files)
            if path.endswith('.sql'):
                cmd = [
                    "psql",
                    "-h", "localhost",
                    "-U", "postgres",
                    "-d", "almsdata",
                    "-f", path,
                    "--no-password"
                ]
            else:
                # Use pg_restore for .dump files
                cmd = [
                    "pg_restore",
                    "-h", "localhost",
                    "-U", "postgres",
                    "-d", "almsdata",
                    "--clean",
                    "--if-exists",
                    path,
                    "--no-password"
                ]
            
            # Set PGPASSWORD environment variable
            env = os.environ.copy()
            env["PGPASSWORD"] = "***REMOVED***"
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                QMessageBox.information(
                    self, "Restore Complete",
                    f"Database restored successfully!\n\n"
                    f"From: {os.path.basename(path)}\n\n"
                    f"⚠️ Application should be restarted to reload data."
                )
            else:
                QMessageBox.critical(
                    self, "Restore Failed",
                    f"Database restore failed:\n\n{result.stderr[:500]}"
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Restore failed:\n\n{str(e)}")

    def download_backup(self):
        """Download latest backup"""
        path, _ = QFileDialog.getSaveFileName(self, "Save Backup", "", "Database Files (*.dump)")
        if path:
            QMessageBox.information(self, "Download", f"Backup saved to {path}")
    
    def _create_run_types_tab(self):
        """Create the Run Types manager tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Title
        layout.addWidget(QLabel("<b>Manage Charter Run Types</b>"))
        layout.addWidget(QLabel("Edit run types for Charter and Route selection"))

        # Table for run types
        self.run_types_table = QTableWidget()
        self.run_types_table.setColumnCount(3)
        self.run_types_table.setHorizontalHeaderLabels(["Run Type", "Active", "Display Order"])
        self.run_types_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.run_types_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
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

    def _load_run_types(self):
        """Load run types from database into table"""
        try:
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT id, run_type_name, is_active, display_order
                FROM charter_run_types
                ORDER BY display_order, run_type_name
            """)
            rows = cur.fetchall()
            cur.close()

            self.run_types_table.setRowCount(len(rows))

            for row_idx, (rid, name, active, order) in enumerate(rows):
                # Run Type name
                name_item = QTableWidgetItem(name)
                self.run_types_table.setItem(row_idx, 0, name_item)

                # Active checkbox
                active_item = QTableWidgetItem()
                active_item.setCheckState(Qt.CheckState.Checked if active else Qt.CheckState.Unchecked)
                self.run_types_table.setItem(row_idx, 1, active_item)

                # Display order
                order_item = QTableWidgetItem(str(order or ""))
                self.run_types_table.setItem(row_idx, 2, order_item)

                # Store ID for delete operations
                name_item.setData(Qt.ItemDataRole.UserRole, rid)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load run types: {e}")

    def _add_run_type(self):
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

    def _delete_run_type(self):
        """Delete selected run type"""
        selected = self.run_types_table.selectedIndexes()
        if not selected:
            QMessageBox.warning(self, "Warning", "Please select a run type to delete")
            return

        if QMessageBox.question(self, "Confirm", "Delete selected run type?") == QMessageBox.StandardButton.Yes:
            row = selected[0].row()
            self.run_types_table.removeRow(row)

    def _save_run_types(self):
        """Save run type changes to database"""
        try:
            cur = self.db.get_cursor()

            # Disable foreign key checks temporarily
            cur.execute("SET CONSTRAINTS ALL DEFERRED")

            for row in range(self.run_types_table.rowCount()):
                name = self.run_types_table.item(row, 0).text().strip()
                active = self.run_types_table.item(row, 1).checkState() == Qt.CheckState.Checked
                try:
                    order = int(self.run_types_table.item(row, 2).text()) if self.run_types_table.item(row, 2).text() else 999
                except:
                    order = 999

                if not name:
                    continue

                rid = self.run_types_table.item(row, 0).data(Qt.ItemDataRole.UserRole)

                if rid:
                    # Update existing
                    cur.execute("""
                        UPDATE charter_run_types
                        SET run_type_name = %s, is_active = %s, display_order = %s
                        WHERE id = %s
                    """, (name, active, order, rid))
                else:
                    # Insert new
                    cur.execute("""
                        INSERT INTO charter_run_types (run_type_name, is_active, display_order)
                        VALUES (%s, %s, %s)
                    """, (name, active, order))

            self.db.connection.commit()
            QMessageBox.information(self, "Success", "Run types saved successfully")
            self._load_run_types()
        except Exception as e:
            try:
                self.db.connection.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Failed to save run types: {e}")
    
    def _create_error_log_tab(self):
        """Create the Error Log tab"""
        from desktop_app.error_log_viewer import ErrorLogViewer
        return ErrorLogViewer(self.db, self)
