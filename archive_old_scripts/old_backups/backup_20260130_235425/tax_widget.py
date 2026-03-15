"""
Tax Optimization Widget - PyQt6 Integration

Provides UI components for:
- T2/T4 form display and export
- CRA audit checklist
- Tax liability calculator
- Deduction suggestions
- Direct integration with AI Copilot

Usage:
    from tax_widget import TaxOptimizationWidget
    
    widget = TaxOptimizationWidget()
    widget.show()
"""

import sys
from typing import Dict, List, Any, Optional
from datetime import datetime, date
from decimal import Decimal

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QSpinBox,
    QComboBox, QMessageBox, QProgressBar, QTextEdit, QFrame,
    QFormLayout, QScrollArea, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QSize
from PyQt6.QtGui import QFont, QColor, QBrush

from tax_optimization_module import TaxOptimizer


class TaxWorker(QThread):
    """Background worker for tax calculations"""
    
    progress = pyqtSignal(str)  # Status updates
    results_ready = pyqtSignal(dict)  # Calculation results
    error = pyqtSignal(str)  # Error messages
    
    def __init__(self, operation: str, **kwargs):
        super().__init__()
        self.operation = operation
        self.params = kwargs
    
    def run(self):
        """Run tax calculation in background"""
        try:
            optimizer = TaxOptimizer()
            
            if self.operation == "t2_form":
                self.progress.emit("Generating T2 form...")
                result = optimizer.generate_t2_form(self.params['year'])
            
            elif self.operation == "t4_slips":
                self.progress.emit("Generating T4 slips...")
                result = optimizer.generate_t4_slips(self.params['year'])
            
            elif self.operation == "audit_checklist":
                self.progress.emit("Building audit checklist...")
                result = optimizer.get_cra_audit_checklist(self.params['year'])
            
            elif self.operation == "quarterly_tax":
                self.progress.emit("Calculating quarterly tax...")
                result = optimizer.calculate_quarterly_tax(
                    self.params['year'],
                    self.params['quarter']
                )
            
            elif self.operation == "deductions":
                self.progress.emit("Analyzing deductions...")
                result = optimizer.analyze_missing_deductions(self.params['year'])
            
            else:
                self.error.emit(f"Unknown operation: {self.operation}")
                return
            
            optimizer.close()
            self.results_ready.emit(result)
            self.progress.emit("Ready")
        
        except Exception as e:
            self.error.emit(f"Error: {str(e)}")


