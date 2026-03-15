"""
Error Log Viewer Widget
UI for viewing, filtering, and resolving logged errors
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QTextEdit, QDialog, QMessageBox, QComboBox,
    QGroupBox, QFormLayout, QLineEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from desktop_app.error_logger import get_error_logger


class ErrorLogViewer(QWidget):
    """View and manage application errors"""
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.error_logger = get_error_logger()
        
        self.init_ui()
        self.load_errors()
    
    def init_ui(self):
        """Build the error viewer UI"""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("🐛 Error Log & Issue Tracker")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Stats panel
        stats_group = QGroupBox("Error Statistics")
        stats_layout = QFormLayout()
        
        self.total_label = QLabel("0")
        self.unresolved_label = QLabel("0")
        self.resolved_label = QLabel("0")
        
        stats_layout.addRow("Total Errors:", self.total_label)
        stats_layout.addRow("Unresolved:", self.unresolved_label)
        stats_layout.addRow("Resolved:", self.resolved_label)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # Filter controls
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("Show:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All Errors", "Unresolved Only", "Resolved Only"])
        self.filter_combo.currentTextChanged.connect(self.load_errors)
        filter_layout.addWidget(self.filter_combo)
        
        filter_layout.addStretch()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_errors)
        filter_layout.addWidget(refresh_btn)
        
        clear_resolved_btn = QPushButton("🗑️ Clear Resolved")
        clear_resolved_btn.clicked.connect(self.clear_resolved_errors)
        filter_layout.addWidget(clear_resolved_btn)
        
        layout.addLayout(filter_layout)
        
        # Errors table
        self.errors_table = QTableWidget()
        self.errors_table.setColumnCount(7)
        self.errors_table.setHorizontalHeaderLabels([
            "ID", "Time", "Type", "Message", "Widget", "Action", "Status"
        ])
        self.errors_table.setColumnWidth(0, 50)
        self.errors_table.setColumnWidth(1, 140)
        self.errors_table.setColumnWidth(2, 120)
        self.errors_table.setColumnWidth(3, 300)
        self.errors_table.setColumnWidth(4, 150)
        self.errors_table.setColumnWidth(5, 120)
        self.errors_table.setColumnWidth(6, 80)
        self.errors_table.doubleClicked.connect(self.show_error_details)
        layout.addWidget(self.errors_table)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        view_btn = QPushButton("👁️ View Details")
        view_btn.clicked.connect(self.view_selected_error)
        btn_layout.addWidget(view_btn)
        
        resolve_btn = QPushButton("✅ Mark Resolved")
        resolve_btn.clicked.connect(self.resolve_selected_error)
        btn_layout.addWidget(resolve_btn)
        
        export_btn = QPushButton("📤 Export to CSV")
        export_btn.clicked.connect(self.export_errors)
        btn_layout.addWidget(export_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def load_errors(self):
        """Load errors from database"""
        try:
            # Get filter setting
            filter_text = self.filter_combo.currentText()
            if filter_text == "Unresolved Only":
                resolved = False
            elif filter_text == "Resolved Only":
                resolved = True
            else:
                resolved = None
            
            # Get errors
            errors = self.error_logger.get_recent_errors(limit=500, resolved=resolved)
            
            # Update table
            self.errors_table.setRowCount(len(errors))
            for row_idx, error in enumerate(errors):
                error_id, timestamp, error_type, error_msg, widget_name, action, is_resolved = error
                
                self.errors_table.setItem(row_idx, 0, QTableWidgetItem(str(error_id)))
                self.errors_table.setItem(row_idx, 1, QTableWidgetItem(str(timestamp)))
                self.errors_table.setItem(row_idx, 2, QTableWidgetItem(error_type))
                
                # Truncate long messages
                msg_short = error_msg[:100] + "..." if len(error_msg) > 100 else error_msg
                self.errors_table.setItem(row_idx, 3, QTableWidgetItem(msg_short))
                
                self.errors_table.setItem(row_idx, 4, QTableWidgetItem(widget_name))
                self.errors_table.setItem(row_idx, 5, QTableWidgetItem(action))
                
                status_item = QTableWidgetItem("✅ Resolved" if is_resolved else "❌ Open")
                if is_resolved:
                    status_item.setForeground(QColor(0, 128, 0))
                else:
                    status_item.setForeground(QColor(255, 0, 0))
                self.errors_table.setItem(row_idx, 6, status_item)
            
            # Update stats
            stats = self.error_logger.get_error_stats()
            self.total_label.setText(str(stats.get('total', 0)))
            self.unresolved_label.setText(str(stats.get('unresolved', 0)))
            self.resolved_label.setText(str(stats.get('resolved', 0)))
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load errors: {e}")
    
    def show_error_details(self):
        """Show detailed error info on double-click"""
        self.view_selected_error()
    
    def view_selected_error(self):
        """View full details of selected error"""
        current_row = self.errors_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "No Selection", "Please select an error to view.")
            return
        
        error_id = int(self.errors_table.item(current_row, 0).text())
        error_details = self.error_logger.get_error_details(error_id)
        
        if not error_details:
            QMessageBox.warning(self, "Not Found", "Error details not found.")
            return
        
        # Show details dialog
        dialog = ErrorDetailDialog(error_details, self)
        dialog.exec()
    
    def resolve_selected_error(self):
        """Mark selected error as resolved"""
        current_row = self.errors_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "No Selection", "Please select an error to resolve.")
            return
        
        error_id = int(self.errors_table.item(current_row, 0).text())
        
        # Ask for resolution notes
        from PyQt6.QtWidgets import QInputDialog
        notes, ok = QInputDialog.getMultiLineText(
            self, "Resolution Notes",
            "Enter resolution notes (optional):"
        )
        
        if ok:
            if self.error_logger.mark_resolved(error_id, notes):
                QMessageBox.information(self, "Success", "Error marked as resolved.")
                self.load_errors()
            else:
                QMessageBox.critical(self, "Error", "Failed to mark error as resolved.")
    
    def clear_resolved_errors(self):
        """Delete all resolved errors"""
        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Delete all resolved errors from the database?\n\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                cur = self.db.get_cursor()
                cur.execute("DELETE FROM app_errors WHERE resolved = TRUE")
                self.db.commit()
                QMessageBox.information(self, "Success", f"Deleted {cur.rowcount} resolved errors.")
                self.load_errors()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete errors: {e}")
    
    def export_errors(self):
        """Export errors to CSV"""
        try:
            from datetime import datetime
            import csv
            
            filename = f"L:/limo/reports/error_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT error_id, timestamp, error_type, error_message, 
                       widget_name, action, resolved, resolution_notes
                FROM app_errors
                ORDER BY timestamp DESC
            """)
            
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['ID', 'Timestamp', 'Type', 'Message', 'Widget', 'Action', 'Resolved', 'Notes'])
                writer.writerows(cur.fetchall())
            
            QMessageBox.information(self, "Success", f"Errors exported to:\n{filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export errors: {e}")


