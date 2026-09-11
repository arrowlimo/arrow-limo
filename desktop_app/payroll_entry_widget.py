"""
Payroll Entry Widget
Manual payroll data entry and editing for employee_pay_master.
Allows selecting an employee and pay period, loading existing records,
editing hours/pay/deductions,
and saving back with transaction safety.
"""

import logging
import getpass
import re
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

from db_error_handling import DatabaseContext
from employee_pay_ledger_widget import EmployeePayLedgerWidget
from employee_work_items import (
    EmployeeWorkItemsDialog,
    ensure_employee_work_items_table,
    get_work_item_summary,
    get_work_items,
)
from employee_pay_banking_linker import (
    auto_link_pending_employee_pay_transactions,
)
from payroll_t4_review import T4ManualOverrideDialog, build_t4_readiness_lines
from PyQt6.QtCore import QDate, Qt, QTimer, QUrl, pyqtSlot
from PyQt6.QtGui import QBrush, QColor, QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_APP_ROOT = (
    Path(sys.executable).parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent.parent
)

logger = logging.getLogger(__name__)

PAY2_NOTE_PATTERN = re.compile(
    r"\[PAY2\s+hours=(?P<hours>-?\d+(?:\.\d+)?)\s+"
    r"rate=(?P<rate>-?\d+(?:\.\d+)?)\]",
    re.IGNORECASE,
)
EXTRA_TAX_NOTE_PATTERN = re.compile(
    r"\[EXTRA_TAX\s+annual=(?P<annual>-?\d+(?:\.\d+)?)\]",
    re.IGNORECASE,
)

EI_EXEMPT_EMPLOYEE_NUMBERS = {"dr09", "dr100"}

PAY_PRINTOUT_TOTAL_HOURS_DEFAULT = "Total Hours: 0.00"
PAY_PRINTOUT_TOTAL_GRATUITY_DEFAULT = "Total Gratuity: $0.00"
TITLE_MISSING_SELECTION = "Missing Selection"
TITLE_VERIFICATION_ONLY = "Verification Only"
TITLE_MISSING_DEPENDENCY = "Missing Dependency"
MSG_SELECT_EMPLOYEE_AND_PERIOD = "Select an employee and pay period first."
MSG_SELECT_EMPLOYEE = "Select an employee first."
LABEL_CPP_EMPLOYEE = "CPP Employee"
LABEL_EI_EMPLOYEE = "EI Employee"
LABEL_TOTAL_DEDUCTIONS = "Total Deductions"
LABEL_NET_PAY = "Net Pay"
MAX_REASONABLE_DEDUCTION_RATIO = 0.50


class SelectAllDoubleSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox that selects its full value on focus/click for easy"
    "overwrite."""


    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        QTimer.singleShot(0, self.selectAll)


