"""
Receipt Search & Match Widget (restored minimal version)
Provides a stable search + view interface for receipts and a placeholder for add/update.
Original file was corrupted; this version prioritizes loading without crashes.
"""

import os
import json
from decimal import Decimal
from typing import List

import psycopg2
from PyQt6.QtCore import Qt, QDate, QTimer, QSize
from PyQt6.QtGui import QDoubleValidator, QGuiApplication, QPainter, QColor, QFont
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
    QComboBox,
    QCompleter,
    QDialog,
    QPlainTextEdit,
    QDialogButtonBox,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QStyledItemDelegate,
    QStyle,
    QScrollArea,
    QCheckBox,
    QRadioButton,
)

from desktop_app.common_widgets import StandardDateEdit


class DateInput(QLineEdit):
    """Flexible date input like Excel: supports multiple formats and shortcuts.

    Supports:
    - t / T = today
    - y / Y = yesterday
    - MM/DD/YYYY, M/D/YYYY
    - YYYY-MM-DD, YYYY/MM/DD
    - YYYYMMDD
    - DD MMM YYYY, MMM DD YYYY, Month DD YYYY
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_date = QDate.currentDate()
        self.setText(self._current_date.toString("MM/dd/yyyy"))
        self.setPlaceholderText("MM/DD/YYYY or Jan 01 2012 (t=yesterday)")
        # Tooltip with examples
        self.setToolTip(
            "Examples: 01/17/2026, 1/7/2026, 2026-01-17, 20260117,\n"
            "Jan 17 2026, 17 Jan 2026, January 17 2026, t (today), y (yesterday)"
        )
        self.textChanged.connect(self._on_text_changed)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def _on_text_changed(self, text: str):
        parsed = self._parse_date(text.strip())
        if parsed is None:
            # Invalid → light red bg
            self.setStyleSheet("background-color: #ffecec; border: 1px solid #cc0000;")
        else:
            self._current_date = parsed
            # Valid → light green bg
            self.setStyleSheet("background-color: #eaffea; border: 1px solid #00aa00;")

    def _parse_date(self, s: str) -> QDate | None:
        if not s:
            return None
        # Shortcuts
        if s.lower() == 't':
            return QDate.currentDate()
        if s.lower() == 'y':
            return QDate.currentDate().addDays(-1)

        # Try multiple formats
        from datetime import datetime
        fmts = [
            "%m/%d/%Y", "%m/%d/%y",
            "%Y-%m-%d", "%Y/%m/%d",
            "%Y%m%d",
            "%d %b %Y", "%b %d %Y",
            "%d %B %Y", "%B %d %Y",
        ]
        for fmt in fmts:
            try:
                dt = datetime.strptime(s, fmt)
                return QDate(dt.year, dt.month, dt.day)
            except Exception:
                pass
        # Fallback: try letting QDate parse ISO
        try:
            qd = QDate.fromString(s, "yyyy-MM-dd")
            if qd.isValid():
                return qd
        except Exception:
            pass
        return None

    # API compatibility
    def date(self) -> QDate:
        return self._current_date

    def setDate(self, qdate: QDate):
        if not isinstance(qdate, QDate):
            return
        self._current_date = qdate
        self.setText(qdate.toString("MM/dd/yyyy"))


class CalculatorDialog(QDialog):
    """Simple calculator dialog for quick amount math."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calculator")
        layout = QVBoxLayout(self)
        self.input = QLineEdit(self)
        self.input.setPlaceholderText("Enter expression, e.g., 120+35.5-10")
        layout.addWidget(self.input)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def evaluate(self) -> Decimal | None:
        text = (self.input.text() or "").strip()
        if not text:
            return None
        # Allow only safe characters: digits, dot, parentheses, + - * /
        allowed = set("0123456789.+-*/() ")
        if any(ch not in allowed for ch in text):
            return None
        try:
            # Evaluate in a restricted namespace
            result = eval(text, {"__builtins__": {}}, {})
            return Decimal(str(result))
        except Exception:
            return None


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


class ReceiptCompactDelegate(QStyledItemDelegate):
    """Renders a compact 4-line summary in the Vendor column (index 2)."""

    def paint(self, painter: QPainter, option, index):
        # Only customize the Vendor/Summary column
        if index.column() != 2:
            return super().paint(painter, option, index)

        data = index.data(Qt.ItemDataRole.UserRole) or {}
        date = data.get("date") or ""
        vendor = data.get("vendor") or ""
        amount = data.get("amount")
        amount_str = f"${amount:,.2f}" if isinstance(amount, (int, float)) else (str(amount) if amount else "")
        gl = data.get("gl") or ""
        desc = data.get("description") or ""
        banking_id = data.get("banking_id")
        matched_str = "✓ Matched" if banking_id not in (None, "") else ""
        created_from_banking = data.get("created_from_banking", False)
        source_str = "BANKING_IMPORT" if created_from_banking else ""
        charter = data.get("charter") or ""
        charter_str = f"Charter {charter}" if charter else ""
        payment = data.get("payment_method") or ""
        payment_str = f"Payment {payment}" if payment else ""

        line1 = f"{date} • {vendor} • {amount_str} • {gl}"
        line2 = desc
        line3_parts = [p for p in (matched_str, source_str, charter_str) if p]
        line3 = " • ".join(line3_parts) if line3_parts else ""
        line4 = payment_str
        lines = [l for l in (line1, line2, line3, line4) if l]
        text = "\n".join(lines)

        painter.save()
        # Handle selection background
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
            pen_color = option.palette.highlightedText().color()
        else:
            pen_color = option.palette.text().color()

        # Text styling
        base_font = option.font
        small_font = QFont(base_font)
        small_font.setPointSize(max(8, base_font.pointSize() - 1))
        painter.setFont(small_font)
        painter.setPen(pen_color)

        # Padding inside cell
        rect = option.rect.adjusted(6, 4, -6, -4)
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
        painter.restore()

    def sizeHint(self, option, index):
        # Provide extra height for 4 lines
        fm = option.fontMetrics
        line_height = fm.height()
        total_height = (line_height * 4) + 8  # padding
        return QSize(option.rect.width(), total_height)


