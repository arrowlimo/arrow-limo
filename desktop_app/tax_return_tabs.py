from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class T1ReturnTab(QWidget):
    def __init__(self, host) -> None:
        super().__init__(host)
        self.host = host

        layout = QVBoxLayout(self)
        title = QLabel("T1 Personal Return Entry")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        form = QFormLayout()
        host.t1_taxpayer_name = QLineEdit("Paul Richard")
        host.t1_sin = QLineEdit()
        host.t1_t1_status = QLabel("Draft")
        host.t1_t1_status.setStyleSheet("font-weight: bold; color: #1f2937;")
        form.addRow("Taxpayer Name:", host.t1_taxpayer_name)
        form.addRow("SIN:", host.t1_sin)
        form.addRow("Status:", host.t1_t1_status)
        layout.addLayout(form)

        host.t1_lines_table = host._create_line_table(
            ["Line #", "Description", "Amount", "Notes"]
        )
        layout.addWidget(host.t1_lines_table)

        row_buttons = QHBoxLayout()
        add_btn = QPushButton("Add Line")
        add_btn.clicked.connect(
            lambda: host._add_line_row(host.t1_lines_table, ["", "", "0.00", ""])
        )
        row_buttons.addWidget(add_btn)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(lambda: host._delete_selected_rows(host.t1_lines_table))
        row_buttons.addWidget(remove_btn)

        save_btn = QPushButton("Save Draft")
        save_btn.clicked.connect(host.save_t1_return_draft)
        row_buttons.addWidget(save_btn)

        submit_btn = QPushButton("Save & Submit")
        submit_btn.setStyleSheet("background-color: #065f46; color: white;")
        submit_btn.clicked.connect(host.submit_t1_return)
        row_buttons.addWidget(submit_btn)

        row_buttons.addStretch()
        layout.addLayout(row_buttons)

        host._load_t1_form()


class T2ReturnTab(QWidget):
    def __init__(self, host) -> None:
        super().__init__(host)
        self.host = host

        layout = QVBoxLayout(self)
        title = QLabel("T2 Corporate Return Entry")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        form = QFormLayout()
        host.t2_corp_name = QLineEdit("Arrow Limousine Ltd.")
        host.t2_business_number = QLineEdit()
        host.t2_return_status = QLabel("Draft")
        host.t2_return_status.setStyleSheet("font-weight: bold; color: #1f2937;")
        form.addRow("Corporation Name:", host.t2_corp_name)
        form.addRow("Business Number:", host.t2_business_number)
        form.addRow("Status:", host.t2_return_status)
        layout.addLayout(form)

        host.t2_schedule125_table = host._create_line_table(
            ["Schedule", "Line #", "Description", "Amount", "Notes"]
        )
        host.t2_schedule100_table = host._create_line_table(
            ["Schedule", "Line #", "Description", "Amount", "Notes"]
        )
        layout.addWidget(QLabel("Schedule 125"))
        layout.addWidget(host.t2_schedule125_table)
        layout.addWidget(QLabel("Schedule 100"))
        layout.addWidget(host.t2_schedule100_table)

        row_buttons = QHBoxLayout()
        add_125 = QPushButton("Add 125 Line")
        add_125.clicked.connect(
            lambda: host._add_line_row(
                host.t2_schedule125_table, ["125", "", "", "0.00", ""]
            )
        )
        row_buttons.addWidget(add_125)

        add_100 = QPushButton("Add 100 Line")
        add_100.clicked.connect(
            lambda: host._add_line_row(
                host.t2_schedule100_table, ["100", "", "", "0.00", ""]
            )
        )
        row_buttons.addWidget(add_100)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(
            lambda: (
                host._delete_selected_rows(host.t2_schedule125_table),
                host._delete_selected_rows(host.t2_schedule100_table),
            )
        )
        row_buttons.addWidget(remove_btn)

        save_btn = QPushButton("Save Draft")
        save_btn.clicked.connect(host.save_t2_return_draft)
        row_buttons.addWidget(save_btn)

        submit_btn = QPushButton("Save & Submit")
        submit_btn.setStyleSheet("background-color: #0f766e; color: white;")
        submit_btn.clicked.connect(host.submit_t2_return)
        row_buttons.addWidget(submit_btn)

        row_buttons.addStretch()
        layout.addLayout(row_buttons)

        host._load_t2_form()