class TaxOptimizationWidget(QWidget):
    """Tax optimization UI widget with CRA compliance and T2/T4 generation"""
    
    # Signal to send tax data to AI Copilot
    request_ai_analysis = pyqtSignal(str)  # Tax question for AI
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tax_optimizer = TaxOptimizer()
        self.current_year = datetime.now().year
        self.current_quarter = (datetime.now().month - 1) // 3 + 1
        self.worker = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Title
        title = QLabel("Tax Optimization & CRA Compliance")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Control panel
        control_layout = QHBoxLayout()
        
        control_layout.addWidget(QLabel("Tax Year:"))
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2010, 2030)
        self.year_spin.setValue(self.current_year)
        self.year_spin.setMaximumWidth(80)
        control_layout.addWidget(self.year_spin)
        
        control_layout.addWidget(QLabel("Quarter:"))
        self.quarter_combo = QComboBox()
        self.quarter_combo.addItems(["Q1", "Q2", "Q3", "Q4"])
        self.quarter_combo.setCurrentIndex(self.current_quarter - 1)
        self.quarter_combo.setMaximumWidth(80)
        control_layout.addWidget(self.quarter_combo)
        
        control_layout.addStretch()
        
        refresh_btn = QPushButton("Refresh Data")
        refresh_btn.clicked.connect(self._refresh_data)
        refresh_btn.setMaximumWidth(120)
        control_layout.addWidget(refresh_btn)
        
        layout.addLayout(control_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Tab widget
        tabs = QTabWidget()
        
        # Tab 1: T2 Form
        tabs.addTab(self._create_t2_tab(), "T2 Form")
        
        # Tab 2: T4 Slips
        tabs.addTab(self._create_t4_tab(), "T4 Slips")
        
        # Tab 3: Audit Checklist
        tabs.addTab(self._create_audit_tab(), "CRA Audit")
        
        # Tab 4: Quarterly Tax
        tabs.addTab(self._create_quarterly_tab(), "Quarterly Tax")
        
        # Tab 5: Deduction Suggestions
        tabs.addTab(self._create_deductions_tab(), "Deductions")
        
        layout.addWidget(tabs)
        
        # Status bar
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: green; font-weight: bold;")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def _create_t2_tab(self) -> QWidget:
        """Create T2 form tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Display area
        self.t2_display = QTextEdit()
        self.t2_display.setReadOnly(True)
        self.t2_display.setFont(__import__('PyQt6.QtGui', fromlist=['QFont']).QFont("Courier", 9))
        layout.addWidget(self.t2_display)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        load_btn = QPushButton("Load T2 Data")
        load_btn.clicked.connect(lambda: self._load_data("t2_form"))
        button_layout.addWidget(load_btn)
        
        export_btn = QPushButton("Export as PDF")
        export_btn.clicked.connect(self._export_t2_pdf)
        button_layout.addWidget(export_btn)
        
        ai_btn = QPushButton("Ask AI")
        ai_btn.clicked.connect(lambda: self.request_ai_analysis.emit("Review our T2 form and suggest tax optimization strategies"))
        button_layout.addWidget(ai_btn)
        
        layout.addLayout(button_layout)
        layout.setContentsMargins(10, 10, 10, 10)
        
        return widget
    
    def _create_t4_tab(self) -> QWidget:
        """Create T4 slips tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Table for T4 data
        self.t4_table = QTableWidget()
        self.t4_table.setColumnCount(5)
        self.t4_table.setHorizontalHeaderLabels([
            "Employee", "Total Income", "Tax Deducted", "CPP", "EI"
        ])
        self.t4_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.t4_table)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        load_btn = QPushButton("Load T4 Slips")
        load_btn.clicked.connect(lambda: self._load_data("t4_slips"))
        button_layout.addWidget(load_btn)
        
        export_btn = QPushButton("Export All")
        export_btn.clicked.connect(self._export_t4_slips)
        button_layout.addWidget(export_btn)
        
        ai_btn = QPushButton("Ask AI")
        ai_btn.clicked.connect(lambda: self.request_ai_analysis.emit("Summarize our T4 payroll tax compliance"))
        button_layout.addWidget(ai_btn)
        
        layout.addLayout(button_layout)
        layout.setContentsMargins(10, 10, 10, 10)
        
        return widget
    
    def _create_audit_tab(self) -> QWidget:
        """Create audit checklist tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Checklist display
        self.audit_display = QTextEdit()
        self.audit_display.setReadOnly(True)
        layout.addWidget(self.audit_display)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        load_btn = QPushButton("Generate Checklist")
        load_btn.clicked.connect(lambda: self._load_data("audit_checklist"))
        button_layout.addWidget(load_btn)
        
        export_btn = QPushButton("Export Report")
        export_btn.clicked.connect(self._export_audit)
        button_layout.addWidget(export_btn)
        
        ai_btn = QPushButton("Ask AI")
        ai_btn.clicked.connect(lambda: self.request_ai_analysis.emit("Review our CRA audit readiness and identify gaps"))
        button_layout.addWidget(ai_btn)
        
        layout.addLayout(button_layout)
        layout.setContentsMargins(10, 10, 10, 10)
        
        return widget
    
    def _create_quarterly_tab(self) -> QWidget:
        """Create quarterly tax tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Display area
        self.quarterly_display = QTextEdit()
        self.quarterly_display.setReadOnly(True)
        layout.addWidget(self.quarterly_display)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        calc_btn = QPushButton("Calculate")
        calc_btn.clicked.connect(self._calculate_quarterly)
        button_layout.addWidget(calc_btn)
        
        ai_btn = QPushButton("Ask AI")
        ai_btn.clicked.connect(lambda: self.request_ai_analysis.emit(f"Estimate our quarterly tax liability for Q{self.quarter_combo.currentIndex() + 1} {self.year_spin.value()}"))
        button_layout.addWidget(ai_btn)
        
        layout.addLayout(button_layout)
        layout.setContentsMargins(10, 10, 10, 10)
        
        return widget
    
    def _create_deductions_tab(self) -> QWidget:
        """Create deductions analysis tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Display area
        self.deductions_display = QTextEdit()
        self.deductions_display.setReadOnly(True)
        layout.addWidget(self.deductions_display)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        analyze_btn = QPushButton("Analyze")
        analyze_btn.clicked.connect(lambda: self._load_data("deductions"))
        button_layout.addWidget(analyze_btn)
        
        ai_btn = QPushButton("Ask AI")
        ai_btn.clicked.connect(lambda: self.request_ai_analysis.emit("Review our business deductions and suggest missing ones"))
        button_layout.addWidget(ai_btn)
        
        layout.addLayout(button_layout)
        layout.setContentsMargins(10, 10, 10, 10)
        
        return widget
    
    def _load_data(self, operation: str):
        """Load tax data in background"""
        year = self.year_spin.value()
        quarter = self.quarter_combo.currentIndex() + 1
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Loading...")
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        
        # Create worker
        if operation == "quarterly_tax":
            self.worker = TaxWorker(operation, year=year, quarter=quarter)
        else:
            self.worker = TaxWorker(operation, year=year)
        
        self.worker.progress.connect(self._on_progress)
        self.worker.results_ready.connect(
            lambda r: self._on_results(operation, r)
        )
        self.worker.error.connect(self._on_error)
        self.worker.start()
    
    def _calculate_quarterly(self):
        """Calculate quarterly tax"""
        self._load_data("quarterly_tax")
    
    def _refresh_data(self):
        """Refresh all displayed data"""
        self.status_label.setText("Refreshing data...")
        self.status_label.setStyleSheet("color: blue; font-weight: bold;")
    
    def _on_progress(self, status: str):
        """Update progress"""
        self.status_label.setText(status)
    
    def _on_results(self, operation: str, results: Dict[str, Any]):
        """Display results"""
        if "error" in results:
            self.status_label.setText(f"Error: {results['error']}")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            return
        
        # Format and display results based on operation
        if operation == "t2_form":
            self._display_t2(results)
        elif operation == "t4_slips":
            self._display_t4(results)
        elif operation == "audit_checklist":
            self._display_audit(results)
        elif operation == "quarterly_tax":
            self._display_quarterly(results)
        elif operation == "deductions":
            self._display_deductions(results)
        
        self.progress_bar.setVisible(False)
        self.status_label.setText("Ready")
        self.status_label.setStyleSheet("color: green; font-weight: bold;")
    
    def _on_error(self, error: str):
        """Handle error"""
        self.status_label.setText(error)
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        self.progress_bar.setVisible(False)
    
    def _display_t2(self, data: Dict[str, Any]):
        """Display T2 form data"""
        text = f"""T2 CANADIAN TAX RETURN - {data.get('tax_year')}
{'='*60}

