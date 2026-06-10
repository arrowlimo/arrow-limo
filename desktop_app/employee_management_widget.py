"""
Employee Management Widget - CRUD operations for employees
Features: Add/Update employees, HOS compliance tracking, work classifications,
payroll entry
"""

import logging
import re

from common_widgets import StandardDateEdit
from db_error_handling import DatabaseContext
from employee_drill_down import EmployeeDetailDialog
from PyQt6.QtCore import QDate, Qt, QTimer
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class SelectAllSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox variant that selects the full value on focus/click."""

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)


class EmployeeNumberTableItem(QTableWidgetItem):
    """Table item with natural sort for employee numbers like"
    "D013/H004/O021."""

    _code_re = re.compile(r"^([A-Z]+)(\d+)$")

    @classmethod
    def _sort_key(cls, value) -> object:
        text = (value or "").strip().upper().replace(" ", "")
        match = cls._code_re.match(text)
        if match:
            return (0, match.group(1), int(match.group(2)))
        return (1, text, 0)

    def __lt__(self, other) -> object:
        other_text = (
            other.text() if isinstance(other, QTableWidgetItem) else ""
        )
        return self._sort_key(self.text()) < self._sort_key(other_text)

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        QTimer.singleShot(0, self.selectAll)


class EmployeeManagementWidget(QWidget):
    """Complete employee management with CRUD, HOS, and payroll"""

    def __init__(self, db) -> None:
        super().__init__()
        self.db = db
        self.current_employee_id = None
        self.init_ui()
        self.load_employees()

    def init_ui(self) -> None:
        """Build the employee management interface"""
        layout = QVBoxLayout()

        # Breadcrumb navigation
        breadcrumb_layout = QHBoxLayout()
        back_btn = QPushButton("⬅ Back to Navigator")
        back_btn.setMaximumWidth(150)
        back_btn.clicked.connect(self.go_back)
        breadcrumb_layout.addWidget(back_btn)
        breadcrumb_layout.addWidget(
            QLabel("📍 Core Operations › Employee Management")
        )
        breadcrumb_layout.addStretch()
        layout.addLayout(breadcrumb_layout)

        # Header
        header = QLabel("<h2>👥 Employee Management</h2>")
        header.setStyleSheet("color: #2c3e50; padding: 10px;")
        layout.addWidget(header)

        # Action buttons at TOP
        btn_layout = QHBoxLayout()
        self.new_btn = QPushButton("➕ New Employee")
        self.new_btn.clicked.connect(self.new_employee)
        self.new_btn.setStyleSheet(
            "background-color: #27ae60; color: white; padding: 8px;"
        )
        btn_layout.addWidget(self.new_btn)

        self.detail_btn = QPushButton("📋 View Full Details")
        self.detail_btn.clicked.connect(self.open_employee_detail)
        self.detail_btn.setEnabled(False)
        btn_layout.addWidget(self.detail_btn)

        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self.delete_employee)
        self.delete_btn.setStyleSheet(
            "background-color: #e74c3c; color: white; padding: 8px;"
        )
        self.delete_btn.setEnabled(False)
        btn_layout.addWidget(self.delete_btn)

        # Bulk actions
        self.bulk_inactivate_btn = QPushButton("🚫 Mark ALL Drivers Inactive")
        self.bulk_inactivate_btn.setToolTip(
            "Set employment_status='inactive' for all chauffeurs/drivers"
        )
        self.bulk_inactivate_btn.setStyleSheet(
            "background-color: #f39c12; color: white; padding: 8px;"
        )
        self.bulk_inactivate_btn.clicked.connect(
            self.bulk_mark_all_drivers_inactive
        )
        btn_layout.addWidget(self.bulk_inactivate_btn)

        self.bulk_activate_selected_btn = QPushButton("✅ Activate Selected")
        self.bulk_activate_selected_btn.setToolTip(
            "Set employment_status='active' for selected rows in the table"
        )
        self.bulk_activate_selected_btn.setStyleSheet(
            "background-color: #2ecc71; color: white; padding: 8px;"
        )
        self.bulk_activate_selected_btn.clicked.connect(
            self.bulk_activate_selected
        )
        btn_layout.addWidget(self.bulk_activate_selected_btn)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_employees)
        btn_layout.addWidget(refresh_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Stats row
        stats_layout = self._create_stats_section()
        layout.addLayout(stats_layout)

        # Main splitter (left: list/search, right: form)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: Search and employee list
        left_panel = self._create_list_panel()
        splitter.addWidget(left_panel)

        # Right panel: Form tabs
        right_panel = self._create_form_panel()
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)
        self.setLayout(layout)

    def _create_stats_section(self) -> object:
        """Create stats cards"""
        stats = QHBoxLayout()

        self.total_emp_label = QLabel("Total: 0")
        self.drivers_label = QLabel("Drivers: 0")
        self.active_label = QLabel("Active: 0")
        self.payroll_label = QLabel("Monthly Payroll: $0")

        for lbl in [
            self.total_emp_label,
            self.drivers_label,
            self.active_label,
            self.payroll_label,
        ]:
            lbl.setStyleSheet("""
                background-color: #ecf0f1;
                padding: 15px;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            """)
            stats.addWidget(lbl)

        return stats

    def _create_list_panel(self) -> object:
        """Create left panel with search and employee list"""
        panel = QFrame()
        layout = QVBoxLayout()

        # Search section
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search employees...")
        self.search_input.textChanged.connect(self.load_employees)
        search_layout.addWidget(QLabel("Search:"))
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Filters
        filter_layout = QHBoxLayout()
        self.dept_filter = QComboBox()
        self.dept_filter.addItems(
            ["All Departments", "Operations", "Administration", "Maintenance"]
        )
        self.dept_filter.currentTextChanged.connect(self.load_employees)

        self.status_filter = QComboBox()
        self.status_filter.addItems(
            ["All Status", "active", "inactive", "on_leave"]
        )
        self.status_filter.currentTextChanged.connect(self.load_employees)

        filter_layout.addWidget(self.dept_filter)
        filter_layout.addWidget(self.status_filter)
        layout.addLayout(filter_layout)

        # Employee table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Emp #", "Name", "Position", "Phone", "Status", "Hire Date"]
        )
        self.table.cellDoubleClicked.connect(self.load_selected_employee)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        # Enable multi-select of entire rows for bulk actions
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
        )
        layout.addWidget(self.table)

        panel.setLayout(layout)
        return panel

    def go_back(self) -> None:
        """Return to Navigator tab"""
        parent = self.parent()
        while parent and not hasattr(parent, "tabs"):
            parent = parent.parent()
        if parent and hasattr(parent, "tabs"):
            parent.tabs.setCurrentIndex(0)  # Navigator is tab 0

    def _create_form_panel(self) -> object:
        """Create right panel with tabbed forms"""
        panel = QFrame()
        layout = QVBoxLayout()

        self.form_tabs = QTabWidget()

        # Tab 1: Basic Info
        basic_tab = self._create_basic_info_tab()
        self.form_tabs.addTab(basic_tab, "📝 Basic Info")

        # Tab 2: Work Classifications
        classification_tab = self._create_classification_tab()
        self.form_tabs.addTab(classification_tab, "💼 Classifications")

        # Tab 3: HOS Compliance
        hos_tab = self._create_hos_tab()
        self.form_tabs.addTab(hos_tab, "⚖️ HOS Compliance")

        # Tab 4: Payroll
        payroll_tab = self._create_payroll_tab()
        self.form_tabs.addTab(payroll_tab, "💰 Payroll")

        layout.addWidget(self.form_tabs)

        # Save/Delete buttons
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 Save Employee")
        self.save_btn.clicked.connect(self.save_employee)
        self.save_btn.setStyleSheet(
            "background-color: #3498db; color: white; padding: 10px;"
            "font-size: 14px;"
        )

        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self.delete_employee)
        self.delete_btn.setStyleSheet(
            "background-color: #e74c3c; color: white; padding: 10px;"
        )
        self.delete_btn.setEnabled(False)

        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.delete_btn)
        layout.addLayout(btn_layout)

        panel.setLayout(layout)
        return panel

    def _create_basic_info_tab(self) -> object:
        """Create basic employee information form"""
        widget = QWidget()
        form = QFormLayout()

        # Employee ID (read-only, greyed out)
        self.employee_id_display = QLineEdit()
        self.employee_id_display.setReadOnly(True)
        self.employee_id_display.setStyleSheet(
            "background-color: #ecf0f1; color: #7f8c8d;"
        )
        self.employee_id_display.setPlaceholderText("Auto-generated")

        # Employee Number (DR100, etc.)
        self.employee_number_input = QLineEdit()
        self.employee_number_input.setPlaceholderText("e.g., DR100, H04, OF5")

        self.name_input = QLineEdit()
        self.position_input = QLineEdit()
        self.department_input = QComboBox()
        self.department_input.addItems(
            ["Operations", "Administration", "Maintenance", "Other"]
        )

        self.phone_input = QLineEdit()
        self.email_input = QLineEdit()
        self.hire_date_input = StandardDateEdit(prefer_month_text=True)
        self.hire_date_input.setDate(QDate.currentDate())
        self.hire_date_input.setCalendarPopup(True)

        self.status_input = QComboBox()
        self.status_input.addItems(["active", "inactive", "on_leave"])

        self.is_driver_checkbox = QCheckBox("Is Chauffeur/Driver")
        self.is_dispatcher_checkbox = QCheckBox("Is Dispatcher")

        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(100)

        form.addRow("Employee ID:", self.employee_id_display)
        form.addRow("Employee #:", self.employee_number_input)
        form.addRow("Full Name:", self.name_input)
        form.addRow("Position:", self.position_input)
        form.addRow("Department:", self.department_input)
        form.addRow("Phone:", self.phone_input)
        form.addRow("Email:", self.email_input)
        form.addRow("Hire Date:", self.hire_date_input)
        form.addRow("Status:", self.status_input)
        form.addRow("", self.is_driver_checkbox)
        form.addRow("", self.is_dispatcher_checkbox)
        form.addRow("Notes:", self.notes_input)

        widget.setLayout(form)
        return widget

    def _create_classification_tab(self) -> object:
        """Create work classification management"""
        widget = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("<h3>Work Classifications</h3>"))

        form = QFormLayout()

        self.class_type_input = QComboBox()
        self.class_type_input.addItems(
            [
                "chauffeur",
                "dispatcher",
                "accountant",
                "bookkeeper",
                "cleaner",
                "part_time",
                "volunteer",
            ]
        )

        self.pay_structure_input = QComboBox()
        self.pay_structure_input.addItems(
            ["hourly", "salary", "contract", "volunteer"]
        )
        self.pay_structure_input.currentTextChanged.connect(
            self._toggle_pay_fields
        )

        self.hourly_rate_input = SelectAllSpinBox()
        self.hourly_rate_input.setRange(0, 999.99)
        self.hourly_rate_input.setPrefix("$")
        self.hourly_rate_input.setValue(20.00)

        self.hourly_rate_2_input = SelectAllSpinBox()
        self.hourly_rate_2_input.setRange(0, 999.99)
        self.hourly_rate_2_input.setPrefix("$")
        self.hourly_rate_2_input.setValue(10.00)

        self.monthly_salary_input = SelectAllSpinBox()
        self.monthly_salary_input.setRange(0, 99999.99)
        self.monthly_salary_input.setPrefix("$")

        self.salary_deferred_input = SelectAllSpinBox()
        self.salary_deferred_input.setRange(0, 99999.99)
        self.salary_deferred_input.setPrefix("$")
        self.salary_deferred_input.setToolTip(
            "Amount of salary deferred (for owners/partners)"
        )

        self.overtime_rate_input = SelectAllSpinBox()
        self.overtime_rate_input.setRange(0, 999.99)
        self.overtime_rate_input.setPrefix("$")
        self.overtime_rate_input.setValue(30.00)

        form.addRow("Classification Type:", self.class_type_input)
        form.addRow("Pay Structure:", self.pay_structure_input)
        form.addRow("Hourly Rate:", self.hourly_rate_input)
        form.addRow("Wage Rate 2:", self.hourly_rate_2_input)
        form.addRow("Monthly Salary:", self.monthly_salary_input)
        form.addRow("Salary Deferred:", self.salary_deferred_input)
        form.addRow("Overtime Rate:", self.overtime_rate_input)

        # --- Extra Tax Withholding (employee-requested, applied every period) ---
        separator = QLabel("<b>Extra Tax Withholding (Employee Request)</b>")
        separator.setStyleSheet(
            "color: #1a3c6d; margin-top: 10px; padding-top: 4px;"
            " border-top: 1px solid #bdc3c7;"
        )
        form.addRow(separator)

        self.extra_tax_type_input = QComboBox()
        self.extra_tax_type_input.addItem("$ Fixed Annual Amount", "$")
        self.extra_tax_type_input.addItem("% of Gross Per Period", "%")
        self.extra_tax_type_input.setToolTip(
            "How the extra withholding is specified:\n"
            "  $ — fixed annual dollar amount spread over pay periods\n"
            "  % — percentage of gross pay per period"
        )
        form.addRow("Extra Tax Type:", self.extra_tax_type_input)

        self.extra_tax_annual_input = SelectAllSpinBox()
        self.extra_tax_annual_input.setRange(0, 99999.99)
        self.extra_tax_annual_input.setPrefix("$")
        self.extra_tax_annual_input.setDecimals(2)
        self.extra_tax_annual_input.setToolTip(
            "Annual extra tax the employee wants withheld (TD1 Line 2).\n"
            "Divided by number of pay periods and added to each period's tax."
        )
        form.addRow("Extra Annual ($):", self.extra_tax_annual_input)

        self.extra_tax_pct_input = SelectAllSpinBox()
        self.extra_tax_pct_input.setRange(0, 50.00)
        self.extra_tax_pct_input.setSuffix(" %")
        self.extra_tax_pct_input.setDecimals(2)
        self.extra_tax_pct_input.setToolTip(
            "Extra percentage of gross to withhold as tax each period."
        )
        form.addRow("Extra Rate (%):", self.extra_tax_pct_input)

        def _toggle_extra_tax_fields(idx):
            is_pct = self.extra_tax_type_input.itemData(idx) == "%"
            self.extra_tax_annual_input.setEnabled(not is_pct)
            self.extra_tax_pct_input.setEnabled(is_pct)

        self.extra_tax_type_input.currentIndexChanged.connect(_toggle_extra_tax_fields)
        _toggle_extra_tax_fields(0)

        layout.addLayout(form)
        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _create_hos_tab(self) -> object:
        """Create HOS compliance tracking"""
        widget = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("<h3>⚖️ Hours of Service Compliance</h3>"))
        layout.addWidget(
            QLabel("<p>Red Deer Bylaw & Alberta Hours of Service Rules</p>")
        )

        # HOS limits
        info_text = QLabel("""
        <b>Regulatory Limits:</b><br>
        • Maximum 13 hours driving per day<br>
        • Maximum 70 hours in 7 days<br>
        • Minimum 8 hours off-duty between shifts<br>
        • Daily logs required for commercial drivers<br>
        • Red Deer City Bylaw: Valid Class 4 license required
        """)
        info_text.setStyleSheet(
            "background-color: #fff3cd; padding: 10px; border-radius: 5px;"
        )
        layout.addWidget(info_text)

        # Recent hours table
        layout.addWidget(QLabel("<b>Recent Hours (Last 7 Days):</b>"))
        self.hos_table = QTableWidget()
        self.hos_table.setColumnCount(4)
        self.hos_table.setHorizontalHeaderLabels(
            ["Date", "Start", "End", "Total Hours"]
        )
        layout.addWidget(self.hos_table)

        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _create_payroll_tab(self) -> object:
        """Create payroll entry and summary"""
        widget = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("<h3>💰 Payroll Summary</h3>"))

        # Quick stats
        stats_layout = QHBoxLayout()
        self.ytd_gross_label = QLabel("YTD Gross: $0")
        self.ytd_net_label = QLabel("YTD Net: $0")
        self.last_pay_label = QLabel("Last Pay Date: -")

        for lbl in [
            self.ytd_gross_label,
            self.ytd_net_label,
            self.last_pay_label,
        ]:
            lbl.setStyleSheet(
                "background-color: #e8f5e9; padding: 10px; border-radius: 5px;"
            )
            stats_layout.addWidget(lbl)

        layout.addLayout(stats_layout)

        # Recent pay table
        layout.addWidget(QLabel("<b>Recent Pay Periods:</b>"))
        self.payroll_table = QTableWidget()
        self.payroll_table.setColumnCount(6)
        self.payroll_table.setHorizontalHeaderLabels(
            ["Pay Date", "Period", "Gross", "Deductions", "Net", "Status"]
        )
        layout.addWidget(self.payroll_table)

        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _toggle_pay_fields(self, pay_structure) -> None:
        """Show/hide pay fields based on structure"""
        if pay_structure == "hourly":
            self.hourly_rate_input.setEnabled(True)
            self.monthly_salary_input.setEnabled(False)
        elif pay_structure == "salary":
            self.hourly_rate_input.setEnabled(False)
            self.monthly_salary_input.setEnabled(True)
        else:
            self.hourly_rate_input.setEnabled(True)
            self.monthly_salary_input.setEnabled(True)

    def new_employee(self) -> None:
        """Clear form for new employee"""
        self.current_employee_id = None
        self.employee_id_display.clear()
        self.employee_number_input.clear()
        self.name_input.clear()
        self.position_input.clear()
        self.phone_input.clear()
        self.email_input.clear()
        self.hire_date_input.setDate(QDate.currentDate())
        self.status_input.setCurrentText("active")
        self.is_driver_checkbox.setChecked(False)
        self.is_dispatcher_checkbox.setChecked(False)
        self.notes_input.clear()
        self.hourly_rate_input.setValue(20.00)
        self.hourly_rate_2_input.setValue(10.00)
        self.extra_tax_type_input.setCurrentIndex(0)
        self.extra_tax_annual_input.setValue(0.0)
        self.extra_tax_pct_input.setValue(0.0)
        self.delete_btn.setEnabled(False)
        self.name_input.setFocus()
        self.form_tabs.setCurrentIndex(0)

    def load_selected_employee(self, row, column=None) -> None:
        """Load selected employee from table - triggered by double-click or"
        "manual selection"""

        try:
            # Get employee_id from column 0 (Emp #) which stores it in UserRole
            emp_num_item = self.table.item(row, 0)
            if not emp_num_item:
                return

            emp_id = emp_num_item.data(Qt.ItemDataRole.UserRole)
            if not emp_id:
                return

            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT employee_id, employee_number, full_name, position,
                           cell_phone, email, employee_category, phone,
                           hire_date, employment_status, is_chauffeur,
                           hourly_rate, hourly_pay_rate,
                           COALESCE(extra_tax_type, '$') AS extra_tax_type,
                           COALESCE(extra_tax_annual, 0) AS extra_tax_annual,
                           COALESCE(extra_tax_pct, 0)    AS extra_tax_pct
                    FROM employees
                    WHERE employee_id = %s
                    LIMIT 1
                """,
                    (emp_id,),
                )

                result = cur.fetchone()
            if result:
                self.current_employee_id = result[0]
                self.employee_id_display.setText(str(result[0]))
                self.employee_number_input.setText(result[1] or "")
                self.name_input.setText(result[2] or "")
                self.position_input.setText(result[3] or "")
                self.phone_input.setText(result[4] or "")
                self.email_input.setText(result[5] or "")

                # Set department from employee_category
                dept = result[6] or "Operations"
                dept_idx = self.department_input.findText(dept)
                if dept_idx >= 0:
                    self.department_input.setCurrentIndex(dept_idx)

                if result[8]:
                    self.hire_date_input.setDate(
                        QDate.fromString(str(result[8]), "yyyy-MM-dd")
                    )

                status = result[9] or "active"
                idx = self.status_input.findText(status)
                if idx >= 0:
                    self.status_input.setCurrentIndex(idx)

                self.is_driver_checkbox.setChecked(result[10] or False)
                self.is_dispatcher_checkbox.setChecked(
                    False
                )  # No dispatcher column
                self.notes_input.setPlainText("")
                self.hourly_rate_input.setValue(float(result[11] or 20.0))
                self.hourly_rate_2_input.setValue(float(result[12] or 10.0))

                # Extra tax withholding
                extra_tax_type = result[13] or '$'
                extra_tax_annual = float(result[14] or 0)
                extra_tax_pct = float(result[15] or 0)
                type_idx = self.extra_tax_type_input.findData(extra_tax_type)
                if type_idx >= 0:
                    self.extra_tax_type_input.setCurrentIndex(type_idx)
                self.extra_tax_annual_input.setValue(extra_tax_annual)
                self.extra_tax_pct_input.setValue(extra_tax_pct)

                self.delete_btn.setEnabled(True)
                self.detail_btn.setEnabled(True)  # Enable full details button
                self.load_employee_classifications()
                self.load_employee_hos()
                self.load_employee_payroll()

        except Exception as e:
            logger.error(f"Failed to load employee: {e}")
            QMessageBox.warning(
                self, "Load Error", f"Failed to load employee: {e}"
            )

    def open_employee_detail(self) -> None:
        """Open comprehensive employee detail dialog"""
        if not self.current_employee_id:
            QMessageBox.warning(
                self, "No Selection", "Please select an employee first"
            )
            return

        dialog = EmployeeDetailDialog(
            self.db, self.current_employee_id, parent=self
        )
        dialog.exec()

    def load_employees(self) -> None:
        """Load employees matching search/filters"""
        search_text = self.search_input.text().strip()
        dept_filter = self.dept_filter.currentText()
        status_filter = self.status_filter.currentText()

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                where_clauses = []
                params = []

                if search_text:
                    where_clauses.append(
                        "(full_name ILIKE %s OR cell_phone ILIKE %s OR email "
                        "ILIKE %s)"
                    )
                    params.extend(
                        [
                            f"%{search_text}%",
                            f"%{search_text}%",
                            f"%{search_text}%",
                        ]
                    )

                # Apply department filter
                if dept_filter and dept_filter != "All Departments":
                    where_clauses.append("department = %s")
                    params.append(dept_filter)

                # Apply status filter
                if status_filter and status_filter != "All Status":
                    where_clauses.append("employment_status = %s")
                    params.append(status_filter)

                where_sql = (
                    " AND ".join(where_clauses) if where_clauses else "1=1"
                )

                query = f"""
                    SELECT employee_id, employee_number, full_name, position,
                    cell_phone, employment_status, hire_date
                    FROM employees
                    WHERE {where_sql}
                    ORDER BY employee_number NULLS LAST, full_name
                    LIMIT 100
                """

                cur.execute(query, params)
                rows = cur.fetchall()

            sorting_enabled = self.table.isSortingEnabled()
            self.table.setSortingEnabled(False)
            self.table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                # r: (employee_id, employee_number, full_name, position,
                # cell_phone, employment_status, hire_date)
                emp_num_item = EmployeeNumberTableItem(r[1] or "")
                # Store employee_id on the emp_num cell for easy retrieval
                # during bulk actions
                emp_num_item.setData(Qt.ItemDataRole.UserRole, r[0])
                self.table.setItem(i, 0, emp_num_item)
                self.table.setItem(i, 1, QTableWidgetItem(r[2] or ""))
                self.table.setItem(i, 2, QTableWidgetItem(r[3] or ""))
                self.table.setItem(i, 3, QTableWidgetItem(r[4] or ""))
                self.table.setItem(i, 4, QTableWidgetItem(str(r[5] or "")))
                self.table.setItem(i, 5, QTableWidgetItem(str(r[6] or "")))

            self.table.setSortingEnabled(sorting_enabled)
            if (
                sorting_enabled
                and self.table.horizontalHeader().sortIndicatorSection() < 0
            ):
                # Default sort by name so duplicate scanning is easier.
                self.table.sortItems(1, Qt.SortOrder.AscendingOrder)

            self.update_stats()

        except Exception as e:
            logger.error(f"Failed to load employees: {e}")
            QMessageBox.warning(
                self, "Load Error", f"Failed to load employees: {e}"
            )

    def update_stats(self) -> None:
        """Update statistics cards"""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                # Total employees
                cur.execute(
                    "SELECT COUNT(*) FROM employees WHERE employment_status ="
                    "'active'"
                )
                total = cur.fetchone()[0] or 0
                self.total_emp_label.setText(f"Total: {total}")

                # Drivers
                cur.execute(
                    "SELECT COUNT(*) FROM employees WHERE is_chauffeur = TRUE "
                    "AND employment_status = 'active'"
                )
                drivers = cur.fetchone()[0] or 0
                self.drivers_label.setText(f"Drivers: {drivers}")

                # Active today (placeholder - could check schedules)
                self.active_label.setText(f"Active: {total}")

                # Monthly payroll estimate
                cur.execute("""
                    SELECT COALESCE(SUM(monthly_salary), 0)
                    FROM employee_work_classifications
                    WHERE is_active = TRUE AND pay_structure = 'salary'
                """)
                monthly = cur.fetchone()[0] or 0
                self.payroll_label.setText(
                    f"Monthly Payroll: ${float(monthly):,.2f}"
                )

        except Exception as e:
            logger.error("Stats update error: %s", e)

    def load_employee_classifications(self) -> None:
        """Load work classifications for current employee"""
        if not self.current_employee_id:
            return

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT classification_type, pay_structure, hourly_rate,
                           monthly_salary, salary_deferred, overtime_rate
                    FROM employee_work_classifications
                    WHERE employee_id = %s AND is_active = TRUE
                    ORDER BY effective_start_date DESC
                    LIMIT 1
                """,
                    (self.current_employee_id,),
                )

                result = cur.fetchone()
            if result:
                idx = self.class_type_input.findText(result[0])
                if idx >= 0:
                    self.class_type_input.setCurrentIndex(idx)

                idx = self.pay_structure_input.findText(result[1])
                if idx >= 0:
                    self.pay_structure_input.setCurrentIndex(idx)

                if result[2] and self.hourly_rate_input.value() <= 0:
                    self.hourly_rate_input.setValue(float(result[2]))
                if result[3]:
                    self.monthly_salary_input.setValue(float(result[3]))
                if result[4]:
                    self.salary_deferred_input.setValue(float(result[4]))
                if result[5]:
                    self.overtime_rate_input.setValue(float(result[5]))

        except Exception as e:
            logger.error("Classification load error: %s", e)

    def load_employee_hos(self) -> None:
        """Load HOS compliance data"""
        if not self.current_employee_id:
            return

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                # Note: employee_schedules table is empty - using pay_periods
                # as
                # alternative
                cur.execute(
                    """
                    SELECT pp.period_start_date, NULL as scheduled_start_time,
                           NULL as scheduled_end_time,
                           NULL as total_hours_worked
                    FROM pay_periods pp
                    JOIN employee_pay_master epm ON pp.pay_period_id =
                    epm.pay_period_id
                    WHERE epm.employee_id = %s
                      AND pp.period_start_date
                          >= CURRENT_DATE - INTERVAL '7 days'
                    ORDER BY pp.period_start_date DESC
                    LIMIT 10
                """,
                    (self.current_employee_id,),
                )

                rows = cur.fetchall()
            self.hos_table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                self.hos_table.setItem(i, 0, QTableWidgetItem(str(r[0])))
                self.hos_table.setItem(i, 1, QTableWidgetItem(str(r[1] or "")))
                self.hos_table.setItem(i, 2, QTableWidgetItem(str(r[2] or "")))
                self.hos_table.setItem(
                    i, 3, QTableWidgetItem(str(r[3] or "0.0"))
                )

        except Exception as e:
            logger.error("HOS load error: %s", e)

    def load_employee_payroll(self) -> None:
        """Load payroll summary"""
        if not self.current_employee_id:
            return

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                # YTD stats - using employee_pay_master instead of
                # non_charter_payroll
                cur.execute(
                    """
                    SELECT COALESCE(SUM(gross_pay), 0),
                           COALESCE(SUM(net_pay), 0),
                           MAX(created_at::date)
                    FROM employee_pay_master
                    WHERE employee_id = %s
                      AND fiscal_year = EXTRACT(YEAR FROM CURRENT_DATE)
                """,
                    (self.current_employee_id,),
                )

                ytd = cur.fetchone()
                if ytd:
                    self.ytd_gross_label.setText(
                        f"YTD Gross: ${float(ytd[0] or 0):,.2f}"
                    )
                    self.ytd_net_label.setText(
                        f"YTD Net: ${float(ytd[1] or 0):,.2f}"
                    )
                    self.last_pay_label.setText(f"Last Pay: {ytd[2] or '-'}")

                # Recent pays - using employee_pay_master instead of
                # non_charter_payroll
                cur.execute(
                    """
                    SELECT epm.created_at::date,
                           pp.period_start_date || ' to '
                               || pp.period_end_date as period,
                           epm.gross_pay, epm.total_deductions,
                           epm.net_pay, 'paid' as status
                    FROM employee_pay_master epm
                    JOIN pay_periods pp ON epm.pay_period_id = pp.pay_period_id
                    WHERE epm.employee_id = %s
                    ORDER BY epm.created_at DESC
                    LIMIT 10
                """,
                    (self.current_employee_id,),
                )

                rows = cur.fetchall()
            self.payroll_table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                self.payroll_table.setItem(
                    i, 0, QTableWidgetItem(str(r[0] or ""))
                )
                self.payroll_table.setItem(
                    i, 1, QTableWidgetItem(str(r[1] or ""))
                )
                self.payroll_table.setItem(
                    i, 2, QTableWidgetItem(f"${float(r[2] or 0):,.2f}")
                )
                self.payroll_table.setItem(
                    i, 3, QTableWidgetItem(f"${float(r[3] or 0):,.2f}")
                )
                self.payroll_table.setItem(
                    i, 4, QTableWidgetItem(f"${float(r[4] or 0):,.2f}")
                )
                self.payroll_table.setItem(
                    i, 5, QTableWidgetItem(str(r[5] or ""))
                )

        except Exception as e:
            logger.error("Payroll load error: %s", e)

    def save_employee(self) -> None:
        """Save or update employee"""
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(
                self, "Validation", "Employee name is required"
            )
            self.name_input.setFocus()
            return

        emp_number = self.employee_number_input.text().strip() or None
        position = self.position_input.text().strip() or None
        department = self.department_input.currentText()
        phone = self.phone_input.text().strip() or None
        email = self.email_input.text().strip() or None
        hire_date = self.hire_date_input.date().toString("MM/dd/yyyy")
        status = self.status_input.currentText()
        is_driver = self.is_driver_checkbox.isChecked()
        hourly_rate = self.hourly_rate_input.value()
        hourly_rate_2 = self.hourly_rate_2_input.value()
        self.is_dispatcher_checkbox.isChecked()
        self.notes_input.toPlainText().strip() or None

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                if self.current_employee_id:
                    # Update - NOTE: department column doesn't exist in DB, use
                    # employee_category instead
                    extra_tax_type = self.extra_tax_type_input.currentData() or '$'
                    extra_tax_annual = self.extra_tax_annual_input.value()
                    extra_tax_pct = self.extra_tax_pct_input.value()
                    cur.execute(
                        """
                        UPDATE employees
                        SET employee_number = %s, full_name = %s,
                        position = %s,
                            employee_category = %s, cell_phone = %s,
                            email = %s,
                            hire_date = %s, employment_status = %s,
                                                        is_chauffeur = %s,
                                                        hourly_rate = %s,
                                                        hourly_pay_rate = %s,
                                                        extra_tax_type = %s,
                                                        extra_tax_annual = %s,
                                                        extra_tax_pct = %s
                        WHERE employee_id = %s
                    """,
                        (
                            emp_number,
                            name,
                            position,
                            department,
                            phone,
                            email,
                            hire_date,
                            status,
                            is_driver,
                            hourly_rate,
                            hourly_rate_2,
                            extra_tax_type,
                            extra_tax_annual,
                            extra_tax_pct,
                            self.current_employee_id,
                        ),
                    )

                    # Update classification
                    cur.execute(
                        """
                        INSERT INTO employee_work_classifications
                        (employee_id, classification_type, pay_structure,
                        hourly_rate,
                         monthly_salary, salary_deferred, overtime_rate,
                         effective_start_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_DATE)
                        ON CONFLICT DO NOTHING
                    """,
                        (
                            self.current_employee_id,
                            self.class_type_input.currentText(),
                            self.pay_structure_input.currentText(),
                            self.hourly_rate_input.value(),
                            self.monthly_salary_input.value(),
                            self.salary_deferred_input.value(),
                            self.overtime_rate_input.value(),
                        ),
                    )

                    QMessageBox.information(
                        self,
                        "Saved",
                        f"Employee #{self.current_employee_id} updated",
                    )
                else:
                    # Insert-or-update guard to prevent duplicate employee rows
                    # when the same person is re-entered.
                    cur.execute(
                        """
                        SELECT employee_id
                        FROM employees
                        WHERE (
                            %s IS NOT NULL
                            AND employee_number IS NOT NULL
                            AND LOWER(TRIM(employee_number)) = LOWER(TRIM(%s))
                        )
                        OR LOWER(TRIM(REGEXP_REPLACE(
                            COALESCE(full_name, ''), '\\s+', ' ', 'g')))
                           = LOWER(TRIM(REGEXP_REPLACE(
                               COALESCE(%s, ''), '\\s+', ' ', 'g')))
                        ORDER BY employee_id
                        LIMIT 1
                    """,
                        (emp_number, emp_number, name),
                    )
                    existing = cur.fetchone()

                    if existing:
                        emp_id = existing[0]
                        extra_tax_type = self.extra_tax_type_input.currentData() or '$'
                        extra_tax_annual = self.extra_tax_annual_input.value()
                        extra_tax_pct = self.extra_tax_pct_input.value()
                        cur.execute(
                            """
                            UPDATE employees
                            SET employee_number = COALESCE(%s,
                            employee_number),
                                full_name = %s,
                                position = %s,
                                employee_category = %s,
                                cell_phone = %s,
                                email = %s,
                                hire_date = %s,
                                employment_status = %s,
                                is_chauffeur = %s,
                                hourly_rate = %s,
                                hourly_pay_rate = %s,
                                extra_tax_type = %s,
                                extra_tax_annual = %s,
                                extra_tax_pct = %s
                            WHERE employee_id = %s
                        """,
                            (
                                emp_number,
                                name,
                                position,
                                department,
                                phone,
                                email,
                                hire_date,
                                status,
                                is_driver,
                                hourly_rate,
                                hourly_rate_2,
                                extra_tax_type,
                                extra_tax_annual,
                                extra_tax_pct,
                                emp_id,
                            ),
                        )
                        self.current_employee_id = emp_id
                    else:
                        extra_tax_type = self.extra_tax_type_input.currentData() or '$'
                        extra_tax_annual = self.extra_tax_annual_input.value()
                        extra_tax_pct = self.extra_tax_pct_input.value()
                        cur.execute(
                            """
                            INSERT INTO employees
                            (employee_number, full_name, position,
                            employee_category,
                             cell_phone, email, hire_date, employment_status,
                             is_chauffeur,
                             hourly_rate, hourly_pay_rate,
                             extra_tax_type, extra_tax_annual, extra_tax_pct)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING employee_id
                        """,
                            (
                                emp_number,
                                name,
                                position,
                                department,
                                phone,
                                email,
                                hire_date,
                                status,
                                is_driver,
                                hourly_rate,
                                hourly_rate_2,
                                extra_tax_type,
                                extra_tax_annual,
                                extra_tax_pct,
                            ),
                        )
                        emp_id = cur.fetchone()[0]
                        self.current_employee_id = emp_id

                    # Add classification
                    cur.execute(
                        """
                        INSERT INTO employee_work_classifications
                        (employee_id, classification_type, pay_structure,
                        hourly_rate,
                         monthly_salary, salary_deferred, overtime_rate,
                         effective_start_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_DATE)
                    """,
                        (
                            emp_id,
                            self.class_type_input.currentText(),
                            self.pay_structure_input.currentText(),
                            self.hourly_rate_input.value(),
                            self.monthly_salary_input.value(),
                            self.salary_deferred_input.value(),
                            self.overtime_rate_input.value(),
                        ),
                    )

                    if existing:
                        QMessageBox.information(
                            self,
                            "Saved",
                            f"Employee #{emp_id} updated (matched existing)",
                        )
                    else:
                        QMessageBox.information(
                            self, "Saved", f"Employee #{emp_id} created"
                        )

            self.load_employees()
            self.search_input.clear()

        except Exception as e:
            logger.error(f"Failed to save employee: {e}")
            QMessageBox.critical(
                self, "Save Failed", f"Could not save employee:\n{e}"
            )

    def delete_employee(self) -> None:
        """Delete employee (with confirmation)"""
        if not self.current_employee_id:
            return

        response = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete employee #{self.current_employee_id}?\nThis action"
            f"cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if response == QMessageBox.StandardButton.Yes:
            try:
                with DatabaseContext(self.db, auto_commit=True) as cur:
                    cur.execute(
                        "UPDATE employees SET employment_status = 'inactive'"
                        "WHERE employee_id = %s",
                        (self.current_employee_id,),
                    )
                QMessageBox.information(
                    self, "Deleted", "Employee marked inactive"
                )
                self.new_employee()
                self.load_employees()
            except Exception as e:
                logger.error(f"Failed to delete employee: {e}")
                QMessageBox.critical(
                    self, "Delete Failed", f"Could not delete employee:\n{e}"
                )

    def _selected_employee_ids(self) -> object:
        """Return list of employee_ids for selected table rows."""
        ids = []
        try:
            for idx in self.table.selectionModel().selectedRows():
                row = idx.row()
                item = self.table.item(row, 0)
                if item is None:
                    continue
                emp_id = item.data(Qt.ItemDataRole.UserRole)
                if emp_id:
                    ids.append(emp_id)
        except Exception:
            pass
        return ids

    def bulk_mark_all_drivers_inactive(self) -> None:
        """Set employment_status='inactive' for all chauffeurs/drivers."""
        confirm = QMessageBox.question(
            self,
            "Confirm Bulk Inactivation",
            "Mark ALL drivers (is_chauffeur=TRUE) as INACTIVE?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute("""
                    UPDATE employees
                    SET employment_status = 'inactive'
                    WHERE is_chauffeur = TRUE
                        AND employment_status <> 'inactive'
                    """)
            QMessageBox.information(
                self, "Completed", "All drivers marked inactive."
            )
            self.load_employees()
        except Exception as e:
            logger.error(f"Failed to mark drivers inactive: {e}")
            QMessageBox.critical(
                self,
                "Bulk Update Failed",
                f"Could not mark drivers inactive:\n{e}",
            )

    def bulk_activate_selected(self) -> None:
        """Activate selected employees in the table."""
        ids = self._selected_employee_ids()
        if not ids:
            QMessageBox.information(
                self,
                "No Selection",
                "Select one or more employees to activate.",
            )
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                # Use IN clause; build placeholders safely
                placeholders = ",".join(["%s"] * len(ids))
                sql = (
                    "UPDATE employees SET employment_status='active'"
                    f" WHERE employee_id IN ({placeholders})"
                )
                cur.execute(sql, ids)
            QMessageBox.information(
                self, "Completed", f"Activated {len(ids)} employee(s)."
            )
            self.load_employees()
        except Exception as e:
            logger.error(f"Failed to activate selected employees: {e}")
            QMessageBox.critical(
                self,
                "Bulk Update Failed",
                f"Could not activate selected employees:\n{e}",
            )