class ErrorDetailDialog(QDialog):
    """Dialog showing full error details"""
    
    def __init__(self, error_details, parent=None):
        super().__init__(parent)
        self.error_details = error_details
        self.setWindowTitle("Error Details")
        self.setGeometry(100, 100, 800, 600)
        
        self.init_ui()
    
    def init_ui(self):
        """Build the details dialog"""
        layout = QVBoxLayout()
        
        error_id, timestamp, error_type, error_msg, traceback_text, widget_name, action, user_context, resolved, resolution_notes, resolved_at = self.error_details
        
        # Info section
        info_group = QGroupBox("Error Information")
        info_layout = QFormLayout()
        
        info_layout.addRow("Error ID:", QLabel(str(error_id)))
        info_layout.addRow("Timestamp:", QLabel(str(timestamp)))
        info_layout.addRow("Type:", QLabel(error_type))
        info_layout.addRow("Widget:", QLabel(widget_name))
        info_layout.addRow("Action:", QLabel(action))
        info_layout.addRow("Status:", QLabel("✅ Resolved" if resolved else "❌ Unresolved"))
        
        if resolved:
            info_layout.addRow("Resolved At:", QLabel(str(resolved_at)))
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Error message
        msg_group = QGroupBox("Error Message")
        msg_layout = QVBoxLayout()
        msg_text = QTextEdit()
        msg_text.setPlainText(error_msg)
        msg_text.setReadOnly(True)
        msg_text.setMaximumHeight(100)
        msg_layout.addWidget(msg_text)
        msg_group.setLayout(msg_layout)
        layout.addWidget(msg_group)
        
        # Traceback
        tb_group = QGroupBox("Traceback")
        tb_layout = QVBoxLayout()
        tb_text = QTextEdit()
        tb_text.setPlainText(traceback_text)
        tb_text.setReadOnly(True)
        tb_text.setFont(QFont("Courier", 9))
        tb_layout.addWidget(tb_text)
        tb_group.setLayout(tb_layout)
        layout.addWidget(tb_group)
        
        # Resolution notes
        if resolution_notes:
            notes_group = QGroupBox("Resolution Notes")
            notes_layout = QVBoxLayout()
            notes_text = QTextEdit()
            notes_text.setPlainText(resolution_notes)
            notes_text.setReadOnly(True)
            notes_text.setMaximumHeight(80)
            notes_layout.addWidget(notes_text)
            notes_group.setLayout(notes_layout)
            layout.addWidget(notes_group)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)
