"""
Client Drill-Down Detail View
Comprehensive client management - contact, charter history, payments, credit,
preferences
"""

import logging
import time

import psycopg2

from common_widgets import StandardDateEdit
from db_error_handling import DatabaseContext
from payment_dialog import PaymentDialog
from PyQt6.QtCore import QDate, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QAbstractItemView,
    QDateEdit,
)
from ui_standards import (
    SmartFormField,
    make_read_only_table,
    setup_standard_table,
)

logger = logging.getLogger(__name__)


def _is_account_number_unique_violation(error: psycopg2.Error) -> bool:
    """Return True when a DB error is a unique conflict on account_number."""
    constraint_name = (
        getattr(getattr(error, "diag", None), "constraint_name", "") or ""
    ).lower()
    message = str(error).lower()
    return (
        "account_number" in constraint_name
        or (
            "unique" in message
            and "account_number" in message
            and "clients" in message
        )
    )


def _next_client_account_number(cur) -> str:
    """Get a safe next account number, repairing stale sequence drift."""
    cur.execute(
        "SELECT MAX(CAST(account_number AS INTEGER)) FROM clients "
        "WHERE account_number ~ '^[0-9]+$'"
    )
    max_account = int(cur.fetchone()[0] or 7604)

    try:
        cur.execute("SAVEPOINT acct_seq")
        cur.execute("SELECT nextval('account_number_seq')")
        candidate = int(cur.fetchone()[0])

        if candidate <= max_account:
            cur.execute("SELECT setval('account_number_seq', %s, true)", (max_account,))
            cur.execute("SELECT nextval('account_number_seq')")
            candidate = int(cur.fetchone()[0])

        cur.execute("RELEASE SAVEPOINT acct_seq")
        return str(candidate)
    except Exception:
        cur.execute("ROLLBACK TO SAVEPOINT acct_seq")
        return str(max_account + 1)