class PayrollEntryWidget(QWidget):
    """Manual payroll entry and edit form."""

    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        ensure_employee_work_items_table(self.db)
        self._employee_search_typing = False
        self._loading_entry = False
        self._saving_entry = False
        self._auto_save_dirty = False
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.setInterval(800)
        self._auto_save_timer.timeout.connect(self._auto_save_pending_changes)
        self.pay_periods = []
        self.employee_lookup = {}
        self._printout_total_hours = 0.0
        self._printout_total_hours_1 = 0.0
        self._printout_total_hours_2 = 0.0
        self._printout_total_gratuity = 0.0
        self._printout_verification_only = False
        self._last_synced_charter_hours = None
        self._last_synced_approved_hours = None
        self._last_synced_gratuity = None
        self._updating_printout_table = False
        self._warned_cra_fallback_years: set[int] = set()
        self.current_charter_row = -1  # Track current charter being edited
        self._build_ui()
        self._connect_auto_persist_signals()
        self.load_employees()
        current_year = QDate.currentDate().year()
        self._populate_years(current_year)
        self.load_pay_periods(current_year)

    def _build_ui(self) -> None:
        # Main layout for the widget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        # Container widget for all content
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QLabel("<h2>🧾 Payroll Entry</h2>")
        header.setStyleSheet("padding: 6px; color: #1f2937;")
        layout.addWidget(header)

        layout.addWidget(
            QLabel(
                "Select an employee and pay period, load the record, edit"
                "fields, then save."

            )
        )

        lookup = self._build_lookup_row()
        layout.addLayout(lookup)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #2563eb; font-weight: bold;")
        layout.addWidget(self.status_label)

        self.t4_override_status_label = QLabel(
            "T4 override status: select employee and year."
        )
        self.t4_override_status_label.setStyleSheet(
            "color: #6b7280; font-weight: bold;"
        )
        layout.addWidget(self.t4_override_status_label)

        layout.addWidget(self._build_hours_group())
        layout.addWidget(self._build_pay_group())
        layout.addWidget(self._build_deductions_group())
        layout.addWidget(self._build_deduction_comparison_group())
        layout.addWidget(self._build_pay_printout_group())
        layout.addWidget(self._build_pd7a_group())
        layout.addWidget(self._build_pay_event_group())
        layout.addWidget(self._build_hiring_form_group())
        layout.addWidget(self._build_metadata_group())

        self.pay_ledger = EmployeePayLedgerWidget(self.db)
        layout.addWidget(self.pay_ledger)

        layout.addStretch()

        # Set container as scroll area widget
        self.scroll_area.setWidget(container)
        main_layout.addWidget(self.scroll_area)

    def _build_lookup_row(self) -> QHBoxLayout:
        row = QHBoxLayout()

        self.employee_combo = QComboBox()
        self.employee_combo.setEditable(True)
        self.employee_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.employee_combo.setPlaceholderText("Employee")
        self._setup_employee_search()
        self.employee_combo.activated.connect(self._on_employee_selected)
        row.addWidget(QLabel("Employee:"))
        row.addWidget(self.employee_combo, stretch=2)

        # Employee Filter (for historical year selection)
        self.employee_filter_combo = QComboBox()
        self.employee_filter_combo.addItems(
            [
                "Active in Selected Year",
                "Currently Active Only",
                "All Employees",
            ]
        )
        self.employee_filter_combo.setToolTip(
            "Active in Selected Year: Shows employees who worked during the"
            "selected year\n"

            "Currently Active Only: Shows only currently active employees\n"
            "All Employees: Shows all employees regardless of status"
        )
        self.employee_filter_combo.currentTextChanged.connect(
            self._on_filter_changed
        )
        row.addWidget(self.employee_filter_combo)

        self.year_combo = QComboBox()
        self.year_combo.currentTextChanged.connect(self._on_year_changed)
        row.addWidget(QLabel("Year:"))
        row.addWidget(self.year_combo)

        self.pay_period_combo = QComboBox()
        self.pay_period_combo.currentIndexChanged.connect(
            self._load_pay_printout
        )
        self.pay_period_combo.currentIndexChanged.connect(
            self._load_monthly_remittance_summary
        )
        self.pay_period_combo.currentIndexChanged.connect(
            self._refresh_pay_ledger
        )
        self.pay_period_combo.currentIndexChanged.connect(
            self._auto_load_entry_for_selection
        )
        self.pay_period_combo.currentIndexChanged.connect(
            self._load_ytd_totals
        )
        self.pay_period_combo.currentIndexChanged.connect(
            self._refresh_work_item_summary
        )
        row.addWidget(QLabel("Pay Period:"))
        row.addWidget(self.pay_period_combo, stretch=2)

        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self.load_entry)
        row.addWidget(load_btn)

        self.save_btn = QPushButton("Save")
        self.save_btn.setStyleSheet("background-color: #2563eb; color: white;")
        self.save_btn.clicked.connect(self.save_entry)
        row.addWidget(self.save_btn)

        reset_btn = QPushButton("Clear")
        reset_btn.clicked.connect(self.clear_form)
        row.addWidget(reset_btn)

        recalc_btn = QPushButton("Recalculate")
        recalc_btn.setToolTip(
            "Recalculate base pay from hours x rates (rates will NOT change)"
        )
        recalc_btn.clicked.connect(
            lambda: self.recalculate_totals(force_base_pay=True)
        )
        row.addWidget(recalc_btn)

        print_t4_btn = QPushButton("Print Official T4")
        print_t4_btn.setStyleSheet("background-color: #059669; color: white;")
        print_t4_btn.clicked.connect(self.print_official_t4)
        row.addWidget(print_t4_btn)

        manual_t4_btn = QPushButton("T4 Manual Override")
        manual_t4_btn.setStyleSheet(
            "background-color: #92400e; color: white;"
        )
        manual_t4_btn.setToolTip(
            "Enter or adjust T4 box values for the selected employee/year."
            " Official T4 print will prefer these saved values."
        )
        manual_t4_btn.clicked.connect(self.open_t4_manual_override_dialog)
        row.addWidget(manual_t4_btn)

        t4_readiness_btn = QPushButton("T4 Readiness")
        t4_readiness_btn.setStyleSheet(
            "background-color: #0f766e; color: white;"
        )
        t4_readiness_btn.setToolTip(
            "Check SIN/address completeness and loaded year coverage before"
            "printing T4"

        )
        t4_readiness_btn.clicked.connect(self.show_t4_readiness)
        row.addWidget(t4_readiness_btn)

        print_statement_btn = QPushButton("Print Pay Statement")
        print_statement_btn.setStyleSheet(
            "background-color: #0ea5e9; color: white;"
        )
        print_statement_btn.clicked.connect(self.print_pay_statement)
        row.addWidget(print_statement_btn)

        print_register_btn = QPushButton("Print Payroll Register")
        print_register_btn.setStyleSheet(
            "background-color: #1d4ed8; color: white;"
        )
        print_register_btn.setToolTip(
            "Print combined charter rows, non-charter work items, and"
            " payroll deduction/contribution breakdown for this period."
        )
        print_register_btn.clicked.connect(self.print_payroll_register)
        row.addWidget(print_register_btn)

        open_ledger_btn = QPushButton("Open Payment Ledger")
        open_ledger_btn.setStyleSheet(
            "background-color: #374151; color: white;"
        )
        open_ledger_btn.setToolTip(
            "Jump to Add/Edit/Delete employee payment entries"
        )
        open_ledger_btn.clicked.connect(self.open_payment_ledger)
        row.addWidget(open_ledger_btn)

        return row

    def _setup_employee_search(self) -> None:
        """Enable type-to-search for employee picker (case-insensitive"
        "contains match)."""

        line_edit = self.employee_combo.lineEdit()
        # Disable QComboBox inline completer so typing does not auto-select a
        # row.
        self.employee_combo.setCompleter(None)
        if line_edit:
            line_edit.setCompleter(None)
            line_edit.setPlaceholderText("Type employee name or number...")
            line_edit.textEdited.connect(self._on_employee_text_edited)
            line_edit.editingFinished.connect(
                self._on_employee_editing_finished
            )

    def _on_employee_selected(self, _index=None) -> None:
        """Run employee-dependent loads only after explicit user selection."""
        if self._employee_search_typing:
            return
        self._employee_search_typing = False
        self._apply_employee_master_rates(self._selected_employee_id())
        self._load_pay_printout()
        self._load_ytd_totals()
        self._refresh_pay_ledger()
        self._refresh_work_item_summary()
        self._auto_load_entry_for_selection()
        self._refresh_t4_override_status()

    def _on_employee_editing_finished(self) -> None:
        """End typing mode so selecting an item can trigger normal loading."""
        self._employee_search_typing = False

    def _on_employee_text_edited(self, text) -> None:
        """Filter employee combo box based on typed text."""
        self._employee_search_typing = True
        search_text = text.lower().strip()

        if not search_text:
            # Show all employees if search is empty
            for i in range(self.employee_combo.count()):
                self.employee_combo.view().setRowHidden(i, False)
            return

        # Filter based on contains match (case-insensitive)
        for i in range(self.employee_combo.count()):
            item_text = self.employee_combo.itemText(i).lower()
            # Show if text appears anywhere in the item (number or name)
            matches = search_text in item_text
            self.employee_combo.view().setRowHidden(i, not matches)

        # Keep focus in the line edit while typing; do not force popup open.

    def _connect_auto_persist_signals(self) -> None:
        """Wire editable payroll fields to recalculate + debounced"
        "auto-save."""

        spin_fields = [
            self.charter_hours,
            self.approved_hours,
            self.approved_hours_2,
            self.overtime_hours,
            self.manual_hours_adjustment,
            self.hourly_rate,
            self.hourly_rate_2,
            self.base_pay,
            self.gratuity_amount,
            self.reimbursements,
            self.other_income,
            self.federal_tax,
            self.provincial_tax,
            self.cpp_employee,
            self.ei_employee,
            self.data_completeness,
            self.confidence_level,
        ]
        if hasattr(self, "float_draw"):
            spin_fields.append(self.float_draw)

        for spin in spin_fields:
            spin.valueChanged.connect(self._on_form_field_changed)

        self.rate_source_combo.currentTextChanged.connect(
            self._on_form_field_changed
        )
        self.data_source_combo.currentTextChanged.connect(
            self._on_form_field_changed
        )
        self.notes_edit.textChanged.connect(self._on_form_field_changed)

    def _on_form_field_changed(self, _value=None) -> None:
        """Recalculate immediately and autosave shortly after user edits."""
        if self._loading_entry or self._saving_entry:
            return

        if not self._selected_employee_id() or not self._selected_pay_period():
            return

        # User requested fully automatic recalculation on each value edit.
        self.recalculate_totals(force_base_pay=True)
        self._auto_save_dirty = True
        self._auto_save_timer.start()

    def _auto_save_pending_changes(self) -> None:
        """Persist form edits after typing settles so save/recalc is"
        "one-step."""

        if not self._auto_save_dirty:
            return
        if self._loading_entry or self._saving_entry:
            return
        if not self._selected_employee_id() or not self._selected_pay_period():
            return

        saved = self.save_entry(silent=True, recalc_before_save=False)
        if saved:
            self._set_status(
                f"Auto-saved at {datetime.now().strftime('%H:%M:%S')}"
            )
            self._auto_save_dirty = False

    def _build_pay_printout_group(self) -> QGroupBox:
        group = QGroupBox("Pay Printout (Charters/Work for Period)")
        group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout = QVBoxLayout(group)

        info = QLabel(
            "Click a charter row to edit (double-click or click 📝 Edit"
            "Selected), modify Hours 1 / Hours 2 / gratuity above, then click"
            "💾 Update Charter."


        )
        info.setStyleSheet("color: #6b7280; font-size: 9pt;")
        layout.addWidget(info)

        self.pay_printout_table = QTableWidget()
        self.pay_printout_table.setColumnCount(6)
        self.pay_printout_table.setHorizontalHeaderLabels(
            [
                "Charter Date",
                "Reserve #",
                "Approved Hours",
                "Other Hours",
                "Approved Gratuity",
                "Run Status",
            ]
        )
        self.pay_printout_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.pay_printout_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self.pay_printout_table.setMinimumHeight(160)
        layout.addWidget(self.pay_printout_table)

        # Charter editing buttons
        button_row = QHBoxLayout()

        edit_charter_btn = QPushButton("📝 Edit Selected")
        edit_charter_btn.setToolTip(
            "Load the selected charter row into the form for editing"
        )
        edit_charter_btn.clicked.connect(self._load_charter_to_form)
        button_row.addWidget(edit_charter_btn)

        update_charter_btn = QPushButton("💾 Update Charter")
        update_charter_btn.setStyleSheet(
            "background-color: #f59e0b; color: white;"
        )
        update_charter_btn.setToolTip(
            "Save form changes back to the selected charter row"
        )
        update_charter_btn.clicked.connect(self._update_charter_from_form)
        button_row.addWidget(update_charter_btn)

        remove_charter_btn = QPushButton("🗑️ Delete Row")
        remove_charter_btn.setToolTip("Remove the selected charter row")
        remove_charter_btn.clicked.connect(self._remove_charter_row)
        button_row.addWidget(remove_charter_btn)

        button_row.addStretch()
        layout.addLayout(button_row)

        # Connect table double-click to load charter
        self.pay_printout_table.doubleClicked.connect(
            self._load_charter_to_form
        )
        self.pay_printout_table.itemChanged.connect(
            self._on_pay_printout_item_changed
        )
        # Track which row is being edited
        self.current_charter_row = -1

        totals_row = QHBoxLayout()
        self.pay_printout_total_hours = QLabel(PAY_PRINTOUT_TOTAL_HOURS_DEFAULT)
        self.pay_printout_total_gratuity = QLabel(PAY_PRINTOUT_TOTAL_GRATUITY_DEFAULT)
        self.pay_printout_wcb = QLabel("WCB (month): $0.00")
        self.pay_printout_total_hours.setStyleSheet("font-weight: bold;")
        self.pay_printout_total_gratuity.setStyleSheet("font-weight: bold;")
        self.pay_printout_wcb.setStyleSheet("font-weight: bold;")
        totals_row.addWidget(self.pay_printout_total_hours)
        totals_row.addSpacing(20)
        totals_row.addWidget(self.pay_printout_total_gratuity)
        totals_row.addSpacing(20)
        totals_row.addWidget(self.pay_printout_wcb)
        totals_row.addStretch()

        self.autofill_from_charters_btn = QPushButton("🔄 Pull & Calculate")
        self.autofill_from_charters_btn.setToolTip(
            "Reload charters for this employee/period, sync Hours 1 / Hours 2 / Gratuity\n"
            "into the payroll form, then auto-calculate CPP, EI, and income tax.\n"
            "Review all values and edit before saving."
        )
        self.autofill_from_charters_btn.clicked.connect(
            self._autofill_from_charters
        )
        totals_row.addWidget(self.autofill_from_charters_btn)

        layout.addLayout(totals_row)
        return group

    def _build_pd7a_group(self) -> QGroupBox:
        group = QGroupBox("Monthly Remittance (PD7A) - Summary")
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(15)
        grid.setVerticalSpacing(8)

        self.pd7a_month_label = QLabel("(Select a pay period)")
        self.pd7a_month_label.setStyleSheet(
            "font-weight: bold; color: #1e40af;"
        )

        self.pd7a_gross = QLabel("$0.00")
        self.pd7a_cpp_employee = QLabel("$0.00")
        self.pd7a_cpp_employer = QLabel("$0.00")
        self.pd7a_ei_employee = QLabel("$0.00")
        self.pd7a_ei_employer = QLabel("$0.00")
        self.pd7a_federal = QLabel("$0.00")
        self.pd7a_provincial = QLabel("$0.00")
        self.pd7a_total_deductions = QLabel("$0.00")
        self.pd7a_net = QLabel("$0.00")
        self.pd7a_wcb = QLabel("$0.00")

        # Style the labels
        for lbl in [
            self.pd7a_gross,
            self.pd7a_cpp_employee,
            self.pd7a_cpp_employer,
            self.pd7a_ei_employee,
            self.pd7a_ei_employer,
            self.pd7a_federal,
            self.pd7a_provincial,
            self.pd7a_total_deductions,
            self.pd7a_net,
            self.pd7a_wcb,
        ]:
            lbl.setStyleSheet(
                "font-family: 'Courier New'; font-size: 11pt; padding: 3px;"
            )
            lbl.setMinimumWidth(100)

        self.pd7a_refresh_btn = QPushButton("🔄 Recalculate Monthly Totals")
        self.pd7a_refresh_btn.clicked.connect(
            self._load_monthly_remittance_summary
        )
        self.pd7a_print_btn = QPushButton("🖨️ Print PD7A Summary")
        self.pd7a_print_btn.clicked.connect(self.print_pd7a_summary)

        # Row 0 - Month header
        grid.addWidget(QLabel("<b>Month:</b>"), 0, 0)
        grid.addWidget(self.pd7a_month_label, 0, 1, 1, 3)

        # Row 1
        grid.addWidget(QLabel("Total Gross (T4-14):"), 1, 0)
        grid.addWidget(self.pd7a_gross, 1, 1)
        grid.addWidget(QLabel("Federal Tax (T4-22):"), 1, 2)
        grid.addWidget(self.pd7a_federal, 1, 3)
        grid.addWidget(QLabel("Provincial Tax (T4-22):"), 1, 4)
        grid.addWidget(self.pd7a_provincial, 1, 5)

        # Row 2 - Employee portions
        grid.addWidget(QLabel("CPP Employee (T4-16):"), 2, 0)
        grid.addWidget(self.pd7a_cpp_employee, 2, 1)
        grid.addWidget(QLabel("EI Employee (T4-18):"), 2, 2)
        grid.addWidget(self.pd7a_ei_employee, 2, 3)
        grid.addWidget(QLabel("WCB (Month):"), 2, 4)
        grid.addWidget(self.pd7a_wcb, 2, 5)

        # Row 3 - Employer portions (CRA requirement)
        cpp_emp_label = QLabel("<i>CPP Employer (1:1):</i>")
        cpp_emp_label.setStyleSheet("color: #059669; font-size: 10pt;")
        grid.addWidget(cpp_emp_label, 3, 0)
        grid.addWidget(self.pd7a_cpp_employer, 3, 1)

        ei_emp_label = QLabel("<i>EI Employer (140%):</i>")
        ei_emp_label.setStyleSheet("color: #059669; font-size: 10pt;")
        grid.addWidget(ei_emp_label, 3, 2)
        grid.addWidget(self.pd7a_ei_employer, 3, 3)

        # Row 4 - Totals
        total_ded_label = QLabel("<b>Total Deductions:</b>")
        total_ded_label.setStyleSheet("color: #dc2626;")
        grid.addWidget(total_ded_label, 4, 0)
        grid.addWidget(self.pd7a_total_deductions, 4, 1)

        net_label = QLabel("<b>Net Pay:</b>")
        net_label.setStyleSheet("color: #059669; font-size: 11pt;")
        grid.addWidget(net_label, 4, 2)
        grid.addWidget(self.pd7a_net, 4, 3)

        # Row 5 - Button
        grid.addWidget(self.pd7a_refresh_btn, 5, 0, 1, 2)
        grid.addWidget(self.pd7a_print_btn, 5, 2, 1, 2)

        grid.setColumnStretch(6, 1)

        return group

    def _build_hiring_form_group(self) -> QGroupBox:
        group = QGroupBox("Hiring Form (Quick)")
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(15)
        grid.setVerticalSpacing(8)

        self.hire_date_input = QDateEdit()
        self.hire_date_input.setCalendarPopup(True)
        self.hire_date_input.setDate(QDate.currentDate())

        self.position_input = QLineEdit()
        self.position_input.setPlaceholderText(
            "Office, Dispatch, Driver, etc."
        )

        self.hourly_rate_input = self._money_spin()
        self.annual_salary_input = self._money_spin()

        self.employment_status_input = QComboBox()
        self.employment_status_input.addItems(["active", "inactive", "leave"])

        self.save_hiring_btn = QPushButton("Save Hiring Info")
        self.save_hiring_btn.clicked.connect(self.save_hiring_info)

        # Set fixed widths
        for widget in [self.hourly_rate_input, self.annual_salary_input]:
            widget.setMinimumWidth(120)
            widget.setMaximumWidth(150)

        self.position_input.setMinimumWidth(180)
        self.position_input.setMaximumWidth(250)
        self.employment_status_input.setMinimumWidth(180)
        self.employment_status_input.setMaximumWidth(220)

        # Row 0
        grid.addWidget(QLabel("Hire Date:"), 0, 0)
        grid.addWidget(self.hire_date_input, 0, 1)
        grid.addWidget(QLabel("Position:"), 0, 2)
        grid.addWidget(self.position_input, 0, 3)
        grid.addWidget(QLabel("Status:"), 0, 4)
        grid.addWidget(self.employment_status_input, 0, 5)

        # Row 1
        grid.addWidget(QLabel("Hourly Rate:"), 1, 0)
        grid.addWidget(self.hourly_rate_input, 1, 1)
        grid.addWidget(QLabel("Annual Salary:"), 1, 2)
        grid.addWidget(self.annual_salary_input, 1, 3)

        # Row 2 - Save button
        grid.addWidget(self.save_hiring_btn, 2, 0, 1, 2)

        grid.setColumnStretch(6, 1)

        return group

    def _build_pay_event_group(self) -> QGroupBox:
        group = QGroupBox("Employment Pay Event")
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(15)
        grid.setVerticalSpacing(8)

        self.pay_event_type = QComboBox()
        self.pay_event_type.addItems(
            [
                "Hire",
                "Termination",
                "Salary Change",
                "Bonus",
                "Adjustment",
                "Other",
            ]
        )

        self.pay_event_date = QDateEdit()
        self.pay_event_date.setCalendarPopup(True)
        self.pay_event_date.setDate(QDate.currentDate())

        self.pay_event_amount = self._money_spin()
        self.pay_event_reference = QLineEdit()
        self.pay_event_notes = QTextEdit()
        self.pay_event_notes.setPlaceholderText(
            "Notes (e.g., onboarding form filed, salary confirmation, PD7A"
            "adjustment)"

        )
        self.pay_event_notes.setMaximumHeight(80)

        self.save_pay_event_btn = QPushButton("Save Pay Event")
        self.save_pay_event_btn.clicked.connect(self.save_pay_event)

        # Set fixed widths
        self.pay_event_amount.setMinimumWidth(120)
        self.pay_event_amount.setMaximumWidth(150)
        self.pay_event_type.setMinimumWidth(180)
        self.pay_event_type.setMaximumWidth(220)
        self.pay_event_reference.setMinimumWidth(180)
        self.pay_event_reference.setMaximumWidth(250)

        # Row 0
        grid.addWidget(QLabel("Event Type:"), 0, 0)
        grid.addWidget(self.pay_event_type, 0, 1)
        grid.addWidget(QLabel("Event Date:"), 0, 2)
        grid.addWidget(self.pay_event_date, 0, 3)
        grid.addWidget(QLabel("Amount:"), 0, 4)
        grid.addWidget(self.pay_event_amount, 0, 5)

        # Row 1
        grid.addWidget(QLabel("Reference:"), 1, 0)
        grid.addWidget(self.pay_event_reference, 1, 1, 1, 2)

        # Row 2 - Notes (span full width)
        grid.addWidget(QLabel("Notes:"), 2, 0)
        grid.addWidget(self.pay_event_notes, 2, 1, 1, 5)

        # Row 3 - Save button
        grid.addWidget(self.save_pay_event_btn, 3, 0, 1, 2)

        grid.setColumnStretch(6, 1)

        return group

    def _build_hours_group(self) -> QGroupBox:
        group = QGroupBox("Hours & Rates")
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(15)
        grid.setVerticalSpacing(8)

        self._init_hours_fields()
        self._configure_hours_field_widths()
        self._populate_hours_layout(grid)
        self._connect_hours_signals()
        grid.setColumnStretch(6, 1)
        return group

    def _init_hours_fields(self) -> None:
        self.charter_hours = self._spin(1_000, 2)
        self.charter_hours_1 = self._spin(1_000, 2, read_only=True)
        self.charter_hours_2 = self._spin(1_000, 2, read_only=True)
        self.approved_hours = self._spin(1_000, 2)  # Approved Hours 1
        self.approved_hours_2 = self._spin(1_000, 2)  # Approved Hours 2
        self.overtime_hours = self._spin(1_000, 2)
        self.manual_hours_adjustment = self._spin(1_000, 2)
        self.total_hours_worked = self._spin(1_000, 2, read_only=True)
        # Pay 1 rate (employee master)
        self.hourly_rate = self._spin(1_000, 2, read_only=True)
        # Pay 2 rate (employee master)
        self.hourly_rate_2 = self._spin(1_000, 2, read_only=True)

        # Calculated pay fields
        self.pay1_calculated = self._money_spin(read_only=True)
        self.pay2_calculated = self._money_spin(read_only=True)
        self.combined_total = self._money_spin(read_only=True)

        self.hourly_rate.setValue(20.00)
        self.hourly_rate_2.setValue(10.00)

        self.rate_source_combo = QComboBox()
        self.rate_source_combo.addItems(
            ["employee_master", "charter_default", "manual_override"]
        )
        self.rate_source_combo.setEnabled(False)
        self.rate_source_combo.setToolTip(
            "Rates are enforced from employee master.\n"
            "Pay 1 = employees.hourly_rate\n"
            "Pay 2 = employees.hourly_pay_rate"
        )

    def _configure_hours_field_widths(self) -> None:
        # Set fixed widths for input fields
        for widget in [
            self.charter_hours,
            self.charter_hours_1,
            self.charter_hours_2,
            self.approved_hours,
            self.approved_hours_2,
            self.overtime_hours,
            self.manual_hours_adjustment,
            self.total_hours_worked,
            self.hourly_rate,
            self.hourly_rate_2,
        ]:
            widget.setMinimumWidth(120)
            widget.setMaximumWidth(150)

        self.rate_source_combo.setMinimumWidth(180)
        self.rate_source_combo.setMaximumWidth(220)

    def _populate_hours_layout(self, grid: QGridLayout) -> None:
        # Row 0
        grid.addWidget(QLabel("Charter Hours 1:"), 0, 0)
        grid.addWidget(self.charter_hours_1, 0, 1)
        grid.addWidget(QLabel("Charter Hours 2:"), 0, 2)
        grid.addWidget(self.charter_hours_2, 0, 3)
        grid.addWidget(QLabel("Charter Hours Total:"), 0, 4)
        grid.addWidget(self.charter_hours, 0, 5)

        # Row 1
        grid.addWidget(QLabel("Approved Hours 1:"), 1, 0)
        grid.addWidget(self.approved_hours, 1, 1)
        grid.addWidget(QLabel("Approved Hours 2:"), 1, 2)
        grid.addWidget(self.approved_hours_2, 1, 3)
        grid.addWidget(QLabel("<b>Total Hours (auto):</b>"), 1, 4)
        grid.addWidget(self.total_hours_worked, 1, 5)

        # Row 2
        grid.addWidget(QLabel("Overtime Hours:"), 2, 0)
        grid.addWidget(self.overtime_hours, 2, 1)
        grid.addWidget(QLabel("Manual Hours Adj:"), 2, 2)
        grid.addWidget(self.manual_hours_adjustment, 2, 3)

        # Row 3
        pay1_label = QLabel("Pay 1 Rate:")
        pay1_label.setToolTip(
            "Hourly rate for Approved Hours 1. Does NOT auto-change on"
            "Recalculate."

        )
        grid.addWidget(pay1_label, 3, 0)
        self.hourly_rate.setToolTip(
            "Pay 1 hourly rate (locked). Only Base Pay recalculates."
        )
        grid.addWidget(self.hourly_rate, 3, 1)

        pay2_label = QLabel("Pay 2 Rate:")
        pay2_label.setToolTip(
            "Hourly rate for Approved Hours 2. Does NOT auto-change on"
            "Recalculate."

        )
        grid.addWidget(pay2_label, 3, 2)
        self.hourly_rate_2.setToolTip(
            "Pay 2 hourly rate (locked). Only Base Pay recalculates."
        )
        grid.addWidget(self.hourly_rate_2, 3, 3)

        # Row 4 - Calculated Pay Fields
        pay1_calc_label = QLabel("<b>Pay 1 Calculated:</b>")
        pay1_calc_label.setStyleSheet("color: #1e40af;")
        grid.addWidget(pay1_calc_label, 4, 0)
        grid.addWidget(self.pay1_calculated, 4, 1)

        pay2_calc_label = QLabel("<b>Pay 2 Calculated:</b>")
        pay2_calc_label.setStyleSheet("color: #1e40af;")
        grid.addWidget(pay2_calc_label, 4, 2)
        grid.addWidget(self.pay2_calculated, 4, 3)

        combined_label = QLabel("<b>Combined Total:</b>")
        combined_label.setStyleSheet("color: #059669; font-weight: bold;")
        grid.addWidget(combined_label, 4, 4)
        grid.addWidget(self.combined_total, 4, 5)

        # Row 5
        grid.addWidget(QLabel("Rate Source:"), 5, 0)
        grid.addWidget(self.rate_source_combo, 5, 1, 1, 2)

    def _connect_hours_signals(self) -> None:
        # Connect signals to update calculated fields
        self.approved_hours.valueChanged.connect(self._update_calculated_pays)
        self.approved_hours_2.valueChanged.connect(
            self._update_calculated_pays
        )
        self.hourly_rate.valueChanged.connect(self._update_calculated_pays)
        self.hourly_rate_2.valueChanged.connect(self._update_calculated_pays)
        self.overtime_hours.valueChanged.connect(self.recalculate_totals)
        self.manual_hours_adjustment.valueChanged.connect(
            self.recalculate_totals
        )

    def _build_pay_group(self) -> QGroupBox:
        group = QGroupBox("Pay Components")
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(15)
        grid.setVerticalSpacing(8)

        self.base_pay = self._money_spin()
        self.gratuity_percent = self._spin(100, 2)
        self.gratuity_amount = self._money_spin()
        self.reimbursements = self._money_spin()
        self.other_income = self._money_spin()
        self.gross_pay = self._money_spin(read_only=True)
        self.ei_insurable = self._money_spin(read_only=True)
        self.cpp_pensionable = self._money_spin(read_only=True)
        self.ytd_gross_pay = self._money_spin(read_only=True)
        self.ytd_ei_insurable = self._money_spin(read_only=True)
        self.ytd_cpp_pensionable = self._money_spin(read_only=True)
        self.work_items_income_label = QLabel("Non-Charter Work: $0.00")
        self.work_items_reimburse_label = QLabel("Reimbursements Tracked: $0.00")
        self.work_items_advances_label = QLabel("Advances/Floats/Loans Outstanding: $0.00")
        self.manage_work_items_btn = QPushButton("Work / Advances")
        self.manage_work_items_btn.clicked.connect(self._open_work_items_dialog)

        # Connect auto-calculation for T4 boxes 24 and 26
        # These update when gross_pay changes (via recalculate_totals)

        # Set fixed widths for currency fields
        for widget in [
            self.base_pay,
            self.gratuity_amount,
            self.reimbursements,
            self.other_income,
            self.gross_pay,
            self.ei_insurable,
            self.cpp_pensionable,
            self.ytd_gross_pay,
            self.ytd_ei_insurable,
            self.ytd_cpp_pensionable,
        ]:
            widget.setMinimumWidth(120)
            widget.setMaximumWidth(150)

        self.gratuity_percent.setMinimumWidth(100)
        self.gratuity_percent.setMaximumWidth(120)
        self.gratuity_percent.setEnabled(False)
        self.gratuity_percent.setToolTip(
            "Legacy field retained for schema compatibility. Payroll gratuity"
            "is value-based."

        )

        # Row 0
        grid.addWidget(QLabel("Base Pay:"), 0, 0)
        grid.addWidget(self.base_pay, 0, 1)
        grid.addWidget(QLabel("Gratuity % (legacy):"), 0, 2)
        grid.addWidget(self.gratuity_percent, 0, 3)
        grid.addWidget(QLabel("Gratuity$:"), 0, 4)
        grid.addWidget(self.gratuity_amount, 0, 5)

        # Row 1
        grid.addWidget(QLabel("Reimbursements:"), 1, 0)
        grid.addWidget(self.reimbursements, 1, 1)
        grid.addWidget(QLabel("Other Income:"), 1, 2)
        grid.addWidget(self.other_income, 1, 3)

        # Row 2 - Gross Pay & T4 boxes highlighted
        gross_label = QLabel("<b>Gross Pay (T4-14):</b>")
        gross_label.setStyleSheet("color: #1e40af;")
        grid.addWidget(gross_label, 2, 0)
        grid.addWidget(self.gross_pay, 2, 1)

        ei_label = QLabel("<b>EI Insurable (T4-24):</b>")
        ei_label.setStyleSheet("color: #1e40af;")
        grid.addWidget(ei_label, 2, 2)
        grid.addWidget(self.ei_insurable, 2, 3)

        cpp_label = QLabel("<b>CPP Pensionable (T4-26):</b>")
        cpp_label.setStyleSheet("color: #1e40af;")
        grid.addWidget(cpp_label, 2, 4)
        grid.addWidget(self.cpp_pensionable, 2, 5)

        # Row 3 - YTD summary for T4 boxes
        ytd_gross_label = QLabel("<b>YTD Gross (T4-14):</b>")
        ytd_gross_label.setStyleSheet("color: #065f46;")
        grid.addWidget(ytd_gross_label, 3, 0)
        grid.addWidget(self.ytd_gross_pay, 3, 1)

        ytd_ei_label = QLabel("<b>YTD EI Insurable (T4-24):</b>")
        ytd_ei_label.setStyleSheet("color: #065f46;")
        grid.addWidget(ytd_ei_label, 3, 2)
        grid.addWidget(self.ytd_ei_insurable, 3, 3)

        ytd_cpp_label = QLabel("<b>YTD CPP Pensionable (T4-26):</b>")
        ytd_cpp_label.setStyleSheet("color: #065f46;")
        grid.addWidget(ytd_cpp_label, 3, 4)
        grid.addWidget(self.ytd_cpp_pensionable, 3, 5)

        self.work_items_income_label.setStyleSheet("color: #0f766e; font-weight: bold;")
        self.work_items_reimburse_label.setStyleSheet("color: #0f766e; font-weight: bold;")
        self.work_items_advances_label.setStyleSheet("color: #b45309; font-weight: bold;")
        grid.addWidget(self.work_items_income_label, 4, 0, 1, 2)
        grid.addWidget(self.work_items_reimburse_label, 4, 2, 1, 2)
        grid.addWidget(self.work_items_advances_label, 4, 4)
        grid.addWidget(self.manage_work_items_btn, 4, 5)

        grid.setColumnStretch(6, 1)  # Stretch last column to fill space

        return group

    def _build_deductions_group(self) -> QGroupBox:
        group = QGroupBox("Deductions & Net Pay")
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(15)
        grid.setVerticalSpacing(8)

        self._init_deduction_fields()
        self._connect_deduction_signals()
        self._configure_deduction_field_widths()
        self._populate_deductions_layout(grid)
        grid.setColumnStretch(6, 1)  # Stretch last column to fill space
        return group

    def _init_deduction_fields(self) -> None:
        self.federal_tax = self._money_spin()
        self.provincial_tax = self._money_spin()
        self.total_income_tax = self._money_spin(read_only=True)
        self.cpp_employee = self._money_spin()
        self.ei_employee = self._money_spin()
        self.cpp_employer = self._money_spin(read_only=True)  # CRA: 1:1 match
        self.ei_employer = self._money_spin(
            read_only=True
        )  # CRA: 1.4x employee
        self.union_dues = self._money_spin()
        self.pay_advance_deduction = self._money_spin()
        self.total_deductions = self._money_spin(read_only=True)
        self.net_pay = self._money_spin(read_only=True)
        self.ytd_income_tax = self._money_spin(read_only=True)
        self.ytd_cpp_employee = self._money_spin(read_only=True)
        self.ytd_ei_employee = self._money_spin(read_only=True)
        self.ytd_total_deductions = self._money_spin(read_only=True)
        self.ytd_net_pay = self._money_spin(read_only=True)

        self._manual_deduction_override_style = (
            "QDoubleSpinBox { border: 1px solid #dc2626; "
            "background-color: #fef2f2; }"
        )
        self._manual_deduction_calc_labels: dict[str, QLabel] = {}
        self._manual_deduction_flags: dict[str, QLabel] = {}
        for key in ("cpp", "ei", "federal", "provincial"):
            calc_label = QLabel("Calc: $0.00")
            calc_label.setStyleSheet("color: #0f766e; font-size: 9pt;")
            calc_label.setToolTip(
                "CRA-based calculated deduction for this field."
            )

            flag_label = QLabel("")
            flag_label.setStyleSheet(
                "color: #dc2626; font-weight: bold; font-size: 9pt;"
            )
            flag_label.setToolTip(
                "Shows MANUAL when entered value differs from CRA-calculated"
                " value."
            )

            self._manual_deduction_calc_labels[key] = calc_label
            self._manual_deduction_flags[key] = flag_label

        self._manual_deduction_widgets: dict[str, QDoubleSpinBox] = {
            "cpp": self.cpp_employee,
            "ei": self.ei_employee,
            "federal": self.federal_tax,
            "provincial": self.provincial_tax,
        }

    def _connect_deduction_signals(self) -> None:
        # Connect auto-calculation for total income tax (T4-22)
        self.federal_tax.valueChanged.connect(self._update_total_income_tax)
        self.provincial_tax.valueChanged.connect(self._update_total_income_tax)

        # Connect auto-calculation for employer portions (CRA compliance)
        self.cpp_employee.valueChanged.connect(self._update_employer_cpp)
        self.ei_employee.valueChanged.connect(self._update_employer_ei)

    def _configure_deduction_field_widths(self) -> None:
        # Set fixed widths for currency fields
        for widget in [
            self.federal_tax,
            self.provincial_tax,
            self.total_income_tax,
            self.cpp_employee,
            self.ei_employee,
            self.cpp_employer,
            self.ei_employer,
            self.union_dues,
            self.pay_advance_deduction,
            self.total_deductions,
            self.net_pay,
            self.ytd_income_tax,
            self.ytd_cpp_employee,
            self.ytd_ei_employee,
            self.ytd_total_deductions,
            self.ytd_net_pay,
        ]:
            widget.setMinimumWidth(120)
            widget.setMaximumWidth(150)

        for calc_label in self._manual_deduction_calc_labels.values():
            calc_label.setMinimumWidth(92)
            calc_label.setMaximumWidth(92)
        for flag_label in self._manual_deduction_flags.values():
            flag_label.setMinimumWidth(58)
            flag_label.setMaximumWidth(58)

    def _build_deduction_input_widget(
        self,
        amount_widget: QDoubleSpinBox,
        calc_label: QLabel,
        flag_label: QLabel,
    ) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(amount_widget)
        row.addWidget(calc_label)
        row.addWidget(flag_label)
        row.addStretch(1)
        return container

    def _populate_deductions_layout(self, grid: QGridLayout) -> None:
        # Row 0 - Employee deductions
        grid.addWidget(QLabel("CPP Employee (T4-16):"), 0, 0)
        grid.addWidget(
            self._build_deduction_input_widget(
                self.cpp_employee,
                self._manual_deduction_calc_labels["cpp"],
                self._manual_deduction_flags["cpp"],
            ),
            0,
            1,
        )
        grid.addWidget(QLabel("EI Employee (T4-18):"), 0, 2)
        grid.addWidget(
            self._build_deduction_input_widget(
                self.ei_employee,
                self._manual_deduction_calc_labels["ei"],
                self._manual_deduction_flags["ei"],
            ),
            0,
            3,
        )
        self.michael_ei_exempt_btn = QPushButton("Apply EI Exempt")
        self.michael_ei_exempt_btn.setToolTip(
            "Set EI employee/employer to $0.00 for configured EI-exempt"
            "employees (Michael Dr09, Paul Dr100)."

        )
        self.michael_ei_exempt_btn.clicked.connect(
            self._apply_selected_employee_ei_exempt
        )
        grid.addWidget(self.michael_ei_exempt_btn, 0, 4, 1, 2)

        # Row 0.5 - Employer portions (CRA compliance)
        cpp_employer_label = QLabel("<i>CPP Employer (1:1):</i>")
        cpp_employer_label.setStyleSheet("color: #059669; font-size: 10pt;")
        grid.addWidget(cpp_employer_label, 1, 0)
        grid.addWidget(self.cpp_employer, 1, 1)

        ei_employer_label = QLabel("<i>EI Employer (140%):</i>")
        ei_employer_label.setStyleSheet("color: #059669; font-size: 10pt;")
        grid.addWidget(ei_employer_label, 1, 2)
        grid.addWidget(self.ei_employer, 1, 3)

        self.auto_suggest_cpp_ei_btn = QPushButton("⚡ Auto-suggest CPP / EI")
        self.auto_suggest_cpp_ei_btn.setToolTip(
            "Calculate CPP and EI employee deductions from gross pay "
            "using CRA rates for the selected year, capped by YTD totals."
        )
        self.auto_suggest_cpp_ei_btn.clicked.connect(self._auto_suggest_cpp_ei)
        grid.addWidget(self.auto_suggest_cpp_ei_btn, 1, 4, 1, 2)

        # Row 2 - Tax fields
        grid.addWidget(QLabel("Federal Tax:"), 2, 0)
        grid.addWidget(
            self._build_deduction_input_widget(
                self.federal_tax,
                self._manual_deduction_calc_labels["federal"],
                self._manual_deduction_flags["federal"],
            ),
            2,
            1,
        )
        grid.addWidget(QLabel("Provincial Tax:"), 2, 2)
        grid.addWidget(
            self._build_deduction_input_widget(
                self.provincial_tax,
                self._manual_deduction_calc_labels["provincial"],
                self._manual_deduction_flags["provincial"],
            ),
            2,
            3,
        )

        total_tax_label = QLabel("<b>Total Income Tax (T4-22):</b>")
        total_tax_label.setStyleSheet("color: #1e40af;")
        grid.addWidget(total_tax_label, 2, 4)
        grid.addWidget(self.total_income_tax, 2, 5)

        # Row 3 - Totals highlighted
        total_label = QLabel("<b>Total Deductions:</b>")
        total_label.setStyleSheet("color: #dc2626;")
        grid.addWidget(total_label, 3, 0)
        grid.addWidget(self.total_deductions, 3, 1)

        net_label = QLabel("<b>Net Pay:</b>")
        net_label.setStyleSheet("color: #059669; font-size: 11pt;")
        grid.addWidget(net_label, 3, 2)
        grid.addWidget(self.net_pay, 3, 3)

        pay_adv_label = QLabel("<b>Pay Advances:</b>")
        pay_adv_label.setStyleSheet("color: #7c2d12; font-size: 11pt;")
        grid.addWidget(pay_adv_label, 3, 4)
        grid.addWidget(self.pay_advance_deduction, 3, 5)

        # Row 4 - YTD deduction summary for T4 boxes and payroll totals
        ytd_tax_label = QLabel("<b>YTD Income Tax (T4-22):</b>")
        ytd_tax_label.setStyleSheet("color: #065f46;")
        grid.addWidget(ytd_tax_label, 4, 0)
        grid.addWidget(self.ytd_income_tax, 4, 1)

        ytd_cpp_emp_label = QLabel("<b>YTD CPP Emp (T4-16):</b>")
        ytd_cpp_emp_label.setStyleSheet("color: #065f46;")
        grid.addWidget(ytd_cpp_emp_label, 4, 2)
        grid.addWidget(self.ytd_cpp_employee, 4, 3)

        ytd_ei_emp_label = QLabel("<b>YTD EI Emp (T4-18):</b>")
        ytd_ei_emp_label.setStyleSheet("color: #065f46;")
        grid.addWidget(ytd_ei_emp_label, 4, 4)
        grid.addWidget(self.ytd_ei_employee, 4, 5)

        # Row 5 - YTD totals
        ytd_deductions_label = QLabel("<b>YTD Total Deductions:</b>")
        ytd_deductions_label.setStyleSheet("color: #065f46;")
        grid.addWidget(ytd_deductions_label, 5, 0)
        grid.addWidget(self.ytd_total_deductions, 5, 1)

        ytd_net_label = QLabel("<b>YTD Net Pay:</b>")
        ytd_net_label.setStyleSheet("color: #065f46;")
        grid.addWidget(ytd_net_label, 5, 2)
        grid.addWidget(self.ytd_net_pay, 5, 3)

    def _build_deduction_comparison_group(self) -> QGroupBox:
        group = QGroupBox("Calculated CPP / EI / Tax Comparison")
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(15)
        grid.setVerticalSpacing(8)

        self.calc_taxable_income = self._money_spin(read_only=True)
        self.calc_cpp_percent = self._spin(100, 3, read_only=True)
        self.calc_ei_percent = self._spin(100, 3, read_only=True)
        self.calc_tax_percent = self._spin(100, 3, read_only=True)
        self.calc_cpp_amount = self._money_spin(read_only=True)
        self.calc_ei_amount = self._money_spin(read_only=True)
        self.calc_tax_amount = self._money_spin(read_only=True)
        self.extra_annual_contribution = self._money_spin()
        self.extra_period_contribution = self._money_spin(read_only=True)

        for widget in [
            self.calc_taxable_income,
            self.calc_cpp_amount,
            self.calc_ei_amount,
            self.calc_tax_amount,
            self.extra_annual_contribution,
            self.extra_period_contribution,
        ]:
            widget.setMinimumWidth(120)
            widget.setMaximumWidth(150)

        for widget in [
            self.calc_cpp_percent,
            self.calc_ei_percent,
            self.calc_tax_percent,
        ]:
            widget.setMinimumWidth(100)
            widget.setMaximumWidth(130)
            widget.setSuffix(" %")

        self.extra_annual_contribution.setToolTip(
            "Employee requested additional annual withholding. "
            "Distributed per pay period and added to calculated tax."
        )

        self.copy_calculated_btn = QPushButton("Update Record From Calculated")
        self.copy_calculated_btn.setToolTip(
            "Copy calculated CPP/EI/Tax values into editable pay fields. "
            "Use this when you want to apply suggestions."
        )
        self.copy_calculated_btn.clicked.connect(
            self._apply_calculated_deductions_to_pay
        )

        grid.addWidget(QLabel("Taxable Income (Gross - Reimb):"), 0, 0)
        grid.addWidget(self.calc_taxable_income, 0, 1)
        grid.addWidget(QLabel("CPP % (calc):"), 0, 2)
        grid.addWidget(self.calc_cpp_percent, 0, 3)
        grid.addWidget(QLabel("EI % (calc):"), 0, 4)
        grid.addWidget(self.calc_ei_percent, 0, 5)

        grid.addWidget(QLabel("CPP Amount (calc):"), 1, 0)
        grid.addWidget(self.calc_cpp_amount, 1, 1)
        grid.addWidget(QLabel("EI Amount (calc):"), 1, 2)
        grid.addWidget(self.calc_ei_amount, 1, 3)
        grid.addWidget(QLabel("Tax % (effective):"), 1, 4)
        grid.addWidget(self.calc_tax_percent, 1, 5)

        grid.addWidget(QLabel("Tax Amount (calc):"), 2, 0)
        grid.addWidget(self.calc_tax_amount, 2, 1)
        grid.addWidget(QLabel("Extra Annual Contribution:"), 2, 2)
        grid.addWidget(self.extra_annual_contribution, 2, 3)
        grid.addWidget(QLabel("Extra This Period:"), 2, 4)
        grid.addWidget(self.extra_period_contribution, 2, 5)

        action_row = QHBoxLayout()
        action_row.addWidget(self.copy_calculated_btn)
        action_row.addStretch()
        grid.addLayout(action_row, 3, 0, 1, 6)

        self.extra_annual_contribution.valueChanged.connect(
            self._on_form_field_changed
        )

        return group

    def _build_metadata_group(self) -> QGroupBox:
        group = QGroupBox("Data Quality & Notes")
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(15)
        grid.setVerticalSpacing(8)

        self.data_completeness = self._spin(100, 2)
        self.data_completeness.setValue(100.0)
        self.data_source_combo = QComboBox()
        self.data_source_combo.addItems(
            ["manual_entry", "charter_hours", "reconstructed", "mixed"]
        )
        self.confidence_level = self._spin(100, 2)
        self.confidence_level.setValue(100.0)
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText(
            "Optional notes or evidence for this pay entry..."
        )
        self.notes_edit.setMaximumHeight(80)

        # Set fixed widths
        for widget in [self.data_completeness, self.confidence_level]:
            widget.setMinimumWidth(100)
            widget.setMaximumWidth(120)

        self.data_source_combo.setMinimumWidth(180)
        self.data_source_combo.setMaximumWidth(220)

        # Row 0
        grid.addWidget(QLabel("Data Completeness %:"), 0, 0)
        grid.addWidget(self.data_completeness, 0, 1)
        grid.addWidget(QLabel("Data Source:"), 0, 2)
        grid.addWidget(self.data_source_combo, 0, 3)
        grid.addWidget(QLabel("Confidence %:"), 0, 4)
        grid.addWidget(self.confidence_level, 0, 5)

        # Row 1 - Notes (span full width)
        grid.addWidget(QLabel("Notes:"), 1, 0)
        grid.addWidget(self.notes_edit, 1, 1, 1, 5)

        grid.setColumnStretch(6, 1)

        return group

    def _money_spin(self, read_only=False) -> SelectAllDoubleSpinBox:
        spin = SelectAllDoubleSpinBox()
        spin.setDecimals(2)
        spin.setMaximum(1_000_000.00)
        spin.setMinimum(0.00)
        spin.setPrefix("$")
        spin.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
            if read_only
            else QAbstractSpinBox.ButtonSymbols.UpDownArrows
        )
        spin.setReadOnly(read_only)
        return spin

    def _spin(
        self, maximum, decimals=0, read_only=False
    ) -> SelectAllDoubleSpinBox:
        spin = SelectAllDoubleSpinBox()
        spin.setDecimals(decimals)
        spin.setMaximum(maximum)
        spin.setMinimum(0)
        spin.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
            if read_only
            else QAbstractSpinBox.ButtonSymbols.UpDownArrows
        )
        spin.setReadOnly(read_only)
        return spin

    def _populate_years(self, default_year) -> None:
        years = list(range(2011, 2031))
        for yr in years:
            self.year_combo.addItem(str(yr))
        default_idx = self.year_combo.findText(str(default_year))
        if default_idx >= 0:
            self.year_combo.setCurrentIndex(default_idx)

    def _on_year_changed(self, text) -> None:
        try:
            year = int(text)
        except ValueError:
            return
        self.load_pay_periods(year)
        # Reload employees for the selected year
        self.load_employees()
        self._load_ytd_totals()
        self._refresh_t4_override_status()

    def _on_filter_changed(self) -> None:
        """Reload employees when filter changes"""
        self.load_employees()

    def load_employees(self) -> None:
        """Load employees into the combo box based on selected year and"
        "filter."""

        try:
            # Get selected year and filter mode
            try:
                selected_year = int(self.year_combo.currentText())
            except (ValueError, AttributeError):
                selected_year = QDate.currentDate().year()

            filter_mode = (
                self.employee_filter_combo.currentText()
                if hasattr(self, "employee_filter_combo")
                else "Currently Active Only"
            )

            # Build query based on filter mode
            if filter_mode == "All Employees":
                # Show all employees regardless of status
                query = """
                    SELECT DISTINCT
                        employee_id,
                        COALESCE(employee_number, '') AS emp_num,
                        COALESCE(full_name, '') AS full_name
                    FROM employees
                    ORDER BY full_name, emp_num
                    LIMIT 500
                """
                params = ()
            elif filter_mode == "Active in Selected Year":
                # Show employees who had pay records OR charters in the
                # selected year, OR are currently active
                query = """
                    SELECT DISTINCT
                        e.employee_id,
                        COALESCE(e.employee_number, '') AS emp_num,
                        COALESCE(e.full_name, '') AS full_name
                    FROM employees e
                    WHERE
                        e.employee_id IN (
                            -- Employees with pay records in selected year
                            SELECT DISTINCT employee_id
                            FROM employee_pay_master
                            WHERE fiscal_year = %s
                            UNION
                            -- Employees with charters in selected year
                            SELECT DISTINCT employee_id
                            FROM charters
                            WHERE EXTRACT(YEAR FROM charter_date) = %s
                              AND employee_id IS NOT NULL
                        )
                        OR (
                            e.employment_status IS NULL
                            OR e.employment_status != 'inactive'
                        )
                    ORDER BY full_name, emp_num
                    LIMIT 500
                """
                params = (selected_year, selected_year)
            else:  # "Currently Active Only"
                # Original behavior - only currently active employees
                query = """
                    SELECT
                        employee_id,
                        COALESCE(employee_number, '') AS emp_num,
                        COALESCE(full_name, '') AS full_name
                    FROM employees
                          WHERE employment_status IS NULL
                              OR employment_status != 'inactive'
                    ORDER BY full_name, emp_num
                    LIMIT 500
                """
                params = ()

            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(query, params)

                # Store current selection to restore if possible
                current_emp_id = self.employee_combo.currentData()

                self.employee_combo.clear()
                self.employee_lookup = {}

                rows = cur.fetchall()
                for emp_id, emp_num, name in rows:
                    label = f"{name} ({emp_num})" if emp_num else name
                    self.employee_combo.addItem(label, emp_id)
                    self.employee_lookup[emp_id] = label

                # Try to restore previous selection
                if current_emp_id:
                    for i in range(self.employee_combo.count()):
                        if self.employee_combo.itemData(i) == current_emp_id:
                            self.employee_combo.setCurrentIndex(i)
                            break

                # Reset search visibility (show all items, clear filter)
                for i in range(self.employee_combo.count()):
                    self.employee_combo.view().setRowHidden(i, False)

                # Update status to show filter mode
                self._set_status(
                    f"Loaded {len(rows)} employees ({filter_mode}, Year:"
                    f"{selected_year})"

                )

        except Exception as exc:
            logger.exception("Failed to load employees")
            self._set_status(f"Failed to load employees: {exc}", error=True)

    def load_pay_periods(self, fiscal_year: int) -> None:
        """Load pay periods for selected year. Generate monthly periods if"
        "none found."""

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT pay_period_id, period_number, period_start_date,
                    period_end_date, pay_date
                    FROM pay_periods
                    WHERE fiscal_year = %s
                    ORDER BY period_number
                    """,
                    (fiscal_year,),
                )
                loaded_periods = list(cur.fetchall())

            self.pay_period_combo.clear()
            self.pay_periods = []

            if not loaded_periods:
                # No periods in DB - generate 12 monthly periods
                logger.info(
                    f"No pay periods in DB for {fiscal_year}, generating"
                    f"monthly periods"

                )
                for month in range(1, 13):
                    period_start = date(fiscal_year, month, 1)
                    # Get last day of month
                    if month == 12:
                        period_end = date(fiscal_year, 12, 31)
                    else:
                        period_end = date(
                            fiscal_year, month + 1, 1
                        ) - timedelta(days=1)
                    pay_date = period_end
                    label = (
                        f"P{month:02d} • {period_start} → "
                        f"{period_end} (Pay {pay_date})"
                    )
                    self.pay_period_combo.addItem(label, 0)
                    self.pay_periods.append(
                        (
                            0,
                            fiscal_year,
                            month,
                            period_start,
                            period_end,
                            pay_date,
                        )
                    )
            else:
                # Use periods from database
                for pp_id, num, start, end, pay in loaded_periods:
                    label = f"P{num:02d} • {start} → {end} (Pay {pay})"
                    self.pay_period_combo.addItem(label, pp_id)
                    self.pay_periods.append(
                        (pp_id, fiscal_year, num, start, end, pay)
                    )

            if self.pay_period_combo.count() > 0:
                self.pay_period_combo.setCurrentIndex(0)
        except Exception as exc:
            logger.exception("Failed to load pay periods")
            self._set_status(f"Failed to load pay periods: {exc}", error=True)

    def _refresh_pay_ledger(self) -> None:
        """Refresh the pay ledger when employee or pay period selection"
        "changes."""

        if not hasattr(self, "pay_ledger"):
            return
        emp_id = self._selected_employee_id()
        pay_period = self._selected_pay_period()
        if not emp_id or not pay_period:
            self.pay_ledger.refresh(None, None, None, 0)
            return

        try:
            linked_count = auto_link_pending_employee_pay_transactions(
                self.db,
                employee_id=int(emp_id),
                pay_period_id=int(pay_period[0]) if pay_period[0] else None,
                fiscal_year=int(pay_period[1]) if pay_period[1] else None,
                max_rows=150,
            )
            if linked_count > 0:
                logger.info(
                    "Employee-pay auto-link matched %s pending transaction(s)",
                    linked_count,
                )
        except Exception as exc:
            logger.warning("Employee-pay auto-link skipped: %s", exc)

        net = self.net_pay.value() if hasattr(self, "net_pay") else 0.0
        self.pay_ledger.refresh(emp_id, pay_period[1], pay_period[0], net)

    def _selected_employee_id(self) -> int | None:
        idx = self.employee_combo.currentIndex()
        if idx < 0:
            # Editable combo can have typed text without currentIndex
            # selection.
            text = (self.employee_combo.currentText() or "").strip()
            if not text:
                return None

            # 1) Exact text match to an existing combo item.
            lowered = text.lower()
            for i in range(self.employee_combo.count()):
                if (
                    self.employee_combo.itemText(i) or ""
                ).strip().lower() == lowered:
                    return self.employee_combo.itemData(i)

            # 2) Parse employee number from trailing "(EMP_NUM)" in label.
            match = re.search(r"\(([^)]+)\)\s*$", text)
            if match:
                employee_number = match.group(1).strip()
                try:
                    with DatabaseContext(self.db, auto_commit=False) as cur:
                        cur.execute(
                            """
                            SELECT employee_id
                            FROM employees
                            WHERE employee_number = %s
                            LIMIT 1
                            """,
                            (employee_number,),
                        )
                        row = cur.fetchone()
                        if row:
                            return row[0]
                except Exception as exc:
                    logger.warning(
                        "Failed employee lookup by number '%s': %s",
                        employee_number,
                        exc,
                    )

            # 3) Fallback by full_name exact match.
            try:
                with DatabaseContext(self.db, auto_commit=False) as cur:
                    cur.execute(
                        """
                        SELECT employee_id
                        FROM employees
                        WHERE LOWER(COALESCE(full_name, '')) = LOWER(%s)
                        LIMIT 1
                        """,
                        (text,),
                    )
                    row = cur.fetchone()
                    if row:
                        return row[0]
            except Exception as exc:
                logger.warning(
                    "Failed employee lookup by full name '%s': %s",
                    text,
                    exc,
                )

            return None

        return self.employee_combo.itemData(idx)

    def focus_employee_id(
        self, employee_id: int, fiscal_year: int | None = None
    ) -> bool:
        """Deep-link helper: jump combo selection to a given employee id."""
        try:
            target_id = int(employee_id)
        except (TypeError, ValueError):
            return False

        try:
            if fiscal_year is not None and hasattr(self, "year_combo"):
                year_text = str(int(fiscal_year))
                idx = self.year_combo.findText(year_text)
                if idx >= 0:
                    self.year_combo.setCurrentIndex(idx)
                else:
                    self.year_combo.setCurrentText(year_text)

            if hasattr(self, "load_employees"):
                self.load_employees()

            if not hasattr(self, "employee_combo"):
                return False

            for i in range(self.employee_combo.count()):
                if self.employee_combo.itemData(i) == target_id:
                    self.employee_combo.setCurrentIndex(i)
                    if hasattr(self, "_auto_load_entry_for_selection"):
                        self._auto_load_entry_for_selection()
                    return True
        except Exception as exc:
            logger.warning(
                "focus_employee_id failed for employee_id=%s fiscal_year=%s: %s",
                employee_id,
                fiscal_year,
                exc,
            )
            return False

        return False

    def _get_employee_master_rates(self, emp_id) -> tuple[float, float]:
        """Return Pay 1/Pay 2 rates from employees with safe defaults."""
        default_pay1 = 20.0
        default_pay2 = 10.0
        if not emp_id:
            return default_pay1, default_pay2

        try:
            ecols = self._get_columns("employees")
            pay1_col = "hourly_rate" if "hourly_rate" in ecols else None
            pay2_col = (
                "hourly_pay_rate" if "hourly_pay_rate" in ecols else None
            )

            if not pay1_col and not pay2_col:
                return default_pay1, default_pay2

            pay1_expr = f"COALESCE({pay1_col}, 0)" if pay1_col else "0"
            pay2_expr = f"COALESCE({pay2_col}, 0)" if pay2_col else "0"

            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(  # nosec
                    f"""
                    SELECT {pay1_expr}, {pay2_expr}
                    FROM employees
                    WHERE employee_id = %s
                    LIMIT 1
                    """,
                    (emp_id,),
                )
                row = cur.fetchone()
                if not row:
                    return default_pay1, default_pay2

            pay1 = float(row[0] or 0.0)
            pay2 = float(row[1] or 0.0)
            if pay1 <= 0:
                pay1 = default_pay1
            if pay2 <= 0:
                pay2 = default_pay2
            return pay1, pay2
        except Exception:
            logger.exception(
                "Failed to load employee master rates for %s", emp_id
            )
            return default_pay1, default_pay2

    def _apply_employee_master_rates(self, emp_id=None) -> None:
        """Force UI pay rates to employee master values."""
        if emp_id is None:
            emp_id = self._selected_employee_id()

        pay1, pay2 = self._get_employee_master_rates(emp_id)
        prev_rate1_block = self.hourly_rate.blockSignals(True)
        prev_rate2_block = self.hourly_rate_2.blockSignals(True)
        prev_source_block = self.rate_source_combo.blockSignals(True)
        try:
            self.hourly_rate.setValue(pay1)
            self.hourly_rate_2.setValue(pay2)
            self._set_combo_value(self.rate_source_combo, "employee_master")
        finally:
            self.hourly_rate.blockSignals(prev_rate1_block)
            self.hourly_rate_2.blockSignals(prev_rate2_block)
            self.rate_source_combo.blockSignals(prev_source_block)

    def _selected_pay_period(self) -> tuple | None:
        idx = self.pay_period_combo.currentIndex()
        if idx < 0:
            return None
        # Keep selection by index (stable even when pay_period_id repeats,
        # e.g. generated periods)
        if idx < len(self.pay_periods):
            return self.pay_periods[idx]
        return None

    def _selection_has_saved_entry(self) -> bool:
        """Return True when selected employee/pay period already has a saved"
        "payroll row."""

        emp_id = self._selected_employee_id()
        pay_period = self._selected_pay_period()
        if not emp_id or not pay_period:
            return False

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM employee_pay_master
                    WHERE employee_id = %s AND pay_period_id = %s
                    LIMIT 1
                    """,
                    (emp_id, pay_period[0]),
                )
                return cur.fetchone() is not None
        except Exception as exc:
            logger.warning(
                "Selection existence check failed for employee=%s pay_period=%s: %s",
                emp_id,
                pay_period[0] if pay_period else None,
                exc,
            )
            return False

    def _auto_load_entry_for_selection(self) -> None:
        """Auto-load saved payroll record when employee/pay-period selection"
        "changes."""

        if not self._selected_employee_id() or not self._selected_pay_period():
            return
        self.load_entry()

    @pyqtSlot()
    def clear_form(self) -> None:
        """Reset fields to zero/defaults."""
        spins = [
            self.charter_hours,
            self.charter_hours_1,
            self.charter_hours_2,
            self.approved_hours,
            self.approved_hours_2,
            self.overtime_hours,
            self.manual_hours_adjustment,
            self.total_hours_worked,
            self.hourly_rate,
            self.hourly_rate_2,
            self.pay1_calculated,
            self.pay2_calculated,
            self.combined_total,
            self.base_pay,
            self.gratuity_percent,
            self.gratuity_amount,
            self.reimbursements,
            self.other_income,
            self.gross_pay,
            self.federal_tax,
            self.provincial_tax,
            self.cpp_employee,
            self.ei_employee,
            self.union_dues,
            self.total_deductions,
            self.net_pay,
            self.ytd_gross_pay,
            self.ytd_ei_insurable,
            self.ytd_cpp_pensionable,
            self.ytd_income_tax,
            self.ytd_cpp_employee,
            self.ytd_ei_employee,
            self.ytd_total_deductions,
            self.ytd_net_pay,
            self.calc_taxable_income,
            self.calc_cpp_percent,
            self.calc_ei_percent,
            self.calc_tax_percent,
            self.calc_cpp_amount,
            self.calc_ei_amount,
            self.calc_tax_amount,
            self.extra_annual_contribution,
            self.extra_period_contribution,
        ]
        if hasattr(self, "float_draw"):
            spins.append(self.float_draw)
        for spin in spins:
            spin.setValue(0)
        self.hourly_rate.setValue(20.00)
        self.hourly_rate_2.setValue(10.00)
        self._apply_employee_master_rates(self._selected_employee_id())
        self.data_completeness.setValue(100.0)
        self.confidence_level.setValue(100.0)
        self.data_source_combo.setCurrentIndex(0)
        self.rate_source_combo.setCurrentIndex(0)
        self.notes_edit.clear()
        self._last_synced_charter_hours = None
        self._last_synced_approved_hours = None
        self._last_synced_gratuity = None
        self._set_status(
            "Form cleared. Load an employee + pay period to edit."
        )
        self._refresh_t4_override_status()

    @pyqtSlot()
    def load_entry(self) -> None:
        selection = self._get_load_selection()
        if not selection:
            return
        emp_id, pay_period = selection

        self._loading_entry = True
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                column_flags = self._pay_master_column_flags(cur)
                row = self._load_pay_entry_row(cur, emp_id, pay_period[0], column_flags)
                if not row:
                    self.clear_form()
                    self._set_status(
                        "No record yet. Enter values and Save to create."
                    )
                    return
                self._apply_loaded_pay_entry(row, emp_id, pay_period)
        except Exception as exc:
            logger.exception("Failed to load payroll entry")
            self._set_status(f"Failed to load: {exc}", error=True)
        finally:
            self._loading_entry = False

    def _get_load_selection(self) -> tuple[int, tuple] | None:
        emp_id = self._selected_employee_id()
        pay_period = self._selected_pay_period()
        if emp_id and pay_period:
            return emp_id, pay_period

        import traceback
        logger.warning(
            "Missing Selection dialog triggered. emp_id=%r pay_period=%r\n%s",
            emp_id, pay_period, "".join(traceback.format_stack()),
        )
        QMessageBox.warning(
            self,
            TITLE_MISSING_SELECTION,
            MSG_SELECT_EMPLOYEE_AND_PERIOD,
        )
        return None

    def _pay_master_column_flags(self, cur) -> dict[str, bool]:
        self._ensure_pay_advance_column()
        flags = {}
        for column_name in (
            "total_income_tax",
            "ei_insurable",
            "cpp_pensionable",
            "float_draw",
            "cpp_employer",
            "ei_employer",
            "pay_advance_deduction",
        ):
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'employee_pay_master'
                      AND column_name = %s
                )
                """,
                (column_name,),
            )
            flags[column_name] = bool(cur.fetchone()[0])
        return flags

    def _load_pay_entry_row(self, cur, emp_id, pay_period_id, flags) -> tuple | None:
        total_income_tax_expr = (
            "total_income_tax"
            if flags["total_income_tax"]
            else "COALESCE(federal_tax, 0) + COALESCE(provincial_tax, 0) AS total_income_tax"
        )
        ei_insurable_expr = (
            "ei_insurable"
            if flags["ei_insurable"]
            else "0::numeric AS ei_insurable"
        )
        cpp_pensionable_expr = (
            "cpp_pensionable"
            if flags["cpp_pensionable"]
            else "0::numeric AS cpp_pensionable"
        )
        float_draw_expr = (
            "float_draw"
            if flags["float_draw"]
            else "0::numeric AS float_draw"
        )
        cpp_employer_expr = (
            "cpp_employer"
            if flags["cpp_employer"]
            else "COALESCE(cpp_employee, 0) AS cpp_employer"
        )
        ei_employer_expr = (
            "ei_employer"
            if flags["ei_employer"]
            else "ROUND(COALESCE(ei_employee, 0) * 1.4, 2) AS ei_employer"
        )

        cur.execute(  # nosec
            f"""
            SELECT employee_pay_id, charter_hours_sum, approved_hours,
            overtime_hours,
                   manual_hours_adjustment, total_hours_worked,
                   hourly_rate, rate_source,
                      base_pay, gratuity_percent, gratuity_amount,
                             {float_draw_expr}, reimbursements,
                         pay_advance_deduction,
                   other_income, gross_pay, federal_tax,
                   provincial_tax, {total_income_tax_expr},
                      cpp_employee, ei_employee, {cpp_employer_expr},
                      {ei_employer_expr}, {ei_insurable_expr},
                      {cpp_pensionable_expr}, union_dues,
                   total_deductions, net_pay, data_completeness,
                   data_source, confidence_level,
                   notes
            FROM employee_pay_master
            WHERE employee_id = %s AND pay_period_id = %s
            LIMIT 1
            """,
            (emp_id, pay_period_id),
        )
        return cur.fetchone()

    def _get_employee_extra_tax_annual(self, emp_id) -> float:
        """Return the standing extra-tax annual amount from the employee record.

        Handles both types:
          '$'  — fixed annual dollar amount (returned as-is)
          '%'  — percentage of gross; converts to an approximate annual dollar
                 amount using the current gross_pay field and num_periods so the
                 existing per-period division in _compute_calculated_deduction_values
                 produces the correct per-period deduction.
        Returns 0.0 on any error or if no extra tax is configured.
        """
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT COALESCE(extra_tax_type, '$'),
                           COALESCE(extra_tax_annual, 0),
                           COALESCE(extra_tax_pct, 0)
                    FROM employees
                    WHERE employee_id = %s
                    LIMIT 1
                    """,
                    (emp_id,),
                )
                row = cur.fetchone()
            if not row:
                return 0.0
            tax_type, annual_amt, pct = row[0], float(row[1]), float(row[2])
            if tax_type == '%':
                gross = max(0.0, self.gross_pay.value())
                num_periods = max(1, self._period_count())
                return gross * (pct / 100.0) * num_periods
            return max(0.0, annual_amt)
        except Exception:
            return 0.0

    def _apply_loaded_pay_entry(self, row, emp_id, pay_period) -> None:
        (
            employee_pay_id,
            charter_hours_sum,
            approved_hours_total,
            overtime_hours,
            manual_hours_adjustment,
            total_hours_worked,
            _hourly_rate,
            _rate_source,
            base_pay,
            _gratuity_percent,
            gratuity_amount,
            float_draw,
            reimbursements,
            pay_advance_deduction,
            other_income,
            gross_pay,
            federal_tax,
            provincial_tax,
            total_income_tax,
            cpp_employee,
            ei_employee,
            cpp_employer,
            ei_employer,
            ei_insurable,
            cpp_pensionable,
            union_dues,
            total_deductions,
            net_pay,
            data_completeness,
            data_source,
            confidence_level,
            notes,
        ) = row

        cleaned_notes, pay2_hours, _pay2_rate_legacy = self._extract_pay2_from_notes(notes)
        cleaned_notes, extra_annual = self._extract_extra_tax_from_notes(cleaned_notes)
        approved_hours_total = float(approved_hours_total or 0)
        approved_hours_1 = max(0.0, approved_hours_total - pay2_hours)

        self.charter_hours.setValue(float(charter_hours_sum or 0))
        self.charter_hours_1.setValue(approved_hours_1)
        self.charter_hours_2.setValue(pay2_hours)
        self.approved_hours.setValue(approved_hours_1)
        self.approved_hours_2.setValue(pay2_hours)
        self.overtime_hours.setValue(float(overtime_hours or 0))
        self.manual_hours_adjustment.setValue(float(manual_hours_adjustment or 0))
        self.total_hours_worked.setValue(float(total_hours_worked or 0))
        # Always use employee master rates (do not inherit historical row/note variations).
        self._apply_employee_master_rates(emp_id)

        self.base_pay.setValue(float(base_pay or 0))
        # Gratuity percent is deprecated; keep value-based gratuity as source of truth.
        self.gratuity_percent.setValue(0.0)
        self.gratuity_amount.setValue(float(gratuity_amount or 0))
        if hasattr(self, "float_draw"):
            self.float_draw.setValue(float(float_draw or 0))
        self.reimbursements.setValue(float(reimbursements or 0))
        if pay_advance_deduction is None:
            pay_advance_deduction = self._get_employee_pay_advance_balance(emp_id)
        self.pay_advance_deduction.setValue(float(pay_advance_deduction or 0))
        self.other_income.setValue(float(other_income or 0))
        self.gross_pay.setValue(float(gross_pay or 0))
        self.ei_insurable.setValue(float(ei_insurable or 0))
        self.cpp_pensionable.setValue(float(cpp_pensionable or 0))

        self.federal_tax.setValue(float(federal_tax or 0))
        self.provincial_tax.setValue(float(provincial_tax or 0))
        self.total_income_tax.setValue(float(total_income_tax or 0))
        self.cpp_employee.setValue(float(cpp_employee or 0))
        self.ei_employee.setValue(float(ei_employee or 0))
        self.cpp_employer.setValue(float(cpp_employer or 0))
        self.ei_employer.setValue(float(ei_employer or 0))
        self.union_dues.setValue(float(union_dues or 0))
        self.total_deductions.setValue(float(total_deductions or 0))
        self.net_pay.setValue(float(net_pay or 0))

        self.data_completeness.setValue(float(data_completeness or 0))
        self._set_combo_value(self.data_source_combo, data_source)
        self.confidence_level.setValue(float(confidence_level or 0))
        # If no per-period override was embedded in notes, look up the
        # employee's standing extra-tax preference from the employees table.
        if extra_annual <= 0.0 and emp_id:
            extra_annual = self._get_employee_extra_tax_annual(emp_id)
        self.extra_annual_contribution.setValue(extra_annual)
        self.notes_edit.setPlainText(cleaned_notes or "")
        self._last_synced_charter_hours = None
        self._last_synced_approved_hours = None
        self._last_synced_gratuity = None

        self._set_status(
            f"Loaded employee_pay_id {employee_pay_id} for P{pay_period[2]:02d}."
        )
        self._update_calculated_displays_only()
        self.recalculate_totals()
        self._load_ytd_totals()
        self._load_pay_printout()
        self._refresh_work_item_summary()
        self.pay_ledger.refresh(
            emp_id,
            pay_period[1],
            pay_period[0],
            self.net_pay.value(),
        )
        self._refresh_t4_override_status()

    @pyqtSlot()
    def save_entry(
        self, _checked=False, silent=False, recalc_before_save=True
    ) -> bool:
        if self._saving_entry:
            return False

        selection = self._get_save_selection(silent)
        if not selection:
            return False
        emp_id, pay_period = selection

        # Enforce rates from employee master before recalculation/save.
        self._apply_employee_master_rates(emp_id)

        if recalc_before_save:
            self.recalculate_totals(force_base_pay=False)

        # Auto-apply CRA deductions when gross pay > 0 but all tax/contribution
        # fields are still zero (e.g. new entry not yet processed via the
        # "Update Record From Calculated" button).
        if recalc_before_save and self.gross_pay.value() > 0:
            zero_eps = 0.005
            all_deductions_zero = (
                abs(self.federal_tax.value()) <= zero_eps
                and abs(self.provincial_tax.value()) <= zero_eps
                and abs(self.cpp_employee.value()) <= zero_eps
                and abs(self.ei_employee.value()) <= zero_eps
            )
            if all_deductions_zero:
                self._apply_calculated_deductions_to_pay()

        if recalc_before_save:
            self._auto_correct_deduction_outlier(reason="save", silent=silent)

        fiscal_year = pay_period[1]
        values = self._gather_values()
        self._apply_ei_exempt_overrides(emp_id, values)

        self._saving_entry = True
        saved_ok = False
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'employee_pay_master'
                """)
                table_columns = {row[0] for row in cur.fetchall()}
                params, sql = self._build_pay_master_upsert_sql(
                    values,
                    emp_id,
                    pay_period,
                    fiscal_year,
                    table_columns,
                )
                cur.execute(sql, params)
                saved_id = cur.fetchone()[0]
                if not silent:
                    self._set_status(
                        f"Saved employee_pay_id {saved_id} for"
                        f"P{pay_period[2]:02d} ({fiscal_year})."

                    )
            self._load_ytd_totals()
            self.pay_ledger.refresh(
                emp_id,
                fiscal_year,
                pay_period[0],
                self.net_pay.value(),
            )
            saved_ok = True
        except Exception as exc:
            logger.exception("Failed to save payroll entry")
            if not silent:
                self._set_status(f"Failed to save: {exc}", error=True)
        finally:
            self._saving_entry = False
        return saved_ok

    def _get_save_selection(self, silent: bool = False) -> tuple | None:
        emp_id = self._selected_employee_id()
        pay_period = self._selected_pay_period()
        if emp_id and pay_period:
            return emp_id, pay_period

        if not silent:
            QMessageBox.warning(
                self,
                "Missing Selection",
                "Select an employee and pay period first.",
            )
        return None

    def _apply_ei_exempt_overrides(self, emp_id: int, values: dict) -> None:
        if not self._is_ei_exempt_employee(emp_id):
            return

        values["ei_employee"] = 0.0
        values["ei_employer"] = 0.0
        self.ei_employee.setValue(0.0)
        self.ei_employer.setValue(0.0)
        self.recalculate_totals(force_base_pay=False)
        values["total_deductions"] = self.total_deductions.value()
        values["net_pay"] = self.net_pay.value()

    def _build_pay_master_upsert_sql(
        self,
        values: dict,
        emp_id: int,
        pay_period,
        fiscal_year: int,
        table_columns: set[str],
    ) -> tuple[dict, str]:
        params = {
            **values,
            "employee_id": emp_id,
            "pay_period_id": pay_period[0],
            "fiscal_year": fiscal_year,
            "created_by": "desktop_app",
        }
        desired_columns = [
            "employee_id",
            "pay_period_id",
            "fiscal_year",
            "charter_hours_sum",
            "approved_hours",
            "overtime_hours",
            "manual_hours_adjustment",
            "total_hours_worked",
            "hourly_rate",
            "rate_source",
            "base_pay",
            "gratuity_percent",
            "gratuity_amount",
            "float_draw",
            "reimbursements",
            "pay_advance_deduction",
            "other_income",
            "gross_pay",
            "federal_tax",
            "provincial_tax",
            "total_income_tax",
            "cpp_employee",
            "ei_employee",
            "cpp_employer",
            "ei_employer",
            "ei_insurable",
            "cpp_pensionable",
            "union_dues",
            "total_deductions",
            "net_pay",
            "data_completeness",
            "data_source",
            "confidence_level",
            "notes",
            "updated_at",
            "created_by",
        ]
        insert_columns = [
            col
            for col in desired_columns
            if col in table_columns or col == "updated_at"
        ]
        insert_values_sql = [
            "NOW()" if col == "updated_at" else f"%({col})s"
            for col in insert_columns
        ]

        update_columns = [
            col
            for col in insert_columns
            if col not in {"employee_id", "pay_period_id", "updated_at"}
        ]
        update_assignments = [
            f"{col} = EXCLUDED.{col}"
            for col in update_columns
            if col != "created_by"
        ]
        update_assignments.append("updated_at = NOW()")
        if "created_by" in update_columns:
            update_assignments.append("created_by = EXCLUDED.created_by")

        sql = f"""
            INSERT INTO employee_pay_master
                ({', '.join(insert_columns)})
            VALUES ({', '.join(insert_values_sql)})
            ON CONFLICT (employee_id, pay_period_id) DO UPDATE SET
                {', '.join(update_assignments)}
            RETURNING employee_pay_id
        """
        return params, sql

    def _update_calculated_pays(self) -> None:
        """Update calculated pay fields and base pay when hours or rates"
        "change."""

        # Calculate individual pay amounts
        pay1_calc = round(
            self.approved_hours.value() * self.hourly_rate.value(), 2
        )
        pay2_calc = round(
            self.approved_hours_2.value() * self.hourly_rate_2.value(), 2
        )
        combined = round(pay1_calc + pay2_calc, 2)

        # Update display fields
        self.pay1_calculated.setValue(pay1_calc)
        self.pay2_calculated.setValue(pay2_calc)
        self.combined_total.setValue(combined)

        # Auto-update Base Pay from combined total
        self.base_pay.setValue(combined)

        # Recalculate all downstream totals (gratuity, gross, deductions, net)
        self.recalculate_totals(force_base_pay=False)

    def _update_calculated_displays_only(self) -> None:
        """Update display fields without changing base pay (used during"
        "load)."""

        # Calculate individual pay amounts
        pay1_calc = round(
            self.approved_hours.value() * self.hourly_rate.value(), 2
        )
        pay2_calc = round(
            self.approved_hours_2.value() * self.hourly_rate_2.value(), 2
        )
        combined = round(pay1_calc + pay2_calc, 2)

        # Update display fields ONLY (don't override loaded base_pay)
        self.pay1_calculated.setValue(pay1_calc)
        self.pay2_calculated.setValue(pay2_calc)
        self.combined_total.setValue(combined)

    def recalculate_totals(self, force_base_pay=False) -> None:
        """
        Recalculate totals. If force_base_pay=True,
        always recalculate base pay from hours*rates.
        This is called by the Recalculate button with force_base_pay=True.
        During load_entry, it's called with force_base_pay=False
        to avoid overwriting manual values.

        IMPORTANT: Pay 1 Rate and Pay 2 Rate are LOCKED and never auto-changed.
                   They remain at their loaded/set values. Only Base Pay is
                   recalculated.
        """
        approved_hours_1 = self.approved_hours.value()
        approved_hours_2 = self.approved_hours_2.value()
        total_hours = (
            approved_hours_1
            + approved_hours_2
            + self.overtime_hours.value()
            + self.manual_hours_adjustment.value()
        )
        if total_hours < 0:
            total_hours = 0
        self.total_hours_worked.setValue(round(total_hours, 2))

        pay1_hours = max(
            0.0,
            approved_hours_1
            + self.overtime_hours.value()
            + self.manual_hours_adjustment.value(),
        )
        pay2_hours = max(0.0, approved_hours_2)

        # *** CRITICAL: Use the CURRENT (locked) Pay 1 and Pay 2 rates - NEVER
        # auto-change them ***
        pay1_rate = self.hourly_rate.value()  # LOCKED - do not modify
        pay2_rate = self.hourly_rate_2.value()  # LOCKED - do not modify

        suggested_base = round(
            (pay1_rate * pay1_hours) + (pay2_rate * pay2_hours),
            2,
        )
        # Only auto-update base_pay if:
        # 1) It's currently zero (loading new entry), OR
        # 2) force_base_pay=True (user clicked "Recalculate" button explicitly)
        if force_base_pay or abs(self.base_pay.value()) < 0.005:
            self.base_pay.setValue(suggested_base)

        # Gratuity remains value-based; no percent-driven fallback.

        float_draw_value = (
            self.float_draw.value() if hasattr(self, "float_draw") else 0.0
        )
        taxable_gross = (
            self.base_pay.value()
            + self.gratuity_amount.value()
            + float_draw_value
            + self.other_income.value()
        )
        self.gross_pay.setValue(round(taxable_gross, 2))

        # Auto-update T4 Box 24 (EI Insurable) and Box 26 (CPP Pensionable)
        # Typically these equal gross pay unless there are special exemptions
        self.ei_insurable.setValue(round(taxable_gross, 2))
        self.cpp_pensionable.setValue(round(taxable_gross, 2))

        total_deductions = (
            self.federal_tax.value()
            + self.provincial_tax.value()
            + self.cpp_employee.value()
            + self.ei_employee.value()
            + self.pay_advance_deduction.value()
        )
        # Union dues removed - not applicable
        # + self.union_dues.value())
        self.total_deductions.setValue(round(total_deductions, 2))

        # Reimbursements are paid out; pay advances reduce the payout.
        net = (
            taxable_gross
            + self.reimbursements.value()
            - self.pay_advance_deduction.value()
            - total_deductions
        )
        self.net_pay.setValue(round(net, 2))

        # Update total income tax (T4-22)
        self._update_total_income_tax()
        self._update_calculated_deduction_comparison()

    def _refresh_work_item_summary(self) -> None:
        emp_id = self._selected_employee_id()
        pay_period = self._selected_pay_period()
        fiscal_year = int(self.year_combo.currentText() or 0) if self.year_combo.currentText() else None
        if not emp_id:
            self.work_items_income_label.setText("Non-Charter Work: $0.00")
            self.work_items_reimburse_label.setText("Reimbursements Tracked: $0.00")
            self.work_items_advances_label.setText("Advances/Floats/Loans Outstanding: $0.00")
            return

        pay_period_id = int(pay_period[0]) if pay_period else None
        summary = get_work_item_summary(
            self.db,
            int(emp_id),
            pay_period_id=pay_period_id,
            fiscal_year=fiscal_year,
        )
        self.work_items_income_label.setText(
            f"Non-Charter Work: ${summary.payable_income:,.2f}"
        )
        self.work_items_reimburse_label.setText(
            f"Reimbursements Tracked: ${summary.reimbursements:,.2f}"
        )
        self.work_items_advances_label.setText(
            "Advances/Floats/Loans Outstanding: "
            f"${summary.advances_outstanding + summary.float_outstanding + summary.loan_outstanding:,.2f}"
        )

    def _open_work_items_dialog(self) -> None:
        emp_id = self._selected_employee_id()
        if not emp_id:
            QMessageBox.information(
                self,
                "Work Items",
                "Select an employee first.",
            )
            return

        pay_period = self._selected_pay_period()
        pay_period_id = int(pay_period[0]) if pay_period else None
        fiscal_year = int(self.year_combo.currentText() or 0) if self.year_combo.currentText() else None

        dlg = EmployeeWorkItemsDialog(
            self.db,
            int(emp_id),
            fiscal_year=fiscal_year,
            pay_period_id=pay_period_id,
            parent=self,
        )
        dlg.exec()

        summary = get_work_item_summary(
            self.db,
            int(emp_id),
            pay_period_id=pay_period_id,
            fiscal_year=fiscal_year,
        )

        # Apply tracked items into payroll fields so T4 boxes include
        # non-charter compensated work and reconciled reimbursements.
        if summary.payable_income > 0:
            self.other_income.setValue(round(summary.payable_income, 2))
        if summary.reimbursements > 0:
            self.reimbursements.setValue(round(summary.reimbursements, 2))
        outstanding = max(
            0.0,
            summary.advances_outstanding
            + summary.float_outstanding
            + summary.loan_outstanding,
        )
        if outstanding > 0:
            self.pay_advance_deduction.setValue(round(outstanding, 2))

        self._refresh_work_item_summary()
        self.recalculate_totals(force_base_pay=False)

    def _period_count(self) -> int:
        count = len(self.pay_periods) if self.pay_periods else 12
        return max(count, 1)

    def _selected_tax_year(self) -> int:
        try:
            return int(self.year_combo.currentText())
        except (ValueError, AttributeError):
            return QDate.currentDate().year()

    def _warn_cra_fallback_once(self, year: int) -> None:
        if year in self._warned_cra_fallback_years:
            return
        self._warned_cra_fallback_years.add(year)
        self._set_status(
            f"⚠ CRA rates/brackets not configured for {year}; using fallback values.",
            error=False,
        )
        logger.warning(
            "CRA rates/brackets not configured for %s; using fallback values.",
            year,
        )

    def _current_cra_rates(self) -> dict[str, float]:
        year = self._selected_tax_year()

        # Prefer DB-backed yearly rates so values persist across releases.
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT
                        cpp_contribution_rate_employee,
                        cpp_max_employee_contribution,
                        cpp_basic_exemption,
                        ei_rate,
                        ei_max_employee_contribution
                    FROM tax_year_reference
                    WHERE year = %s
                    LIMIT 1
                    """,
                    (year,),
                )
                row = cur.fetchone()
            if row and all(v is not None for v in row):
                return {
                    "cpp_rate": float(row[0]),
                    "cpp_max": float(row[1]),
                    "cpp_exempt": float(row[2]),
                    "ei_rate": float(row[3]),
                    "ei_max": float(row[4]),
                }
        except Exception as exc:
            logger.warning(
                "Could not load payroll rates from tax_year_reference for %s: %s",
                year,
                exc,
            )

        rates_by_year = {
            2026: {
                "cpp_rate": 0.0595,
                "cpp_max": 4230.45,
                "cpp_exempt": 3500,
                "ei_rate": 0.0163,
                "ei_max": 1123.07,
            },
            2025: {
                "cpp_rate": 0.0595,
                "cpp_max": 4034.10,
                "cpp_exempt": 3500,
                "ei_rate": 0.0164,
                "ei_max": 1077.48,
            },
            2024: {
                "cpp_rate": 0.0595,
                "cpp_max": 3867.50,
                "cpp_exempt": 3500,
                "ei_rate": 0.0166,
                "ei_max": 1049.12,
            },
            2023: {
                "cpp_rate": 0.0595,
                "cpp_max": 3754.45,
                "cpp_exempt": 3500,
                "ei_rate": 0.0163,
                "ei_max": 1002.45,
            },
            2022: {
                "cpp_rate": 0.057,
                "cpp_max": 3499.80,
                "cpp_exempt": 3500,
                "ei_rate": 0.0158,
                "ei_max": 952.74,
            },
            2021: {
                "cpp_rate": 0.0545,
                "cpp_max": 3166.45,
                "cpp_exempt": 3500,
                "ei_rate": 0.0158,
                "ei_max": 889.54,
            },
            2020: {
                "cpp_rate": 0.0525,
                "cpp_max": 2898.00,
                "cpp_exempt": 3500,
                "ei_rate": 0.0158,
                "ei_max": 856.36,
            },
            2019: {
                "cpp_rate": 0.051,
                "cpp_max": 2748.90,
                "cpp_exempt": 3500,
                "ei_rate": 0.0162,
                "ei_max": 860.22,
            },
            2018: {
                "cpp_rate": 0.0495,
                "cpp_max": 2593.80,
                "cpp_exempt": 3500,
                "ei_rate": 0.0166,
                "ei_max": 858.22,
            },
            2017: {
                "cpp_rate": 0.0495,
                "cpp_max": 2564.10,
                "cpp_exempt": 3500,
                "ei_rate": 0.0163,
                "ei_max": 836.19,
            },
            2016: {
                "cpp_rate": 0.0495,
                "cpp_max": 2544.30,
                "cpp_exempt": 3500,
                "ei_rate": 0.0188,
                "ei_max": 955.04,
            },
            2015: {
                "cpp_rate": 0.0495,
                "cpp_max": 2479.95,
                "cpp_exempt": 3500,
                "ei_rate": 0.0188,
                "ei_max": 930.60,
            },
            2014: {
                "cpp_rate": 0.0495,
                "cpp_max": 2425.50,
                "cpp_exempt": 3500,
                "ei_rate": 0.0188,
                "ei_max": 913.68,
            },
            2013: {
                "cpp_rate": 0.0495,
                "cpp_max": 2356.20,
                "cpp_exempt": 3500,
                "ei_rate": 0.0188,
                "ei_max": 891.12,
            },
            2012: {
                "cpp_rate": 0.0495,
                "cpp_max": 2306.70,
                "cpp_exempt": 3500,
                "ei_rate": 0.0183,
                "ei_max": 839.97,
            },
        }
        fallback = {
            "cpp_rate": 0.0495,
            "cpp_max": 2897.00,
            "cpp_exempt": 3500,
            "ei_rate": 0.0188,
            "ei_max": 891.12,
        }
        rates = rates_by_year.get(year)
        if rates is None:
            self._warn_cra_fallback_once(year)
            return fallback
        return rates

    def _compute_bracket_tax(self, annual_income: float, year: int) -> tuple[float, float]:
        """Compute federal and Alberta provincial income tax from CRA brackets.

        Returns (federal_annual, provincial_annual) for the given annual income.
        Queries the federal_tax_brackets / alberta_tax_brackets DB tables first;
        falls back to hardcoded values for years not yet in the DB.
        Alberta is used as the province (BPA-based deduction applied first).
        """
        # CRA-confirmed hardcoded brackets (income_to=None means infinity)
        # Federal BPAs: 2023=$15,000  2024=$15,705  2025=$16,129  2026=$16,566
        # Alberta BPAs: 2023/24=$21,003  2025=$21,985  2026=$22,573
        hardcoded_federal: dict[int, dict] = {
            2026: {"bpa": 16566, "brackets": [
                (58944, 0.15), (117888, 0.205), (182744, 0.26),
                (260257, 0.29), (float("inf"), 0.33),
            ]},
            2025: {"bpa": 16129, "brackets": [
                (57375, 0.15), (114750, 0.205), (177882, 0.26),
                (253414, 0.29), (float("inf"), 0.33),
            ]},
            2024: {"bpa": 15705, "brackets": [
                (55867, 0.15), (111733, 0.205), (173205, 0.26),
                (246752, 0.29), (float("inf"), 0.33),
            ]},
            2023: {"bpa": 15000, "brackets": [
                (53359, 0.15), (106717, 0.205), (165430, 0.26),
                (235675, 0.29), (float("inf"), 0.33),
            ]},
        }
        hardcoded_alberta: dict[int, dict] = {
            2026: {"bpa": 22573, "brackets": [
                (148269, 0.10), (177922, 0.12), (237230, 0.13),
                (355845, 0.14), (float("inf"), 0.15),
            ]},
            2025: {"bpa": 21985, "brackets": [
                (148269, 0.10), (177922, 0.12), (237230, 0.13),
                (355845, 0.14), (float("inf"), 0.15),
            ]},
            2024: {"bpa": 21003, "brackets": [
                (148269, 0.10), (177922, 0.12), (237230, 0.13),
                (355845, 0.14), (float("inf"), 0.15),
            ]},
            2023: {"bpa": 21003, "brackets": [
                (148269, 0.10), (177922, 0.12), (237230, 0.13),
                (355845, 0.14), (float("inf"), 0.15),
            ]},
        }

        def _load_from_db(table: str) -> dict | None:
            """Try to load brackets for 'year' from DB. Returns cfg dict or None."""
            try:
                from db_utils import DatabaseContext
                with DatabaseContext(self.db, auto_commit=False) as cur:
                    cur.execute(  # nosec
                        f"SELECT income_to, tax_rate FROM {table} "
                        "WHERE year = %s ORDER BY bracket_number",
                        (year,),
                    )
                    rows = cur.fetchall()
                if not rows:
                    return None
                # BPA is stored separately only for federal; use hardcoded BPA
                brackets = [
                    (float(r[0]) if r[0] is not None else float("inf"),
                     float(r[1]))
                    for r in rows
                ]
                # Determine BPA from hardcoded tables (DB doesn't store BPA)
                if table == "federal_tax_brackets":
                    bpa = hardcoded_federal.get(year, hardcoded_federal[2026])["bpa"]
                else:
                    bpa = hardcoded_alberta.get(year, hardcoded_alberta[2026])["bpa"]
                return {"bpa": bpa, "brackets": brackets}
            except Exception:
                return None

        def _bracket_tax(income: float, bpa: float, brackets: list) -> float:
            taxable = max(0.0, income - bpa)
            tax = 0.0
            prev = 0.0
            for threshold, rate in brackets:
                if taxable <= prev:
                    break
                chunk = min(taxable, threshold) - prev
                tax += chunk * rate
                prev = threshold
            return tax

        fed_from_db = _load_from_db("federal_tax_brackets")
        prov_from_db = _load_from_db("alberta_tax_brackets")
        fed_cfg = fed_from_db or hardcoded_federal.get(year, hardcoded_federal[2026])
        prov_cfg = prov_from_db or hardcoded_alberta.get(year, hardcoded_alberta[2026])
        if year not in hardcoded_federal or year not in hardcoded_alberta:
            if fed_from_db is None or prov_from_db is None:
                self._warn_cra_fallback_once(year)

        fed_annual = _bracket_tax(annual_income, fed_cfg["bpa"], fed_cfg["brackets"])
        prov_annual = _bracket_tax(annual_income, prov_cfg["bpa"], prov_cfg["brackets"])
        return round(fed_annual, 2), round(prov_annual, 2)

    def _compute_calculated_deduction_values(
        self, preserve_existing_tax: bool = True
    ) -> dict[str, float]:
        comparison_income = max(
            0.0, self.gross_pay.value() - self.reimbursements.value()
        )
        rates = self._current_cra_rates()
        num_periods = self._period_count()

        ytd_cpp = self.ytd_cpp_employee.value()
        ytd_ei = self.ytd_ei_employee.value()

        period_exemption = rates["cpp_exempt"] / num_periods
        cpp_pensionable = max(0.0, comparison_income - period_exemption)
        cpp_amount = min(
            round(cpp_pensionable * rates["cpp_rate"], 2),
            max(0.0, rates["cpp_max"] - ytd_cpp),
        )

        ei_amount = min(
            round(comparison_income * rates["ei_rate"], 2),
            max(0.0, rates["ei_max"] - ytd_ei),
        )

        extra_annual = max(0.0, self.extra_annual_contribution.value())
        extra_period = round(extra_annual / num_periods, 2)

        current_fed = self.federal_tax.value()
        current_prov = self.provincial_tax.value()
        current_total_tax = current_fed + current_prov

        if preserve_existing_tax and current_total_tax > 0:
            # User has existing values — preserve their effective rate
            effective_tax_pct = (
                (current_total_tax / comparison_income) * 100
                if comparison_income > 0 else 0.0
            )
            tax_amount = round(
                (comparison_income * (effective_tax_pct / 100.0)) + extra_period, 2
            )
            if current_total_tax > 0:
                fed_share = current_fed / current_total_tax
                prov_share = current_prov / current_total_tax
            else:
                fed_share, prov_share = 1.0, 0.0
            fed_tax_amount = round(tax_amount * fed_share, 2)
            prov_tax_amount = round(tax_amount * prov_share, 2)
        else:
            # No existing tax — calculate from CRA brackets
            try:
                year = int(self.year_combo.currentText())
            except (ValueError, AttributeError):
                year = 2026
            annual_income = comparison_income * num_periods
            fed_annual, prov_annual = self._compute_bracket_tax(annual_income, year)
            fed_tax_amount = round(fed_annual / num_periods + extra_period * 0.6, 2)
            prov_tax_amount = round(prov_annual / num_periods + extra_period * 0.4, 2)
            tax_amount = round(fed_tax_amount + prov_tax_amount, 2)
            effective_tax_pct = (
                (tax_amount / comparison_income) * 100 if comparison_income > 0 else 0.0
            )

        cpp_pct = (
            (cpp_amount / comparison_income) * 100 if comparison_income > 0 else 0.0
        )
        ei_pct = (
            (ei_amount / comparison_income) * 100 if comparison_income > 0 else 0.0
        )

        return {
            "comparison_income": round(comparison_income, 2),
            "cpp_amount": round(cpp_amount, 2),
            "ei_amount": round(ei_amount, 2),
            "tax_amount": round(tax_amount, 2),
            "fed_tax_amount": round(fed_tax_amount, 2),
            "prov_tax_amount": round(prov_tax_amount, 2),
            "cpp_pct": round(cpp_pct, 3),
            "ei_pct": round(ei_pct, 3),
            "tax_pct": round(effective_tax_pct, 3),
            "extra_period": extra_period,
        }

    def _deduction_ratio_snapshot(self) -> dict[str, float]:
        gross = max(0.0, self.gross_pay.value())
        income_tax = self.federal_tax.value() + self.provincial_tax.value()
        total_ded = self.total_deductions.value()
        if gross <= 0:
            return {
                "gross": 0.0,
                "income_tax": income_tax,
                "total_ded": total_ded,
                "income_tax_ratio": 0.0,
                "total_ded_ratio": 0.0,
            }
        return {
            "gross": gross,
            "income_tax": income_tax,
            "total_ded": total_ded,
            "income_tax_ratio": income_tax / gross,
            "total_ded_ratio": total_ded / gross,
        }

    def _auto_correct_deduction_outlier(
        self, reason: str, silent: bool = False
    ) -> bool:
        snapshot = self._deduction_ratio_snapshot()
        if (
            snapshot["gross"] <= 0
            or snapshot["total_ded_ratio"] <= MAX_REASONABLE_DEDUCTION_RATIO
        ):
            return False

        values = self._compute_calculated_deduction_values(
            preserve_existing_tax=False
        )
        self.cpp_employee.setValue(values["cpp_amount"])
        self.ei_employee.setValue(values["ei_amount"])
        self.federal_tax.setValue(values["fed_tax_amount"])
        self.provincial_tax.setValue(values["prov_tax_amount"])
        self.recalculate_totals(force_base_pay=False)

        if not silent:
            self._set_status(
                "Deduction outlier corrected using CRA-based tax/CPP/EI "
                f"values before {reason}."
            )
        logger.warning(
            "Corrected payroll deduction outlier before %s: gross=%.2f "
            "income_tax=%.2f total_ded=%.2f total_ded_ratio=%.2f%%",
            reason,
            snapshot["gross"],
            snapshot["income_tax"],
            snapshot["total_ded"],
            snapshot["total_ded_ratio"] * 100.0,
        )
        return True

    def _update_calculated_deduction_comparison(self) -> None:
        values = self._compute_calculated_deduction_values()
        self.calc_taxable_income.setValue(values["comparison_income"])
        self.calc_cpp_amount.setValue(values["cpp_amount"])
        self.calc_ei_amount.setValue(values["ei_amount"])
        self.calc_tax_amount.setValue(values["tax_amount"])
        self.calc_cpp_percent.setValue(values["cpp_pct"])
        self.calc_ei_percent.setValue(values["ei_pct"])
        self.calc_tax_percent.setValue(values["tax_pct"])
        self.extra_period_contribution.setValue(values["extra_period"])
        self._refresh_manual_deduction_indicators()

    def _refresh_manual_deduction_indicators(self) -> None:
        """Show CRA-calculated deduction amounts and mark manual overrides."""

        calc_values = self._compute_calculated_deduction_values(
            preserve_existing_tax=False
        )
        expected_amounts = {
            "cpp": calc_values["cpp_amount"],
            "ei": calc_values["ei_amount"],
            "federal": calc_values["fed_tax_amount"],
            "provincial": calc_values["prov_tax_amount"],
        }
        entered_amounts = {
            "cpp": self.cpp_employee.value(),
            "ei": self.ei_employee.value(),
            "federal": self.federal_tax.value(),
            "provincial": self.provincial_tax.value(),
        }
        tolerance = 0.01

        for key, expected in expected_amounts.items():
            self._manual_deduction_calc_labels[key].setText(
                f"Calc: ${expected:.2f}"
            )
            is_manual = abs(entered_amounts[key] - expected) > tolerance

            field_widget = self._manual_deduction_widgets[key]
            if is_manual:
                self._manual_deduction_flags[key].setText("MANUAL")
                field_widget.setStyleSheet(self._manual_deduction_override_style)
            else:
                self._manual_deduction_flags[key].setText("")
                field_widget.setStyleSheet("")

    def _apply_calculated_deductions_to_pay(
        self, preserve_existing_tax: bool = False
    ) -> None:
        values = self._compute_calculated_deduction_values(
            preserve_existing_tax=preserve_existing_tax
        )
        self.cpp_employee.setValue(values["cpp_amount"])
        self.ei_employee.setValue(values["ei_amount"])

        self.federal_tax.setValue(values["fed_tax_amount"])
        self.provincial_tax.setValue(values["prov_tax_amount"])

        self.recalculate_totals(force_base_pay=False)
        self._set_status(
            "Applied calculated CPP/EI/tax values. Manual edits remain"
            " available."
        )

    def _update_total_income_tax(self) -> None:
        """Auto-calculate total income tax (T4-22) from federal +"
        "provincial."""

        total = self.federal_tax.value() + self.provincial_tax.value()
        self.total_income_tax.setValue(round(total, 2))

    def _update_employer_cpp(self) -> None:
        """Auto-calculate CPP employer portion (1:1 matching - CRA"
        "requirement)"""

        self.cpp_employer.setValue(self.cpp_employee.value())

    def _update_employer_ei(self) -> None:
        """Auto-calculate EI employer portion (1.4x employee - CRA"
        "requirement)"""

        self.ei_employer.setValue(round(self.ei_employee.value() * 1.4, 2))

    @pyqtSlot()
    def _auto_suggest_cpp_ei(self) -> None:
        """Calculate and fill CPP/EI employee deductions from gross pay.

        Uses CRA rates for the selected fiscal year, pro-rates the CPP
        basic exemption per pay period, and caps against the annual maximum
        minus YTD already contributed.
        """
        rates = self._current_cra_rates()
        gross = max(0.0, self.gross_pay.value() - self.reimbursements.value())
        ytd_cpp = self.ytd_cpp_employee.value()
        ytd_ei = self.ytd_ei_employee.value()

        # Determine pay periods in year (monthly = 12)
        num_periods = self._period_count()

        # CPP: pro-rate exemption per period
        period_exemption = rates["cpp_exempt"] / num_periods
        cpp_pensionable = max(0.0, gross - period_exemption)
        cpp_this_period = round(cpp_pensionable * rates["cpp_rate"], 2)
        cpp_room = max(0.0, rates["cpp_max"] - ytd_cpp)
        cpp_this_period = min(cpp_this_period, cpp_room)

        # EI: no exemption
        ei_this_period = round(gross * rates["ei_rate"], 2)
        ei_room = max(0.0, rates["ei_max"] - ytd_ei)
        ei_this_period = min(ei_this_period, ei_room)

        self.cpp_employee.setValue(cpp_this_period)
        self.ei_employee.setValue(ei_this_period)

    def _gather_values(self) -> dict:
        self._apply_employee_master_rates(self._selected_employee_id())
        approved_hours_1 = self.approved_hours.value()
        approved_hours_2 = self.approved_hours_2.value()
        note_text = self._compose_notes_with_pay2(
            self.notes_edit.toPlainText().strip()
        )
        return {
            "charter_hours_sum": self.charter_hours.value(),
            "approved_hours": approved_hours_1 + approved_hours_2,
            "overtime_hours": self.overtime_hours.value(),
            "manual_hours_adjustment": self.manual_hours_adjustment.value(),
            "total_hours_worked": self.total_hours_worked.value(),
            "hourly_rate": self.hourly_rate.value(),
            "rate_source": "employee_master",
            "base_pay": self.base_pay.value(),
            "gratuity_percent": 0.0,
            "gratuity_amount": self.gratuity_amount.value(),
            "float_draw": (
                self.float_draw.value() if hasattr(self, "float_draw") else 0.0
            ),
            "reimbursements": self.reimbursements.value(),
            "pay_advance_deduction": self.pay_advance_deduction.value(),
            "other_income": self.other_income.value(),
            "gross_pay": self.gross_pay.value(),
            "federal_tax": self.federal_tax.value(),
            "provincial_tax": self.provincial_tax.value(),
            "total_income_tax": self.total_income_tax.value(),
            "cpp_employee": self.cpp_employee.value(),
            "ei_employee": self.ei_employee.value(),
            "cpp_employer": self.cpp_employer.value(),
            "ei_employer": self.ei_employer.value(),
            "ei_insurable": self.ei_insurable.value(),
            "cpp_pensionable": self.cpp_pensionable.value(),
            "union_dues": 0.0,  # Always 0 - not applicable
            "total_deductions": self.total_deductions.value(),
            "net_pay": self.net_pay.value(),
            "data_completeness": self.data_completeness.value(),
            "data_source": self.data_source_combo.currentText() or None,
            "confidence_level": self.confidence_level.value(),
            "notes": note_text or None,
        }

    def _set_status(self, text, error=False) -> None:
        if error:
            self.status_label.setStyleSheet(
                "color: #dc2626; font-weight: bold;"
            )
        else:
            self.status_label.setStyleSheet(
                "color: #2563eb; font-weight: bold;"
            )
        self.status_label.setText(text)

    def _set_combo_value(self, combo: QComboBox, value) -> None:
        if value is None:
            return
        idx = combo.findText(str(value))
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _is_ei_exempt_employee(self, emp_id) -> bool:
        """Return True when selected employee is configured as EI-exempt."""
        if not emp_id:
            return False
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT COALESCE(employee_number, ''),
                           COALESCE(full_name, '')
                    FROM employees
                    WHERE employee_id = %s
                    LIMIT 1
                    """,
                    (emp_id,),
                )
                row = cur.fetchone()
        except Exception as exc:
            logger.warning(
                "Failed EI exemption lookup for employee_id=%s: %s",
                emp_id,
                exc,
            )
            return False

        if not row:
            return False

        employee_number = (row[0] or "").strip().lower()
        full_name = (row[1] or "").strip().lower()
        return (
            employee_number in EI_EXEMPT_EMPLOYEE_NUMBERS
            or "richard, michael" in full_name
            or "richard, paul" in full_name
        )

    @pyqtSlot()
    def _apply_selected_employee_ei_exempt(self) -> None:
        """Apply EI exemption to the currently selected employee when"
        "applicable."""

        emp_id = self._selected_employee_id()
        if not self._is_ei_exempt_employee(emp_id):
            QMessageBox.information(
                self,
                "Not Configured",
                "EI exemption button is configured for Michael (Dr09) and"
                "Paul (Dr100).",

            )
            return

        self.ei_employee.setValue(0.0)
        self.ei_employer.setValue(0.0)
        self.recalculate_totals(force_base_pay=False)
        self._set_status("Applied EI exemption (EI set to $0.00).")

    def _get_columns(self, table_name: str) -> set[str]:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    """,
                    (table_name,),
                )
                return {row[0] for row in cur.fetchall()}
        except Exception as exc:
            logger.warning(
                "Failed to fetch columns for table '%s': %s",
                table_name,
                exc,
            )

        return set()

    def _ensure_pay_advance_column(self) -> None:
        """Add the payroll pay-advance column when the table is missing it."""

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    ALTER TABLE employee_pay_master
                    ADD COLUMN IF NOT EXISTS pay_advance_deduction NUMERIC NOT NULL DEFAULT 0
                    """
                )
        except Exception as exc:
            logger.warning("Could not ensure pay advance column: %s", exc)

    def _get_employee_pay_advance_balance(self, emp_id) -> float:
        """Return the outstanding pay advance balance for an employee."""

        if not emp_id:
            return 0.0
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(ABS(COALESCE(amount, 0))), 0)
                    FROM employee_expenses
                    WHERE employee_id = %s
                      AND category = 'PAY_ADVANCE'
                      AND COALESCE(reimbursement_status, '') <> 'reimbursed'
                    """,
                    (emp_id,),
                )
                row = cur.fetchone()
            return float(row[0] or 0) if row else 0.0
        except Exception as exc:
            logger.warning("Failed to load pay advance balance for %s: %s", emp_id, exc)
            return 0.0

    def _reset_ytd_totals(self) -> None:
        ytd_widgets = [
            self.ytd_gross_pay,
            self.ytd_ei_insurable,
            self.ytd_cpp_pensionable,
            self.ytd_income_tax,
            self.ytd_cpp_employee,
            self.ytd_ei_employee,
            self.ytd_total_deductions,
            self.ytd_net_pay,
        ]
        for widget in ytd_widgets:
            widget.setValue(0.0)

    def _build_ytd_exprs(self, pay_master_columns: set[str]) -> tuple[str, str, str, str]:
        taxable_gross_sum_expr = (
            "COALESCE(SUM(GREATEST(COALESCE(gross_pay, 0) - "
            "COALESCE(reimbursements, 0), 0)), 0)"
            if "reimbursements" in pay_master_columns
            else "COALESCE(SUM(gross_pay), 0)"
        )

        ei_insurable_expr = (
            "COALESCE(SUM(ei_insurable), 0)"
            if "ei_insurable" in pay_master_columns
            else taxable_gross_sum_expr
        )
        cpp_pensionable_expr = (
            "COALESCE(SUM(cpp_pensionable), 0)"
            if "cpp_pensionable" in pay_master_columns
            else taxable_gross_sum_expr
        )
        income_tax_expr = (
            "COALESCE(SUM(total_income_tax), 0)"
            if "total_income_tax" in pay_master_columns
            else "COALESCE(SUM(COALESCE(federal_tax, 0) + "
            "COALESCE(provincial_tax, 0)), 0)"
        )
        return (
            taxable_gross_sum_expr,
            ei_insurable_expr,
            cpp_pensionable_expr,
            income_tax_expr,
        )

    def _build_ytd_period_filter(self, emp_id: int, fiscal_year: int) -> tuple[str, dict]:
        selected_period = self._selected_pay_period()
        selected_period_num = selected_period[2] if selected_period else None
        selected_pp_id = selected_period[0] if selected_period else None

        if selected_period_num is not None and selected_pp_id:
            period_filter = """
                AND pay_period_id IN (
                    SELECT pay_period_id FROM pay_periods
                    WHERE fiscal_year = %(fiscal_year)s
                      AND period_number <= %(period_num)s
                )
            """
            query_params: dict = {
                "emp_id": emp_id,
                "fiscal_year": fiscal_year,
                "period_num": selected_period_num,
            }
            return period_filter, query_params

        if selected_period_num is not None:
            return "", {
                "emp_id": emp_id,
                "fiscal_year": fiscal_year,
                "period_num": selected_period_num,
            }

        return "", {
            "emp_id": emp_id,
            "fiscal_year": fiscal_year,
            "period_num": 999,
        }

    def _apply_ytd_row(self, row) -> None:
        self.ytd_gross_pay.setValue(float(row[0] or 0.0))
        self.ytd_ei_insurable.setValue(float(row[1] or 0.0))
        self.ytd_cpp_pensionable.setValue(float(row[2] or 0.0))
        self.ytd_income_tax.setValue(float(row[3] or 0.0))
        self.ytd_cpp_employee.setValue(float(row[4] or 0.0))
        self.ytd_ei_employee.setValue(float(row[5] or 0.0))
        self.ytd_total_deductions.setValue(float(row[6] or 0.0))
        self.ytd_net_pay.setValue(float(row[7] or 0.0))

    def _load_ytd_totals(self) -> None:
        """Load year-to-date totals for the selected employee and year."""
        self._reset_ytd_totals()

        emp_id = self._selected_employee_id()
        if not emp_id:
            return

        try:
            fiscal_year = int(self.year_combo.currentText())
        except (ValueError, AttributeError):
            return

        pay_master_columns = self._get_columns("employee_pay_master")
        if not pay_master_columns:
            return

        (
            taxable_gross_sum_expr,
            ei_insurable_expr,
            cpp_pensionable_expr,
            income_tax_expr,
        ) = self._build_ytd_exprs(pay_master_columns)
        period_filter, query_params = self._build_ytd_period_filter(
            emp_id, fiscal_year
        )

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(  # nosec
                    f"""
                    SELECT
                        {taxable_gross_sum_expr} AS ytd_gross,
                        {ei_insurable_expr} AS ytd_ei_insurable,
                        {cpp_pensionable_expr} AS ytd_cpp_pensionable,
                        {income_tax_expr} AS ytd_income_tax,
                        COALESCE(SUM(cpp_employee), 0) AS ytd_cpp_employee,
                        COALESCE(SUM(ei_employee), 0) AS ytd_ei_employee,
                        COALESCE(SUM(total_deductions),
                        0) AS ytd_total_deductions,
                        COALESCE(SUM(net_pay), 0) AS ytd_net_pay
                    FROM employee_pay_master
                    WHERE employee_id = %(emp_id)s AND fiscal_year =
                    %(fiscal_year)s
                    {period_filter}
                    """,
                    query_params,
                )
                row = cur.fetchone() or (0, 0, 0, 0, 0, 0, 0, 0)
            self._apply_ytd_row(row)
        except Exception:
            logger.exception("Failed to load YTD totals")

    def _extract_pay2_from_notes(self, notes_text) -> tuple[str, float, float]:
        """Extract PAY2 metadata from notes while keeping user-facing notes"
        "clean."""

        raw = (notes_text or "").strip()
        match = PAY2_NOTE_PATTERN.search(raw)
        if not match:
            return raw, 0.0, 10.0

        hours = float(match.group("hours"))
        cleaned = PAY2_NOTE_PATTERN.sub("", raw).strip()
        if cleaned.endswith("|"):
            cleaned = cleaned[:-1].strip()
        # Keep PAY2 hours metadata, but rate is now enforced from employee
        # master.
        return cleaned, max(0.0, hours), 10.0

    def _extract_extra_tax_from_notes(self, notes_text) -> tuple[str, float]:
        """Extract extra annual tax metadata from notes."""

        raw = (notes_text or "").strip()
        match = EXTRA_TAX_NOTE_PATTERN.search(raw)
        if not match:
            return raw, 0.0

        annual = max(0.0, float(match.group("annual")))
        cleaned = EXTRA_TAX_NOTE_PATTERN.sub("", raw).strip()
        if cleaned.endswith("|"):
            cleaned = cleaned[:-1].strip()
        return cleaned, annual

    def _compose_notes_with_pay2(self, user_notes) -> str:
        """Persist PAY2 values without changing DB schema."""
        cleaned, _, _ = self._extract_pay2_from_notes(user_notes)
        cleaned, _ = self._extract_extra_tax_from_notes(cleaned)
        pay2_hours = max(0.0, self.approved_hours_2.value())
        pay2_rate = (
            self.hourly_rate_2.value()
            if self.hourly_rate_2.value() > 0
            else 10.0
        )
        extra_annual = max(0.0, self.extra_annual_contribution.value())
        tags = []

        if pay2_hours >= 0.005 or abs(pay2_rate - 10.0) >= 0.005:
            tags.append(f"[PAY2 hours={pay2_hours:.2f} rate={pay2_rate:.2f}]")

        if extra_annual >= 0.005:
            tags.append(f"[EXTRA_TAX annual={extra_annual:.2f}]")
        if not tags:
            return cleaned

        metadata = " ".join(tags)
        if cleaned:
            return f"{cleaned} {metadata}".strip()
        return metadata

    def _sync_pay_fields_from_printout(self, force=False) -> None:
        """Use printout totals as payroll defaults without clobbering manual"
        "overrides."""

        if not force and self._selection_has_saved_entry():
            return

        total_hours = float(getattr(self, "_printout_total_hours", 0.0) or 0.0)
        total_hours_1 = float(
            getattr(self, "_printout_total_hours_1", 0.0) or 0.0
        )
        total_hours_2 = float(
            getattr(self, "_printout_total_hours_2", 0.0) or 0.0
        )
        total_gratuity = float(
            getattr(self, "_printout_total_gratuity", 0.0) or 0.0
        )

        # Always show charter split totals in verification fields.
        self.charter_hours_1.setValue(total_hours_1)
        self.charter_hours_2.setValue(total_hours_2)

        def should_sync(current_value, last_synced) -> bool:
            return (
                force
                or abs(current_value) < 0.005
                or (
                    last_synced is not None
                    and abs(current_value - last_synced) < 0.005
                )
            )

        changed = False
        if total_hours > 0:
            if should_sync(
                self.charter_hours.value(), self._last_synced_charter_hours
            ):
                self.charter_hours.setValue(total_hours)
                self._last_synced_charter_hours = total_hours
                changed = True
            # Approved Hours 1 comes from Hours 1 column (approved/paid), not total
            if total_hours_1 > 0 and should_sync(
                self.approved_hours.value(), self._last_synced_approved_hours
            ):
                self.approved_hours.setValue(total_hours_1)
                self._last_synced_approved_hours = total_hours_1
                changed = True
            # Approved Hours 2 comes from Hours 2 column (remaining)
            if should_sync(self.approved_hours_2.value(), None):
                self.approved_hours_2.setValue(total_hours_2)
                changed = True

        if should_sync(
            self.gratuity_amount.value(), self._last_synced_gratuity
        ):
            self.gratuity_amount.setValue(total_gratuity)
            self._last_synced_gratuity = total_gratuity
            changed = True

        if changed:
            self.recalculate_totals()

    def _parse_route_time(self, raw_value) -> time | None:
        """Best-effort parse of route time values stored as"
        "time/datetime/text."""

        if raw_value is None:
            return None
        if isinstance(raw_value, datetime):
            return raw_value.time()
        if isinstance(raw_value, time):
            return raw_value

        text = str(raw_value).strip()
        if not text:
            return None

        # Normalize common separators and spacing.
        candidate = text.upper().replace(".", ":")
        candidate = re.sub(r"\s+", " ", candidate)

        for fmt in (
            "%H:%M",
            "%H:%M:%S",
            "%I:%M %p",
            "%I:%M%p",
            "%I %p",
            "%I%p",
        ):
            try:
                return datetime.strptime(candidate, fmt).time()
            except ValueError:
                continue
        return None

    def _route_span_hours_for_charter(self, cur, charter_id) -> float:
        """Calculate first-pickup to last-dropoff span (hours) from"
        "charter_routes."""

        if not charter_id:
            return 0.0

        cur.execute(
            """
            SELECT pickup_time, dropoff_time
            FROM charter_routes
            WHERE charter_id = %s
            """,
            (charter_id,),
        )
        rows = cur.fetchall() or []
        if not rows:
            return 0.0

        starts = []
        ends = []
        for pickup_raw, dropoff_raw in rows:
            pickup_time = self._parse_route_time(pickup_raw)
            dropoff_time = self._parse_route_time(dropoff_raw)
            if pickup_time:
                starts.append(pickup_time.hour * 60 + pickup_time.minute)
            if dropoff_time:
                ends.append(dropoff_time.hour * 60 + dropoff_time.minute)

        if not starts or not ends:
            return 0.0

        start_min = min(starts)
        end_min = max(ends)
        if end_min < start_min:
            end_min += 24 * 60
        return round((end_min - start_min) / 60.0, 2)

    def _load_pay_printout(self) -> None:
        """Load charters/work for the selected employee and pay period."""
        emp_id = self._selected_employee_id()
        pay_period = self._selected_pay_period()
        if not emp_id or not pay_period:
            return

        _pp_id, _, _, start, end, _ = pay_period
        try:
            ccols = self._get_columns("charters")
            ecols = self._get_columns("employees")
            driver_col = self._charter_driver_column(ccols)
            if not self._charter_printout_columns_ready(ccols, driver_col):
                return

            with DatabaseContext(self.db, auto_commit=False) as cur:
                payload = self._build_pay_printout_payload(cur, emp_id, start, end, ccols, ecols)
                if not payload:
                    return
                self._apply_pay_printout_payload(cur, payload, emp_id, end, ecols)
        except Exception as exc:
            self._updating_printout_table = False
            logger.exception("Failed to load pay printout")
            self._set_status(f"Failed to load pay printout: {exc}", error=True)

    def _charter_driver_column(self, ccols: set[str]) -> str | None:
        for candidate in ("employee_id", "assigned_driver_id", "driver_id"):
            if candidate in ccols:
                return candidate
        return None

    def _charter_printout_columns_ready(
        self, ccols: set[str], driver_col
    ) -> bool:
        required = {"reserve_number", "charter_date"}
        if not required.issubset(ccols):
            self.pay_printout_table.setRowCount(0)
            self.pay_printout_total_hours.setText(PAY_PRINTOUT_TOTAL_HOURS_DEFAULT)
            self.pay_printout_total_gratuity.setText(PAY_PRINTOUT_TOTAL_GRATUITY_DEFAULT)
            self._set_status(
                f"⚠️  Missing columns in charters table: {required - ccols}",
                error=False,
            )
            return False
        if not driver_col:
            self.pay_printout_table.setRowCount(0)
            self.pay_printout_total_hours.setText(PAY_PRINTOUT_TOTAL_HOURS_DEFAULT)
            self.pay_printout_total_gratuity.setText(PAY_PRINTOUT_TOTAL_GRATUITY_DEFAULT)
            self._set_status(
                "⚠️  No driver ID column found in charters (need"
                "employee_id, assigned_driver_id, or driver_id)",
                error=False,
            )
            return False
        return True

    def _build_pay_printout_payload(
        self, cur, emp_id, start, end, ccols, ecols
    ) -> dict:
        route_cols = self._get_columns("charter_routes")
        can_use_route_span = {"charter_id", "pickup_time", "dropoff_time"} <= route_cols
        hours_col = "driver_hours_worked" if "driver_hours_worked" in ccols else None
        approved_hours_col = "approved_hours" if "approved_hours" in ccols else None
        gratuity_col = (
            "approved_gratuity" if "approved_gratuity" in ccols else None
        )

        select_cols = self._pay_printout_select_cols(ccols, hours_col, approved_hours_col, gratuity_col)
        select_clause = ", ".join(select_cols)
        employee_name, driver_code = self._pay_printout_employee_identity(cur, emp_id, ecols)
        attempts = self._pay_printout_match_attempts(
            ccols,
            driver_col=self._charter_driver_column(ccols),
            employee_name=employee_name,
            driver_code=driver_code,
            emp_id=emp_id,
        )

        rows = []
        matched_by = None
        self._printout_verification_only = False
        for where_clause, where_value, label in attempts:
            cur.execute(  # nosec
                f"""
                SELECT {select_clause}
                FROM charters
                WHERE {where_clause}
                  AND charter_date BETWEEN %s AND %s
                ORDER BY charter_date
                """,
                (where_value, start, end),
            )
            rows = cur.fetchall()
            if rows:
                matched_by = label
                break

        if not rows:
            rows, matched_by = self._driver_payroll_fallback(cur, emp_id, start, end)

        return {
            "rows": rows,
            "matched_by": matched_by,
            "select_cols": select_cols,
            "hours_col": hours_col,
            "approved_hours_col": approved_hours_col,
            "gratuity_col": gratuity_col,
            "can_use_route_span": can_use_route_span,
        }

    def _pay_printout_select_cols(
        self, ccols, hours_col, approved_hours_col, gratuity_col
    ) -> list[str]:
        select_cols = [
            "charter_id",
            "charter_date",
            "reserve_number",
            "status",
        ]
        if hours_col:
            select_cols.append(hours_col)
        if approved_hours_col:
            select_cols.append(approved_hours_col)
        if gratuity_col:
            select_cols.append(gratuity_col)
        return select_cols

    def _pay_printout_employee_identity(
        self, cur, emp_id, ecols
    ) -> tuple[str | None, str | None]:
        employee_name = None
        driver_code = None
        if {"full_name", "driver_code"} <= ecols:
            cur.execute(
                """
                SELECT COALESCE(full_name, ''), COALESCE(driver_code, '')
                FROM employees
                WHERE employee_id = %s
                LIMIT 1
                """,
                (emp_id,),
            )
            emp_row = cur.fetchone()
            if emp_row:
                employee_name = (emp_row[0] or "").strip()
                driver_code = (emp_row[1] or "").strip()
        elif "full_name" in ecols:
            cur.execute(
                """
                SELECT COALESCE(full_name, '')
                FROM employees
                WHERE employee_id = %s
                LIMIT 1
                """,
                (emp_id,),
            )
            emp_row = cur.fetchone()
            if emp_row:
                employee_name = (emp_row[0] or "").strip()
        return employee_name, driver_code

    def _pay_printout_match_attempts(
        self,
        ccols,
        driver_col,
        employee_name,
        driver_code,
        emp_id,
    ) -> list[tuple[str, object, str]]:
        attempts = [(f"{driver_col} = %s", emp_id, f"{driver_col}=employee_id")]
        if driver_code and "driver" in ccols:
            attempts.append(
                (
                    "LOWER(TRIM(COALESCE(driver::text, ''))) = LOWER(TRIM(%s))",
                    driver_code,
                    "driver=driver_code",
                )
            )
        if employee_name:
            for name_col in (
                "driver_name",
                "assigned_driver_name",
                "employee_name",
                "chauffeur",
                "driver",
            ):
                if name_col in ccols:
                    attempts.append(
                        (
                            f"LOWER(TRIM(COALESCE({name_col}::text, ''))) = LOWER(TRIM(%s))",
                            employee_name,
                            f"{name_col}=employee_name",
                        )
                    )
        return attempts

    def _driver_payroll_fallback(
        self, cur, emp_id, start, end
    ) -> tuple[list[tuple], str | None]:
        dp_cols = self._get_columns("driver_payroll")
        if {"employee_id", "pay_date", "reserve_number"} <= dp_cols:
            cur.execute(
                """
                SELECT pay_date, reserve_number, COALESCE(hours_worked, 0),
                       COALESCE(gratuity_amount, 0)
                FROM driver_payroll
                WHERE employee_id = %s
                  AND pay_date BETWEEN %s AND %s
                ORDER BY pay_date, reserve_number, id
                """,
                (emp_id, start, end),
            )
            dp_rows = cur.fetchall()
            if dp_rows:
                rows = [
                    (None, pay_date, reserve_number, hours_worked, gratuity_amount)
                    for (pay_date, reserve_number, hours_worked, gratuity_amount) in dp_rows
                ]
                self._printout_verification_only = True
                return rows, "driver_payroll_fallback"
        return [], None

    def _apply_pay_printout_payload(
        self, cur, payload, emp_id, end, ecols
    ) -> None:
        rows = payload["rows"]
        matched_by = payload["matched_by"]
        select_cols = payload["select_cols"]
        hours_col = payload["hours_col"]
        approved_hours_col = payload["approved_hours_col"]
        gratuity_col = payload["gratuity_col"]
        can_use_route_span = payload["can_use_route_span"]

        self._updating_printout_table = True
        self.pay_printout_table.setRowCount(len(rows))
        total_hours_1_sum = 0.0
        total_hours_2_sum = 0.0
        total_hours_sum = 0.0
        total_gratuity = 0.0

        for r, row in enumerate(rows):
            data = dict(zip(select_cols, row, strict=False))
            payable = self._fill_pay_printout_row(
                cur,
                r,
                data,
                hours_col,
                approved_hours_col,
                gratuity_col,
                can_use_route_span,
            )
            if payable:
                total_hours_1_sum += float(
                    self.pay_printout_table.item(r, 2).text() or 0
                )
                total_hours_2_sum += float(
                    self.pay_printout_table.item(r, 3).text() or 0
                )
                total_hours_sum += float(
                    self.pay_printout_table.item(r, 2).text() or 0
                ) + float(self.pay_printout_table.item(r, 3).text() or 0)
                total_gratuity += float(
                    self.pay_printout_table.item(r, 4)
                    .text()
                    .replace("$", "")
                    .replace(",", "")
                    or 0
                )

        self._finalize_pay_printout_totals(
            total_hours_sum,
            total_hours_1_sum,
            total_hours_2_sum,
            total_gratuity,
            matched_by,
            len(rows),
        )
        self._update_pay_printout_wcb(cur, emp_id, end, ecols)

    def _fill_pay_printout_row(
        self,
        cur,
        r,
        data,
        hours_col,
        approved_hours_col,
        gratuity_col,
        can_use_route_span,
    ) -> None:
        charter_id = data.get("charter_id")
        c_date = data.get("charter_date")
        reserve = data.get("reserve_number")
        row_total_hours = 0.0
        if hours_col and data.get(hours_col) is not None:
            row_total_hours = float(data.get(hours_col) or 0.0)
        elif can_use_route_span:
            row_total_hours = self._route_span_hours_for_charter(cur, charter_id)

        raw_approved_hours = (
            data.get(approved_hours_col) if approved_hours_col else None
        )
        approved_hours = max(0.0, float(raw_approved_hours or 0.0))
        # hours_2 = any remaining hours beyond approved (only if driver_hours_worked > approved)
        hours_2 = max(0.0, row_total_hours - approved_hours)

        raw_gratuity = data.get(gratuity_col) if gratuity_col else None
        gratuity = max(0.0, float(raw_gratuity or 0.0))
        run_status = str(data.get("status") or "").strip().lower()
        is_closed = run_status == "closed"
        approval_missing = raw_approved_hours is None or raw_gratuity is None
        payable = is_closed and not approval_missing
        if run_status == "cancelled":
            status_text = "CANCELLED - excluded"
        elif not is_closed:
            status_text = "NOT CLOSED - excluded"
        elif approval_missing:
            status_text = "MISSING APPROVAL - excluded"
        else:
            status_text = "CLOSED - included"

        self.pay_printout_table.setItem(r, 0, QTableWidgetItem(str(c_date or "")))
        date_item = self.pay_printout_table.item(r, 0)
        if date_item:
            date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        reserve_item = QTableWidgetItem(str(reserve or ""))
        reserve_item.setData(Qt.ItemDataRole.UserRole, charter_id)
        reserve_item.setFlags(reserve_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.pay_printout_table.setItem(r, 1, reserve_item)
        self.pay_printout_table.setItem(r, 2, QTableWidgetItem(f"{approved_hours:.2f}"))
        self.pay_printout_table.setItem(r, 3, QTableWidgetItem(f"{hours_2:.2f}"))
        self.pay_printout_table.setItem(r, 4, QTableWidgetItem(f"${gratuity:,.2f}"))
        status_item = QTableWidgetItem(status_text)
        status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.pay_printout_table.setItem(r, 5, status_item)
        if not payable:
            warning_brush = QBrush(QColor("#b91c1c"))
            for column in range(self.pay_printout_table.columnCount()):
                item = self.pay_printout_table.item(r, column)
                if item:
                    item.setForeground(warning_brush)
        return payable

    def _finalize_pay_printout_totals(
        self,
        total_hours_sum,
        total_hours_1_sum,
        total_hours_2_sum,
        total_gratuity,
        matched_by,
        row_count,
    ) -> None:
        self.pay_printout_total_hours.setText(f"Total Hours: {total_hours_sum:.2f}")
        self.pay_printout_total_gratuity.setText(f"Total Gratuity: ${total_gratuity:,.2f}")
        self._printout_total_hours = total_hours_sum
        self._printout_total_hours_1 = total_hours_1_sum
        self._printout_total_hours_2 = total_hours_2_sum
        self._printout_total_gratuity = total_gratuity
        self._updating_printout_table = False
        if not self._printout_verification_only:
            self._sync_pay_fields_from_printout(force=False)
        self._set_pay_printout_status(matched_by, row_count)

    def _set_pay_printout_status(self, matched_by, row_count) -> None:
        if matched_by:
            if matched_by.endswith("employee_name"):
                self._set_status(f"Loaded {row_count} reserve rows (matched by employee name).", error=False)
            elif matched_by == "driver=driver_code":
                self._set_status(f"Loaded {row_count} reserve rows (matched by driver code).", error=False)
            elif matched_by == "driver_payroll_fallback":
                self._set_status(f"Loaded {row_count} reserve rows from driver payroll history (verification-only).", error=False)
            else:
                self._set_status(f"Loaded {row_count} reserve rows ({matched_by}).", error=False)

    def _update_pay_printout_wcb(self, cur, emp_id, end, ecols) -> None:
        self.pay_printout_wcb.setText("WCB (month): $0.00")
        wcols = self._get_columns("wcb_summary")
        if {"driver_id", "year", "month", "wcb_payment"} <= wcols and "employee_number" in ecols:
            cur.execute("SELECT employee_number FROM employees WHERE employee_id = %s", (emp_id,))
            emp_row = cur.fetchone()
            if emp_row and emp_row[0]:
                driver_id = emp_row[0]
                pay_month = end.month if hasattr(end, "month") else None
                pay_year = end.year if hasattr(end, "year") else None
                if pay_month and pay_year:
                    cur.execute(
                        """
                        SELECT wcb_payment
                        FROM wcb_summary
                        WHERE driver_id = %s AND year = %s AND month = %s
                        LIMIT 1
                        """,
                        (driver_id, pay_year, pay_month),
                    )
                    wcb_row = cur.fetchone()
                    if wcb_row and wcb_row[0] is not None:
                        self.pay_printout_wcb.setText(f"WCB (month): ${float(wcb_row[0]):,.2f}")

    def _persist_pay_printout_row(self, row, update_form=True) -> None:
        """Persist an edited grid row back to charters and refresh totals."""
        reserve_item = self.pay_printout_table.item(row, 1)
        charter_id = (
            reserve_item.data(Qt.ItemDataRole.UserRole)
            if reserve_item
            else None
        )
        if not charter_id:
            return

        try:
            hours_1_item = self.pay_printout_table.item(row, 2)
            hours_2_item = self.pay_printout_table.item(row, 3)
            gratuity_item = self.pay_printout_table.item(row, 4)

            hours_1 = float(
                (hours_1_item.text() if hours_1_item else "0") or "0"
            )
            hours_2 = float(
                (hours_2_item.text() if hours_2_item else "0") or "0"
            )
            gratuity_text = (
                (gratuity_item.text() if gratuity_item else "0")
                .replace("$", "")
                .replace(",", "")
            )
            gratuity = float(gratuity_text or "0")
        except ValueError:
            self._set_status(
                "Invalid Hours 1 / Hours 2 / Gratuity value.", error=True
            )
            return

        total_hours = round(max(0.0, hours_1) + max(0.0, hours_2), 2)

        ccols = self._get_columns("charters")
        set_clauses = []
        params = []

        if "driver_hours_worked" in ccols:
            set_clauses.append("driver_hours_worked = %s")
            params.append(total_hours)

        if "approved_hours" in ccols:
            set_clauses.append("approved_hours = %s")
            params.append(max(0.0, hours_1))

        if "approved_gratuity" in ccols:
            set_clauses.append("approved_gratuity = %s")
            params.append(max(0.0, gratuity))
        elif "driver_gratuity_amount" in ccols:
            set_clauses.append("driver_gratuity_amount = %s")
            params.append(max(0.0, gratuity))
        elif "driver_gratuity" in ccols:
            set_clauses.append("driver_gratuity = %s")
            params.append(max(0.0, gratuity))

        if "updated_at" in ccols:
            set_clauses.append("updated_at = NOW()")

        if set_clauses:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                params.append(charter_id)
                cur.execute(  # nosec
                    f"""
                    UPDATE charters
                    SET {', '.join(set_clauses)}
                    WHERE charter_id = %s
                    """,
                    tuple(params),
                )

        self._recalculate_printout_totals()
        self.current_charter_row = row
        if update_form:
            self._load_charter_to_form()
        self._set_status(f"Auto-updated charter row {row + 1}.", error=False)

    def _on_pay_printout_item_changed(self, item) -> None:
        """Auto-persist editable grid changes for Hours 1/Hours 2/Gratuity."""
        if self._updating_printout_table or not item:
            return
        if self._printout_verification_only:
            return
        if item.column() not in (2, 3, 4):
            return

        # Keep top payroll totals stable; do not load one edited row into the
        # form.
        self._persist_pay_printout_row(item.row(), update_form=False)

    def _load_charter_to_form(self) -> None:
        """Track selected charter row without mutating payroll form fields."""
        if self._printout_verification_only:
            QMessageBox.information(
                self,
                TITLE_VERIFICATION_ONLY,
                "These rows are loaded from driver payroll history for"
                "verification only."

                " Payroll values remain separate and should be entered in the"
                "payroll fields above.",

            )
            return

        current_row = self.pay_printout_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(
                self, "No Selection", "Select a charter row to edit."
            )
            return

        self.current_charter_row = current_row
        self._set_status(
            f"✏️ Selected charter row {current_row + 1}. Edit Hours 1/Hours"
            f"2/Gratuity in the grid, then click 'Update Charter' (or just"
            f"edit inline to auto-save).",


            error=False,
        )

    def _update_charter_from_form(self) -> None:
        """Persist the selected charter grid row without using payroll form"
        "fields."""

        if self._printout_verification_only:
            QMessageBox.information(
                self,
                TITLE_VERIFICATION_ONLY,
                "These rows are verification-only and cannot be edited.",
            )
            return

        if self.current_charter_row < 0:
            QMessageBox.warning(
                self,
                "No Charter Selected",
                "Load a charter first by clicking 'Edit Selected'.",
            )
            return

        row = self.current_charter_row
        try:
            self._persist_pay_printout_row(row, update_form=False)
        except Exception as exc:
            logger.exception("Failed to persist charter row %s", row)
            self._set_status(
                f"Updated row in payroll view but failed DB save: {exc}",
                error=True,
            )
            return

        self._set_status(f"✅ Updated charter row {row + 1}.", error=False)
        self.current_charter_row = -1

    def _remove_charter_row(self) -> None:
        """Remove the currently selected charter row."""
        if self._printout_verification_only:
            QMessageBox.information(
                self,
                TITLE_VERIFICATION_ONLY,
                "These rows are verification-only and cannot be deleted.",
            )
            return

        current_row = self.pay_printout_table.currentRow()
        if current_row >= 0:
            self.pay_printout_table.removeRow(current_row)
            self._recalculate_printout_totals()
            if self.current_charter_row == current_row:
                self.current_charter_row = -1
        else:
            QMessageBox.warning(
                self, "No Selection", "Select a row to delete."
            )

    def _recalculate_printout_totals(self) -> None:
        """Recalculate totals from the pay_printout_table."""
        total_hours = 0.0
        total_hours_1 = 0.0
        total_hours_2 = 0.0
        total_gratuity = 0.0
        for row in range(self.pay_printout_table.rowCount()):
            try:
                hours_text = (
                    self.pay_printout_table.item(row, 2).text()
                    if self.pay_printout_table.item(row, 2)
                    else "0"
                )
                hours_2_text = (
                    self.pay_printout_table.item(row, 3).text()
                    if self.pay_printout_table.item(row, 3)
                    else "0"
                )
                gratuity_text = (
                    self.pay_printout_table.item(row, 4).text()
                    if self.pay_printout_table.item(row, 4)
                    else "0"
                )
                hours = (
                    float(hours_text.replace(",", "")) if hours_text else 0.0
                )
                hours_2 = (
                    float(hours_2_text.replace(",", ""))
                    if hours_2_text
                    else 0.0
                )
                gratuity_str = gratuity_text.replace("$", "").replace(",", "")
                gratuity = float(gratuity_str) if gratuity_str else 0.0
                total_hours += hours + hours_2
                total_hours_1 += hours
                total_hours_2 += hours_2
                total_gratuity += gratuity
            except (ValueError, AttributeError):
                pass
        self.pay_printout_total_hours.setText(
            f"Total Hours: {total_hours:.2f}"
        )
        self.pay_printout_total_gratuity.setText(
            f"Total Gratuity: ${total_gratuity:,.2f}"
        )
        self._printout_total_hours = total_hours
        self._printout_total_hours_1 = total_hours_1
        self._printout_total_hours_2 = total_hours_2
        self._printout_total_gratuity = total_gratuity
        if not self._printout_verification_only:
            self._sync_pay_fields_from_printout(force=False)

    def _load_monthly_remittance_summary(self) -> None:
        """Aggregate monthly deductions for PD7A-style confirmation."""
        pay_period = self._selected_pay_period()
        if not pay_period:
            return

        _, _, _, _, _, pay_date = pay_period
        if not pay_date:
            return

        try:
            month = pay_date.month
            year = pay_date.year
            self.pd7a_month_label.setText(f"{year}-{month:02d}")
            pay_master_columns = self._get_columns("employee_pay_master")
            cpp_employer_sum_expr = (
                "SUM(cpp_employer)"
                if "cpp_employer" in pay_master_columns
                else "SUM(COALESCE(cpp_employee, 0))"
            )
            ei_employer_sum_expr = (
                "SUM(ei_employer)"
                if "ei_employer" in pay_master_columns
                else "SUM(ROUND(COALESCE(ei_employee, 0) * 1.4, 2))"
            )

            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT pay_period_id
                    FROM pay_periods
                    WHERE EXTRACT(YEAR FROM pay_date) = %s
                      AND EXTRACT(MONTH FROM pay_date) = %s
                    """,
                    (year, month),
                )
                period_ids = [row[0] for row in cur.fetchall()]
                if not period_ids:
                    return

                cur.execute(  # nosec
                    f"""
                    SELECT
                        SUM(gross_pay) as gross,
                        SUM(cpp_employee) as cpp_employee,
                        {cpp_employer_sum_expr} as cpp_employer,
                        SUM(ei_employee) as ei_employee,
                        {ei_employer_sum_expr} as ei_employer,
                        SUM(federal_tax) as federal,
                        SUM(provincial_tax) as provincial,
                        SUM(total_deductions) as total_deductions,
                        SUM(net_pay) as net_pay
                    FROM employee_pay_master
                    WHERE pay_period_id = ANY(%s)
                    """,
                    (period_ids,),
                )
                row = cur.fetchone() or (0, 0, 0, 0, 0, 0, 0, 0, 0)
                (
                    gross,
                    cpp_employee,
                    cpp_employer,
                    ei_employee,
                    ei_employer,
                    federal,
                    provincial,
                    total_deductions,
                    net_pay,
                ) = row

                self.pd7a_gross.setText(f"${float(gross or 0):,.2f}")
                self.pd7a_cpp_employee.setText(
                    f"${float(cpp_employee or 0):,.2f}"
                )
                self.pd7a_cpp_employer.setText(
                    f"${float(cpp_employer or 0):,.2f}"
                )
                self.pd7a_ei_employee.setText(
                    f"${float(ei_employee or 0):,.2f}"
                )
                self.pd7a_ei_employer.setText(
                    f"${float(ei_employer or 0):,.2f}"
                )
                self.pd7a_federal.setText(f"${float(federal or 0):,.2f}")
                self.pd7a_provincial.setText(f"${float(provincial or 0):,.2f}")
                self.pd7a_total_deductions.setText(
                    f"${float(total_deductions or 0):,.2f}"
                )
                self.pd7a_net.setText(f"${float(net_pay or 0):,.2f}")

                # WCB summary for month
                self.pd7a_wcb.setText("$0.00")
                wcols = self._get_columns("wcb_summary")
                if {"year", "month", "wcb_payment"} <= wcols:
                    cur.execute(
                        """
                        SELECT SUM(wcb_payment)
                        FROM wcb_summary
                        WHERE year = %s AND month = %s
                        """,
                        (year, month),
                    )
                    wcb_row = cur.fetchone()
                    if wcb_row and wcb_row[0] is not None:
                        self.pd7a_wcb.setText(f"${float(wcb_row[0]):,.2f}")
        except Exception as exc:
            logger.exception("Failed to load monthly remittance")
            self._set_status(
                f"Failed to load monthly remittance: {exc}", error=True
            )

    @pyqtSlot()
    def print_pd7a_summary(self) -> None:
        """Generate a printable PD7A-style monthly remittance summary."""

        import os

        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.units import inch
            from reportlab.pdfgen import canvas
        except Exception:
            QMessageBox.critical(
                self,
                TITLE_MISSING_DEPENDENCY,
                "reportlab is required to print the PD7A summary.",
            )
            return

        selection = self._get_save_selection(silent=False)
        if not selection:
            return
        _, pay_period = selection

        pay_date = pay_period[5]
        if not pay_date:
            QMessageBox.warning(
                self,
                "Missing Pay Date",
                "The selected pay period has no pay date.",
            )
            return

        # Refresh labels from DB before printing to avoid stale totals.
        self._load_monthly_remittance_summary()

        month = int(pay_date.month)
        year = int(pay_date.year)
        output_filename = f"PD7A_Summary_{year}_{month:02d}.pdf"
        output_path = _APP_ROOT / output_filename

        summary_lines = [
            ("Total Gross (T4-14)", self.pd7a_gross.text()),
            ("Federal Tax (T4-22)", self.pd7a_federal.text()),
            ("Provincial Tax (T4-22)", self.pd7a_provincial.text()),
            ("CPP Employee (T4-16)", self.pd7a_cpp_employee.text()),
            ("CPP Employer (1:1)", self.pd7a_cpp_employer.text()),
            ("EI Employee (T4-18)", self.pd7a_ei_employee.text()),
            ("EI Employer (140%)", self.pd7a_ei_employer.text()),
            (LABEL_TOTAL_DEDUCTIONS, self.pd7a_total_deductions.text()),
            (LABEL_NET_PAY, self.pd7a_net.text()),
            ("WCB (Month)", self.pd7a_wcb.text()),
        ]

        try:
            c = canvas.Canvas(str(output_path), pagesize=letter)
            width, height = letter
            left = 0.75 * inch
            right = width - 0.75 * inch
            y = height - 0.8 * inch

            c.setFont("Helvetica-Bold", 16)
            c.drawString(left, y, "PD7A Monthly Remittance Summary")
            y -= 0.32 * inch

            c.setFont("Helvetica", 10)
            c.drawString(left, y, f"Month: {year}-{month:02d}")
            y -= 0.2 * inch
            c.drawString(
                left,
                y,
                f"Selected Pay Date: {pay_date.isoformat()}",
            )
            y -= 0.2 * inch
            c.drawString(left, y, f"Generated: {date.today().isoformat()}")
            y -= 0.3 * inch

            c.setLineWidth(0.8)
            c.line(left, y, right, y)
            y -= 0.22 * inch

            label_x = left
            value_x = right
            c.setFont("Helvetica", 10)
            for label, value in summary_lines:
                if y < 1.0 * inch:
                    c.showPage()
                    y = height - 0.8 * inch
                    c.setFont("Helvetica", 10)
                c.drawString(label_x, y, label)
                c.drawRightString(value_x, y, value)
                y -= 0.22 * inch

            y -= 0.14 * inch
            c.setFont("Helvetica-Oblique", 8)
            c.drawString(
                left,
                y,
                "This is a payroll remittance summary view to support monthly filing review.",
            )
            y -= 0.14 * inch
            c.drawString(
                left,
                y,
                "Review source payroll rows before submitting any statutory remittance.",
            )
            c.save()

            self._set_status(f"PD7A summary generated: {output_filename}")
            if os.path.exists(output_path):
                self._open_generated_file(output_path)
        except Exception as exc:
            logger.exception("PD7A summary generation error")
            self._set_status(
                f"PD7A summary generation error: {exc}", error=True
            )

    def _autofill_from_charters(self) -> None:
        """Pull hours + gratuity from charters for the selected pay period,
        then auto-calculate CPP / EI / income tax so the record is ready to
        review and save with one click."""

        emp_id = self._selected_employee_id()
        pay_period = self._selected_pay_period()
        if not emp_id or not pay_period:
            QMessageBox.warning(
                self,
                TITLE_MISSING_SELECTION,
                MSG_SELECT_EMPLOYEE_AND_PERIOD,
            )
            return

        try:
            # Step 1: reload charter rows and push Hours 1 / Hours 2 /
            # Gratuity into the payroll form fields (force=True overrides any
            # previous value).
            self._load_pay_printout()
            self._sync_pay_fields_from_printout(force=True)
            self._apply_selected_work_items_to_payroll()

            # Step 2: auto-calculate CPP, EI, federal and provincial tax from
            # CRA brackets so the entry is complete on one click.
            # Force fresh tax computation for the currently selected employee
            # to avoid carrying over prior employee tax amounts.
            self._apply_calculated_deductions_to_pay(
                preserve_existing_tax=False
            )

            self._set_status(
                "✅ Closed-run approved hours/gratuity and non-charter work"
                " loaded from live data; deductions calculated."
                " Review and Save."
            )
        except Exception as exc:
            self._set_status(f"Auto-fill failed: {exc}", error=True)

    def _apply_selected_work_items_to_payroll(self) -> None:
        """Include current-period non-charter work in a live payroll refresh."""
        emp_id = self._selected_employee_id()
        pay_period = self._selected_pay_period()
        if not emp_id or not pay_period:
            return
        summary = get_work_item_summary(
            self.db,
            int(emp_id),
            pay_period_id=int(pay_period[0]),
            fiscal_year=int(self.year_combo.currentText()),
        )
        self.other_income.setValue(round(summary.payable_income, 2))
        self.reimbursements.setValue(round(summary.reimbursements, 2))
        self._refresh_work_item_summary()

    def _ensure_pay_events_table(self) -> None:
        with DatabaseContext(self.db, auto_commit=True) as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS employee_pay_events (
                    pay_event_id SERIAL PRIMARY KEY,
                    employee_id INT NOT NULL,
                    pay_period_id INT,
                    event_type VARCHAR(50) NOT NULL,
                    event_date DATE NOT NULL,
                    amount DECIMAL(12,2),
                    reference VARCHAR(100),
                    notes TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW())
                """)

    @pyqtSlot()
    def save_pay_event(self) -> None:
        emp_id = self._selected_employee_id()
        pay_period = self._selected_pay_period()
        if not emp_id:
            QMessageBox.warning(
                self, TITLE_MISSING_SELECTION, MSG_SELECT_EMPLOYEE
            )
            return

        try:
            self._ensure_pay_events_table()
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO employee_pay_events (
                        employee_id, pay_period_id, event_type, event_date,
                        amount, reference, notes) VALUES (%s, %s, %s, %s, %s,
                        %s, %s)
                    """,
                    (
                        emp_id,
                        pay_period[0] if pay_period else None,
                        self.pay_event_type.currentText(),
                        self.pay_event_date.date().toPyDate(),
                        (
                            float(self.pay_event_amount.value())
                            if self.pay_event_amount.value()
                            else None
                        ),
                        self.pay_event_reference.text().strip() or None,
                        self.pay_event_notes.toPlainText().strip() or None,
                    ),
                )
                self._set_status("Pay event saved.")
        except Exception as exc:
            logger.exception("Failed to save pay event")
            self._set_status(f"Failed to save pay event: {exc}", error=True)

    @pyqtSlot()
    def save_hiring_info(self) -> None:
        emp_id = self._selected_employee_id()
        if not emp_id:
            QMessageBox.warning(
                self, TITLE_MISSING_SELECTION, MSG_SELECT_EMPLOYEE
            )
            return

        try:
            ecols = self._get_columns("employees")
            updates = []
            params = []

            if "hire_date" in ecols:
                updates.append("hire_date = %s")
                params.append(self.hire_date_input.date().toPyDate())
            if "position" in ecols:
                updates.append("position = %s")
                params.append(self.position_input.text().strip() or None)
            if "hourly_rate" in ecols:
                updates.append("hourly_rate = %s")
                params.append(float(self.hourly_rate_input.value()) or None)
            if "salary" in ecols:
                updates.append("salary = %s")
                params.append(float(self.annual_salary_input.value()) or None)
            if "employment_status" in ecols:
                updates.append("employment_status = %s")
                params.append(self.employment_status_input.currentText())

            if not updates:
                QMessageBox.warning(
                    self,
                    "Missing Columns",
                    "Employee table does not have hire/position/rate fields.",
                )
                return

            params.append(emp_id)
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(  # nosec
                    f"UPDATE employees SET {', '.join(updates)} WHERE "
                    f"employee_id = %s",

                    tuple(params),
                )
                self._set_status("Hiring info saved to employee record.")
        except Exception as exc:
            logger.exception("Failed to save hiring info")
            self._set_status(f"Failed to save hiring info: {exc}", error=True)

    @pyqtSlot()
    def print_official_t4(self) -> None:
        """Generate official CRA T4 form for selected employee/year."""

        # Import T4 form filler
        try:
            from t4_official_form_filler import (
                T4OfficialFormFiller,
            )
        except ImportError:
            QMessageBox.critical(
                self, "Import Error", "T4 form filler module not found."
            )
            return

        # Load employer details from company_info table (falls back to defaults)
        T4OfficialFormFiller.load_employer_from_db(self.db)

        emp_id = self._selected_employee_id()
        if not emp_id:
            QMessageBox.warning(self, TITLE_MISSING_SELECTION, MSG_SELECT_EMPLOYEE)
            return

        try:
            tax_year = int(self.year_combo.currentText())
        except (ValueError, AttributeError):
            QMessageBox.warning(self, "Missing Year", "Select a valid tax year first.")
            return

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                ecols = self._get_columns("employees")
                employee_data = self._load_t4_official_employee(cur, emp_id, ecols)
                if not employee_data:
                    QMessageBox.warning(
                        self, "Employee Not Found", f"Employee ID {emp_id} not found."
                    )
                    return

                data_issues = self._build_t4_official_data_issues(employee_data)
                if data_issues:
                    issue_text = "\n".join(f"- {issue} " for issue in data_issues)
                    QMessageBox.critical(
                        self,
                        "T4 Print Blocked: Missing Employee Data",
                        f"Cannot print official T4 for"
                        f"{employee_data['full_name'] or 'selected employee'}"
                        f".\n\nPlease update employee payroll profile fields"
                        f"first:\n{issue_text}",
                    )
                    return

                pay_master_columns = self._get_columns("employee_pay_master")
                if not pay_master_columns:
                    QMessageBox.warning(
                        self,
                        "Missing Data",
                        "employee_pay_master columns could not be loaded.",
                    )
                    return
                t4_row = self._load_t4_official_summary(cur, emp_id, tax_year, pay_master_columns)
                payroll_rows = int(t4_row[7] or 0)
                period_count = int(t4_row[8] or 0)
                manual_override = self._load_t4_manual_override(
                    cur, emp_id, tax_year
                )
                has_manual_override = manual_override is not None

                if payroll_rows == 0 and not has_manual_override:
                    QMessageBox.warning(
                        self,
                        "No Payroll Data",
                        f"No employee_pay_master rows found for {tax_year}.\nT4 cannot be generated until payroll data exists for that year.",
                    )
                    return

                if period_count <= 1 and not has_manual_override:
                    reply = QMessageBox.warning(
                        self,
                        "Limited Year Coverage Detected",
                        f"Only {period_count} pay period appears loaded for"
                        f" {tax_year} ({payroll_rows} payroll row(s)).\n\n"
                        f"T4 will include only loaded year-to-date data, which can look like January-only totals.\n\n"
                        f"Continue printing anyway?",
                        QMessageBox.StandardButton.Yes
                        | QMessageBox.StandardButton.No,
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return

                t4_data = {
                    "box14": float(t4_row[0]),  # Employment Income
                    "box16": float(t4_row[1]),  # CPP Employee
                    "box18": float(t4_row[2]),  # EI Employee
                    "box22": float(t4_row[3]),  # Income Tax
                    "box24": float(t4_row[4]),  # EI Insurable
                    "box26": float(t4_row[5]),  # CPP Pensionable
                    "box44": float(t4_row[6]),  # Union Dues
                    "box52": 0.0,  # Pension Adjustment (not tracked)
                }
                if has_manual_override:
                    t4_data.update(manual_override)
                    self._set_status(
                        "Using saved manual T4 override for official print."
                    )

            self._generate_official_t4_pdf(
                T4OfficialFormFiller,
                employee_data,
                t4_data,
                tax_year,
            )

        except Exception as exc:
            logger.exception("T4 generation error")
            self._set_status(f"T4 generation error: {exc}", error=True)
            import traceback

            traceback.print_exc()

    def _generate_official_t4_pdf(
        self,
        filler_cls,
        employee_data: dict,
        t4_data: dict,
        tax_year: int,
    ) -> None:
        import os

        filler = filler_cls()
        emp_name_safe = employee_data["full_name"].replace(" ", "_").replace("/", "-")
        output_filename = f"T4_{tax_year}_{emp_name_safe}_EMPLOYEE.pdf"
        output_path = _APP_ROOT / output_filename

        result = filler.fill_t4_form(
            employee_data,
            t4_data,
            tax_year,
            str(output_path),
            format_type="employee",
        )

        if result:
            self._set_status(f"T4 generated (employee copy): {output_filename}")
            if os.path.exists(output_path):
                self._open_generated_file(output_path)
        else:
            self._set_status("T4 generation failed.", error=True)

    def _open_generated_file(self, output_path: Path) -> None:
        """Open generated files with platform-appropriate launcher safely."""
        path_str = str(output_path)
        try:
            url = QUrl.fromLocalFile(path_str)
            if not QDesktopServices.openUrl(url):
                logger.warning("Could not open generated file %s", path_str)
        except Exception as exc:
            logger.warning("Could not open generated file %s: %s", path_str, exc)

    def _t4_official_employee_exprs(
        self, ecols: set[str]
    ) -> tuple[str, str, str, str, str, str, str, str]:
        if "full_name" in ecols:
            full_name_expr = "COALESCE(full_name, '')"
        elif "employee_name" in ecols:
            full_name_expr = "COALESCE(employee_name, '')"
        elif {"first_name", "last_name"} <= ecols:
            full_name_expr = (
                "TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, ''))"
            )
        elif "first_name" in ecols:
            full_name_expr = "COALESCE(first_name, '')"
        elif "last_name" in ecols:
            full_name_expr = "COALESCE(last_name, '')"
        else:
            full_name_expr = "''"

        first_name_expr = "COALESCE(first_name, '')" if "first_name" in ecols else "''"
        last_name_expr = "COALESCE(last_name, '')" if "last_name" in ecols else "''"
        sin_expr = "COALESCE(t4_sin, '')" if "t4_sin" in ecols else "COALESCE(sin, '')" if "sin" in ecols else "''"
        address_expr = "COALESCE(street_address, '')" if "street_address" in ecols else "COALESCE(address, '')" if "address" in ecols else "''"
        city_expr = "COALESCE(city, '')" if "city" in ecols else "''"
        province_expr = "COALESCE(province, '')" if "province" in ecols else "''"
        postal_expr = "COALESCE(postal_code, '')" if "postal_code" in ecols else "''"
        return (
            full_name_expr,
            first_name_expr,
            last_name_expr,
            sin_expr,
            address_expr,
            city_expr,
            province_expr,
            postal_expr,
        )

    def _load_t4_official_employee(
        self, cur, emp_id: int, ecols: set[str]
    ) -> dict[str, str] | None:
        (
            full_name_expr,
            first_name_expr,
            last_name_expr,
            sin_expr,
            address_expr,
            city_expr,
            province_expr,
            postal_expr,
        ) = self._t4_official_employee_exprs(ecols)

        cur.execute(  # nosec
            f"""
            SELECT
                {full_name_expr} AS full_name,
                {first_name_expr} AS first_name,
                {last_name_expr} AS last_name,
                {sin_expr} AS sin,
                {address_expr} AS address,
                {city_expr} AS city,
                {province_expr} AS province,
                {postal_expr} AS postal_code
            FROM employees
            WHERE employee_id = %s
            """,
            (emp_id,),
        )
        emp_row = cur.fetchone()
        if not emp_row:
            return None

        return {
            "full_name": emp_row[0] or "",
            "first_name": emp_row[1] or "",
            "last_name": emp_row[2] or "",
            "sin": emp_row[3] or "",
            "address": emp_row[4] or "",
            "city": emp_row[5] or "",
            "province": emp_row[6] or "AB",
            "postal_code": emp_row[7] or "",
        }

    def _build_t4_official_data_issues(
        self, employee_data: dict
    ) -> list[str]:
        sin_digits = "".join(ch for ch in employee_data["sin"] if ch.isdigit())
        data_issues = []
        if len(sin_digits) != 9:
            data_issues.append("SIN must contain exactly 9 digits.")
        if not (employee_data["address"] or "").strip():
            data_issues.append("Street address is missing.")
        if not (employee_data["city"] or "").strip():
            data_issues.append("City is missing.")
        if not (employee_data["province"] or "").strip():
            data_issues.append("Province is missing.")
        if not (employee_data["postal_code"] or "").strip():
            data_issues.append("Postal code is missing.")
        return data_issues

    def _t4_official_paymaster_exprs(
        self, pay_master_columns: set[str]
    ) -> tuple[str, str, str, str, str]:
        taxable_gross_sum_expr = (
            "COALESCE(SUM(GREATEST(COALESCE(gross_pay, 0) - COALESCE(reimbursements, 0), 0)), 0)"
            if "reimbursements" in pay_master_columns
            else "COALESCE(SUM(gross_pay), 0)"
        )
        ei_insurable_expr = (
            "COALESCE(SUM(ei_insurable), 0)"
            if "ei_insurable" in pay_master_columns
            else taxable_gross_sum_expr
        )
        cpp_pensionable_expr = (
            "COALESCE(SUM(cpp_pensionable), 0)"
            if "cpp_pensionable" in pay_master_columns
            else taxable_gross_sum_expr
        )
        income_tax_expr = (
            "COALESCE(SUM(total_income_tax), 0)"
            if "total_income_tax" in pay_master_columns
            else "COALESCE(SUM(COALESCE(federal_tax, 0) + COALESCE(provincial_tax, 0)), 0)"
        )
        union_dues_expr = (
            "COALESCE(SUM(union_dues), 0)"
            if "union_dues" in pay_master_columns
            else "0::numeric"
        )
        return (
            taxable_gross_sum_expr,
            ei_insurable_expr,
            cpp_pensionable_expr,
            income_tax_expr,
            union_dues_expr,
        )

    def _load_t4_official_summary(
        self,
        cur,
        emp_id: int,
        tax_year: int,
        pay_master_columns: set[str],
    ) -> tuple:
        (
            taxable_gross_sum_expr,
            ei_insurable_expr,
            cpp_pensionable_expr,
            income_tax_expr,
            union_dues_expr,
        ) = self._t4_official_paymaster_exprs(pay_master_columns)

        cur.execute(  # nosec
            f"""
            SELECT
                {taxable_gross_sum_expr} as box14,
                COALESCE(SUM(cpp_employee), 0) as box16,
                COALESCE(SUM(ei_employee), 0) as box18,
                {income_tax_expr} as box22,
                {ei_insurable_expr} as box24,
                {cpp_pensionable_expr} as box26,
                {union_dues_expr} as box44,
                COUNT(*) as payroll_rows,
                COUNT(DISTINCT pay_period_id) as period_count
            FROM employee_pay_master
            WHERE employee_id = %(emp_id)s AND fiscal_year = %(fiscal_year)s
            """,
            {"emp_id": emp_id, "fiscal_year": tax_year},
        )
        return cur.fetchone()

    def _t4_value_keys(self) -> tuple[str, ...]:
        return (
            "box14",
            "box16",
            "box18",
            "box22",
            "box24",
            "box26",
            "box44",
            "box46",
            "box52",
        )

    def _is_value_match(self, left: float, right: float) -> bool:
        return abs(float(left) - float(right)) < 0.005

    def _format_money_value(self, value: float) -> str:
        return f"${float(value):,.2f}"

    def _refresh_t4_override_status(self) -> None:
        if not hasattr(self, "t4_override_status_label"):
            return

        emp_id = self._selected_employee_id()
        if not emp_id:
            self.t4_override_status_label.setText(
                "T4 override status: select employee and year."
            )
            self.t4_override_status_label.setStyleSheet(
                "color: #6b7280; font-weight: bold;"
            )
            return

        try:
            tax_year = int(self.year_combo.currentText())
        except (ValueError, AttributeError):
            self.t4_override_status_label.setText(
                "T4 override status: missing year selection."
            )
            self.t4_override_status_label.setStyleSheet(
                "color: #b45309; font-weight: bold;"
            )
            return

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                pay_master_columns = self._get_columns("employee_pay_master")
                t4_row = self._load_t4_official_summary(
                    cur, emp_id, tax_year, pay_master_columns
                )
                actual_values = {
                    "box14": float(t4_row[0] or 0),
                    "box16": float(t4_row[1] or 0),
                    "box18": float(t4_row[2] or 0),
                    "box22": float(t4_row[3] or 0),
                    "box24": float(t4_row[4] or 0),
                    "box26": float(t4_row[5] or 0),
                    "box44": float(t4_row[6] or 0),
                    "box46": 0.0,
                    "box52": 0.0,
                }
                manual_override = self._load_t4_manual_override(
                    cur, emp_id, tax_year
                )

            if not manual_override:
                self.t4_override_status_label.setText(
                    f"T4 override status ({tax_year}): no manual override"
                    " saved."
                )
                self.t4_override_status_label.setStyleSheet(
                    "color: #1f2937; font-weight: bold;"
                )
                return

            confirmed = bool(manual_override.get("source_of_truth_confirmed"))
            confirmed_by = manual_override.get("source_of_truth_confirmed_by", "")
            confirmed_at = manual_override.get("source_of_truth_confirmed_at")

            mismatched_boxes = []
            for key in self._t4_value_keys():
                manual_value = float(manual_override.get(key, 0) or 0)
                actual_value = float(actual_values.get(key, 0) or 0)
                if not self._is_value_match(manual_value, actual_value):
                    mismatched_boxes.append(key.replace("box", "Box "))

            if not mismatched_boxes:
                msg = f"T4 override status ({tax_year}): active and matches payroll data."
                if confirmed:
                    msg += " Confirmed as source of truth."
                if confirmed_by:
                    msg += f" By {confirmed_by}."
                if confirmed_at:
                    msg += f" At {confirmed_at}."
                self.t4_override_status_label.setText(msg)
                self.t4_override_status_label.setStyleSheet(
                    "color: #065f46; font-weight: bold;"
                )
            else:
                msg = (
                    f"T4 override status ({tax_year}): active and differs"
                    f" from payroll data in {', '.join(mismatched_boxes)}."
                )
                if confirmed:
                    msg += " Confirmed source of truth needs fix."
                self.t4_override_status_label.setText(msg)
                self.t4_override_status_label.setStyleSheet(
                    "color: #b91c1c; font-weight: bold;"
                )

        except Exception as exc:
            logger.warning("T4 override status refresh failed: %s", exc)
            self.t4_override_status_label.setText(
                "T4 override status: unavailable."
            )
            self.t4_override_status_label.setStyleSheet(
                "color: #b45309; font-weight: bold;"
            )

    def _table_exists(self, cur, table_name: str) -> bool:
        cur.execute(
            """
            SELECT EXISTS(
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
            )
            """,
            (table_name,),
        )
        return bool(cur.fetchone()[0])

    def _ensure_legacy_t4_table(self, cur) -> None:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS t4_entries (
                correction_id SERIAL PRIMARY KEY,
                employee_id INT NOT NULL,
                tax_year INT NOT NULL,
                t4_box_14 NUMERIC(12, 2) DEFAULT 0,
                t4_box_16 NUMERIC(12, 2) DEFAULT 0,
                t4_box_18 NUMERIC(12, 2) DEFAULT 0,
                t4_box_22 NUMERIC(12, 2) DEFAULT 0,
                t4_box_24 NUMERIC(12, 2) DEFAULT 0,
                t4_box_26 NUMERIC(12, 2) DEFAULT 0,
                t4_box_44 NUMERIC(12, 2) DEFAULT 0,
                t4_box_46 NUMERIC(12, 2) DEFAULT 0,
                t4_box_52 NUMERIC(12, 2) DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(employee_id, tax_year)
            )
            """
        )

    def _ensure_t4_review_columns(self, cur) -> None:
        for table_name in ("t4_entries", "employee_t4_records"):
            if not self._table_exists(cur, table_name):
                continue
            cur.execute(
                f"""
                ALTER TABLE {table_name}
                ADD COLUMN IF NOT EXISTS source_of_truth_confirmed BOOLEAN DEFAULT FALSE
                """
            )
            cur.execute(
                f"""
                ALTER TABLE {table_name}
                ADD COLUMN IF NOT EXISTS source_of_truth_confirmed_at TIMESTAMPTZ
                """
            )
            cur.execute(
                f"""
                ALTER TABLE {table_name}
                ADD COLUMN IF NOT EXISTS source_of_truth_confirmed_by TEXT
                """
            )
            cur.execute(
                f"""
                ALTER TABLE {table_name}
                ADD COLUMN IF NOT EXISTS source_of_truth_variance_note TEXT
                """
            )

    def _load_t4_manual_override(
        self, cur, emp_id: int, tax_year: int
    ) -> dict[str, float] | None:
        self._ensure_t4_review_columns(cur)
        if self._table_exists(cur, "t4_entries"):
            cur.execute(
                """
                SELECT
                    COALESCE(t4_box_14, 0),
                    COALESCE(t4_box_16, 0),
                    COALESCE(t4_box_18, 0),
                    COALESCE(t4_box_22, 0),
                    COALESCE(t4_box_24, 0),
                    COALESCE(t4_box_26, 0),
                    COALESCE(t4_box_44, 0),
                    COALESCE(t4_box_46, 0),
                    COALESCE(t4_box_52, 0),
                    COALESCE(notes, ''),
                    COALESCE(source_of_truth_confirmed, FALSE),
                    source_of_truth_confirmed_at,
                    COALESCE(source_of_truth_confirmed_by, ''),
                    COALESCE(source_of_truth_variance_note, '')
                FROM t4_entries
                WHERE employee_id = %s AND tax_year = %s
                """,
                (emp_id, tax_year),
            )
            row = cur.fetchone()
            if row:
                return {
                    "box14": float(row[0] or 0),
                    "box16": float(row[1] or 0),
                    "box18": float(row[2] or 0),
                    "box22": float(row[3] or 0),
                    "box24": float(row[4] or 0),
                    "box26": float(row[5] or 0),
                    "box44": float(row[6] or 0),
                    "box46": float(row[7] or 0),
                    "box52": float(row[8] or 0),
                    "notes": row[9] or "",
                    "source_of_truth_confirmed": bool(row[10]),
                    "source_of_truth_confirmed_at": row[11],
                    "source_of_truth_confirmed_by": row[12] or "",
                    "source_of_truth_variance_note": row[13] or "",
                }

        if self._table_exists(cur, "employee_t4_records"):
            cur.execute(
                """
                SELECT
                    COALESCE(box_14_employment_income, 0),
                    COALESCE(box_16_cpp_contributions, 0),
                    COALESCE(box_18_ei_premiums, 0),
                    COALESCE(box_22_income_tax, 0),
                    COALESCE(box_24_ei_insurable_earnings, 0),
                    COALESCE(box_26_cpp_pensionable_earnings, 0),
                    COALESCE(box_44_union_dues, 0),
                    COALESCE(box_46_charitable_donations, 0),
                    COALESCE(box_52_pension_adjustment, 0),
                    COALESCE(notes, ''),
                    COALESCE(source_of_truth_confirmed, FALSE),
                    source_of_truth_confirmed_at,
                    COALESCE(source_of_truth_confirmed_by, ''),
                    COALESCE(source_of_truth_variance_note, '')
                FROM employee_t4_records
                WHERE employee_id = %s AND tax_year = %s
                """,
                (emp_id, tax_year),
            )
            row = cur.fetchone()
            if row:
                return {
                    "box14": float(row[0] or 0),
                    "box16": float(row[1] or 0),
                    "box18": float(row[2] or 0),
                    "box22": float(row[3] or 0),
                    "box24": float(row[4] or 0),
                    "box26": float(row[5] or 0),
                    "box44": float(row[6] or 0),
                    "box46": float(row[7] or 0),
                    "box52": float(row[8] or 0),
                    "notes": row[9] or "",
                    "source_of_truth_confirmed": bool(row[10]),
                    "source_of_truth_confirmed_at": row[11],
                    "source_of_truth_confirmed_by": row[12] or "",
                    "source_of_truth_variance_note": row[13] or "",
                }

        return None

    def _upsert_t4_manual_override(
        self,
        cur,
        emp_id: int,
        tax_year: int,
        values: dict[str, float],
        notes: str,
        confirmed: bool = False,
        confirmed_by: str | None = None,
        variance_note: str = "",
    ) -> None:
        self._ensure_t4_review_columns(cur)
        if self._table_exists(cur, "t4_entries"):
            cur.execute(
                """
                INSERT INTO t4_entries (
                    employee_id,
                    tax_year,
                    t4_box_14,
                    t4_box_16,
                    t4_box_18,
                    t4_box_22,
                    t4_box_24,
                    t4_box_26,
                    t4_box_44,
                    t4_box_46,
                    t4_box_52,
                    notes,
                    source_of_truth_confirmed,
                    source_of_truth_confirmed_at,
                    source_of_truth_confirmed_by,
                    source_of_truth_variance_note,
                    created_at,
                    updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, NOW(), NOW()
                )
                ON CONFLICT (employee_id, tax_year)
                DO UPDATE SET
                    t4_box_14 = EXCLUDED.t4_box_14,
                    t4_box_16 = EXCLUDED.t4_box_16,
                    t4_box_18 = EXCLUDED.t4_box_18,
                    t4_box_22 = EXCLUDED.t4_box_22,
                    t4_box_24 = EXCLUDED.t4_box_24,
                    t4_box_26 = EXCLUDED.t4_box_26,
                    t4_box_44 = EXCLUDED.t4_box_44,
                    t4_box_46 = EXCLUDED.t4_box_46,
                    t4_box_52 = EXCLUDED.t4_box_52,
                    notes = EXCLUDED.notes,
                    source_of_truth_confirmed = EXCLUDED.source_of_truth_confirmed,
                    source_of_truth_confirmed_at = EXCLUDED.source_of_truth_confirmed_at,
                    source_of_truth_confirmed_by = EXCLUDED.source_of_truth_confirmed_by,
                    source_of_truth_variance_note = EXCLUDED.source_of_truth_variance_note,
                    updated_at = NOW()
                """,
                (
                    emp_id,
                    tax_year,
                    values["box14"],
                    values["box16"],
                    values["box18"],
                    values["box22"],
                    values["box24"],
                    values["box26"],
                    values["box44"],
                    values["box46"],
                    values["box52"],
                    notes,
                    confirmed,
                    datetime.now() if confirmed else None,
                    confirmed_by,
                    variance_note,
                ),
            )
            return

        if self._table_exists(cur, "employee_t4_records"):
            cur.execute(
                """
                INSERT INTO employee_t4_records (
                    employee_id,
                    tax_year,
                    box_14_employment_income,
                    box_16_cpp_contributions,
                    box_18_ei_premiums,
                    box_22_income_tax,
                    box_24_ei_insurable_earnings,
                    box_26_cpp_pensionable_earnings,
                    box_44_union_dues,
                    box_46_charitable_donations,
                    box_52_pension_adjustment,
                    notes,
                    source_of_truth_confirmed,
                    source_of_truth_confirmed_at,
                    source_of_truth_confirmed_by,
                    source_of_truth_variance_note,
                    created_at,
                    updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, NOW(), NOW()
                )
                ON CONFLICT (employee_id, tax_year)
                DO UPDATE SET
                    box_14_employment_income = EXCLUDED.box_14_employment_income,
                    box_16_cpp_contributions = EXCLUDED.box_16_cpp_contributions,
                    box_18_ei_premiums = EXCLUDED.box_18_ei_premiums,
                    box_22_income_tax = EXCLUDED.box_22_income_tax,
                    box_24_ei_insurable_earnings = EXCLUDED.box_24_ei_insurable_earnings,
                    box_26_cpp_pensionable_earnings = EXCLUDED.box_26_cpp_pensionable_earnings,
                    box_44_union_dues = EXCLUDED.box_44_union_dues,
                    box_46_charitable_donations = EXCLUDED.box_46_charitable_donations,
                    box_52_pension_adjustment = EXCLUDED.box_52_pension_adjustment,
                    notes = EXCLUDED.notes,
                    source_of_truth_confirmed = EXCLUDED.source_of_truth_confirmed,
                    source_of_truth_confirmed_at = EXCLUDED.source_of_truth_confirmed_at,
                    source_of_truth_confirmed_by = EXCLUDED.source_of_truth_confirmed_by,
                    source_of_truth_variance_note = EXCLUDED.source_of_truth_variance_note,
                    updated_at = NOW()
                """,
                (
                    emp_id,
                    tax_year,
                    values["box14"],
                    values["box16"],
                    values["box18"],
                    values["box22"],
                    values["box24"],
                    values["box26"],
                    values["box44"],
                    values["box46"],
                    values["box52"],
                    notes,
                    confirmed,
                    datetime.now() if confirmed else None,
                    confirmed_by,
                    variance_note,
                ),
            )
            return

        self._ensure_legacy_t4_table(cur)
        self._upsert_t4_manual_override(cur, emp_id, tax_year, values, notes)

    @pyqtSlot()
    def open_t4_manual_override_dialog(self) -> None:
        emp_id = self._selected_employee_id()
        if not emp_id:
            QMessageBox.warning(
                self, TITLE_MISSING_SELECTION, MSG_SELECT_EMPLOYEE
            )
            return

        try:
            tax_year = int(self.year_combo.currentText())
        except (ValueError, AttributeError):
            QMessageBox.warning(
                self, "Missing Year", "Select a valid tax year first."
            )
            return

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                employee_data = self._load_t4_official_employee(
                    cur, emp_id, self._get_columns("employees")
                )
                pay_master_columns = self._get_columns("employee_pay_master")
                t4_row = self._load_t4_official_summary(
                    cur, emp_id, tax_year, pay_master_columns
                )
                actual_values = {
                    "box14": float(t4_row[0] or 0),
                    "box16": float(t4_row[1] or 0),
                    "box18": float(t4_row[2] or 0),
                    "box22": float(t4_row[3] or 0),
                    "box24": float(t4_row[4] or 0),
                    "box26": float(t4_row[5] or 0),
                    "box44": float(t4_row[6] or 0),
                    "box46": 0.0,
                    "box52": 0.0,
                }
                default_values = {
                    "box14": float(t4_row[0] or 0),
                    "box16": float(t4_row[1] or 0),
                    "box18": float(t4_row[2] or 0),
                    "box22": float(t4_row[3] or 0),
                    "box24": float(t4_row[4] or 0),
                    "box26": float(t4_row[5] or 0),
                    "box44": float(t4_row[6] or 0),
                    "box46": 0.0,
                    "box52": 0.0,
                    "notes": "",
                }
                existing_override = self._load_t4_manual_override(
                    cur, emp_id, tax_year
                )

            if existing_override:
                default_values.update(existing_override)

            display_name = (
                employee_data["full_name"]
                if employee_data
                else f"Employee {emp_id}"
            )
            dialog = T4ManualOverrideDialog(
                self,
                emp_id=emp_id,
                tax_year=tax_year,
                display_name=display_name,
                default_values=default_values,
                actual_values=actual_values,
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            values = dialog.values()
            notes = dialog.notes()
            confirmed = dialog.confirmed
            variance_bits = []
            if confirmed:
                for key, entered_value in values.items():
                    actual_value = float(actual_values.get(key, 0.0) or 0.0)
                    if not self._is_value_match(entered_value, actual_value):
                        variance_bits.append(
                            f"{key.upper()}: entered {entered_value:,.2f} vs actual {actual_value:,.2f}"
                        )

            variance_note = "; ".join(variance_bits)
            with DatabaseContext(self.db, auto_commit=True) as save_cur:
                self._upsert_t4_manual_override(
                    save_cur,
                    emp_id=emp_id,
                    tax_year=tax_year,
                    values=values,
                    notes=notes,
                    confirmed=confirmed,
                    confirmed_by=getpass.getuser(),
                    variance_note=variance_note,
                )
            status_suffix = " and confirmed source of truth" if confirmed else ""
            self._set_status(
                f"Saved manual T4 override for {display_name} ({tax_year}){status_suffix}."
            )
            self._refresh_t4_override_status()
        except Exception as exc:
            logger.exception("Failed to open T4 manual override dialog")
            self._set_status(f"T4 manual override error: {exc}", error=True)

    def _show_t4_manual_override_dialog(
        self,
        emp_id: int,
        tax_year: int,
        display_name: str,
        default_values: dict[str, float],
        actual_values: dict[str, float],
    ) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(f"T4 Manual Override - {tax_year}")
        dialog.setMinimumWidth(560)

        layout = QVBoxLayout(dialog)
        header = QLabel(
            f"Employee: {display_name} (ID {emp_id})\n"
            "Manual values saved here override payroll-calculated"
            " totals when printing Official T4."
        )
        header.setWordWrap(True)
        header.setStyleSheet("color: #1f2937;")
        layout.addWidget(header)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        fields: dict[str, QDoubleSpinBox] = {}
        compare_labels: dict[str, QLabel] = {}
        for key, label in (
            ("box14", "Box 14 - Employment Income"),
            ("box16", "Box 16 - CPP Employee"),
            ("box18", "Box 18 - EI Employee"),
            ("box22", "Box 22 - Income Tax"),
            ("box24", "Box 24 - EI Insurable"),
            ("box26", "Box 26 - CPP Pensionable"),
            ("box44", "Box 44 - Union Dues"),
            ("box46", "Box 46 - Other Remuneration"),
            ("box52", "Box 52 - Pension Adjustment"),
        ):
            field = self._money_spin()
            field.setMaximum(99_999_999.99)
            field.setValue(float(default_values.get(key, 0.0) or 0.0))
            fields[key] = field

            actual_label = QLabel(
                f"Actual: {self._format_money_value(actual_values.get(key, 0.0))}"
            )
            actual_label.setStyleSheet("color: #1f2937; font-weight: bold;")

            compare_label = QLabel("")
            compare_labels[key] = compare_label

            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            row_layout.addWidget(field)
            row_layout.addWidget(actual_label)
            row_layout.addWidget(compare_label)
            row_layout.addStretch(1)

            form.addRow(f"{label}:", row_widget)

        notes_edit = QTextEdit()
        notes_edit.setPlaceholderText(
            "Reason for adjustment (example: Paul 2013 T4 manual correction)."
        )
        notes_edit.setMaximumHeight(100)
        notes_edit.setPlainText(str(default_values.get("notes", "") or ""))
        form.addRow("Notes:", notes_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        confirm_btn = QPushButton("Save & Confirm as Source of Truth")
        confirm_btn.setStyleSheet("background-color: #065f46; color: white;")
        buttons.addButton(confirm_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        save_mode = {"confirmed": False}
        confirm_btn.clicked.connect(lambda: save_mode.__setitem__("confirmed", True))

        def refresh_compare_label(box_key: str) -> None:
            entered_value = float(fields[box_key].value())
            actual_value = float(actual_values.get(box_key, 0.0) or 0.0)
            delta = entered_value - actual_value
            match = self._is_value_match(entered_value, actual_value)
            if match:
                compare_labels[box_key].setText("MATCH")
                compare_labels[box_key].setStyleSheet(
                    "color: #065f46; font-weight: bold;"
                )
            else:
                compare_labels[box_key].setText(f"DIFF {delta:+,.2f}")
                compare_labels[box_key].setStyleSheet(
                    "color: #b91c1c; font-weight: bold;"
                )

        for key, field in fields.items():
            field.valueChanged.connect(
                lambda _value, k=key: refresh_compare_label(k)
            )
            refresh_compare_label(key)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values = {
            key: float(widget.value()) for key, widget in fields.items()
        }
        notes = notes_edit.toPlainText().strip()
        confirmed = bool(save_mode["confirmed"])
        variance_bits = []
        if confirmed:
            for key, entered_value in values.items():
                actual_value = float(actual_values.get(key, 0.0) or 0.0)
                if not self._is_value_match(entered_value, actual_value):
                    variance_bits.append(
                        f"{key.upper()}: entered {entered_value:,.2f} vs actual {actual_value:,.2f}"
                    )
        variance_note = "; ".join(variance_bits)

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                self._upsert_t4_manual_override(
                    cur,
                    emp_id=emp_id,
                    tax_year=tax_year,
                    values=values,
                    notes=notes,
                    confirmed=confirmed,
                    confirmed_by=getpass.getuser(),
                    variance_note=variance_note,
                )
            status_suffix = " and confirmed source of truth" if confirmed else ""
            self._set_status(
                f"Saved manual T4 override for {display_name} ({tax_year}){status_suffix}."
            )
            self._refresh_t4_override_status()
        except Exception as exc:
            logger.exception("Failed to save manual T4 override")
            self._set_status(
                f"Failed to save T4 manual override: {exc}", error=True
            )

    @pyqtSlot()
    def show_t4_readiness(self) -> None:
        """Show a pre-print readiness report for the selected employee and"
        "fiscal year."""

        emp_id = self._selected_employee_id()
        if not emp_id:
            QMessageBox.warning(
                self, TITLE_MISSING_SELECTION, MSG_SELECT_EMPLOYEE
            )
            return

        try:
            tax_year = int(self.year_combo.currentText())
        except (ValueError, AttributeError):
            QMessageBox.warning(
                self, "Missing Year", "Select a valid tax year first."
            )
            return

        try:
            payload = self._load_t4_readiness_data(emp_id, tax_year)
            if not payload:
                QMessageBox.warning(
                    self,
                    "Employee Not Found",
                    f"Employee ID {emp_id} not found.",
                )
                return

            readiness_lines = build_t4_readiness_lines(payload, emp_id)
            sin_ok = payload["sin_ok"]
            address_ok = payload["address_ok"]
            payroll_rows = payload["payroll_rows"]
            period_count = payload["period_count"]

            status_ok = (
                sin_ok and address_ok and payroll_rows > 0 and period_count > 1
            )
            title = (
                "T4 Readiness: READY"
                if status_ok
                else "T4 Readiness: ATTENTION NEEDED"
            )
            if status_ok:
                QMessageBox.information(
                    self, title, "\n".join(readiness_lines)
                )
            else:
                QMessageBox.warning(self, title, "\n".join(readiness_lines))

        except Exception as exc:
            logger.exception("Failed to build T4 readiness report")
            self._set_status(f"T4 readiness error: {exc}", error=True)

    def _employee_readiness_field_exprs(
        self, ecols: set[str]
    ) -> tuple[str, str, str, str, str, str]:
        full_name_expr = (
            "COALESCE(full_name, '')" if "full_name" in ecols else "''"
        )
        sin_expr = (
            "COALESCE(t4_sin, '')"
            if "t4_sin" in ecols
            else ("COALESCE(sin, '')" if "sin" in ecols else "''")
        )
        address_expr = (
            "COALESCE(street_address, '')"
            if "street_address" in ecols
            else ("COALESCE(address, '')" if "address" in ecols else "''")
        )
        city_expr = "COALESCE(city, '')" if "city" in ecols else "''"
        province_expr = (
            "COALESCE(province, '')" if "province" in ecols else "''"
        )
        postal_expr = (
            "COALESCE(postal_code, '')" if "postal_code" in ecols else "''"
        )
        return (
            full_name_expr,
            sin_expr,
            address_expr,
            city_expr,
            province_expr,
            postal_expr,
        )

    def _load_t4_readiness_data(
        self, emp_id: int, tax_year: int
    ) -> dict[str, object] | None:
        with DatabaseContext(self.db, auto_commit=False) as cur:
            ecols = self._get_columns("employees")
            (
                full_name_expr,
                sin_expr,
                address_expr,
                city_expr,
                province_expr,
                postal_expr,
            ) = self._employee_readiness_field_exprs(ecols)

            cur.execute(  # nosec
                f"""
                SELECT
                    {full_name_expr} AS full_name,
                    {sin_expr} AS sin,
                    {address_expr} AS street_address,
                    {city_expr} AS city,
                    {province_expr} AS province,
                    {postal_expr} AS postal_code
                FROM employees
                WHERE employee_id = %s
                """,
                (emp_id,),
            )
            emp_row = cur.fetchone()
            if not emp_row:
                return None

            full_name = emp_row[0] or ""
            sin_val = emp_row[1] or ""
            street = emp_row[2] or ""
            city = emp_row[3] or ""
            province = emp_row[4] or ""
            postal = emp_row[5] or ""

            sin_digits = "".join(ch for ch in sin_val if ch.isdigit())
            sin_ok = len(sin_digits) == 9
            address_ok = bool(
                street.strip() and city.strip() and province.strip() and postal.strip()
            )

            cur.execute(
                """
                SELECT
                    COUNT(*) AS payroll_rows,
                    COUNT(DISTINCT pay_period_id) AS period_count,
                    COALESCE(SUM(gross_pay), 0) AS gross_sum
                FROM employee_pay_master
                WHERE employee_id = %s AND fiscal_year = %s
                """,
                (emp_id, tax_year),
            )
            payroll_row = cur.fetchone() or (0, 0, 0)

        return {
            "full_name": full_name,
            "tax_year": tax_year,
            "sin_ok": sin_ok,
            "address_ok": address_ok,
            "payroll_rows": int(payroll_row[0] or 0),
            "period_count": int(payroll_row[1] or 0),
            "gross_sum": float(payroll_row[2] or 0),
        }

    def _build_t4_readiness_lines(
        self, payload: dict, emp_id: int
    ) -> list[str]:
        return build_t4_readiness_lines(payload, emp_id)

    @pyqtSlot()
    def print_pay_statement(self) -> None:
        """Generate a monthly pay statement PDF for the selected employee/pay"
        "period."""

        import os

        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.units import inch
            from reportlab.pdfgen import canvas
        except Exception:
            QMessageBox.critical(
                self,
                TITLE_MISSING_DEPENDENCY,
                "reportlab is required to print pay statements.",
            )
            return

        selection = self._get_save_selection(silent=False)
        if not selection:
            return
        emp_id, pay_period = selection

        self._auto_correct_deduction_outlier(reason="print", silent=True)

        _, fiscal_year, period_number, period_start, period_end, pay_date = (
            pay_period
        )

        # Keep charter detail page aligned with current DB data.
        self._load_pay_printout()

        employee_name, employee_number = self._load_employee_identity(emp_id)
        lines = self._pay_statement_lines()
        charter_rows = []
        for row in range(self.pay_printout_table.rowCount()):
            date_item = self.pay_printout_table.item(row, 0)
            reserve_item = self.pay_printout_table.item(row, 1)
            h1_item = self.pay_printout_table.item(row, 2)
            h2_item = self.pay_printout_table.item(row, 3)
            gratuity_item = self.pay_printout_table.item(row, 4)
            charter_rows.append(
                (
                    (date_item.text() if date_item else "").strip(),
                    (reserve_item.text() if reserve_item else "").strip(),
                    (h1_item.text() if h1_item else "0").strip(),
                    (h2_item.text() if h2_item else "0").strip(),
                    (gratuity_item.text() if gratuity_item else "$0.00").strip(),
                )
            )

        safe_name = "".join(
            ch if ch.isalnum() or ch in "-_" else "_" for ch in employee_name
        )
        output_filename = f"PayStatement_{fiscal_year}_P{period_number:02d}_{safe_name}.pdf"
        output_path = _APP_ROOT / output_filename

        try:
            self._render_pay_statement_pdf(
                canvas,
                letter,
                inch,
                output_path,
                employee_name,
                employee_number,
                period_number,
                period_start,
                period_end,
                pay_date,
                lines,
                charter_rows,
            )
            self._set_status(f"Pay statement generated: {output_filename}")
            if os.path.exists(output_path):
                self._open_generated_file(output_path)
        except Exception as exc:
            logger.exception("Pay statement generation error")
            self._set_status(
                f"Pay statement generation error: {exc}", error=True
            )

    @pyqtSlot()
    def print_payroll_register(self) -> None:
        """Generate a combined payroll register PDF for the selected period."""

        import os

        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.units import inch
            from reportlab.pdfgen import canvas
        except Exception:
            QMessageBox.critical(
                self,
                TITLE_MISSING_DEPENDENCY,
                "reportlab is required to print payroll register PDFs.",
            )
            return

        selection = self._get_save_selection(silent=False)
        if not selection:
            return
        emp_id, pay_period = selection

        (
            pay_period_id,
            fiscal_year,
            period_number,
            period_start,
            period_end,
            pay_date,
        ) = pay_period

        # Keep report content aligned with current DB data.
        self._load_pay_printout()
        self._refresh_work_item_summary()
        self._load_monthly_remittance_summary()

        employee_name, employee_number = self._load_employee_identity(emp_id)
        company_name, company_address, payroll_account = self._load_company_identity(
            fiscal_year
        )
        safe_name = "".join(
            ch if ch.isalnum() or ch in "-_" else "_"
            for ch in employee_name
        )
        output_filename = (
            f"PayrollRegister_{fiscal_year}_P{period_number:02d}_{safe_name}.pdf"
        )
        output_path = _APP_ROOT / output_filename

        work_summary = get_work_item_summary(
            self.db,
            int(emp_id),
            pay_period_id=int(pay_period_id) if pay_period_id else None,
            fiscal_year=int(fiscal_year) if fiscal_year else None,
        )
        work_items = get_work_items(
            self.db,
            int(emp_id),
            int(pay_period_id) if pay_period_id else None,
            int(fiscal_year) if fiscal_year else None,
        )

        charter_rows = []
        for row in range(self.pay_printout_table.rowCount()):
            date_item = self.pay_printout_table.item(row, 0)
            reserve_item = self.pay_printout_table.item(row, 1)
            h1_item = self.pay_printout_table.item(row, 2)
            h2_item = self.pay_printout_table.item(row, 3)
            gratuity_item = self.pay_printout_table.item(row, 4)
            charter_rows.append(
                (
                    (date_item.text() if date_item else "").strip(),
                    (reserve_item.text() if reserve_item else "").strip(),
                    (h1_item.text() if h1_item else "0").strip(),
                    (h2_item.text() if h2_item else "0").strip(),
                    (gratuity_item.text() if gratuity_item else "$0.00").strip(),
                )
            )

        def _draw_section_title(c, y_pos, title):
            c.setFont("Helvetica-Bold", 11)
            c.drawString(left, y_pos, title)
            y_pos -= 0.14 * inch
            c.setLineWidth(0.6)
            c.line(left, y_pos, right, y_pos)
            return y_pos - 0.16 * inch

        def _ensure_space(c, y_pos, min_height=0.8 * inch):
            if y_pos < min_height:
                c.showPage()
                return height - 0.8 * inch
            return y_pos

        try:
            c = canvas.Canvas(str(output_path), pagesize=letter)
            width, height = letter
            left = 0.65 * inch
            right = width - 0.65 * inch
            y = height - 0.8 * inch

            c.setFont("Helvetica-Bold", 12)
            c.drawString(left, y, company_name)
            c.setFont("Helvetica-Bold", 15)
            c.drawRightString(right, y, "Payroll Register")
            y -= 0.24 * inch

            c.setFont("Helvetica", 9)
            if company_address:
                c.drawString(left, y, company_address[:90])
                y -= 0.18 * inch
            if payroll_account:
                c.drawString(left, y, f"CRA Payroll Account: {payroll_account}")
                y -= 0.2 * inch

            c.setFont("Helvetica", 10)
            c.drawString(left, y, f"Employee: {employee_name}")
            if employee_number:
                c.drawRightString(right, y, f"Employee #: {employee_number}")
            y -= 0.2 * inch
            c.drawString(
                left,
                y,
                f"Period: P{period_number:02d}  {period_start} to {period_end}",
            )
            if pay_date:
                c.drawRightString(right, y, f"Pay Date: {pay_date}")
            y -= 0.2 * inch
            c.drawString(left, y, f"Generated: {date.today().isoformat()}")
            y -= 0.24 * inch
            c.line(left, y, right, y)
            y -= 0.24 * inch

            # Charter rows section
            y = _draw_section_title(c, y, "Charter Hours / Gratuity Detail")
            c.setFont("Helvetica-Bold", 9)
            c.drawString(left, y, "Date")
            c.drawString(left + 1.15 * inch, y, "Reserve")
            c.drawString(left + 3.1 * inch, y, "Hours 1")
            c.drawString(left + 4.0 * inch, y, "Hours 2")
            c.drawRightString(right, y, "Gratuity")
            y -= 0.14 * inch
            c.line(left, y, right, y)
            y -= 0.16 * inch
            c.setFont("Helvetica", 9)

            if not charter_rows:
                c.drawString(left, y, "No charter rows found for the selected period.")
                y -= 0.2 * inch
            else:
                for c_date, reserve, h1, h2, grat in charter_rows:
                    y = _ensure_space(c, y)
                    c.drawString(left, y, c_date[:16])
                    c.drawString(left + 1.15 * inch, y, reserve[:28])
                    c.drawRightString(left + 3.75 * inch, y, h1)
                    c.drawRightString(left + 4.65 * inch, y, h2)
                    c.drawRightString(right, y, grat)
                    y -= 0.18 * inch

            y -= 0.04 * inch
            c.setFont("Helvetica-Bold", 9)
            c.drawString(left, y, self.pay_printout_total_hours.text())
            c.drawString(left + 2.5 * inch, y, self.pay_printout_total_gratuity.text())
            c.drawRightString(right, y, self.pay_printout_wcb.text())
            y -= 0.28 * inch

            # Non-charter section
            y = _ensure_space(c, y)
            y = _draw_section_title(c, y, "Non-Charter Work Items / Cash Movement")
            c.setFont("Helvetica", 9)
            c.drawString(left, y, f"Payable Non-Charter Income: ${work_summary.payable_income:,.2f}")
            y -= 0.16 * inch
            c.drawString(left, y, f"Reimbursements: ${work_summary.reimbursements:,.2f}")
            y -= 0.16 * inch
            c.drawString(
                left,
                y,
                "Advances/Floats/Loans Outstanding: "
                f"${work_summary.advances_outstanding + work_summary.float_outstanding + work_summary.loan_outstanding:,.2f}",
            )
            y -= 0.22 * inch

            c.setFont("Helvetica-Bold", 9)
            c.drawString(left, y, "Date")
            c.drawString(left + 1.0 * inch, y, "Type")
            c.drawString(left + 2.25 * inch, y, "Description")
            c.drawRightString(right - 0.95 * inch, y, "Amount")
            c.drawRightString(right, y, "Status")
            y -= 0.14 * inch
            c.line(left, y, right, y)
            y -= 0.16 * inch
            c.setFont("Helvetica", 8)

            if not work_items:
                c.drawString(left, y, "No work items found for selected scope.")
                y -= 0.2 * inch
            else:
                for _wid, w_date, item_type, desc, _hrs, _rate, amount, _ref, status in work_items:
                    y = _ensure_space(c, y)
                    c.drawString(left, y, str(w_date or ""))
                    c.drawString(left + 1.0 * inch, y, str(item_type or "")[:18])
                    c.drawString(left + 2.25 * inch, y, str(desc or "")[:45])
                    c.drawRightString(right - 0.95 * inch, y, f"${float(amount or 0):,.2f}")
                    c.drawRightString(right, y, str(status or ""))
                    y -= 0.16 * inch

            # Payroll summary section
            y -= 0.1 * inch
            y = _ensure_space(c, y)
            y = _draw_section_title(c, y, "Payroll Deductions / Contributions Summary")
            c.setFont("Helvetica", 9)
            summary_pairs = [
                ("Gross Pay", f"${self.gross_pay.value():,.2f}"),
                ("Other Income (Non-Charter)", f"${self.other_income.value():,.2f}"),
                ("Reimbursements", f"${self.reimbursements.value():,.2f}"),
                ("Pay Advance Deduction", f"${self.pay_advance_deduction.value():,.2f}"),
                ("Federal Tax", f"${self.federal_tax.value():,.2f}"),
                ("Provincial Tax", f"${self.provincial_tax.value():,.2f}"),
                (LABEL_CPP_EMPLOYEE, f"${self.cpp_employee.value():,.2f}"),
                ("CPP Employer", f"${self.cpp_employer.value():,.2f}"),
                (LABEL_EI_EMPLOYEE, f"${self.ei_employee.value():,.2f}"),
                ("EI Employer", f"${self.ei_employer.value():,.2f}"),
                (LABEL_TOTAL_DEDUCTIONS, f"${self.total_deductions.value():,.2f}"),
                (LABEL_NET_PAY, f"${self.net_pay.value():,.2f}"),
            ]
            for label, value in summary_pairs:
                y = _ensure_space(c, y)
                c.drawString(left, y, label)
                c.drawRightString(right, y, value)
                y -= 0.17 * inch

            y -= 0.08 * inch
            y = _ensure_space(c, y)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(left, y, "Monthly PD7A Snapshot")
            y -= 0.16 * inch
            c.setFont("Helvetica", 9)
            pd7a_pairs = [
                ("Month", self.pd7a_month_label.text()),
                ("Gross", self.pd7a_gross.text()),
                (LABEL_CPP_EMPLOYEE, self.pd7a_cpp_employee.text()),
                ("CPP Employer", self.pd7a_cpp_employer.text()),
                (LABEL_EI_EMPLOYEE, self.pd7a_ei_employee.text()),
                ("EI Employer", self.pd7a_ei_employer.text()),
                ("Federal", self.pd7a_federal.text()),
                ("Provincial", self.pd7a_provincial.text()),
                (LABEL_TOTAL_DEDUCTIONS, self.pd7a_total_deductions.text()),
                ("Net", self.pd7a_net.text()),
                ("WCB", self.pd7a_wcb.text()),
            ]
            for label, value in pd7a_pairs:
                y = _ensure_space(c, y)
                c.drawString(left, y, label)
                c.drawRightString(right, y, value)
                y -= 0.16 * inch

            y -= 0.16 * inch
            y = _ensure_space(c, y, min_height=0.9 * inch)
            c.setFont("Helvetica-Oblique", 8)
            c.drawString(
                left,
                y,
                "Prepared for electronic distribution (email). No signature lines required.",
            )

            c.save()
            self._set_status(f"Payroll register generated: {output_filename}")
            if os.path.exists(output_path):
                self._open_generated_file(output_path)
        except Exception as exc:
            logger.exception("Payroll register generation error")
            self._set_status(
                f"Payroll register generation error: {exc}", error=True
            )

    def _load_employee_identity(self, emp_id: int) -> tuple[str, str]:
        employee_name = (
            self.employee_combo.currentText() or ""
        ).strip() or f"EMP_{emp_id}"
        employee_number = ""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                ecols = self._get_columns("employees")
                emp_num_expr = (
                    "COALESCE(employee_number::text, '')"
                    if "employee_number" in ecols
                    else "''"
                )
                cur.execute(  # nosec
                    f"""
                    SELECT
                        COALESCE(full_name, '') AS full_name,
                        {emp_num_expr} AS employee_number
                    FROM employees
                    WHERE employee_id = %s
                    """,
                    (emp_id,),
                )
                row = cur.fetchone()
                if row:
                    db_name = (row[0] or "").strip()
                    if db_name:
                        employee_name = db_name
                    employee_number = (row[1] or "").strip()
        except Exception as exc:
            logger.warning(
                f"Could not load employee details for pay statement: {exc}"
            )
        return employee_name, employee_number

    def _load_company_identity(self, fiscal_year: int | None = None) -> tuple[str, str, str]:
        """Load company display identity from company_info with safe fallbacks."""

        company_name = "Arrow Limo"
        company_address = ""
        payroll_account = ""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                if fiscal_year is None:
                    cur.execute(
                        "SELECT field_name, field_value FROM company_info"
                    )
                else:
                    cur.execute(
                        """
                        SELECT field_name, field_value
                        FROM company_info
                        WHERE last_verified_year IS NULL
                           OR last_verified_year <= %s
                        ORDER BY COALESCE(last_verified_year, 0) DESC, field_name
                        """,
                        (fiscal_year,),
                    )
                info = {
                    str(k or "").strip().lower(): str(v or "").strip()
                    for k, v in cur.fetchall()
                }

            company_name = (
                info.get("legal_name")
                or info.get("company_name")
                or info.get("name")
                or company_name
            )
            addr_parts = [
                info.get("address_line1", ""),
                info.get("address_city", ""),
                info.get("address_province", ""),
                info.get("address_postal", ""),
            ]
            company_address = ", ".join(part for part in addr_parts if part).strip(", ")
            if not company_address:
                company_address = info.get("address", "")
            payroll_account = (
                info.get("cra_payroll_account")
                or info.get("payroll_account")
                or info.get("payroll_account_number")
                or ""
            )
        except Exception as exc:
            logger.warning(
                "Could not load company info for payroll register: %s", exc
            )
        return company_name, company_address, payroll_account

    def _pay_statement_lines(self) -> list[tuple[str, float, float]]:
        return [
            ("Gross Pay", self.gross_pay.value(), self.ytd_gross_pay.value()),
            (
                "  Federal Income Tax (CRA)",
                self.federal_tax.value(),
                self.ytd_federal_tax.value() if hasattr(self, "ytd_federal_tax") else 0.0,
            ),
            (
                "  Provincial Income Tax (CRA)",
                self.provincial_tax.value(),
                self.ytd_provincial_tax.value() if hasattr(self, "ytd_provincial_tax") else 0.0,
            ),
            (
                "  CPP Employee (5.95% CRA Rate)",
                self.cpp_employee.value(),
                self.ytd_cpp_employee.value(),
            ),
            (
                "  EI Employee (1.63% CRA Rate)",
                self.ei_employee.value(),
                self.ytd_ei_employee.value(),
            ),
            (
                LABEL_TOTAL_DEDUCTIONS,
                self.total_deductions.value(),
                self.ytd_total_deductions.value(),
            ),
            (LABEL_NET_PAY, self.net_pay.value(), self.ytd_net_pay.value()),
            (
                "EI Insurable (T4-24)",
                self.ei_insurable.value(),
                self.ytd_ei_insurable.value(),
            ),
            (
                "CPP Pensionable (T4-26)",
                self.cpp_pensionable.value(),
                self.ytd_cpp_pensionable.value(),
            ),
        ]

    def _render_pay_statement_pdf(
        self,
        canvas,
        letter,
        inch,
        output_path,
        employee_name,
        employee_number,
        period_number,
        period_start,
        period_end,
        pay_date,
        lines,
        charter_rows,
    ) -> None:
        c = canvas.Canvas(str(output_path), pagesize=letter)
        width, height = letter

        left = 0.75 * inch
        right = width - 0.75 * inch
        y = height - 0.8 * inch

        c.setFont("Helvetica-Bold", 16)
        c.drawString(left, y, "Monthly Pay Statement")
        y -= 0.35 * inch

        c.setFont("Helvetica", 10)
        c.drawString(left, y, f"Employee: {employee_name}")
        if employee_number:
            c.drawString(right - 2.0 * inch, y, f"Employee #: {employee_number}")
        y -= 0.22 * inch
        c.drawString(
            left,
            y,
            f"Period: P{period_number:02d}  {period_start} to {period_end}",
        )
        c.drawString(right - 2.0 * inch, y, f"Pay Date: {pay_date}")
        y -= 0.35 * inch

        # ========== CHARTER RUNS SECTION ==========
        charter_hours_1 = self.charter_hours_1.value()
        charter_hours_2 = self.charter_hours_2.value()
        hourly_rate_1 = self.hourly_rate.value()
        hourly_rate_2 = self.hourly_rate_2.value()
        
        if charter_hours_1 > 0 or charter_hours_2 > 0:
            c.setFont("Helvetica-Bold", 11)
            c.drawString(left, y, "Charter Work")
            y -= 0.22 * inch
            
            c.setFont("Helvetica", 9)
            if charter_hours_1 > 0:
                pay1_amount = round(charter_hours_1 * hourly_rate_1, 2)
                c.drawString(left, y, f"Charter Hours (Pay 1): {charter_hours_1:.2f} hrs @ ${hourly_rate_1:,.2f}/hr")
                c.drawRightString(right, y, f"${pay1_amount:,.2f}")
                y -= 0.18 * inch
            
            if charter_hours_2 > 0:
                pay2_amount = round(charter_hours_2 * hourly_rate_2, 2)
                c.drawString(left, y, f"Charter Hours (Pay 2): {charter_hours_2:.2f} hrs @ ${hourly_rate_2:,.2f}/hr")
                c.drawRightString(right, y, f"${pay2_amount:,.2f}")
                y -= 0.18 * inch
            
            y -= 0.08 * inch

        # ========== OTHER EARNINGS SECTION ==========
        gratuity_amount = self.gratuity_amount.value()
        other_income = self.other_income.value()
        reimbursements = self.reimbursements.value()
        
        if gratuity_amount > 0 or other_income > 0:
            c.setFont("Helvetica-Bold", 11)
            c.drawString(left, y, "Other Earnings")
            y -= 0.22 * inch
            
            c.setFont("Helvetica", 9)
            if gratuity_amount > 0:
                c.drawString(left, y, "Gratuity (Non-Taxable)")
                c.drawRightString(right, y, f"${gratuity_amount:,.2f}")
                y -= 0.18 * inch
            
            if other_income > 0:
                c.drawString(left, y, "Other Income")
                c.drawRightString(right, y, f"${other_income:,.2f}")
                y -= 0.18 * inch
            
            y -= 0.08 * inch

        # ========== DEDUCTIONS & CONTRIBUTIONS SECTION ==========
        c.setFont("Helvetica-Bold", 11)
        c.drawString(left, y, "Deductions & Contributions (CRA Calculated)")
        y -= 0.22 * inch
        
        c.setFont("Helvetica", 9)
        federal_tax = self.federal_tax.value()
        provincial_tax = self.provincial_tax.value()
        cpp_employee = self.cpp_employee.value()
        ei_employee = self.ei_employee.value()
        
        c.drawString(left, y, "Federal Income Tax (CRA Rate)")
        c.drawRightString(right, y, f"${federal_tax:,.2f}")
        y -= 0.18 * inch
        
        c.drawString(left, y, "Provincial Income Tax (CRA Rate)")
        c.drawRightString(right, y, f"${provincial_tax:,.2f}")
        y -= 0.18 * inch
        
        c.drawString(left, y, "CPP Employee Contribution (5.95%)")
        c.drawRightString(right, y, f"${cpp_employee:,.2f}")
        y -= 0.18 * inch
        
        c.drawString(left, y, "EI Employee Premium (1.63%)")
        c.drawRightString(right, y, f"${ei_employee:,.2f}")
        y -= 0.18 * inch
        
        # WCB if present
        try:
            wcb_text = self.pay_printout_wcb.text()
            if wcb_text and "$" in wcb_text:
                wcb_amount = wcb_text.split("$")[1].strip()
                c.drawString(left, y, "Workers' Compensation (WCB)")
                c.drawRightString(right, y, f"${wcb_amount}")
                y -= 0.18 * inch
        except Exception:
            pass
        
        y -= 0.08 * inch

        # ========== REIMBURSEMENTS SECTION ==========
        if reimbursements > 0:
            c.setFont("Helvetica-Bold", 11)
            c.drawString(left, y, "Reimbursements (Non-Taxable)")
            y -= 0.22 * inch
            c.setFont("Helvetica", 9)
            c.drawString(left, y, "Expense Reimbursements")
            c.drawRightString(right, y, f"${reimbursements:,.2f}")
            y -= 0.18 * inch
            y -= 0.08 * inch

        y -= 0.1 * inch
        c.setLineWidth(0.8)
        c.line(left, y, right, y)
        y -= 0.22 * inch

        # ========== PERCENTAGE CHECK SECTION ==========
        gross_pay = max(0.0, self.gross_pay.value())
        income_tax_total = self.federal_tax.value() + self.provincial_tax.value()
        total_deductions = self.total_deductions.value()
        if gross_pay > 0:
            income_tax_pct = (income_tax_total / gross_pay) * 100.0
            total_deduction_pct = (total_deductions / gross_pay) * 100.0
        else:
            income_tax_pct = 0.0
            total_deduction_pct = 0.0

        c.setFont("Helvetica-Bold", 11)
        c.drawString(left, y, "Payroll Percentage Check")
        y -= 0.22 * inch

        c.setFont("Helvetica", 9)
        c.drawString(left, y, "Income Tax % of Gross")
        c.drawRightString(right, y, f"{income_tax_pct:,.2f}%")
        y -= 0.18 * inch

        c.drawString(left, y, "Total Deductions % of Gross")
        c.drawRightString(right, y, f"{total_deduction_pct:,.2f}%")
        y -= 0.18 * inch

        if total_deduction_pct > (MAX_REASONABLE_DEDUCTION_RATIO * 100.0):
            c.setFont("Helvetica-Bold", 9)
            c.drawString(
                left,
                y,
                "WARNING: Total deductions exceeded 50% of gross before auto-correction check.",
            )
            y -= 0.18 * inch

        y -= 0.08 * inch

        # ========== SUMMARY TABLE ==========
        col_item = left
        col_period = left + 3.0 * inch
        col_ytd = left + 4.7 * inch

        c.setFont("Helvetica-Bold", 10)
        c.drawString(col_item, y, "Summary")
        c.drawString(col_period, y, "This Period")
        c.drawString(col_ytd, y, "Year-to-Date")
        y -= 0.14 * inch
        c.line(left, y, right, y)
        y -= 0.18 * inch

        c.setFont("Helvetica", 10)
        for label, period_val, ytd_val in lines:
            if y < 1.0 * inch:
                c.showPage()
                y = height - 0.8 * inch
                c.setFont("Helvetica", 10)
            c.drawString(col_item, y, label)
            c.drawRightString(col_period + 1.45 * inch, y, f"${period_val:,.2f}")
            c.drawRightString(col_ytd + 1.45 * inch, y, f"${ytd_val:,.2f}")
            y -= 0.22 * inch

        y -= 0.1 * inch
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(
            left,
            y,
            "YTD values are cumulative through the selected pay period.",
        )
        y -= 0.14 * inch
        c.drawString(
            left,
            y,
            f"Generated by ALMS Payroll Entry on {date.today().isoformat()}",
        )
        y -= 0.12 * inch
        c.drawString(
            left,
            y,
            "CRA deductions calculated per current tax year rates. Verify calculations with CRA records.",
        )

        self._render_pay_statement_charter_page(
            c,
            letter,
            inch,
            employee_name,
            employee_number,
            period_number,
            period_start,
            period_end,
            charter_rows,
        )
        c.save()

    def _render_pay_statement_charter_page(
        self,
        canvas_obj,
        letter,
        inch,
        employee_name,
        employee_number,
        period_number,
        period_start,
        period_end,
        charter_rows,
    ) -> None:
        """Append charter-row detail page to the pay statement PDF."""
        canvas_obj.showPage()
        width, height = letter
        left = 0.75 * inch
        right = width - 0.75 * inch

        def _draw_page_header() -> float:
            y_pos = height - 0.8 * inch
            canvas_obj.setFont("Helvetica-Bold", 14)
            canvas_obj.drawString(left, y_pos, "Pay Statement Charter Detail")
            y_pos -= 0.28 * inch
            canvas_obj.setFont("Helvetica", 10)
            canvas_obj.drawString(left, y_pos, f"Employee: {employee_name}")
            if employee_number:
                canvas_obj.drawString(
                    right - 2.0 * inch,
                    y_pos,
                    f"Employee #: {employee_number}",
                )
            y_pos -= 0.2 * inch
            canvas_obj.drawString(
                left,
                y_pos,
                f"Period: P{period_number:02d}  {period_start} to {period_end}",
            )
            y_pos -= 0.24 * inch
            canvas_obj.setFont("Helvetica-Bold", 9)
            canvas_obj.drawString(left, y_pos, "Charter Date")
            canvas_obj.drawString(left + 1.3 * inch, y_pos, "Reserve #")
            canvas_obj.drawRightString(left + 4.2 * inch, y_pos, "Hours 1")
            canvas_obj.drawRightString(left + 5.0 * inch, y_pos, "Hours 2")
            canvas_obj.drawRightString(right, y_pos, "Gratuity")
            y_pos -= 0.14 * inch
            canvas_obj.line(left, y_pos, right, y_pos)
            return y_pos - 0.16 * inch

        y = _draw_page_header()
        canvas_obj.setFont("Helvetica", 9)

        if not charter_rows:
            canvas_obj.drawString(
                left,
                y,
                "No charter rows found for this pay period.",
            )
            y -= 0.2 * inch
        else:
            for c_date, reserve, h1, h2, grat in charter_rows:
                if y < 1.0 * inch:
                    canvas_obj.showPage()
                    y = _draw_page_header()
                    canvas_obj.setFont("Helvetica", 9)
                canvas_obj.drawString(left, y, c_date[:16])
                canvas_obj.drawString(left + 1.3 * inch, y, reserve[:26])
                canvas_obj.drawRightString(left + 4.2 * inch, y, h1)
                canvas_obj.drawRightString(left + 5.0 * inch, y, h2)
                canvas_obj.drawRightString(right, y, grat)
                y -= 0.18 * inch

        y -= 0.08 * inch
        canvas_obj.setFont("Helvetica-Bold", 9)
        canvas_obj.drawString(left, y, self.pay_printout_total_hours.text())
        canvas_obj.drawString(
            left + 2.7 * inch,
            y,
            self.pay_printout_total_gratuity.text(),
        )
        canvas_obj.drawRightString(right, y, self.pay_printout_wcb.text())
        y -= 0.2 * inch
        canvas_obj.setFont("Helvetica-Oblique", 8)
        canvas_obj.drawString(
            left,
            y,
            f"Generated on {date.today().isoformat()}",
        )

    @pyqtSlot()
    def open_payment_ledger(self) -> None:
        """Jump to the payment ledger section and focus the Add Payment"
        "action."""

        self._refresh_pay_ledger()
        if hasattr(self, "scroll_area") and hasattr(self, "pay_ledger"):
            self.scroll_area.ensureWidgetVisible(
                self.pay_ledger, xMargin=0, yMargin=30
            )

        if hasattr(self, "pay_ledger") and hasattr(self.pay_ledger, "add_btn"):
            self.pay_ledger.add_btn.setFocus()

        self._set_status(
            "Payment ledger ready. Use Add Payment / Edit Selected / Delete"
            "Selected."

        )