class ReceiptSearchMatchWidget(QWidget):
    """Lightweight, crash-safe rebuild of the receipt search/match UI."""

    def __init__(self, conn: psycopg2.extensions.connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.last_results: List[tuple] = []
        self.write_enabled = str(os.environ.get("RECEIPT_WIDGET_WRITE_ENABLED", "false")).lower() in ("1", "true", "yes")
        self.receipts_columns = self._load_receipts_columns()
        self._audit_table_checked = False
        self._audit_table_exists = False
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
        """Left panel: 3-line search filters only"""
        panel = QWidget()
        panel.setMaximumWidth(350)
        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(5, 5, 5, 5)
        vbox.setSpacing(6)

        # ===== LINE 1: Vendor | Include Description =====
        line1 = QHBoxLayout()
        line1.setContentsMargins(0, 0, 0, 0)
        line1.setSpacing(3)
        
        line1.addWidget(QLabel("Vendor:"), 0)
        self.vendor_filter = QLineEdit()
        self.vendor_filter.setPlaceholderText("Type vendor name (fuzzy match, e.g., 'Fibr' finds Fibrenew)")
        self.vendor_filter.setMaximumWidth(160)
        line1.addWidget(self.vendor_filter, 0)
        
        self.include_desc_chk = QCheckBox("Include description")
        self.include_desc_chk.setMaximumWidth(140)
        line1.addWidget(self.include_desc_chk, 0)
        line1.addStretch()
        
        vbox.addLayout(line1)

        # ===== LINE 2: Date Range | Amount +/- | Sum by banking =====
        line2 = QHBoxLayout()
        line2.setContentsMargins(0, 0, 0, 0)
        line2.setSpacing(3)
        
        line2.addWidget(QLabel("Date Range:"), 0)
        self.date_from = StandardDateEdit()
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        self.date_from.setMaximumWidth(90)
        line2.addWidget(self.date_from, 0)
        
        line2.addWidget(QLabel("to"), 0)
        self.date_to = StandardDateEdit()
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setMaximumWidth(90)
        line2.addWidget(self.date_to, 0)
        
        line2.addWidget(QLabel("±"), 0)
        self.date_range_days = QDoubleSpinBox()
        self.date_range_days.setRange(0, 365)
        self.date_range_days.setValue(7)
        self.date_range_days.setSuffix(" days")
        self.date_range_days.setMaximumWidth(75)
        line2.addWidget(self.date_range_days, 0)
        
        line2.addWidget(QLabel("Amount:"), 0)
        self.amount_filter = QDoubleSpinBox()
        self.amount_filter.setRange(0, 1_000_000_000)
        self.amount_filter.setDecimals(2)
        self.amount_filter.setPrefix("$")
        self.amount_filter.setMaximumWidth(70)
        line2.addWidget(self.amount_filter, 0)
        
        line2.addWidget(QLabel("±"), 0)
        self.amount_range = QDoubleSpinBox()
        self.amount_range.setRange(0, 10000)
        self.amount_range.setDecimals(2)
        self.amount_range.setPrefix("$")
        self.amount_range.setValue(1.0)
        self.amount_range.setMaximumWidth(65)
        line2.addWidget(self.amount_range, 0)
        
        self.sum_by_banking_chk = QCheckBox("Sum by banking link")
        self.sum_by_banking_chk.setMaximumWidth(130)
        line2.addWidget(self.sum_by_banking_chk, 0)
        line2.addStretch()
        
        vbox.addLayout(line2)

        # ===== LINE 3: Charter | Show splits | Action Buttons =====
        line3 = QHBoxLayout()
        line3.setContentsMargins(0, 0, 0, 0)
        line3.setSpacing(3)
        
        line3.addWidget(QLabel("Charter:"), 0)
        self.charter_filter = QLineEdit()
        self.charter_filter.setPlaceholderText("Reserve # (e.g., 012345)")
        self.charter_filter.setMaximumWidth(100)
        line3.addWidget(self.charter_filter, 0)
        
        self.show_linked_splits_chk = QCheckBox("Show linked splits")
        self.show_linked_splits_chk.setMaximumWidth(130)
        line3.addWidget(self.show_linked_splits_chk, 0)
        line3.addStretch()
        
        vbox.addLayout(line3)

        # ===== LINE 4: Action Buttons =====
        button_line = QHBoxLayout()
        button_line.setContentsMargins(0, 0, 0, 0)
        button_line.setSpacing(2)
        
        self.find_receipts_btn = QPushButton("Find Receipts")
        self.find_receipts_btn.setMaximumWidth(100)
        self.find_receipts_btn.setMaximumHeight(28)
        self.find_receipts_btn.clicked.connect(self._do_search)
        button_line.addWidget(self.find_receipts_btn, 0)
        
        self.search_btn = QPushButton("🔍 Search")
        self.search_btn.setMaximumWidth(80)
        self.search_btn.setMaximumHeight(28)
        self.search_btn.clicked.connect(self._do_search)
        button_line.addWidget(self.search_btn, 0)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setMaximumWidth(60)
        self.clear_btn.setMaximumHeight(28)
        self.clear_btn.clicked.connect(self._clear_filters)
        button_line.addWidget(self.clear_btn, 0)
        
        self.find_banking_btn = QPushButton("🏦 Banking")
        self.find_banking_btn.setMaximumWidth(85)
        self.find_banking_btn.setMaximumHeight(28)
        self.find_banking_btn.clicked.connect(self._search_banking_transactions)
        button_line.addWidget(self.find_banking_btn, 0)
        
        self.link_to_form_btn = QPushButton("→ Link")
        self.link_to_form_btn.setMaximumWidth(70)
        self.link_to_form_btn.setMaximumHeight(28)
        self.link_to_form_btn.setToolTip("Populate form from selected receipt")
        self.link_to_form_btn.clicked.connect(self._prefill_from_search)
        button_line.addWidget(self.link_to_form_btn, 0)
        
        button_line.addStretch()
        vbox.addLayout(button_line)

        # Status label
        self.results_label = QLabel("(no results)")
        self.results_label.setStyleSheet("color: #666; font-size: 8pt; margin-top: 3px;")
        vbox.addWidget(self.results_label)

        vbox.addStretch()
        return panel

    def _search_banking_transactions(self):
        """Placeholder for banking transaction search."""
        QMessageBox.information(self, "Banking Search", "Banking transaction search coming soon.")

    def _build_detail_panel(self) -> QWidget:
        panel = QWidget()
        vbox = QVBoxLayout(panel)

        # Results table with updated headers
        self.results_table = QTableWidget(0, 6)
        self.results_table.setHorizontalHeaderLabels(
            ["ID", "Date", "Vendor", "Amount", "GL/Category", "Charter"]
        )
        header: QHeaderView = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.itemSelectionChanged.connect(self._populate_form_from_selection)
        # Double-click to drill-down (faster way to populate form)
        self.results_table.doubleClicked.connect(self._populate_form_from_selection)
        vbox.addWidget(self.results_table)

        # Compact view toggle (renders 4-line summary in Vendor column)
        compact_row = QHBoxLayout()
        self.compact_toggle = QPushButton("Compact View")
        self.compact_toggle.setCheckable(True)
        self.compact_toggle.toggled.connect(self._toggle_compact_view)
        compact_row.addWidget(self.compact_toggle)
        compact_row.addStretch()
        vbox.addLayout(compact_row)

        # Charter Lookup Row (for quick reserve_number linking)
        charter_box = QGroupBox("🔗 Charter Lookup")
        charter_form = QFormLayout(charter_box)
        charter_lookup_row = QHBoxLayout()
        self.charter_lookup_input = QLineEdit()
        self.charter_lookup_input.setPlaceholderText("Reserve # (e.g., 012345)")
        self.charter_lookup_input.setMaximumWidth(120)
        charter_lookup_row.addWidget(self.charter_lookup_input)
        self.charter_date_from_lookup = StandardDateEdit()
        self.charter_date_from_lookup.setDate(QDate.currentDate().addDays(-7))
        self.charter_date_from_lookup.setMaximumWidth(120)
        charter_lookup_row.addWidget(QLabel("From"))
        charter_lookup_row.addWidget(self.charter_date_from_lookup)
        self.charter_date_to_lookup = StandardDateEdit()
        self.charter_date_to_lookup.setDate(QDate.currentDate())
        self.charter_date_to_lookup.setMaximumWidth(120)
        charter_lookup_row.addWidget(QLabel("To"))
        charter_lookup_row.addWidget(self.charter_date_to_lookup)
        charter_link_btn = QPushButton("🔍 Link Selected")
        charter_link_btn.clicked.connect(self._link_selected_to_charter)
        charter_lookup_row.addWidget(charter_link_btn)
        charter_lookup_row.addStretch()
        charter_form.addRow("", charter_lookup_row)
        vbox.addWidget(charter_box)

        # Comprehensive form layout matching screenshot
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        form_widget = QWidget()
        form_main_layout = QVBoxLayout(form_widget)
        
        # Document Type selector at top
        doc_type_group = QGroupBox("📄 Add New Receipt or Invoice")
        doc_type_layout = QHBoxLayout(doc_type_group)
        doc_type_layout.addWidget(QLabel("Document Type:"))
        self.doc_type_receipt = QRadioButton("Receipt (Paid Immediately)")
        self.doc_type_invoice = QRadioButton("Invoice (May be unpaid)")
        self.doc_type_receipt.setChecked(True)
        doc_type_layout.addWidget(self.doc_type_receipt)
        doc_type_layout.addWidget(self.doc_type_invoice)
        doc_type_layout.addStretch()
        form_main_layout.addWidget(doc_type_group)
        
        # Main form fields
        self.form_layout = QFormLayout()
        
        # Vendor
        self.new_vendor = QLineEdit()
        self.form_layout.addRow("Vendor:", self.new_vendor)
        QTimer.singleShot(0, self._attach_vendor_completer)

        # Receipt Date
        date_row = QHBoxLayout()
        self.new_date = DateInput()
        self.new_date.setMaximumWidth(120)
        date_row.addWidget(self.new_date)
        date_row.addWidget(QLabel("Format: MM/dd/yyyy"))
        self.form_layout.addRow("Receipt Date:", date_row)

        # Amount
        amt_row = QHBoxLayout()
        self.new_amount = QLineEdit()
        self.new_amount.setPlaceholderText("0.00")
        self.new_amount.setMaximumWidth(100)
        amt_row.addWidget(self.new_amount)
        amt_row.addStretch()
        self.form_layout.addRow("Amount:", amt_row)

        # Manual GST override with enable/disable logic
        gst_override_row = QHBoxLayout()
        self.gst_override_enable = QCheckBox("Manual GST override")
        self.gst_override_input = QDoubleSpinBox()
        self.gst_override_input.setMaximumWidth(100)
        self.gst_override_input.setEnabled(False)
        self.gst_override_reason = QComboBox()
        self.gst_override_reason.addItems(["Manual - Government fee", "Manual - NGO donation", "Manual - test"])
        self.gst_override_reason.setMaximumWidth(200)
        self.gst_override_reason.setEnabled(False)
        self.gst_override_enable.toggled.connect(lambda on: (
            self.gst_override_input.setEnabled(on),
            self.gst_override_reason.setEnabled(on)
        ))
        gst_override_row.addWidget(self.gst_override_enable)
        gst_override_row.addWidget(self.gst_override_input)
        gst_override_row.addWidget(self.gst_override_reason)
        gst_override_row.addStretch()
        self.form_layout.addRow("", gst_override_row)

        # Override Note
        override_note_row = QHBoxLayout()
        self.override_note = QLineEdit()
        self.override_note.setPlaceholderText("Optional note for audit (e.g., gov fee exempt, only service fee taxable)")
        override_note_row.addWidget(self.override_note)
        override_note_row.addStretch()
        self.form_layout.addRow("Override Note:", override_note_row)

        # Tax Jurisdiction
        tax_jurisdiction_row = QHBoxLayout()
        self.tax_jurisdiction = QComboBox()
        self.tax_jurisdiction.addItems(["AB (GST 5%)"])
        self.tax_jurisdiction.setMaximumWidth(120)
        tax_jurisdiction_row.addWidget(self.tax_jurisdiction)
        tax_jurisdiction_row.addStretch()
        self.form_layout.addRow("Tax Jurisdiction:", tax_jurisdiction_row)

        # GST (auto-calculated)
        gst_auto_row = QHBoxLayout()
        self.gst_auto_label = QLabel("$0.00")
        self.gst_auto_label.setStyleSheet("color: blue; font-weight: bold;")
        gst_auto_row.addWidget(self.gst_auto_label)
        gst_auto_row.addStretch()
        self.form_layout.addRow("GST (auto):", gst_auto_row)

        # Auto-calculate GST when amount changes
        def _update_gst():
            try:
                amt_text = self.new_amount.text().replace("$", "").replace(",", "").strip()
                if amt_text:
                    gross = float(amt_text)
                    gst_amount = gross * 0.05 / (1 + 0.05)  # 5% GST included in gross
                    self.gst_auto_label.setText(f"${gst_amount:.2f}")
                else:
                    self.gst_auto_label.setText("$0.00")
            except Exception:
                self.gst_auto_label.setText("$0.00")
        self.new_amount.textChanged.connect(_update_gst)

        # PST / Sales Tax
        pst_row = QHBoxLayout()
        self.pst_amount = QDoubleSpinBox()
        self.pst_amount.setMaximumWidth(100)
        pst_row.addWidget(self.pst_amount)
        pst_row.addStretch()
        self.form_layout.addRow("PST / Sales Tax:", pst_row)

        # Invoice #
        invoice_row = QHBoxLayout()
        self.invoice_number = QLineEdit()
        self.invoice_number.setPlaceholderText("e.g., INV-2023-001 or leave blank for auto")
        invoice_row.addWidget(self.invoice_number)
        invoice_row.addStretch()
        self.form_layout.addRow("Invoice #:", invoice_row)

        # Description
        self.new_desc = QLineEdit()
        self.new_desc.setPlaceholderText("e.g., Office rent - March 2013")
        self.form_layout.addRow("Description:", self.new_desc)

        # GL Account - compact
        gl_row = QHBoxLayout()
        self.new_gl = QComboBox()
        self.new_gl.setEditable(True)
        self.new_gl.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.new_gl.setPlaceholderText("Type GL code or category...")
        self.new_gl.setMaximumWidth(350)
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT account_code, account_name FROM chart_of_accounts ORDER BY account_code")
            rows = cur.fetchall()
            for code, name in rows:
                if code:
                    self.new_gl.addItem(f"{code} — {name}", code)
            completer = QCompleter([self.new_gl.itemText(i) for i in range(self.new_gl.count())])
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.new_gl.setCompleter(completer)
            cur.close()
        except Exception:
            pass
        gl_row.addWidget(self.new_gl)
        gl_row.addStretch()
        self.form_layout.addRow("GL Account:", gl_row)

        # Fleet Unit (Vehicle) - compact
        vehicle_row = QHBoxLayout()
        self.new_vehicle_combo = QComboBox()
        self.new_vehicle_combo.addItem("", None)
        self.new_vehicle_combo.setMaximumWidth(150)
        self._load_vehicles_into_combo()
        vehicle_row.addWidget(self.new_vehicle_combo)
        vehicle_row.addStretch()
        self.form_layout.addRow("Fleet Unit:", vehicle_row)

        # Driver Reimbursement (Driver selector)
        driver_row = QHBoxLayout()
        self.new_driver_combo = QComboBox()
        self.new_driver_combo.setEditable(True)
        self.new_driver_combo.addItem("", None)
        self.new_driver_combo.setMaximumWidth(200)
        self._load_drivers_into_combo()
        driver_row.addWidget(self.new_driver_combo)
        driver_row.addStretch()
        self.form_layout.addRow("Driver Reimbursement:", driver_row)

        # Charter Number with fuzzy lookup
        charter_row = QHBoxLayout()
        self.new_charter_input = QLineEdit()
        self.new_charter_input.setPlaceholderText("e.g., 015234 (type to search)")
        self.new_charter_input.setMaximumWidth(150)
        charter_row.addWidget(self.new_charter_input)
        charter_row.addStretch()
        self.form_layout.addRow("Charter Number:", charter_row)
        # Attach fuzzy lookup completer for charter field
        self._attach_charter_completer()

        # Fuel (L)
        fuel_row = QHBoxLayout()
        self.fuel_liters = QDoubleSpinBox()
        self.fuel_liters.setRange(0, 5000)
        self.fuel_liters.setDecimals(2)
        self.fuel_liters.setSuffix(" L")
        self.fuel_liters.setMaximumWidth(100)
        fuel_row.addWidget(self.fuel_liters)
        fuel_row.addStretch()
        self.form_layout.addRow("Fuel (L):", fuel_row)
        try:
            self.new_gl.currentIndexChanged.connect(self._toggle_fuel_row)
        except Exception:
            pass

        # Payment Method with Personal/Dvr Personal checkboxes (consolidated)
        payment_row = QHBoxLayout()
        self.payment_method = QComboBox()
        self.payment_method.addItems([
            "cash", "check", "credit_card", "debit_card",
            "bank_transfer", "trade_of_services", "unknown",
        ])
        # Set default to debit_card
        debit_idx = self.payment_method.findText("debit_card")
        if debit_idx >= 0:
            self.payment_method.setCurrentIndex(debit_idx)
        self.payment_method.setMaximumWidth(150)
        payment_row.addWidget(self.payment_method)
        self.personal_chk = QCheckBox("Personal")
        payment_row.addWidget(self.personal_chk)
        self.dvr_personal_chk = QCheckBox("Dvr Personal")
        payment_row.addWidget(self.dvr_personal_chk)
        payment_row.addStretch()
        self.form_layout.addRow("Payment Method:", payment_row)

        # Tax Exclusions header (fields to be added if needed)
        tax_excl_label = QLabel("Tax Exclusions:")
        self.form_layout.addRow(tax_excl_label, QWidget())

        # Banking Transaction ID with tip
        banking_row = QHBoxLayout()
        self.new_banking_id = QLineEdit()
        self.new_banking_id.setPlaceholderText("Leave blank if cash or reim...")
        self.new_banking_id.setMaximumWidth(200)
        banking_row.addWidget(self.new_banking_id)
        self.copy_banking_btn = QPushButton("📋 Copy")
        self.copy_banking_btn.setMaximumWidth(70)
        self.copy_banking_btn.clicked.connect(lambda: QGuiApplication.clipboard().setText((self.new_banking_id.text() or "").strip()))
        banking_row.addWidget(self.copy_banking_btn)
        banking_row.addStretch()
        self.form_layout.addRow("Banking Transaction ID:", banking_row)
        
        # Banking tip
        tip_label = QLabel("💡 TIP: Multiple receipts can share the same Banking Transaction ID (e.g., one $2,772 deposit paying 3 invoices)")
        tip_label.setWordWrap(True)
        tip_label.setStyleSheet("color: #0066cc; font-size: 9pt; padding: 5px;")
        self.form_layout.addRow("", tip_label)
        date_row.addStretch()
        self.form_layout.addRow("Receipt Date:", date_row)

        # Amount with calculator and GST format helper
        amount_row = QHBoxLayout()
        self.new_amount = CurrencyInput()
        self.new_amount.setMaximumWidth(120)
        amount_row.addWidget(self.new_amount)
        calc_btn = QPushButton("🧮")
        calc_btn.setMaximumWidth(40)
        calc_btn.setToolTip("Calculator")
        def _open_calc():
            dlg = CalculatorDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                val = dlg.evaluate()
                if val is None:
                    QMessageBox.warning(self, "Invalid expression", "Please enter a valid arithmetic expression.")
                else:
                    self.new_amount.setText(f"{float(val):.2f}")
        calc_btn.clicked.connect(_open_calc)
        amount_row.addWidget(calc_btn)
        amount_row.addWidget(QLabel("Format: 10 (=$10.00), 10.50 or $0 (+0.50)"))
        amount_row.addStretch()
        self.form_layout.addRow("Amount:", amount_row)

        # Status label
        self.results_label = QLabel("(no results)")
        self.results_label.setStyleSheet("color: #666; font-size: 8pt; margin-top: 3px;")
        vbox.addWidget(self.results_label)

        vbox.addStretch()
        return panel

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _link_to_invoice(self):
        """Link selected receipt to a vendor invoice."""
        rid = getattr(self, "loaded_receipt_id", None)
        if not rid:
            QMessageBox.information(self, "No Selection", "Select a receipt from the table to link to invoice.")
            return
        
        try:
            # Simple dialog to select invoice
            dlg = QDialog(self)
            dlg.setWindowTitle("Link Receipt to Invoice")
            dlg.setMinimumWidth(500)
            layout = QVBoxLayout(dlg)
            
            layout.addWidget(QLabel("Select vendor and invoice to link:"))
            
            # Vendor selector
            vendor_layout = QHBoxLayout()
            vendor_layout.addWidget(QLabel("Vendor:"))
            vendor_combo = QComboBox()
            vendor_combo.setEditable(True)
            
            try:
                cur = self.conn.cursor()
                cur.execute("SELECT DISTINCT vendor_name FROM vendor_invoices WHERE vendor_name IS NOT NULL ORDER BY vendor_name")
                for row in cur.fetchall():
                    vendor_combo.addItem(row[0])
                cur.close()
            except:
                pass
            
            vendor_layout.addWidget(vendor_combo)
            vendor_layout.addStretch()
            layout.addLayout(vendor_layout)
            
            # Invoice selector
            invoice_layout = QHBoxLayout()
            invoice_layout.addWidget(QLabel("Invoice:"))
            invoice_combo = QComboBox()
            invoice_layout.addWidget(invoice_combo)
            invoice_layout.addStretch()
            layout.addLayout(invoice_layout)
            
            # Load invoices when vendor changes
            def _load_invoices():
                invoice_combo.clear()
                vendor = vendor_combo.currentText()
                if vendor:
                    try:
                        cur = self.conn.cursor()
                        cur.execute(
                            "SELECT vendor_invoice_id, invoice_number, invoice_amount FROM vendor_invoices "
                            "WHERE vendor_name = %s ORDER BY invoice_date DESC",
                            (vendor,)
                        )
                        for iid, inum, iamt in cur.fetchall():
                            invoice_combo.addItem(f"{inum} (${iamt:.2f})", iid)
                        cur.close()
                    except:
                        pass
            
            vendor_combo.currentTextChanged.connect(_load_invoices)
            _load_invoices()
            
            # Dialog buttons
            btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)
            layout.addWidget(btns)
            
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            
            invoice_id = invoice_combo.currentData()
            if not invoice_id:
                QMessageBox.warning(self, "No Invoice", "Please select an invoice.")
                return
            
            # Link receipt to invoice
            cur = self.conn.cursor()
            cur.execute(
                "UPDATE receipts SET vendor_invoice_id = %s WHERE receipt_id = %s",
                (invoice_id, rid)
            )
            self.conn.commit()
            cur.close()
            
            QMessageBox.information(self, "Linked", f"Receipt #{rid} linked to invoice #{invoice_combo.currentText()}.")
            self._do_search()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not link receipt:\n{e}")
    
    def _link_to_charter(self):
        """Link selected receipt to charter (alias for existing charter lookup functionality)."""
        if not hasattr(self, "loaded_receipt_id") or not self.loaded_receipt_id:
            QMessageBox.information(self, "No Selection", "Select a receipt from the table to link to charter.")
            return
        self._link_selected_to_charter()

    def _clear_filters(self):
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        self.date_to.setDate(QDate.currentDate())
        self.vendor_filter.clear()
        self.charter_filter.clear()
        self.amount_filter.setValue(0)
        self.date_range_days.setValue(7)
        self.amount_range.setValue(1.0)
        self.include_desc_chk.setChecked(False)
        self.sum_by_banking_chk.setChecked(False)
        self.show_linked_splits_chk.setChecked(False)
        self.results_label.setText("(no results)")
        self.results_table.setRowCount(0)

    def _do_search(self):
        sql = [
            "SELECT receipt_id, receipt_date, vendor_name, gross_amount,",
            "COALESCE(gl_account_name, gl_account_code::text, '') AS gl_name,",
            "banking_transaction_id, COALESCE(reserve_number, '') AS reserve_num,",
            "COALESCE(description, '') AS description, COALESCE(payment_method, '') AS payment_method,",
            "COALESCE(created_from_banking, false) AS created_from_banking",
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
            if getattr(self, "include_desc_chk", None) and self.include_desc_chk.isChecked():
                sql.append("AND (vendor_name ILIKE %s OR description ILIKE %s)")
                params.extend([f"%{vendor}%", f"%{vendor}%"])
            else:
                sql.append("AND vendor_name ILIKE %s")
                params.append(f"%{vendor}%")

        # Charter filter
        charter = (self.charter_filter.text() or "").strip()
        if charter:
            sql.append("AND reserve_number ILIKE %s")
            params.append(f"%{charter}%")

        # Amount filter with range (±)
        amt = self.amount_filter.value()
        amt_range = self.amount_range.value()
        if amt > 0:
            sql.append("AND gross_amount BETWEEN %s AND %s")
            params.extend([float(amt) - float(amt_range), float(amt) + float(amt_range)])

        sql.append("ORDER BY receipt_date DESC, receipt_id DESC LIMIT 200")

        try:
            cur = self.conn.cursor()
            cur.execute("\n".join(sql), params)
            rows = cur.fetchall()
            cur.close()
        except Exception as e:
            QMessageBox.critical(self, "Search Error", f"Could not run search:\n\n{e}")
            return

        self.last_results = rows
        self._populate_table(rows)
        self.results_label.setText(f"Found {len(rows)} results")

    def _populate_table(self, rows: List[tuple]):
        # Table columns: ID | Date | Vendor | Amount | GL/Category | Banking ID | Charter
        self.results_table.setColumnCount(7)
        self.results_table.setHorizontalHeaderLabels(
            ["ID", "Date", "Vendor", "Amount", "GL/Category", "Banking ID", "Charter"]
        )
        header: QHeaderView = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        
        self.results_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            # Expect at least 7 columns; optionally 9 if description/payment_method provided
            rid, rdate, vendor, amount, gl_name, banking_id, charter_num = row[:7]
            self.results_table.setItem(r, 0, QTableWidgetItem(str(rid)))
            self.results_table.setItem(r, 1, QTableWidgetItem(str(rdate)))
            vendor_item = QTableWidgetItem(vendor or "")
            # Store summary data for compact delegate
            desc = row[7] if len(row) > 7 else ""
            paym = row[8] if len(row) > 8 else ""
            created_from_banking = bool(row[9]) if len(row) > 9 else False
            summary = {
                "date": str(rdate),
                "vendor": vendor or "",
                "amount": float(amount) if amount is not None else None,
                "gl": gl_name or "",
                "description": desc or "",
                "banking_id": banking_id,
                "charter": charter_num or "",
                "payment_method": paym or "",
                "created_from_banking": created_from_banking,
            }
            vendor_item.setData(Qt.ItemDataRole.UserRole, summary)
            self.results_table.setItem(r, 2, vendor_item)
            amt_item = QTableWidgetItem(f"${amount:,.2f}" if amount is not None else "")
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.results_table.setItem(r, 3, amt_item)
            self.results_table.setItem(r, 4, QTableWidgetItem(gl_name or ""))
            # Banking ID and Charter
            self.results_table.setItem(r, 5, QTableWidgetItem(str(banking_id) if banking_id is not None else ""))
            self.results_table.setItem(r, 6, QTableWidgetItem(charter_num or ""))

        # Adjust row heights if compact is enabled
        if getattr(self, "compact_toggle", None) and self.compact_toggle.isChecked():
            for r in range(self.results_table.rowCount()):
                # Rough height for 4-line summary
                self.results_table.setRowHeight(r, 4 * self.results_table.fontMetrics().height() + 10)

    def _populate_form_from_selection(self):
        selected = self.results_table.selectedItems()
        if not selected:
            self._clear_form()
            return
        row = selected[0].row()
        try:
            rid_item = self.results_table.item(row, 0)
            date_item = self.results_table.item(row, 1)
            vendor_item = self.results_table.item(row, 2)
            amt_item = self.results_table.item(row, 3)
            gl_item = self.results_table.item(row, 4)
            banking_item = self.results_table.item(row, 5)
            charter_item = self.results_table.item(row, 6)

            self.new_date.setDate(QDate.fromString(date_item.text(), "yyyy-MM-dd"))
            self.new_vendor.setText(vendor_item.text())
            self.new_amount.setText(amt_item.text().replace("$", "").replace(",", ""))
            self.new_desc.setText("")
            self.new_gl.setEditText(gl_item.text())
            self.new_banking_id.setText(banking_item.text())
            # Populate charter input from table
            try:
                self.new_charter_input.setText(charter_item.text())
            except Exception:
                pass
            # Enable limited update when writes are enabled and a row is selected
            self.loaded_receipt_id = int(rid_item.text()) if rid_item and rid_item.text().isdigit() else None
            self.update_btn.setEnabled(self.write_enabled and self.loaded_receipt_id is not None)
        except Exception:
            self._clear_form()

    def _clear_form(self):
        today = QDate.currentDate()
        self.new_date.setDate(today)
        self.new_vendor.clear()
        self.new_amount.clear()
        self.new_desc.clear()
        self.new_gl.setCurrentIndex(-1)
        self.new_banking_id.clear()
        self.new_charter_input.clear()
        self.new_vehicle_combo.setCurrentIndex(0)
        self.new_driver_combo.setCurrentIndex(0)
        self.payment_method.setCurrentIndex(0)
        self.fuel_liters.setValue(0)
        
        # Clear new fields
        self.gst_override_enable.setChecked(False)
        self.gst_override_input.setValue(0)
        self.gst_override_reason.setCurrentIndex(0)
        self.gst_auto_label.setText("$0.00")
        self.override_note.clear()
        self.tax_jurisdiction.setCurrentIndex(0)
        self.pst_amount.setValue(0)
        self.invoice_number.clear()
        self.personal_chk.setChecked(False)
        self.dvr_personal_chk.setChecked(False)
        self.doc_type_receipt.setChecked(True)
        
        self.update_btn.setEnabled(False)
        self.add_btn.setEnabled(self.write_enabled)

    def _add_receipt(self):
        if not self.write_enabled:
            QMessageBox.information(self, "Writes disabled", "Set RECEIPT_WIDGET_WRITE_ENABLED=true to enable adding receipts.")
            return
        try:
            date = self.new_date.date().toPyDate()
            vendor = (self.new_vendor.text() or "").strip()
            source_reference = (self.new_banking_id.text() or "").strip()  # source_reference now stored in banking_id field
            amount = self.new_amount.value()
            desc = (self.new_desc.text() or "").strip()
            gl_text = (self.new_gl.currentText() or "").strip() if isinstance(self.new_gl, QComboBox) else (self.new_gl.text() or "").strip()
            banking_id_text = (self.new_banking_id.text() or "").strip()
            banking_id = int(banking_id_text) if banking_id_text.isdigit() else None
            vehicle_id = self.new_vehicle_combo.currentData() if self.new_vehicle_combo.currentData() else None
            driver_id = self.new_driver_combo.currentData() if self.new_driver_combo.currentData() else None
            reserve_number = (self.new_charter_input.text() or "").strip() or None
            gst_amount = float(self.gst_override_input.value()) if self.gst_override_enable.isChecked() else None
            payment_method = self.payment_method.currentText()

            if not vendor or amount <= 0:
                QMessageBox.warning(self, "Missing data", "Vendor and positive Amount are required.")
                return

            # Duplicate warning: ±$1, ±7 days by vendor
            if self._has_potential_duplicate(vendor, date, amount, banking_id):
                choice = QMessageBox.question(
                    self,
                    "Potential duplicate",
                    "Similar receipts found (±$1, ±7 days). Proceed with insert?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if choice != QMessageBox.StandardButton.Yes:
                    return

            cur = self.conn.cursor()
            cols = ["receipt_date", "vendor_name", "gross_amount", "description", "gl_account_name", "banking_transaction_id", "source_reference"]
            vals = [date, vendor, float(amount), desc or None, gl_text or None, banking_id, source_reference or None]
            if "vehicle_id" in self.receipts_columns:
                cols.append("vehicle_id")
                vals.append(vehicle_id)
            if "employee_id" in self.receipts_columns:
                cols.append("employee_id")
                vals.append(driver_id)
            if "reserve_number" in self.receipts_columns:
                cols.append("reserve_number")
                vals.append(reserve_number)
            if "fuel_liters" in self.receipts_columns:
                cols.append("fuel_liters")
                vals.append(float(self.fuel_liters.value()))
            if "gst_amount" in self.receipts_columns:
                cols.append("gst_amount")
                vals.append(gst_amount)
            if "payment_method" in self.receipts_columns:
                cols.append("payment_method")
                vals.append(payment_method)

            placeholders = ", ".join(["%s"] * len(vals))
            sql = (
                f"INSERT INTO receipts ({', '.join(cols)}) "
                f"SELECT {placeholders} "
                "WHERE NOT EXISTS (SELECT 1 FROM receipts r WHERE r.vendor_name = %s AND r.receipt_date = %s AND r.gross_amount = %s AND COALESCE(r.banking_transaction_id,0) = COALESCE(%s,0)) "
                "RETURNING receipt_id"
            )
            params = vals + [vendor, date, float(amount), banking_id]
            cur.execute(sql, params)
            row = cur.fetchone()
            self.conn.commit()
            cur.close()

            if row and row[0]:
                rid = row[0]
                try:
                    self._audit_log(
                        action="insert",
                        receipt_id=rid,
                        details={
                            "receipt_date": str(date),
                            "vendor_name": vendor,
                            "source_reference": source_reference or None,
                            "gross_amount": float(amount),
                            "description": desc or None,
                            "gl_account_name": gl_text or None,
                            "banking_transaction_id": banking_id,
                            "vehicle_id": vehicle_id,
                            "employee_id": driver_id,
                            "reserve_number": reserve_number,
                            "fuel_liters": float(self.fuel_liters.value()),
                            "gst_amount": gst_amount,
                            "payment_method": payment_method,
                        },
                    )
                except Exception:
                    pass
                QMessageBox.information(self, "Added", f"Receipt #{rid} added.")
                self._clear_form()
                self._do_search()
            else:
                QMessageBox.information(self, "Duplicate skipped", "Matching receipt already exists; no insert performed.")
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            QMessageBox.critical(self, "Add Error", f"Could not add receipt:\n\n{e}")

    def _update_receipt(self):
        if not self.write_enabled:
            QMessageBox.information(self, "Writes disabled", "Set RECEIPT_WIDGET_WRITE_ENABLED=true to enable updates.")
            return
        rid = getattr(self, "loaded_receipt_id", None)
        if not rid:
            QMessageBox.information(self, "No selection", "Select a receipt from the table to update.")
            return
        try:
            # Snapshot BEFORE values for audit (limited to fields we may change)
            before = {}
            try:
                cur_b = self.conn.cursor()
                cur_b.execute(
                    "SELECT description, gl_account_name, banking_transaction_id, vehicle_id, employee_id, reserve_number, fuel_liters, gst_amount, payment_method FROM receipts WHERE receipt_id = %s",
                    (rid,),
                )
                row_b = cur_b.fetchone()
                cur_b.close()
                if row_b:
                    keys = [
                        "description",
                        "gl_account_name",
                        "banking_transaction_id",
                        "vehicle_id",
                        "employee_id",
                        "reserve_number",
                        "fuel_liters",
                        "gst_amount",
                        "payment_method",
                    ]
                    before = {k: row_b[i] for i, k in enumerate(keys)}
            except Exception:
                before = {}
            desc = (self.new_desc.text() or "").strip()
            gl_text = (self.new_gl.currentText() or "").strip() if isinstance(self.new_gl, QComboBox) else (self.new_gl.text() or "").strip()
            banking_id_text = (self.new_banking_id.text() or "").strip()
            banking_id = int(banking_id_text) if banking_id_text.isdigit() else None
            vehicle_id = self.new_vehicle_combo.currentData() if self.new_vehicle_combo.currentData() else None
            driver_id = self.new_driver_combo.currentData() if self.new_driver_combo.currentData() else None
            reserve_number = (self.new_charter_input.text() or "").strip() or None
            fuel_liters = float(self.fuel_liters.value())
            gst_amount = float(self.gst_override_input.value()) if self.gst_override_enable.isChecked() else None
            payment_method = self.payment_method.currentText()

            cur = self.conn.cursor()
            sets = ["description = %s", "gl_account_name = %s", "banking_transaction_id = %s"]
            params = [desc or None, gl_text or None, banking_id]
            if "vehicle_id" in self.receipts_columns:
                sets.append("vehicle_id = %s")
                params.append(vehicle_id)
            if "employee_id" in self.receipts_columns:
                sets.append("employee_id = %s")
                params.append(driver_id)
            if "reserve_number" in self.receipts_columns:
                sets.append("reserve_number = %s")
                params.append(reserve_number)
            if "fuel_liters" in self.receipts_columns:
                sets.append("fuel_liters = %s")
                params.append(fuel_liters)
            if "gst_amount" in self.receipts_columns:
                sets.append("gst_amount = %s")
                params.append(gst_amount)
            if "payment_method" in self.receipts_columns:
                sets.append("payment_method = %s")
                params.append(payment_method)

            sql = f"UPDATE receipts SET {', '.join(sets)} WHERE receipt_id = %s"
            params.append(rid)
            cur.execute(sql, params)
            self.conn.commit()
            cur.close()
            try:
                after = {
                    "description": desc or None,
                    "gl_account_name": gl_text or None,
                    "banking_transaction_id": banking_id,
                    "vehicle_id": vehicle_id,
                    "employee_id": driver_id,
                    "reserve_number": reserve_number,
                    "fuel_liters": fuel_liters,
                    "gst_amount": gst_amount,
                    "payment_method": payment_method,
                }
                self._audit_log(action="update", receipt_id=rid, details={"before": before, "after": after})
            except Exception:
                pass
            QMessageBox.information(self, "Updated", f"Receipt #{rid} updated.")
            self._do_search()
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            QMessageBox.critical(self, "Update Error", f"Could not update receipt #{rid}:\n\n{e}")

    def _has_potential_duplicate(self, vendor: str, date, amount: Decimal, banking_id: int | None) -> bool:
        try:
            cur = self.conn.cursor()
            sql = (
                "SELECT 1 FROM receipts r "
                "WHERE r.vendor_name ILIKE %s "
                "AND r.receipt_date BETWEEN %s - INTERVAL '7 days' AND %s + INTERVAL '7 days' "
                "AND r.gross_amount BETWEEN %s AND %s "
            )
            params = [f"%{vendor}%", date, date, float(amount) - 1.0, float(amount) + 1.0]
            if banking_id is not None:
                sql += "AND r.banking_transaction_id = %s"
                params.append(banking_id)
            cur.execute(sql, params)
            exists = cur.fetchone() is not None
            cur.close()
            return exists
        except Exception:
            return False

    def _check_duplicates(self):
        """Check for potential duplicate receipts based on current form values."""
        try:
            vendor = (self.new_vendor.text() or "").strip()
            amount = self.new_amount.value()
            date = self.new_date.date().toPyDate()
            
            if not vendor or amount <= 0:
                QMessageBox.information(self, "Missing data", "Enter Vendor and Amount to check for duplicates.")
                return
            
            cur = self.conn.cursor()
            cur.execute(
                """SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
                          COALESCE(description, '') as description,
                          COALESCE(gl_account_name, '') as gl_account
                   FROM receipts
                   WHERE vendor_name ILIKE %s
                   AND receipt_date BETWEEN %s - INTERVAL '7 days' AND %s + INTERVAL '7 days'
                   AND gross_amount BETWEEN %s AND %s
                   ORDER BY receipt_date DESC
                   LIMIT 10""",
                [f"%{vendor}%", date, date, float(amount) - 1.0, float(amount) + 1.0]
            )
            rows = cur.fetchall()
            cur.close()
            
            if not rows:
                QMessageBox.information(self, "No Duplicates", f"No potential duplicates found for {vendor} ~${amount:.2f} ±7 days.")
            else:
                msg = f"Found {len(rows)} potential duplicate(s):\n\n"
                for rid, rdate, rvend, ramt, rdesc, rgl in rows:
                    msg += f"• Receipt #{rid}: {rdate} | {rvend} | ${ramt:.2f} | {rgl}\n  {rdesc[:50]}\n\n"
                QMessageBox.warning(self, "Potential Duplicates Found", msg)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not check duplicates:\n{e}")

    def _prefill_from_search(self):
        """Prefill form fields from selected search result."""
        try:
            row = self.results_table.currentRow()
            if row < 0:
                QMessageBox.information(self, "No Selection", "Select a receipt from the search results to prefill.")
                return
            
            # Get receipt ID from first column
            rid_item = self.results_table.item(row, 0)
            if not rid_item:
                return
            
            rid = int(rid_item.text())
            
            # Fetch full receipt details
            cur = self.conn.cursor()
            cur.execute(
                """SELECT receipt_date, vendor_name, gross_amount, description,
                          gl_account_name, banking_transaction_id, vehicle_id,
                          employee_id, reserve_number, fuel_liters, gst_amount, payment_method
                   FROM receipts WHERE receipt_id = %s""",
                (rid,)
            )
            row_data = cur.fetchone()
            cur.close()
            
            if not row_data:
                QMessageBox.warning(self, "Not Found", f"Receipt #{rid} not found.")
                return
            
            # Populate form
            (rdate, vendor, amount, desc, gl, bank_id, veh_id, emp_id, 
             reserve, fuel, gst, pmeth) = row_data
            
            if rdate:
                self.new_date.setDate(QDate(rdate.year, rdate.month, rdate.day))
            if vendor:
                self.new_vendor.setText(vendor)
            if amount:
                self.new_amount.setText(f"{float(amount):.2f}")
            if desc:
                self.new_desc.setText(desc)
            if gl:
                # Try to find matching GL account in combo
                idx = self.new_gl.findText(gl, Qt.MatchFlag.MatchContains)
                if idx >= 0:
                    self.new_gl.setCurrentIndex(idx)
            if bank_id:
                self.new_banking_id.setText(str(bank_id))
            if veh_id:
                idx = self.new_vehicle_combo.findData(veh_id)
                if idx >= 0:
                    self.new_vehicle_combo.setCurrentIndex(idx)
            if emp_id:
                idx = self.new_driver_combo.findData(emp_id)
                if idx >= 0:
                    self.new_driver_combo.setCurrentIndex(idx)
            if reserve:
                self.new_charter_input.setText(reserve)
            if fuel:
                self.fuel_liters.setValue(float(fuel))
            if gst:
                self.gst_override_input.setValue(float(gst))
                self.gst_override_enable.setChecked(True)
            if pmeth:
                idx = self.payment_method.findText(pmeth)
                if idx >= 0:
                    self.payment_method.setCurrentIndex(idx)
            
            QMessageBox.information(self, "Prefilled", f"Form prefilled from Receipt #{rid}. Review and modify as needed.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not prefill from search:\n{e}")

    # ------------------------------------------------------------------
    # Split/Allocate helper
    # ------------------------------------------------------------------
    def _open_split_dialog(self):
        if not self.write_enabled:
            QMessageBox.information(self, "Writes disabled", "Set RECEIPT_WIDGET_WRITE_ENABLED=true to enable splitting.")
            return
        base_amount = self.new_amount.value()
        if base_amount <= 0:
            QMessageBox.information(self, "Missing amount", "Enter a positive Amount before splitting.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Split/Allocate Receipt Amount")
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("Enter one allocation per line: amount, GL/category, optional description"))
        edit = QPlainTextEdit()
        edit.setPlaceholderText("e.g.\n300.00, Fuel, October gas\n350.00, Repairs, Oil change")
        v.addWidget(edit)
        v.addWidget(QLabel("Total must equal current Amount."))
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        v.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        if dlg.exec() != QDialog.Accepted:
            return
        text = (edit.toPlainText() or "").strip()
        if not text:
            return
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        allocations = []
        total = Decimal("0")
        for line in lines:
            parts = [p.strip() for p in line.split(",")]
            if not parts:
                continue
            try:
                amt = Decimal(parts[0])
            except Exception:
                QMessageBox.warning(self, "Parse error", f"Could not parse amount in line: {line}")
                return
            gl_text = parts[1] if len(parts) > 1 else ""
            desc = parts[2] if len(parts) > 2 else ""
            allocations.append((amt, gl_text, desc))
            total += amt
        if abs(float(total) - float(base_amount)) > 0.01:
            QMessageBox.warning(self, "Total mismatch", f"Allocations total ${float(total):,.2f} does not equal current Amount ${float(base_amount):,.2f}.")
            return
        # Perform inserts for each allocation
        inserted = 0
        for amt, gl_text, desc in allocations:
            try:
                self._insert_allocation_line(amount=amt, gl_text=gl_text, extra_desc=desc)
                inserted += 1
            except Exception as e:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                QMessageBox.critical(self, "Split Error", f"Failed to insert allocation line (${float(amt):,.2f}, {gl_text}):\n\n{e}")
                return
        QMessageBox.information(self, "Split complete", f"Inserted {inserted} allocation lines.")
        self._clear_form()
        self._do_search()

    def _insert_allocation_line(self, amount: Decimal, gl_text: str, extra_desc: str):
        date = self.new_date.date().toPyDate()
        vendor = (self.new_vendor.text() or "").strip()
        source_reference = (self.new_banking_id.text() or "").strip()
        base_desc = (self.new_desc.text() or "").strip()
        full_desc = (base_desc + (f"; {extra_desc}" if extra_desc else "")).strip() or None
        banking_id_text = (self.new_banking_id.text() or "").strip()
        banking_id = int(banking_id_text) if banking_id_text.isdigit() else None
        vehicle_id = self.new_vehicle_combo.currentData() if self.new_vehicle_combo.currentData() else None
        driver_id = self.new_driver_combo.currentData() if self.new_driver_combo.currentData() else None
        reserve_number = (self.new_charter_input.text() or "").strip() or None
        gst_amount = float(self.gst_override_input.value()) if self.gst_override_enable.isChecked() else None
        payment_method = self.payment_method.currentText()

        if not vendor or amount <= 0:
            raise ValueError("Vendor and positive Amount are required for allocation line.")

        # Duplicate warning guard; silently skip if match exists
        if self._has_potential_duplicate(vendor, date, amount, banking_id):
            return
        cur = self.conn.cursor()
        cols = ["receipt_date", "vendor_name", "gross_amount", "description", "gl_account_name", "banking_transaction_id", "source_reference"]
        vals = [date, vendor, float(amount), full_desc, (gl_text or None), banking_id, source_reference or None]
        if "vehicle_id" in self.receipts_columns:
            cols.append("vehicle_id")
            vals.append(vehicle_id)
        if "employee_id" in self.receipts_columns:
            cols.append("employee_id")
            vals.append(driver_id)
        if "reserve_number" in self.receipts_columns:
            cols.append("reserve_number")
            vals.append(reserve_number)
        if "fuel_liters" in self.receipts_columns:
            cols.append("fuel_liters")
            vals.append(float(self.fuel_liters.value()))
        if "gst_amount" in self.receipts_columns:
            cols.append("gst_amount")
            vals.append(gst_amount)
        if "payment_method" in self.receipts_columns:
            cols.append("payment_method")
            vals.append(payment_method)

        placeholders = ", ".join(["%s"] * len(vals))
        sql = (
            f"INSERT INTO receipts ({', '.join(cols)}) "
            f"SELECT {placeholders} "
            "WHERE NOT EXISTS (SELECT 1 FROM receipts r WHERE r.vendor_name = %s AND r.receipt_date = %s AND r.gross_amount = %s AND COALESCE(r.banking_transaction_id,0) = COALESCE(%s,0)) "
            "RETURNING receipt_id"
        )
        params = vals + [vendor, date, float(amount), banking_id]
        cur.execute(sql, params)
        row = cur.fetchone()
        self.conn.commit()
        cur.close()
        if row and row[0]:
            rid = row[0]
            try:
                self._audit_log(
                    action="insert",
                    receipt_id=rid,
                    details={
                        "receipt_date": str(date),
                        "vendor_name": vendor,
                        "source_reference": source_reference or None,
                        "gross_amount": float(amount),
                        "description": full_desc,
                        "gl_account_name": gl_text or None,
                        "banking_transaction_id": banking_id,
                        "vehicle_id": vehicle_id,
                        "employee_id": driver_id,
                        "reserve_number": reserve_number,
                        "fuel_liters": float(self.fuel_liters.value()),
                        "gst_amount": gst_amount,
                        "payment_method": payment_method,
                        "allocation": True,
                    },
                )
            except Exception:
                pass

    # Helpers
    def _load_receipts_columns(self) -> set:
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'receipts'")
            cols = {row[0] for row in cur.fetchall()}
            cur.close()
            return cols
        except Exception:
            return set()

    def _ensure_audit_table(self):
        if self._audit_table_checked:
            return
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = 'receipt_audit_log'
                """
            )
            exists = cur.fetchone() is not None
            cur.close()
            self._audit_table_exists = exists
            self._audit_table_checked = True
            # Optional creation gated by env var
            if not exists and str(os.environ.get("RECEIPT_AUDIT_CREATE", "false")).lower() in ("1", "true", "yes"):
                try:
                    curc = self.conn.cursor()
                    curc.execute(
                        """
                        CREATE TABLE IF NOT EXISTS receipt_audit_log (
                            audit_id BIGSERIAL PRIMARY KEY,
                            receipt_id INTEGER,
                            action TEXT NOT NULL,
                            event_time TIMESTAMPTZ DEFAULT now(),
                            actor TEXT DEFAULT 'DesktopApp',
                            details JSONB
                        )
                        """
                    )
                    self.conn.commit()
                    curc.close()
                    self._audit_table_exists = True
                except Exception:
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass
        except Exception:
            self._audit_table_checked = True
            self._audit_table_exists = False

    def _audit_log(self, action: str, receipt_id: int | None, details: dict):
        try:
            self._ensure_audit_table()
            if not self._audit_table_exists:
                return
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO receipt_audit_log (receipt_id, action, actor, details) VALUES (%s, %s, %s, %s)",
                (receipt_id, action, "DesktopApp", json.dumps(details)),
            )
            self.conn.commit()
            cur.close()
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass

    def _load_vehicles_into_combo(self):
        try:
            cur = self.conn.cursor()
            # Natural numeric sort: L1, L2, ..., L10, ..., L25 (not string sort)
            cur.execute("""
                SELECT vehicle_id, COALESCE(vehicle_number, 'L'||vehicle_id::text) 
                FROM vehicles 
                ORDER BY 
                    CASE WHEN vehicle_number ~ '^L[0-9]+$' 
                         THEN (regexp_matches(vehicle_number, '[0-9]+'))[1]::integer 
                         ELSE 999999 
                    END,
                    vehicle_id
            """)
            for vid, label in cur.fetchall():
                self.new_vehicle_combo.addItem(label, vid)
            cur.close()
        except Exception:
            pass

    def _load_drivers_into_combo(self):
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT employee_id, CONCAT_WS(' ', first_name, last_name) FROM employees ORDER BY first_name, last_name")
            names = []
            for emp_id, name in cur.fetchall():
                self.new_driver_combo.addItem(name, emp_id)
                names.append(name)
            comp = QCompleter(names)
            comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            comp.setFilterMode(Qt.MatchFlag.MatchContains)
            self.new_driver_combo.setCompleter(comp)
            cur.close()
        except Exception:
            pass

    def _attach_vendor_completer(self):
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT DISTINCT vendor_name FROM receipts WHERE vendor_name IS NOT NULL ORDER BY vendor_name LIMIT 5000")
            vendors = [row[0] for row in cur.fetchall()]
            cur.close()
            comp = QCompleter(vendors)
            comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            comp.setFilterMode(Qt.MatchFlag.MatchContains)
            self.new_vendor.setCompleter(comp)
        except Exception:
            pass

    def _attach_charter_completer(self):
        """Add fuzzy/contains charter number lookup completer."""
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT DISTINCT CAST(reserve_number AS TEXT) FROM charters WHERE reserve_number IS NOT NULL ORDER BY reserve_number LIMIT 5000")
            charters = [row[0] for row in cur.fetchall()]
            cur.close()
            comp = QCompleter(charters)
            comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            comp.setFilterMode(Qt.MatchFlag.MatchContains)
            self.new_charter_input.setCompleter(comp)
        except Exception:
            pass

    def _toggle_fuel_row(self):
        try:
            text = (self.new_gl.currentText() or "").lower()
        except Exception:
            text = (self.new_gl.text() or "").lower()
        self._set_fuel_row_visible("fuel" in text or "gas" in text)

    def _set_fuel_row_visible(self, visible: bool):
        try:
            self.fuel_liters.parent().setVisible(visible)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------
    def _load_recent(self):
        try:
            # Ensure transaction is clean before querying
            try:
                self.conn.rollback()
            except Exception:
                pass
            
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT receipt_id, receipt_date, vendor_name, gross_amount,
                       COALESCE(gl_account_code, '') AS gl_code,
                       banking_transaction_id,
                       COALESCE(reserve_number, '') AS reserve_num,
                       COALESCE(description, '') AS description,
                       COALESCE(payment_method, '') AS payment_method,
                       COALESCE(created_from_banking, false) AS created_from_banking
                FROM receipts
                ORDER BY receipt_date DESC, receipt_id DESC
                LIMIT 50
                """
            )
            rows = cur.fetchall()
            cur.close()
            self.conn.commit()
            self.last_results = rows
            self._populate_table(rows)
            self.results_label.setText(f"Recent 50 receipts loaded ({len(rows)})")
        except Exception as e:
            # Silently fail during init - user can manually trigger search
            try:
                self.conn.rollback()
            except Exception:
                pass
            import sys
            print(f"[ReceiptWidget] Load recent failed: {e}", file=sys.stderr)
            self.results_label.setText("(No recent receipts loaded - use search)")

    def _toggle_compact_view(self, on: bool):
        # Show 4-line summary in Vendor column when enabled
        if on:
            # Rename header for vendor column to Summary
            headers = ["ID", "Date", "Summary", "Amount", "GL/Category", "Banking ID", "Charter"]
            self.results_table.setHorizontalHeaderLabels(headers)
            # Hide non-summary columns except Vendor(2)
            for col in (0, 1, 3, 4, 5, 6):
                self.results_table.setColumnHidden(col, True)
            # Attach delegate
            self.results_table.setItemDelegateForColumn(2, ReceiptCompactDelegate(self.results_table))
            # Increase row heights for readability
            for r in range(self.results_table.rowCount()):
                self.results_table.setRowHeight(r, 4 * self.results_table.fontMetrics().height() + 10)
        else:
            # Restore headers
            headers = ["ID", "Date", "Vendor", "Amount", "GL/Category", "Banking ID", "Charter"]
            self.results_table.setHorizontalHeaderLabels(headers)
            # Unhide columns
            for col in (0, 1, 3, 4, 5, 6):
                self.results_table.setColumnHidden(col, False)
            # Remove delegate
            self.results_table.setItemDelegateForColumn(2, QStyledItemDelegate(self.results_table))
            # Reset row heights to default
            for r in range(self.results_table.rowCount()):
                self.results_table.setRowHeight(r, self.results_table.fontMetrics().height() + 8)

    def _link_selected_to_charter(self):
        """Link the selected receipt row to a charter by reserve_number."""
        selected = self.results_table.selectedItems()
        if not selected:
            QMessageBox.information(self, "No selection", "Select a receipt row to link to a charter.")
            return
        rid = int(self.results_table.item(selected[0].row(), 0).text())
        reserve_num = (self.charter_lookup_input.text() or "").strip()
        if not reserve_num:
            QMessageBox.information(self, "Missing reserve #", "Enter a reserve number to link.")
            return
        try:
            cur = self.conn.cursor()
            cur.execute("UPDATE receipts SET reserve_number = %s WHERE receipt_id = %s", (reserve_num, rid))
            self.conn.commit()
            cur.close()
            QMessageBox.information(self, "Linked", f"Receipt {rid} linked to Charter {reserve_num}.")
            self.charter_lookup_input.clear()
            self._do_search()
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            QMessageBox.critical(self, "Link Error", f"Could not link receipt:\n\n{e}")

    # ------------------------------------------------------------------
    # Banking match suggestions
    # ------------------------------------------------------------------
    def _suggest_banking_matches(self):
        """Suggest unmatched banking transactions based on amount/date."""
        amt = self.new_amount.value()
        date = self.new_date.date().toPyDate()
        if amt <= 0 or not date:
            QMessageBox.information(self, "Missing data", "Enter Amount and Date to find banking matches.")
            return
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT id, transaction_date, description, 
                       COALESCE(debit_amount, 0) - COALESCE(credit_amount, 0) AS net_amount
                FROM banking_transactions
                WHERE ABS(COALESCE(debit_amount, 0) - COALESCE(credit_amount, 0) - %s) < 0.01
                  AND transaction_date BETWEEN %s - INTERVAL '2 days' AND %s + INTERVAL '2 days'
                  AND (reconciliation_status IS NULL OR reconciliation_status IN ('unreconciled','ignored'))
                ORDER BY ABS(transaction_date - %s), id DESC
                LIMIT 20
                """,
                (amt, date, date, date),
            )
            rows = cur.fetchall()
            cur.close()
            if not rows:
                QMessageBox.information(self, "No matches", f"No banking transactions found matching ${amt:,.2f} near {date}.")
                return
            dlg = QDialog(self)
            dlg.setWindowTitle("Banking Match Suggestions")
            v = QVBoxLayout(dlg)
            v.addWidget(QLabel(f"Found {len(rows)} candidate(s) for ${amt:,.2f} on {date}:"))
            lst = QListWidget()
            for tid, txn_date, desc, net_amt in rows:
                item_text = f"ID {tid} | {txn_date} | ${net_amt:,.2f} | {desc[:40]}"
                item = QListWidgetItem(item_text)
                item.setData(1000, tid)  # Store ID in custom role
                lst.addItem(item)
            v.addWidget(lst)
            btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            v.addWidget(btns)
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)
            if dlg.exec() != QDialog.Accepted or not lst.currentItem():
                return
            selected = lst.currentItem().data(1000)
            self.new_banking_id.setText(str(selected))
            QMessageBox.information(self, "Selected", f"Banking Transaction {selected} selected.")
        except Exception as e:
            QMessageBox.critical(self, "Suggestion Error", f"Could not find banking matches:\n\n{e}")

    # ------------------------------------------------------------------
    # Bulk import CSV
    # ------------------------------------------------------------------
    def _open_bulk_import(self):
        """Open bulk receipt import dialog from CSV."""
        if not self.write_enabled:
            QMessageBox.information(self, "Writes disabled", "Set RECEIPT_WIDGET_WRITE_ENABLED=true to enable bulk import.")
            return
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Receipt CSV", "", "CSV Files (*.csv)")
        if not file_path:
            return
        try:
            import csv
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            if not rows:
                QMessageBox.information(self, "Empty file", "CSV contains no data rows.")
                return
            # Expected columns: date, vendor, amount, description, gl_account, [optional: vehicle_id, employee_id, reserve_number]
            inserted = 0
            skipped = 0
            for row_idx, row in enumerate(rows):
                try:
                    date_str = (row.get("date") or "").strip()
                    vendor = (row.get("vendor") or "").strip()
                    amount_str = (row.get("amount") or "").strip()
                    desc = (row.get("description") or "").strip()
                    gl_text = (row.get("gl_account") or "").strip()
                    vehicle_id = None
                    driver_id = None
                    reserve_number = None
                    if "vehicle_id" in row and row["vehicle_id"].strip().isdigit():
                        vehicle_id = int(row["vehicle_id"])
                    if "employee_id" in row and row["employee_id"].strip().isdigit():
                        driver_id = int(row["employee_id"])
                    if "reserve_number" in row:
                        reserve_number = (row["reserve_number"] or "").strip() or None
                    if not vendor or not amount_str:
                        skipped += 1
                        continue
                    from datetime import datetime as dt
                    try:
                        date = dt.strptime(date_str, "%Y-%m-%d").date()
                    except Exception:
                        date = dt.now().date()
                    amount = Decimal(amount_str.replace(",", ""))
                    if amount <= 0:
                        skipped += 1
                        continue
                    if self._has_potential_duplicate(vendor, date, amount, None):
                        skipped += 1
                        continue
                    cur = self.conn.cursor()
                    cols = ["receipt_date", "vendor_name", "gross_amount", "description", "gl_account_name"]
                    vals = [date, vendor, float(amount), desc or None, gl_text or None]
                    if "vehicle_id" in self.receipts_columns and vehicle_id:
                        cols.append("vehicle_id")
                        vals.append(vehicle_id)
                    if "employee_id" in self.receipts_columns and driver_id:
                        cols.append("employee_id")
                        vals.append(driver_id)
                    if "reserve_number" in self.receipts_columns and reserve_number:
                        cols.append("reserve_number")
                        vals.append(reserve_number)
                    placeholders = ", ".join(["%s"] * len(vals))
                    sql = (
                        f"INSERT INTO receipts ({', '.join(cols)}) "
                        f"SELECT {placeholders} "
                        "WHERE NOT EXISTS (SELECT 1 FROM receipts r WHERE r.vendor_name = %s AND r.receipt_date = %s AND r.gross_amount = %s) "
                        "RETURNING receipt_id"
                    )
                    params = vals + [vendor, date, float(amount)]
                    cur.execute(sql, params)
                    row_result = cur.fetchone()
                    self.conn.commit()
                    cur.close()
                    if row_result and row_result[0]:
                        rid = row_result[0]
                        try:
                            self._audit_log(
                                action="bulk_import",
                                receipt_id=rid,
                                details={
                                    "csv_row": row_idx + 2,  # +2 for header + 1-based
                                    "receipt_date": str(date),
                                    "vendor_name": vendor,
                                    "gross_amount": float(amount),
                                    "description": desc or None,
                                    "gl_account_name": gl_text or None,
                                },
                            )
                        except Exception:
                            pass
                        inserted += 1
                except Exception:
                    skipped += 1
            QMessageBox.information(self, "Bulk Import Complete", f"Inserted {inserted}, skipped {skipped}.")
            self._do_search()
        except Exception as e:
            QMessageBox.critical(self, "Bulk Import Error", f"Could not import CSV:\n\n{e}")

    # ------------------------------------------------------------------
    # Quick reconciliation view
    # ------------------------------------------------------------------
    def _open_reconciliation_view(self):
        """Show unmatched receipts and banking transactions for quick matching."""
        if not self.write_enabled:
            QMessageBox.information(self, "Writes disabled", "Set RECEIPT_WIDGET_WRITE_ENABLED=true to enable reconciliation.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Quick Reconciliation")
        dlg.resize(1000, 600)
        v = QVBoxLayout(dlg)
        try:
            cur = self.conn.cursor()
            # Unmatched receipts
            cur.execute(
                """
                SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
                FROM receipts
                WHERE banking_transaction_id IS NULL
                ORDER BY receipt_date DESC
                LIMIT 100
                """
            )
            unmatched_receipts = cur.fetchall()
            # Unmatched banking transactions
            cur.execute(
                """
                SELECT id, transaction_date, description, COALESCE(debit_amount, 0) - COALESCE(credit_amount, 0) AS net_amount
                FROM banking_transactions
                WHERE id NOT IN (SELECT DISTINCT banking_transaction_id FROM receipts WHERE banking_transaction_id IS NOT NULL)
                  AND (reconciliation_status IS NULL OR reconciliation_status IN ('unreconciled','ignored'))
                ORDER BY transaction_date DESC
                LIMIT 100
                """
            )
            unmatched_banking = cur.fetchall()
            cur.close()
            v.addWidget(QLabel(f"🧾 Unmatched Receipts ({len(unmatched_receipts)}) | 🏦 Unmatched Banking ({len(unmatched_banking)})"))
            # Side-by-side tables
            h = QHBoxLayout()
            # Receipts table
            receipts_table = QTableWidget(len(unmatched_receipts), 5)
            receipts_table.setHorizontalHeaderLabels(["ID", "Date", "Vendor", "Amount", "Description"])
            for r, (rid, rdate, vendor, amt, desc) in enumerate(unmatched_receipts):
                receipts_table.setItem(r, 0, QTableWidgetItem(str(rid)))
                receipts_table.setItem(r, 1, QTableWidgetItem(str(rdate)))
                receipts_table.setItem(r, 2, QTableWidgetItem(vendor or ""))
                receipts_table.setItem(r, 3, QTableWidgetItem(f"${amt:,.2f}" if amt else ""))
                receipts_table.setItem(r, 4, QTableWidgetItem(desc or ""))
            h.addWidget(receipts_table)
            # Banking table
            banking_table = QTableWidget(len(unmatched_banking), 4)
            banking_table.setHorizontalHeaderLabels(["ID", "Date", "Description", "Amount"])
            for r, (bid, bdate, bdesc, bamt) in enumerate(unmatched_banking):
                banking_table.setItem(r, 0, QTableWidgetItem(str(bid)))
                banking_table.setItem(r, 1, QTableWidgetItem(str(bdate)))
                banking_table.setItem(r, 2, QTableWidgetItem(bdesc or ""))
                banking_table.setItem(r, 3, QTableWidgetItem(f"${bamt:,.2f}" if bamt else ""))
            h.addWidget(banking_table)
            v.addLayout(h)
            # Match button
            match_btn = QPushButton("↔️  Match Selected")
            def do_match():
                r_row = receipts_table.currentRow()
                b_row = banking_table.currentRow()
                if r_row < 0 or b_row < 0:
                    QMessageBox.information(dlg, "Select both", "Select one receipt and one banking transaction.")
                    return
                rid = int(receipts_table.item(r_row, 0).text())
                bid = int(banking_table.item(b_row, 0).text())
                try:
                    cur2 = self.conn.cursor()
                    cur2.execute("UPDATE receipts SET banking_transaction_id = %s WHERE receipt_id = %s", (bid, rid))
                    self.conn.commit()
                    cur2.close()
                    QMessageBox.information(dlg, "Matched", f"Receipt {rid} linked to Banking {bid}.")
                    dlg.close()
                except Exception as e:
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass
                    QMessageBox.critical(dlg, "Match Error", f"Could not link receipt:\n\n{e}")
            match_btn.clicked.connect(do_match)
            v.addWidget(match_btn)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Reconciliation Error", f"Could not load reconciliation data:\n\n{e}")


__all__ = ["ReceiptSearchMatchWidget"]
