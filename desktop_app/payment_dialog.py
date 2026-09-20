"""
Payment Dialog: Transaction history, add payment, view CC info, Mark NFD
Matches LMSGold payment format with table view and action buttons
"""

import logging
import re

from db_error_handling import DatabaseContext
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


def _canonical_payment_method(method_label: str) -> str:
    mapping = {
        "e-transfer": "etransfer",
        "credit card": "credit_card",
        "debit card": "debit_card",
        "cash": "cash",
        "cheque": "cheque",
        "nrr retainer": "nrr",
        "bank transfer": "bank_transfer",
        "other": "other",
    }
    return mapping.get((method_label or "").strip().lower(), "other")


def _extract_nrr_portion(text: str) -> float:
    raw = (text or "").strip()
    if not raw:
        return 0.0

    bracket = re.search(r"\[NRR_PART:\s*(\d+(?:\.\d{1,2})?)\]", raw, flags=re.IGNORECASE)
    if bracket:
        try:
            return float(bracket.group(1))
        except Exception:
            return 0.0

    marker = re.search(r"\bnrr\b\D{0,12}(\d+(?:\.\d{1,2})?)", raw.replace(",", ""), flags=re.IGNORECASE)
    if marker:
        try:
            return float(marker.group(1))
        except Exception:
            return 0.0
    return 0.0