BUSINESS INFORMATION:
  Name: {data.get('business_name')}
  BN: {data.get('business_number')}
  Fiscal Year End: {data.get('fiscal_year_end')}

FINANCIAL SUMMARY:
  Gross Revenue: ${data.get('gross_revenue', 0):,.2f}
  Operating Expenses: ${data.get('operating_expenses', 0):,.2f}
  Net Income: ${data.get('net_income', 0):,.2f}

TAX CALCULATION:
  Corporate Tax Rate: {data.get('combined_tax_rate', 0):.1%}
  Corporate Tax Payable: ${data.get('corporate_tax_payable', 0):,.2f}

GST/HST INFORMATION:
  GST Collected: ${data.get('gst_collected', 0):,.2f}
  GST Paid: ${data.get('gst_paid', 0):,.2f}
  Net GST Payable: ${data.get('net_gst_payable', 0):,.2f}

PAYROLL SUMMARY:
  Employees: {data.get('employee_count')}
  Total Payroll: ${data.get('total_payroll', 0):,.2f}
  CPP Contributions: ${data.get('cpp_contributions_paid', 0):,.2f}
  EI Contributions: ${data.get('ei_contributions_paid', 0):,.2f}
  WCB Contributions: ${data.get('wcb_contributions', 0):,.2f}

STATUS: {data.get('status')}
Generated: {data.get('generated_date')}
"""
        self.t2_display.setText(text)
    
    def _display_t4(self, data):
        """Display T4 slips"""
        self.t4_table.setRowCount(0)
        if isinstance(data, list):
            for row_idx, slip in enumerate(data):
                if "error" in slip:
                    continue
                self.t4_table.insertRow(row_idx)
                self.t4_table.setItem(row_idx, 0, QTableWidgetItem(slip.get('employee_name', 'N/A')))
                self.t4_table.setItem(row_idx, 1, QTableWidgetItem(f"${slip.get('box_14_employment_income', 0):,.2f}"))
                self.t4_table.setItem(row_idx, 2, QTableWidgetItem(f"${slip.get('box_16_income_tax_deducted', 0):,.2f}"))
                self.t4_table.setItem(row_idx, 3, QTableWidgetItem(f"${slip.get('box_20_cpp_contributions', 0):,.2f}"))
                self.t4_table.setItem(row_idx, 4, QTableWidgetItem(f"${slip.get('box_26_ei_contributions', 0):,.2f}"))
    
    def _display_audit(self, data: Dict[str, Any]):
        """Display audit checklist"""
        text = f"""CRA AUDIT READINESS CHECKLIST - {data.get('year')}
{'='*60}

