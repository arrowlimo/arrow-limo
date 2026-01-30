"""
Login Dialog: PyQt6 UI for user authentication
Handles: username/password entry, remember-me, error handling, styling
"""

from typing import Optional, Dict, Callable
import json
import os
import webbrowser
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QCheckBox, QMessageBox, QFrame, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont, QColor
from PyQt6.QtWidgets import QGraphicsDropShadowEffect
from pathlib import Path

from login_manager import LoginManager, AuthenticationError, AccountLockedError


class LoginDialog(QDialog):
    """PyQt6 login dialog with database authentication"""
    
    # Signal emitted when login succeeds
    login_successful = pyqtSignal(dict)  # Passes auth_user dict
    
    def __init__(self, parent=None, active_db_target: str = "local", set_db_callback: Optional[Callable[[str], None]] = None):
        super().__init__(parent)
        self.login_manager = LoginManager()
        self.auth_user = None
        self.prefs_file = Path.home() / ".limo_login_prefs.json"
        self.active_db_target = (active_db_target or "local").lower().strip()
        self.set_db_callback = set_db_callback
        self.init_ui()
        # Sync DB selection to env + login manager on startup
        self._on_db_target_changed(self.active_db_target)
        self._load_saved_login()
        self.check_remember_token()
    
    def init_ui(self):
        """Build login form UI"""
        self.setWindowTitle('Arrow Limousine Management System - Login')
        self.setFixedSize(560, 700)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setFocus()
        self.raise_()
        self.activateWindow()
        
        # Apply modern styling
        self.setStyleSheet('''
            QDialog {
                background-color: #0b1727;
            }
            QFrame#CardFrame {
                background: rgba(255, 255, 255, 0.97);
                border-radius: 14px;
                border: 1px solid rgba(0, 0, 0, 0.1);
            }
            QLineEdit {
                padding: 6px 10px;
                border: 1px solid #d0d7e2;
                border-radius: 6px;
                font-size: 14px;
                background-color: #ffffff;
                selection-background-color: #3b82f6;
                min-height: 32px;
                max-height: 32px;
            }
            QLineEdit:focus {
                border: 2px solid #3b82f6;
                outline: none;
            }
            QPushButton {
                padding: 8px 20px;
                border: none;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton#LoginButton {
                background-color: #2563eb;
                color: white;
                min-height: 32px;
            }
            QPushButton#LoginButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton#LoginButton:pressed {
                background-color: #1e40af;
            }
            QPushButton#CancelButton {
                background-color: #e5e7eb;
                color: #111827;
                min-height: 32px;
            }
            QPushButton#CancelButton:hover {
                background-color: #d1d5db;
            }
            QCheckBox {
                color: #374151;
                font-size: 12px;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #ffffff;
                border: 1px solid #d0d7e2;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #2563eb;
                border: 1px solid #2563eb;
                border-radius: 3px;
            }
            QRadioButton {
                color: #374151;
                font-size: 12px;
                spacing: 4px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
            QRadioButton::indicator:unchecked {
                background-color: #ffffff;
                border: 1px solid #d0d7e2;
                border-radius: 8px;
            }
            QRadioButton::indicator:checked {
                background-color: #2563eb;
                border: 1px solid #2563eb;
                border-radius: 8px;
            }
        ''')
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Centered card container
        card_container = QHBoxLayout()
        card_container.setContentsMargins(0, 40, 0, 0)
        
        # Card frame
        card = QFrame()
        card.setObjectName('CardFrame')
        card.setFixedSize(400, 580)
        card_layout = QVBoxLayout()
        card_layout.setSpacing(8)
        card_layout.setContentsMargins(32, 28, 32, 28)
        
        # Centered title with logo at top of card
        title_row = QHBoxLayout()
        title_row.setSpacing(12)
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        # Logo
        logo = QLabel()
        logo_pixmap = QPixmap(r'L:\limo\photo\arrow.ico')
        if not logo_pixmap.isNull():
            logo.setPixmap(logo_pixmap.scaledToWidth(100, Qt.TransformationMode.SmoothTransformation))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_row.addWidget(logo)
        
        # Title text with ALMS in gold, stacked vertically
        title_label = QLabel()
        title_label.setText(
            '<div style="margin:0; padding:0;">'
            '<div style="margin:0; padding:0; line-height:18px;">'
            '<span style="color: #d4af37; font-weight: bold; font-size: 30px; letter-spacing: 2px;">A</span>'
            '<span style="color: #1f2937; font-weight: bold; font-size: 30px; letter-spacing: 2px;">RROW</span>'
            '</div>'
            '<div style="margin:0; padding:0; line-height:18px;">'
            '<span style="color: #d4af37; font-weight: bold; font-size: 30px; letter-spacing: 2px;">L</span>'
            '<span style="color: #1f2937; font-weight: bold; font-size: 30px; letter-spacing: 2px;">IMOUSINE</span>'
            '</div>'
            '<div style="margin:0; padding:0; line-height:18px;">'
            '<span style="color: #d4af37; font-weight: bold; font-size: 30px; letter-spacing: 2px;">M</span>'
            '<span style="color: #1f2937; font-weight: bold; font-size: 30px; letter-spacing: 2px;">ANAGEMENT</span>'
            '</div>'
            '<div style="margin:0; padding:0; line-height:18px;">'
            '<span style="color: #d4af37; font-weight: bold; font-size: 30px; letter-spacing: 2px;">S</span>'
            '<span style="color: #1f2937; font-weight: bold; font-size: 30px; letter-spacing: 2px;">YSTEM</span>'
            '</div>'
            '</div>'
        )
        title_label.setFont(QFont('Segoe UI', 24))
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        title_label.setMinimumWidth(250)
        title_label.setStyleSheet("background: transparent; margin: 0; padding: 0;")
        title_row.addWidget(title_label)
        
        title_row.addStretch()
        
        card_layout.addLayout(title_row)
        card_layout.addSpacing(2)
        
        # Username field
        self.username_label = QLabel('Username')
        self.username_label.setFont(QFont('Segoe UI', 12, QFont.Weight.Medium))
        self.username_label.setStyleSheet("color: #374151;")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText('Enter your username')
        self.username_input.setMaximumWidth(280)
        self.username_input.returnPressed.connect(self.handle_login)
        
        card_layout.addWidget(self.username_label)
        card_layout.addWidget(self.username_input)
        card_layout.addSpacing(4)
        
        # Password field
        self.password_label = QLabel('Password')
        self.password_label.setFont(QFont('Segoe UI', 12, QFont.Weight.Medium))
        self.password_label.setStyleSheet("color: #374151;")
        
        password_row = QHBoxLayout()
        password_row.setSpacing(6)
        password_row.setContentsMargins(0, 0, 0, 0)
        password_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText('Enter your password')
        self.password_input.setMaximumWidth(240)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self.handle_login)
        
        self.view_password_btn = QPushButton('👁️')
        self.view_password_btn.setMaximumWidth(40)
        self.view_password_btn.setStyleSheet('''
            QPushButton {
                background-color: #f3f4f6;
                border: 1px solid #d0d7e2;
                border-radius: 6px;
                font-size: 14px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #e5e7eb;
            }
        ''')
        self.view_password_btn.clicked.connect(self._toggle_password_view)
        self.password_view_visible = False
        
        password_row.addWidget(self.password_input)
        password_row.addWidget(self.view_password_btn)
        
        card_layout.addWidget(self.password_label)
        card_layout.addLayout(password_row)
        card_layout.addSpacing(12)
        
        # Store password row for visibility control
        self.password_row_layout = password_row
        
        # Remember me checkbox row
        remember_row = QHBoxLayout()
        remember_row.setSpacing(12)
        remember_row.setContentsMargins(0, 0, 0, 0)
        remember_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.remember_checkbox = QCheckBox('Remember me')
        self.remember_checkbox.setStyleSheet("color: #374151; font-size: 11px; spacing: 6px;")
        remember_row.addWidget(self.remember_checkbox)
        card_layout.addLayout(remember_row)
        card_layout.addSpacing(8)
        
        # Database target selection row
        options_row = QHBoxLayout()
        options_row.setSpacing(12)
        options_row.setContentsMargins(0, 0, 0, 0)
        options_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        db_label = QLabel('Database: ')
        db_label.setStyleSheet("color: #374151; font-size: 11px;")
        options_row.addWidget(db_label)
        
        # Radio buttons for database selection
        self.db_button_group = QButtonGroup(self)
        
        self.local_radio = QRadioButton('Local')
        self.local_radio.setStyleSheet("color: #374151; font-size: 11px;")
        self.local_radio.setChecked(self.active_db_target == "local")
        self.db_button_group.addButton(self.local_radio)
        options_row.addWidget(self.local_radio)
        
        self.neon_radio = QRadioButton('Neon Cloud')
        self.neon_radio.setStyleSheet("color: #374151; font-size: 11px;")
        self.neon_radio.setChecked(self.active_db_target == "neon")
        self.db_button_group.addButton(self.neon_radio)
        options_row.addWidget(self.neon_radio)
        
        self.web_radio = QRadioButton('Web')
        self.web_radio.setStyleSheet("color: #374151; font-size: 11px;")
        self.web_radio.setChecked(self.active_db_target == "web")
        self.db_button_group.addButton(self.web_radio)
        options_row.addWidget(self.web_radio)
        
        options_row.addStretch()
        
        # Connect radio button signals
        self.local_radio.toggled.connect(lambda checked: checked and self._on_db_target_changed("local"))
        self.neon_radio.toggled.connect(lambda checked: checked and self._on_db_target_changed("neon"))
        self.web_radio.toggled.connect(lambda checked: checked and self._on_db_target_changed("web"))
        
        card_layout.addLayout(options_row)
        card_layout.addSpacing(4)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.login_button = QPushButton('Sign In')
        self.login_button.setObjectName('LoginButton')
        self.login_button.setMaximumWidth(160)
        self.login_button.clicked.connect(self.handle_login)
        
        self.cancel_button = QPushButton('Cancel')
        self.cancel_button.setObjectName('CancelButton')
        self.cancel_button.setMaximumWidth(160)
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.login_button)
        button_layout.addWidget(self.cancel_button)
        card_layout.addLayout(button_layout)
        
        card.setLayout(card_layout)
        
        # Center the card
        card_container.addStretch()
        card_container.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        card_container.addStretch()
        
        main_layout.addLayout(card_container, 1)
        self.setLayout(main_layout)
    
    def showEvent(self, event):
        """Fix alignment/rendering issue on first show"""
        super().showEvent(event)
        # Trigger layout update to fix alignment rendering race condition
        self.layout().update()
        self.updateGeometry()
    
    def check_remember_token(self):
        """Check if remember-me token exists and valid"""
        # Only auto-login when the user previously opted in
        if not self.remember_checkbox.isChecked():
            return

        user_id = self.login_manager.load_remember_token()
        if user_id:
            try:
                auth_user = self.login_manager.get_user_by_id(user_id)
                if auth_user:
                    # Auto-login if token is valid
                    self.auth_user = auth_user
                    self.login_successful.emit(auth_user)
                    self.accept()
            except Exception:
                # Database connection failed, allow user to select DB target and try again
                pass

    def _load_saved_login(self):
        """Prefill username/checkbox from last session (no passwords stored)"""
        if not self.prefs_file.exists():
            return
        try:
            with open(self.prefs_file, "r") as f:
                data = json.load(f)
            self.username_input.setText(data.get("username", ""))
            self.remember_checkbox.setChecked(bool(data.get("remember", False)))
        except Exception:
            # Ignore prefs errors silently
            pass

    def _save_login_prefs(self, username: str, remember: bool) -> None:
        """Persist username and remember preference only"""
        if not remember:
            self._clear_login_prefs()
            return
        try:
            with open(self.prefs_file, "w") as f:
                json.dump({"username": username, "remember": True}, f)
        except Exception:
            pass

    def _clear_login_prefs(self) -> None:
        if self.prefs_file.exists():
            try:
                self.prefs_file.unlink()
            except Exception:
                pass

    def _refresh_login_manager_from_env(self) -> None:
        """Reload DB connection settings from environment for the active target."""
        self.login_manager.db_host = os.getenv('DB_HOST', self.login_manager.db_host)
        self.login_manager.db_port = int(os.getenv('DB_PORT', self.login_manager.db_port))
        self.login_manager.db_name = os.getenv('DB_NAME', self.login_manager.db_name)
        self.login_manager.db_user = os.getenv('DB_USER', self.login_manager.db_user)
        self.login_manager.db_password = os.getenv('DB_PASSWORD', self.login_manager.db_password)

    def _on_db_target_changed(self, target: str) -> None:
        """Handle DB target selection (Local, Neon, or Web)"""
        self.active_db_target = target.lower().strip()

        if target == "web":
            # Web option opens browser to Render deployment immediately
            # Hide the dialog and open browser without showing info message
            try:
                render_url = "https://arrow-limo.onrender.com"
                webbrowser.open(render_url)
                # Close the desktop login dialog since user is using web
                self.reject()
            except Exception as e:
                QMessageBox.warning(self, "Browser Error", 
                    f"Could not open browser: {e}\n\nVisit manually: https://arrow-limo.onrender.com")
            return

        # Show credential fields for Local/Neon login
        self._show_credential_fields()

        if target == "local":
            # Local database configuration (localhost)
            os.environ["DB_TARGET"] = "local"
            os.environ["DB_HOST"] = "localhost"
            os.environ["DB_PORT"] = "5432"
            os.environ["DB_NAME"] = "almsdata"
            os.environ["DB_USER"] = "postgres"
            os.environ["DB_PASSWORD"] = "***REMOVED***"
            os.environ["DB_SSLMODE"] = ""
        
        elif target == "neon":
            # Neon cloud database configuration
            os.environ["DB_TARGET"] = "neon"
            os.environ["DB_HOST"] = "ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech"
            os.environ["DB_PORT"] = "5432"
            os.environ["DB_NAME"] = "neondb"
            os.environ["DB_USER"] = "neondb_owner"
            os.environ["DB_PASSWORD"] = "***REMOVED***"
            os.environ["DB_SSLMODE"] = "require"

        if self.set_db_callback:
            self.set_db_callback(target)

        self._refresh_login_manager_from_env()
    
    def handle_login(self):
        """Process login attempt"""
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        if not username or not password:
            QMessageBox.warning(self, 'Login Error', 'Please enter both username and password')
            return
        
        # Disable button during login
        self.login_button.setEnabled(False)
        self.login_button.setText('Signing in...')
        
        try:
            # Attempt authentication
            print(f'[LOGIN DEBUG] Attempting login for: {username}')
            auth_user = self.login_manager.authenticate(username, password)
            self.auth_user = auth_user
            print(f'[LOGIN DEBUG] Login successful for: {username}')
            
            # Save remember token if checked
            if self.remember_checkbox.isChecked():
                self.login_manager.save_remember_token(auth_user['user_id'])
                self._save_login_prefs(username, True)
            else:
                self.login_manager.clear_remember_token()
                self._clear_login_prefs()
            
            # Emit success signal
            self.login_successful.emit(auth_user)
            self.accept()
            
        except AccountLockedError as e:
            print(f'[LOGIN DEBUG] Account locked: {str(e)}')
            # Silently fail - don't show warning dialog
            self.password_input.clear()
            self.password_input.setFocus()
        except AuthenticationError as e:
            print(f'[LOGIN DEBUG] Auth failed: {str(e)}')
            # Silently fail - don't show warning dialog for invalid credentials
            self.password_input.clear()
            self.password_input.setFocus()
        except Exception as e:
            print(f'[LOGIN DEBUG] Exception: {str(e)}')
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, 'Login Error', f'An unexpected error occurred: {str(e)}')
            self.password_input.clear()
            self.password_input.setFocus()
        finally:
            self.login_button.setEnabled(True)
            self.login_button.setText('Sign In')
    
    def _toggle_password_view(self):
        """Toggle between showing and hiding password"""
        if self.password_view_visible:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.view_password_btn.setText('👁️')
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.view_password_btn.setText('🙈')
        self.password_view_visible = not self.password_view_visible
    
    def show_error(self, message: str):
        """Display error message"""
        self.password_input.clear()
        self.password_input.setFocus()
    
    def clear_error(self):
        """Hide error message"""
        pass
    
    def _on_remote_web_selected(self):
        """Handle Remote Web selection - opens browser for web-based restore interface"""
        # Hide credential fields for Remote Web login
        self.username_label.hide()
        self.username_input.hide()
        self.password_label.hide()
        self.password_input.hide()
        self.view_password_btn.hide()
        self.login_button.setText('Open Web Interface')
        self.login_button.clicked.disconnect()
        self.login_button.clicked.connect(self._open_remote_web_interface)
        
    def _show_credential_fields(self):
        """Show credential fields for Local/Neon login"""
        self.username_label.show()
        self.username_input.show()
        self.password_label.show()
        self.password_input.show()
        self.view_password_btn.show()
        self.login_button.setText('Sign In')
        self.login_button.clicked.disconnect()
        self.login_button.clicked.connect(self.handle_login)
        
    def _open_remote_web_interface(self):
        """Open remote web interface via Render deployment"""
        # Render deployment URL
        render_url = "https://arrow-limo.onrender.com"
        message = (
            "Opening web-based management system...\n\n"
            f"URL: {render_url}\n\n"
            "Your default browser will open with the login page.\n"
            "The web interface connects to the Neon cloud database."
        )
        QMessageBox.information(self, "Web Access", message)
        
        # Open the web interface in default browser
        try:
            webbrowser.open(render_url)
            # Close the desktop login dialog since user is using web
            self.reject()
        except Exception as e:
            QMessageBox.warning(self, "Browser Error", f"Could not open browser: {e}\n\nVisit manually: {render_url}")
    
    def keyPressEvent(self, event):
        """Handle key events"""
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            self.clear_error()
            super().keyPressEvent(event)