def _strip_nrr_markers(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return ""
    value = re.sub(r"\[NRR_PART:\s*\d+(?:\.\d{1,2})?\]", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\bnrr\b\D{0,12}\d+(?:\.\d{1,2})?", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s{2,}", " ", value).strip()
    return value


def _normalize_hold_method(method_label: str) -> str:
    method = (method_label or "").strip().lower()
    if method in ("nrr retainer", "nrr", "retainer"):
        return "nrr"
    return _canonical_payment_method(method_label)


class PaymentDialog(QDialog):
    """Payment management dialog with transaction history and payment entry"""

    def __init__(self, db, reserve_number, client_id=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.reserve_number = reserve_number
        self.client_id = client_id

        self.setWindowTitle(f"Payment Entry - {reserve_number}")
        self.setGeometry(100, 100, 1200, 700)
        self.setModal(True)

        layout = QVBoxLayout()

        # ===== HEADER WITH RESERVE INFO =====
        header_layout = QHBoxLayout()

        res_label = QLabel(f"Reserve #: {reserve_number}")
        res_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        res_label.setStyleSheet("color: #1a3d7a;")
        header_layout.addWidget(res_label)

        header_layout.addStretch()
        layout.addLayout(header_layout)
        layout.addSpacing(10)

        # ===== TABS =====
        tabs = QTabWidget()

        # Tab 1: Payment History
        history_tab = self.create_history_tab()
        tabs.addTab(history_tab, "📊 Payment History")

        # Tab 2: Add Payment
        add_payment_tab = self.create_add_payment_tab()
        tabs.addTab(add_payment_tab, "+ Add Payment")

        # Tab 3: Client CC Info
        cc_info_tab = self.create_cc_info_tab()
        tabs.addTab(cc_info_tab, "💳 Credit Card Info")

        layout.addWidget(tabs)

        # ===== SUMMARY FOOTER =====
        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(30)

        total_charges_label = QLabel("Total Charges:")
        self.total_charges_display = QLineEdit()
        self.total_charges_display.setReadOnly(True)
        self.total_charges_display.setMaximumWidth(120)
        summary_layout.addWidget(total_charges_label)
        summary_layout.addWidget(self.total_charges_display)

        payments_label = QLabel("Payments:")
        self.payments_display = QLineEdit()
        self.payments_display.setReadOnly(True)
        self.payments_display.setMaximumWidth(120)
        summary_layout.addWidget(payments_label)
        summary_layout.addWidget(self.payments_display)

        balance_label = QLabel("Balance Due:")
        self.balance_display = QLineEdit()
        self.balance_display.setReadOnly(True)
        self.balance_display.setMaximumWidth(120)
        self.balance_display.setStyleSheet("background-color: #fff3cd;")
        summary_layout.addWidget(balance_label)
        summary_layout.addWidget(self.balance_display)

        summary_layout.addStretch()
        layout.addLayout(summary_layout)

        # ===== ACTION BUTTONS =====
        button_layout = QHBoxLayout()

        self.mark_nfd_btn = QPushButton("❌ Mark NFD (No Funds)")
        self.mark_nfd_btn.clicked.connect(self.mark_nfd)
        self.mark_nfd_btn.setStyleSheet("background-color: #ff6b6b; color: white;")
        button_layout.addWidget(self.mark_nfd_btn)

        self.email_receipt_btn = QPushButton("📧 Email Receipt")
        self.email_receipt_btn.clicked.connect(self.email_receipt)
        button_layout.addWidget(self.email_receipt_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Load payment data
        self.load_payment_history()
        self.load_summary()

    def create_history_tab(self) -> object:
        """Tab 1: Payment history table matching LMSGold format"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("PAYMENT & CHARGE HISTORY")
        title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        layout.addWidget(title)

        # Transaction table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(8)  # Added record_id column (hidden)
        self.history_table.setHorizontalHeaderLabels(
            [
                "Date",
                "Type",
                "Description",
                "Amount",
                "Reference",
                "Balance",
                "Status",
                "ID",
            ]
        )
        self.history_table.setColumnHidden(7, True)  # Hide ID column
        self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.history_table.resizeColumnsToContents()
        layout.addWidget(self.history_table)

        # Action buttons
        action_layout = QHBoxLayout()

        delete_btn = QPushButton("🗑️ Delete")
        delete_btn.clicked.connect(self.delete_transaction)
        action_layout.addWidget(delete_btn)

        edit_btn = QPushButton("✏️ Edit")
        edit_btn.clicked.connect(self.edit_transaction)
        action_layout.addWidget(edit_btn)

        move_btn = QPushButton("↔ Move To Charter")
        move_btn.clicked.connect(self.move_transaction_to_charter)
        action_layout.addWidget(move_btn)

        unassign_btn = QPushButton("⤴ Unassign")
        unassign_btn.clicked.connect(self.unassign_transaction)
        action_layout.addWidget(unassign_btn)

        action_layout.addStretch()
        layout.addLayout(action_layout)

        widget.setLayout(layout)
        return widget

    def create_add_payment_tab(self) -> object:
        """Tab 2: Add new payment entry"""
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("ADD PAYMENT")
        title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        layout.addWidget(title)

        # Payment form
        form_layout = QVBoxLayout()
        form_layout.setSpacing(8)

        # Row 1: Date and Amount
        row1 = QHBoxLayout()

        date_label = QLabel("Payment Date:")
        date_label.setMinimumWidth(100)
        self.payment_date = QDateEdit()
        self.payment_date.setCalendarPopup(True)
        self.payment_date.setDate(QDate.currentDate())
        self.payment_date.setMaximumWidth(150)
        row1.addWidget(date_label)
        row1.addWidget(self.payment_date)
        row1.addSpacing(30)

        amount_label = QLabel("Amount:")
        amount_label.setMinimumWidth(100)
        self.payment_amount = QDoubleSpinBox()
        self.payment_amount.setMinimum(0)
        self.payment_amount.setMaximum(999999)
        self.payment_amount.setDecimals(2)
        self.payment_amount.setPrefix("$")
        self.payment_amount.setMaximumWidth(150)
        row1.addWidget(amount_label)
        row1.addWidget(self.payment_amount)
        row1.addStretch()
        form_layout.addLayout(row1)

        # Row 2: Payment Method
        row2 = QHBoxLayout()

        method_label = QLabel("Payment Method:")
        method_label.setMinimumWidth(100)
        self.payment_method = QComboBox()
        self.payment_method.addItems(
            [
                "E-Transfer",
                "Credit Card",
                "Cash",
                "Cheque",
                "NRR Retainer",
                "Bank Transfer",
                "Other",
            ]
        )
        self.payment_method.setMaximumWidth(200)
        row2.addWidget(method_label)
        row2.addWidget(self.payment_method)
        row2.addSpacing(30)

        # Reference on the same row as payment method
        ref_label = QLabel("Reference/Check #:")
        ref_label.setMinimumWidth(100)
        self.payment_reference = QLineEdit()
        self.payment_reference.setPlaceholderText("e.g., transaction ID, check number")
        self.payment_reference.setMaximumWidth(260)
        row2.addWidget(ref_label)
        row2.addWidget(self.payment_reference)
        row2.addStretch()
        form_layout.addLayout(row2)

        # Row 4: Notes
        notes_label = QLabel("Notes:")
        notes_label.setMinimumWidth(100)
        notes_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.payment_notes = QTextEdit()
        self.payment_notes.setPlaceholderText("Optional split marker examples: nrr=500 or [NRR_PART:500]")
        self.payment_notes.setMaximumHeight(80)
        row4 = QHBoxLayout()
        row4.addWidget(notes_label)
        row4.addWidget(self.payment_notes)
        form_layout.addLayout(row4)

        layout.addLayout(form_layout)
        layout.addSpacing(10)

        # Submit button
        submit_btn = QPushButton("💾 Record Payment")
        submit_btn.clicked.connect(self.record_payment)
        submit_btn.setStyleSheet(
            "background-color: #28a745; color: white; padding: 8px;" "font-weight: bold;"
        )
        layout.addWidget(submit_btn)

        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def create_cc_info_tab(self) -> object:
        """Tab 3: Credit Card and contact information (for payment entry"
        "only)"""

        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("CLIENT PAYMENT INFORMATION")
        title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        layout.addWidget(title)

        # CC Info Section
        cc_title = QLabel("CREDIT CARD ON FILE")
        cc_title.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        cc_title.setStyleSheet("color: #555;")
        layout.addWidget(cc_title)

        # Row 1: Card Type and Last 4
        row1 = QHBoxLayout()

        card_type_label = QLabel("Card Type:")
        card_type_label.setMinimumWidth(100)
        self.cc_card_type = QLineEdit()
        self.cc_card_type.setReadOnly(True)
        self.cc_card_type.setMaximumWidth(150)
        row1.addWidget(card_type_label)
        row1.addWidget(self.cc_card_type)
        row1.addSpacing(30)

        card_last4_label = QLabel("Last 4 Digits:")
        card_last4_label.setMinimumWidth(100)
        self.cc_last4 = QLineEdit()
        self.cc_last4.setReadOnly(True)
        self.cc_last4.setMaximumWidth(150)
        row1.addWidget(card_last4_label)
        row1.addWidget(self.cc_last4)
        row1.addSpacing(30)

        # Expiry on the same line as card type / last 4
        expiry_label = QLabel("Expiry Date:")
        expiry_label.setMinimumWidth(100)
        self.cc_expiry = QLineEdit()
        self.cc_expiry.setReadOnly(True)
        self.cc_expiry.setMaximumWidth(150)
        row1.addWidget(expiry_label)
        row1.addWidget(self.cc_expiry)
        row1.addStretch()
        layout.addLayout(row1)

        layout.addSpacing(15)

        # Email Info Section
        email_title = QLabel("CONTACT INFORMATION")
        email_title.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        email_title.setStyleSheet("color: #555;")
        layout.addWidget(email_title)

        # Email and phone on a single row
        row3 = QHBoxLayout()

        email_label = QLabel("Email:")
        email_label.setMinimumWidth(100)
        self.client_email = QLineEdit()
        self.client_email.setPlaceholderText("client@example.com")
        self.client_email.setMaximumWidth(260)
        row3.addWidget(email_label)
        row3.addWidget(self.client_email)
        row3.addSpacing(30)

        phone_label = QLabel("Phone:")
        phone_label.setMinimumWidth(100)
        self.client_phone = QLineEdit()
        self.client_phone.setPlaceholderText("(555) 123-4567")
        self.client_phone.setMaximumWidth(200)
        row3.addWidget(phone_label)
        row3.addWidget(self.client_phone)
        row3.addStretch()
        layout.addLayout(row3)

        layout.addSpacing(15)

        # Save button for contact info
        save_contact_btn = QPushButton("💾 Update Contact Information")
        save_contact_btn.clicked.connect(self.save_contact_info)
        layout.addWidget(save_contact_btn)

        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def load_payment_history(self) -> None:
        """Load payment and charge history for this charter"""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    "SELECT charter_id FROM charters WHERE reserve_number = %s LIMIT 1",
                    (self.reserve_number,),
                )
                charter_row = cur.fetchone()
                charter_id_text = str(charter_row[0]) if charter_row and charter_row[0] is not None else ""

                # Primary source: charter_payments
                cur.execute(
                    """
                    SELECT
                        DATE(p.payment_date) as payment_date,
                        'PAYMENT' as type,
                        CASE
                            WHEN LOWER(COALESCE(p.payment_method, '')) IN ('nrr', 'retainer')
                              OR LOWER(COALESCE(p.payment_key, '')) LIKE '%%nrr%%'
                              OR LOWER(COALESCE(p.source, '')) LIKE '%%nrr%%'
                            THEN 'NRR Retainer'
                            WHEN LOWER(COALESCE(p.source, '')) LIKE '%%escrow%%'
                              OR LOWER(COALESCE(p.payment_key, '')) LIKE '%%escrow%%'
                            THEN 'Escrow Hold'
                            ELSE COALESCE(p.payment_method, 'Unknown')
                        END as description,
                        p.amount as amount,
                        COALESCE(p.source, '') as reference,
                        0 as balance,
                        COALESCE(p.payment_label, '') as status,
                        p.id as record_id
                    FROM charter_payments p
                    WHERE CAST(p.charter_id AS TEXT) = %s
                       OR (%s <> '' AND CAST(p.charter_id AS TEXT) = %s)
                """,
                    (self.reserve_number, charter_id_text, charter_id_text),
                )
                payment_rows = cur.fetchall() or []

                # Legacy fallback: mirror invoice packet behavior for older data.
                if not payment_rows:
                    cur.execute(
                        """
                        SELECT
                            DATE(p.payment_date) as payment_date,
                            'LEGACY_PAYMENT' as type,
                            CASE
                                WHEN LOWER(COALESCE(p.payment_label, '')) LIKE '%%nrr%%'
                                  OR LOWER(COALESCE(p.notes, '')) LIKE '%%nrr%%'
                                THEN 'NRR Retainer'
                                WHEN LOWER(COALESCE(p.payment_label, '')) LIKE '%%escrow%%'
                                  OR LOWER(COALESCE(p.notes, '')) LIKE '%%escrow%%'
                                THEN 'Escrow Hold'
                                ELSE COALESCE(p.payment_method, 'Other')
                            END as description,
                            COALESCE(p.amount, 0) as amount,
                            COALESCE(p.reference_number, '') as reference,
                            0 as balance,
                            COALESCE(p.payment_label, 'legacy') as status,
                            p.payment_id as record_id
                        FROM payments p
                        WHERE p.reserve_number = %s
                           OR (%s <> '' AND CAST(p.charter_id AS TEXT) = %s)
                        ORDER BY p.payment_date DESC, p.payment_id DESC
                        """,
                        (self.reserve_number, charter_id_text, charter_id_text),
                    )
                    payment_rows = cur.fetchall() or []

                cur.execute(
                    """
                    SELECT
                        DATE(ch.created_at) as charge_date,
                        'CHARGE' as type,
                        ch.description as description,
                        ch.amount as amount,
                        '' as reference,
                        0 as balance,
                        'Applied' as status,
                        ch.charge_id as record_id
                    FROM charter_charges ch
                    WHERE ch.reserve_number = %s
                    ORDER BY ch.created_at DESC, ch.charge_id DESC
                    """,
                    (self.reserve_number,),
                )
                charge_rows = cur.fetchall() or []

                rows = list(payment_rows) + list(charge_rows)

            rows.sort(key=lambda row: str(row[0] or ""), reverse=True)

            # Populate table
            self.history_table.setRowCount(0)

            for row_num, row_data in enumerate(rows):
                self.history_table.insertRow(row_num)

                for col_num, value in enumerate(row_data):
                    if col_num == 3:  # Amount column
                        text = f"${float(value):.2f}" if value else "$0.00"
                    else:
                        text = str(value) if value else ""

                    item = QTableWidgetItem(text)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                    # Highlight payments in green, charges in red
                    if col_num == 1:  # Type column
                        if value == "PAYMENT":
                            item.setBackground(QColor(220, 240, 220))
                        elif value == "LEGACY_PAYMENT":
                            item.setBackground(QColor(220, 230, 245))
                        elif value == "CHARGE":
                            item.setBackground(QColor(240, 220, 220))

                    self.history_table.setItem(row_num, col_num, item)

            self.history_table.resizeColumnsToContents()

        except Exception as e:
            logger.error(f"Failed to load payment history: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load payment history: {e!s}")

    def load_summary(self) -> None:
        """Load and display payment summary (Total Charges, Payments,"
        "Balance)"""

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                # Use stored values from charters row
                cur.execute(
                    """
                    SELECT COALESCE(grand_total, 0),
                           COALESCE(amount_paid, 0),
                           COALESCE(balance_owing, 0)
                    FROM charters
                    WHERE reserve_number = %s
                """,
                    (self.reserve_number,),
                )

                row = cur.fetchone()
                total_charges = float(row[0]) if row else 0
                total_paid = float(row[1]) if row else 0
                balance = float(row[2]) if row else 0

            # Update displays
            self.total_charges_display.setText(f"${total_charges:.2f}")
            self.payments_display.setText(f"${total_paid:.2f}")
            self.balance_display.setText(f"${balance:.2f}")

        except Exception as e:
            logger.error(f"Failed to load summary: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load summary: {e!s}")

    def record_payment(self) -> None:
        """Record a new payment"""
        if self.payment_amount.value() <= 0:
            QMessageBox.warning(self, "Invalid Amount", "Please enter a valid payment amount")
            return

        payment_total = round(float(self.payment_amount.value()), 2)
        method_val = _canonical_payment_method(self.payment_method.currentText())
        reference_txt = self.payment_reference.text().strip()
        notes_txt = self.payment_notes.toPlainText().strip()
        nrr_portion = max(0.0, float(_extract_nrr_portion(notes_txt) or 0.0))
        if method_val == "nrr" and nrr_portion <= 0:
            nrr_portion = payment_total
        nrr_portion = min(nrr_portion, payment_total)
        cleaned_notes = _strip_nrr_markers(notes_txt)

        source_parts = ["manual"]
        if reference_txt:
            source_parts.append(reference_txt)
        if cleaned_notes:
            source_parts.append(cleaned_notes)
        source_val = " | ".join(source_parts)

        split_created = nrr_portion > 0 and nrr_portion < payment_total

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "SELECT charter_id, total_amount_due FROM charters WHERE reserve_number = %s LIMIT 1",
                    (self.reserve_number,),
                )
                charter_row = cur.fetchone()
                charter_id_text = str(charter_row[0]) if charter_row and charter_row[0] is not None else self.reserve_number
                client_id_val = self.client_id
                if client_id_val is None:
                    cur.execute(
                        "SELECT client_id FROM charters WHERE reserve_number = %s LIMIT 1",
                        (self.reserve_number,),
                    )
                    client_row = cur.fetchone()
                    client_id_val = client_row[0] if client_row and client_row[0] is not None else None

                def _insert_client_hold(amount: float, hold_method: str, hold_note: str) -> None:
                    if client_id_val is None:
                        raise RuntimeError("client_id_required_for_hold")
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
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'escrow', NOW(), NOW())
                        """,
                        (
                            int(client_id_val),
                            self.payment_date.date().toPyDate(),
                            round(amount, 2),
                            round(amount, 2),
                            hold_method,
                            self.reserve_number,
                            hold_note,
                            "nrr_retainer",
                        ),
                    )

                if split_created:
                    base_amount = round(payment_total - nrr_portion, 2)
                    if base_amount > 0:
                        base_method = method_val if method_val != "nrr" else "etransfer"
                        cur.execute(
                            """
                            INSERT INTO charter_payments (
                                charter_id,
                                payment_date,
                                amount,
                                payment_method,
                                source,
                                imported_at)
                            VALUES (%s, %s, %s, %s, %s, NOW())
                        """,
                            (
                                charter_id_text,
                                self.payment_date.date().toPyDate(),
                                base_amount,
                                base_method,
                                source_val,
                            ),
                        )
                    _insert_client_hold(
                        round(nrr_portion, 2),
                        _normalize_hold_method(self.payment_method.currentText()),
                        f"NRR held from reserve #{self.reserve_number}",
                    )
                else:
                    if nrr_portion > 0:
                        _insert_client_hold(
                            round(nrr_portion, 2),
                            _normalize_hold_method(self.payment_method.currentText()),
                            f"NRR held from reserve #{self.reserve_number}",
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO charter_payments (
                                charter_id,
                                payment_date,
                                amount,
                                payment_method,
                                source,
                                imported_at)
                            VALUES (%s, %s, %s, %s, %s, NOW())
                        """,
                            (
                                charter_id_text,
                                self.payment_date.date().toPyDate(),
                                payment_total,
                                method_val,
                                source_val,
                            ),
                        )

                # Keep charter summary columns aligned with posted payments.
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
                        SELECT COALESCE(SUM(p.amount), 0) AS total_paid
                        FROM charter_payments p
                        WHERE CAST(p.charter_id AS TEXT) = %s
                           OR CAST(p.charter_id AS TEXT) = %s
                    ) paid
                    WHERE c.reserve_number = %s
                    """,
                    (self.reserve_number, charter_id_text, self.reserve_number),
                )

            if split_created:
                QMessageBox.information(
                    self,
                    "Success",
                    (
                        "Payment recorded and split successfully\n"
                        f"Base: ${payment_total - nrr_portion:.2f}\n"
                        f"NRR held: ${nrr_portion:.2f}"
                    ),
                )
            elif nrr_portion > 0:
                QMessageBox.information(
                    self,
                    "Success",
                    f"NRR held as escrow: ${nrr_portion:.2f}",
                )
            else:
                QMessageBox.information(self, "Success", "Payment recorded successfully")

            # Clear form
            self.payment_amount.setValue(0)
            self.payment_reference.clear()
            self.payment_notes.clear()

            # Reload history and summary
            self.load_payment_history()
            self.load_summary()

        except Exception as e:
            logger.error(f"Failed to record payment: {e}")
            QMessageBox.critical(self, "Error", f"Failed to record payment: {e!s}")

    def mark_nfd(self) -> None:
        """Mark payment as No Funds Deposit (NFD)"""
        if (
            QMessageBox.question(
                self,
                "Confirm",
                "Mark this charter as NFD (No Funds)?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        ):
            try:
                with DatabaseContext(self.db, auto_commit=True) as cur:
                    # Record NFD charge in charter_charges
                    cur.execute(
                        """
                        INSERT INTO charter_charges (
                            reserve_number,
                            description,
                            amount,
                            charge_type,
                            created_at)
                        VALUES (%s, %s, %s, %s, NOW())
                    """,
                        (
                            self.reserve_number,
                            "NSF - No Funds Deposit",
                            25.00,  # Standard NSF fee
                            "nfd",
                        ),
                    )

                QMessageBox.information(self, "Success", "NFD recorded - $25.00 fee applied")

                # Reload
                self.load_payment_history()
                self.load_summary()

            except Exception as e:
                logger.error(f"Failed to record NFD: {e}")
                QMessageBox.critical(self, "Error", f"Failed to record NFD: {e!s}")

    def email_receipt(self) -> None:
        """Email payment receipt to client"""
        email = self.client_email.text().strip()

        if not email:
            QMessageBox.warning(self, "Missing Email", "Please enter client email address")
            return

        QMessageBox.information(
            self,
            "Email Receipt",
            f"Receipt would be sent to: {email}\n\n(Email integration not yet implemented)",
        )

    def delete_transaction(self) -> None:
        """Delete selected payment or charge (admin authority)"""
        selected = self.history_table.selectedIndexes()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a transaction to delete")
            return

        row = selected[0].row()
        transaction_type = self.history_table.item(row, 1).text()
        if transaction_type == "LEGACY_PAYMENT":
            QMessageBox.warning(
                self,
                "Legacy Payment",
                "This row is from the legacy payments table. Delete it from the legacy payments workflow.",
            )
            return
        amount = self.history_table.item(row, 3).text()
        description = self.history_table.item(row, 2).text()
        record_id_item = self.history_table.item(row, 7)  # Hidden column with record_id

        if not record_id_item:
            QMessageBox.warning(self, "Error", "Could not identify transaction ID")
            return

        record_id = record_id_item.text()

        # Confirm deletion with details
        if (
            QMessageBox.question(
                self,
                "Confirm Delete",
                f"Delete "
                f"{transaction_type.lower()}?\n\n{description}\nAmount: "
                f"{amount}\n\nThis cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        ):
            try:
                with DatabaseContext(self.db, auto_commit=True) as cur:
                    cur.execute(
                        "SELECT charter_id FROM charters WHERE reserve_number = %s LIMIT 1",
                        (self.reserve_number,),
                    )
                    charter_row = cur.fetchone()
                    charter_id_text = str(charter_row[0]) if charter_row and charter_row[0] is not None else ""

                    if transaction_type == "PAYMENT":
                        cur.execute(
                            """
                            DELETE FROM charter_payments
                            WHERE id = %s
                              AND (
                                    CAST(charter_id AS TEXT) = %s
                                 OR (%s <> '' AND CAST(charter_id AS TEXT) = %s)
                              )
                        """,
                            (record_id, self.reserve_number, charter_id_text, charter_id_text),
                        )
                    elif transaction_type == "CHARGE":
                        cur.execute(
                            """
                            DELETE FROM charter_charges
                            WHERE charge_id = %s AND reserve_number = %s
                        """,
                            (record_id, self.reserve_number),
                        )
                    else:
                        QMessageBox.warning(self, "Error", "Unknown transaction type")
                        return

                    if cur.rowcount == 0:
                        QMessageBox.warning(
                            self,
                            "Not Found",
                            "Transaction not found or already deleted",
                        )
                        return

                    if transaction_type == "PAYMENT":
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
                                SELECT COALESCE(SUM(p.amount), 0) AS total_paid
                                FROM charter_payments p
                                WHERE CAST(p.charter_id AS TEXT) = %s
                                   OR (%s <> '' AND CAST(p.charter_id AS TEXT) = %s)
                            ) paid
                            WHERE c.reserve_number = %s
                            """,
                            (self.reserve_number, charter_id_text, charter_id_text, self.reserve_number),
                        )

                QMessageBox.information(
                    self,
                    "Deleted",
                    f"{transaction_type.capitalize()} deleted: {amount}",
                )

                # Reload history and summary
                self.load_payment_history()
                self.load_summary()

            except Exception as e:
                logger.error(f"Failed to delete {transaction_type.lower()}: {e}")
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to delete {transaction_type.lower()}: {e!s}",
                )

    def _recalc_charter_payment_summary(
        self,
        cur,
        reserve_number: str,
        charter_id_text: str,
    ) -> None:
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
                SELECT COALESCE(SUM(p.amount), 0) AS total_paid
                FROM charter_payments p
                WHERE CAST(p.charter_id AS TEXT) = %s
                   OR CAST(p.charter_id AS TEXT) = %s
            ) paid
            WHERE c.reserve_number = %s
            """,
            (reserve_number, charter_id_text, reserve_number),
        )

    def move_transaction_to_charter(self) -> None:
        """Move a selected posted payment to a different charter reserve."""
        selected = self.history_table.selectedIndexes()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a payment to move")
            return

        row = selected[0].row()
        transaction_type = self.history_table.item(row, 1).text()
        if transaction_type != "PAYMENT":
            QMessageBox.warning(self, "Invalid Selection", "Only payments can be moved.")
            return

        record_id_item = self.history_table.item(row, 7)
        if not record_id_item:
            QMessageBox.warning(self, "Error", "Could not identify payment ID")
            return
        record_id = record_id_item.text().strip()
        if not record_id:
            QMessageBox.warning(self, "Error", "Invalid payment ID")
            return

        target_reserve, ok = QInputDialog.getText(
            self,
            "Move Payment",
            "Enter target reserve number:",
            text="",
        )
        if not ok:
            return

        target_reserve = (target_reserve or "").strip()
        if not target_reserve:
            QMessageBox.warning(self, "Missing Reserve", "Target reserve number is required.")
            return
        if target_reserve == self.reserve_number:
            QMessageBox.information(
                self,
                "No Change",
                "Target reserve matches the current charter.",
            )
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "SELECT charter_id FROM charters WHERE reserve_number = %s LIMIT 1",
                    (self.reserve_number,),
                )
                source_charter_row = cur.fetchone()
                source_charter_id_text = (
                    str(source_charter_row[0])
                    if source_charter_row and source_charter_row[0] is not None
                    else ""
                )

                cur.execute(
                    "SELECT charter_id FROM charters WHERE reserve_number = %s LIMIT 1",
                    (target_reserve,),
                )
                target_row = cur.fetchone()
                if not target_row or target_row[0] is None:
                    QMessageBox.warning(
                        self,
                        "Target Not Found",
                        f"No charter found for reserve {target_reserve}.",
                    )
                    return
                target_charter_id_text = str(target_row[0])

                cur.execute(
                    """
                    UPDATE charter_payments
                    SET charter_id = %s,
                        imported_at = COALESCE(imported_at, NOW())
                    WHERE id = %s
                      AND (
                            CAST(charter_id AS TEXT) = %s
                         OR (%s <> '' AND CAST(charter_id AS TEXT) = %s)
                      )
                    """,
                    (
                        target_charter_id_text,
                        record_id,
                        self.reserve_number,
                        source_charter_id_text,
                        source_charter_id_text,
                    ),
                )

                if cur.rowcount == 0:
                    QMessageBox.warning(
                        self,
                        "Move Failed",
                        "Payment not found on the current charter, or already moved.",
                    )
                    return

                self._recalc_charter_payment_summary(
                    cur,
                    self.reserve_number,
                    source_charter_id_text,
                )
                self._recalc_charter_payment_summary(
                    cur,
                    target_reserve,
                    target_charter_id_text,
                )

            QMessageBox.information(
                self,
                "Payment Moved",
                f"Payment #{record_id} moved to reserve {target_reserve}.",
            )
            self.load_payment_history()
            self.load_summary()

        except Exception as e:
            logger.error(f"Failed to move payment: {e}")
            QMessageBox.critical(self, "Error", f"Failed to move payment: {e!s}")

    def unassign_transaction(self) -> None:
        """Unassign a selected posted payment from this charter."""
        selected = self.history_table.selectedIndexes()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a payment to unassign")
            return

        row = selected[0].row()
        transaction_type = self.history_table.item(row, 1).text()
        if transaction_type != "PAYMENT":
            QMessageBox.warning(self, "Invalid Selection", "Only payments can be unassigned.")
            return

        record_id_item = self.history_table.item(row, 7)
        if not record_id_item:
            QMessageBox.warning(self, "Error", "Could not identify payment ID")
            return
        record_id = record_id_item.text().strip()
        if not record_id:
            QMessageBox.warning(self, "Error", "Invalid payment ID")
            return

        if (
            QMessageBox.question(
                self,
                "Confirm Unassign",
                f"Unassign payment #{record_id} from reserve {self.reserve_number}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "SELECT charter_id FROM charters WHERE reserve_number = %s LIMIT 1",
                    (self.reserve_number,),
                )
                source_charter_row = cur.fetchone()
                source_charter_id_text = (
                    str(source_charter_row[0])
                    if source_charter_row and source_charter_row[0] is not None
                    else ""
                )

                cur.execute(
                    """
                    UPDATE charter_payments
                    SET charter_id = NULL,
                        source = COALESCE(source, '') || ' | unassigned:' || NOW()::text,
                        imported_at = COALESCE(imported_at, NOW())
                    WHERE id = %s
                      AND (
                            CAST(charter_id AS TEXT) = %s
                         OR (%s <> '' AND CAST(charter_id AS TEXT) = %s)
                      )
                    """,
                    (
                        record_id,
                        self.reserve_number,
                        source_charter_id_text,
                        source_charter_id_text,
                    ),
                )

                if cur.rowcount == 0:
                    QMessageBox.warning(
                        self,
                        "Unassign Failed",
                        "Payment not found on the current charter, or already unassigned.",
                    )
                    return

                self._recalc_charter_payment_summary(
                    cur,
                    self.reserve_number,
                    source_charter_id_text,
                )

            QMessageBox.information(
                self,
                "Payment Unassigned",
                f"Payment #{record_id} was unassigned from reserve {self.reserve_number}.",
            )
            self.load_payment_history()
            self.load_summary()

        except Exception as e:
            logger.error(f"Failed to unassign payment: {e}")
            QMessageBox.critical(self, "Error", f"Failed to unassign payment: {e!s}")

    def edit_transaction(self) -> None:
        """Edit selected payment (charges cannot be edited - delete and"
        "re-add instead)"""

        selected = self.history_table.selectedIndexes()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a transaction to edit")
            return

        row = selected[0].row()
        transaction_type = self.history_table.item(row, 1).text()

        if transaction_type != "PAYMENT":
            if transaction_type == "LEGACY_PAYMENT":
                QMessageBox.warning(
                    self,
                    "Cannot Edit",
                    "Legacy payments are read-only in this manager.",
                )
                return
            QMessageBox.warning(
                self,
                "Cannot Edit",
                "Only payments can be edited. To modify a charge, delete it and add a new one.",
            )
            return

        record_id_item = self.history_table.item(row, 7)
        if not record_id_item:
            QMessageBox.warning(self, "Error", "Could not identify payment ID")
            return

        record_id = record_id_item.text()

        # Load payment details into Add Payment tab
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT payment_date, amount, payment_method, source, NULL
                    FROM charter_payments
                    WHERE id = %s
                """,
                    (record_id,),
                )

                payment_data = cur.fetchone()

            if not payment_data:
                QMessageBox.warning(self, "Not Found", "Payment not found")
                return

            # Populate form fields
            self.payment_date.setDate(QDate(payment_data[0]))
            self.payment_amount.setValue(float(payment_data[1]))

            # Set payment method
            method_text = payment_data[2] or "Cash"
            index = self.payment_method.findText(method_text, Qt.MatchFlag.MatchFixedString)
            if index >= 0:
                self.payment_method.setCurrentIndex(index)

            self.payment_reference.setText(payment_data[3] or "")
            self.payment_notes.setPlainText(payment_data[4] or "")

            # Store the payment_id for update
            self.editing_payment_id = record_id

            # Switch to Add Payment tab and notify user
            QMessageBox.information(
                self,
                "Edit Mode",
                "Payment loaded for editing. Modify the fields and click "
                "'Record Payment' to save changes.",
            )

        except Exception as e:
            logger.error(f"Failed to load payment: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load payment: {e!s}")

    def save_contact_info(self) -> None:
        """Save client contact information"""
        email = self.client_email.text().strip()
        phone = self.client_phone.text().strip()

        if not email and not phone:
            QMessageBox.warning(self, "No Data", "Please enter email or phone number")
            return

        try:
            if self.client_id:
                with DatabaseContext(self.db, auto_commit=True) as cur:
                    # Update client record with contact info
                    cur.execute(
                        """
                        UPDATE clients
                        SET email = %s, phone = %s, updated_at = NOW()
                        WHERE client_id = %s
                    """,
                        (email or None, phone or None, self.client_id),
                    )

                QMessageBox.information(self, "Success", "Contact information saved")
            else:
                QMessageBox.warning(self, "No Client", "Client ID not available")

        except Exception as e:
            logger.error(f"Failed to save contact info: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save contact info: {e!s}")
