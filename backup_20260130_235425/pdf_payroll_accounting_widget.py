"""
PyQt6 Widget - Unified PDF Export for Payroll & Accounting Functions
Provides UI for generating:
- Payroll: Pay stubs, T4 tax slips
- Accounting: Invoices, expense reports, vendor statements

Integrates with pdf_payroll_accounting_filler_FIXED.py
"""

import sys
import os
from datetime import datetime, date, timedelta
from decimal import Decimal
from threading import Thread
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QComboBox, QSpinBox, QCalendarWidget,
    QPushButton, QLabel, QLineEdit, QFileDialog, QProgressBar, QMessageBox,
    QDateEdit, QFormLayout, QGroupBox, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QIcon, QColor

# Import the PDF filler
try:
    from pdf_payroll_accounting_filler_FIXED import PayrollAccountingPDFFiller
except ImportError:
    PayrollAccountingPDFFiller = None


class PDFExportWorker(QThread):
    """Background worker thread for PDF generation"""
    
    progress_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    success_signal = pyqtSignal(str)
    
    def __init__(self, function_type, output_dir, **kwargs):
        super().__init__()
        self.function_type = function_type
        self.output_dir = output_dir
        self.kwargs = kwargs
        self.filler = PayrollAccountingPDFFiller()
    
    def run(self):
        """Execute PDF generation in background"""
        try:
            self.progress_signal.emit(f"Generating {self.function_type}...")
            
            if self.function_type == "T4 Slip":
                employee_id = self.kwargs['employee_id']
                tax_year = self.kwargs['tax_year']
                output_path = os.path.join(self.output_dir, f"t4_slip_{employee_id}_{tax_year}.pdf")
                result = self.filler.generate_t4_slip(employee_id, tax_year, output_path)
            
            elif self.function_type == "Pay Stub":
                employee_id = self.kwargs['employee_id']
                year = self.kwargs['year']
                month = self.kwargs['month']
                output_path = os.path.join(self.output_dir, f"paystub_{employee_id}_{year}_{month:02d}.pdf")
                result = self.filler.generate_paystub(employee_id, year, month, output_path)
            
            elif self.function_type == "Invoice":
                invoice_id = self.kwargs['invoice_id']
                output_path = os.path.join(self.output_dir, f"invoice_{invoice_id}.pdf")
                result = self.filler.generate_invoice_pdf(invoice_id, output_path)
            
            elif self.function_type == "Expense Report":
                start_date = self.kwargs['start_date']
                end_date = self.kwargs['end_date']
                output_path = os.path.join(self.output_dir, f"expense_report_{start_date}_{end_date}.pdf")
                result = self.filler.generate_expense_report(start_date, end_date, output_path)
            
            elif self.function_type == "Vendor Statement":
                vendor_name = self.kwargs['vendor_name']
                output_path = os.path.join(self.output_dir, f"vendor_statement_{vendor_name.replace(' ', '_')}.pdf")
                result = self.filler.generate_vendor_statement(vendor_name, output_path)
            
            if result:
                self.success_signal.emit(f"{self.function_type} created: {os.path.basename(result)}")
            else:
                self.error_signal.emit(f"Failed to generate {self.function_type}")
        
        except Exception as e:
            self.error_signal.emit(f"Error: {str(e)}")