class ClientDetailDialog(QDialog):
    """
    Complete client master-detail view with:
    - Contact information and billing details
    - Charter history (all bookings)
    - Payment history and outstanding balance
    - Credit terms and limits
    - Preferences (favorite drivers, vehicles, beverages)
    - Special requirements and notes
    - Contract documents
    - Communication history
    - Dispute tracking
    - Client value metrics (lifetime value, frequency)
    """

    saved = pyqtSignal(dict)

    TAB_INDEX_CONTACT = 0
    TAB_INDEX_CHARTER_HISTORY = 1
    TAB_INDEX_PAYMENTS = 2
    TAB_INDEX_CREDIT = 3
    TAB_INDEX_PREFERENCES = 4
    TAB_INDEX_COMMUNICATIONS = 5
    TAB_INDEX_DOCUMENTS = 6
    TAB_INDEX_DISPUTES = 7
    TAB_INDEX_METRICS = 8

    def __init__(self, db, client_id=None, parent=None, start_tab: int = 0) -> None:
        try:
            super().__init__(parent)
            self.db = db
            self.client_id = client_id
            self.client_data = None
            self._deferred_sections_loaded = set()
            self._is_initializing = True

            # Ensure contract_charter_reserve column exists
            try:
                with DatabaseContext(self.db, auto_commit=True) as _cur:
                    _cur.execute(
                        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS "
                        "contract_charter_reserve VARCHAR(20)"
                    )
            except Exception as _e:
                logger.debug("Suppressed: %s", _e)
            self.setWindowTitle(f"Client Detail - {client_id or 'New'}")
            self.setGeometry(50, 50, 1400, 900)

            layout = QVBoxLayout()

            # ===== TOP ACTION BUTTONS (STANDARD LAYOUT) =====
            button_layout = QHBoxLayout()

            # Left side: Action-specific buttons (Suspend, Activate, Link
            # Child)
            self.suspend_btn = QPushButton("🚫 Suspend Client")
            self.suspend_btn.clicked.connect(self.suspend_client)
            button_layout.addWidget(self.suspend_btn)

            self.activate_btn = QPushButton("✅ Activate Client")
            self.activate_btn.clicked.connect(self.activate_client)
            button_layout.addWidget(self.activate_btn)

            self.link_child_btn = QPushButton("🔗 Link Child Account")
            self.link_child_btn.clicked.connect(self.link_child_account)
            button_layout.addWidget(self.link_child_btn)

            button_layout.addStretch()

            # Right side: Standard drill-down buttons (Add, Duplicate, Delete,
            # Save, Close)
            self.add_new_btn = QPushButton("+ Add New")
            self.add_new_btn.clicked.connect(self.add_new_client)
            button_layout.addWidget(self.add_new_btn)

            self.duplicate_btn = QPushButton("📋 Duplicate")
            self.duplicate_btn.clicked.connect(self.duplicate_client)
            button_layout.addWidget(self.duplicate_btn)

            self.delete_btn = QPushButton("🗑️ Delete")
            self.delete_btn.clicked.connect(self.delete_client)
            button_layout.addWidget(self.delete_btn)

            self.save_btn = QPushButton("💾 Save All Changes")
            self.save_btn.clicked.connect(self.save_client)
            button_layout.addWidget(self.save_btn)

            close_btn = QPushButton("Close")
            close_btn.clicked.connect(self.close)
            button_layout.addWidget(close_btn)

            layout.addLayout(button_layout)

            # ===== TABS =====
            self.tabs = QTabWidget()

            self.tabs.addTab(self.create_contact_tab(), "👤 Contact Info")
            self.tabs.addTab(self.create_charter_history_tab(), "🚗 Charter History")
            self.tabs.addTab(self.create_payments_tab(), "💳 Payments")
            self.tabs.addTab(self.create_credit_tab(), "💰 Credit & Terms")
            self.tabs.addTab(self.create_preferences_tab(), "⭐ Preferences")
            self.tabs.addTab(self.create_communications_tab(), "📧 Communications")
            self.tabs.addTab(self.create_documents_tab(), "📄 Documents")
            self.tabs.addTab(self.create_disputes_tab(), "⚠️ Disputes")
            self.tabs.addTab(self.create_metrics_tab(), "📊 Client Metrics")

            if 0 <= int(start_tab) < self.tabs.count():
                self.tabs.setCurrentIndex(int(start_tab))

            layout.addWidget(self.tabs)
            self.setLayout(layout)

            if client_id:
                self.load_client_data()

            self.tabs.currentChanged.connect(self._load_deferred_section_for_tab)
            self._is_initializing = False
            # If dialog starts on a deferred tab (e.g., Payments), load it now.
            self._load_deferred_section_for_tab(self.tabs.currentIndex())
        except Exception:
            logger.exception("ClientDetailDialog.__init__ failed")
            raise

    def create_contact_tab(self) -> object:
        """Tab 1: Contact information and billing"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("Contact Information")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_widget = QWidget()
        form = QFormLayout()

        # Basic info
        self.company_name = QLineEdit()
        form.addRow("Client Name (Individual or Business):", self.company_name)

        self.client_name = QLineEdit()
        form.addRow("Contact Person:", self.client_name)

        # Corporate hierarchy
        corporate_group = QGroupBox("Corporate Information")
        corporate_form = QFormLayout()

        # Both type checkboxes on one row
        self.is_company = QCheckBox("This is a company (not an individual)")
        self.is_company.stateChanged.connect(self.on_is_company_toggled)
        self.is_corporate = QCheckBox("This is a corporate client")
        type_row = QHBoxLayout()
        type_row.addWidget(self.is_company)
        type_row.addWidget(self.is_corporate)
        type_row.addStretch()
        corporate_form.addRow("Type:", type_row)

        # First / last name on one row
        self.first_name = QLineEdit()
        self.last_name = QLineEdit()
        name_row = QHBoxLayout()
        name_row.addWidget(self.first_name)
        name_row.addWidget(QLabel("Last Name:"))
        name_row.addWidget(self.last_name)
        corporate_form.addRow("First Name (Individual):", name_row)

        # Corporate parent ID and role on one row
        self.corporate_parent_id = QSpinBox()
        self.corporate_parent_id.setMinimum(0)
        self.corporate_parent_id.setMaximum(999999)
        self.corporate_parent_id.setValue(0)
        self.corporate_role = QComboBox()
        self.corporate_role.addItems(
            [
                "None",
                "primary",
                "employee_1",
                "employee_2",
                "employee_3",
                "employee_4",
                "employee_5",
                "employee_6",
                "employee_7",
                "employee_8",
            ]
        )
        parent_role_row = QHBoxLayout()
        parent_role_row.addWidget(self.corporate_parent_id)
        parent_role_row.addWidget(QLabel("Role in Company:"))
        parent_role_row.addWidget(self.corporate_role)
        parent_role_row.addStretch()
        corporate_form.addRow("Corporate Parent ID (0=Individual):", parent_role_row)

        corporate_group.setLayout(corporate_form)
        form.addRow(corporate_group)

        # Phone / email on one row
        self.phone = SmartFormField.phone_field()
        self.email = SmartFormField.email_field()
        contact_row = QHBoxLayout()
        contact_row.addWidget(self.phone)
        contact_row.addWidget(QLabel("Email:"))
        contact_row.addWidget(self.email)
        form.addRow("Phone:", contact_row)

        self.address = SmartFormField.auto_expanding_text(max_height=100)
        form.addRow("Address:", self.address)

        # City / province / postal on one row
        self.city = QLineEdit()
        self.province = QLineEdit()
        self.province.setMaximumWidth(120)
        self.postal = SmartFormField.postal_code_field()
        city_row = QHBoxLayout()
        city_row.addWidget(self.city)
        city_row.addWidget(QLabel("Province:"))
        city_row.addWidget(self.province)
        city_row.addWidget(QLabel("Postal Code:"))
        city_row.addWidget(self.postal)
        form.addRow("City:", city_row)

        # Billing info
        billing_group = QGroupBox("Billing Information")
        billing_form = QFormLayout()

        # Billing email / tax id on one row
        self.billing_email = SmartFormField.email_field()
        self.tax_id = QLineEdit()
        billing_top_row = QHBoxLayout()
        billing_top_row.addWidget(self.billing_email)
        billing_top_row.addWidget(QLabel("Tax ID/GST #:"))
        billing_top_row.addWidget(self.tax_id)
        billing_form.addRow("Billing Email:", billing_top_row)

        # Payment terms / preferred payment on one row
        self.payment_terms = QComboBox()
        self.payment_terms.addItems(
            ["Due on Receipt", "Net 15", "Net 30", "Net 60", "COD", "Prepaid"]
        )
        self.preferred_payment = QComboBox()
        self.preferred_payment.addItems(
            ["Credit Card", "Invoice", "Cash", "Check", "Bank Transfer"]
        )
        billing_terms_row = QHBoxLayout()
        billing_terms_row.addWidget(self.payment_terms)
        billing_terms_row.addWidget(QLabel("Preferred Payment:"))
        billing_terms_row.addWidget(self.preferred_payment)
        billing_terms_row.addStretch()
        billing_form.addRow("Payment Terms:", billing_terms_row)

        billing_group.setLayout(billing_form)
        form.addRow(billing_group)

        # Contract Charter
        contract_group = QGroupBox("Contract Charter")
        contract_form = QFormLayout()

        self.is_contract_client = QCheckBox("This client has a contract charter")
        contract_form.addRow("Contract Client:", self.is_contract_client)

        self.contract_charter_input = QLineEdit()
        self.contract_charter_input.setPlaceholderText("Reserve # e.g. 019842")
        self.contract_charter_input.setMaximumWidth(160)
        contract_form.addRow("Contract Charter #:", self.contract_charter_input)

        view_contract_btn = QPushButton("\U0001f4cb View Contract Charter")
        view_contract_btn.setMaximumWidth(200)
        view_contract_btn.clicked.connect(self._view_contract_charter)
        contract_form.addRow("", view_contract_btn)

        contract_group.setLayout(contract_form)
        form.addRow(contract_group)

        # Status
        self.client_status = QComboBox()
        self.client_status.addItems(["Active", "Inactive", "Suspended", "VIP", "Blacklisted"])
        form.addRow("Status:", self.client_status)

        self.notes = SmartFormField.auto_expanding_text(max_height=300)
        form.addRow("Notes:", self.notes)

        form_widget.setLayout(form)
        scroll.setWidget(form_widget)
        layout.addWidget(scroll)

        widget.setLayout(layout)
        return widget

    def create_charter_history_tab(self) -> object:
        """Tab 2: Complete charter history"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("Charter History")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        # Summary stats
        stats_layout = QHBoxLayout()
        self.total_charters = QLabel("Total Charters: 0")
        self.total_revenue = QLabel("Total Revenue: $0.00")
        self.avg_charter_value = QLabel("Avg Charter: $0.00")
        self.last_charter_date = QLabel("Last Charter: Never")
        stats_layout.addWidget(self.total_charters)
        stats_layout.addWidget(self.total_revenue)
        stats_layout.addWidget(self.avg_charter_value)
        stats_layout.addWidget(self.last_charter_date)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # Charter history table
        self.charter_table = QTableWidget()
        setup_standard_table(
            self.charter_table,
            [
                "Date",
                "Reserve #",
                "Pickup",
                "Destination",
                "Driver",
                "Vehicle",
                "Amount",
                "Status",
            ],
            {
                "Date": "date",
                "Reserve #": "reserve_number",
                "Amount": "amount",
                "Status": "status",
                "Driver": "name",
                "Vehicle": "vehicle",
                "Pickup": "address",
                "Destination": "address",
            },
        )
        make_read_only_table(self.charter_table)
        self.charter_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.charter_table.doubleClicked.connect(self.open_charter_detail)
        layout.addWidget(self.charter_table)

        # Charter buttons
        btn_layout = QHBoxLayout()
        new_charter_btn = QPushButton("+ New Charter")
        new_charter_btn.clicked.connect(self.new_charter)
        btn_layout.addWidget(new_charter_btn)

        refresh_charters_btn = QPushButton("🔄 Refresh From DB")
        refresh_charters_btn.setToolTip(
            "Reload client charter/payment data from the database and reflect offsite changes."
        )
        refresh_charters_btn.clicked.connect(self.refresh_client_dashboard)
        btn_layout.addWidget(refresh_charters_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        widget.setLayout(layout)
        return widget

    def create_payments_tab(self) -> object:
        """Tab 3: Payment history and outstanding balance"""
        widget = QWidget()
        layout = QVBoxLayout()

        header = QHBoxLayout()
        title = QLabel("Payment History (Manual Record)")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header.addWidget(title)
        help_icon = QLabel("i")
        help_icon.setToolTip(
            "Manual ledger entry only — records payments already received "
            "(cash/check/bank). No online processing or auto-charging."
        )
        header.addWidget(help_icon)
        header.addStretch()
        layout.addLayout(header)
        hint = QLabel(
            "Manual ledger entry only — records payments already received "
            "(cash/check/bank). No online processing or auto-charging."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 10px; color: #666;")
        layout.addWidget(hint)

        # Payment summary
        summary_layout = QHBoxLayout()
        self.total_paid = QLabel("Total Paid: $0.00")
        self.outstanding_balance = QLabel("Outstanding: $0.00")
        self.unapplied_credit = QLabel("Unapplied Credit: $0.00")
        self.escrow_held = QLabel("Escrow Held: $0.00")
        self.refund_held = QLabel("Refund Held: $0.00")
        self.overdue_amount = QLabel("Overdue: $0.00")
        summary_layout.addWidget(self.total_paid)
        summary_layout.addWidget(self.outstanding_balance)
        summary_layout.addWidget(self.unapplied_credit)
        summary_layout.addWidget(self.escrow_held)
        summary_layout.addWidget(self.refund_held)
        summary_layout.addWidget(self.overdue_amount)
        summary_layout.addStretch()
        layout.addLayout(summary_layout)

        # Payment table
        self.payment_table = QTableWidget()
        setup_standard_table(
            self.payment_table,
            [
                "Date",
                "Reserve #",
                "Amount",
                "Method",
                "Reference",
                "Reconciled",
                "Notes",
            ],
            {
                "Date": "date",
                "Reserve #": "reserve_number",
                "Amount": "amount",
                "Notes": "description",
            },
        )
        make_read_only_table(self.payment_table)
        self.payment_table.setToolTip(
            "Double-click a posted payment to open its charter."
        )
        self.payment_table.doubleClicked.connect(self.open_payment_charter_detail)
        layout.addWidget(self.payment_table)

        # Payment buttons
        btn_layout = QHBoxLayout()
        record_payment_btn = QPushButton("+ Record Payment")
        record_payment_btn.setToolTip(
            "Record a manually received client payment; no online processing or auto-charging."
        )
        record_payment_btn.clicked.connect(self.record_payment)
        btn_layout.addWidget(record_payment_btn)

        pay_back_btn = QPushButton("↩ Pay Back Held Balance")
        pay_back_btn.setToolTip(
            "Record money paid back to the client from held credit/refund/escrow balances."
        )
        pay_back_btn.clicked.connect(self._pay_back_held_balance)
        btn_layout.addWidget(pay_back_btn)

        send_statement_btn = QPushButton("📧 Send Statement")
        send_statement_btn.clicked.connect(self.send_statement)
        btn_layout.addWidget(send_statement_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        widget.setLayout(layout)
        return widget

    def create_credit_tab(self) -> object:
        """Tab 4: Credit terms and limits"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("Credit & Terms")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        form = QFormLayout()

        self.credit_limit = QDoubleSpinBox()
        self.credit_limit.setMaximum(9999999)
        self.credit_limit.setPrefix("$")
        self.credit_limit.setMaximumWidth(160)

        self.credit_used = QDoubleSpinBox()
        self.credit_used.setMaximum(9999999)
        self.credit_used.setReadOnly(True)
        self.credit_used.setPrefix("$")
        self.credit_used.setMaximumWidth(160)

        # Credit Limit + Credit Used share one row (both are short $ fields).
        limit_row = QHBoxLayout()
        limit_row.addWidget(self.credit_limit)
        limit_row.addSpacing(30)
        limit_row.addWidget(QLabel("Credit Used:"))
        limit_row.addWidget(self.credit_used)
        limit_row.addStretch()
        form.addRow("Credit Limit:", limit_row)

        self.credit_available = QDoubleSpinBox()
        self.credit_available.setMaximum(9999999)
        self.credit_available.setReadOnly(True)
        self.credit_available.setPrefix("$")
        self.credit_available.setMaximumWidth(160)

        self.deposit_percent = QDoubleSpinBox()
        self.deposit_percent.setMaximum(100)
        self.deposit_percent.setSuffix("%")
        self.deposit_percent.setMaximumWidth(160)

        # Available Credit + Deposit % on one row.
        avail_row = QHBoxLayout()
        avail_row.addWidget(self.credit_available)
        avail_row.addSpacing(30)
        avail_row.addWidget(QLabel("Deposit %:"))
        avail_row.addWidget(self.deposit_percent)
        avail_row.addStretch()
        form.addRow("Available Credit:", avail_row)

        self.deposit_required = QCheckBox()

        self.credit_check_date = StandardDateEdit(prefer_month_text=True)
        self.credit_check_date.setCalendarPopup(True)
        self.credit_check_date.setMaximumWidth(160)

        # Deposit Required + Last Credit Check on one row.
        deposit_row = QHBoxLayout()
        deposit_row.addWidget(self.deposit_required)
        deposit_row.addSpacing(30)
        deposit_row.addWidget(QLabel("Last Credit Check:"))
        deposit_row.addWidget(self.credit_check_date)
        deposit_row.addStretch()
        form.addRow("Deposit Required:", deposit_row)

        self.credit_rating = QComboBox()
        self.credit_rating.addItems(["Excellent", "Good", "Fair", "Poor", "Not Rated"])
        self.credit_rating.setMaximumWidth(160)
        rating_row = QHBoxLayout()
        rating_row.addWidget(self.credit_rating)
        rating_row.addStretch()
        form.addRow("Credit Rating:", rating_row)

        layout.addLayout(form)
        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def create_preferences_tab(self) -> object:
        """Tab 5: Client preferences"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("Client Preferences")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        # Favorite drivers
        driver_group = QGroupBox("Favorite Drivers")
        driver_layout = QVBoxLayout()
        self.fav_drivers_list = QListWidget()
        driver_layout.addWidget(self.fav_drivers_list)
        driver_btn_layout = QHBoxLayout()
        add_driver_btn = QPushButton("+ Add Driver")
        add_driver_btn.clicked.connect(self.add_favorite_driver)
        driver_btn_layout.addWidget(add_driver_btn)
        remove_driver_btn = QPushButton("- Remove")
        remove_driver_btn.clicked.connect(self.remove_favorite_driver)
        driver_btn_layout.addWidget(remove_driver_btn)
        driver_btn_layout.addStretch()
        driver_layout.addLayout(driver_btn_layout)
        driver_group.setLayout(driver_layout)
        layout.addWidget(driver_group)

        # Favorite vehicles
        vehicle_group = QGroupBox("Favorite Vehicles")
        vehicle_layout = QVBoxLayout()
        self.fav_vehicles_list = QListWidget()
        vehicle_layout.addWidget(self.fav_vehicles_list)
        vehicle_btn_layout = QHBoxLayout()
        add_vehicle_btn = QPushButton("+ Add Vehicle")
        add_vehicle_btn.clicked.connect(self.add_favorite_vehicle)
        vehicle_btn_layout.addWidget(add_vehicle_btn)
        remove_vehicle_btn = QPushButton("- Remove")
        remove_vehicle_btn.clicked.connect(self.remove_favorite_vehicle)
        vehicle_btn_layout.addWidget(remove_vehicle_btn)
        vehicle_btn_layout.addStretch()
        vehicle_layout.addLayout(vehicle_btn_layout)
        vehicle_group.setLayout(vehicle_layout)
        layout.addWidget(vehicle_group)

        # Special requirements
        req_group = QGroupBox("Special Requirements")
        req_layout = QVBoxLayout()
        self.special_requirements = QTextEdit()
        self.special_requirements.setPlaceholderText("Wheelchair accessible, child seats, etc.")
        req_layout.addWidget(self.special_requirements)
        req_group.setLayout(req_layout)
        layout.addWidget(req_group)

        widget.setLayout(layout)
        return widget

    def create_communications_tab(self) -> object:
        """Tab 6: Communication history"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("Communication History")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        # Communications table
        self.comm_table = QTableWidget()
        setup_standard_table(
            self.comm_table,
            ["Date/Time", "Type", "Subject", "Sta", "Notes"],
            {"Date/Time": "datetime", "Notes": "description"},
        )
        make_read_only_table(self.comm_table)
        layout.addWidget(self.comm_table)

        # Communication buttons
        btn_layout = QHBoxLayout()
        log_call_btn = QPushButton("📞 Log Call")
        log_call_btn.clicked.connect(self.log_call)
        btn_layout.addWidget(log_call_btn)

        log_email_btn = QPushButton("📧 Log Email")
        log_email_btn.clicked.connect(self.log_email)
        btn_layout.addWidget(log_email_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        widget.setLayout(layout)
        return widget

    def create_documents_tab(self) -> object:
        """Tab 7: Contract documents"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("Client Documents")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        # Document list
        self.doc_list = QListWidget()
        self.doc_list.doubleClicked.connect(self.open_client_document)
        layout.addWidget(self.doc_list)

        # Document buttons
        btn_layout = QHBoxLayout()
        upload_btn = QPushButton("📤 Upload Document")
        upload_btn.clicked.connect(self.upload_client_doc)
        btn_layout.addWidget(upload_btn)

        view_btn = QPushButton("👁️ View Selected")
        view_btn.clicked.connect(self.view_client_doc)
        btn_layout.addWidget(view_btn)

        delete_btn = QPushButton("🗑️ Delete Selected")
        delete_btn.clicked.connect(self.delete_client_doc)
        btn_layout.addWidget(delete_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        widget.setLayout(layout)
        return widget

    def create_disputes_tab(self) -> object:
        """Tab 8: Billing disputes and issues"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("Disputes & Issues")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        # Disputes table
        self.dispute_table = QTableWidget()
        setup_standard_table(
            self.dispute_table,
            [
                "Date",
                "Charter #",
                "Issue Type",
                "Amount",
                "Status",
                "Resolution",
            ],
            {
                "Date": "date",
                "Amount": "amount",
                "Status": "status",
                "Resolution": "description",
            },
        )
        make_read_only_table(self.dispute_table)
        layout.addWidget(self.dispute_table)

        # Dispute buttons
        btn_layout = QHBoxLayout()
        log_dispute_btn = QPushButton("+ Log Dispute")
        log_dispute_btn.clicked.connect(self.log_dispute)
        btn_layout.addWidget(log_dispute_btn)

        resolve_btn = QPushButton("✅ Resolve Selected")
        resolve_btn.clicked.connect(self.resolve_dispute)
        btn_layout.addWidget(resolve_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        widget.setLayout(layout)
        return widget

    def create_metrics_tab(self) -> object:
        """Tab 9: Client value metrics"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("Client Metrics")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        # Metrics form
        form = QFormLayout()

        self.lifetime_value = QDoubleSpinBox()
        self.lifetime_value.setMaximum(9999999)
        self.lifetime_value.setReadOnly(True)
        self.lifetime_value.setPrefix("$")
        form.addRow("Lifetime Value:", self.lifetime_value)

        self.avg_monthly_revenue = QDoubleSpinBox()
        self.avg_monthly_revenue.setMaximum(9999999)
        self.avg_monthly_revenue.setReadOnly(True)
        self.avg_monthly_revenue.setPrefix("$")
        form.addRow("Avg Monthly Revenue:", self.avg_monthly_revenue)

        self.charter_frequency = QLabel("0 charters/month")
        form.addRow("Charter Frequency:", self.charter_frequency)

        self.first_charter_date = QLabel("N/A")
        form.addRow("First Charter:", self.first_charter_date)

        self.client_since_days = QLabel("0 days")
        form.addRow("Client Since:", self.client_since_days)

        self.payment_reliability = QLabel("100%")
        form.addRow("Payment Reliability:", self.payment_reliability)

        self.cancellation_rate = QLabel("0%")
        form.addRow("Cancellation Rate:", self.cancellation_rate)

        layout.addLayout(form)
        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def load_client_data(self) -> None:
        """Load all client data from database"""
        try:
            start_ts = time.perf_counter()
            # Reset any open transaction snapshot before reloading so we always
            # read the latest committed offsite changes.
            try:
                self.db.rollback()
            except Exception as _e:
                logger.debug("Suppressed: %s", _e)

            with DatabaseContext(self.db, auto_commit=False) as cur:
                # Main client data
                cur.execute(
                    """
                    SELECT client_id, company_name, client_name, primary_phone,
                    email, address_line1,
                           first_name, last_name, parent_client_id,
                           corporate_role, is_company,
                           contract_charter_reserve,
                           city, province, zip_code
                    FROM clients
                    WHERE client_id = %s
                """,
                    (self.client_id,),
                )
                client = cur.fetchone()
                if client:
                    (
                        _cid,
                        company,
                        name,
                        phone,
                        email,
                        addr,
                        first_name,
                        last_name,
                        parent_id,
                        role,
                        is_company_val,
                        contract_reserve,
                        city_val,
                        province_val,
                        postal_val,
                    ) = client

                    is_company = bool(is_company_val) if is_company_val is not None else False
                    is_child = int(parent_id or 0) > 0

                    self.company_name.setText(str(company or ""))
                    self.client_name.setText(str(name or ""))
                    self.phone.setText(str(phone or ""))
                    self.email.setText(str(email or ""))
                    self.address.setPlainText(str(addr or ""))

                    # Parse client_name to extract first/last name if not a
                    # company
                    if not is_company:
                        # If client_name is in "Last, First" format, parse it
                        client_name_str = str(name or "").strip()
                        if "," in client_name_str:
                            parts = client_name_str.split(",", 1)
                            parsed_last = parts[0].strip()
                            parsed_first = parts[1].strip() if len(parts) > 1 else ""
                            self.last_name.setText(parsed_last)
                            self.first_name.setText(parsed_first)
                        else:
                            # Otherwise use stored first/last or assume last
                            # name
                            # only
                            self.first_name.setText(str(first_name or ""))
                            self.last_name.setText(str(last_name or client_name_str))

                        # Show first/last name fields for individuals/children
                        self.first_name.setVisible(True)
                        self.last_name.setVisible(True)
                    else:
                        # Hide first/last name fields for companies
                        self.first_name.setVisible(False)
                        self.last_name.setVisible(False)
                        # For companies, clear these fields
                        self.first_name.setText("")
                        self.last_name.setText("")

                    self.city.setText(str(city_val or ""))
                    self.province.setText(str(province_val or ""))
                    self.postal.setText(str(postal_val or ""))

                    self.corporate_parent_id.setValue(int(parent_id or 0))
                    self.is_company.setChecked(is_company)
                    if role:
                        idx = self.corporate_role.findText(str(role))
                        if idx >= 0:
                            self.corporate_role.setCurrentIndex(idx)
                    self.is_corporate.setChecked(is_child)

                    # Contract charter
                    cr = contract_reserve or ""
                    self.contract_charter_input.setText(cr)
                    self.is_contract_client.setChecked(bool(cr))

                # Clear tab content placeholders and defer section-specific
                # loads until each tab is actually opened.
                self.charter_table.setRowCount(0)
                self.payment_table.setRowCount(0)
                self.total_charters.setText("Total Charters: 0")
                self.total_revenue.setText("Total Revenue: $0.00")
                self.avg_charter_value.setText("Avg Charter: $0.00")
                self.total_paid.setText("Total Paid: $0.00")
                self.outstanding_balance.setText("Outstanding: $0.00")
                self.unapplied_credit.setText("Unapplied Credit: $0.00")
                self.escrow_held.setText("Escrow Held: $0.00")
                self.refund_held.setText("Refund Held: $0.00")
                self.overdue_amount.setText("Overdue: $0.00")

                self._deferred_sections_loaded.clear()
                self._load_deferred_section_for_tab(self.tabs.currentIndex())

            elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
            logger.info(
                "ClientDetailDialog base load completed in %sms for client_id=%s",
                elapsed_ms,
                self.client_id,
            )

        except Exception as e:
            logger.error(f"Failed to load client data: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load client data: {e}")

    def _load_documents(self) -> None:
        self.doc_list.clear()
        self.doc_list.addItem("📄 Service Agreement.pdf")
        self.doc_list.addItem("📄 Credit Application.pdf")

    def _load_charter_history(self) -> None:
        if not self.client_id:
            self.charter_table.setRowCount(0)
            return

        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT c.charter_date, c.reserve_number, c.pickup_address,
                       c.dropoff_address,
                       e.full_name, v.vehicle_number, c.total_amount_due
                FROM charters c
                LEFT JOIN employees e ON c.employee_id = e.employee_id
                LEFT JOIN vehicles v ON c.vehicle_id = v.vehicle_id
                WHERE c.client_id = %s
                ORDER BY c.charter_date DESC
                LIMIT 100
                """,
                (self.client_id,),
            )
            charter_rows = cur.fetchall() or []

        self.charter_table.setRowCount(len(charter_rows))
        total_rev = 0.0
        for i, (c_date, res, pickup, dest, driver, veh, amount) in enumerate(charter_rows):
            self.charter_table.setItem(i, 0, QTableWidgetItem(str(c_date)))
            self.charter_table.setItem(i, 1, QTableWidgetItem(str(res)))
            self.charter_table.setItem(i, 2, QTableWidgetItem(str(pickup or "")))
            self.charter_table.setItem(i, 3, QTableWidgetItem(str(dest or "")))
            self.charter_table.setItem(i, 4, QTableWidgetItem(str(driver or "")))
            self.charter_table.setItem(i, 5, QTableWidgetItem(str(veh or "")))
            self.charter_table.setItem(
                i,
                6,
                QTableWidgetItem(f"${float(amount or 0): ,.2f} "),
            )
            self.charter_table.setItem(i, 7, QTableWidgetItem("Complete"))
            total_rev += float(amount or 0)

        self.total_charters.setText(f"Total Charters: {len(charter_rows)}")
        self.total_revenue.setText(f"Total Revenue: ${total_rev:,.2f}")
        if charter_rows:
            self.avg_charter_value.setText(f"Avg Charter: ${total_rev / len(charter_rows):,.2f}")
        else:
            self.avg_charter_value.setText("Avg Charter: $0.00")

    def _load_payment_history(self) -> None:
        if not self.client_id:
            self.payment_table.setRowCount(0)
            return

        self._ensure_unapplied_payments_table()

        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT
                    payment_date,
                    reserve_number,
                    amount,
                    payment_method,
                    reference
                FROM (
                    SELECT
                        DATE(cp.payment_date) AS payment_date,
                        c.reserve_number,
                        cp.amount,
                        cp.payment_method,
                        COALESCE(cp.source, '') AS reference
                    FROM charters c
                    JOIN charter_payments cp ON (
                        CAST(cp.charter_id AS TEXT) = c.reserve_number
                        OR CAST(cp.charter_id AS TEXT) = CAST(c.charter_id AS TEXT)
                    )
                    WHERE c.client_id = %s

                    UNION ALL

                    SELECT
                        DATE(lp.payment_date) AS payment_date,
                        c.reserve_number,
                        lp.amount,
                        lp.payment_method,
                        COALESCE(lp.reference_number, '') AS reference
                    FROM charters c
                    JOIN payments lp ON (
                        lp.reserve_number = c.reserve_number
                        OR CAST(lp.charter_id AS TEXT) = CAST(c.charter_id AS TEXT)
                    )
                    WHERE c.client_id = %s
                      AND NOT EXISTS (
                          SELECT 1
                          FROM charter_payments cp2
                          WHERE CAST(cp2.charter_id AS TEXT) = c.reserve_number
                             OR CAST(cp2.charter_id AS TEXT) = CAST(c.charter_id AS TEXT)
                      )
                ) all_payments
                ORDER BY payment_date DESC NULLS LAST
                LIMIT 200
                """,
                (self.client_id, self.client_id),
            )
            payment_rows = cur.fetchall() or []

            cur.execute(
                """
                SELECT
                    payment_date,
                    amount,
                    remaining_amount,
                    payment_method,
                    COALESCE(reference, ''),
                                        COALESCE(notes, ''),
                                        COALESCE(hold_type, 'credit')
                FROM client_unapplied_payments
                WHERE client_id = %s
                  AND COALESCE(remaining_amount, 0) > 0
                ORDER BY payment_date DESC, id DESC
                LIMIT 200
                """,
                (self.client_id,),
            )
            unapplied_rows = cur.fetchall() or []

            cur.execute(
                """
                SELECT COALESCE(SUM(total_amount_due), 0)
                FROM charters
                WHERE client_id = %s
                """,
                (self.client_id,),
            )
            totals_row = cur.fetchone() or (0,)

        self.payment_table.setRowCount(len(payment_rows) + len(unapplied_rows))
        for i, (p_date, res, amt, method, ref) in enumerate(payment_rows):
            self.payment_table.setItem(i, 0, QTableWidgetItem(str(p_date)))
            self.payment_table.setItem(i, 1, QTableWidgetItem(str(res)))
            self.payment_table.setItem(i, 2, QTableWidgetItem(f"${float(amt or 0):,.2f}"))
            self.payment_table.setItem(i, 3, QTableWidgetItem(str(method or "")))
            self.payment_table.setItem(i, 4, QTableWidgetItem(str(ref or "")))
            self.payment_table.setItem(i, 5, QTableWidgetItem("Yes"))
            self.payment_table.setItem(i, 6, QTableWidgetItem(""))

        offset = len(payment_rows)
        held_credit_total = 0.0
        held_escrow_total = 0.0
        held_refund_total = 0.0
        for j, (p_date, amt, rem_amt, method, ref, notes, hold_type) in enumerate(unapplied_rows):
            row_idx = offset + j
            normalized_hold_type = str(hold_type or "credit").strip().lower()
            reserve_label = "# UNAPPLIED"
            if normalized_hold_type == "escrow":
                reserve_label = "# ESCROW_HELD"
                held_escrow_total += float(rem_amt or amt or 0)
            elif normalized_hold_type == "refund":
                reserve_label = "# REFUND_HELD"
                held_refund_total += float(rem_amt or amt or 0)
            else:
                held_credit_total += float(rem_amt or amt or 0)
            self.payment_table.setItem(row_idx, 0, QTableWidgetItem(str(p_date)))
            self.payment_table.setItem(row_idx, 1, QTableWidgetItem(reserve_label))
            self.payment_table.setItem(
                row_idx,
                2,
                QTableWidgetItem(f"${float(rem_amt or amt or 0):,.2f}"),
            )
            self.payment_table.setItem(row_idx, 3, QTableWidgetItem(str(method or "")))
            self.payment_table.setItem(row_idx, 4, QTableWidgetItem(str(ref or "")))
            self.payment_table.setItem(row_idx, 5, QTableWidgetItem("Held"))
            self.payment_table.setItem(row_idx, 6, QTableWidgetItem(str(notes or "")))

        total_due = float(totals_row[0] or 0)
        total_paid = sum(float(row[2] or 0) for row in payment_rows)
        unapplied_credit = held_credit_total + held_escrow_total + held_refund_total
        outstanding = total_due - total_paid
        net_outstanding = max(0.0, outstanding - unapplied_credit)
        self.total_paid.setText(f"Total Paid: ${total_paid:,.2f}")
        self.outstanding_balance.setText(f"Outstanding: ${outstanding:,.2f} (Net ${net_outstanding:,.2f})")
        self.unapplied_credit.setText(f"Unapplied Credit: ${held_credit_total:,.2f}")
        self.escrow_held.setText(f"Escrow Held: ${held_escrow_total:,.2f}")
        self.refund_held.setText(f"Refund Held: ${held_refund_total:,.2f}")
        self.overdue_amount.setText("Overdue: $0.00")

    def _load_metrics_summary(self) -> None:
        if not self.client_id:
            self.lifetime_value.setValue(0)
            self.avg_monthly_revenue.setValue(0)
            self.first_charter_date.setText("N/A")
            self.charter_frequency.setText("0 charters/month")
            return

        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT
                    COALESCE(SUM(total_amount_due), 0) AS total_revenue,
                    COUNT(*) AS charter_count,
                    MIN(charter_date) AS first_charter
                FROM charters
                WHERE client_id = %s
                """,
                (self.client_id,),
            )
            row = cur.fetchone() or (0, 0, None)

        total_revenue = float(row[0] or 0)
        charter_count = int(row[1] or 0)
        first_charter = row[2]

        self.lifetime_value.setValue(total_revenue)
        self.avg_monthly_revenue.setValue(total_revenue / 12 if charter_count else 0)
        self.first_charter_date.setText(str(first_charter or "N/A"))
        self.charter_frequency.setText(f"{charter_count} charters total")

    def _load_deferred_section_for_tab(self, tab_index: int) -> None:
        if self._is_initializing:
            return
        if tab_index in self._deferred_sections_loaded:
            return

        try:
            if tab_index == self.TAB_INDEX_CHARTER_HISTORY:
                self._load_charter_history()
            elif tab_index == self.TAB_INDEX_PAYMENTS:
                self._load_payment_history()
            elif tab_index == self.TAB_INDEX_PREFERENCES:
                self._load_favorites()
            elif tab_index == self.TAB_INDEX_COMMUNICATIONS:
                self._load_communications()
            elif tab_index == self.TAB_INDEX_DOCUMENTS:
                self._load_documents()
            elif tab_index == self.TAB_INDEX_DISPUTES:
                self._load_disputes()
            elif tab_index == self.TAB_INDEX_METRICS:
                self._load_metrics_summary()
            else:
                return

            self._deferred_sections_loaded.add(tab_index)
        except Exception:
            logger.exception(
                "Deferred section load failed for tab index %s", tab_index
            )

    @pyqtSlot()
    def refresh_client_dashboard(self) -> None:
        """Reload all tabs for this client from the latest DB state."""
        self.load_client_data()

    @pyqtSlot()
    def save_client(self) -> None:
        """Save all client changes"""
        try:
            # Get corporate role value
            corporate_role = self.corporate_role.currentText()
            if corporate_role == "None":
                corporate_role = None

            # Auto-generate client_name: company_name if set, else "last_name,
            # first_name"
            company = self.company_name.text().strip()
            first = self.first_name.text().strip()
            last = self.last_name.text().strip()

            if company:
                # Company name takes precedence
                auto_client_name = company
            elif first or last:
                # Generate from first/last: "Last, First"
                if first and last:
                    auto_client_name = f"{last}, {first}"
                elif last:
                    auto_client_name = last
                else:
                    auto_client_name = first
            else:
                auto_client_name = self.client_name.text().strip()

            with DatabaseContext(self.db, auto_commit=True) as cur:
                if self.client_id:
                    cur.execute(
                        """
                        UPDATE clients SET
                            company_name = %s,
                            client_name = %s,
                            primary_phone = %s,
                            email = %s,
                            address_line1 = %s,
                            city = %s,
                            province = %s,
                            zip_code = %s,
                            first_name = %s,
                            last_name = %s,
                            parent_client_id = %s,
                            corporate_role = %s,
                            is_company = %s,
                            contract_charter_reserve = %s
                        WHERE client_id = %s
                    """,
                        (
                            company,
                            auto_client_name,
                            self.phone.text().strip() or None,
                            self.email.text(),
                            self.address.toPlainText(),
                            self.city.text().strip() or None,
                            self.province.text().strip() or None,
                            self.postal.text().strip() or None,
                            first,
                            last,
                            self.corporate_parent_id.value(),
                            corporate_role,
                            self.is_company.isChecked(),
                            self.contract_charter_input.text().strip() or None,
                            self.client_id,
                        ),
                    )
                else:
                    created = None
                    last_error = None
                    for attempt in range(3):
                        new_account_number = _next_client_account_number(cur)
                        cur.execute("SAVEPOINT client_insert")
                        try:
                            cur.execute(
                                """
                                INSERT INTO clients (
                                    account_number,
                                    company_name,
                                    client_name,
                                    primary_phone,
                                    email,
                                    address_line1,
                                    city,
                                    province,
                                    zip_code,
                                    first_name,
                                    last_name,
                                    parent_client_id,
                                    corporate_role,
                                    is_company,
                                    contract_charter_reserve,
                                    created_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, NOW())
                                RETURNING client_id
                            """,
                                (
                                    new_account_number,
                                    company,
                                    auto_client_name,
                                    self.phone.text().strip() or None,
                                    self.email.text(),
                                    self.address.toPlainText(),
                                    self.city.text().strip() or None,
                                    self.province.text().strip() or None,
                                    self.postal.text().strip() or None,
                                    first,
                                    last,
                                    self.corporate_parent_id.value() or None,
                                    corporate_role,
                                    self.is_company.isChecked(),
                                    self.contract_charter_input.text().strip() or None,
                                ),
                            )
                            created = cur.fetchone()
                            cur.execute("RELEASE SAVEPOINT client_insert")
                            last_error = None
                            break
                        except psycopg2.Error as insert_error:
                            cur.execute("ROLLBACK TO SAVEPOINT client_insert")
                            last_error = insert_error
                            if (
                                attempt < 2
                                and _is_account_number_unique_violation(insert_error)
                            ):
                                continue
                            raise

                    if last_error is not None:
                        raise last_error

                    self.client_id = int(created[0]) if created else None
                    self.setWindowTitle(f"Client Detail - {self.client_id or 'New'}")

            QMessageBox.information(self, "Success", "Client saved successfully")
            self.saved.emit({"action": "save", "client_id": self.client_id})
        except Exception as e:
            logger.error(f"Failed to save client: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def _view_contract_charter(self) -> None:
        """Open the contract charter for viewing."""
        reserve = self.contract_charter_input.text().strip()
        if not reserve:
            QMessageBox.information(
                self, "No Contract Charter", "Enter a contract charter reserve number first."
            )
            return
        try:
            from charter_form_widget import CharterFormWidget

            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (reserve,))
                row = cur.fetchone()
            if not row:
                QMessageBox.warning(
                    self, "Not Found", f"Charter with reserve # {reserve} was not found."
                )
                return
            charter_id = row[0]
            self._exec_charter_form(
                CharterFormWidget,
                title=f"Charter #{reserve}",
                charter_id=charter_id,
            )
        except Exception as e:
            logger.error(f"Failed to open contract charter: {e}")
            QMessageBox.critical(self, "Error", f"Could not open charter: {e}")

    @pyqtSlot()
    def add_new_client(self) -> None:
        """Create a new client - open dialog with no client_id"""
        reply = QMessageBox.question(
            self,
            "Add New Client",
            "Create a new client record?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            new_dialog = ClientDetailDialog(self.db, client_id=None, parent=self.parent())
            new_dialog.saved.connect(self.on_client_saved)
            new_dialog.exec()

    @pyqtSlot()
    def duplicate_client(self) -> None:
        """Duplicate current client with modified name"""
        if not self.client_id:
            QMessageBox.warning(self, "Warning", "No client loaded to duplicate.")
            return

        # Collect current client data
        try:
            _new_name, _ok = QLineEdit().text(), False
            dialog = QDialog(self)
            dialog.setWindowTitle("Duplicate Client")
            dialog.setGeometry(100, 100, 400, 150)

            dlg_layout = QVBoxLayout()
            dlg_layout.addWidget(QLabel("Enter a new name for the duplicate client:"))

            name_input = QLineEdit()
            name_input.setText(self.client_name.text() + " (Copy)")
            dlg_layout.addWidget(name_input)

            btn_layout = QHBoxLayout()
            ok_btn = QPushButton("Duplicate")
            ok_btn.clicked.connect(dialog.accept)
            cancel_btn = QPushButton("Cancel")
            cancel_btn.clicked.connect(dialog.reject)
            btn_layout.addStretch()
            btn_layout.addWidget(ok_btn)
            btn_layout.addWidget(cancel_btn)
            dlg_layout.addLayout(btn_layout)

            dialog.setLayout(dlg_layout)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_name = name_input.text().strip()
                if not new_name:
                    QMessageBox.warning(
                        self,
                        "Warning",
                        "Please enter a name for the duplicate client.",
                    )
                    return

                # Insert duplicate record
                with DatabaseContext(self.db, auto_commit=True) as cur:
                    cur.execute(
                        """
                        INSERT INTO clients (company_name, client_name,
                        primary_phone, email, address_line1, first_name,
                        last_name, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                        (
                            new_name,
                            new_name,
                            self.phone.text(),
                            self.email.text(),
                            self.address.toPlainText(),
                            self.first_name.text(),
                            self.last_name.text(),
                        ),
                    )

                QMessageBox.information(self, "Success", f"Client duplicated as '{new_name}'.")
                self.load_client_data()
        except Exception as e:
            logger.error(f"Failed to duplicate client: {e}")
            QMessageBox.critical(self, "Error", f"Failed to duplicate: {e}")

    @pyqtSlot()
    def delete_client(self) -> None:
        """Delete current client after confirmation"""
        if not self.client_id:
            QMessageBox.warning(self, "Warning", "No client loaded to delete.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Delete client '{self.client_name.text()}'?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                with DatabaseContext(self.db, auto_commit=True) as cur:
                    cur.execute(
                        "DELETE FROM clients WHERE client_id = %s",
                        (self.client_id,),
                    )

                QMessageBox.information(self, "Success", "Client deleted successfully.")
                self.saved.emit({"action": "delete", "client_id": self.client_id})
                self.close()
            except Exception as e:
                logger.error(f"Failed to delete client: {e}")
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")

    def on_client_saved(self, data) -> None:
        """Handle child dialog save - refresh current view"""
        if self.client_id:
            self.load_client_data()

    # ===== STUB METHODS =====
    def _client_columns(self) -> set[str]:
        """Return available columns for clients table (schema-safe updates)."""
        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'clients'
            """
            )
            return {str(col) for (col,) in cur.fetchall()}

    def _set_client_active_state(
        self,
        status_value: str,
        is_active_value: bool,
        is_inactive_value: bool,
        success_message: str,
    ) -> None:
        if not self.client_id:
            QMessageBox.warning(self, "Warning", "No client loaded.")
            return

        try:
            columns = self._client_columns()
            set_clauses = []
            params: list[object] = []

            if "status" in columns:
                set_clauses.append("status = %s")
                params.append(status_value)
            if "is_active" in columns:
                set_clauses.append("is_active = %s")
                params.append(is_active_value)
            if "is_inactive" in columns:
                set_clauses.append("is_inactive = %s")
                params.append(is_inactive_value)
            if "updated_at" in columns:
                set_clauses.append("updated_at = NOW()")

            if not set_clauses:
                QMessageBox.warning(
                    self,
                    "Unavailable",
                    "No compatible status columns were found on clients table.",
                )
                return

            params.append(self.client_id)
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    f"UPDATE clients SET {', '.join(set_clauses)} WHERE client_id = %s",
                    tuple(params),
                )

            display_status = status_value.capitalize()
            status_idx = self.client_status.findText(display_status)
            if status_idx >= 0:
                self.client_status.setCurrentIndex(status_idx)

            QMessageBox.information(self, "Success", success_message)
            self.load_client_data()
        except Exception as e:
            logger.error("Failed to update client status: %s", e)
            QMessageBox.critical(self, "Error", f"Failed to update status: {e}")

    def _ensure_client_drilldown_tables(self) -> None:
        with DatabaseContext(self.db, auto_commit=True) as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS client_favorite_drivers (
                    favorite_id SERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL,
                    employee_id INTEGER,
                    driver_name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS client_favorite_vehicles (
                    favorite_id SERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL,
                    vehicle_id INTEGER,
                    vehicle_label VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS client_communications (
                    communication_id SERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL,
                    communication_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    communication_type VARCHAR(30) NOT NULL,
                    subject VARCHAR(255),
                    status VARCHAR(30) DEFAULT 'logged',
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS client_disputes (
                    dispute_id SERIAL PRIMARY KEY,
                    client_id INTEGER NOT NULL,
                    dispute_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    charter_number VARCHAR(50),
                    issue_type VARCHAR(100),
                    amount NUMERIC(12,2),
                    status VARCHAR(30) DEFAULT 'open',
                    resolution TEXT,
                    resolved_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """
            )

    def _load_favorites(self) -> None:
        self.fav_drivers_list.clear()
        self.fav_vehicles_list.clear()
        if not self.client_id:
            return
        try:
            self._ensure_client_drilldown_tables()
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT favorite_id, driver_name
                    FROM client_favorite_drivers
                    WHERE client_id = %s
                    ORDER BY driver_name
                """,
                    (self.client_id,),
                )
                for fav_id, driver_name in cur.fetchall() or []:
                    item = QTableWidgetItem(str(driver_name or ""))
                    item.setData(Qt.ItemDataRole.UserRole, int(fav_id))
                    self.fav_drivers_list.addItem(item.text())
                    self.fav_drivers_list.item(self.fav_drivers_list.count() - 1).setData(
                        Qt.ItemDataRole.UserRole, int(fav_id)
                    )

                cur.execute(
                    """
                    SELECT favorite_id, vehicle_label
                    FROM client_favorite_vehicles
                    WHERE client_id = %s
                    ORDER BY vehicle_label
                """,
                    (self.client_id,),
                )
                for fav_id, vehicle_label in cur.fetchall() or []:
                    self.fav_vehicles_list.addItem(str(vehicle_label or ""))
                    self.fav_vehicles_list.item(self.fav_vehicles_list.count() - 1).setData(
                        Qt.ItemDataRole.UserRole, int(fav_id)
                    )
        except Exception:
            logger.exception("Failed to load client favorites")

    def _load_communications(self) -> None:
        self.comm_table.setRowCount(0)
        if not self.client_id:
            return
        try:
            self._ensure_client_drilldown_tables()
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT communication_id, communication_at,
                           communication_type, subject, status, notes
                    FROM client_communications
                    WHERE client_id = %s
                    ORDER BY communication_at DESC, communication_id DESC
                    LIMIT 200
                """,
                    (self.client_id,),
                )
                rows = cur.fetchall() or []

            self.comm_table.setRowCount(len(rows))
            for row_idx, (
                comm_id,
                comm_at,
                comm_type,
                subject,
                status,
                notes,
            ) in enumerate(rows):
                dt_item = QTableWidgetItem(str(comm_at or ""))
                dt_item.setData(Qt.ItemDataRole.UserRole, int(comm_id))
                self.comm_table.setItem(row_idx, 0, dt_item)
                self.comm_table.setItem(row_idx, 1, QTableWidgetItem(str(comm_type or "")))
                self.comm_table.setItem(row_idx, 2, QTableWidgetItem(str(subject or "")))
                self.comm_table.setItem(row_idx, 3, QTableWidgetItem(str(status or "")))
                self.comm_table.setItem(row_idx, 4, QTableWidgetItem(str(notes or "")))
        except Exception:
            logger.exception("Failed to load communications")

    def _load_disputes(self) -> None:
        self.dispute_table.setRowCount(0)
        if not self.client_id:
            return
        try:
            self._ensure_client_drilldown_tables()
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT dispute_id, dispute_date, charter_number,
                           issue_type, amount, status, resolution
                    FROM client_disputes
                    WHERE client_id = %s
                    ORDER BY dispute_date DESC, dispute_id DESC
                    LIMIT 200
                """,
                    (self.client_id,),
                )
                rows = cur.fetchall() or []

            self.dispute_table.setRowCount(len(rows))
            for row_idx, (
                dispute_id,
                dispute_date,
                charter_number,
                issue_type,
                amount,
                status,
                resolution,
            ) in enumerate(rows):
                date_item = QTableWidgetItem(str(dispute_date or ""))
                date_item.setData(Qt.ItemDataRole.UserRole, int(dispute_id))
                self.dispute_table.setItem(row_idx, 0, date_item)
                self.dispute_table.setItem(row_idx, 1, QTableWidgetItem(str(charter_number or "")))
                self.dispute_table.setItem(row_idx, 2, QTableWidgetItem(str(issue_type or "")))
                self.dispute_table.setItem(
                    row_idx,
                    3,
                    QTableWidgetItem(f"${float(amount or 0):,.2f}" if amount is not None else ""),
                )
                self.dispute_table.setItem(row_idx, 4, QTableWidgetItem(str(status or "")))
                self.dispute_table.setItem(row_idx, 5, QTableWidgetItem(str(resolution or "")))
        except Exception:
            logger.exception("Failed to load disputes")

    @pyqtSlot()
    def suspend_client(self) -> None:
        if not self.client_id:
            QMessageBox.warning(self, "Warning", "No client loaded.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Suspend",
            f"Suspend client '{self.client_name.text().strip() or self.client_id}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._set_client_active_state(
            status_value="suspended",
            is_active_value=False,
            is_inactive_value=True,
            success_message="Client suspended successfully.",
        )

    @pyqtSlot()
    def activate_client(self) -> None:
        if not self.client_id:
            QMessageBox.warning(self, "Warning", "No client loaded.")
            return

        self._set_client_active_state(
            status_value="active",
            is_active_value=True,
            is_inactive_value=False,
            success_message="Client activated successfully.",
        )

    @pyqtSlot()
    def link_child_account(self) -> None:
        """Link another client as a child account (subsidiary) of this"
        "company"""

        if not self.client_id:
            QMessageBox.warning(
                self,
                "Warning",
                "Load a client first before linking child accounts",
            )
            return

        # Dialog to select child client
        dialog = QDialog(self)
        dialog.setWindowTitle("Link Child Account")
        dialog.setGeometry(100, 100, 500, 300)

        layout = QVBoxLayout()

        # Instructions
        layout.addWidget(
            QLabel(
                "Select a client to link as a child account:\n(This client "
                "becomes a subsidiary of the current company)"
            )
        )

        # Search/select field
        search_input = QLineEdit()
        search_input.setPlaceholderText("Search by client name, ID, or company...")
        layout.addWidget(search_input)

        # Client list
        client_list = QListWidget()
        layout.addWidget(client_list)

        def load_available_clients(search_text="") -> None:
            """Load clients that can be linked as children (not already"
            "children)"""

            try:
                with DatabaseContext(self.db, auto_commit=False) as cur:
                    # Only independent clients
                    where = "WHERE parent_client_id = 0" " OR parent_client_id IS NULL"
                    params = []

                    if search_text:
                        where += (
                            " AND (client_name ILIKE %s"
                            " OR company_name ILIKE %s"
                            " OR client_id = %s)"
                        )
                        params = [
                            f"%{search_text} %",
                            f"%{search_text} %",
                            search_text.split()[-1] if search_text else "",
                        ]

                    cur.execute(
                        """
                        SELECT client_id, client_name, company_name
                        FROM clients
                        {where}
                        ORDER BY COALESCE(company_name, client_name)
                        LIMIT 100
                    """,
                        params if search_text else [],
                    )
                    rows = cur.fetchall()

                client_list.clear()
                for cid, cname, ccompany in rows:
                    display = f"[{cid}] {ccompany or cname}"
                    (QListWidget.item_type() if hasattr(QListWidget, "item_type") else None)
                    client_list.addItem(display)
                    client_list.item(client_list.count() - 1).setData(Qt.ItemDataRole.UserRole, cid)

            except Exception as e:
                logger.error(f"Failed to load clients: {e}")
                QMessageBox.warning(dialog, "Error", f"Failed to load clients: {e}")

        # Load initial list
        load_available_clients()

        # Search connection
        search_input.textChanged.connect(lambda: load_available_clients(search_input.text()))

        # Buttons
        btn_layout = QHBoxLayout()

        link_btn = QPushButton("Link as Child")

        def do_link() -> None:
            item = client_list.currentItem()
            if not item:
                QMessageBox.warning(dialog, "Warning", "Select a client to link")
                return

            child_id = item.data(Qt.ItemDataRole.UserRole)
            try:
                with DatabaseContext(self.db, auto_commit=True) as cur:
                    cur.execute(
                        """
                        UPDATE clients
                        SET parent_client_id = %s
                        WHERE client_id = %s
                    """,
                        (self.client_id, child_id),
                    )

                QMessageBox.information(
                    dialog,
                    "Success",
                    f"Client {child_id} linked as child account",
                )
                dialog.accept()
            except Exception as e:
                logger.error(f"Failed to link client: {e}")
                QMessageBox.critical(dialog, "Error", f"Failed to link: {e}")

        link_btn.clicked.connect(do_link)
        btn_layout.addWidget(link_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)
        dialog.setLayout(layout)
        dialog.exec()

    def on_is_company_toggled(self) -> None:
        """Show/hide first/last name fields based on is_company checkbox"""
        is_company = self.is_company.isChecked()

        if is_company:
            # Company: hide first/last name, clear them
            self.first_name.setVisible(False)
            self.last_name.setVisible(False)
            self.first_name.setText("")
            self.last_name.setText("")
        else:
            # Individual/Child: show first/last name
            self.first_name.setVisible(True)
            self.last_name.setVisible(True)

    def open_charter_detail(self, index) -> None:
        try:
            row = index.row() if index is not None else -1
            if row < 0:
                QMessageBox.information(self, "Open Charter", "Select a charter first.")
                return

            reserve_item = self.charter_table.item(row, 1)
            reserve_number = reserve_item.text().strip() if reserve_item else ""
            if not reserve_number:
                QMessageBox.warning(self, "Open Charter", "Missing reserve number for selected row.")
                return
            self._open_charter_by_reserve(reserve_number)
        except Exception as e:
            logger.error("Failed to open charter detail: %s", e)
            QMessageBox.critical(self, "Error", f"Could not open charter: {e}")

    def open_payment_charter_detail(self, index) -> None:
        """Open the charter associated with a posted payment row."""
        try:
            row = index.row() if index is not None else -1
            if row < 0:
                QMessageBox.information(self, "Open Charter", "Select a payment first.")
                return
            reserve_item = self.payment_table.item(row, 1)
            reserve_number = reserve_item.text().strip() if reserve_item else ""
            if not reserve_number:
                QMessageBox.warning(self, "Open Charter", "This payment has no reserve number.")
                return
            if reserve_number.startswith("#"):
                QMessageBox.information(
                    self,
                    "Held Payment",
                    "This is held client money and is not attached to a charter.",
                )
                return
            self._open_charter_by_reserve(reserve_number)
        except Exception as e:
            logger.error("Failed to open payment charter detail: %s", e)
            QMessageBox.critical(self, "Error", f"Could not open charter: {e}")

    def _open_charter_by_reserve(self, reserve_number: str) -> None:
        """Open a charter form in a modal host dialog."""
        try:
            from charter_form_widget import CharterFormWidget

            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    "SELECT charter_id FROM charters WHERE reserve_number = %s LIMIT 1",
                    (reserve_number,),
                )
                row_data = cur.fetchone()

            if not row_data:
                QMessageBox.warning(
                    self,
                    "Not Found",
                    f"Charter {reserve_number} was not found.",
                )
                return

            charter_id = int(row_data[0])
            self._exec_charter_form(
                CharterFormWidget,
                title=f"Charter #{reserve_number}",
                charter_id=charter_id,
            )
            self.load_client_data()
        except Exception as e:
            logger.error("Failed to open charter detail: %s", e)
            QMessageBox.critical(self, "Error", f"Could not open charter: {e}")

    def _exec_charter_form(self, form_class, title: str, **form_kwargs) -> None:
        """Host the tab-oriented charter widget in a modal drill-down dialog."""
        class _GuardedCharterDialog(QDialog):
            def reject(host_dialog) -> None:
                form = getattr(host_dialog, "charter_form", None)
                if form is None or form._guard_dirty():
                    super().reject()

        dlg = _GuardedCharterDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(1500, 900)
        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setContentsMargins(0, 0, 0, 0)
        charter_form = form_class(self.db, parent=dlg, **form_kwargs)
        dlg.charter_form = charter_form
        charter_form.close_requested.connect(dlg.accept)
        dlg_layout.addWidget(charter_form)
        try:
            dlg.exec()
        finally:
            autosave_timer = getattr(charter_form, "_autosave_timer", None)
            if autosave_timer is not None:
                autosave_timer.stop()
            charter_form.deleteLater()
            dlg.deleteLater()

    @pyqtSlot()
    def new_charter(self) -> None:
        if not self.client_id:
            QMessageBox.warning(self, "Warning", "No client loaded.")
            return

        try:
            from charter_form_widget import CharterFormWidget

            self._exec_charter_form(
                CharterFormWidget,
                title="New Charter",
                client_id=self.client_id,
            )
            self.load_client_data()
        except Exception as e:
            logger.error("Failed to open new charter form: %s", e)
            QMessageBox.critical(self, "Error", f"Could not open charter form: {e}")

    @pyqtSlot()
    def record_payment(self) -> None:
        if not self.client_id:
            QMessageBox.warning(self, "Warning", "No client loaded.")
            return

        self._ensure_unapplied_payments_table()

        selected_rows = []
        model = self.charter_table.selectionModel()
        if model is not None:
            selected_rows = sorted({idx.row() for idx in model.selectedRows()})

        if not selected_rows:
            reply = QMessageBox.question(
                self,
                "Record Client Payment",
                "No charter is selected.\n\n"
                "Yes: Hold payment as unapplied credit\n"
                "No: Select date range and spread payment by balances owing\n"
                "Cancel: Do nothing",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                if self._record_advance_payment_hold():
                    self.load_client_data()
                return
            if reply == QMessageBox.StandardButton.No:
                if self._record_bulk_payment_by_date_range():
                    self.load_client_data()
            return

        reserves = []
        for row in selected_rows:
            reserve_item = self.charter_table.item(row, 1)
            reserve_number = reserve_item.text().strip() if reserve_item else ""
            if reserve_number:
                reserves.append(reserve_number)

        if not reserves:
            QMessageBox.warning(
                self,
                "Error",
                "Could not determine reserve number for selected charter(s).",
            )
            return

        if len(reserves) > 1:
            reply = QMessageBox.question(
                self,
                "Multiple Charters Selected",
                (
                    f"You selected {len(reserves)} charters.\n\n"
                    "Yes: Allocate one payment across these charters\n"
                    "No: Open each charter payment manager one-by-one"
                ),
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return
            if reply == QMessageBox.StandardButton.Yes:
                if self._record_bulk_payment(reserves):
                    self.load_client_data()
                return

        for reserve_number in reserves:
            dlg = PaymentDialog(self.db, reserve_number, client_id=self.client_id, parent=self)
            dlg.exec()

        # Refresh payment table after dialog closes
        self.load_client_data()

    def _record_bulk_payment(self, reserves: list[str]) -> bool:
        """Allocate one client payment across multiple selected charters."""
        if not reserves:
            return False

        self._ensure_unapplied_payments_table()

        balances = self._fetch_outstanding_balances(reserves)
        if not balances:
            QMessageBox.warning(self, "No Balances", "Could not load selected charter balances.")
            return False

        dialog = QDialog(self)
        dialog.setWindowTitle("Bulk Client Payment Allocation")
        dialog.setGeometry(120, 120, 760, 560)

        layout = QVBoxLayout(dialog)
        layout.addWidget(
            QLabel(
                "Apply one payment and split it across selected charters. "
                "Only allocation rows with amount > 0 will be posted."
            )
        )

        top_form = QFormLayout()
        payment_date = QDateEdit()
        payment_date.setCalendarPopup(True)
        payment_date.setDate(QDate.currentDate())
        top_form.addRow("Payment Date:", payment_date)

        amount_input = QDoubleSpinBox()
        amount_input.setMaximum(99999999)
        amount_input.setDecimals(2)
        amount_input.setPrefix("$")
        total_outstanding = sum(float(v) for v in balances.values())
        amount_input.setValue(round(total_outstanding, 2) if total_outstanding > 0 else 0.0)
        top_form.addRow("Payment Amount:", amount_input)

        method_combo = QComboBox()
        method_combo.addItems(
            [
                "E-Transfer",
                "Credit Card",
                "Debit Card",
                "Cash",
                "Cheque",
                "Bank Transfer",
                "Deposit",
                "NRR Retainer",
                "Other",
            ]
        )
        top_form.addRow("Payment Method:", method_combo)

        reference_input = QLineEdit()
        reference_input.setPlaceholderText("e.g., transaction ID, check number")
        top_form.addRow("Reference:", reference_input)

        notes_input = QTextEdit()
        notes_input.setMaximumHeight(80)
        top_form.addRow("Notes:", notes_input)
        layout.addLayout(top_form)

        alloc_table = QTableWidget()
        alloc_table.setColumnCount(3)
        alloc_table.setHorizontalHeaderLabels(["Reserve #", "Outstanding", "Allocate"])
        alloc_table.setRowCount(0)

        allocation_widgets: list[QDoubleSpinBox] = []
        seen_reserves = {str(r) for r in reserves}

        total_label = QLabel()

        def _refresh_total_label() -> None:
            allocated = sum(float(w.value()) for w in allocation_widgets)
            payment_total = float(amount_input.value())
            diff = payment_total - allocated
            total_label.setText(
                f"Allocated: ${allocated:,.2f} | Payment: ${payment_total:,.2f} | Remaining: ${diff:,.2f}"
            )

        def _add_allocation_row(
            reserve: str,
            outstanding: float,
            default_allocate: float | None = None,
        ) -> None:
            reserve = str(reserve)
            outstanding = float(outstanding or 0.0)
            row_idx = alloc_table.rowCount()
            alloc_table.insertRow(row_idx)
            alloc_table.setItem(row_idx, 0, QTableWidgetItem(reserve))
            alloc_table.setItem(row_idx, 1, QTableWidgetItem(f"${outstanding:,.2f}"))

            alloc_spin = QDoubleSpinBox()
            alloc_spin.setDecimals(2)
            alloc_spin.setMaximum(max(outstanding, 0.0))
            alloc_spin.setPrefix("$")
            initial_alloc = max(outstanding, 0.0) if default_allocate is None else max(0.0, min(default_allocate, outstanding))
            alloc_spin.setValue(round(initial_alloc, 2))
            alloc_spin.valueChanged.connect(lambda _v: _refresh_total_label())
            alloc_table.setCellWidget(row_idx, 2, alloc_spin)

            allocation_widgets.append(alloc_spin)
            reserves.append(reserve)
            balances[reserve] = outstanding
            seen_reserves.add(reserve)

        base_reserves = list(reserves)
        reserves.clear()
        for reserve in base_reserves:
            _add_allocation_row(reserve, float(balances.get(reserve, 0.0) or 0.0))

        alloc_table.resizeColumnsToContents()
        layout.addWidget(alloc_table)

        amount_input.valueChanged.connect(lambda _v: _refresh_total_label())
        _refresh_total_label()
        layout.addWidget(total_label)

        button_row = QHBoxLayout()

        auto_fill_btn = QPushButton("Auto Fill by Outstanding")

        def _auto_fill() -> None:
            remaining = float(amount_input.value())
            for idx, reserve in enumerate(reserves):
                outstanding = float(balances.get(reserve, 0.0) or 0.0)
                alloc_value = max(0.0, min(outstanding, remaining))
                allocation_widgets[idx].setValue(round(alloc_value, 2))
                remaining -= alloc_value
            _refresh_total_label()

        auto_fill_btn.clicked.connect(_auto_fill)
        button_row.addWidget(auto_fill_btn)

        append_next_btn = QPushButton("Append Next Outstanding")

        def _append_next_outstanding() -> None:
            remaining = round(
                float(amount_input.value()) - sum(float(w.value()) for w in allocation_widgets),
                2,
            )
            if remaining <= 0.009:
                QMessageBox.information(
                    dialog,
                    "No Remaining Amount",
                    "There is no remaining payment amount to allocate.",
                )
                return

            next_reserves = self._fetch_next_outstanding_reserves(list(seen_reserves), limit=100)
            if not next_reserves:
                QMessageBox.information(
                    dialog,
                    "No Additional Outstanding",
                    "No more outstanding client charters were found to append.",
                )
                return

            added = 0
            for reserve, outstanding in next_reserves:
                if remaining <= 0.009:
                    break
                alloc_value = max(0.0, min(float(outstanding or 0.0), remaining))
                _add_allocation_row(str(reserve), float(outstanding or 0.0), alloc_value)
                remaining = round(remaining - alloc_value, 2)
                added += 1

            alloc_table.resizeColumnsToContents()
            _refresh_total_label()

            if added <= 0:
                QMessageBox.information(
                    dialog,
                    "No Rows Added",
                    "The next outstanding charters are already included in this allocation.",
                )

        append_next_btn.clicked.connect(_append_next_outstanding)
        button_row.addWidget(append_next_btn)
        button_row.addStretch()

        post_btn = QPushButton("Post Bulk Payment")
        cancel_btn = QPushButton("Cancel")
        button_row.addWidget(post_btn)
        button_row.addWidget(cancel_btn)
        layout.addLayout(button_row)

        posted = {"ok": False}

        def _post() -> None:
            payment_total = float(amount_input.value())
            if payment_total <= 0:
                QMessageBox.warning(dialog, "Invalid Amount", "Payment amount must be greater than $0.00.")
                return

            allocations: list[tuple[str, float]] = []
            for row_idx, reserve in enumerate(reserves):
                amount = float(allocation_widgets[row_idx].value())
                if amount > 0:
                    allocations.append((reserve, amount))

            if not allocations:
                QMessageBox.warning(dialog, "No Allocation", "Allocate at least one charter amount.")
                return

            allocated_total = round(sum(v for _, v in allocations), 2)
            if allocated_total - round(payment_total, 2) > 0.009:
                QMessageBox.warning(
                    dialog,
                    "Allocation Exceeds Payment",
                    "Allocated total cannot exceed the payment amount.",
                )
                return

            method_map = {
                "E-Transfer": "etransfer",
                "Credit Card": "credit_card",
                "Debit Card": "debit_card",
                "Cash": "cash",
                "Cheque": "cheque",
                "Bank Transfer": "bank_transfer",
                "Deposit": "deposit",
                "NRR Retainer": "nrr",
                "Other": "other",
            }
            method_val = method_map.get(method_combo.currentText(), "other")

            reference_txt = reference_input.text().strip()
            notes_txt = notes_input.toPlainText().strip()
            source_parts = ["bulk_client_payment"]
            if reference_txt:
                source_parts.append(reference_txt)
            if notes_txt:
                source_parts.append(notes_txt)
            source_val = " | ".join(source_parts)

            try:
                with DatabaseContext(self.db, auto_commit=True) as cur:
                    for reserve, alloc_amount in allocations:
                        cur.execute(
                            """
                            INSERT INTO charter_payments (
                                charter_id,
                                payment_date,
                                amount,
                                payment_method,
                                source,
                                imported_at
                            )
                            VALUES (%s, %s, %s, %s, %s, NOW())
                            """,
                            (
                                reserve,
                                payment_date.date().toPyDate(),
                                alloc_amount,
                                method_val,
                                source_val,
                            ),
                        )

                        # Keep charter payment summary columns in sync for UI summary widgets.
                        cur.execute(
                            """
                            UPDATE charters c
                            SET amount_paid = COALESCE(paid.total_paid, 0),
                                balance_owing = GREATEST(
                                    COALESCE(c.total_amount_due, 0) - COALESCE(paid.total_paid, 0),
                                    0
                                ),
                                updated_at = NOW()
                            FROM (
                                SELECT COALESCE(SUM(amount), 0) AS total_paid
                                FROM charter_payments
                                WHERE charter_id = %s
                            ) paid
                            WHERE c.reserve_number = %s
                            """,
                            (reserve, reserve),
                        )

                    remainder = round(payment_total - allocated_total, 2)
                    if remainder > 0.009:
                        self._insert_unapplied_payment_row(
                            cur=cur,
                            payment_date=payment_date.date().toPyDate(),
                            amount=remainder,
                            method_val=method_val,
                            reference_txt=reference_txt,
                            notes_txt=(
                                f"Bulk allocation remainder. {notes_txt}".strip()
                                if notes_txt
                                else "Bulk allocation remainder"
                            ),
                            source_val="bulk_payment_remainder",
                            hold_type="credit",
                        )
            except Exception as e:
                logger.error("Bulk payment post failed: %s", e)
                QMessageBox.critical(dialog, "Error", f"Failed to post bulk payment: {e}")
                return

            posted["ok"] = True
            QMessageBox.information(
                dialog,
                "Bulk Payment Posted",
                (
                    f"Posted ${allocated_total:,.2f} across {len(allocations)} charter(s).\n"
                    f"Unallocated remainder: ${round(payment_total - allocated_total, 2):,.2f}"
                ),
            )
            dialog.accept()

        post_btn.clicked.connect(_post)
        cancel_btn.clicked.connect(dialog.reject)

        _auto_fill()
        dialog.exec()
        return bool(posted["ok"])

    def _record_bulk_payment_by_date_range(self) -> bool:
        """Select outstanding charters by date range and spread payment proportionally."""
        self._ensure_unapplied_payments_table()

        dialog = QDialog(self)
        dialog.setWindowTitle("Date-Range Bulk Payment Allocation")
        dialog.setGeometry(120, 120, 860, 640)

        layout = QVBoxLayout(dialog)
        layout.addWidget(
            QLabel(
                "Select outstanding charters for this client by date range, then spread one "
                "payment proportionally by each charter's balance owing."
            )
        )

        filter_row = QHBoxLayout()
        start_date = QDateEdit()
        start_date.setCalendarPopup(True)
        start_date.setDate(QDate.currentDate().addYears(-2))
        end_date = QDateEdit()
        end_date.setCalendarPopup(True)
        end_date.setDate(QDate.currentDate())
        load_btn = QPushButton("Load Date Range")
        select_all_btn = QPushButton("Select All")
        clear_all_btn = QPushButton("Clear All")
        filter_row.addWidget(QLabel("From:"))
        filter_row.addWidget(start_date)
        filter_row.addWidget(QLabel("To:"))
        filter_row.addWidget(end_date)
        filter_row.addWidget(load_btn)
        filter_row.addWidget(select_all_btn)
        filter_row.addWidget(clear_all_btn)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        alloc_table = QTableWidget()
        alloc_table.setColumnCount(4)
        alloc_table.setHorizontalHeaderLabels(["Select", "Charter Date", "Reserve #", "Outstanding"])
        alloc_table.setRowCount(0)
        layout.addWidget(alloc_table)

        top_form = QFormLayout()
        payment_date = QDateEdit()
        payment_date.setCalendarPopup(True)
        payment_date.setDate(QDate.currentDate())
        top_form.addRow("Payment Date:", payment_date)

        amount_input = QDoubleSpinBox()
        amount_input.setMaximum(99999999)
        amount_input.setDecimals(2)
        amount_input.setPrefix("$")
        amount_input.setValue(0.0)
        top_form.addRow("Payment Amount:", amount_input)

        method_combo = QComboBox()
        method_combo.addItems(
            [
                "E-Transfer",
                "Credit Card",
                "Debit Card",
                "Cash",
                "Cheque",
                "Bank Transfer",
                "Deposit",
                "NRR Retainer",
                "Other",
            ]
        )
        top_form.addRow("Payment Method:", method_combo)

        reference_input = QLineEdit()
        reference_input.setPlaceholderText("e.g., transaction ID, check number")
        top_form.addRow("Reference:", reference_input)

        notes_input = QTextEdit()
        notes_input.setMaximumHeight(80)
        notes_input.setPlaceholderText(
            "Optional notes. You can deselect one or two charters that are not being paid in this run."
        )
        top_form.addRow("Notes:", notes_input)
        layout.addLayout(top_form)

        summary_label = QLabel("Selected: 0 | Selected Outstanding: $0.00")
        layout.addWidget(summary_label)

        rows_state: list[dict[str, object]] = []

        def _set_all_checked(value: bool) -> None:
            for row_idx in range(alloc_table.rowCount()):
                item = alloc_table.item(row_idx, 0)
                if item is not None:
                    item.setCheckState(Qt.CheckState.Checked if value else Qt.CheckState.Unchecked)
            _refresh_summary()

        def _refresh_summary() -> None:
            selected_count = 0
            selected_total = 0.0
            for row_idx, row_data in enumerate(rows_state):
                item = alloc_table.item(row_idx, 0)
                if item is None:
                    continue
                if item.checkState() == Qt.CheckState.Checked:
                    selected_count += 1
                    selected_total += float(row_data.get("outstanding") or 0.0)
            summary_label.setText(
                f"Selected: {selected_count} | Selected Outstanding: ${selected_total:,.2f}"
            )

        def _load_rows() -> None:
            py_start = start_date.date().toPyDate()
            py_end = end_date.date().toPyDate()
            outstanding_rows = self._fetch_outstanding_rows_by_date_range(py_start, py_end, limit=1000)
            rows_state.clear()
            alloc_table.setRowCount(0)
            for reserve, charter_date, outstanding in outstanding_rows:
                row_idx = alloc_table.rowCount()
                alloc_table.insertRow(row_idx)
                select_item = QTableWidgetItem("")
                select_item.setFlags(select_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                select_item.setCheckState(Qt.CheckState.Checked)
                alloc_table.setItem(row_idx, 0, select_item)
                alloc_table.setItem(row_idx, 1, QTableWidgetItem(str(charter_date or "")))
                alloc_table.setItem(row_idx, 2, QTableWidgetItem(str(reserve or "")))
                alloc_table.setItem(row_idx, 3, QTableWidgetItem(f"${float(outstanding or 0.0):,.2f}"))
                rows_state.append(
                    {
                        "reserve": str(reserve),
                        "charter_date": str(charter_date or ""),
                        "outstanding": float(outstanding or 0.0),
                    }
                )

            alloc_table.resizeColumnsToContents()
            _refresh_summary()
            if rows_state:
                amount_input.setValue(round(sum(float(r.get("outstanding") or 0.0) for r in rows_state), 2))

        def _build_proportional_allocations(payment_total: float) -> list[tuple[str, float]]:
            selected: list[dict[str, object]] = []
            for row_idx, row_data in enumerate(rows_state):
                item = alloc_table.item(row_idx, 0)
                if item is None:
                    continue
                if item.checkState() == Qt.CheckState.Checked:
                    outstanding = float(row_data.get("outstanding") or 0.0)
                    if outstanding > 0:
                        selected.append(row_data)

            if not selected:
                return []

            total_selected_outstanding = sum(float(row.get("outstanding") or 0.0) for row in selected)
            if total_selected_outstanding <= 0:
                return []

            distributable = min(float(payment_total), float(total_selected_outstanding))
            allocations: list[list[object]] = []
            rounded_sum = 0.0
            for row in selected:
                reserve = str(row.get("reserve") or "")
                outstanding = float(row.get("outstanding") or 0.0)
                raw = distributable * (outstanding / total_selected_outstanding)
                rounded = min(round(raw, 2), outstanding)
                allocations.append([reserve, outstanding, rounded])
                rounded_sum += rounded

            remaining_cents = int(round((distributable - rounded_sum) * 100))
            idx = 0
            while remaining_cents > 0 and allocations:
                reserve, outstanding, rounded = allocations[idx]
                candidate = round(float(rounded) + 0.01, 2)
                if candidate <= float(outstanding):
                    allocations[idx][2] = candidate
                    remaining_cents -= 1
                idx = (idx + 1) % len(allocations)

            return [
                (str(reserve), float(rounded))
                for reserve, _outstanding, rounded in allocations
                if float(rounded) > 0.0
            ]

        button_row = QHBoxLayout()
        post_btn = QPushButton("Post Proportional Allocation")
        cancel_btn = QPushButton("Cancel")
        button_row.addStretch()
        button_row.addWidget(post_btn)
        button_row.addWidget(cancel_btn)
        layout.addLayout(button_row)

        posted = {"ok": False}

        def _post() -> None:
            payment_total = round(float(amount_input.value() or 0.0), 2)
            if payment_total <= 0.0:
                QMessageBox.warning(dialog, "Invalid Amount", "Payment amount must be greater than $0.00.")
                return

            allocations = _build_proportional_allocations(payment_total)
            if not allocations:
                QMessageBox.warning(
                    dialog,
                    "No Selected Balances",
                    "Select one or more outstanding balances to allocate.",
                )
                return

            method_map = {
                "E-Transfer": "etransfer",
                "Credit Card": "credit_card",
                "Debit Card": "debit_card",
                "Cash": "cash",
                "Cheque": "cheque",
                "Bank Transfer": "bank_transfer",
                "Deposit": "deposit",
                "NRR Retainer": "nrr",
                "Other": "other",
            }
            method_val = method_map.get(method_combo.currentText(), "other")
            reference_txt = reference_input.text().strip()
            notes_txt = notes_input.toPlainText().strip()
            allocated_total = round(sum(amount for _, amount in allocations), 2)

            try:
                with DatabaseContext(self.db, auto_commit=True) as cur:
                    for reserve, alloc_amount in allocations:
                        cur.execute(
                            """
                            INSERT INTO charter_payments (
                                charter_id,
                                payment_date,
                                amount,
                                payment_method,
                                source,
                                imported_at
                            )
                            VALUES (%s, %s, %s, %s, %s, NOW())
                            """,
                            (
                                reserve,
                                payment_date.date().toPyDate(),
                                alloc_amount,
                                method_val,
                                "bulk_client_payment_date_range",
                            ),
                        )

                        cur.execute(
                            """
                            UPDATE charters c
                            SET amount_paid = COALESCE(paid.total_paid, 0),
                                balance_owing = GREATEST(
                                    COALESCE(c.total_amount_due, 0) - COALESCE(paid.total_paid, 0),
                                    0
                                ),
                                updated_at = NOW()
                            FROM (
                                SELECT COALESCE(SUM(amount), 0) AS total_paid
                                FROM charter_payments
                                WHERE charter_id = %s
                            ) paid
                            WHERE c.reserve_number = %s
                            """,
                            (reserve, reserve),
                        )

                    remainder = round(payment_total - allocated_total, 2)
                    if remainder > 0.009:
                        self._insert_unapplied_payment_row(
                            cur=cur,
                            payment_date=payment_date.date().toPyDate(),
                            amount=remainder,
                            method_val=method_val,
                            reference_txt=reference_txt,
                            notes_txt=(
                                f"Date-range allocation remainder. {notes_txt}".strip()
                                if notes_txt
                                else "Date-range allocation remainder"
                            ),
                            source_val="bulk_payment_remainder",
                            hold_type="credit",
                        )
            except Exception as e:
                logger.error("Date-range bulk payment post failed: %s", e)
                QMessageBox.critical(dialog, "Error", f"Failed to post bulk payment: {e}")
                return

            posted["ok"] = True
            QMessageBox.information(
                dialog,
                "Bulk Payment Posted",
                (
                    f"Posted ${allocated_total:,.2f} across {len(allocations)} charter(s).\n"
                    f"Unallocated remainder held: ${round(payment_total - allocated_total, 2):,.2f}"
                ),
            )
            dialog.accept()

        load_btn.clicked.connect(_load_rows)
        select_all_btn.clicked.connect(lambda: _set_all_checked(True))
        clear_all_btn.clicked.connect(lambda: _set_all_checked(False))
        alloc_table.itemChanged.connect(lambda _item: _refresh_summary())
        post_btn.clicked.connect(_post)
        cancel_btn.clicked.connect(dialog.reject)

        _load_rows()
        dialog.exec()
        return bool(posted["ok"])

    def _record_advance_payment_hold(self) -> bool:
        """Record payment as unapplied client credit until allocation."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Record Advance Client Payment")
        dialog.setGeometry(140, 140, 520, 360)

        layout = QVBoxLayout(dialog)
        layout.addWidget(
            QLabel(
                "Record a client payment before charter allocation.\n"
                "This amount is held as unapplied credit until allocated."
            )
        )

        form = QFormLayout()

        payment_date = QDateEdit()
        payment_date.setCalendarPopup(True)
        payment_date.setDate(QDate.currentDate())
        form.addRow("Payment Date:", payment_date)

        amount_input = QDoubleSpinBox()
        amount_input.setMaximum(99999999)
        amount_input.setDecimals(2)
        amount_input.setPrefix("$")
        amount_input.setValue(0.0)
        form.addRow("Amount:", amount_input)

        method_combo = QComboBox()
        method_combo.addItems(
            [
                "E-Transfer",
                "Credit Card",
                "Debit Card",
                "Cash",
                "Cheque",
                "Bank Transfer",
                "Deposit",
                "NRR Retainer",
                "Other",
            ]
        )
        form.addRow("Payment Method:", method_combo)

        reference_input = QLineEdit()
        reference_input.setPlaceholderText("e.g., cheque number / transaction ID")
        form.addRow("Reference:", reference_input)

        hold_type_combo = QComboBox()
        hold_type_combo.addItems([
            "Unapplied Credit",
            "Escrow Hold",
            "Refund Hold",
        ])
        form.addRow("Hold Type:", hold_type_combo)

        notes_input = QTextEdit()
        notes_input.setMaximumHeight(80)
        notes_input.setPlaceholderText("Optional notes")
        form.addRow("Notes:", notes_input)

        layout.addLayout(form)

        button_row = QHBoxLayout()
        hold_btn = QPushButton("Hold as Unapplied Credit")
        cancel_btn = QPushButton("Cancel")
        button_row.addStretch()
        button_row.addWidget(hold_btn)
        button_row.addWidget(cancel_btn)
        layout.addLayout(button_row)

        posted = {"ok": False}

        def _post_hold() -> None:
            amount_val = round(float(amount_input.value() or 0.0), 2)
            if amount_val <= 0.0:
                QMessageBox.warning(dialog, "Invalid Amount", "Amount must be greater than $0.00.")
                return

            method_map = {
                "E-Transfer": "etransfer",
                "Credit Card": "credit_card",
                "Debit Card": "debit_card",
                "Cash": "cash",
                "Cheque": "cheque",
                "Bank Transfer": "bank_transfer",
                "Deposit": "deposit",
                "NRR Retainer": "nrr",
                "Other": "other",
            }
            method_val = method_map.get(method_combo.currentText(), "other")
            reference_txt = reference_input.text().strip()
            notes_txt = notes_input.toPlainText().strip()
            hold_type_map = {
                "Unapplied Credit": "credit",
                "Escrow Hold": "escrow",
                "Refund Hold": "refund",
            }
            hold_type = hold_type_map.get(hold_type_combo.currentText(), "credit")
            if method_combo.currentText() == "NRR Retainer":
                hold_type = "escrow"

            try:
                with DatabaseContext(self.db, auto_commit=True) as cur:
                    self._insert_unapplied_payment_row(
                        cur=cur,
                        payment_date=payment_date.date().toPyDate(),
                        amount=amount_val,
                        method_val=method_val,
                        reference_txt=reference_txt,
                        notes_txt=notes_txt,
                        source_val="advance_payment_hold",
                        hold_type=hold_type,
                    )
            except Exception as e:
                logger.error("Failed to record advance payment hold: %s", e)
                QMessageBox.critical(dialog, "Error", f"Failed to record advance payment hold: {e}")
                return

            posted["ok"] = True
            QMessageBox.information(
                dialog,
                "Advance Payment Recorded",
                (
                    f"Held ${amount_val:,.2f} as {hold_type}.\n"
                    "Allocate it later to charters or pay it back to the client."
                ),
            )
            dialog.accept()

        hold_btn.clicked.connect(_post_hold)
        cancel_btn.clicked.connect(dialog.reject)
        dialog.exec()
        return bool(posted["ok"])

    def _insert_unapplied_payment_row(
        self,
        cur,
        payment_date,
        amount: float,
        method_val: str,
        reference_txt: str,
        notes_txt: str,
        source_val: str,
        hold_type: str = "credit",
    ) -> None:
        cur.execute(
            """
            INSERT INTO client_unapplied_payments (
                client_id,
                payment_date,
                amount,
                remaining_amount,
                payment_method,
                reference,
                notes,
                source,
                hold_type,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (
                self.client_id,
                payment_date,
                float(amount),
                float(amount),
                (method_val or "other"),
                (reference_txt or ""),
                (notes_txt or ""),
                (source_val or "manual"),
                (hold_type or "credit"),
            ),
        )

    def _fetch_all_outstanding_reserves(self, limit: int = 500) -> list[str]:
        """Return all reserves with outstanding balance for current client."""
        rows: list[str] = []
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    WITH outstanding AS (
                        SELECT
                            c.reserve_number,
                            c.charter_date,
                            GREATEST(
                                COALESCE(c.total_amount_due, 0)
                                - COALESCE((
                                    SELECT SUM(p.amount)
                                    FROM charter_payments p
                                    WHERE p.charter_id = c.reserve_number
                                ), 0),
                                0
                            ) AS outstanding
                        FROM charters c
                        WHERE c.client_id = %s
                          AND COALESCE(c.reserve_number, '') <> ''
                    )
                    SELECT reserve_number
                    FROM outstanding
                    WHERE outstanding > 0
                    ORDER BY charter_date DESC NULLS LAST, reserve_number DESC
                    LIMIT %s
                    """,
                    (self.client_id, int(limit)),
                )
                rows = [str(r[0]) for r in (cur.fetchall() or []) if r and r[0]]
        except Exception as e:
            logger.error("Failed to fetch all outstanding reserves: %s", e)
        return rows

    def _ensure_unapplied_payments_table(self) -> None:
        """Ensure unapplied client payment holding table exists."""
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS client_unapplied_payments (
                        id BIGSERIAL PRIMARY KEY,
                        client_id INTEGER NOT NULL,
                        payment_date DATE NOT NULL,
                        amount NUMERIC(14,2) NOT NULL DEFAULT 0,
                        remaining_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
                        payment_method VARCHAR(50),
                        reference VARCHAR(255),
                        notes TEXT,
                        source VARCHAR(120),
                        hold_type VARCHAR(20) NOT NULL DEFAULT 'credit',
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                    """
                )
                cur.execute(
                    """
                    ALTER TABLE client_unapplied_payments
                    ADD COLUMN IF NOT EXISTS hold_type VARCHAR(20) NOT NULL DEFAULT 'credit'
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_client_unapplied_payments_client
                    ON client_unapplied_payments(client_id, payment_date DESC)
                    """
                )
        except Exception as e:
            logger.error("Failed ensuring client_unapplied_payments table: %s", e)

    def _fetch_outstanding_rows_by_date_range(
        self,
        start_date,
        end_date,
        limit: int = 1000,
    ) -> list[tuple[str, str, float]]:
        """Fetch outstanding charters in a date range for date-based bulk allocation."""
        rows: list[tuple[str, str, float]] = []
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT
                        c.reserve_number,
                        c.charter_date,
                        GREATEST(
                            COALESCE(c.total_amount_due, 0)
                            - COALESCE((
                                SELECT SUM(p.amount)
                                FROM charter_payments p
                                WHERE p.charter_id = c.reserve_number
                            ), 0),
                            0
                        ) AS outstanding
                    FROM charters c
                    WHERE c.client_id = %s
                      AND COALESCE(c.reserve_number, '') <> ''
                      AND c.charter_date BETWEEN %s AND %s
                    ORDER BY c.charter_date ASC, c.reserve_number ASC
                    LIMIT %s
                    """,
                    (self.client_id, start_date, end_date, int(limit)),
                )
                rows = [
                    (str(reserve), str(charter_date or ""), float(outstanding or 0.0))
                    for reserve, charter_date, outstanding in (cur.fetchall() or [])
                    if reserve and float(outstanding or 0.0) > 0
                ]
        except Exception as e:
            logger.error("Failed to fetch date-range outstanding rows: %s", e)
        return rows

    @pyqtSlot()
    def _pay_back_held_balance(self) -> None:
        """Reduce held client balances when money is refunded/returned to client."""
        if not self.client_id:
            QMessageBox.warning(self, "Warning", "No client loaded.")
            return

        self._ensure_unapplied_payments_table()
        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT
                    id,
                    payment_date,
                    COALESCE(hold_type, 'credit'),
                    COALESCE(remaining_amount, 0),
                    COALESCE(reference, '')
                FROM client_unapplied_payments
                WHERE client_id = %s
                  AND COALESCE(remaining_amount, 0) > 0
                ORDER BY payment_date DESC, id DESC
                LIMIT 500
                """,
                (self.client_id,),
            )
            held_rows = cur.fetchall() or []

        if not held_rows:
            QMessageBox.information(self, "No Held Balances", "No held balances are available to pay back.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Pay Back Held Balance")
        dialog.setGeometry(180, 180, 620, 400)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Choose a held balance row and amount to pay back to the client."))

        held_combo = QComboBox()
        for row_id, p_date, hold_type, remaining, reference in held_rows:
            label = (
                f"ID {row_id} | {p_date} | {str(hold_type).upper()} | "
                f"Remaining ${float(remaining or 0):,.2f} | Ref {reference or '-'}"
            )
            held_combo.addItem(label, (int(row_id), float(remaining or 0.0)))
        layout.addWidget(held_combo)

        amount_input = QDoubleSpinBox()
        amount_input.setMaximum(99999999)
        amount_input.setDecimals(2)
        amount_input.setPrefix("$")
        amount_input.setValue(0.0)
        layout.addWidget(amount_input)

        notes_input = QLineEdit()
        notes_input.setPlaceholderText("Reason / note for client pay-back")
        layout.addWidget(notes_input)

        button_row = QHBoxLayout()
        post_btn = QPushButton("Post Pay-Back")
        cancel_btn = QPushButton("Cancel")
        button_row.addStretch()
        button_row.addWidget(post_btn)
        button_row.addWidget(cancel_btn)
        layout.addLayout(button_row)

        def _set_max_from_selection() -> None:
            data = held_combo.currentData()
            max_amt = float(data[1] if data else 0.0)
            amount_input.setMaximum(max_amt if max_amt > 0 else 0.0)
            if amount_input.value() > max_amt:
                amount_input.setValue(max_amt)

        def _post_pay_back() -> None:
            data = held_combo.currentData()
            if not data:
                QMessageBox.warning(dialog, "No Selection", "Select a held balance row.")
                return
            row_id, max_amt = int(data[0]), float(data[1])
            pay_back_amt = round(float(amount_input.value() or 0.0), 2)
            if pay_back_amt <= 0.0:
                QMessageBox.warning(dialog, "Invalid Amount", "Pay-back amount must be greater than $0.00.")
                return
            if pay_back_amt - max_amt > 0.009:
                QMessageBox.warning(dialog, "Amount Too High", "Pay-back amount exceeds remaining held balance.")
                return

            note = notes_input.text().strip()
            payback_note = f"Pay-back posted: ${pay_back_amt:,.2f}. {note}".strip()
            try:
                with DatabaseContext(self.db, auto_commit=True) as cur:
                    cur.execute(
                        """
                        UPDATE client_unapplied_payments
                        SET remaining_amount = GREATEST(COALESCE(remaining_amount, 0) - %s, 0),
                            notes = CASE
                                WHEN COALESCE(notes, '') = '' THEN %s
                                ELSE notes || E'\n' || %s
                            END,
                            updated_at = NOW()
                        WHERE id = %s AND client_id = %s
                        """,
                        (
                            pay_back_amt,
                            payback_note,
                            payback_note,
                            row_id,
                            self.client_id,
                        ),
                    )
            except Exception as e:
                logger.error("Failed posting held-balance pay-back: %s", e)
                QMessageBox.critical(dialog, "Error", f"Failed to post pay-back: {e}")
                return

            QMessageBox.information(dialog, "Pay-Back Posted", f"Posted pay-back of ${pay_back_amt:,.2f}.")
            dialog.accept()

        held_combo.currentIndexChanged.connect(_set_max_from_selection)
        post_btn.clicked.connect(_post_pay_back)
        cancel_btn.clicked.connect(dialog.reject)
        _set_max_from_selection()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_client_data()

    def _fetch_next_outstanding_reserves(
        self,
        exclude_reserves: list[str],
        limit: int = 100,
    ) -> list[tuple[str, float]]:
        """Return additional outstanding reserves for this client not in the excluded list."""
        rows: list[tuple[str, float]] = []
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    WITH outstanding AS (
                        SELECT
                            c.reserve_number,
                            c.charter_date,
                            GREATEST(
                                COALESCE(c.total_amount_due, 0)
                                - COALESCE((
                                    SELECT SUM(p.amount)
                                    FROM charter_payments p
                                    WHERE p.charter_id = c.reserve_number
                                ), 0),
                                0
                            ) AS outstanding
                        FROM charters c
                        WHERE c.client_id = %s
                          AND COALESCE(c.reserve_number, '') <> ''
                          AND NOT (c.reserve_number = ANY(%s))
                    )
                    SELECT reserve_number, outstanding
                    FROM outstanding
                    WHERE outstanding > 0
                    ORDER BY charter_date DESC NULLS LAST, reserve_number DESC
                    LIMIT %s
                    """,
                    (self.client_id, exclude_reserves or [], int(limit)),
                )
                rows = [
                    (str(reserve_number), float(outstanding or 0.0))
                    for reserve_number, outstanding in (cur.fetchall() or [])
                    if reserve_number is not None
                ]
        except Exception as e:
            logger.error("Failed to fetch next outstanding reserves: %s", e)
        return rows

    def _fetch_outstanding_balances(self, reserves: list[str]) -> dict[str, float]:
        """Fetch outstanding by reserve using charter totals minus posted payments."""
        result: dict[str, float] = {}
        if not reserves:
            return result
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT
                        c.reserve_number,
                        GREATEST(
                            COALESCE(c.total_amount_due, 0)
                            - COALESCE((
                                SELECT SUM(p.amount)
                                FROM charter_payments p
                                WHERE p.charter_id = c.reserve_number
                            ), 0),
                            0
                        ) AS outstanding
                    FROM charters c
                    WHERE c.client_id = %s
                      AND c.reserve_number = ANY(%s)
                    ORDER BY c.charter_date DESC
                    """,
                    (self.client_id, reserves),
                )
                for reserve_number, outstanding in cur.fetchall() or []:
                    result[str(reserve_number)] = float(outstanding or 0)
        except Exception as e:
            logger.error("Failed to fetch outstanding balances: %s", e)
        return result

    @pyqtSlot()
    def send_statement(self) -> None:
        if not self.client_id:
            QMessageBox.warning(self, "Warning", "No client loaded.")
            return
        QMessageBox.information(
            self,
            "Statement Prepared",
            (
                f"Client: {self.client_name.text().strip() or self.client_id}\n"
                f"Total Paid: {self.total_paid.text().replace('Total Paid: ', '')}\n"
                f"Outstanding: {self.outstanding_balance.text().replace('Outstanding: ', '')}\n"
                "\nStatement preview is ready. Email delivery can be added in a later pass."
            ),
        )

    @pyqtSlot()
    def add_favorite_driver(self) -> None:
        if not self.client_id:
            QMessageBox.warning(self, "Warning", "No client loaded.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Add Favorite Driver")
        form = QFormLayout(dialog)

        driver_combo = QComboBox()
        candidates: list[tuple[int, str]] = []
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT employee_id, full_name
                    FROM employees
                    WHERE COALESCE(full_name, '') <> ''
                    ORDER BY full_name
                    LIMIT 500
                """
                )
                candidates = [(int(emp_id), str(name)) for emp_id, name in cur.fetchall() or []]
        except Exception:
            logger.exception("Failed loading drivers for favorites")

        for emp_id, name in candidates:
            driver_combo.addItem(name, emp_id)
        form.addRow("Driver:", driver_combo)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        buttons.addStretch()
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        form.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted or driver_combo.currentIndex() < 0:
            return

        driver_name = driver_combo.currentText().strip()
        driver_id = driver_combo.currentData()
        if not driver_name:
            return

        try:
            self._ensure_client_drilldown_tables()
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO client_favorite_drivers
                    (client_id, employee_id, driver_name)
                    VALUES (%s, %s, %s)
                """,
                    (self.client_id, driver_id, driver_name),
                )
            self._load_favorites()
        except Exception as e:
            logger.error("Failed to add favorite driver: %s", e)
            QMessageBox.critical(self, "Error", f"Failed to add favorite driver: {e}")

    @pyqtSlot()
    def remove_favorite_driver(self) -> None:
        item = self.fav_drivers_list.currentItem()
        if item:
            fav_id = item.data(Qt.ItemDataRole.UserRole)
            try:
                if fav_id:
                    with DatabaseContext(self.db, auto_commit=True) as cur:
                        cur.execute(
                            "DELETE FROM client_favorite_drivers WHERE favorite_id = %s",
                            (fav_id,),
                        )
                self.fav_drivers_list.takeItem(self.fav_drivers_list.row(item))
            except Exception as e:
                logger.error("Failed to remove favorite driver: %s", e)
                QMessageBox.critical(self, "Error", f"Failed to remove favorite driver: {e}")

    @pyqtSlot()
    def add_favorite_vehicle(self) -> None:
        if not self.client_id:
            QMessageBox.warning(self, "Warning", "No client loaded.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Add Favorite Vehicle")
        form = QFormLayout(dialog)

        vehicle_combo = QComboBox()
        candidates: list[tuple[int, str]] = []
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT vehicle_id,
                           COALESCE(vehicle_number, '') || ' ' ||
                           COALESCE(make, '') || ' ' || COALESCE(model, '')
                    FROM vehicles
                    ORDER BY vehicle_number
                    LIMIT 500
                """
                )
                candidates = [
                    (int(vehicle_id), " ".join(str(label or "").split()).strip())
                    for vehicle_id, label in cur.fetchall() or []
                ]
        except Exception:
            logger.exception("Failed loading vehicles for favorites")

        for vehicle_id, label in candidates:
            vehicle_combo.addItem(label or str(vehicle_id), vehicle_id)
        form.addRow("Vehicle:", vehicle_combo)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        buttons.addStretch()
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        form.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted or vehicle_combo.currentIndex() < 0:
            return

        vehicle_label = vehicle_combo.currentText().strip()
        vehicle_id = vehicle_combo.currentData()
        if not vehicle_label:
            return

        try:
            self._ensure_client_drilldown_tables()
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO client_favorite_vehicles
                    (client_id, vehicle_id, vehicle_label)
                    VALUES (%s, %s, %s)
                """,
                    (self.client_id, vehicle_id, vehicle_label),
                )
            self._load_favorites()
        except Exception as e:
            logger.error("Failed to add favorite vehicle: %s", e)
            QMessageBox.critical(self, "Error", f"Failed to add favorite vehicle: {e}")

    @pyqtSlot()
    def remove_favorite_vehicle(self) -> None:
        item = self.fav_vehicles_list.currentItem()
        if item:
            fav_id = item.data(Qt.ItemDataRole.UserRole)
            try:
                if fav_id:
                    with DatabaseContext(self.db, auto_commit=True) as cur:
                        cur.execute(
                            "DELETE FROM client_favorite_vehicles WHERE favorite_id = %s",
                            (fav_id,),
                        )
                self.fav_vehicles_list.takeItem(self.fav_vehicles_list.row(item))
            except Exception as e:
                logger.error("Failed to remove favorite vehicle: %s", e)
                QMessageBox.critical(self, "Error", f"Failed to remove favorite vehicle: {e}")

    @pyqtSlot()
    def log_call(self) -> None:
        self._log_communication("phone_call")

    @pyqtSlot()
    def log_email(self) -> None:
        self._log_communication("email")

    def _log_communication(self, comm_type: str) -> None:
        if not self.client_id:
            QMessageBox.warning(self, "Warning", "No client loaded.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Log Communication")
        form = QFormLayout(dialog)

        subject = QLineEdit()
        subject.setPlaceholderText("Subject")
        form.addRow("Subject:", subject)

        notes = QTextEdit()
        notes.setMaximumHeight(120)
        form.addRow("Notes:", notes)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        buttons.addStretch()
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        form.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            self._ensure_client_drilldown_tables()
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO client_communications
                    (client_id, communication_type, subject, status, notes)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                    (
                        self.client_id,
                        comm_type,
                        subject.text().strip() or None,
                        "logged",
                        notes.toPlainText().strip() or None,
                    ),
                )
            self._load_communications()
        except Exception as e:
            logger.error("Failed to log communication: %s", e)
            QMessageBox.critical(self, "Error", f"Failed to log communication: {e}")

    @pyqtSlot()
    def upload_client_doc(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Document")
        if file_path:
            QMessageBox.information(self, "Info", f"Document uploaded: {file_path}")

    @pyqtSlot()
    def view_client_doc(self) -> None:
        item = self.doc_list.currentItem()
        if item:
            QMessageBox.information(self, "Info", f"Opening: {item.text()}")

    @pyqtSlot()
    def delete_client_doc(self) -> None:
        item = self.doc_list.currentItem()
        if item:
            self.doc_list.takeItem(self.doc_list.row(item))

    def open_client_document(self, index) -> None:
        self.view_client_doc()

    @pyqtSlot()
    def log_dispute(self) -> None:
        if not self.client_id:
            QMessageBox.warning(self, "Warning", "No client loaded.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Log Dispute")
        form = QFormLayout(dialog)

        dispute_date = StandardDateEdit(prefer_month_text=True)
        dispute_date.setCalendarPopup(True)
        dispute_date.setDate(QDate.currentDate())
        form.addRow("Date:", dispute_date)

        charter_number = QLineEdit()
        charter_number.setPlaceholderText("Reserve #")
        form.addRow("Charter #:", charter_number)

        issue_type = QComboBox()
        issue_type.addItems(["billing", "service", "timing", "damage", "other"])
        form.addRow("Issue Type:", issue_type)

        amount = QDoubleSpinBox()
        amount.setMaximum(9_999_999)
        amount.setDecimals(2)
        amount.setPrefix("$")
        form.addRow("Amount:", amount)

        resolution = QTextEdit()
        resolution.setMaximumHeight(120)
        form.addRow("Notes:", resolution)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        buttons.addStretch()
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        form.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            self._ensure_client_drilldown_tables()
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO client_disputes
                    (client_id, dispute_date, charter_number, issue_type,
                     amount, status, resolution)
                    VALUES (%s, %s, %s, %s, %s, 'open', %s)
                """,
                    (
                        self.client_id,
                        dispute_date.date().toPyDate(),
                        charter_number.text().strip() or None,
                        issue_type.currentText(),
                        float(amount.value()) if amount.value() > 0 else None,
                        resolution.toPlainText().strip() or None,
                    ),
                )
            self._load_disputes()
        except Exception as e:
            logger.error("Failed to log dispute: %s", e)
            QMessageBox.critical(self, "Error", f"Failed to log dispute: {e}")

    @pyqtSlot()
    def resolve_dispute(self) -> None:
        row = self.dispute_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Resolve Dispute", "Select a dispute first.")
            return

        id_item = self.dispute_table.item(row, 0)
        dispute_id = id_item.data(Qt.ItemDataRole.UserRole) if id_item else None
        if not dispute_id:
            QMessageBox.warning(self, "Resolve Dispute", "Could not determine dispute ID.")
            return

        current_resolution_item = self.dispute_table.item(row, 5)
        current_resolution = current_resolution_item.text() if current_resolution_item else ""

        dialog = QDialog(self)
        dialog.setWindowTitle("Resolve Dispute")
        form = QFormLayout(dialog)

        resolution = QTextEdit()
        resolution.setMaximumHeight(140)
        resolution.setPlainText(current_resolution)
        form.addRow("Resolution:", resolution)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Resolve")
        save_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        buttons.addStretch()
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        form.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            self._ensure_client_drilldown_tables()
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    UPDATE client_disputes
                    SET status = 'resolved',
                        resolution = %s,
                        resolved_at = NOW()
                    WHERE dispute_id = %s
                """,
                    (resolution.toPlainText().strip() or None, dispute_id),
                )
            self._load_disputes()
        except Exception as e:
            logger.error("Failed to resolve dispute: %s", e)
            QMessageBox.critical(self, "Error", f"Failed to resolve dispute: {e}")
