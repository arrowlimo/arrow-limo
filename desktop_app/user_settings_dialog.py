"""
User Settings Dialog - Allow users to change their own display theme
"""
import json
import logging

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

logger = logging.getLogger(__name__)


class UserSettingsDialog(QDialog):
    """Dialog for users to manage their own settings"""
    
    def __init__(self, parent=None, auth_user=None, db=None) -> None:
        super().__init__(parent)
        self.auth_user = auth_user or {}
        self.db = db
        self.username = self.auth_user.get('username', 'User')
        self.user_id = self.auth_user.get('user_id')
        
        self.setWindowTitle(f"Settings - {self.username}")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setMinimumHeight(250)
        
        self._init_ui()
        self._load_current_settings()
    
    def _init_ui(self) -> None:
        """Build UI"""
        layout = QVBoxLayout()
        
        # User info
        user_info = QGroupBox("User Profile")
        user_info_layout = QFormLayout()
        user_info_layout.addRow("Username:", QLabel(self.username))
        user_role = QLabel(self.auth_user.get('role', 'Unknown'))
        user_info_layout.addRow("Role:", user_role)
        user_info.setLayout(user_info_layout)
        layout.addWidget(user_info)
        
        # Display settings
        display_group = QGroupBox("Display Settings")
        display_layout = QFormLayout()
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("System Default", "default")
        self.theme_combo.addItem("Soft Blue", "soft_blue")
        self.theme_combo.addItem("Light Gray", "light_gray")
        display_layout.addRow("Display Theme:", self.theme_combo)
        
        display_group.setLayout(display_layout)
        layout.addWidget(display_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        save_btn = QPushButton("💾 Save Settings")
        save_btn.clicked.connect(self._save_settings)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _load_current_settings(self) -> None:
        """Load current user settings"""
        try:
            if not self.db or not self.user_id:
                return
            
            cur = self.db.get_cursor()
            cur.execute(
                "SELECT permissions FROM users WHERE user_id = %s",
                (self.user_id,)
            )
            result = cur.fetchone()
            if result and result[0]:
                permissions = result[0]
                if isinstance(permissions, str):
                    permissions = json.loads(permissions)
                
                theme = permissions.get('display_theme', 'default')
                index = self.theme_combo.findData(theme)
                if index >= 0:
                    self.theme_combo.setCurrentIndex(index)
        except Exception as e:
            logger.warning("Error loading user settings: %s", e)
    
    def _save_settings(self) -> None:
        """Save user settings"""
        try:
            if not self.db or not self.user_id:
                QMessageBox.warning(
                    self, "Error",
                    "Cannot save settings: database connection error"
                )
                return
            
            cur = self.db.get_cursor()
            
            # Get current permissions
            cur.execute(
                "SELECT permissions FROM users WHERE user_id = %s",
                (self.user_id,)
            )
            result = cur.fetchone()
            permissions = {}
            if result and result[0]:
                perm_data = result[0]
                if isinstance(perm_data, str):
                    permissions = json.loads(perm_data)
                else:
                    permissions = perm_data
            
            # Update display_theme
            permissions['display_theme'] = self.theme_combo.currentData()
            
            # Save to database
            cur.execute(
                "UPDATE users SET permissions = %s WHERE user_id = %s",
                (json.dumps(permissions), self.user_id)
            )
            self.db.commit()
            
            QMessageBox.information(
                self, "Success",
                "Settings saved successfully!\n"
                "(Theme will apply on next login)"
            )
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Failed to save settings:\n{e}"
            )
