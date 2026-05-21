"""
Client Drill-Down Detail View
Comprehensive client management - contact, charter history, payments, credit,
preferences
"""

import logging

from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
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
)

from common_widgets import StandardDateEdit
from ui_standards import (
    SmartFormField,
    make_read_only_table,
    setup_standard_table,
)
from db_error_handling import DatabaseContext
from payment_dialog import PaymentDialog

logger = logging.getLogger(__name__)


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

    def __init__(self, db, client_id=None, parent=None) -> None:
        try:
            super().__init__(parent)
            self.db = db
            self.client_id = client_id
            self.client_data = None

            # Ensure contract_charter_reserve column exists
            try:
                with DatabaseContext(self.db, auto_commit=True) as _cur:
                    _cur.execute(
                        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS "
                        "contract_charter_reserve VARCHAR(20)"
                    )
            except Exception:
                pass

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
            self.add_new_btn = QPushButton("➕ Add New")
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
            tabs = QTabWidget()

            tabs.addTab(self.create_contact_tab(), "👤 Contact Info")
            tabs.addTab(
                self.create_charter_history_tab(), "🚗 Charter History"
            )
            tabs.addTab(self.create_payments_tab(), "💳 Payments")
            tabs.addTab(self.create_credit_tab(), "💰 Credit & Terms")
            tabs.addTab(self.create_preferences_tab(), "⭐ Preferences")
            tabs.addTab(self.create_communications_tab(), "📧 Communications")
            tabs.addTab(self.create_documents_tab(), "📄 Documents")
            tabs.addTab(self.create_disputes_tab(), "⚠️ Disputes")
            tabs.addTab(self.create_metrics_tab(), "📊 Client Metrics")

            layout.addWidget(tabs)
            self.setLayout(layout)

            if client_id:
                self.load_client_data()
        except Exception as e:
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

        self.is_company = QCheckBox("This is a company (not an individual)")
        self.is_company.stateChanged.connect(self.on_is_company_toggled)
        corporate_form.addRow("Company:", self.is_company)

        self.is_corporate = QCheckBox("This is a corporate client")
        corporate_form.addRow("Corporate Client:", self.is_corporate)

        self.first_name = QLineEdit()
        corporate_form.addRow("First Name (Individual):", self.first_name)

        self.last_name = QLineEdit()
        corporate_form.addRow("Last Name (Individual):", self.last_name)

        self.corporate_parent_id = QSpinBox()
        self.corporate_parent_id.setMinimum(0)
        self.corporate_parent_id.setMaximum(999999)
        self.corporate_parent_id.setValue(0)
        corporate_form.addRow(
            "Corporate Parent ID (0=Individual):", self.corporate_parent_id
        )

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
        corporate_form.addRow("Role in Company:", self.corporate_role)

        corporate_group.setLayout(corporate_form)
        form.addRow(corporate_group)

        self.phone = SmartFormField.phone_field()
        form.addRow("Phone:", self.phone)

        self.email = SmartFormField.email_field()
        form.addRow("Email:", self.email)

        self.address = SmartFormField.auto_expanding_text(max_height=100)
        form.addRow("Address:", self.address)

        self.city = QLineEdit()
        form.addRow("City:", self.city)

        self.province = QLineEdit()
        form.addRow("Province:", self.province)

        self.postal = SmartFormField.postal_code_field()
        form.addRow("Postal Code:", self.postal)

        # Billing info
        billing_group = QGroupBox("Billing Information")
        billing_form = QFormLayout()

        self.billing_email = SmartFormField.email_field()
        billing_form.addRow("Billing Email:", self.billing_email)

        self.tax_id = QLineEdit()
        billing_form.addRow("Tax ID/GST #:", self.tax_id)

        self.payment_terms = QComboBox()
        self.payment_terms.addItems(
            ["Due on Receipt", "Net 15", "Net 30", "Net 60", "COD", "Prepaid"]
        )
        billing_form.addRow("Payment Terms:", self.payment_terms)

        self.preferred_payment = QComboBox()
        self.preferred_payment.addItems(
            ["Credit Card", "Invoice", "Cash", "Check", "Bank Transfer"]
        )
        billing_form.addRow("Preferred Payment:", self.preferred_payment)

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
        self.client_status.addItems(
            ["Active", "Inactive", "Suspended", "VIP", "Blacklisted"]
        )
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
        self.charter_table.doubleClicked.connect(self.open_charter_detail)
        layout.addWidget(self.charter_table)

        # Charter buttons
        btn_layout = QHBoxLayout()
        new_charter_btn = QPushButton("➕ New Charter")
        new_charter_btn.clicked.connect(self.new_charter)
        btn_layout.addWidget(new_charter_btn)
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
        help_icon = QLabel("ℹ️")
        help_icon.setToolTip(
            "Manual ledger entry only — records payments already received"
            "(cash/check/bank). No online processing or auto-charging."
        )
        header.addWidget(help_icon)
        header.addStretch()
        layout.addLayout(header)
        hint = QLabel(
            "Manual ledger entry only — records payments already received"
            "(cash/check/bank). No online processing or auto-charging."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 10px; color: #666;")
        layout.addWidget(hint)

        # Payment summary
        summary_layout = QHBoxLayout()
        self.total_paid = QLabel("Total Paid: $0.00")
        self.outstanding_balance = QLabel("Outstanding: $0.00")
        self.overdue_amount = QLabel("Overdue: $0.00")
        summary_layout.addWidget(self.total_paid)
        summary_layout.addWidget(self.outstanding_balance)
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
        layout.addWidget(self.payment_table)

        # Payment buttons
        btn_layout = QHBoxLayout()
        record_payment_btn = QPushButton("➕ Record Payment")
        record_payment_btn.setToolTip(
            "Record a manually received client payment; no online processing"
            "or auto-charging."
        )
        record_payment_btn.clicked.connect(self.record_payment)
        btn_layout.addWidget(record_payment_btn)

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
        form.addRow("Credit Limit:", self.credit_limit)

        self.credit_used = QDoubleSpinBox()
        self.credit_used.setMaximum(9999999)
        self.credit_used.setReadOnly(True)
        self.credit_used.setPrefix("$")
        form.addRow("Credit Used:", self.credit_used)

        self.credit_available = QDoubleSpinBox()
        self.credit_available.setMaximum(9999999)
        self.credit_available.setReadOnly(True)
        self.credit_available.setPrefix("$")
        form.addRow("Available Credit:", self.credit_available)

        self.deposit_required = QCheckBox()
        form.addRow("Deposit Required:", self.deposit_required)

        self.deposit_percent = QDoubleSpinBox()
        self.deposit_percent.setMaximum(100)
        self.deposit_percent.setSuffix("%")
        form.addRow("Deposit %:", self.deposit_percent)

        self.credit_check_date = StandardDateEdit(prefer_month_text=True)
        self.credit_check_date.setCalendarPopup(True)
        form.addRow("Last Credit Check:", self.credit_check_date)

        self.credit_rating = QComboBox()
        self.credit_rating.addItems(
            ["Excellent", "Good", "Fair", "Poor", "Not Rated"]
        )
        form.addRow("Credit Rating:", self.credit_rating)

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
        add_driver_btn = QPushButton("➕ Add Driver")
        add_driver_btn.clicked.connect(self.add_favorite_driver)
        driver_btn_layout.addWidget(add_driver_btn)
        remove_driver_btn = QPushButton("➖ Remove")
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
        add_vehicle_btn = QPushButton("➕ Add Vehicle")
        add_vehicle_btn.clicked.connect(self.add_favorite_vehicle)
        vehicle_btn_layout.addWidget(add_vehicle_btn)
        remove_vehicle_btn = QPushButton("➖ Remove")
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
        self.special_requirements.setPlaceholderText(
            "Wheelchair accessible, child seats, etc."
        )
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
        log_dispute_btn = QPushButton("➕ Log Dispute")
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
            with DatabaseContext(self.db, auto_commit=False) as cur:
                # Main client data
                cur.execute(
                    """
                    SELECT client_id, company_name, client_name, primary_phone,
                    email, address_line1,
                           first_name, last_name, parent_client_id,
                           corporate_role, is_company,
                           contract_charter_reserve
                    FROM clients
                    WHERE client_id = %s
                """,
                    (self.client_id,),
                )
                client = cur.fetchone()
                if client:
                    (
                        cid,
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
                    ) = client

                    is_company = (
                        bool(is_company_val)
                        if is_company_val is not None
                        else False
                    )
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
                            parsed_first = (
                                parts[1].strip() if len(parts) > 1 else ""
                            )
                            self.last_name.setText(parsed_last)
                            self.first_name.setText(parsed_first)
                        else:
                            # Otherwise use stored first/last or assume last
                            # name
                            # only
                            self.first_name.setText(str(first_name or ""))
                            self.last_name.setText(
                                str(last_name or client_name_str)
                            )

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

                # Charter history
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

                charter_rows = cur.fetchall()
                self.charter_table.setRowCount(
                    len(charter_rows) if charter_rows else 0
                )
                if charter_rows:
                    total_rev = 0
                    for i, (
                        c_date,
                        res,
                        pickup,
                        dest,
                        driver,
                        veh,
                        amount,
                    ) in enumerate(charter_rows):
                        self.charter_table.setItem(
                            i, 0, QTableWidgetItem(str(c_date))
                        )
                        self.charter_table.setItem(
                            i, 1, QTableWidgetItem(str(res))
                        )
                        self.charter_table.setItem(
                            i, 2, QTableWidgetItem(str(pickup or ""))
                        )
                        self.charter_table.setItem(
                            i, 3, QTableWidgetItem(str(dest or ""))
                        )
                        self.charter_table.setItem(
                            i, 4, QTableWidgetItem(str(driver or ""))
                        )
                        self.charter_table.setItem(
                            i, 5, QTableWidgetItem(str(veh or ""))
                        )
                        self.charter_table.setItem(
                            i,
                            6,
                            QTableWidgetItem(f"${float(amount or 0): ,.2f} "),
                        )
                        self.charter_table.setItem(
                            i, 7, QTableWidgetItem("Complete")
                        )
                        total_rev += float(amount or 0)

                    self.total_charters.setText(
                        f"Total Charters: {len(charter_rows)}"
                    )
                    self.total_revenue.setText(
                        f"Total Revenue: ${total_rev:,.2f}"
                    )
                    if len(charter_rows) > 0:
                        self.avg_charter_value.setText(
                            f"Avg Charter: $"
                            f"{total_rev / len(charter_rows):,.2f}"
                        )
                    self.lifetime_value.setValue(total_rev)

                # Payment history
                cur.execute(
                    """
                    SELECT p.payment_date, p.charter_id, p.amount,
                    p.payment_method
                    FROM charter_payments p
                    JOIN charters c ON p.charter_id = c.reserve_number
                    WHERE c.client_id = %s
                    ORDER BY p.payment_date DESC
                    LIMIT 100
                """,
                    (self.client_id,),
                )

                payment_rows = cur.fetchall()
                self.payment_table.setRowCount(
                    len(payment_rows) if payment_rows else 0
                )
                if payment_rows:
                    total_pd = 0
                    for i, (p_date, res, amt, method) in enumerate(
                        payment_rows
                    ):
                        self.payment_table.setItem(
                            i, 0, QTableWidgetItem(str(p_date))
                        )
                        self.payment_table.setItem(
                            i, 1, QTableWidgetItem(str(res))
                        )
                        self.payment_table.setItem(
                            i, 2, QTableWidgetItem(f"${float(amt or 0):,.2f}")
                        )
                        self.payment_table.setItem(
                            i, 3, QTableWidgetItem(str(method or ""))
                        )
                        self.payment_table.setItem(i, 4, QTableWidgetItem(""))
                        self.payment_table.setItem(
                            i, 5, QTableWidgetItem("Yes")
                        )
                        self.payment_table.setItem(i, 6, QTableWidgetItem(""))
                        total_pd += float(amt or 0)

                    self.total_paid.setText(f"Total Paid: ${total_pd:,.2f}")

                # Load documents
                self.doc_list.addItem("📄 Service Agreement.pdf")
                self.doc_list.addItem("📄 Credit Application.pdf")

        except Exception as e:
            logger.error(f"Failed to load client data: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to load client data: {e}"
            )

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
                            self.phone.text(),
                            self.email.text(),
                            self.address.toPlainText(),
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
                    # Auto-generate account_number (max numeric + 1)
                    cur.execute(
                        "SELECT MAX(CAST(account_number AS INTEGER))"
                        " FROM clients WHERE account_number ~ '^[0-9]+$'"
                    )
                    max_acct = cur.fetchone()[0] or 7604
                    new_account_number = str(int(max_acct) + 1)

                    cur.execute(
                        """
                        INSERT INTO clients (
                            account_number,
                            company_name,
                            client_name,
                            primary_phone,
                            email,
                            address_line1,
                            first_name,
                            last_name,
                            parent_client_id,
                            corporate_role,
                            is_company,
                            contract_charter_reserve,
                            created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, NOW())
                        RETURNING client_id
                    """,
                        (
                            new_account_number,
                            company,
                            auto_client_name,
                            self.phone.text(),
                            self.email.text(),
                            self.address.toPlainText(),
                            first,
                            last,
                            self.corporate_parent_id.value() or None,
                            corporate_role,
                            self.is_company.isChecked(),
                            self.contract_charter_input.text().strip() or None,
                        ),
                    )
                    created = cur.fetchone()
                    self.client_id = int(created[0]) if created else None
                    self.setWindowTitle(
                        f"Client Detail - {self.client_id or 'New'}"
                    )

            QMessageBox.information(
                self, "Success", "Client saved successfully"
            )
            self.saved.emit({"action": "save", "client_id": self.client_id})
        except Exception as e:
            logger.error(f"Failed to save client: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def _view_contract_charter(self) -> None:
        """Open the contract charter for viewing."""
        reserve = self.contract_charter_input.text().strip()
        if not reserve:
            QMessageBox.information(
                self, "No Contract Charter",
                "Enter a contract charter reserve number first."
            )
            return
        try:
            from charter_form_widget import CharterFormWidget
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    "SELECT charter_id FROM charters WHERE reserve_number = %s",
                    (reserve,)
                )
                row = cur.fetchone()
            if not row:
                QMessageBox.warning(
                    self, "Not Found",
                    f"Charter with reserve # {reserve} was not found."
                )
                return
            charter_id = row[0]
            dlg = CharterFormWidget(self.db, charter_id=charter_id, parent=self)
            dlg.exec()
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
            new_dialog = ClientDetailDialog(
                self.db, client_id=None, parent=self.parent()
            )
            new_dialog.saved.connect(self.on_client_saved)
            new_dialog.exec()

    @pyqtSlot()
    def duplicate_client(self) -> None:
        """Duplicate current client with modified name"""
        if not self.client_id:
            QMessageBox.warning(
                self, "Warning", "No client loaded to duplicate."
            )
            return

        # Collect current client data
        try:
            _new_name, _ok = QLineEdit().text(), False
            dialog = QDialog(self)
            dialog.setWindowTitle("Duplicate Client")
            dialog.setGeometry(100, 100, 400, 150)

            dlg_layout = QVBoxLayout()
            dlg_layout.addWidget(
                QLabel("Enter a new name for the duplicate client:")
            )

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

                QMessageBox.information(
                    self, "Success", f"Client duplicated as '{new_name}'."
                )
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
            f"Delete client '{self.client_name.text()}'?\nThis action cannot"
            f"be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                with DatabaseContext(self.db, auto_commit=True) as cur:
                    cur.execute(
                        "DELETE FROM clients WHERE client_id = %s",
                        (self.client_id,),
                    )

                QMessageBox.information(
                    self, "Success", "Client deleted successfully."
                )
                self.saved.emit(
                    {"action": "delete", "client_id": self.client_id}
                )
                self.close()
            except Exception as e:
                logger.error(f"Failed to delete client: {e}")
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")

    def on_client_saved(self, data) -> None:
        """Handle child dialog save - refresh current view"""
        if self.client_id:
            self.load_client_data()

    # ===== STUB METHODS =====
    @pyqtSlot()
    def suspend_client(self) -> None:
        QMessageBox.information(
            self, "Info", "Suspend client process (to be implemented)"
        )

    @pyqtSlot()
    def activate_client(self) -> None:
        QMessageBox.information(
            self, "Info", "Activate client process (to be implemented)"
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
                "Select a client to link as a child account:\n(This client"
                "becomes a subsidiary of the current company)"
            )
        )

        # Search/select field
        search_input = QLineEdit()
        search_input.setPlaceholderText(
            "Search by client name, ID, or company..."
        )
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
                    where = (
                        "WHERE parent_client_id = 0"
                        " OR parent_client_id IS NULL"
                    )
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
                    (
                        QListWidget.item_type()
                        if hasattr(QListWidget, "item_type")
                        else None
                    )
                    client_list.addItem(display)
                    client_list.item(client_list.count() - 1).setData(
                        Qt.ItemDataRole.UserRole, cid
                    )

            except Exception as e:
                logger.error(f"Failed to load clients: {e}")
                QMessageBox.warning(
                    dialog, "Error", f"Failed to load clients: {e}"
                )

        # Load initial list
        load_available_clients()

        # Search connection
        search_input.textChanged.connect(
            lambda: load_available_clients(search_input.text())
        )

        # Buttons
        btn_layout = QHBoxLayout()

        link_btn = QPushButton("Link as Child")

        def do_link() -> None:
            item = client_list.currentItem()
            if not item:
                QMessageBox.warning(
                    dialog, "Warning", "Select a client to link"
                )
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
        QMessageBox.information(
            self, "Info", "Open charter detail (to be implemented)"
        )

    @pyqtSlot()
    def new_charter(self) -> None:
        QMessageBox.information(
            self, "Info", "Create new charter (to be implemented)"
        )

    @pyqtSlot()
    def record_payment(self) -> None:
        selected = self.charter_table.selectedItems()
        if not selected:
            QMessageBox.information(
                self,
                "Select a Charter",
                "Please select a charter from the Charter History tab before"
                "recording a payment.",
            )
            return
        row = self.charter_table.currentRow()
        reserve_number = (
            self.charter_table.item(row, 1).text()
            if self.charter_table.item(row, 1)
            else None
        )
        if not reserve_number:
            QMessageBox.warning(
                self,
                "Error",
                "Could not determine reserve number for selected charter.",
            )
            return
        dlg = PaymentDialog(
            self.db, reserve_number, client_id=self.client_id, parent=self
        )
        dlg.exec()
        # Refresh payment table after dialog closes
        self.load_client_data()

    @pyqtSlot()
    def send_statement(self) -> None:
        QMessageBox.information(
            self, "Info", "Send statement (to be implemented)"
        )

    @pyqtSlot()
    def add_favorite_driver(self) -> None:
        QMessageBox.information(
            self, "Info", "Add favorite driver (to be implemented)"
        )

    @pyqtSlot()
    def remove_favorite_driver(self) -> None:
        item = self.fav_drivers_list.currentItem()
        if item:
            self.fav_drivers_list.takeItem(self.fav_drivers_list.row(item))

    @pyqtSlot()
    def add_favorite_vehicle(self) -> None:
        QMessageBox.information(
            self, "Info", "Add favorite vehicle (to be implemented)"
        )

    @pyqtSlot()
    def remove_favorite_vehicle(self) -> None:
        item = self.fav_vehicles_list.currentItem()
        if item:
            self.fav_vehicles_list.takeItem(self.fav_vehicles_list.row(item))

    @pyqtSlot()
    def log_call(self) -> None:
        QMessageBox.information(
            self, "Info", "Log phone call (to be implemented)"
        )

    @pyqtSlot()
    def log_email(self) -> None:
        QMessageBox.information(self, "Info", "Log email (to be implemented)")

    @pyqtSlot()
    def upload_client_doc(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Document")
        if file_path:
            QMessageBox.information(
                self, "Info", f"Document uploaded: {file_path}"
            )

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
        QMessageBox.information(
            self, "Info", "Log dispute (to be implemented)"
        )

    @pyqtSlot()
    def resolve_dispute(self) -> None:
        QMessageBox.information(
            self, "Info", "Resolve dispute (to be implemented)"
        )