COMPLIANCE SCORE: {data.get('compliance_score', 0):.1f}%
STATUS: {data.get('status')}

CHECKLIST ITEMS:
"""
        for item in data.get('checklist_items', []):
            status_mark = "✓" if item.get('status') == 'PASS' else "✗"
            text += f"\n[{status_mark}] {item.get('category')} - {item.get('item')}\n"
            text += f"    Status: {item.get('status')} | Found: {item.get('found')} / Required: {item.get('required_count')}\n"
        
        text += f"\n\nRECOMMENDATIONS:\n"
        for rec in data.get('recommendations', []):
            text += f"  • {rec}\n"
        
        self.audit_display.setText(text)
    
    def _display_quarterly(self, data: Dict[str, Any]):
        """Display quarterly tax calculation"""
        text = f"""QUARTERLY TAX LIABILITY - Q{data.get('quarter')} {data.get('year')}
{'='*60}

INCOME SUMMARY:
  Gross Revenue: ${data.get('gross_revenue', 0):,.2f}
  Expenses: ${data.get('expenses', 0):,.2f}
  Net Income: ${data.get('net_income', 0):,.2f}

PAYROLL:
  Payroll Amount: ${data.get('payroll_amount', 0):,.2f}
  Withholdings: ${data.get('payroll_withholdings', 0):,.2f}

TAX LIABILITY:
  Corporate Income Tax: ${data.get('corporate_income_tax', 0):,.2f}
  WCB Liability: ${data.get('wcb_liability', 0):,.2f}
  GST Collected: ${data.get('gst_collected', 0):,.2f}
  GST Paid: ${data.get('gst_paid', 0):,.2f}
  Net GST Payable: ${data.get('net_gst_payable', 0):,.2f}

TOTAL TAX CALCULATION:
  Total Before Credits: ${data.get('total_tax_before_credits', 0):,.2f}
  Less Withholdings: ${data.get('less_withholdings', 0):,.2f}
  Net Tax Payable: ${data.get('net_tax_payable', 0):,.2f}

Due Date: {data.get('due_date')}
Status: {data.get('status')}
"""
        self.quarterly_display.setText(text)
    
    def _display_deductions(self, data: Dict[str, Any]):
        """Display deduction analysis"""
        text = f"""MISSING DEDUCTIONS ANALYSIS - {data.get('year')}
{'='*60}

POTENTIAL TAX SAVINGS: ${data.get('estimated_tax_relief', 0):,.2f}
High Priority Items: {data.get('high_priority_items', 0)}

DEDUCTION SUGGESTIONS:
"""
        for suggestion in data.get('deduction_suggestions', []):
            text += f"\n{suggestion.get('category')} [{suggestion.get('priority')}]\n"
            text += f"  Current: ${suggestion.get('current_amount', 0):,.2f}\n"
            if 'industry_average' in suggestion:
                text += f"  Industry Average: ${suggestion.get('industry_average', 0):,.2f}\n"
            text += f"  Potential Deduction: ${suggestion.get('potential_deduction', 0):,.2f}\n"
            text += f"  Tax Savings: ${suggestion.get('tax_savings', 0):,.2f}\n"
            text += f"  Recommendation: {suggestion.get('recommendation')}\n"
        
        text += f"\n\nNEXT STEPS:\n"
        for step in data.get('next_steps', []):
            text += f"  • {step}\n"
        
        self.deductions_display.setText(text)
    
    def _export_t2_pdf(self):
        """Export T2 as PDF"""
        QMessageBox.information(self, "Export", "PDF export will be available in next version")
    
    def _export_t4_slips(self):
        """Export all T4 slips"""
        QMessageBox.information(self, "Export", "Bulk T4 export will be available in next version")
    
    def _export_audit(self):
        """Export audit checklist"""
        QMessageBox.information(self, "Export", "Audit export will be available in next version")


if __name__ == "__main__":
    app = __import__('PyQt6.QtWidgets', fromlist=['QApplication']).QApplication(sys.argv)
    widget = TaxOptimizationWidget()
    widget.setWindowTitle("Tax Optimization")
    widget.setGeometry(100, 100, 1000, 700)
    widget.show()
    sys.exit(app.exec())
