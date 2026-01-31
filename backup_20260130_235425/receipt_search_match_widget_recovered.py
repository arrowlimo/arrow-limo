"""
Receipt Search & Match Widget (restored minimal version)
Provides a stable search + view interface for receipts and a placeholder for add/update.
Original file was corrupted; this version prioritizes loading without crashes.
"""

from decimal import Decimal
from typing import List

import psycopg2
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QDoubleSpinBox,
    QGroupBox,
    QFormLayout,
    QMessageBox,
    QSplitter,
    QHeaderView,
)

from desktop_app.common_widgets import StandardDateEdit


class DateInput(StandardDateEdit):
    """Keep legacy name used elsewhere; StandardDateEdit already handles parsing."""

    def date(self):
        # Preserve compatibility with QDateEdit API
        return super().date()


class CurrencyInput(QLineEdit):
    """Simple currency field with 2-decimal validation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        validator = QDoubleValidator(0.0, 1_000_000_000.0, 2, self)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.setValidator(validator)
        self.setPlaceholderText("0.00")
        self.setMaxLength(20)

    def value(self) -> Decimal:
        text = (self.text() or "0").replace(",", "").strip()
        try:
            return Decimal(text)
        except Exception:
            return Decimal("0")


class ReceiptSearchMatchWidget(QWidget):
    """Lightweight, crash-safe rebuild of the receipt search/match UI."""

    def __init__(self, conn: psycopg2.extensions.connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.last_results: List[tuple] = []
        self._build_ui()
        self._load_recent()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.search_panel = self._build_search_panel()
        self.detail_panel = self._build_detail_panel()

        splitter.addWidget(self.search_panel)
        splitter.addWidget(self.detail_panel)
        splitter.setSizes([350, 650])

        layout.addWidget(splitter)

    def _build_search_panel(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)

        self.date_from = StandardDateEdit()
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        self.date_to = StandardDateEdit()
        self.date_to.setDate(QDate.currentDate())

        date_row = QHBoxLayout()
        date_row.addWidget(self.date_from)
        date_row.addWidget(QLabel("to"))
        date_row.addWidget(self.date_to)
        form.addRow("Date range", date_row)

        self.vendor_filter = QLineEdit()
        self.vendor_filter.setPlaceholderText("Vendor contains...")
        form.addRow("Vendor", self.vendor_filter)

        self.desc_filter = QLineEdit()
        self.desc_filter.setPlaceholderText("Description contains...")
        form.addRow("Description", self.desc_filter)

        self.amount_filter = QDoubleSpinBox()
        self.amount_filter.setRange(0, 1_000_000_000)
        self.amount_filter.setDecimals(2)
        self.amount_filter.setPrefix("$")
        self.amount_filter.setMaximumWidth(140)
        form.addRow("Amount", self.amount_filter)

        btn_row = QHBoxLayout()
        self.search_btn = QPushButton("🔍 Search")
        self.search_btn.clicked.connect(self._do_search)
        btn_row.addWidget(self.search_btn)

        self.clear_btn = QPushButton("✕ Clear")
        self.clear_btn.clicked.connect(self._clear_filters)
        btn_row.addWidget(self.clear_btn)
        btn_row.addStretch()
        form.addRow("", btn_row)

        self.results_label = QLabel("")
        form.addRow("", self.results_label)

        return panel

    def _build_detail_panel(self) -> QWidget:
        panel = QWidget()
        vbox = QVBoxLayout(panel)

        self.results_table = QTableWidget(0, 6)
        self.results_table.setHorizontalHeaderLabels(
            ["ID", "Date", "Vendor", "Amount", "GL/Category", "Banking ID"]
        )
        header: QHeaderView = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.itemSelectionChanged.connect(self._populate_form_from_selection)
        vbox.addWidget(self.results_table)

        add_box = QGroupBox("Add / Update (temporarily read-only)")
        form = QFormLayout(add_box)

        self.new_date = DateInput()
        form.addRow("Date", self.new_date)

        self.new_vendor = QLineEdit()
        form.addRow("Vendor", self.new_vendor)

        self.new_invoice = QLineEdit()
        form.addRow("Invoice #", self.new_invoice)

        self.new_amount = CurrencyInput()
        form.addRow("Amount", self.new_amount)

        self.new_desc = QLineEdit()
        form.addRow("Description", self.new_desc)

        self.new_gl = QLineEdit()
        self.new_gl.setPlaceholderText("GL code or category")
        form.addRow("GL/Category", self.new_gl)

        self.new_banking_id = QLineEdit()
        form.addRow("Banking Txn ID", self.new_banking_id)

        button_row = QHBoxLayout()
        self.add_btn = QPushButton("✅ Add")
        self.add_btn.setEnabled(False)
        self.add_btn.setToolTip("Disabled in recovery build. Request full restore before adding.")
        self.add_btn.clicked.connect(self._add_receipt)
        button_row.addWidget(self.add_btn)

        self.update_btn = QPushButton("💾 Update")
        self.update_btn.setEnabled(False)
        self.update_btn.clicked.connect(self._update_receipt)
        button_row.addWidget(self.update_btn)

        self.clear_form_btn = QPushButton("⟲ Clear Form")
        self.clear_form_btn.clicked.connect(self._clear_form)
        button_row.addWidget(self.clear_form_btn)
        button_row.addStretch()
        form.addRow("", button_row)

        vbox.addWidget(add_box)
        return panel

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _clear_filters(self):
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        self.date_to.setDate(QDate.currentDate())
        self.vendor_filter.clear()
        self.desc_filter.clear()
        self.amount_filter.setValue(0)
        self.results_label.clear()
        self.results_table.setRowCount(0)

    def _do_search(self):
        sql = [
            "SELECT receipt_id, receipt_date, vendor_name, gross_amount,",
            "COALESCE(gl_account_name, gl_account_code::text, '') AS gl_name,",
            "banking_transaction_id",
            "FROM receipts",
            "WHERE 1=1",
        ]
        params: List[object] = []

        start = self.date_from.date()
        end = self.date_to.date()
        if start and end:
            sql.append("AND receipt_date BETWEEN %s AND %s")
            params.extend([start.toPyDate(), end.toPyDate()])

        vendor = (self.vendor_filter.text() or "").strip()
        if vendor:
            sql.append("AND vendor_name ILIKE %s")
            params.append(f"%{vendor}%")

        desc = (self.desc_filter.text() or "").strip()
        if desc:
            sql.append("AND description ILIKE %s")
            params.append(f"%{desc}%")

        amt = self.amount_filter.value()
        if amt > 0:
            sql.append("AND gross_amount BETWEEN %s AND %s")
            params.extend([amt - 1, amt + 1])

        sql.append("ORDER BY receipt_date DESC, receipt_id DESC LIMIT 200")

        try:
            cur = self.conn.cursor()
            cur.execute("\n".join(sql), params)
            rows = cur.fetchall()
            cur.close()
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Search Error", f"Could not run search:\n\n{e}")
            return

        self.last_results = rows
        self._populate_table(rows)
        self.results_label.setText(f"Found {len(rows)} rows")

    def _populate_table(self, rows: List[tuple]):
        self.results_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            rid, rdate, vendor, amount, gl_name, banking_id = row
            self.results_table.setItem(r, 0, QTableWidgetItem(str(rid)))
            self.results_table.setItem(r, 1, QTableWidgetItem(str(rdate)))
            amt_item = QTableWidgetItem(f"${amount:,.2f}" if amount is not None else "")
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.results_table.setItem(r, 2, QTableWidgetItem(vendor or ""))
            self.results_table.setItem(r, 3, amt_item)
            self.results_table.setItem(r, 4, QTableWidgetItem(gl_name or ""))
            self.results_table.setItem(r, 5, QTableWidgetItem(str(banking_id) if banking_id else ""))

    def _populate_form_from_selection(self):
        selected = self.results_table.selectedItems()
        if not selected:
            self._clear_form()
            return
        row = selected[0].row()
        try:
            date_item = self.results_table.item(row, 1)
            vendor_item = self.results_table.item(row, 2)
            amt_item = self.results_table.item(row, 3)
            gl_item = self.results_table.item(row, 4)
            banking_item = self.results_table.item(row, 5)

            self.new_date.setDate(QDate.fromString(date_item.text(), "yyyy-MM-dd"))
            self.new_vendor.setText(vendor_item.text())
            self.new_invoice.clear()
            self.new_amount.setText(amt_item.text().replace("$", "").replace(",", ""))
            self.new_desc.setText("")
            self.new_gl.setText(gl_item.text())
            self.new_banking_id.setText(banking_item.text())
            self.update_btn.setEnabled(False)  # Disabled in recovery build
        except Exception:
            self._clear_form()

    def _clear_form(self):
        today = QDate.currentDate()
        self.new_date.setDate(today)
        self.new_vendor.clear()
        self.new_invoice.clear()
        self.new_amount.clear()
        self.new_desc.clear()
        self.new_gl.clear()
        self.new_banking_id.clear()
        self.update_btn.setEnabled(False)
        self.add_btn.setEnabled(False)

    def _add_receipt(self):
        QMessageBox.information(
            self,
            "Add temporarily disabled",
            "The original widget was corrupted. This recovery build disables add/update to avoid data loss."
            " Please request a full restore if you need write operations.",
        )

    def _update_receipt(self):
        QMessageBox.information(
            self,
            "Update temporarily disabled",
            "The original widget was corrupted. This recovery build disables add/update to avoid data loss."
            " Please request a full restore if you need write operations.",
        )

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------
    def _load_recent(self):
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT receipt_id, receipt_date, vendor_name, gross_amount,
                       COALESCE(gl_account_name, gl_account_code::text, '') AS gl_name,
                       banking_transaction_id
                FROM receipts
                ORDER BY receipt_date DESC, receipt_id DESC
                LIMIT 50
                """
            )
            rows = cur.fetchall()
            cur.close()
            self.last_results = rows
            self._populate_table(rows)
            self.results_label.setText(f"Recent 50 receipts loaded ({len(rows)})")
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.warning(self, "Load Error", f"Could not load recent receipts:\n\n{e}")


__all__ = ["ReceiptSearchMatchWidget"]
