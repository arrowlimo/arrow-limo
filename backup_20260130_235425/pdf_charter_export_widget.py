"""
PDF Charter Export Widget
PyQt6 UI for exporting charters to comprehensive PDF documents
Integrates booking, client, dispatch, routing, invoice, and beverage data
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QMessageBox, QFileDialog, QProgressBar,
    QGroupBox, QFormLayout, QComboBox, QCheckBox, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor, QIcon
import psycopg2
import os
from datetime import datetime
from desktop_app.pdf_charter_export_module import PDFCharterExporter

class PDFExportWorker(QThread):
    """Background worker for PDF export"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # success, filepath
    
    def __init__(self, reserve_number, output_path):
        super().__init__()
        self.reserve_number = reserve_number
        self.output_path = output_path
    
    def run(self):
        """Run PDF export in background"""
        try:
            self.progress.emit(f"Exporting charter {self.reserve_number}...")
            
            exporter = PDFCharterExporter()
            result = exporter.generate_pdf(self.reserve_number, self.output_path)
            
            if result:
                self.progress.emit(f"PDF created successfully")
                self.finished.emit(True, result)
            else:
                self.progress.emit(f"Failed to create PDF")
                self.finished.emit(False, "PDF generation failed")
        
        except Exception as e:
            self.progress.emit(f"Error: {str(e)}")
            self.finished.emit(False, str(e))


class PDFChartExportWidget(QWidget):
    """Widget for exporting charters to PDF"""
    
    pdf_exported = pyqtSignal(str)  # Emits filepath
    
    def __init__(self, db_conn=None, parent=None):
        super().__init__(parent)
        self.db_conn = db_conn
        self.export_worker = None
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("PDF Charter Export")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Export Section
        export_group = QGroupBox("Export Charter to PDF")
        export_layout = QFormLayout()
        
        # Reserve number input
        self.reserve_input = QLineEdit()
        self.reserve_input.setPlaceholderText("e.g., 001002")
        export_layout.addRow("Reserve #:", self.reserve_input)
        
        # Options
        self.include_routing = QCheckBox("Include routing schedule")
        self.include_routing.setChecked(True)
        export_layout.addRow("Options:", self.include_routing)
        
        self.include_beverages = QCheckBox("Include beverage order")
        export_layout.addRow("", self.include_beverages)
        
        self.include_invoice = QCheckBox("Include invoice details")
        export_layout.addRow("", self.include_invoice)
        
        self.include_driver = QCheckBox("Include driver information")
        self.include_driver.setChecked(True)
        export_layout.addRow("", self.include_driver)
        
        # Output location
        location_layout = QHBoxLayout()
        self.location_input = QLineEdit()
        self.location_input.setReadOnly(True)
        self.location_input.setText(os.getcwd())
        location_layout.addWidget(self.location_input)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_location)
        location_layout.addWidget(browse_btn)
        
        export_layout.addRow("Save to:", location_layout)
        
        export_group.setLayout(export_layout)
        layout.addWidget(export_group)
        
        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #2c5aa0; font-weight: bold;")
        layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        export_btn = QPushButton("Export to PDF")
        export_btn.setStyleSheet("background-color: #2c5aa0; color: white; font-weight: bold; padding: 8px;")
        export_btn.clicked.connect(self.export_charter)
        button_layout.addWidget(export_btn)
        
        open_btn = QPushButton("Open Last PDF")
        open_btn.clicked.connect(self.open_last_pdf)
        button_layout.addWidget(open_btn)
        
        layout.addLayout(button_layout)
        
        # Notes
        notes = QTextEdit()
        notes.setReadOnly(True)
        notes.setMaximumHeight(100)
        notes.setText(
            "EXPORT INCLUDES:\n"
            "• Charter booking details (date, time, passengers, vehicle, driver)\n"
            "• Client information (name, address, contact, payment terms)\n"
            "• Route/dispatch schedule (pickup/dropoff locations and times)\n"
            "• Beverage order items (quantities, prices, totals)\n"
            "• Invoice details (line items, amounts, taxes)\n"
            "• Driver information (name, phone, hire date, hourly rate)\n"
            "• Financial summary (rate, taxes, total due, paid, balance)"
        )
        layout.addWidget(QLabel("What's Included:"))
        layout.addWidget(notes)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def browse_location(self):
        """Browse for export location"""
        folder = QFileDialog.getExistingDirectory(self, "Select Export Folder")
        if folder:
            self.location_input.setText(folder)
    
    def export_charter(self):
        """Export charter to PDF"""
        reserve = self.reserve_input.text().strip()
        
        if not reserve:
            QMessageBox.warning(self, "Error", "Please enter a reserve number")
            return
        
        output_folder = self.location_input.text()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"charter_{reserve}_{timestamp}.pdf"
        output_path = os.path.join(output_folder, filename)
        
        # Start export
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.status_label.setText("Exporting...")
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        
        self.export_worker = PDFExportWorker(reserve, output_path)
        self.export_worker.progress.connect(self.update_status)
        self.export_worker.finished.connect(self.export_finished)
        self.export_worker.start()
        
        # Store last filepath
        self.last_pdf_path = output_path
    
    def update_status(self, message):
        """Update status message"""
        self.status_label.setText(message)
    
    def export_finished(self, success, message):
        """Handle export completion"""
        self.progress_bar.setVisible(False)
        
        if success:
            self.status_label.setText(f"Success: {message}")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            
            QMessageBox.information(
                self,
                "Export Complete",
                f"PDF exported successfully:\n\n{message}"
            )
            
            self.pdf_exported.emit(message)
            self.reserve_input.clear()
        else:
            self.status_label.setText(f"Error: {message}")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            
            QMessageBox.critical(
                self,
                "Export Failed",
                f"PDF export failed:\n\n{message}"
            )
    
    def open_last_pdf(self):
        """Open last exported PDF"""
        if hasattr(self, 'last_pdf_path') and os.path.exists(self.last_pdf_path):
            os.startfile(self.last_pdf_path)
        else:
            QMessageBox.warning(self, "Error", "No PDF has been exported yet")