class PD7ATab(QWidget):
    def __init__(self, host) -> None:
        super().__init__(host)
        self.host = host

        layout = QVBoxLayout(self)
        title = QLabel("PD7A Source Deductions")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        form = QFormLayout()
        host.pd7a_month = QComboBox()
        host.pd7a_month.addItems([f"{m:02d}" for m in range(1, 13)])
        host.pd7a_month.currentTextChanged.connect(host._load_pd7a_form)
        form.addRow("Month:", host.pd7a_month)

        host.pd7a_employee_count = QDoubleSpinBox()
        host.pd7a_employee_count.setMaximum(99999)
        form.addRow("Employee Count:", host.pd7a_employee_count)

        host.pd7a_total_gross = QDoubleSpinBox()
        host.pd7a_total_gross.setMaximum(99999999)
        host.pd7a_total_gross.setPrefix("$")
        form.addRow("Total Gross Payroll:", host.pd7a_total_gross)

        host.pd7a_cpp_total = QDoubleSpinBox()
        host.pd7a_cpp_total.setMaximum(99999999)
        host.pd7a_cpp_total.setPrefix("$")
        form.addRow("CPP Total:", host.pd7a_cpp_total)

        host.pd7a_ei_total = QDoubleSpinBox()
        host.pd7a_ei_total.setMaximum(99999999)
        host.pd7a_ei_total.setPrefix("$")
        form.addRow("EI Total:", host.pd7a_ei_total)

        host.pd7a_income_tax = QDoubleSpinBox()
        host.pd7a_income_tax.setMaximum(99999999)
        host.pd7a_income_tax.setPrefix("$")
        form.addRow("Income Tax Deducted:", host.pd7a_income_tax)

        host.pd7a_total_due = QDoubleSpinBox()
        host.pd7a_total_due.setMaximum(99999999)
        host.pd7a_total_due.setPrefix("$")
        host.pd7a_total_due.setReadOnly(True)
        form.addRow("Total Remittance Due:", host.pd7a_total_due)

        host.pd7a_adjusted = QDoubleSpinBox()
        host.pd7a_adjusted.setMaximum(99999999)
        host.pd7a_adjusted.setPrefix("$")
        form.addRow("Adjusted Remittance:", host.pd7a_adjusted)

        host.pd7a_status = QLabel("Draft")
        host.pd7a_status.setStyleSheet("font-weight: bold; color: #1f2937;")
        form.addRow("Status:", host.pd7a_status)
        layout.addLayout(form)

        host.pd7a_notes = QTextEdit()
        host.pd7a_notes.setPlaceholderText("PD7A notes / filing reference / fixes")
        host.pd7a_notes.setMaximumHeight(90)
        layout.addWidget(host.pd7a_notes)

        host.pd7a_month_table = host._create_line_table(
            ["Month", "Employees", "Gross", "CPP", "EI", "Tax", "Due", "Adjusted", "Status"]
        )
        layout.addWidget(host.pd7a_month_table)

        row_buttons = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(host._load_pd7a_form)
        row_buttons.addWidget(refresh_btn)

        save_btn = QPushButton("Save Draft")
        save_btn.clicked.connect(host.save_pd7a_return_draft)
        row_buttons.addWidget(save_btn)

        submit_btn = QPushButton("Save & Submit")
        submit_btn.setStyleSheet("background-color: #7c2d12; color: white;")
        submit_btn.clicked.connect(host.submit_pd7a_return)
        row_buttons.addWidget(submit_btn)

        row_buttons.addStretch()
        layout.addLayout(row_buttons)

        host._load_pd7a_form()