class PDFPayrollAccountingWidget(QWidget):
    """Main widget for payroll and accounting PDF exports"""
    
    def __init__(self):
        super().__init__()
        self.output_dir = os.path.join(os.path.expanduser("~"), "Documents", "PDF Exports")
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self.worker_thread = None
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        
        # Title
        title_label = QLabel("PDF Export - Payroll & Accounting")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #1f4788;")
        layout.addWidget(title_label)
        
        # Tabs for different export types
        tabs = QTabWidget()
        tabs.addTab(self.create_payroll_tab(), "Payroll")
        tabs.addTab(self.create_accounting_tab(), "Accounting")
        layout.addWidget(tabs)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status_label)
        
        # Output directory selector
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Export Location:"))
        self.dir_label = QLineEdit(self.output_dir)
        self.dir_label.setReadOnly(True)
        dir_layout.addWidget(self.dir_label)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.select_output_directory)
        dir_layout.addWidget(browse_btn)
        layout.addLayout(dir_layout)
        
        self.setLayout(layout)
    
    def create_payroll_tab(self) -> QWidget:
        """Create payroll export tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # T4 Slip section
        t4_group = QGroupBox("T4 Tax Slip")
        t4_layout = QFormLayout()
        
        self.t4_emp_spin = QSpinBox()
        self.t4_emp_spin.setMinimum(1)
        self.t4_emp_spin.setMaximum(1000)
        t4_layout.addRow("Employee ID:", self.t4_emp_spin)
        
        self.t4_year_spin = QSpinBox()
        self.t4_year_spin.setValue(datetime.now().year)
        self.t4_year_spin.setMinimum(2000)
        self.t4_year_spin.setMaximum(2099)
        t4_layout.addRow("Tax Year:", self.t4_year_spin)
        
        t4_btn = QPushButton("Generate T4")
        t4_btn.clicked.connect(self.generate_t4)
        t4_layout.addRow(t4_btn)
        
        t4_group.setLayout(t4_layout)
        layout.addWidget(t4_group)
        
        # Pay Stub section
        stub_group = QGroupBox("Pay Stub")
        stub_layout = QFormLayout()
        
        self.stub_emp_spin = QSpinBox()
        self.stub_emp_spin.setMinimum(1)
        self.stub_emp_spin.setMaximum(1000)
        stub_layout.addRow("Employee ID:", self.stub_emp_spin)
        
        self.stub_year_spin = QSpinBox()
        self.stub_year_spin.setValue(datetime.now().year)
        self.stub_year_spin.setMinimum(2000)
        self.stub_year_spin.setMaximum(2099)
        stub_layout.addRow("Year:", self.stub_year_spin)
        
        self.stub_month_spin = QSpinBox()
        self.stub_month_spin.setValue(datetime.now().month)
        self.stub_month_spin.setMinimum(1)
        self.stub_month_spin.setMaximum(12)
        stub_layout.addRow("Month:", self.stub_month_spin)
        
        stub_btn = QPushButton("Generate Pay Stub")
        stub_btn.clicked.connect(self.generate_paystub)
        stub_layout.addRow(stub_btn)
        
        stub_group.setLayout(stub_layout)
        layout.addWidget(stub_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_accounting_tab(self) -> QWidget:
        """Create accounting export tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Invoice section
        inv_group = QGroupBox("Invoice")
        inv_layout = QFormLayout()
        
        self.inv_id_spin = QSpinBox()
        self.inv_id_spin.setMinimum(1)
        self.inv_id_spin.setMaximum(999999)
        inv_layout.addRow("Invoice ID:", self.inv_id_spin)
        
        inv_btn = QPushButton("Generate Invoice")
        inv_btn.clicked.connect(self.generate_invoice)
        inv_layout.addRow(inv_btn)
        
        inv_group.setLayout(inv_layout)
        layout.addWidget(inv_group)
        
        # Expense Report section
        exp_group = QGroupBox("Expense Report")
        exp_layout = QFormLayout()
        
        self.exp_start_edit = QDateEdit()
        self.exp_start_edit.setDate(QDate.currentDate().addMonths(-1))
        exp_layout.addRow("Start Date:", self.exp_start_edit)
        
        self.exp_end_edit = QDateEdit()
        self.exp_end_edit.setDate(QDate.currentDate())
        exp_layout.addRow("End Date:", self.exp_end_edit)
        
        exp_btn = QPushButton("Generate Expense Report")
        exp_btn.clicked.connect(self.generate_expense_report)
        exp_layout.addRow(exp_btn)
        
        exp_group.setLayout(exp_layout)
        layout.addWidget(exp_group)
        
        # Vendor Statement section
        vendor_group = QGroupBox("Vendor Statement")
        vendor_layout = QFormLayout()
        
        self.vendor_input = QLineEdit()
        self.vendor_input.setPlaceholderText("Enter vendor name")
        vendor_layout.addRow("Vendor:", self.vendor_input)
        
        vendor_btn = QPushButton("Generate Vendor Statement")
        vendor_btn.clicked.connect(self.generate_vendor_statement)
        vendor_layout.addRow(vendor_btn)
        
        vendor_group.setLayout(vendor_layout)
        layout.addWidget(vendor_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def select_output_directory(self):
        """Select output directory for PDFs"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select PDF Export Directory", self.output_dir
        )
        if directory:
            self.output_dir = directory
            self.dir_label.setText(directory)
    
    def generate_t4(self):
        """Generate T4 slip"""
        if not PayrollAccountingPDFFiller:
            QMessageBox.critical(self, "Error", "PDF module not available")
            return
        
        self.run_worker("T4 Slip", employee_id=self.t4_emp_spin.value(), tax_year=self.t4_year_spin.value())
    
    def generate_paystub(self):
        """Generate pay stub"""
        if not PayrollAccountingPDFFiller:
            QMessageBox.critical(self, "Error", "PDF module not available")
            return
        
        self.run_worker("Pay Stub", employee_id=self.stub_emp_spin.value(), 
                       year=self.stub_year_spin.value(), month=self.stub_month_spin.value())
    
    def generate_invoice(self):
        """Generate invoice PDF"""
        if not PayrollAccountingPDFFiller:
            QMessageBox.critical(self, "Error", "PDF module not available")
            return
        
        self.run_worker("Invoice", invoice_id=self.inv_id_spin.value())
    
    def generate_expense_report(self):
        """Generate expense report"""
        if not PayrollAccountingPDFFiller:
            QMessageBox.critical(self, "Error", "PDF module not available")
            return
        
        start_date = self.exp_start_edit.date().toPyDate()
        end_date = self.exp_end_edit.date().toPyDate()
        self.run_worker("Expense Report", start_date=start_date, end_date=end_date)
    
    def generate_vendor_statement(self):
        """Generate vendor statement"""
        if not PayrollAccountingPDFFiller:
            QMessageBox.critical(self, "Error", "PDF module not available")
            return
        
        vendor = self.vendor_input.text().strip()
        if not vendor:
            QMessageBox.warning(self, "Input Required", "Please enter a vendor name")
            return
        
        self.run_worker("Vendor Statement", vendor_name=vendor)
    
    def run_worker(self, function_type: str, **kwargs):
        """Run PDF export in background worker thread"""
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Please wait for current export to finish")
            return
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Generating {function_type}...")
        
        self.worker_thread = PDFExportWorker(function_type, self.output_dir, **kwargs)
        self.worker_thread.progress_signal.connect(self.on_progress)
        self.worker_thread.error_signal.connect(self.on_error)
        self.worker_thread.success_signal.connect(self.on_success)
        self.worker_thread.start()
    
    def on_progress(self, message: str):
        """Handle progress updates"""
        self.status_label.setText(message)
        self.progress_bar.setValue(50)
    
    def on_error(self, message: str):
        """Handle errors"""
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Error: {message}")
        QMessageBox.critical(self, "Error", message)
    
    def on_success(self, message: str):
        """Handle successful PDF generation"""
        self.progress_bar.setValue(100)
        self.status_label.setText(message)
        self.progress_bar.setVisible(False)
        QMessageBox.information(self, "Success", message)


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    widget = PDFPayrollAccountingWidget()
    widget.setWindowTitle("PDF Export - Payroll & Accounting")
    widget.resize(600, 700)
    widget.show()
    sys.exit(app.exec())
