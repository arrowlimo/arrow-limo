"""
Receipt Search & Match Widget (restored minimal version)
Provides a stable search + view interface for receipts and a placeholder for
add/update.
Original file was corrupted; this version prioritizes loading without crashes.
"""

import json
import logging
import os
import re
import traceback
from decimal import Decimal

import psycopg2

logger = logging.getLogger(__name__)
from common_widgets import StandardDateEdit
from PyQt6.QtCore import QDate, QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QDoubleValidator,
    QFont,
    QGuiApplication,
    QPainter,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from split_receipt_manager_dialog import SplitReceiptManagerDialog
from vendor_lookup_widget import VendorLookupWidget

GL_DISPLAY_NAME_OVERRIDES = {
    "2550": "Director Vehicle Reimbursement - David Richard",
    "5116": "Client Amenities - Food, Coffee, Supplies",
    "5300": "Administrative Expense",
}

DAVID_REIMBURSEMENT_GL_CODE = "2550"


class NumericSortItem(QTableWidgetItem):
    """QTableWidgetItem that sorts by a stored numeric value rather than
    display text.
    """

    def __init__(self, display_text: str, sort_value: float) -> None:
        super().__init__(display_text)
        self._sort_value = sort_value

    def __lt__(self, other: "QTableWidgetItem") -> bool:
        if isinstance(other, NumericSortItem):
            return self._sort_value < other._sort_value
        try:
            return self._sort_value < float(
                other.text().replace("$", "").replace(",", "")
            )
        except (ValueError, AttributeError):
            return super().__lt__(other)


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

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_date = QDate.currentDate()
        self.setText(self._current_date.toString("MM/dd/yyyy"))
        self.setPlaceholderText("MM/DD/YYYY or Jan 01 2012 (t=yesterday)")
        # Tooltip with examples
        self.setToolTip(
            "Examples: 01/17/2026, 1/7/2026, 2026-01-17, 20260117,\n"
            "Jan 17 2026, 17 Jan 2026, January 17 2026, t (today), y "
            "(yesterday)"
        )
        self.textChanged.connect(self._on_text_changed)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def _on_text_changed(self, text: str) -> None:
        parsed = self._parse_date(text.strip())
        if parsed is None:
            # Invalid → light red bg
            self.setStyleSheet(
                "background-color: #ffecec; border: 1px solid #cc0000;"
            )
        else:
            self._current_date = parsed
            # Valid → light green bg
            self.setStyleSheet(
                "background-color: #eaffea; border: 1px solid #00aa00;"
            )

    def _parse_date(self, s: str) -> QDate | None:
        if not s:
            return None
        # Shortcuts
        if s.lower() == "t":
            return QDate.currentDate()
        if s.lower() == "y":
            return QDate.currentDate().addDays(-1)

        # Try multiple formats
        from datetime import datetime

        fmts = [
            "%m/%d/%Y",
            "%m/%d/%y",
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y%m%d",
            "%d %b %Y",
            "%b %d %Y",
            "%d %B %Y",
            "%B %d %Y",
        ]
        for fmt in fmts:
            try:
                dt = datetime.strptime(s, fmt)
                return QDate(dt.year, dt.month, dt.day)
            except ValueError:
                pass
        # Fallback: try letting QDate parse ISO
        qd = QDate.fromString(s, "yyyy-MM-dd")
        if qd.isValid():
            return qd
        return None

    # API compatibility
    def date(self) -> QDate:
        return self._current_date

    def setDate(self, qdate: QDate) -> None:
        if not isinstance(qdate, QDate):
            return
        self._current_date = qdate
        self.setText(qdate.toString("MM/dd/yyyy"))


class CalculatorDialog(QDialog):
    """Simple calculator dialog for quick amount math."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calculator")
        layout = QVBoxLayout(self)
        self.input = QLineEdit(self)
        self.input.setPlaceholderText("Enter expression, e.g., 120+35.5-10")
        layout.addWidget(self.input)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
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
    """Simple currency field with 2-decimal validation. Allows negative values
    for returns/credits.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        validator = QDoubleValidator(
            -1_000_000_000.0, 1_000_000_000.0, 2, self
        )
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

    def paint(self, painter: QPainter, option, index) -> None:
        # Only customize the Vendor/Summary column
        if index.column() != 2:
            super().paint(painter, option, index)
            return
        try:
            data = index.data(Qt.ItemDataRole.UserRole) or {}
            date = data.get("date") or ""
            vendor = data.get("vendor") or ""
            amount = data.get("amount")
            amount_str = (
                f"${amount:,.2f}"
                if isinstance(amount, (int, float))
                else (str(amount) if amount else "")
            )
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
            line3_parts = [
                p for p in (matched_str, source_str, charter_str) if p
            ]
            line3 = " • ".join(line3_parts) if line3_parts else ""
            line4 = payment_str
            lines = [
                line_item
                for line_item in (line1, line2, line3, line4)
                if line_item
            ]
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
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                text,
            )
            painter.restore()
        except Exception:
            super().paint(painter, option, index)

    def sizeHint(self, option, index) -> QSize:
        # Provide extra height for 4 lines
        try:
            fm = option.fontMetrics
            line_height = fm.height()
            total_height = (line_height * 4) + 8  # padding
            return QSize(option.rect.width(), total_height)
        except Exception:
            return super().sizeHint(option, index)


class _SearchWorker(QThread):
    """Background thread that runs a receipt search query without blocking the
    UI.
    """

    results_ready = pyqtSignal(list, bool)  # (rows, truncated)
    error_occurred = pyqtSignal(str)

    def __init__(
        self, conn_kwargs: dict, sql: str, params: list, parent=None
    ) -> None:
        super().__init__(parent)
        self._conn_kwargs = conn_kwargs
        self._sql = sql
        self._params = params
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        conn = None
        try:
            conn = psycopg2.connect(**self._conn_kwargs)
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(self._sql, self._params)
            rows = cur.fetchall()
            cur.close()
            if not self._cancelled:
                self.results_ready.emit(rows, len(rows) == 2000)
        except Exception as e:
            if not self._cancelled:
                self.error_occurred.emit(str(e))
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as _e:
                    logger.debug('Suppressed: %s', _e)
class ReceiptSearchMatchWidget(QWidget):
    """Lightweight, crash-safe rebuild of the receipt search/match UI."""

    vendor_lookup_names_ready = pyqtSignal(list)

    def __init__(
        self, conn: psycopg2.extensions.connection, parent=None
    ) -> None:
        super().__init__(parent)
        self.conn = conn
        self.last_results: list[tuple] = []
        self.write_enabled = str(
            os.environ.get("RECEIPT_WIDGET_WRITE_ENABLED", "true")
        ).lower() in (
            "1",
            "true",
            "yes",
        )
        # Debug logging for write mode
        env_value = os.environ.get("RECEIPT_WIDGET_WRITE_ENABLED", "(not set)")
        logger.debug(f"\n{'=' * 70}")
        logger.debug("📋 RECEIPT WIDGET INITIALIZATION")
        logger.debug(f"{'=' * 70}")
        logger.debug(
            f"Environment Variable: RECEIPT_WIDGET_WRITE_ENABLED = "
            f"{env_value}"
        )

        logger.debug(f"Write Mode Enabled: {self.write_enabled}")
        if self.write_enabled:
            logger.debug(
                "✅ Add/Update/Delete buttons will be ENABLED when receipts "
                "are selected"
            )
        else:
            logger.debug(
                "⚠️  Add/Update/Delete buttons are DISABLED (read-only mode)"
            )
            logger.debug(
                "   To enable: Set RECEIPT_WIDGET_WRITE_ENABLED=1 and restart"
            )
        logger.debug(f"{'=' * 70}\n")

        self.receipts_columns = self._load_receipts_columns()
        self.fuel_column = self._resolve_fuel_column()
        self._audit_table_checked = False
        self._audit_table_exists = False
        # PERFORMANCE: Lazy load drivers and vehicles only when needed
        self._vehicles_loaded = False
        self._drivers_loaded = False
        self._searching = False  # Re-entrancy guard (legacy; kept for safety)
        self._search_worker: _SearchWorker | None = None
        # Sticky / paintbrush mode: lock vendor, GL, and payment for batch
        # entry
        self._sticky_active = False
        self._sticky_defaults: dict = {}  # keys: vendor, gl_code, payment
        self.vendor_lookup_names_ready.connect(self._apply_vendor_lookup_names)
        self._build_ui()
        # Deferred loading - data loads only when user selects year/range
        # self._load_recent()  # Disabled for performance - use Quick Load
        # buttons instead

    def _apply_vendor_lookup_names(self, names: list[str]) -> None:
        current_text = self.vendor_lookup.currentText()
        self.vendor_lookup.blockSignals(True)
        self.vendor_lookup.clear()
        for name in names:
            self.vendor_lookup.addItem(name)
        idx = self.vendor_lookup.findText(current_text)
        if idx >= 0:
            self.vendor_lookup.setCurrentIndex(idx)
        else:
            self.vendor_lookup.setCurrentIndex(-1)
            self.vendor_lookup.lineEdit().clear()
        self.vendor_lookup.blockSignals(False)

    def _normalized_gl_display_name(
        self, code: str, raw_name: str | None
    ) -> str:
        code_text = str(code or "").strip()
        if code_text in GL_DISPLAY_NAME_OVERRIDES:
            return GL_DISPLAY_NAME_OVERRIDES[code_text]

        clean_name = (
            (raw_name or "").replace("\ufffd", " ").replace("\xa0", " ")
        )
        clean_name = re.sub(r"\s+", " ", clean_name).strip(" —-")
        return clean_name or f"GL Account {code_text}"

    def _find_gl_index_by_code(self, code: str) -> int:
        code_text = str(code or "").strip()
        idx = self.new_gl.findData(code_text)
        if idx >= 0:
            return idx

        for item_idx in range(self.new_gl.count()):
            item_text = (self.new_gl.itemText(item_idx) or "").strip()
            if (
                item_text.startswith(f"{code_text} —")
                or item_text.startswith(f"{code_text}-")
                or item_text.startswith(f"{code_text} ")
                or item_text == code_text
            ):
                return item_idx

        return -1

    def _looks_like_david_reimbursement(
        self,
        vendor: str,
        description: str,
        payment_method: str,
        gl_text: str = "",
    ) -> bool:
        combined = " ".join(
            [
                (vendor or ""),
                (description or ""),
                (payment_method or ""),
                (gl_text or ""),
            ]
        ).lower()
        has_david = "david" in combined
        reimbursement_context = any(
            token in combined
            for token in (
                "reimburse",
                "reimbursement",
                "director vehicle",
                "david richard",
                "2550",
            )
        )
        return has_david and reimbursement_context

    def _maybe_autoselect_david_reimbursement_gl(self, *_args) -> None:
        try:
            vendor = ""
            if hasattr(self, "new_vendor"):
                if hasattr(self.new_vendor, "get_vendor"):
                    vendor = self.new_vendor.get_vendor() or ""
                elif hasattr(self.new_vendor, "currentText"):
                    vendor = self.new_vendor.currentText() or ""
                elif hasattr(self.new_vendor, "text"):
                    vendor = self.new_vendor.text() or ""

            description = (
                self.new_desc.text() if hasattr(self, "new_desc") else ""
            )
            payment_method = (
                self.payment_method.currentText()
                if hasattr(self, "payment_method")
                else ""
            )
            gl_text = (
                self.new_gl.currentText() if hasattr(self, "new_gl") else ""
            )

            if not self._looks_like_david_reimbursement(
                vendor, description, payment_method, gl_text
            ):
                return

            idx = self._find_gl_index_by_code(DAVID_REIMBURSEMENT_GL_CODE)
            if (
                idx >= 0
                and str(self.new_gl.currentData() or "").strip()
                != DAVID_REIMBURSEMENT_GL_CODE
            ):
                self.new_gl.setCurrentIndex(idx)
        except Exception as exc:
            logger.debug(
                "Failed to auto-assign reimbursement GL code: %s", exc
            )

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # MAIN vertical splitter: top area (search+results) vs form panel
        # User can drag the handle to give more room to either region.
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(6)

        # HORIZONTAL splitter inside top area: search sidebar | results table
        self.top_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.top_splitter.setChildrenCollapsible(False)
        self.top_splitter.setHandleWidth(6)

        # Left column: Search/Lookup panel
        self.search_panel = self._build_search_panel()
        self.top_splitter.addWidget(self.search_panel)

        # Right column: Results table and related controls
        self.results_panel = self._build_results_panel()
        self.top_splitter.addWidget(self.results_panel)

        # At 1920×1080 / 125 % scale (1536 logical px wide): sidebar ~340,
        # table gets rest
        self.top_splitter.setSizes([340, 1196])
        # sidebar: don't grow by default
        self.top_splitter.setStretchFactor(0, 0)
        self.top_splitter.setStretchFactor(1, 1)  # results: absorb spare width

        self.main_splitter.addWidget(self.top_splitter)

        # BOTTOM SECTION: Full-width detail/form container
        self.detail_panel = self._build_detail_panel()
        self.main_splitter.addWidget(self.detail_panel)

        # Keep Search/Results readable by default; the detail form scrolls when
        # its smaller share cannot show every field.
        self.main_splitter.setSizes([360, 240])
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(
            1, 2
        )

        outer.addWidget(self.main_splitter)

    def _build_search_panel(self) -> QWidget:
        """Left panel: Quick load + search filters (improved vertical "
        "layout)"""

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        scroll.setMinimumWidth(200)
        scroll.setMaximumWidth(420)

        panel = QWidget()
        panel.setMinimumWidth(300)
        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(8, 8, 8, 8)
        vbox.setSpacing(10)

        # ===== QUICK LOAD PANEL (Year/Range buttons) =====
        quick_load_group = QGroupBox()
        quick_load_layout = QVBoxLayout(quick_load_group)
        quick_load_layout.setSpacing(4)

        self.selected_years = set()
        self.year_buttons = {}
        self._year_btn_style = "font-size: 9pt;"
        self._year_btn_selected_style = (
            "font-size: 9pt; background-color: #ffe08a; border: 1px solid "
            "#cc9a00;"
        )

        # Year buttons - compact rows with 5 columns and smaller font
        current_year = QDate.currentDate().year()

        # Generate years dynamically from current year down to 2012
        years_to_show = list(range(current_year, 2011, -1))

        # Create rows with 7 columns each — 2-digit labels keep them compact
        row_index = 0
        for i in range(0, len(years_to_show), 7):
            year_row = QHBoxLayout()
            year_row.setSpacing(2)

            for year in years_to_show[i : i + 7]:
                # 2-digit: "26" instead of "2026"
                btn = QPushButton(str(year)[2:])
                btn.setMinimumHeight(22)
                btn.setMaximumHeight(22)
                btn.setToolTip(str(year))
                btn.setStyleSheet(self._year_btn_style)
                btn.clicked.connect(
                    lambda checked, y=year: self._quick_load_year(y)
                )
                self.year_buttons[year] = btn
                year_row.addWidget(btn)

            # Add stretch if row isn't full
            if len(years_to_show[i : i + 7]) < 7:
                year_row.addStretch()

            quick_load_layout.addLayout(year_row)
            row_index += 1

        # Range buttons
        range_row = QHBoxLayout()
        range_row.setSpacing(2)

        last30_btn = QPushButton("Last 30 Days")
        last30_btn.setMinimumHeight(22)
        last30_btn.setMaximumHeight(22)
        last30_btn.setStyleSheet("font-size: 9pt;")
        last30_btn.clicked.connect(lambda: self._quick_load_days(30))
        range_row.addWidget(last30_btn)

        last90_btn = QPushButton("Last 90 Days")
        last90_btn.setMinimumHeight(22)
        last90_btn.setMaximumHeight(22)
        last90_btn.setStyleSheet("font-size: 9pt;")
        last90_btn.clicked.connect(lambda: self._quick_load_days(90))
        range_row.addWidget(last90_btn)

        quick_load_layout.addLayout(range_row)

        all_btn = QPushButton("All Receipts (⚠️ May be slow)")
        all_btn.setStyleSheet("background-color: #ffeeaa; font-size: 9pt;")
        all_btn.setMinimumHeight(22)
        all_btn.setMaximumHeight(22)
        all_btn.clicked.connect(self._quick_load_all)
        quick_load_layout.addWidget(all_btn)

        # Search button added below All Receipts
        self.search_btn = QPushButton("🔍 Search")
        self.search_btn.setStyleSheet(
            "background-color: #aae0ff; font-size: 9pt; font-weight: bold;"
        )
        self.search_btn.setMinimumHeight(26)
        self.search_btn.setMaximumHeight(26)
        self.search_btn.clicked.connect(self._do_search)
        quick_load_layout.addWidget(self.search_btn)

        vbox.addWidget(quick_load_group)

        # ===== SEARCH FILTERS (Vertical Form Layout) =====
        search_group = QGroupBox()
        search_form = QFormLayout(search_group)
        search_form.setSpacing(8)
        search_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        # Amount (FIRST - receives focus) - Single line with +/- inline
        amount_row = QHBoxLayout()
        amount_row.setSpacing(5)
        self.amount_filter = QDoubleSpinBox()
        self.amount_filter.setRange(-1_000_000_000, 1_000_000_000)
        self.amount_filter.setDecimals(2)
        self.amount_filter.setPrefix("$")
        self.amount_filter.setValue(0.00)
        self.amount_filter.setMaximumWidth(100)
        # Select all text when focused for easy replacement
        self.amount_filter.focusInEvent = lambda event: self._on_spinbox_focus(
            self.amount_filter, event
        )
        # Select all on single click to prevent cursor-only edits
        self.amount_filter.mousePressEvent = (
            lambda event: (
                QDoubleSpinBox.mousePressEvent(self.amount_filter, event)
                or QTimer.singleShot(0, self.amount_filter.selectAll)
            )
            and None
        )
        # Also select on double-click
        self.amount_filter.mouseDoubleClickEvent = (
            lambda event: self.amount_filter.selectAll()
        )
        amount_row.addWidget(self.amount_filter)

        amount_row.addWidget(QLabel("±"))
        self.amount_range = QDoubleSpinBox()
        self.amount_range.setRange(0, 10000)
        self.amount_range.setDecimals(2)
        self.amount_range.setPrefix("$")
        self.amount_range.setValue(0.00)
        self.amount_range.setMaximumWidth(90)
        # Select all text when focused for easy replacement
        self.amount_range.focusInEvent = lambda event: self._on_spinbox_focus(
            self.amount_range, event
        )
        self.amount_range.mousePressEvent = (
            lambda event: (
                QDoubleSpinBox.mousePressEvent(self.amount_range, event)
                or QTimer.singleShot(0, self.amount_range.selectAll)
            )
            and None
        )
        self.amount_range.mouseDoubleClickEvent = (
            lambda event: self.amount_range.selectAll()
        )
        amount_row.addWidget(self.amount_range)
        amount_row.addStretch()
        search_form.addRow("Amount:", amount_row)

        # Connect Enter key in amount field to search
        self.amount_filter.editingFinished.connect(self._on_amount_enter)

        # Receipt ID
        receipt_id_row = QHBoxLayout()
        self.receipt_id_filter = QLineEdit()
        self.receipt_id_filter.setPlaceholderText("e.g., 173235")
        # Auto-select on focus for easy replacement
        self.receipt_id_filter.focusInEvent = (
            lambda event: self._on_lineedit_focus(
                self.receipt_id_filter, event
            )
        )
        receipt_id_row.addWidget(self.receipt_id_filter)
        receipt_id_row.addStretch()
        search_form.addRow("Receipt ID:", receipt_id_row)

        # Vendor filter — hidden backing widget; vendor_lookup combo drives it
        self.vendor_filter = QLineEdit()
        self.vendor_filter.setPlaceholderText("e.g., Fibrenew, Shell, etc.")
        self.include_desc_chk = QCheckBox("Include description")

        # Date Range
        date_row = QVBoxLayout()
        date_row.setSpacing(3)
        date_from_row = QHBoxLayout()
        date_from_row.addWidget(QLabel("From:"))
        self.date_from = StandardDateEdit()
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        date_from_row.addWidget(self.date_from)
        date_row.addLayout(date_from_row)

        date_to_row = QHBoxLayout()
        date_to_row.addWidget(QLabel("To:"))
        self.date_to = StandardDateEdit()
        self.date_to.setDate(QDate.currentDate())
        date_to_row.addWidget(self.date_to)
        date_row.addLayout(date_to_row)

        date_range_row = QHBoxLayout()
        date_range_row.addWidget(QLabel("±"))
        self.date_range_days = QDoubleSpinBox()
        self.date_range_days.setRange(0, 365)
        self.date_range_days.setValue(0)
        self.date_range_days.setSuffix(" days")
        # Select all text when focused for easy replacement
        self.date_range_days.focusInEvent = (
            lambda event: self._on_spinbox_focus(self.date_range_days, event)
        )
        self.date_range_days.mouseDoubleClickEvent = (
            lambda event: self.date_range_days.selectAll()
        )
        date_range_row.addWidget(self.date_range_days)
        date_range_row.addStretch()
        date_row.addLayout(date_range_row)
        search_form.addRow("Date Range:", date_row)

        # Vendor Lookup (populated by year/date selection)
        vendor_lookup_row = QHBoxLayout()
        self.vendor_lookup = QComboBox()
        self.vendor_lookup.setEditable(True)
        self.vendor_lookup.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.vendor_lookup.setMinimumWidth(160)
        self.vendor_lookup.setToolTip(
            "Type a vendor name to filter, or select from the list.\n"
            "Select a year first to populate the dropdown."
        )
        self.vendor_lookup.lineEdit().setPlaceholderText(
            "Vendor (type to filter)"
        )
        self.vendor_lookup.currentIndexChanged.connect(
            self._on_vendor_lookup_selected
        )
        # Wire free typing in the editable combo through to vendor_filter
        # backing field
        self.vendor_lookup.lineEdit().textChanged.connect(
            lambda t: self.vendor_filter.setText(t)
        )
        vendor_lookup_row.addWidget(self.vendor_lookup)
        vendor_lookup_row.addWidget(self.include_desc_chk)
        search_form.addRow("Vendor:", vendor_lookup_row)

        # Options - horizontal layout for more compact display
        options_layout = QHBoxLayout()
        self.sum_by_banking_chk = QCheckBox("Sum by banking link")
        options_layout.addWidget(self.sum_by_banking_chk)
        self.show_linked_splits_chk = QCheckBox("Show linked splits")
        self.show_linked_splits_chk.setToolTip(
            "When checked, shows all individual split receipt lines "
            "separately.\n"
            "When unchecked, groups split receipts as single row with total "
            "amount.\n\n"
            "Use this to see the individual GL splits after splitting a "
            "receipt."
        )

        self.show_linked_splits_chk.setStyleSheet(
            "font-weight: bold; color: #0066cc; padding: 3px;"
        )
        options_layout.addWidget(self.show_linked_splits_chk)
        self.hide_nsf_pairs_chk = QCheckBox("Hide NSF pairs")
        self.hide_nsf_pairs_chk.setChecked(
            True
        )  # hidden by default — both sides net to zero
        self.hide_nsf_pairs_chk.setToolTip(
            "NSF pairs are matched bounce/return receipt pairs that net to "
            "zero.\n"
            "They are excluded from expense totals. Hide both or show both.\n"
            "Uncheck to reveal all NSF pair receipts (shown in orange)."
        )
        self.hide_nsf_pairs_chk.setStyleSheet(
            "font-weight: bold; color: #cc6600; padding: 3px;"
        )
        options_layout.addWidget(self.hide_nsf_pairs_chk)
        options_layout.addStretch()
        search_form.addRow("Options:", options_layout)

        # Sort Options
        sort_layout = QHBoxLayout()
        self.sort_column = QComboBox()
        self.sort_column.addItems(
            [
                "Date (newest)",
                "Date (oldest)",
                "Amount (high-low)",
                "Amount (low-high)",
                "ID (desc)",
                "ID (asc)",
                "Vendor A-Z",
                "Vendor Z-A",
            ]
        )
        self.sort_column.setCurrentIndex(0)  # Default: Date newest first
        sort_layout.addWidget(self.sort_column)
        sort_layout.addStretch()
        search_form.addRow("Sort By:", sort_layout)

        vbox.addWidget(search_group)

        # Set focus to amount field
        self.amount_filter.setFocus()

        # Action buttons moved to top detail panel header
        # Notes and warnings removed for cleaner UI

        # Status label
        self.results_label = QLabel("")
        self.results_label.setStyleSheet(
            "color: #0066cc; font-size: 10pt; margin-top: 8px; font-weight: "
            "bold; padding: 5px;"
        )
        self.results_label.setWordWrap(True)
        vbox.addWidget(self.results_label)

        # Write mode indicator
        write_mode_text = (
            "🔓 Write Mode: ENABLED"
            if self.write_enabled
            else "🔒 Write Mode: DISABLED (read-only)"
        )
        write_mode_color = "#00aa00" if self.write_enabled else "#cc0000"
        self.write_mode_label = QLabel(write_mode_text)
        self.write_mode_label.setStyleSheet(
            f"color: {write_mode_color}; font-size: 8pt; font-weight: bold; "
            f"padding: 3px; border: 1px solid {write_mode_color}; "
            "border-radius: 3px; background-color: "
            f"{'#eaffea' if self.write_enabled else '#ffecec'};"
        )
        self.write_mode_label.setWordWrap(True)
        if not self.write_enabled:
            self.write_mode_label.setToolTip(
                "To enable write mode, set environment variable:\n"
                "RECEIPT_WIDGET_WRITE_ENABLED=1\n"
                "Then restart the application."
            )
        vbox.addWidget(self.write_mode_label)

        vbox.addStretch()
        panel.setMinimumHeight(vbox.sizeHint().height())
        scroll.setWidget(panel)
        return scroll

    def _search_banking_transactions(self) -> None:
        """Search for banking transactions with filters."""
        try:
            # Rollback any previous failed transaction
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            # Build the query - use transaction_id (verified primary key)
            id_col = "transaction_id"
            status_case = (
                "'Unmatched' AS status"  # No banking_transaction_id column
            )
            sql_parts = [
                f"SELECT bt.{id_col}, bt.transaction_date, bt.description,",
                "COALESCE(bt.debit_amount, bt.credit_amount, 0) AS amount,",
                "COALESCE(bt.account_number, 'N/A') AS account,",
                status_case,
                "FROM banking_transactions bt",
                "WHERE 1=1",
            ]
            params = []

            # Get filter values
            amount_text = (
                (getattr(self, "bank_amount_filter", None)
                and self.bank_amount_filter.text())
                or ""
            ).strip()
            if amount_text:
                try:
                    amt = float(amount_text.replace(",", ""))
                    sql_parts.append(
                        "AND (ABS(COALESCE(bt.debit_amount, 0) - %s) < 1.0 "
                        "OR ABS(COALESCE(bt.credit_amount, 0) - %s) < 1.0)"
                    )
                    params.extend([amt, amt])
                except ValueError:
                    pass

            # Date filters
            if hasattr(self, "bank_date_from") and hasattr(
                self, "bank_date_to"
            ):
                date_from = self.bank_date_from.date().toPyDate()
                date_to = self.bank_date_to.date().toPyDate()
                if date_from and date_to:
                    sql_parts.append(
                        "AND bt.transaction_date BETWEEN %s AND %s"
                    )
                    params.extend([date_from, date_to])

            # Show only unmatched if checkbox exists and is unchecked
            if (
                hasattr(self, "bank_show_all_chk")
                and not self.bank_show_all_chk.isChecked()
            ):
                # No banking_transaction_id in local DB
                pass

            sql_parts.append(
                f"ORDER BY bt.transaction_date DESC, bt.{id_col} DESC LIMIT "
                f"100"
            )

            sql = "\n".join(sql_parts)

            cur = self.conn.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()
            cur.close()
            self.conn.commit()

            # Display results in results_table
            self.results_table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                tid, tdate, desc, amount, account, status = row
                self.results_table.setItem(r, 0, QTableWidgetItem(str(tid)))
                self.results_table.setItem(r, 1, QTableWidgetItem(str(tdate)))
                self.results_table.setItem(r, 2, QTableWidgetItem(desc or ""))

                amt_item = QTableWidgetItem(
                    f"${amount:,.2f}" if amount else ""
                )
                amt_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self.results_table.setItem(r, 3, amt_item)

                self.results_table.setItem(
                    r, 4, QTableWidgetItem(account or "")
                )
                self.results_table.setItem(r, 5, QTableWidgetItem(f"{status}"))

                # Color code by status
                if status == "Unmatched":
                    bg_color = QColor(255, 255, 200)  # Light yellow
                else:
                    bg_color = QColor(200, 255, 200)  # Light green
                for col in range(6):
                    item = self.results_table.item(r, col)
                    if item:
                        item.setBackground(bg_color)

            QMessageBox.information(
                self,
                "Banking Search",
                f"✅ Found {len(rows)} banking transaction(s)",
            )

        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.critical(
                self,
                "Banking Search Error",
                f"Could not search banking transactions:\n\n{e}",
            )

    def _build_results_panel(self) -> QWidget:
        """Right column in top section: Results table, matches pane, and
        charter lookup
        """
        panel = QWidget()
        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(5, 5, 5, 5)
        vbox.setSpacing(8)

        # Results table with updated headers
        self.results_table = QTableWidget(0, 9)
        self.results_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Date",
                "Vendor",
                "Amount",
                "GL/Category",
                "Banking ID",
                "Banking Type",
                "Payment Type",
                "Charter",
                "Paper ✓",
            ]
        )
        # Enable click-to-sort on column headers
        self.results_table.setSortingEnabled(True)

        header: QHeaderView = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.itemSelectionChanged.connect(
            self._populate_form_from_selection
        )
        # Double-click to show split matches pane
        self.results_table.itemDoubleClicked.connect(
            self._on_result_double_clicked
        )
        vbox.addWidget(self.results_table)

        # Build and add split matches pane
        self.matches_pane = self._build_matches_pane()
        self.matches_pane.setVisible(False)
        self.matches_pane.setMaximumHeight(150)
        vbox.addWidget(self.matches_pane)

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
        self.charter_lookup_input.setPlaceholderText(
            "Reserve # (e.g., 012345)"
        )
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

        return panel

    def _build_detail_panel(self) -> QWidget:
        """Bottom section spanning full width: Form fields for receipts"""
        panel = QWidget()
        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(5, 5, 5, 5)
        vbox.setSpacing(8)

        # Comprehensive form layout matching screenshot
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        form_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        # Always show at least ~6 rows of fields
        form_scroll.setMinimumHeight(260)
        form_widget = QWidget()
        # MinimumExpanding: form widget expands to fill scroll area but never
        # collapses below its minimum hint, preventing field squish on resize
        form_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding
        )
        form_main_layout = QVBoxLayout(form_widget)
        form_main_layout.setContentsMargins(5, 5, 5, 5)
        form_main_layout.setSpacing(8)

        # Document Type selector at top with ALL ACTION BUTTONS inline
        doc_type_group = QWidget()
        doc_type_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        doc_type_layout = QHBoxLayout(doc_type_group)
        doc_type_layout.setContentsMargins(0, 0, 0, 0)
        doc_type_layout.setSpacing(6)
        doc_type_layout.addWidget(QLabel("Document Type:"))
        self.doc_type_receipt = QRadioButton("Receipt (Paid Immediately)")
        self.doc_type_invoice = QRadioButton("Invoice (May be unpaid)")
        self.doc_type_receipt.setChecked(True)
        doc_type_layout.addWidget(self.doc_type_receipt)
        doc_type_layout.addWidget(self.doc_type_invoice)

        # Separator
        doc_type_layout.addSpacing(15)
        separator = QLabel("│")
        separator.setStyleSheet("color: #999;")
        doc_type_layout.addWidget(separator)
        doc_type_layout.addSpacing(5)

        # ALL ACTION BUTTONS - Better sizing (34px height)
        self.add_btn = QPushButton("➕ Add")
        self.add_btn.setToolTip("Add a new receipt to the database")
        self.add_btn.clicked.connect(self._add_receipt)
        self.add_btn.setMaximumHeight(34)
        self.add_btn.setMinimumWidth(75)
        self.add_btn.setMaximumWidth(75)
        self.add_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; "
            "font-size: 9pt;"
        )
        doc_type_layout.addWidget(self.add_btn)

        self.update_btn = QPushButton("💾 Update")
        if self.write_enabled:
            self.update_btn.setToolTip(
                "Update the selected receipt (select a receipt to enable)"
            )
        else:
            self.update_btn.setToolTip(
                "Update disabled - Write mode is OFF\n\n"
                "To enable: Set RECEIPT_WIDGET_WRITE_ENABLED=1 and restart "
                "the app"
            )
        self.update_btn.clicked.connect(self._update_receipt)
        self.update_btn.setEnabled(False)
        self.update_btn.setMaximumHeight(34)
        self.update_btn.setMinimumWidth(90)
        self.update_btn.setMaximumWidth(90)
        self.update_btn.setStyleSheet("font-size: 9pt;")
        doc_type_layout.addWidget(self.update_btn)

        self.split_btn = QPushButton("✂️ Split")
        self.split_btn.setToolTip(
            "Split this receipt into multiple line items"
        )
        self.split_btn.clicked.connect(self._open_split_dialog)
        self.split_btn.setMaximumHeight(34)
        self.split_btn.setMinimumWidth(75)
        self.split_btn.setMaximumWidth(75)
        self.split_btn.setStyleSheet("font-size: 9pt;")
        doc_type_layout.addWidget(self.split_btn)

        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.setToolTip("Delete the selected receipt")
        self.delete_btn.clicked.connect(self._delete_selected_receipts)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setMaximumHeight(34)
        self.delete_btn.setMinimumWidth(80)
        self.delete_btn.setMaximumWidth(80)
        self.delete_btn.setStyleSheet(
            "background-color: #f44336; color: white; font-size: 9pt;"
        )
        doc_type_layout.addWidget(self.delete_btn)

        # Left sidebar buttons moved here
        self.find_receipts_btn = QPushButton("🔍 Find")
        self.find_receipts_btn.setToolTip(
            "Find receipts using left sidebar filters"
        )
        self.find_receipts_btn.clicked.connect(self._do_search)
        self.find_receipts_btn.setMaximumHeight(34)
        self.find_receipts_btn.setMinimumWidth(70)
        self.find_receipts_btn.setMaximumWidth(70)
        self.find_receipts_btn.setStyleSheet(
            "background-color: #2196F3; color: white; font-weight: bold; "
            "font-size: 9pt;"
        )
        doc_type_layout.addWidget(self.find_receipts_btn)

        self.clear_btn = QPushButton("🧹 Clear")
        self.clear_btn.setToolTip(
            "Clear form fields — ready for new receipt entry (does not affect "
            "search results)"
        )
        self.clear_btn.clicked.connect(self._clear_form)
        self.clear_btn.setMaximumHeight(34)
        self.clear_btn.setMinimumWidth(70)
        self.clear_btn.setMaximumWidth(70)
        self.clear_btn.setStyleSheet("font-size: 9pt;")
        doc_type_layout.addWidget(self.clear_btn)

        banking_match_btn = QPushButton("🏦 Bank")
        banking_match_btn.setToolTip("Find matching banking transactions")
        banking_match_btn.clicked.connect(self._suggest_banking_matches)
        banking_match_btn.setMaximumHeight(34)
        banking_match_btn.setMinimumWidth(75)
        banking_match_btn.setMaximumWidth(75)
        banking_match_btn.setStyleSheet("font-size: 9pt;")
        doc_type_layout.addWidget(banking_match_btn)

        self.link_to_form_btn = QPushButton("📋 Prefill")
        self.link_to_form_btn.setToolTip("Populate form from selected receipt")
        self.link_to_form_btn.clicked.connect(self._prefill_from_search)
        self.link_to_form_btn.setMaximumHeight(34)
        self.link_to_form_btn.setMinimumWidth(75)
        self.link_to_form_btn.setMaximumWidth(75)
        self.link_to_form_btn.setStyleSheet("font-size: 9pt;")
        doc_type_layout.addWidget(self.link_to_form_btn)

        self.sticky_btn = QPushButton("\U0001f58c\ufe0f Sticky")
        self.sticky_btn.setToolTip(
            "Sticky mode: lock Vendor, GL Code and Payment Type so they "
            "survive\n"
            "every Save/Clear.  Only Date, Amount and Description reset.\n"
            "Click again to turn off and restore normal clear behaviour."
        )
        self.sticky_btn.setCheckable(True)
        self.sticky_btn.clicked.connect(self._toggle_sticky_mode)
        self.sticky_btn.setMaximumHeight(34)
        self.sticky_btn.setMinimumWidth(80)
        self.sticky_btn.setMaximumWidth(80)
        self.sticky_btn.setStyleSheet("font-size: 9pt;")
        doc_type_layout.addWidget(self.sticky_btn)

        bulk_import_btn = QPushButton("📥 CSV")
        bulk_import_btn.setToolTip("Import multiple receipts from CSV file")
        bulk_import_btn.clicked.connect(self._open_bulk_import)
        bulk_import_btn.setMaximumHeight(34)
        bulk_import_btn.setMinimumWidth(70)
        bulk_import_btn.setMaximumWidth(70)
        bulk_import_btn.setStyleSheet("font-size: 9pt;")
        doc_type_layout.addWidget(bulk_import_btn)

        reconcile_btn = QPushButton("⚖️ Reconcile")
        reconcile_btn.setToolTip("Quick reconciliation view")
        reconcile_btn.clicked.connect(self._open_reconciliation_view)
        reconcile_btn.setMaximumHeight(34)
        reconcile_btn.setMinimumWidth(95)
        reconcile_btn.setMaximumWidth(95)
        reconcile_btn.setStyleSheet("font-size: 9pt;")
        doc_type_layout.addWidget(reconcile_btn)

        doc_type_layout.addStretch()
        doc_type_group.setFixedHeight(doc_type_layout.sizeHint().height())
        form_main_layout.addWidget(doc_type_group, 0)  # 0 = no stretch

        # Main form fields
        self.form_layout = QFormLayout()
        self.form_layout.setHorizontalSpacing(
            8
        )  # Reduce space between labels and fields
        self.form_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        # Create amount widget early so it can be referenced for GST calc
        self.new_amount = CurrencyInput()

        # Create vendor widget early for first row
        self.new_vendor = VendorLookupWidget(self.conn)
        self.new_vendor.setMinimumWidth(250)
        self.new_vendor.setMaximumWidth(400)
        self.new_vendor.setMinimumHeight(28)

        # Create GL Account combo early to add to top line
        self.new_gl = QComboBox()
        self.new_gl.setEditable(True)
        self.new_gl.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.new_gl.setPlaceholderText("GL code or category...")
        self.new_gl.setMinimumWidth(120)
        self.new_gl.setMaximumWidth(250)
        self.new_gl.setMinimumHeight(28)

        # Block signals during loading to prevent premature calls
        self.new_gl.blockSignals(True)
        try:
            cur = self.conn.cursor()
            # Load ONLY from chart_of_accounts: active, non-header accounts
            cur.execute("""
                SELECT account_code, account_name
                FROM chart_of_accounts
                WHERE is_active = TRUE
                  AND (is_header_account IS NULL OR is_header_account = FALSE)
                ORDER BY account_code
            """)
            rows = cur.fetchall()
            loaded_codes = set()
            for code, name in rows:
                if code:
                    code_text = str(code).strip()
                    if not code_text:
                        continue
                    self.new_gl.addItem(
                        f"{code_text} — "
                        f"{self._normalized_gl_display_name(code_text, name)}",
                        code_text,
                    )
                    loaded_codes.add(code_text)

            # Add David Reimbursement if not in active list
            if DAVID_REIMBURSEMENT_GL_CODE not in loaded_codes:
                self.new_gl.addItem(
                    f"{DAVID_REIMBURSEMENT_GL_CODE} — "
                    + self._normalized_gl_display_name(
                        DAVID_REIMBURSEMENT_GL_CODE, ""
                    ),
                    DAVID_REIMBURSEMENT_GL_CODE,
                )
            completer = QCompleter(
                [self.new_gl.itemText(i) for i in range(self.new_gl.count())]
            )
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.new_gl.setCompleter(completer)
            cur.close()
        except Exception as e:
            logger.warning("Error loading GL accounts: %s", e)
        finally:
            self.new_gl.blockSignals(False)

        # Receipt Date + Amount + Tax Jurisdiction + Vendor + Payment Method
        # row
        date_amount_vendor_row = QHBoxLayout()
        self.new_date = DateInput()
        self.new_date.setMinimumWidth(100)
        self.new_date.setMaximumWidth(130)
        self.new_date.setMinimumHeight(28)
        date_amount_vendor_row.addWidget(self.new_date)
        date_amount_vendor_row.addWidget(QLabel(" Amount:"))
        self.new_amount.setMinimumWidth(100)
        self.new_amount.setMaximumWidth(120)
        self.new_amount.setMinimumHeight(28)
        date_amount_vendor_row.addWidget(self.new_amount)

        # Tax Jurisdiction moved here between Amount and Vendor
        date_amount_vendor_row.addWidget(QLabel(" Tax Jurisdiction:"))
        self.tax_jurisdiction = QComboBox()
        self.tax_jurisdiction.addItems(
            [
                "AB (GST 5%)",
                "BC (GST 5% + PST 7%)",
                "SK (GST 5%)",
                "MB (GST 5%)",
                "ON (HST 13%)",
                "QC (GST 5% + PST 9.975%)",
                "NB (HST 15%)",
                "NS (HST 15%)",
                "PE (HST 15%)",
                "NL (HST 15%)",
                "YT (GST 5%)",
                "NT (GST 5%)",
                "NU (GST 5%)",
                "US (varies)",
                "Other (manual entry)",
            ]
        )
        self.tax_jurisdiction.setCurrentIndex(0)
        self.tax_jurisdiction.setMinimumWidth(100)
        self.tax_jurisdiction.setMaximumWidth(140)
        self.tax_jurisdiction.setMinimumHeight(28)
        date_amount_vendor_row.addWidget(self.tax_jurisdiction)

        date_amount_vendor_row.addWidget(QLabel(" Vendor:"))
        date_amount_vendor_row.addWidget(self.new_vendor)

        # Payment Method moved here next to Vendor
        date_amount_vendor_row.addWidget(QLabel(" Payment:"))
        self.payment_method = QComboBox()
        self.payment_method.addItems(
            [
                "cash",
                "check",
                "credit_card",
                "debit_card",
                "bank_transfer",
                "pre_authorized_debit",
                "trade_of_services",
                "reimbursement",
                "loan",
                "FAS Gas Rebate",
                "Special Airline Charge",
                "Charter Adjustment",
                "Fuel Surcharge",
                "unknown",
            ]
        )
        # Set default to debit_card
        debit_idx = self.payment_method.findText("debit_card")
        if debit_idx >= 0:
            self.payment_method.setCurrentIndex(debit_idx)
        self.payment_method.setMinimumWidth(120)
        self.payment_method.setMaximumWidth(180)
        self.payment_method.setMinimumHeight(28)
        date_amount_vendor_row.addWidget(self.payment_method)

        # Personal checkbox moved here (right of Payment)
        date_amount_vendor_row.addWidget(QLabel(" Personal:"))
        self.personal_chk = QCheckBox()
        date_amount_vendor_row.addWidget(self.personal_chk)

        date_amount_vendor_row.addStretch()
        self.form_layout.addRow("Date:", date_amount_vendor_row)

        # Calculator + GL Code + Description + Invoice row
        calc_gl_row = QHBoxLayout()
        calc_btn = QPushButton("🧮 Calc")
        calc_btn.setMaximumWidth(70)
        calc_btn.setToolTip("Calculator")

        def _open_calc() -> None:
            dlg = CalculatorDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                val = dlg.evaluate()
                if val is None:
                    QMessageBox.warning(
                        self,
                        "Invalid expression",
                        "Please enter a valid arithmetic expression.",
                    )
                else:
                    self.new_amount.setText(f"{float(val):.2f}")

        calc_btn.clicked.connect(_open_calc)
        calc_gl_row.addWidget(calc_btn)
        calc_gl_row.addWidget(QLabel(" GL Code:"))
        calc_gl_row.addWidget(self.new_gl)
        calc_gl_row.addWidget(QLabel(" Description:"))
        self.new_desc = QLineEdit()
        self.new_desc.setPlaceholderText("e.g., Office rent - March 2013")
        self.new_desc.setMaximumHeight(28)  # Lock height
        self.new_desc.setMinimumWidth(200)
        self.new_desc.textChanged.connect(
            self._maybe_autoselect_david_reimbursement_gl
        )
        calc_gl_row.addWidget(self.new_desc)
        calc_gl_row.addWidget(QLabel(" Invoice #:"))
        self.invoice_number = QLineEdit()
        self.invoice_number.setPlaceholderText("INV-001")
        self.invoice_number.setMaximumWidth(100)  # 12 characters approx
        calc_gl_row.addWidget(self.invoice_number)
        calc_gl_row.addStretch()
        self.form_layout.addRow("", calc_gl_row)

        # Manual GST override with enable/disable logic
        self.gst_override_enable = QCheckBox("Manual GST override")
        self.gst_override_input = QDoubleSpinBox()
        self.gst_override_input.setRange(-100000, 100000)
        self.gst_override_input.setDecimals(2)
        self.gst_override_input.setMinimumWidth(80)
        self.gst_override_input.setMaximumWidth(120)
        self.gst_override_input.setEnabled(False)
        self.gst_override_reason = QComboBox()
        self.gst_override_reason.addItems(
            [
                "Manual - Government fee",
                "Manual - NGO donation",
                "Manual - Zero-rated grocery",
                "Manual - test",
            ]
        )
        self.gst_override_reason.setMinimumWidth(150)
        self.gst_override_reason.setMaximumWidth(220)
        self.gst_override_reason.setEnabled(False)
        self.gst_override_enable.toggled.connect(
            lambda on: (
                self.gst_override_input.setEnabled(on),
                self.gst_override_reason.setEnabled(on),
            )
        )

        # Override Note
        self.override_note = QLineEdit()
        self.override_note.setPlaceholderText(
            "Optional note for audit (e.g., gov fee exempt, only service fee "
            "taxable)"
        )
        self.override_note.setMinimumWidth(220)

        # GST (auto-calculated) + manual override + override note (single row)
        gst_auto_row = QHBoxLayout()
        self.gst_auto_label = QLabel("$0.00")
        self.gst_auto_label.setStyleSheet("color: blue; font-weight: bold;")
        gst_auto_row.addWidget(self.gst_auto_label)
        gst_auto_row.addSpacing(12)
        gst_auto_row.addWidget(self.gst_override_enable)
        gst_auto_row.addWidget(self.gst_override_input)
        gst_auto_row.addWidget(self.gst_override_reason)
        gst_auto_row.addWidget(QLabel("Note:"))
        gst_auto_row.addWidget(self.override_note)
        gst_auto_row.addStretch()
        self.form_layout.addRow("GST (auto):", gst_auto_row)

        # Tax Jurisdiction was moved to the first row (between Amount and
        # Vendor)

        # Auto-calculate GST when amount changes
        def _update_gst() -> None:
            try:
                amt_text = (
                    self.new_amount.text()
                    .replace("$", "")
                    .replace(",", "")
                    .strip()
                )
                if amt_text:
                    gross = float(amt_text)
                    # 5% GST included in gross
                    gst_amount = gross * 0.05 / (1 + 0.05)
                    self.gst_auto_label.setText(f"${gst_amount:.2f}")
                else:
                    self.gst_auto_label.setText("$0.00")
            except Exception:
                self.gst_auto_label.setText("$0.00")

        self.new_amount.textChanged.connect(_update_gst)

        # PST / Sales Tax (shown only for provinces with PST/HST)
        pst_row = QHBoxLayout()
        self.pst_amount = QDoubleSpinBox()
        self.pst_amount.setRange(-100000, 100000)
        self.pst_amount.setDecimals(2)
        self.pst_amount.setMinimumWidth(80)
        self.pst_amount.setMaximumWidth(120)
        pst_row.addWidget(self.pst_amount)
        pst_row.addStretch()
        pst_row_widget = QWidget()
        pst_row_widget.setLayout(pst_row)
        pst_label = QLabel("PST / Sales Tax:")
        self.form_layout.addRow(pst_label, pst_row_widget)

        def _toggle_pst_visibility(text: str) -> None:
            upper = (text or "").upper()
            show = ("PST" in upper) or ("HST" in upper)
            pst_label.setVisible(show)
            pst_row_widget.setVisible(show)
            # Collapse the row completely when hidden
            if show:
                pst_label.setMaximumHeight(16777215)  # Qt max
                pst_row_widget.setMaximumHeight(16777215)
            else:
                pst_label.setMaximumHeight(0)
                pst_row_widget.setMaximumHeight(0)

        self.tax_jurisdiction.currentTextChanged.connect(
            _toggle_pst_visibility
        )
        _toggle_pst_visibility(self.tax_jurisdiction.currentText())

        # self.new_amount is created earlier in the form to allow GST auto-calc
        QTimer.singleShot(0, self._attach_vendor_completer)

        # Fleet Unit (Vehicle) + Fuel (L) + Charter Number
        self.fuel_liters = QDoubleSpinBox()
        self.fuel_liters.setRange(0, 5000)
        self.fuel_liters.setDecimals(2)
        self.fuel_liters.setSuffix(" L")
        self.fuel_liters.setMinimumWidth(80)
        self.fuel_liters.setMaximumWidth(120)

        vehicle_row = QHBoxLayout()
        self.new_vehicle_combo = QComboBox()
        self.new_vehicle_combo.addItem("(Click to load vehicles...)", None)
        self.new_vehicle_combo.setMinimumWidth(150)
        self.new_vehicle_combo.setMaximumWidth(220)
        self.new_vehicle_combo.setMinimumHeight(24)
        # PERFORMANCE: Don't load vehicles on init - lazy load on first focus
        # self._load_vehicles_into_combo()  # OLD: Load immediately (slow)
        # Connect lazy load on focus
        self.new_vehicle_combo.installEventFilter(self)
        vehicle_row.addWidget(self.new_vehicle_combo)

        # Fuel field (conditionally visible for fuel/gas GL codes)
        self.fuel_label = QLabel("Fuel:")
        vehicle_row.addWidget(self.fuel_label)
        vehicle_row.addWidget(self.fuel_liters)

        # Odometer field (conditionally visible for maintenance/repair GL codes
        # 5100, 5120)
        self.odometer_label = QLabel("Odometer:")
        self.new_odometer = QSpinBox()
        self.new_odometer.setRange(0, 9999999)
        self.new_odometer.setSpecialValueText("Not recorded")
        self.new_odometer.setSuffix(" km")
        self.new_odometer.setMinimumWidth(120)
        self.new_odometer.setMaximumWidth(150)
        vehicle_row.addWidget(self.odometer_label)
        vehicle_row.addWidget(self.new_odometer)

        # Driver Reimbursement row - Driver | Dvr Personal | Charter # |
        # Vehicle | Fuel | Odometer
        driver_row = QHBoxLayout()
        self.new_driver_combo = QComboBox()
        self.new_driver_combo.setEditable(True)
        self.new_driver_combo.addItem("(Click to load drivers...)", None)
        self.new_driver_combo.setMinimumWidth(200)
        self.new_driver_combo.setMaximumWidth(320)
        self.new_driver_combo.setMinimumHeight(24)
        # PERFORMANCE: Don't load drivers on init - lazy load on first focus
        # self._load_drivers_into_combo()  # OLD: Load immediately (slow)
        # Connect lazy load on focus
        self.new_driver_combo.installEventFilter(self)
        driver_row.addWidget(self.new_driver_combo)

        # Dvr Personal checkbox
        driver_row.addWidget(QLabel(" Dvr Personal:"))
        self.dvr_personal_chk = QCheckBox()
        driver_row.addWidget(self.dvr_personal_chk)

        # Charter # field moved here (right of Dvr Personal)
        driver_row.addWidget(QLabel(" Charter #:"))
        self.new_charter_input = QLineEdit()
        self.new_charter_input.setPlaceholderText("e.g., 015234")
        self.new_charter_input.setMinimumWidth(220)
        self.new_charter_input.setMaximumWidth(360)
        self.new_charter_input.focusInEvent = (
            lambda event: self._on_lineedit_focus(
                self.new_charter_input, event
            )
        )
        self.new_charter_input.mousePressEvent = (
            lambda event: self._on_lineedit_click(
                self.new_charter_input, event
            )
        )
        driver_row.addWidget(self.new_charter_input)

        # Vehicle field moved here (right of Charter #)
        driver_row.addWidget(QLabel(" Vehicle:"))
        driver_row.addWidget(self.new_vehicle_combo)

        # Fuel and Odometer fields (conditionally visible)
        driver_row.addWidget(self.fuel_label)
        driver_row.addWidget(self.fuel_liters)
        driver_row.addWidget(self.odometer_label)
        driver_row.addWidget(self.new_odometer)

        driver_row.addStretch()
        self.form_layout.addRow("Driver Reimburse:", driver_row)

        reimbursement_row = QHBoxLayout()
        reimbursement_row.addWidget(QLabel("Amount to Reimburse:"))
        self.reimbursement_amount_input = CurrencyInput()
        self.reimbursement_amount_input.setPlaceholderText(
            "blank = full amount"
        )
        self.reimbursement_amount_input.setMinimumWidth(110)
        self.reimbursement_amount_input.setMaximumWidth(140)
        reimbursement_row.addWidget(self.reimbursement_amount_input)

        reimbursement_row.addWidget(QLabel("Payee (if not employee):"))
        self.reimbursement_payee_input = QLineEdit()
        self.reimbursement_payee_input.setPlaceholderText(
            "Optional payee name"
        )
        self.reimbursement_payee_input.setMinimumWidth(180)
        self.reimbursement_payee_input.setMaximumWidth(260)
        reimbursement_row.addWidget(self.reimbursement_payee_input)

        reimbursement_row.addWidget(QLabel("Paid Via:"))
        self.reimbursed_via_combo = QComboBox()
        self.reimbursed_via_combo.addItems(
            [
                "Pending",
                "Cash",
                "E-Transfer",
                "Cheque",
                "Payroll",
                "Bank Transfer",
                "Company Card",
            ]
        )
        self.reimbursed_via_combo.setMinimumWidth(120)
        self.reimbursed_via_combo.setMaximumWidth(160)
        reimbursement_row.addWidget(self.reimbursed_via_combo)
        reimbursement_row.addStretch()
        self.form_layout.addRow("Reimbursement:", reimbursement_row)

        # Attach fuzzy lookup completer for charter field (deferred to prevent
        # UI freeze)
        QTimer.singleShot(100, self._attach_charter_completer)

        # Connect GL code change to toggle fuel and odometer visibility
        try:
            self.new_gl.currentIndexChanged.connect(
                self._toggle_conditional_fields
            )
        except Exception as e:
            import traceback

            logger.debug(
                f"⚠️ Could not connect GL signal: "
                f"{e}\n{traceback.format_exc()}"
            )

        # Payment Method was moved to the first row (next to Vendor)
        # Connect to update table colors
        self.payment_method.currentTextChanged.connect(
            self._on_payment_method_changed
        )
        # Personal/Dvr Personal checkboxes were moved to Driver Reimburse row

        if hasattr(self.new_vendor, "currentTextChanged"):
            self.new_vendor.currentTextChanged.connect(
                self._maybe_autoselect_david_reimbursement_gl
            )
        if hasattr(self.new_vendor, "textChanged"):
            self.new_vendor.textChanged.connect(
                self._maybe_autoselect_david_reimbursement_gl
            )

        # Banking Transaction ID with tip
        banking_row = QHBoxLayout()
        self.new_banking_id = QLineEdit()
        self.new_banking_id.setPlaceholderText(
            "Leave blank if cash or reim..."
        )
        self.new_banking_id.setMinimumWidth(150)
        self.new_banking_id.setMaximumWidth(250)
        banking_row.addWidget(self.new_banking_id)
        self.copy_banking_btn = QPushButton("📋 Copy")
        self.copy_banking_btn.setMaximumWidth(70)
        self.copy_banking_btn.clicked.connect(
            lambda: QGuiApplication.clipboard().setText(
                (self.new_banking_id.text() or "").strip()
            )
        )
        banking_row.addWidget(self.copy_banking_btn)
        banking_row.addStretch()
        self.form_layout.addRow("Banking Transaction ID:", banking_row)

        # Add form layout to main layout
        form_main_layout.addLayout(self.form_layout, 0)  # 0 = no stretch

        # Action buttons were moved to doc_type_group header (above)
        # This saves vertical space and allows more rows in the results table

        # Scroll area setup
        form_scroll.setWidget(form_widget)
        # Stretch factor 1 = takes all available space
        vbox.addWidget(form_scroll, 1)

        # Set initial visibility of conditional fields (fuel, odometer)
        self._toggle_conditional_fields()

        return panel

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _link_to_invoice(self) -> None:
        """Link selected receipt to a vendor invoice."""
        rid = getattr(self, "loaded_receipt_id", None)
        if not rid:
            QMessageBox.information(
                self,
                "No Selection",
                "Select a receipt from the table to link to invoice.",
            )
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
                cur.execute(
                    "SELECT DISTINCT vendor_name FROM vendor_invoices "
                    "WHERE vendor_name IS NOT NULL ORDER BY vendor_name"
                )
                for row in cur.fetchall():
                    vendor_combo.addItem(row[0])
                cur.close()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
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
            def _load_invoices() -> None:
                invoice_combo.clear()
                vendor = vendor_combo.currentText()
                if vendor:
                    try:
                        cur = self.conn.cursor()
                        cur.execute(
                            "SELECT vendor_invoice_id, invoice_number, "
                            "invoice_amount FROM vendor_invoices "
                            "WHERE vendor_name = %s ORDER BY invoice_date "
                            "DESC",
                            (vendor,),
                        )
                        for iid, inum, iamt in cur.fetchall():
                            invoice_combo.addItem(f"{inum} (${iamt:.2f})", iid)
                        cur.close()
                    except Exception as _e:
                        logger.debug('Suppressed: %s', _e)
            vendor_combo.currentTextChanged.connect(_load_invoices)
            _load_invoices()

            # Dialog buttons
            btns = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok
                | QDialogButtonBox.StandardButton.Cancel
            )
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)
            layout.addWidget(btns)

            if dlg.exec() != QDialog.DialogCode.Accepted:
                return

            invoice_id = invoice_combo.currentData()
            if not invoice_id:
                QMessageBox.warning(
                    self, "No Invoice", "Please select an invoice."
                )
                return

            # Link receipt to invoice
            cur = self.conn.cursor()
            cur.execute(
                "UPDATE receipts SET vendor_invoice_id = %s WHERE receipt_id "
                "= %s",
                (invoice_id, rid),
            )
            self.conn.commit()
            cur.close()

            QMessageBox.information(
                self,
                "Linked",
                f"Receipt #{rid} linked to invoice "
                f"#{invoice_combo.currentText()}.",
            )
            self._do_search()

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Could not link receipt:\n{e}"
            )

    def _link_to_charter(self) -> None:
        """Link selected receipt to charter (alias for existing charter lookup
        functionality).
        """
        if (
            not hasattr(self, "loaded_receipt_id")
            or not self.loaded_receipt_id
        ):
            QMessageBox.information(
                self,
                "No Selection",
                "Select a receipt from the table to link to charter.",
            )
            return
        self._link_selected_to_charter()

    def _clear_filters(self) -> None:
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        self.date_to.setDate(QDate.currentDate())
        self.vendor_filter.clear()
        self.vendor_lookup.blockSignals(True)
        self.vendor_lookup.setCurrentIndex(0)
        self.vendor_lookup.blockSignals(False)
        self.receipt_id_filter.clear()
        self.amount_filter.setValue(0)
        self.date_range_days.setValue(0)
        self.amount_range.setValue(1.0)
        self.include_desc_chk.setChecked(False)
        self.sum_by_banking_chk.setChecked(False)
        self.show_linked_splits_chk.setChecked(False)
        self.results_label.setText("")
        self.results_label.setStyleSheet("font-size: 9pt;")
        self.results_table.setRowCount(0)

    def _on_spinbox_focus(self, spinbox, event) -> None:
        """Handle focus in QDoubleSpinBox - select all text for easy
        replacement.
        """
        from PyQt6.QtWidgets import QDoubleSpinBox

        QDoubleSpinBox.focusInEvent(spinbox, event)
        QTimer.singleShot(0, spinbox.selectAll)

    def _on_lineedit_focus(self, lineedit, event) -> None:
        """Handle focus in QLineEdit - select all text for easy replacement."""
        from PyQt6.QtWidgets import QLineEdit

        QLineEdit.focusInEvent(lineedit, event)
        lineedit.selectAll()

    def _on_lineedit_click(self, lineedit, event) -> None:
        """Select the complete value even when the field already has focus."""
        from PyQt6.QtWidgets import QLineEdit

        QLineEdit.mousePressEvent(lineedit, event)
        QTimer.singleShot(0, lineedit.selectAll)

    def _on_amount_enter(self) -> None:
        """Called when Enter is pressed in amount field - triggers search."""
        self._do_search()

    def _build_search_sql(self) -> tuple[str, list[object]]:
        """Build the receipt search SQL from current UI filter values.
        Must only be called on the main thread (reads Qt widgets).
        Returns (sql_string, params_list).
        """
        sql = [
            "SELECT r.receipt_id, r.receipt_date, r.vendor_name, "
            "r.gross_amount,",
            "CASE",
            "    WHEN coa.account_code IS NOT NULL THEN coa.account_code || ' "
            "— ' || LEFT(coa.account_name, 60)",
            "    ELSE COALESCE(r.gl_account_code, "
            "r.mapped_expense_account_id::text, r.category, '')",
            "END AS gl_name,",
            "COALESCE(bt_link.transaction_id, r.banking_transaction_id) AS "
            "banking_transaction_id,",
            "CASE",
            "    WHEN COALESCE(NULLIF(bt_id.check_number, ''), "
            "NULLIF(bt_link.check_number, '')) IS NOT NULL THEN 'Cheque'",
            "    WHEN COALESCE(bt_link.credit_amount, bt_id.credit_amount, 0) "
            "> 0 THEN 'Credit'",
            "    WHEN COALESCE(bt_link.debit_amount, bt_id.debit_amount, 0) > "
            "0 THEN 'Debit'",
            "    ELSE ''",
            "END AS banking_type,",
            "COALESCE(r.reserve_number, '') AS charter_num,",
            "COALESCE(r.description, '') AS description,",
            "COALESCE(r.payment_method, '') AS payment_method,",
            "COALESCE(r.created_from_banking, false) AS created_from_banking,",
            "r.vehicle_id,",
            "r.fuel_amount,",
            "r.split_group_id,",
            "COALESCE(r.is_split_receipt, false) AS is_split_receipt,",
            "COALESCE(r.split_group_total, r.gross_amount) AS "
            "split_search_total,",
            "COALESCE(r.is_nsf, false) AS is_nsf,",
            "COALESCE(r.is_paper_verified, false) AS is_paper_verified",
            "FROM receipts r",
            "LEFT JOIN chart_of_accounts coa ON coa.account_code = "
            "r.gl_account_code",
            "LEFT JOIN banking_transactions bt_id ON bt_id.transaction_id = "
            "r.banking_transaction_id",
            "LEFT JOIN LATERAL (",
            "    SELECT bt.transaction_id, bt.debit_amount, bt.credit_amount, "
            "bt.check_number",
            "    FROM banking_transactions bt",
            "    WHERE bt.receipt_id = r.receipt_id",
            "    ORDER BY bt.transaction_date DESC, bt.transaction_id DESC",
            "    LIMIT 1",
            ") bt_link ON true",
            "WHERE 1=1",
        ]
        params: list[object] = []

        start = self.date_from.date()
        end = self.date_to.date()
        if start and end:
            sql.append("AND r.receipt_date BETWEEN %s AND %s")
            params.extend([start.toPyDate(), end.toPyDate()])

        # Receipt ID filter
        receipt_id = (self.receipt_id_filter.text() or "").strip()
        if receipt_id:
            try:
                sql.append("AND r.receipt_id = %s")
                params.append(int(receipt_id))
            except ValueError:
                pass  # Ignore invalid receipt ID

        vendor = (self.vendor_filter.text() or "").strip()
        if vendor:
            if (
                getattr(self, "include_desc_chk", None)
                and self.include_desc_chk.isChecked()
            ):
                sql.append(
                    "AND (r.vendor_name ILIKE %s OR r.description ILIKE %s)"
                )
                params.extend([f"%{vendor}%", f"%{vendor}%"])
            else:
                sql.append("AND r.vendor_name ILIKE %s")
                params.append(f"%{vendor}%")

        # Amount filter with range (±)
        amt = self.amount_filter.value()
        amt_range = self.amount_range.value()
        if amt > 0:
            sql.append("""AND (
                       r.gross_amount BETWEEN %s AND %s
                       OR (
                           COALESCE(r.is_split_receipt, false)
                           AND COALESCE(r.split_group_total, 0)
                               BETWEEN %s AND %s
                       )
                   )""")
            params.extend(
                [
                    float(amt) - float(amt_range),
                    float(amt) + float(amt_range),
                    float(amt) - float(amt_range),
                    float(amt) + float(amt_range),
                ]
            )

        # NSF pair filter — hide both sides of net-zero bounce/return pairs
        if (
            getattr(self, "hide_nsf_pairs_chk", None)
            and self.hide_nsf_pairs_chk.isChecked()
        ):
            sql.append("AND (r.is_nsf IS NULL OR r.is_nsf = FALSE)")

        # Apply sorting based on dropdown selection
        sort_option = self.sort_column.currentText()
        if sort_option == "Date (newest)":
            sql.append("ORDER BY r.receipt_date DESC, r.receipt_id DESC")
        elif sort_option == "Date (oldest)":
            sql.append("ORDER BY r.receipt_date ASC, r.receipt_id ASC")
        elif sort_option == "Amount (high-low)":
            sql.append("ORDER BY r.gross_amount DESC, r.receipt_date DESC")
        elif sort_option == "Amount (low-high)":
            sql.append("ORDER BY r.gross_amount ASC, r.receipt_date DESC")
        elif sort_option == "ID (desc)":
            sql.append("ORDER BY r.receipt_id DESC")
        elif sort_option == "ID (asc)":
            sql.append("ORDER BY r.receipt_id ASC")
        elif sort_option == "Vendor A-Z":
            sql.append("ORDER BY r.vendor_name ASC, r.receipt_date DESC")
        elif sort_option == "Vendor Z-A":
            sql.append("ORDER BY r.vendor_name DESC, r.receipt_date DESC")
        else:
            sql.append("ORDER BY r.receipt_date DESC, r.receipt_id DESC")

        # Cap results to prevent UI crash on very large datasets
        sql.append("LIMIT 2000")

        return "\n".join(sql), params

    def _load_receipt_by_id(self, receipt_id: int) -> None:
        """Load exactly one receipt row by ID into the results table and form.

        Compatibility method used by Enhanced Banking Manager's receipt
        viewer popup.
        """
        try:
            rid = int(receipt_id)
        except (TypeError, ValueError):
            QMessageBox.warning(
                self, "Invalid Receipt", f"Invalid receipt ID: {receipt_id}"
            )
            return

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                  SELECT r.receipt_id, r.receipt_date, r.vendor_name,
                      r.gross_amount,
                CASE
                    WHEN coa.account_code IS NOT NULL THEN
                        coa.account_code || ' — ' || coa.account_name
                    ELSE COALESCE(
                        r.gl_account_code,
                        r.mapped_expense_account_id::text,
                        r.category,
                        ''
                    )
                END AS gl_name,
                COALESCE(
                    bt_link.transaction_id,
                    r.banking_transaction_id
                ) AS banking_transaction_id,
                CASE
                    WHEN COALESCE(
                        NULLIF(bt_id.check_number, ''),
                        NULLIF(bt_link.check_number, '')
                    ) IS NOT NULL THEN 'Cheque'
                    WHEN COALESCE(
                        bt_link.credit_amount, bt_id.credit_amount, 0
                    )
                        > 0 THEN 'Credit'
                    WHEN COALESCE(bt_link.debit_amount, bt_id.debit_amount, 0)
                        > 0 THEN 'Debit'
                    ELSE ''
                END AS banking_type,
                COALESCE(r.reserve_number, '') AS charter_num,
                COALESCE(r.description, '') AS description,
                COALESCE(r.payment_method, '') AS payment_method,
                COALESCE(r.created_from_banking, false)
                    AS created_from_banking,
                r.vehicle_id,
                r.fuel_amount,
                r.split_group_id,
                COALESCE(r.is_split_receipt, false) AS is_split_receipt,
                COALESCE(r.split_group_total, r.gross_amount)
                    AS split_search_total,
                COALESCE(r.is_nsf, false) AS is_nsf,
                COALESCE(r.is_paper_verified, false) AS is_paper_verified
                FROM receipts r
                LEFT JOIN chart_of_accounts coa
                    ON coa.account_code = r.gl_account_code
                LEFT JOIN banking_transactions bt_id
                    ON bt_id.transaction_id = r.banking_transaction_id
                LEFT JOIN LATERAL (
                    SELECT bt.transaction_id, bt.debit_amount,
                           bt.credit_amount, bt.check_number
                    FROM banking_transactions bt
                    WHERE bt.receipt_id = r.receipt_id
                    ORDER BY bt.transaction_date DESC, bt.transaction_id DESC
                    LIMIT 1
                ) bt_link ON true
                WHERE r.receipt_id = %s
                LIMIT 1
                """,
                [rid],
            )
            row = cur.fetchone()
            cur.close()
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.critical(
                self,
                "Load Error",
                f"Could not load receipt #{rid}:\n\n{e}",
            )
            return

        if not row:
            self.results_table.setRowCount(0)
            self._clear_form()
            self.results_label.setText(f"No receipt found for ID {rid}")
            self.results_label.setStyleSheet("color: #cc0000; font-size: 9pt;")
            return

        self.last_results = [row]
        self._populate_table([row])
        self.receipt_id_filter.setText(str(rid))

        if self.results_table.rowCount() > 0:
            self.results_table.setCurrentCell(0, 0)
            self.results_table.selectRow(0)
            self._populate_form_from_selection()

        self.results_label.setText(f"Showing receipt #{rid}")
        self.results_label.setStyleSheet(
            "color: #00aa00; font-size: 9pt; font-weight: bold;"
        )

    def _do_search(self) -> None:
        # Cancel any in-flight search — do NOT call wait() here; blocking the
        # main thread while a previous worker is running causes the UI to
        # freeze
        # and can cascade if timers fire more searches during the wait.
        # The _cancelled flag prevents the old worker from emitting stale
        # results.
        if self._search_worker is not None and self._search_worker.isRunning():
            self._search_worker.cancel()
            self._search_worker.quit()
            # Do NOT call wait() — let the old thread die on its own

        # Build SQL on main thread (reads Qt widgets)
        sql_str, params = self._build_search_sql()

        # Show searching status and disable search button
        self.results_label.setText("🔍 Searching...")
        self.results_label.setStyleSheet(
            "color: #ff8800; font-size: 9pt; font-weight: bold;"
        )
        if hasattr(self, "search_btn"):
            self.search_btn.setEnabled(False)
            self.search_btn.setText("⏳ Searching...")

        # Build connection kwargs from live connection params + password from
        # env
        # (psycopg2's .dsn property strips the password, so we restore it)
        # Guard against the shared conn being closed between operations.
        try:
            _dsn_params = self.conn.get_dsn_parameters()
        except Exception:
            _dsn_params = {}
        _conn_kwargs = {
            "host": _dsn_params.get(
                "host", os.environ.get("DB_HOST", "localhost")
            ),
            "port": int(
                _dsn_params.get("port", os.environ.get("DB_PORT", 5432))
            ),
            "dbname": _dsn_params.get(
                "dbname", os.environ.get("DB_NAME", "almsdata")
            ),
            "user": _dsn_params.get(
                "user", os.environ.get("DB_USER", "postgres")
            ),
            "password": os.environ.get("DB_PASSWORD", ""),
            "connect_timeout": 10,
        }
        _sslmode = os.environ.get("DB_SSLMODE", "")
        if _sslmode:
            _conn_kwargs["sslmode"] = _sslmode
        # Neon pooler rejects statement_timeout as a startup parameter;
        # apply it per-cursor via SET instead.
        _host = _conn_kwargs.get("host", "")
        if not ("-pooler." in _host or ".pooler." in _host):
            _conn_kwargs["options"] = "-c statement_timeout=20000"

        # Launch background worker — keeps UI responsive
        self._search_worker = _SearchWorker(_conn_kwargs, sql_str, params)
        self._search_worker.results_ready.connect(self._on_search_results)
        self._search_worker.error_occurred.connect(self._on_search_error)
        self._search_worker.finished.connect(self._on_search_finished)
        self._search_worker.start()

    def _on_search_finished(self) -> None:
        """Re-enable the search button when the worker thread finishes."""
        if hasattr(self, "search_btn"):
            self.search_btn.setEnabled(True)
            self.search_btn.setText("🔍 Search")

    def _on_search_error(self, msg: str) -> None:
        """Handle a search error from the background worker."""
        QMessageBox.critical(
            self, "Search Error", f"Could not run search:\n\n{msg}"
        )
        self.results_label.setText("❌ Search failed")
        self.results_label.setStyleSheet("color: #cc0000; font-size: 9pt;")

    def _on_search_results(self, rows: list, truncated: bool) -> None:
        """Handle results returned from the background search worker."""
        # Rollback the main connection in case it's in an error state
        try:
            self.conn.rollback()
        except Exception as _e:
            logger.debug('Suppressed: %s', _e)
        try:
            rows = self._augment_rows_with_split_siblings(rows)
            grouped_rows = self._apply_split_search_grouping(rows)
            self.last_results = grouped_rows
            self._populate_table(grouped_rows)
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Display Error",
                f"Search succeeded but could not display results:\n\n{e}",
            )
            self.results_label.setText("❌ Display failed")
            self.results_label.setStyleSheet("color: #cc0000; font-size: 9pt;")
            return

        # Update status based on results
        if len(grouped_rows) == 0:
            self.results_label.setText(
                "No receipts found - try different filters"
            )
            self.results_label.setStyleSheet("color: #ff8800; font-size: 9pt;")
        elif truncated:
            self.results_label.setText(
                "⚠️ Showing first 2000 of 2000+ receipts — add filters to "
                "narrow"
            )
            self.results_label.setStyleSheet(
                "color: #cc6600; font-size: 9pt; font-weight: bold;"
            )
        else:
            self.results_label.setText(
                f"✓ Found {len(grouped_rows)} receipt"
                f"{'s' if len(grouped_rows) != 1 else ''}"
            )
            self.results_label.setStyleSheet(
                "color: #00aa00; font-size: 9pt; font-weight: bold;"
            )

    def _augment_rows_with_split_siblings(self, rows: list[tuple]) -> list[tuple]:
        """Ensure split siblings are present even when date/amount filters clipped them."""
        if not rows:
            return rows

        split_group_ids = {
            row[13]
            for row in rows
            if len(row) > 13 and row[13] is not None
        }
        if not split_group_ids:
            return rows

        existing_ids = {
            int(row[0])
            for row in rows
            if row and row[0] is not None and str(row[0]).isdigit()
        }

        try:
            cur = self.conn.cursor()
            placeholders = ", ".join(["%s"] * len(split_group_ids))
            cur.execute(
                f"""
                SELECT r.receipt_id, r.receipt_date, r.vendor_name,
                       r.gross_amount,
                       CASE
                           WHEN coa.account_code IS NOT NULL THEN
                               coa.account_code || ' — ' || LEFT(coa.account_name, 60)
                           ELSE COALESCE(
                               r.gl_account_code,
                               r.mapped_expense_account_id::text,
                               r.category,
                               ''
                           )
                       END AS gl_name,
                       COALESCE(bt_link.transaction_id, r.banking_transaction_id)
                           AS banking_transaction_id,
                       CASE
                           WHEN COALESCE(
                               NULLIF(bt_id.check_number, ''),
                               NULLIF(bt_link.check_number, '')
                           ) IS NOT NULL THEN 'Cheque'
                           WHEN COALESCE(
                               bt_link.credit_amount, bt_id.credit_amount, 0
                           ) > 0 THEN 'Credit'
                           WHEN COALESCE(
                               bt_link.debit_amount, bt_id.debit_amount, 0
                           ) > 0 THEN 'Debit'
                           ELSE ''
                       END AS banking_type,
                       COALESCE(r.reserve_number, '') AS charter_num,
                       COALESCE(r.description, '') AS description,
                       COALESCE(r.payment_method, '') AS payment_method,
                       COALESCE(r.created_from_banking, false)
                           AS created_from_banking,
                       r.vehicle_id,
                       r.fuel_amount,
                       r.split_group_id,
                       COALESCE(r.is_split_receipt, false) AS is_split_receipt,
                       COALESCE(r.split_group_total, r.gross_amount)
                           AS split_search_total,
                       COALESCE(r.is_nsf, false) AS is_nsf,
                       COALESCE(r.is_paper_verified, false) AS is_paper_verified
                FROM receipts r
                LEFT JOIN chart_of_accounts coa
                    ON coa.account_code = r.gl_account_code
                LEFT JOIN banking_transactions bt_id
                    ON bt_id.transaction_id = r.banking_transaction_id
                LEFT JOIN LATERAL (
                    SELECT bt.transaction_id, bt.debit_amount,
                           bt.credit_amount, bt.check_number
                    FROM banking_transactions bt
                    WHERE bt.receipt_id = r.receipt_id
                    ORDER BY bt.transaction_date DESC, bt.transaction_id DESC
                    LIMIT 1
                ) bt_link ON true
                WHERE r.split_group_id IN ({placeholders})
                ORDER BY r.split_group_id DESC, r.receipt_id DESC
                """,
                list(split_group_ids),
            )
            sibling_rows = cur.fetchall() or []
            cur.close()
        except Exception:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            return rows

        merged = list(rows)
        for sibling in sibling_rows:
            sid = sibling[0] if sibling else None
            if sid is None:
                continue
            try:
                sid_int = int(sid)
            except Exception:
                continue
            if sid_int in existing_ids:
                continue
            merged.append(sibling)
            existing_ids.add(sid_int)

        return merged

    def _apply_split_search_grouping(self, rows: list[tuple]) -> list[tuple]:
        """Group split receipt rows so they can be shown collapsed or expanded
        together.
        """
        if not rows:
            return rows

        show_linked = bool(
            getattr(self, "show_linked_splits_chk", None)
            and self.show_linked_splits_chk.isChecked()
        )

        grouped: dict[str, list[tuple]] = {}
        ordered_keys: list[str] = []

        for row in rows:
            split_group_id = row[13] if len(row) > 13 else None
            is_split = bool(row[14]) if len(row) > 14 else False
            key = (
                f"split:{split_group_id}"
                if is_split and split_group_id
                else f"single:{row[0]}"
            )
            if key not in grouped:
                grouped[key] = []
                ordered_keys.append(key)
            grouped[key].append(row)

        if show_linked:
            expanded: list[tuple] = []
            for key in ordered_keys:
                members = grouped[key]
                members = sorted(
                    members,
                    key=lambda m: int(m[0]) if str(m[0]).isdigit() else 0,
                )
                expanded.extend(members)
            return expanded

        collapsed: list[tuple] = []
        for key in ordered_keys:
            members = grouped[key]
            first = members[0]
            if len(members) == 1 or not key.startswith("split:"):
                collapsed.append(first)
                continue

            representative = list(first)
            split_total = (
                representative[14] if len(representative) > 14 else None
            )
            try:
                if split_total is not None:
                    representative[3] = float(split_total)
            except (TypeError, ValueError):
                pass

            gl_text = (representative[4] or "").strip()
            representative[4] = (
                f"✂️ SPLIT ({len(members)} lines) — {gl_text}"
                if gl_text
                else f"✂️ SPLIT ({len(members)} lines)"
            )
            collapsed.append(tuple(representative))

        return collapsed

    def _populate_table(self, rows: list[tuple]) -> None:
        # Block selection signals while populating to prevent premature form
        # clearing
        self.results_table.blockSignals(True)
        # Disable sorting during population to prevent mid-insert re-sorting
        self.results_table.setSortingEnabled(False)
        # Suppress repaints until the full batch is loaded
        self.results_table.setUpdatesEnabled(False)
        # Block model signals (dataChanged/rowsInserted) to prevent 16,000
        # signal
        # cascades from setBackground() calls — the single repaint at the end
        # is enough
        self.results_table.model().blockSignals(True)
        try:
            # One-time column/header setup (guard so it's a no-op after first
            # load)
            if self.results_table.columnCount() != 10:
                self.results_table.setColumnCount(10)
                self.results_table.setHorizontalHeaderLabels(
                    [
                        "ID",
                        "Date",
                        "Vendor",
                        "Amount",
                        "GL/Category",
                        "Banking ID",
                        "Banking Type",
                        "Payment Type",
                        "Charter",
                        "Paper ✓",
                    ]
                )
                header: QHeaderView = self.results_table.horizontalHeader()
                header.setSectionResizeMode(
                    0, QHeaderView.ResizeMode.ResizeToContents
                )
                header.setSectionResizeMode(
                    1, QHeaderView.ResizeMode.ResizeToContents
                )
                header.setSectionResizeMode(
                    2, QHeaderView.ResizeMode.Interactive
                )
                header.resizeSection(2, 150)
                header.setSectionResizeMode(
                    3, QHeaderView.ResizeMode.ResizeToContents
                )
                header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
                header.setSectionResizeMode(
                    5, QHeaderView.ResizeMode.ResizeToContents
                )
                header.setSectionResizeMode(
                    6, QHeaderView.ResizeMode.ResizeToContents
                )
                header.setSectionResizeMode(
                    7, QHeaderView.ResizeMode.ResizeToContents
                )
                header.setSectionResizeMode(
                    8, QHeaderView.ResizeMode.ResizeToContents
                )
                header.setSectionResizeMode(
                    9, QHeaderView.ResizeMode.ResizeToContents
                )

            self.results_table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                # Expect at least 7 columns; optionally 9 if
                # description/payment_method provided, and now 11 with
                # vehicle_id and fuel_amount
                (
                    rid,
                    rdate,
                    vendor,
                    amount,
                    gl_name,
                    banking_id,
                    banking_type,
                    charter_num,
                ) = row[:8]
                is_nsf_pair = bool(row[16]) if len(row) > 16 else False
                is_paper_verified = bool(row[17]) if len(row) > 17 else False
                self.results_table.setItem(r, 0, QTableWidgetItem(str(rid)))
                self.results_table.setItem(r, 1, QTableWidgetItem(str(rdate)))
                vendor_item = QTableWidgetItem(vendor or "")
                # Store summary data for compact delegate
                desc = row[8] if len(row) > 8 else ""
                paym = row[9] if len(row) > 9 else ""
                created_from_banking = (
                    bool(row[10]) if len(row) > 10 else False
                )
                vehicle_id = row[11] if len(row) > 11 else None
                fuel_amount = row[12] if len(row) > 12 else None
                summary = {
                    "date": str(rdate),
                    "vendor": vendor or "",
                    "amount": float(amount) if amount is not None else None,
                    "gl": gl_name or "",
                    "description": desc or "",
                    "banking_id": banking_id,
                    "banking_type": banking_type or "",
                    "charter": charter_num or "",
                    "payment_method": paym or "",
                    "created_from_banking": created_from_banking,
                    "vehicle_id": vehicle_id,
                    "fuel_amount": float(fuel_amount) if fuel_amount else None,
                    "is_paper_verified": is_paper_verified,
                }
                vendor_item.setData(Qt.ItemDataRole.UserRole, summary)
                self.results_table.setItem(r, 2, vendor_item)
                amt_value = float(amount) if amount is not None else 0.0
                amt_item = NumericSortItem(
                    f"${amount: ,.2f} " if amount is not None else "$0.00",
                    amt_value,
                )
                amt_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self.results_table.setItem(r, 3, amt_item)
                self.results_table.setItem(
                    r, 4, QTableWidgetItem(gl_name or "")
                )
                # Banking ID and Charter
                self.results_table.setItem(
                    r,
                    5,
                    QTableWidgetItem(
                        str(banking_id) if banking_id is not None else ""
                    ),
                )
                self.results_table.setItem(
                    r, 6, QTableWidgetItem(banking_type or "")
                )
                self.results_table.setItem(r, 7, QTableWidgetItem(paym or ""))
                self.results_table.setItem(
                    r, 8, QTableWidgetItem(charter_num or "")
                )
                paper_item = QTableWidgetItem(
                    "✅" if is_paper_verified else ""
                )
                paper_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter
                    | Qt.AlignmentFlag.AlignVCenter
                )
                self.results_table.setItem(r, 9, paper_item)

                # ===== COLOR CODING FOR ROW =====
                # Determine row color based on status and payment method
                row_color = None

                if created_from_banking:
                    # Imported from banking - light yellow
                    row_color = QColor(255, 255, 200)  # Light yellow
                elif banking_id is not None and banking_id != "":
                    # Matched to banking - light green
                    row_color = QColor(200, 255, 200)  # Light green
                elif charter_num:
                    # Linked to charter - light blue
                    row_color = QColor(200, 230, 255)  # Light blue
                elif paym:
                    paym_lower = paym.lower()
                    if paym_lower == "cash":
                        # Cash payment - light tan/peach
                        row_color = QColor(255, 228, 196)  # Light peach/tan
                    elif paym_lower in ("check", "cheque"):
                        # Cheque payment - light lavender/purple
                        row_color = QColor(230, 220, 255)  # Light lavender
                    elif paym_lower == "reimbursement" or (
                        desc
                        and (
                            "reimburse" in desc.lower()
                            or "reimbursement" in desc.lower()
                        )
                    ):
                        # Reimbursement - light orange/coral
                        row_color = QColor(255, 218, 185)  # Light coral/orange
                    elif paym_lower == "loan":
                        # Loan - light mint green
                        row_color = QColor(200, 255, 220)  # Light mint green
                    elif "gas rebate" in paym_lower or "fas" in paym_lower:
                        # FAS Gas Rebate - light cyan
                        row_color = QColor(200, 255, 255)  # Light cyan
                    elif "airline" in paym_lower or "special" in paym_lower:
                        # Special Airline Charge - light gold
                        row_color = QColor(255, 250, 205)  # Light gold
                    elif "adjustment" in paym_lower or "charter" in paym_lower:
                        # Charter Adjustment - light purple
                        row_color = QColor(230, 200, 255)  # Light purple
                    elif "surcharge" in paym_lower or "fuel" in paym_lower:
                        # Fuel Surcharge - light orange
                        row_color = QColor(255, 235, 205)  # Light orange
                    else:
                        # Other payment types - light pink/red
                        row_color = QColor(255, 220, 220)  # Light pink
                else:
                    # Unmatched - light pink/red
                    row_color = QColor(255, 220, 220)  # Light pink

                # NSF pair overrides row color with amber/orange so they stand
                # out
                if is_nsf_pair:
                    row_color = QColor(
                        255, 200, 100
                    )  # Amber — NSF pair (bounce/return)

                # Apply color to all cells in row
                if row_color:
                    for col in range(10):
                        item = self.results_table.item(r, col)
                        if item:
                            item.setBackground(row_color)

                # Adjust row heights if compact is enabled
                if (
                    getattr(self, "compact_toggle", None)
                    and self.compact_toggle.isChecked()
                ):
                    # Rough height for 4-line summary
                    self.results_table.setRowHeight(
                        r, 4 * self.results_table.fontMetrics().height() + 10
                    )
        finally:
            # Unblock model signals first, then widget signals
            self.results_table.model().blockSignals(False)
            # Re-enable signals after table is fully populated
            self.results_table.blockSignals(False)
            # Re-enable sorting so column headers are clickable
            self.results_table.setSortingEnabled(True)
            # Flush all buffered repaints at once (single full repaint)
            self.results_table.setUpdatesEnabled(True)
            # Only reset the add form if the user hasn't started filling it in
            if not self._is_add_form_dirty():
                self._clear_form()

    def _populate_form_from_selection(self) -> None:
        """Populate form fields from selected receipt row. Safe error "
        "handling."""

        try:
            selected = self.results_table.selectedItems()
            if not selected:
                self._clear_form()
                return
            row = selected[0].row()

            rid_item = self.results_table.item(row, 0)
            date_item = self.results_table.item(row, 1)
            vendor_item = self.results_table.item(row, 2)
            amt_item = self.results_table.item(row, 3)
            gl_item = self.results_table.item(row, 4)
            banking_item = self.results_table.item(row, 5)
            charter_item = self.results_table.item(row, 8)

            if not all([rid_item, date_item, vendor_item, amt_item, gl_item]):
                self._clear_form()
                return

            # Date field
            try:
                self.new_date.setDate(
                    QDate.fromString(date_item.text(), "yyyy-MM-dd")
                )
            except Exception:
                self.new_date.setDate(self._default_entry_date())

            # Vendor field - VendorLookupWidget uses set_vendor() not setText()
            vendor_text = vendor_item.text() or ""
            if hasattr(self, "new_vendor"):
                try:
                    if hasattr(self.new_vendor, "set_vendor"):
                        self.new_vendor.set_vendor(vendor_text)
                    else:
                        self.new_vendor.setText(vendor_text)
                except Exception as _e:
                    logger.debug('Suppressed: %s', _e)
            # Amount field
            if hasattr(self, "new_amount"):
                amt_cleaned = (
                    (amt_item.text() or "").replace("$", "").replace(",", "")
                )
                self.new_amount.setText(amt_cleaned)

            # Load description from vendor_item's UserRole data (from compact
            # delegate summary)
            try:
                summary_data = vendor_item.data(Qt.ItemDataRole.UserRole) or {}
                if hasattr(self, "new_desc"):
                    self.new_desc.setText(
                        summary_data.get("description", "") or ""
                    )
            except Exception:
                if hasattr(self, "new_desc"):
                    self.new_desc.setText("")

            # GL Code field
            try:
                if hasattr(self, "new_gl"):
                    self.new_gl.blockSignals(True)
                    try:
                        gl_text = gl_item.text() or ""
                        if isinstance(self.new_gl, QComboBox):
                            self.new_gl.setEditText(gl_text)
                        else:
                            self.new_gl.setText(gl_text)
                    finally:
                        self.new_gl.blockSignals(False)
                        self._toggle_conditional_fields()
            except Exception:
                if hasattr(self, "new_gl"):
                    if isinstance(self.new_gl, QComboBox):
                        self.new_gl.setEditText("")
                    else:
                        self.new_gl.setText("")

            # Banking Transaction ID field
            try:
                if hasattr(self, "new_banking_id"):
                    self.new_banking_id.setText(
                        banking_item.text() if banking_item else ""
                    )
            except Exception:
                if hasattr(self, "new_banking_id"):
                    self.new_banking_id.clear()

            # Charter/Reserve Number field
            try:
                if hasattr(self, "new_charter_input"):
                    self.new_charter_input.setText(
                        charter_item.text() if charter_item else ""
                    )
            except Exception:
                if hasattr(self, "new_charter_input"):
                    self.new_charter_input.clear()

            # Payment Method field - populate from summary data
            try:
                summary_data = vendor_item.data(Qt.ItemDataRole.UserRole) or {}
                if hasattr(self, "payment_method"):
                    payment_method_text = summary_data.get(
                        "payment_method", ""
                    )
                    idx = (
                        self.payment_method.findText(payment_method_text)
                        if payment_method_text
                        else -1
                    )
                    self.payment_method.setCurrentIndex(idx if idx >= 0 else 0)
            except Exception:
                if hasattr(self, "payment_method"):
                    self.payment_method.setCurrentIndex(0)

            # Populate vehicle_id and fuel_amount from summary data
            try:
                summary_data = vendor_item.data(Qt.ItemDataRole.UserRole) or {}
                vehicle_id = summary_data.get("vehicle_id")
                fuel_amount = summary_data.get("fuel_amount")

                # Ensure vehicles are loaded (lazy, first selection only)
                if (
                    hasattr(self, "new_vehicle_combo")
                    and not self._vehicles_loaded
                ):
                    self.new_vehicle_combo.clear()
                    self.new_vehicle_combo.addItem("", None)
                    self._load_vehicles_into_combo()
                    self._vehicles_loaded = True

                # Always clear first
                if hasattr(self, "fuel_liters"):
                    self.fuel_liters.setValue(0)
                if hasattr(self, "new_vehicle_combo"):
                    self.new_vehicle_combo.setCurrentIndex(0)

                # Populate if data exists
                if vehicle_id and hasattr(self, "new_vehicle_combo"):
                    for idx in range(self.new_vehicle_combo.count()):
                        if self.new_vehicle_combo.itemData(idx) == vehicle_id:
                            self.new_vehicle_combo.setCurrentIndex(idx)
                            break

                if (
                    fuel_amount is not None
                    and fuel_amount > 0
                    and hasattr(self, "fuel_liters")
                ):
                    self.fuel_liters.setValue(float(fuel_amount))

            except Exception:
                if hasattr(self, "new_vehicle_combo"):
                    self.new_vehicle_combo.setCurrentIndex(0)
                if hasattr(self, "fuel_liters"):
                    self.fuel_liters.setValue(0)

            # Populate reimbursement fields from linked employee_expenses row
            try:
                if hasattr(self, "reimbursement_amount_input"):
                    self.reimbursement_amount_input.clear()
                if hasattr(self, "reimbursement_payee_input"):
                    self.reimbursement_payee_input.clear()
                if hasattr(self, "reimbursed_via_combo"):
                    self.reimbursed_via_combo.setCurrentIndex(0)

                rid_val = int(rid_item.text()) if rid_item else None
                if rid_val:
                    cur_r = self.conn.cursor()
                    cur_r.execute(
                        """
                        SELECT reimbursed_amount, vendor_name,
                               reimbursement_status
                        FROM employee_expenses
                        WHERE receipt_id = %s
                        ORDER BY expense_id DESC
                        LIMIT 1
                        """,
                        (rid_val,),
                    )
                    exp_row = cur_r.fetchone()
                    cur_r.close()
                    if exp_row:
                        reimb_amt, payee_vendor, reimb_status = exp_row
                        if (
                            hasattr(self, "reimbursement_amount_input")
                            and reimb_amt is not None
                        ):
                            self.reimbursement_amount_input.setText(
                                f"{float(reimb_amt):.2f}"
                            )
                        if (
                            hasattr(self, "reimbursement_payee_input")
                            and payee_vendor
                        ):
                            self.reimbursement_payee_input.setText(
                                str(payee_vendor)
                            )
                        if (
                            hasattr(self, "reimbursed_via_combo")
                            and reimb_status
                        ):
                            via_text = (
                                "Pending"
                                if str(reimb_status).lower() == "pending"
                                else "Cash"
                            )
                            idx = self.reimbursed_via_combo.findText(via_text)
                            if idx >= 0:
                                self.reimbursed_via_combo.setCurrentIndex(idx)
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            # Enable limited update when writes are enabled and a row is
            # selected
            self.loaded_receipt_id = (
                int(rid_item.text())
                if rid_item and rid_item.text().isdigit()
                else None
            )
            if hasattr(self, "update_btn"):
                self.update_btn.setEnabled(
                    self.write_enabled and self.loaded_receipt_id is not None
                )
            if hasattr(self, "delete_btn"):
                self.delete_btn.setEnabled(
                    self.write_enabled and self.loaded_receipt_id is not None
                )
        except Exception:
            try:
                self._clear_form()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
    def _is_add_form_dirty(self) -> bool:
        """Return True if the user has started filling in the add-receipt form.
        Used to prevent background search completions from wiping mid-entry
        data.
        """
        try:
            from decimal import Decimal as _D

            if self.new_amount.value() != _D("0"):
                return True
            vendor = getattr(self.new_vendor, "get_vendor", lambda: "")() or ""
            if vendor.strip():
                return True
            if (self.new_desc.text() or "").strip():
                return True
        except Exception as _e:
            logger.debug('Suppressed: %s', _e)
        return False

    def _default_entry_date(self) -> QDate:
        """Return the default date for new receipt entry.

        Uses Jan 1 of the active year when exactly one year is selected,
        so entering receipts for a historical year doesn't accidentally
        default to the current calendar year.
        """
        if hasattr(self, "selected_years") and len(self.selected_years) == 1:
            year = next(iter(self.selected_years))
            return QDate(year, 1, 1)
        return QDate.currentDate()

    def _clear_form(self) -> None:
        """Clear all form fields and reset to defaults."""
        # Preserve selected years and date range before clearing
        preserved_years = (
            self.selected_years.copy()
            if hasattr(self, "selected_years")
            else set()
        )
        preserved_date_from = (
            self.date_from.date() if hasattr(self, "date_from") else None
        )
        preserved_date_to = (
            self.date_to.date() if hasattr(self, "date_to") else None
        )

        self.new_date.setDate(self._default_entry_date())
        self.new_vendor.clear()
        self.new_amount.clear()
        self.new_desc.clear()
        self.new_gl.setCurrentIndex(-1)

        # CRITICAL: Always clear banking_id to prevent leftover values
        if hasattr(self, "new_banking_id"):
            self.new_banking_id.clear()

        if hasattr(self, "new_charter_input"):
            self.new_charter_input.clear()

        self.new_vehicle_combo.setCurrentIndex(0)
        self.new_driver_combo.setCurrentIndex(0)
        self.payment_method.setCurrentIndex(0)
        self.fuel_liters.setValue(0)
        if hasattr(self, "reimbursement_amount_input"):
            self.reimbursement_amount_input.clear()
        if hasattr(self, "reimbursement_payee_input"):
            self.reimbursement_payee_input.clear()
        if hasattr(self, "reimbursed_via_combo"):
            self.reimbursed_via_combo.setCurrentIndex(0)

        if hasattr(self, "new_odometer"):
            self.new_odometer.setValue(0)

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

        # Restore selected years
        if preserved_years:
            self.selected_years = preserved_years
            if hasattr(self, "_update_year_button_styles"):
                self._update_year_button_styles()

        # Restore date range
        if preserved_date_from and hasattr(self, "date_from"):
            self.date_from.setDate(preserved_date_from)
        if preserved_date_to and hasattr(self, "date_to"):
            self.date_to.setDate(preserved_date_to)

        # Hide conditional fields when form is cleared
        self._toggle_conditional_fields()

        # Re-apply sticky defaults AFTER all clears (paintbrush mode)
        self._apply_sticky_defaults()

    def _add_receipt(self) -> None:
        if not self.write_enabled:
            QMessageBox.information(
                self,
                "Writes disabled",
                "Set RECEIPT_WIDGET_WRITE_ENABLED=true to enable adding "
                "receipts.",
            )
            return
        try:
            date = self.new_date.date().toPyDate()
            vendor = (self.new_vendor.get_vendor() or "").strip()
            source_reference = (
                self.new_banking_id.text() or ""
            ).strip()  # source_reference now stored in banking_id field
            amount = self.new_amount.value()
            desc = (self.new_desc.text() or "").strip()
            gl_text = (
                (self.new_gl.currentText() or "").strip()
                if isinstance(self.new_gl, QComboBox)
                else (self.new_gl.text() or "").strip()
            )
            gl_code = None
            if gl_text:
                gl_code = gl_text.split("—")[0].split("-")[0].strip()
            banking_id_text = (self.new_banking_id.text() or "").strip()
            banking_id = (
                int(banking_id_text) if banking_id_text.isdigit() else None
            )
            vehicle_id = (
                self.new_vehicle_combo.currentData()
                if self.new_vehicle_combo.currentData()
                else None
            )
            driver_id = (
                self.new_driver_combo.currentData()
                if self.new_driver_combo.currentData()
                else None
            )
            reserve_number = (
                self.new_charter_input.text() or ""
            ).strip() or None
            reimbursement_amount_raw = (
                self.reimbursement_amount_input.value()
                if hasattr(self, "reimbursement_amount_input")
                else Decimal("0")
            )
            reimbursement_amount = float(reimbursement_amount_raw or 0)
            if reimbursement_amount <= 0:
                reimbursement_amount = float(amount)
            reimbursement_payee = (
                (self.reimbursement_payee_input.text() or "").strip()
                if hasattr(self, "reimbursement_payee_input")
                else ""
            )
            reimbursed_via = (
                self.reimbursed_via_combo.currentText()
                if hasattr(self, "reimbursed_via_combo")
                else "Pending"
            )

            # Calculate GST: either use override value or auto-calculate (5%
            # included in gross)
            if self.gst_override_enable.isChecked():
                gst_amount = float(self.gst_override_input.value())
            else:
                # Auto-calculate: 5% GST included in gross amount
                gst_amount = (
                    round(float(amount) * 0.05 / 1.05, 2)
                    if amount > 0
                    else 0.0
                )

            payment_method = self.payment_method.currentText()
            is_reimbursement = payment_method.lower() == "reimbursement"

            if is_reimbursement and not driver_id:
                QMessageBox.warning(
                    self,
                    "Missing reimbursee",
                    "For reimbursement receipts, select an employee in "
                    "Driver Reimburse. Payee is optional notes text.",
                )
                return

            if self._looks_like_david_reimbursement(
                vendor, desc, payment_method, gl_text
            ):
                gl_code = DAVID_REIMBURSEMENT_GL_CODE

            if not vendor or amount <= 0:
                QMessageBox.warning(
                    self,
                    "Missing data",
                    "Vendor and positive Amount are required.",
                )
                return

            # Get odometer reading value
            odometer_reading = (
                self.new_odometer.value()
                if hasattr(self, "new_odometer")
                else 0
            )

            # Validate GL code - block revenue codes (4000-4999)
            if gl_text:
                try:
                    # Extract GL code number
                    gl_code = gl_text.split()[0].split("—")[0].strip()
                    if gl_code.isdigit() and 4000 <= int(gl_code) <= 4999:
                        QMessageBox.critical(
                            self,
                            "Invalid GL Code",
                            f"❌ REVENUE GL codes (4000-4999) cannot be used "
                            f"in Receipts!\n\n"
                            f"You selected: {gl_text}\n\n"
                            f"RECEIPTS are for EXPENSES only (GL codes 5000+, "
                            f"6000+).\n\n"
                            f"Charter payments/revenue are tracked in the "
                            f"Payments/Charters table.\n\n"
                            f"If this is a charter payment deposit, record it "
                            f"in Charter Management instead.",
                        )
                        return
                except Exception as gl_ex:
                    # Log GL validation error but don't fail the operation
                    import traceback

                    logger.debug(
                        f"⚠️ GL code validation error: "
                        f"{gl_ex}\n{traceback.format_exc()}"
                    )

            # Duplicate warning: ±$1, ±7 days by vendor - show details
            duplicates = self._find_potential_duplicates(vendor, date, amount)
            if duplicates:
                # Build detailed message showing all duplicates
                msg = (
                    f"Found {len(duplicates)} potential duplicate"
                    " receipt(s):\n\n"
                )
                for (
                    rid,
                    rdate,
                    rvend,
                    ramt,
                    rdesc,
                    backward_date,
                ) in duplicates:
                    msg += (
                        f"• Receipt #{rid}: {rdate} | {rvend} | ${ramt:.2f}\n"
                    )
                    if rdesc:
                        msg += f"  Description: {rdesc[:60]}\n"
                    if backward_date:
                        msg += (
                            "  ⚠️ WARNING: Banking date appears to have "
                            "swapped MM/DD!\n"
                        )
                    msg += "\n"
                msg += (
                    "Do you want to proceed with adding this receipt anyway?"
                )

                choice = QMessageBox.question(
                    self,
                    "Potential Duplicates Found",
                    msg,
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if choice != QMessageBox.StandardButton.Yes:
                    return

            cur = self.conn.cursor()
            cols = [
                "receipt_date",
                "vendor_name",
                "gross_amount",
                "description",
                "source_reference",
            ]
            vals = [
                date,
                vendor,
                float(amount),
                desc or None,
                source_reference or None,
            ]
            if "vehicle_id" in self.receipts_columns:
                cols.append("vehicle_id")
                vals.append(vehicle_id)
            if "employee_id" in self.receipts_columns:
                cols.append("employee_id")
                vals.append(driver_id)
            if "reserve_number" in self.receipts_columns:
                cols.append("reserve_number")
                vals.append(reserve_number)
            if self.fuel_column:
                cols.append(self.fuel_column)
                vals.append(float(self.fuel_liters.value()))
            if "gst_amount" in self.receipts_columns:
                cols.append("gst_amount")
                vals.append(gst_amount)
            if "payment_method" in self.receipts_columns:
                cols.append("payment_method")
                vals.append(payment_method)
            if "is_driver_reimbursement" in self.receipts_columns:
                cols.append("is_driver_reimbursement")
                vals.append(is_reimbursement)
            if "reimbursed_via" in self.receipts_columns:
                cols.append("reimbursed_via")
                vals.append(reimbursed_via if is_reimbursement else None)
            if "reimbursement_amount" in self.receipts_columns:
                cols.append("reimbursement_amount")
                vals.append(
                    reimbursement_amount if is_reimbursement else None
                )
            if "gl_account_code" in self.receipts_columns:
                cols.append("gl_account_code")
                vals.append(gl_code or None)
            if "banking_transaction_id" in self.receipts_columns:
                cols.append("banking_transaction_id")
                vals.append(banking_id)
            if "odometer_reading" in self.receipts_columns:
                cols.append("odometer_reading")
                vals.append(odometer_reading if odometer_reading > 0 else None)

            # Mark verified since user is manually adding this receipt
            cols.append("verified_by_edit")
            vals.append(True)
            cols.append("verified_by_user")
            vals.append("desktop_app")
            cols.append("is_paper_verified")
            vals.append(True)

            cols = self._validated_receipt_columns(cols)
            placeholders = ", ".join(["%s"] * len(vals))
            sql = (
                f"INSERT INTO receipts ({', '.join(cols)}, verified_at) "
                f"VALUES ({placeholders}, NOW()) "
                f"RETURNING receipt_id"
            )
            params = vals
            row = None  # Initialize row to prevent UnboundLocalError
            try:
                cur.execute(sql, params)
                row = cur.fetchone()
                self.conn.commit()
                cur.close()
            except Exception as sql_err:
                cur.close()
                self.conn.rollback()
                logger.debug(f"DEBUG: SQL Error - {sql_err}")
                logger.debug(f"DEBUG: SQL - {sql}")
                logger.debug(f"DEBUG: Params - {params}")
                raise

            if row and row[0]:
                rid = row[0]
                if is_reimbursement:
                    self._upsert_employee_reimbursement_expense(
                        receipt_id=rid,
                        employee_id=driver_id,
                        expense_date=date,
                        gross_amount=float(amount),
                        reimbursed_amount=float(reimbursement_amount),
                        vendor_name=vendor,
                        payee_name=reimbursement_payee,
                        description=desc,
                        reimbursed_via=reimbursed_via,
                    )
                else:
                    self._clear_employee_reimbursement_expense(rid)
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
                            "vehicle_id": vehicle_id,
                            "employee_id": driver_id,
                            "reserve_number": reserve_number,
                            "fuel_amount": (
                                float(self.fuel_liters.value())
                                if self.fuel_column
                                else None
                            ),
                            "gst_amount": gst_amount,
                            "payment_method": payment_method,
                            "odometer_reading": (
                                odometer_reading
                                if odometer_reading > 0
                                else None
                            ),
                        },
                    )
                except Exception as _e:
                    logger.debug('Suppressed: %s', _e)
                QMessageBox.information(
                    self,
                    "Added",
                    f"Receipt #{rid} added (click Search to refresh table).",
                )
                self._clear_form()
                # PERFORMANCE FIX: Don't auto-refresh entire result set after
                # single ADD
                # (mirrors the same fix on _update_receipt — avoids slow All-
                # Receipts queries)
                # User can click Search button to manually refresh if needed.
                # self._do_search()
                # Set focus to amount field for next receipt entry
                QTimer.singleShot(100, lambda: self.amount_filter.setFocus())
                QTimer.singleShot(150, lambda: self.amount_filter.selectAll())
            else:
                QMessageBox.information(
                    self,
                    "Duplicate skipped",
                    "Matching receipt already exists; no insert performed.",
                )
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            # Check if it's a sequence/primary key issue and try to fix it
            error_msg = str(e).lower()
            if "duplicate key" in error_msg and "receipts_pkey" in error_msg:
                try:
                    # Fix sequence and retry
                    fix_cur = self.conn.cursor()
                    fix_cur.execute(
                        "SELECT setval("
                        "pg_get_serial_sequence('receipts', 'receipt_id'), "
                        "COALESCE((SELECT MAX(receipt_id) FROM receipts), 1), "
                        "true)"
                    )
                    self.conn.commit()
                    fix_cur.close()

                    # Retry the insert
                    retry_cur = self.conn.cursor()
                    retry_cur.execute(sql, params)
                    retry_row = retry_cur.fetchone()
                    self.conn.commit()
                    retry_cur.close()

                    if retry_row and retry_row[0]:
                        QMessageBox.information(
                            self,
                            "Added",
                            f"Receipt #{retry_row[0]} added (sequence "
                            f"auto-fixed, click Search to refresh).",
                        )
                        self._clear_form()
                        # PERFORMANCE FIX: Don't auto-refresh — see above
                        # self._do_search()
                        return
                except Exception as retry_err:
                    QMessageBox.critical(
                        self,
                        "Add Error",
                        f"Could not add receipt even after fixing "
                        f"sequence:\n\n{retry_err}",
                    )
                    return

            QMessageBox.critical(
                self, "Add Error", f"Could not add receipt:\n\n{e}"
            )

    def _update_receipt(self) -> None:
        if not self.write_enabled:
            QMessageBox.information(
                self,
                "Writes disabled",
                "Set RECEIPT_WIDGET_WRITE_ENABLED=true to enable updates.",
            )
            return
        rid = getattr(self, "loaded_receipt_id", None)
        if not rid:
            QMessageBox.information(
                self,
                "No selection",
                "Select a receipt from the table to update.",
            )
            return
        try:
            # Clear any failed transaction state before starting a new update.
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            # Snapshot BEFORE values for audit (limited to fields we may
            # change)
            before = {}
            try:
                cur_b = self.conn.cursor()
                before_fields = [
                    "receipt_date",
                    "vendor_name",
                    "gross_amount",
                    "description",
                    "vehicle_id",
                    "employee_id",
                    "reserve_number",
                ]
                if self.fuel_column:
                    before_fields.append(self.fuel_column)
                before_fields.extend(["gst_amount", "payment_method"])
                before_fields = self._validated_receipt_columns(before_fields)
                cur_b.execute(
                    f"SELECT {', '.join(before_fields)} FROM receipts WHERE "
                    f"receipt_id = %s",
                    (rid,),
                )
                row_b = cur_b.fetchone()
                cur_b.close()
                if row_b:
                    keys = [
                        "receipt_date",
                        "vendor_name",
                        "gross_amount",
                        "description",
                        "vehicle_id",
                        "employee_id",
                        "reserve_number",
                    ]
                    if self.fuel_column:
                        keys.append("fuel_amount")
                    keys.extend(["gst_amount", "payment_method"])
                    before = {k: row_b[i] for i, k in enumerate(keys)}
            except Exception:
                before = {}

            # Get form values
            date = self.new_date.date().toPyDate()
            vendor = (self.new_vendor.get_vendor() or "").strip()
            amount = (
                self.new_amount.value()
            )  # CurrencyInput has value() method
            desc = (self.new_desc.text() or "").strip()
            gl_text = (
                (self.new_gl.currentText() or "").strip()
                if isinstance(self.new_gl, QComboBox)
                else (self.new_gl.text() or "").strip()
            )
            gl_code = None
            if gl_text:
                gl_code = gl_text.split("—")[0].split("-")[0].strip()
            banking_id_text = (self.new_banking_id.text() or "").strip()
            banking_id = (
                int(banking_id_text) if banking_id_text.isdigit() else None
            )
            vehicle_id = (
                self.new_vehicle_combo.currentData()
                if self.new_vehicle_combo.currentData()
                else None
            )
            driver_id = (
                self.new_driver_combo.currentData()
                if self.new_driver_combo.currentData()
                else None
            )
            reserve_number = (
                self.new_charter_input.text() or ""
            ).strip() or None
            fuel_liters = float(self.fuel_liters.value())
            reimbursement_amount_raw = (
                self.reimbursement_amount_input.value()
                if hasattr(self, "reimbursement_amount_input")
                else Decimal("0")
            )
            reimbursement_amount = float(reimbursement_amount_raw or 0)
            if reimbursement_amount <= 0:
                reimbursement_amount = float(amount)
            reimbursement_payee = (
                (self.reimbursement_payee_input.text() or "").strip()
                if hasattr(self, "reimbursement_payee_input")
                else ""
            )
            reimbursed_via = (
                self.reimbursed_via_combo.currentText()
                if hasattr(self, "reimbursed_via_combo")
                else "Pending"
            )

            # Calculate GST: either use override value or auto-calculate (5%
            # included in gross)
            if self.gst_override_enable.isChecked():
                gst_amount = float(self.gst_override_input.value())
            else:
                # Auto-calculate: 5% GST included in gross amount
                gst_amount = (
                    round(float(amount) * 0.05 / 1.05, 2)
                    if amount > 0
                    else 0.0
                )

            payment_method = self.payment_method.currentText()
            is_reimbursement = payment_method.lower() == "reimbursement"

            if is_reimbursement and not driver_id:
                QMessageBox.warning(
                    self,
                    "Missing reimbursee",
                    "For reimbursement receipts, select an employee in "
                    "Driver Reimburse. Payee is optional notes text.",
                )
                return

            # Get odometer reading value
            odometer_reading = (
                self.new_odometer.value()
                if hasattr(self, "new_odometer")
                else 0
            )

            cur = self.conn.cursor()
            sets = [
                "receipt_date = %s",
                "vendor_name = %s",
                "gross_amount = %s",
                "description = %s",
            ]
            params = [date, vendor, float(amount), desc or None]
            if "vehicle_id" in self.receipts_columns:
                sets.append("vehicle_id = %s")
                params.append(vehicle_id)
            if "employee_id" in self.receipts_columns:
                sets.append("employee_id = %s")
                params.append(driver_id)
            if "reserve_number" in self.receipts_columns:
                sets.append("reserve_number = %s")
                params.append(reserve_number)
            if self.fuel_column:
                sets.append(f"{self.fuel_column} = %s")
                params.append(fuel_liters)
            if "gst_amount" in self.receipts_columns:
                sets.append("gst_amount = %s")
                params.append(gst_amount)
            if "payment_method" in self.receipts_columns:
                sets.append("payment_method = %s")
                params.append(payment_method)
            if "is_driver_reimbursement" in self.receipts_columns:
                sets.append("is_driver_reimbursement = %s")
                params.append(is_reimbursement)
            if "reimbursed_via" in self.receipts_columns:
                sets.append("reimbursed_via = %s")
                params.append(reimbursed_via if is_reimbursement else None)
            if "reimbursement_amount" in self.receipts_columns:
                sets.append("reimbursement_amount = %s")
                params.append(
                    reimbursement_amount if is_reimbursement else None
                )
            if "gl_account_code" in self.receipts_columns:
                sets.append("gl_account_code = %s")
                params.append(gl_code or None)
            if "banking_transaction_id" in self.receipts_columns:
                sets.append("banking_transaction_id = %s")
                params.append(banking_id)
            if "odometer_reading" in self.receipts_columns:
                sets.append("odometer_reading = %s")
                params.append(
                    odometer_reading if odometer_reading > 0 else None
                )

            # Always mark verified when manually updated
            sets.append("verified_by_edit = TRUE")
            sets.append("verified_at = NOW()")
            sets.append("verified_by_user = 'desktop_app'")
            sets.append("updated_at = NOW()")
            sets.append("is_paper_verified = TRUE")

            set_columns = [s.split(" = ")[0] for s in sets]
            self._validated_receipt_columns(set_columns)
            sql = f"UPDATE receipts SET {', '.join(sets)} WHERE receipt_id = %s"
            params.append(rid)
            cur.execute(sql, params)
            self.conn.commit()
            cur.close()
            if is_reimbursement:
                self._upsert_employee_reimbursement_expense(
                    receipt_id=rid,
                    employee_id=driver_id,
                    expense_date=date,
                    gross_amount=float(amount),
                    reimbursed_amount=float(reimbursement_amount),
                    vendor_name=vendor,
                    payee_name=reimbursement_payee,
                    description=desc,
                    reimbursed_via=reimbursed_via,
                )
            else:
                self._clear_employee_reimbursement_expense(rid)
            try:
                after = {
                    "receipt_date": date,
                    "vendor_name": vendor,
                    "gross_amount": float(amount),
                    "description": desc or None,
                    "vehicle_id": vehicle_id,
                    "employee_id": driver_id,
                    "reserve_number": reserve_number,
                    "fuel_amount": fuel_liters if self.fuel_column else None,
                    "gst_amount": gst_amount,
                    "payment_method": payment_method,
                    "odometer_reading": (
                        odometer_reading if odometer_reading > 0 else None
                    ),
                }
                self._audit_log(
                    action="update",
                    receipt_id=rid,
                    details={"before": before, "after": after},
                )
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.information(
                self,
                "Updated",
                f"Receipt #{rid} updated (click Search to refresh table).",
            )
            # Clear form after update and set focus to amount for next entry
            self._clear_form()
            QTimer.singleShot(100, lambda: self.amount_filter.setFocus())
            QTimer.singleShot(150, lambda: self.amount_filter.selectAll())
            # PERFORMANCE FIX: Don't auto-refresh entire result set after
            # single UPDATE
            # This was causing 30-second delays when many receipts are filtered
            # User can click Search button to manually refresh if needed
            # self._do_search()
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.critical(
                self,
                "Update Error",
                f"Could not update receipt #{rid}:\n\n{e}",
            )

    def _delete_selected_receipts(self) -> None:
        """Delete selected receipt(s) from database."""
        if not self.write_enabled:
            QMessageBox.information(
                self,
                "Writes disabled",
                "Set RECEIPT_WIDGET_WRITE_ENABLED=true to enable deletes.",
            )
            return

        rid = getattr(self, "loaded_receipt_id", None)
        if not rid:
            QMessageBox.warning(
                self,
                "No Selection",
                "Select a receipt from the table to delete.",
            )
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete Receipt #{rid}?\n\nThis will also remove any banking "
            f"matches.\nThis cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            cur = self.conn.cursor()

            # Step 1: Try to delete from banking_receipt_matching_ledger if it
            # exists
            try:
                cur.execute(
                    "DELETE FROM banking_receipt_matching_ledger WHERE "
                    "receipt_id = %s",
                    (rid,),
                )
                self.conn.commit()
            except Exception as e1:
                self.conn.rollback()
                logger.debug(
                    f"  Note: Could not delete from "
                    f"banking_receipt_matching_ledger: {e1}"
                )

            # Step 2: Clear banking_transaction links
            try:
                cur.execute(
                    "UPDATE banking_transactions SET receipt_id = NULL WHERE "
                    "receipt_id = %s",
                    (rid,),
                )
                self.conn.commit()
            except Exception as e2:
                self.conn.rollback()
                logger.debug(
                    f"  Note: Could not clear receipt_id in "
                    f"banking_transactions: {e2}"
                )

            try:
                cur.execute(
                    "UPDATE banking_transactions SET reconciled_receipt_id = "
                    "NULL WHERE reconciled_receipt_id = %s",
                    (rid,),
                )
                self.conn.commit()
            except Exception as e3:
                self.conn.rollback()
                logger.debug(
                    f"  Note: Could not clear reconciled_receipt_id in "
                    f"banking_transactions: {e3}"
                )

            # Step 2b: Clear linked employee reimbursement rows
            try:
                cur.execute(
                    "DELETE FROM employee_expenses WHERE receipt_id = %s",
                    (rid,),
                )
                self.conn.commit()
            except Exception as e4:
                self.conn.rollback()
                logger.debug(
                    "  Note: Could not clear employee_expenses links: "
                    f"{e4}"
                )

            # Step 3: Delete the receipt itself
            cur.execute("DELETE FROM receipts WHERE receipt_id = %s", (rid,))
            self.conn.commit()
            cur.close()

            # Audit log
            try:
                self._audit_log(
                    action="delete", receipt_id=rid, details={"deleted": True}
                )
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.information(
                self, "Deleted", f"✅ Receipt #{rid} deleted."
            )
            self._clear_form()
            self._do_search()

        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.critical(
                self,
                "Delete Error",
                f"Could not delete receipt #{rid}:\n\n{e}",
            )

    def _clear_employee_reimbursement_expense(self, receipt_id) -> None:
        """Remove linked reimbursement rows for this receipt."""
        if not receipt_id:
            return
        try:
            cur = self.conn.cursor()
            cur.execute(
                "DELETE FROM employee_expenses WHERE receipt_id = %s",
                (receipt_id,),
            )
            self.conn.commit()
            cur.close()
        except Exception:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
    def _upsert_employee_reimbursement_expense(
        self,
        receipt_id,
        employee_id,
        expense_date,
        gross_amount,
        reimbursed_amount,
        vendor_name,
        payee_name,
        description,
        reimbursed_via,
    ) -> None:
        """Sync reimbursement receipt info into employee_expenses."""
        if not receipt_id:
            return

        if not employee_id:
            self._clear_employee_reimbursement_expense(receipt_id)
            return

        reimbursed_now = (reimbursed_via or "").strip().lower() != "pending"
        reimbursement_status = "reimbursed" if reimbursed_now else "pending"

        payee_text = (payee_name or "").strip()
        vendor_text = (vendor_name or "").strip()
        effective_vendor = payee_text or vendor_text or "Employee Reimbursement"

        note_parts = []
        if description:
            note_parts.append(str(description).strip())
        if payee_text:
            note_parts.append(f"Payee: {payee_text}")
        if reimbursed_via:
            note_parts.append(f"Paid via: {reimbursed_via}")
        note_parts.append("Source: receipt reimbursement sync")
        expense_description = " | ".join([p for p in note_parts if p])

        try:
            cur = self.conn.cursor()
            cur.execute(
                "DELETE FROM employee_expenses WHERE receipt_id = %s",
                (receipt_id,),
            )
            cur.execute(
                """
                INSERT INTO employee_expenses (
                    employee_id,
                    receipt_id,
                    expense_date,
                    amount,
                    category,
                    subcategory,
                    vendor_name,
                    description,
                    is_business_expense,
                    business_percentage,
                    is_reimbursable,
                    reimbursement_status,
                    reimbursed_amount,
                    reimbursed_date,
                    submitted_at,
                    created_at,
                    updated_at
                )
                VALUES (
                    %s, %s, %s, %s, 'Meals', 'Receipt Reimbursement', %s, %s,
                    TRUE, 100.00, TRUE, %s, %s,
                    CASE WHEN %s THEN %s ELSE NULL END,
                    NOW(), NOW(), NOW()
                )
                """,
                (
                    employee_id,
                    receipt_id,
                    expense_date,
                    gross_amount,
                    effective_vendor,
                    expense_description,
                    reimbursement_status,
                    reimbursed_amount,
                    reimbursed_now,
                    expense_date,
                ),
            )
            self.conn.commit()
            cur.close()
        except Exception:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
    def _has_potential_duplicate(
        self, vendor: str, date, amount: Decimal, banking_id: int | None
    ) -> bool:
        try:
            cur = self.conn.cursor()
            sql = (
                "SELECT 1 FROM receipts r "
                "WHERE r.vendor_name ILIKE %s "
                "AND r.receipt_date BETWEEN %s - INTERVAL '7 days' AND %s + "
                "INTERVAL '7 days' "
                "AND r.gross_amount BETWEEN %s AND %s "
                "AND r.is_voided IS NOT TRUE "
                "AND r.exclude_from_reports IS NOT TRUE "
                "AND r.is_split_receipt IS NOT TRUE "
            )
            params = [
                f"%{vendor}%",
                date,
                date,
                float(amount) - 1.0,
                float(amount) + 1.0,
            ]
            # No banking_transaction_id in local DB
            cur.execute(sql, params)
            exists = cur.fetchone() is not None
            cur.close()
            return exists
        except Exception:
            return False

    def _find_potential_duplicates(
        self, vendor: str, date, amount: Decimal
    ) -> list[tuple]:
        """Find and return potential duplicate receipts (±$1, ±7 days)
        with details.

        Returns list of tuples:
        (receipt_id, receipt_date, vendor_name, gross_amount, description,
        backward_date_warning)
        backward_date_warning is True if banking date has swapped MM/DD
        compared to receipt date
        """
        try:
            cur = self.conn.cursor()
            cur.execute(
                """SELECT r.receipt_id, r.receipt_date, r.vendor_name,
                          r.gross_amount,
                          COALESCE(r.description, '') as description,
                          r.banking_transaction_id,
                          bt.transaction_date as banking_date
                   FROM receipts r
                   LEFT JOIN banking_transactions bt
                          ON r.banking_transaction_id = bt.transaction_id
                   WHERE r.vendor_name ILIKE %s
                   AND r.receipt_date BETWEEN
                       %s - INTERVAL '7 days' AND %s + INTERVAL '7 days'
                   AND r.gross_amount BETWEEN %s AND %s
                   AND r.is_voided IS NOT TRUE
                   AND r.exclude_from_reports IS NOT TRUE
                   AND r.is_split_receipt IS NOT TRUE
                   ORDER BY r.receipt_date DESC, r.receipt_id DESC
                   LIMIT 10""",
                [
                    f"%{vendor} %",
                    date,
                    date,
                    float(amount) - 1.0,
                    float(amount) + 1.0,
                ],
            )
            rows = cur.fetchall()
            cur.close()

            # Process rows to detect backward dates (MM/DD swap)
            results = []
            for row in rows:
                (
                    receipt_id,
                    receipt_date,
                    vendor_name,
                    gross_amount,
                    description,
                    banking_id,
                    banking_date,
                ) = row
                backward_date_warning = False

                # Check if banking date has swapped month/day
                if banking_date and receipt_date:
                    # Swap MM/DD of banking date to check if it matches receipt
                    # date
                    swapped_date = (
                        banking_date.replace(
                            day=banking_date.month, month=banking_date.day
                        )
                        if (
                            banking_date.month <= 12
                            and banking_date.day <= 12
                            and banking_date.month != banking_date.day
                        )
                        else None
                    )

                    if swapped_date and swapped_date == receipt_date:
                        backward_date_warning = True

                results.append(
                    (
                        receipt_id,
                        receipt_date,
                        vendor_name,
                        gross_amount,
                        description,
                        backward_date_warning,
                    )
                )

            return results
        except Exception:
            return []

    def _check_duplicates(self) -> None:
        """Check for potential duplicate receipts based on current form "
        "values."""

        try:
            vendor = (self.new_vendor.get_vendor() or "").strip()
            amount = self.new_amount.value()
            date = self.new_date.date().toPyDate()

            if not vendor or amount <= 0:
                QMessageBox.information(
                    self,
                    "Missing data",
                    "Enter Vendor and Amount to check for duplicates.",
                )
                return

            # Use the shared duplicate detection function
            duplicates = self._find_potential_duplicates(vendor, date, amount)

            if not duplicates:
                QMessageBox.information(
                    self,
                    "No Duplicates",
                    f"No potential duplicates found for {vendor} "
                    f"~${amount:.2f} ±7 days.",
                )
            else:
                msg = f"Found {len(duplicates)} potential duplicate(s):\n\n"
                for (
                    rid,
                    rdate,
                    rvend,
                    ramt,
                    rdesc,
                    backward_date,
                ) in duplicates:
                    msg += (
                        f"• Receipt #{rid}: {rdate} | {rvend} | ${ramt:.2f}\n"
                    )
                    if rdesc:
                        msg += f"  Description: {rdesc[:50]}\n"
                    if backward_date:
                        msg += (
                            "  ⚠️ WARNING: Banking date has swapped MM/DD!\n"
                        )
                    msg += "\n"
                QMessageBox.warning(self, "Potential Duplicates Found", msg)
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Could not check duplicates:\n{e}"
            )

    def _toggle_sticky_mode(self) -> None:
        """Toggle sticky/paintbrush mode: preserve vendor, GL and payment
        across clears.
        """
        self._sticky_active = self.sticky_btn.isChecked()
        if self._sticky_active:
            # Capture current form values as the sticky defaults
            vendor = ""
            if hasattr(self, "new_vendor"):
                if hasattr(self.new_vendor, "get_vendor"):
                    vendor = self.new_vendor.get_vendor() or ""
                elif hasattr(self.new_vendor, "currentText"):
                    vendor = self.new_vendor.currentText() or ""
                elif hasattr(self.new_vendor, "text"):
                    vendor = self.new_vendor.text() or ""
            gl_idx = self.new_gl.currentIndex()
            gl_code = (
                (self.new_gl.itemData(gl_idx) or self.new_gl.currentText())
                if gl_idx >= 0
                else ""
            )
            payment = (
                self.payment_method.currentText()
                if hasattr(self, "payment_method")
                else ""
            )
            self._sticky_defaults = {
                "vendor": vendor,
                "gl_code": gl_code,
                "payment": payment,
            }
            self.sticky_btn.setStyleSheet(
                "font-size: 9pt; background-color: #e8a020; color: white; "
                "font-weight: bold;"
            )
            self.sticky_btn.setText("\U0001f58c\ufe0f Sticky ON")
            # Tint locked fields amber so user knows they are pinned
            for w in (self.new_vendor, self.new_gl, self.payment_method):
                w.setStyleSheet("background-color: #fff8e1;")
        else:
            self._sticky_defaults = {}
            self.sticky_btn.setStyleSheet("font-size: 9pt;")
            self.sticky_btn.setText("\U0001f58c\ufe0f Sticky")
            for w in (self.new_vendor, self.new_gl, self.payment_method):
                w.setStyleSheet("")

    def _apply_sticky_defaults(self) -> None:
        """Re-apply stored sticky defaults after a form clear."""
        if not self._sticky_active or not self._sticky_defaults:
            return
        vendor = self._sticky_defaults.get("vendor", "")
        if vendor and hasattr(self, "new_vendor"):
            if hasattr(self.new_vendor, "set_vendor"):
                self.new_vendor.set_vendor(vendor)
            elif hasattr(self.new_vendor, "setCurrentText"):
                self.new_vendor.setCurrentText(vendor)
            elif hasattr(self.new_vendor, "setText"):
                self.new_vendor.setText(vendor)
        gl_code = self._sticky_defaults.get("gl_code", "")
        if gl_code:
            idx = self.new_gl.findData(gl_code)
            if idx >= 0:
                self.new_gl.setCurrentIndex(idx)
            else:
                self.new_gl.setCurrentText(gl_code)
        payment = self._sticky_defaults.get("payment", "")
        if payment and hasattr(self, "payment_method"):
            pidx = self.payment_method.findText(payment)
            if pidx >= 0:
                self.payment_method.setCurrentIndex(pidx)

    def _prefill_from_search(self) -> None:
        """Prefill form fields from selected search result."""
        try:
            row = self.results_table.currentRow()
            if row < 0:
                QMessageBox.information(
                    self,
                    "No Selection",
                    "Select a receipt from the search results to prefill.",
                )
                return

            # Get receipt ID from first column
            rid_item = self.results_table.item(row, 0)
            if not rid_item:
                return

            rid = int(rid_item.text())

            # Fetch full receipt details
            fields = [
                "receipt_date",
                "vendor_name",
                "gross_amount",
                "description",
                "gl_account_code",
                "banking_transaction_id",
                "vehicle_id",
                "employee_id",
                "reserve_number",
            ]
            if self.fuel_column:
                fields.append(self.fuel_column)
            fields.extend(["gst_amount", "payment_method"])
            if "odometer_reading" in self.receipts_columns:
                fields.append("odometer_reading")
            fields = self._validated_receipt_columns(fields)

            cur = self.conn.cursor()
            cur.execute(
                f"""SELECT {', '.join(fields)}
                   FROM receipts WHERE receipt_id = %s""",
                (rid,),
            )
            row_data = cur.fetchone()
            cur.close()

            if not row_data:
                QMessageBox.warning(
                    self, "Not Found", f"Receipt #{rid} not found."
                )
                return

            # Populate form
            fuel = None
            odometer = None
            has_odometer = "odometer_reading" in self.receipts_columns
            if self.fuel_column and has_odometer:
                (
                    rdate,
                    vendor,
                    amount,
                    desc,
                    gl,
                    bank_id,
                    veh_id,
                    emp_id,
                    reserve,
                    fuel,
                    gst,
                    pmeth,
                    odometer,
                ) = row_data
            elif self.fuel_column:
                (
                    rdate,
                    vendor,
                    amount,
                    desc,
                    gl,
                    bank_id,
                    veh_id,
                    emp_id,
                    reserve,
                    fuel,
                    gst,
                    pmeth,
                ) = row_data
            elif has_odometer:
                (
                    rdate,
                    vendor,
                    amount,
                    desc,
                    gl,
                    bank_id,
                    veh_id,
                    emp_id,
                    reserve,
                    gst,
                    pmeth,
                    odometer,
                ) = row_data
            else:
                (
                    rdate,
                    vendor,
                    amount,
                    desc,
                    gl,
                    bank_id,
                    veh_id,
                    emp_id,
                    reserve,
                    gst,
                    pmeth,
                ) = row_data

            if rdate:
                self.new_date.setDate(
                    QDate(rdate.year, rdate.month, rdate.day)
                )
            if vendor:
                # VendorLookupWidget uses set_vendor() not setText()
                if hasattr(self.new_vendor, "set_vendor"):
                    self.new_vendor.set_vendor(vendor)
                else:
                    self.new_vendor.setText(vendor)
            if amount:
                self.new_amount.setText(f"{float(amount):.2f}")
            if desc:
                self.new_desc.setText(desc)
            if gl:
                # Try to find matching GL account in combo by data (code)
                idx = -1
                for i in range(self.new_gl.count()):
                    if self.new_gl.itemData(i) == gl:
                        idx = i
                        break
                if idx >= 0:
                    self.new_gl.setCurrentIndex(idx)
                else:
                    # Fallback to text match if data search fails
                    idx = self.new_gl.findText(gl, Qt.MatchFlag.MatchContains)
                    if idx >= 0:
                        self.new_gl.setCurrentIndex(idx)
                    else:
                        # Set as editable text if not found
                        self.new_gl.setEditText(gl)
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
            if odometer and hasattr(self, "new_odometer"):
                self.new_odometer.setValue(int(odometer))
            if gst:
                self.gst_override_input.setValue(float(gst))
                self.gst_override_enable.setChecked(True)
            if pmeth:
                idx = self.payment_method.findText(pmeth)
                if idx >= 0:
                    self.payment_method.setCurrentIndex(idx)

            QMessageBox.information(
                self,
                "Prefilled",
                f"Form prefilled from Receipt #{rid}. Review and modify as "
                f"needed.",
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Could not prefill from search:\n{e}"
            )

    # ------------------------------------------------------------------
    # Split/Allocate helper (uses modular split receipt dialog)
    # ------------------------------------------------------------------
    def _open_split_dialog(self) -> None:
        """Open the split receipt manager dialog (modular component)."""
        if not self.write_enabled:
            QMessageBox.information(
                self,
                "Writes disabled",
                "Set RECEIPT_WIDGET_WRITE_ENABLED=true to enable splitting.",
            )
            return

        # Check if we have a selected receipt to split
        rid = getattr(self, "loaded_receipt_id", None)
        if not rid:
            QMessageBox.information(
                self, "No Receipt", "Select a receipt from the table to split."
            )
            return

        try:
            # Fetch receipt details
            cur = self.conn.cursor()
            cur.execute(
                """SELECT receipt_date, vendor_name, gross_amount, description,
                          gst_amount, reserve_number, payment_method
                   FROM receipts WHERE receipt_id = %s""",
                (rid,),
            )
            row = cur.fetchone()
            cur.close()

            if not row:
                QMessageBox.warning(
                    self, "Not Found", f"Receipt #{rid} not found."
                )
                return

            # Prepare receipt data dict
            receipt_data = {
                "receipt_date": row[0],
                "vendor_name": row[1],
                "gross_amount": row[2],
                "description": row[3],
                "gst_amount": row[4],
                "reserve_number": row[5],
                "payment_method": row[6],
            }

            # Open the modular split receipt manager
            dlg = SplitReceiptManagerDialog(self.conn, rid, receipt_data, self)
            dlg.splits_saved.connect(
                lambda: self._on_split_saved()
            )  # Refresh and show splits
            dlg.exec()

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Could not open split dialog:\n{e}"
            )
            return

    def _on_split_saved(self) -> None:
        """Called after splits are saved - auto-enable 'Show linked splits' and
        refresh.
        """
        if hasattr(self, "show_linked_splits_chk"):
            self.show_linked_splits_chk.setChecked(True)
            logger.debug(
                "✓ Auto-enabled 'Show linked splits' to display "
                "new split receipts"
            )
        self._do_search()

    # Helpers
    def _load_receipts_columns(self) -> set[str]:
        """Load receipts table columns. With timeout protection."""
        try:
            cur = self.conn.cursor()
            # Add statement timeout to prevent hanging (3 seconds max)
            cur.execute("SET statement_timeout = 3000")
            cur.execute(
                "SELECT column_name FROM information_schema.columns WHERE "
                "table_name = 'receipts'"
            )
            cols = {row[0] for row in cur.fetchall()}
            cur.close()
            self.conn.commit()  # Clear the timeout setting
            logger.debug(f"✓ Loaded {len(cols)} columns from receipts table")
            return cols
        except Exception as e:
            logger.warning(
                "Failed to load receipts columns (using empty set): %s",
                e,
            )
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            return set()

    def _resolve_fuel_column(self) -> str | None:
        if "fuel_amount" in self.receipts_columns:
            return "fuel_amount"
        if "fuel_liters" in self.receipts_columns:
            return "fuel_liters"
        return None

    def _validated_receipt_columns(self, columns: list[str]) -> list[str]:
        ident_pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
        validated = []
        for col in columns:
            if not col or not ident_pattern.match(col):
                raise ValueError(f"Invalid column identifier: {col}")
            if col not in self.receipts_columns:
                raise ValueError(
                    f"Column not present in receipts schema: {col}"
                )
            validated.append(col)
        return validated

    def _ensure_audit_table(self) -> None:
        if self._audit_table_checked:
            return
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = 'receipt_audit_log'
                """)
            exists = cur.fetchone() is not None
            cur.close()
            self._audit_table_exists = exists
            self._audit_table_checked = True
            # Optional creation gated by env var
            if not exists and str(
                os.environ.get("RECEIPT_AUDIT_CREATE", "false")
            ).lower() in ("1", "true", "yes"):
                try:
                    curc = self.conn.cursor()
                    curc.execute("""
                        CREATE TABLE IF NOT EXISTS receipt_audit_log (
                            audit_id BIGSERIAL PRIMARY KEY,
                            receipt_id INTEGER,
                            action TEXT NOT NULL,
                            event_time TIMESTAMPTZ DEFAULT now(),
                            actor TEXT DEFAULT 'DesktopApp',
                            details JSONB
                        )
                        """)
                    self.conn.commit()
                    curc.close()
                    self._audit_table_exists = True
                except Exception:
                    try:
                        self.conn.rollback()
                    except Exception as _e:
                        logger.debug('Suppressed: %s', _e)
        except Exception:
            self._audit_table_checked = True
            self._audit_table_exists = False

    def _audit_log(
        self, action: str, receipt_id: int | None, details: dict
    ) -> None:
        try:
            self._ensure_audit_table()
            if not self._audit_table_exists:
                return
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO receipt_audit_log (receipt_id, action, actor, "
                "details) VALUES (%s, %s, %s, %s)",
                (receipt_id, action, "DesktopApp", json.dumps(details)),
            )
            self.conn.commit()
            cur.close()
        except Exception:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
    def _load_vehicles_into_combo(self) -> None:
        try:
            # Clear any failed transaction state so this query can run.
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            vehicle_columns = None
            try:
                cur_cols = self.conn.cursor()
                cur_cols.execute(
                    "SELECT column_name FROM information_schema.columns WHERE "
                    "table_name = 'vehicles'"
                )
                vehicle_columns = {row[0] for row in cur_cols.fetchall()}
                cur_cols.close()
            except Exception:
                vehicle_columns = None
                try:
                    cur_cols.close()
                except Exception as _e:
                    logger.debug('Suppressed: %s', _e)
            if vehicle_columns == set():
                self.new_vehicle_combo.addItem("Vehicles table missing", None)
                return

            cur = self.conn.cursor()
            # Natural numeric sort: L1, L2, ..., L10, ..., L25 (not string
            # sort)
            if (
                vehicle_columns is not None
                and "vehicle_number" not in vehicle_columns
            ):
                cur.execute("""
                    SELECT vehicle_id, vehicle_id::text
                    FROM vehicles
                    ORDER BY vehicle_id
                """)
            else:
                try:
                    cur.execute("""
                        SELECT vehicle_id,
                               COALESCE(vehicle_number, 'L'||vehicle_id::text)
                        FROM vehicles
                        ORDER BY
                            CASE WHEN vehicle_number ~ '^L[0-9]+$'
                                 THEN NULLIF(
                                     regexp_replace(
                                         vehicle_number, '\\D', '', 'g'
                                     ),
                                     ''
                                 )::integer
                                 ELSE 999999
                            END,
                            vehicle_id
                    """)
                except Exception:
                    try:
                        self.conn.rollback()
                    except Exception as _e:
                        logger.debug('Suppressed: %s', _e)
                    cur.execute("""
                        SELECT vehicle_id,
                               COALESCE(vehicle_number, vehicle_id::text)
                        FROM vehicles
                        ORDER BY vehicle_id
                    """)

            rows = cur.fetchall()
            for vid, label in rows:
                self.new_vehicle_combo.addItem(label, vid)
            cur.close()

            if not rows:
                self.new_vehicle_combo.addItem("No vehicles found", None)
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            try:
                log_path = os.path.join(
                    os.path.dirname(__file__), "vehicle_load_error.log"
                )
                with open(log_path, "a", encoding="utf-8") as log_file:
                    log_file.write("\n--- Vehicle load error ---\n")
                    log_file.write(f"{e}\n")
                    log_file.write(traceback.format_exc())
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            try:
                self.new_vehicle_combo.addItem("Vehicle load error", None)
                self.new_vehicle_combo.setToolTip(
                    "Vehicle load error (see vehicle_load_error.log)"
                )
                QMessageBox.warning(
                    self,
                    "Vehicle Load Error",
                    "Could not load vehicles. See vehicle_load_error.log for "
                    "details.",
                )
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
    def _load_drivers_into_combo(self) -> None:
        try:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT employee_id, CONCAT_WS(' ', first_name, last_name) "
                "FROM employees ORDER BY first_name, last_name"
            )
            rows = cur.fetchall()
            names = []
            for emp_id, name in rows:
                self.new_driver_combo.addItem(name, emp_id)
                names.append(name)
            comp = QCompleter(names)
            comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            comp.setFilterMode(Qt.MatchFlag.MatchContains)
            self.new_driver_combo.setCompleter(comp)
            cur.close()
            if not rows:
                self.new_driver_combo.addItem("No drivers found", None)
        except Exception:
            try:
                self.new_driver_combo.addItem("Driver load error", None)
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
    def eventFilter(self, obj, event) -> bool:
        """Lazy load drivers and vehicles on first focus."""
        from PyQt6.QtCore import QEvent

        # Vehicle combo - load on first focus
        if (
            obj == self.new_vehicle_combo
            and event.type() == QEvent.Type.FocusIn
        ):
            if not self._vehicles_loaded:
                # Clear placeholder and load data
                self.new_vehicle_combo.clear()
                self.new_vehicle_combo.addItem("", None)  # Blank item
                self._load_vehicles_into_combo()
                self._vehicles_loaded = True
                # Show first real item (skip blank)
                if self.new_vehicle_combo.count() > 1:
                    self.new_vehicle_combo.showPopup()

        # Driver combo - load on first focus
        elif (
            obj == self.new_driver_combo
            and event.type() == QEvent.Type.FocusIn
        ):
            if not self._drivers_loaded:
                # Clear placeholder and load data
                self.new_driver_combo.clear()
                self.new_driver_combo.addItem("", None)  # Blank item
                self._load_drivers_into_combo()
                self._drivers_loaded = True
                # Show dropdown
                if self.new_driver_combo.count() > 1:
                    self.new_driver_combo.showPopup()

        # Pass event to parent
        return super().eventFilter(obj, event)

    def _attach_vendor_completer(self) -> None:
        """Attach vendor autocomplete. Non-blocking with timeout protection."""
        try:
            cur = self.conn.cursor()
            # Add statement timeout to prevent hanging (5 seconds max)
            cur.execute("SET statement_timeout = 5000")
            cur.execute(
                "SELECT DISTINCT vendor_name FROM receipts "
                "WHERE vendor_name IS NOT NULL ORDER BY vendor_name LIMIT 5000"
            )
            vendors = [row[0] for row in cur.fetchall()]
            cur.close()
            self.conn.commit()  # Clear the timeout setting

            if vendors:
                comp = QCompleter(vendors)
                comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                comp.setFilterMode(Qt.MatchFlag.MatchContains)
                self.new_vendor.setCompleter(comp)
                logger.debug(
                    f"✓ Vendor completer attached with {len(vendors)} vendors"
                )
        except Exception as e:
            logger.warning("Vendor completer failed (non-critical): %s", e)
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
    def _attach_charter_completer(self) -> None:
        """Add fuzzy/contains charter number lookup completer. Non-blocking
        with timeout protection.
        """
        try:
            cur = self.conn.cursor()
            # Add statement timeout to prevent hanging (5 seconds max)
            cur.execute("SET statement_timeout = 5000")
            cur.execute(
                "SELECT DISTINCT CAST(reserve_number AS TEXT) FROM charters "
                "WHERE reserve_number IS NOT NULL ORDER BY reserve_number"
            )
            charters = [row[0] for row in cur.fetchall()]
            cur.close()
            self.conn.commit()  # Clear the timeout setting

            if charters:
                comp = QCompleter(charters)
                comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                comp.setFilterMode(Qt.MatchFlag.MatchContains)
                comp.setMaxVisibleItems(15)
                comp.popup().setMinimumWidth(320)
                self.new_charter_input.setCompleter(comp)
                logger.debug(
                    f"✓ Charter completer attached with {len(charters)} "
                    f"charters"
                )

        except Exception as e:
            logger.warning("Charter completer failed (non-critical): %s", e)
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------
    def _load_recent(self) -> None:
        try:
            # Ensure transaction is clean before querying
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            cur = self.conn.cursor()
            cur.execute("""
                SELECT receipt_id, receipt_date, vendor_name, gross_amount,
                       COALESCE(reserve_number, '') AS reserve_num,
                       COALESCE(description, '') AS description,
                       COALESCE(payment_method, '') AS payment_method,
                      COALESCE(created_from_banking, false)
                          AS created_from_banking
                FROM receipts
                ORDER BY receipt_date DESC, receipt_id DESC
                LIMIT 50
                """)
            rows = cur.fetchall()
            cur.close()
            self.conn.commit()
            self.last_results = rows
            self._populate_table(rows)
            self.results_label.setText(
                f"Recent 50 receipts loaded ({len(rows)})"
            )
        except Exception as e:
            # Silently fail during init - user can manually trigger search
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            import sys

            logger.debug(f"[ReceiptWidget] Load recent failed: {e}", file=sys.stderr)
            self.results_label.setText(
                "(No recent receipts loaded - use search)"
            )

    def _toggle_compact_view(self, on: bool) -> None:
        # Show 4-line summary in Vendor column when enabled
        if on:
            # Rename header for vendor column to Summary
            headers = [
                "ID",
                "Date",
                "Summary",
                "Amount",
                "GL/Category",
                "Banking ID",
                "Banking Type",
                "Payment Type",
                "Charter",
                "Paper ✓",
            ]
            self.results_table.setHorizontalHeaderLabels(headers)
            # Hide non-summary columns except Vendor(2)
            for col in (0, 1, 3, 4, 5, 6, 7, 8, 9):
                self.results_table.setColumnHidden(col, True)
            # Attach delegate
            self.results_table.setItemDelegateForColumn(
                2, ReceiptCompactDelegate(self.results_table)
            )
            # Increase row heights for readability
            for r in range(self.results_table.rowCount()):
                self.results_table.setRowHeight(
                    r, 4 * self.results_table.fontMetrics().height() + 10
                )
        else:
            # Restore headers
            headers = [
                "ID",
                "Date",
                "Vendor",
                "Amount",
                "GL/Category",
                "Banking ID",
                "Banking Type",
                "Payment Type",
                "Charter",
                "Paper ✓",
            ]
            self.results_table.setHorizontalHeaderLabels(headers)
            # Unhide columns
            for col in (0, 1, 3, 4, 5, 6, 7, 8, 9):
                self.results_table.setColumnHidden(col, False)
            # Remove delegate
            self.results_table.setItemDelegateForColumn(
                2, QStyledItemDelegate(self.results_table)
            )
            # Reset row heights to default
            for r in range(self.results_table.rowCount()):
                self.results_table.setRowHeight(
                    r, self.results_table.fontMetrics().height() + 8
                )

    def _link_selected_to_charter(self) -> None:
        """Link the selected receipt row to a charter by reserve_number."""

        # PERFORMANCE: Ensure drivers and vehicles are loaded before charter
        # lookup
        # User may want to populate vehicle/driver from charter data
        if not self._vehicles_loaded:
            self.new_vehicle_combo.clear()
            self.new_vehicle_combo.addItem("", None)
            self._load_vehicles_into_combo()
            self._vehicles_loaded = True

        if not self._drivers_loaded:
            self.new_driver_combo.clear()
            self.new_driver_combo.addItem("", None)
            self._load_drivers_into_combo()
            self._drivers_loaded = True

        selected = self.results_table.selectedItems()
        if not selected:
            QMessageBox.information(
                self,
                "No selection",
                "Select a receipt row to link to a charter.",
            )
            return
        rid = int(self.results_table.item(selected[0].row(), 0).text())
        reserve_num = (self.charter_lookup_input.text() or "").strip()
        if not reserve_num:
            QMessageBox.information(
                self, "Missing reserve #", "Enter a reserve number to link."
            )
            return
        try:
            cur = self.conn.cursor()
            cur.execute(
                "UPDATE receipts SET reserve_number = %s WHERE receipt_id = "
                "%s",
                (reserve_num, rid),
            )
            self.conn.commit()
            cur.close()
            QMessageBox.information(
                self,
                "Linked",
                f"Receipt {rid} linked to Charter {reserve_num}.",
            )
            self.charter_lookup_input.clear()
            self._do_search()
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.critical(
                self, "Link Error", f"Could not link receipt:\n\n{e}"
            )

    # ------------------------------------------------------------------
    # Banking match suggestions
    # ------------------------------------------------------------------
    def _suggest_banking_matches(self) -> None:
        """Suggest unmatched banking transactions based on amount/date.
        If charter is linked, auto-creates payment record for full
        reconciliation.
        """
        amt = self.new_amount.value()
        date = self.new_date.date().toPyDate()
        if amt <= 0 or not date:
            QMessageBox.information(
                self,
                "Missing data",
                "Enter Amount and Date to find banking matches.",
            )
            return
        try:
            cur = self.conn.cursor()
            # Search for deposits (credit_amount) or withdrawals (debit_amount)
            # Tolerance: $0.02 exact-match only to prevent false vendor cross-
            # matches
            cur.execute(
                """
                SELECT transaction_id, transaction_date, description,
                       COALESCE(credit_amount, 0) as credit,
                       COALESCE(debit_amount, 0) as debit,
                       COALESCE(credit_amount, 0)
                           - COALESCE(debit_amount, 0) AS net_amount
                FROM banking_transactions
                WHERE (
                    ABS(COALESCE(credit_amount, 0) - %s)
                        < 0.02  -- Deposit exact match
                    OR ABS(COALESCE(debit_amount, 0) - %s)
                        < 0.02  -- Withdrawal exact match
                )
                AND transaction_date BETWEEN
                    %s - INTERVAL '7 days' AND %s + INTERVAL '7 days'
                AND (
                    reconciliation_status IS NULL
                    OR reconciliation_status IN ('unreconciled','ignored')
                    OR (
                        reconciliation_status = 'reconciled'
                        AND receipt_id IS NULL
                        AND (
                            reconciled_receipt_id IS NULL
                            OR NOT EXISTS (
                                SELECT 1
                                FROM receipts r_chk
                                WHERE r_chk.receipt_id =
                                    banking_transactions.reconciled_receipt_id
                            )
                        )
                    )
                )
                ORDER BY ABS(transaction_date - %s),
                         LEAST(
                             ABS(COALESCE(credit_amount,0) - %s),
                             ABS(COALESCE(debit_amount,0) - %s)
                         )
                LIMIT 20
                """,
                (amt, amt, date, date, date, amt, amt),
            )
            rows = cur.fetchall()
            cur.close()
            if not rows:
                QMessageBox.information(
                    self,
                    "No matches",
                    f"No banking transactions found matching ${amt:,.2f} near "
                    f"{date}.",
                )
                return

            # Build dialog
            dlg = QDialog(self)
            dlg.setWindowTitle("🏦 Banking Match & Reconcile")
            dlg.setMinimumWidth(700)
            v = QVBoxLayout(dlg)

            # Header
            header = QLabel(
                f"Found {len(rows)} banking transaction(s) matching "
                f"${amt:,.2f} on {date}:"
            )
            header.setStyleSheet(
                "font-weight: bold; font-size: 11pt; padding: 5px;"
            )
            v.addWidget(header)

            # Info about auto-reconciliation
            reserve = (self.new_charter_input.text() or "").strip()
            if reserve:
                info_label = QLabel(
                    f"✅ Charter #{reserve} linked - selecting a deposit will "
                    f"auto-create payment record & reconcile!"
                )
                info_label.setStyleSheet(
                    "color: #006600; background-color: #e6ffe6; padding: 8px; "
                    "border-radius: 4px;"
                )
            else:
                info_label = QLabel(
                    "💡 TIP: Enter a Charter # above before matching to "
                    "auto-create payment record"
                )
                info_label.setStyleSheet(
                    "color: #666600; background-color: #ffffcc; padding: 8px; "
                    "border-radius: 4px;"
                )
            info_label.setWordWrap(True)
            v.addWidget(info_label)

            # Transaction list
            lst = QListWidget()
            receipt_vendor = (
                self.new_vendor.currentText()
                if hasattr(self, "new_vendor")
                else ""
            ).upper()
            for tid, txn_date, desc, credit, debit, net_amt in rows:
                txn_type = "DEPOSIT" if credit > debit else "WITHDRAWAL"
                txn_amt = credit if credit > debit else debit
                amount_display = (
                    f"${credit:,.2f}" if credit > debit else f"-${debit:,.2f}"
                )
                amt_diff = abs(txn_amt - amt)
                diff_str = f" [diff ${amt_diff:.2f}]" if amt_diff >= 0.01 else ""
                item_text = (
                    f"ID {tid} | {txn_date} | {txn_type} "
                    f"{amount_display}{diff_str} | {desc[:60]}"
                )
                item = QListWidgetItem(item_text)
                item.setData(1000, tid)  # Store ID
                item.setData(1001, credit)  # Store credit amount
                item.setData(1002, debit)  # Store debit amount
                # Warn visually if banking description doesn't contain receipt
                # vendor keywords
                desc_upper = (desc or "").upper()
                vendor_words = [
                    w for w in receipt_vendor.split() if len(w) > 3
                ]
                vendor_match = (
                    any(w in desc_upper for w in vendor_words)
                    if vendor_words
                    else True
                )
                if not vendor_match:
                    # Orange = vendor mismatch warning
                    item.setForeground(QColor(180, 80, 0))
                    item.setText(item_text + "  ⚠ VENDOR MISMATCH")
                lst.addItem(item)
            v.addWidget(lst)

            # Buttons
            btns = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok
                | QDialogButtonBox.StandardButton.Cancel
            )
            v.addWidget(btns)
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)

            if (
                dlg.exec() != QDialog.DialogCode.Accepted
                or not lst.currentItem()
            ):
                return

            selected = lst.currentItem().data(1000)
            credit_amt = lst.currentItem().data(1001)

            # Link banking transaction
            self.new_banking_id.setText(str(selected))

            # If charter is linked AND this is a deposit, auto-create payment
            # record
            if reserve and credit_amt > 0:
                try:
                    self._auto_create_payment_from_deposit(
                        reserve, amt, date, selected
                    )
                    QMessageBox.information(
                        self,
                        "✅ Fully Reconciled",
                        f"Banking Transaction #{selected} linked AND payment "
                        f"record created!\n\n"
                        f"Charter #{reserve} payment of ${amt:,.2f} is now:\n"
                        f"✓ Linked to banking deposit\n"
                        f"✓ Recorded in payments table\n"
                        f"✓ Marked as verified & reconciled",
                    )
                except Exception as e:
                    QMessageBox.warning(
                        self,
                        "Partial Success",
                        f"Banking transaction linked, but payment creation "
                        f"failed:\n{e}\n\n"
                        f"You may need to manually create the payment record.",
                    )
            else:
                QMessageBox.information(
                    self,
                    "Banking Linked",
                    f"Banking Transaction #{selected} linked to receipt.",
                )

        except Exception as e:
            QMessageBox.critical(
                self, "Match Error", f"Could not find banking matches:\n\n{e}"
            )

    def _auto_create_payment_from_deposit(
        self, reserve_number, amount, payment_date, banking_txn_id
    ) -> int:
        """Auto-create payment record when deposit is matched to charter."""
        cur = self.conn.cursor()
        try:
            # Find charter by reserve number
            cur.execute(
                "SELECT charter_id, client_id FROM charters WHERE "
                "reserve_number = %s LIMIT 1",
                (reserve_number,),
            )
            charter_row = cur.fetchone()
            if not charter_row:
                raise Exception(f"Charter #{reserve_number} not found")

            charter_id, client_id = charter_row

            # Check if payment already exists for this charter/amount/date
            cur.execute(
                """
                SELECT payment_id FROM payments
                WHERE charter_id = %s
                AND ABS(amount - %s) < 0.01
                AND payment_date = %s
                LIMIT 1
                """,
                (charter_id, amount, payment_date),
            )
            existing = cur.fetchone()

            if existing:
                # Update existing payment with banking link
                cur.execute(
                    "UPDATE payments SET last_updated = NOW() WHERE "
                    "payment_id = %s",
                    (existing[0],),
                )
                self.conn.commit()
                return existing[0]

            # Create new payment record
            payment_method = self.payment_method.currentText()
            cur.execute(
                """
                INSERT INTO payments (
                    charter_id, reserve_number, client_id, amount,
                    payment_method, payment_date,
                    created_at, last_updated, last_updated_by
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, NOW(), NOW(), 'receipt_auto_link'
                )
                RETURNING payment_id
                """,
                (
                    charter_id,
                    reserve_number,
                    client_id,
                    float(amount),
                    payment_method,
                    payment_date,
                ),
            )

            payment_id = cur.fetchone()[0]
            self.conn.commit()
            return payment_id

        except Exception as e:
            self.conn.rollback()
            raise e
        finally:
            cur.close()

    # ------------------------------------------------------------------
    # Bulk import CSV
    # ------------------------------------------------------------------
    def _open_bulk_import(self) -> None:
        """Open bulk receipt import dialog from CSV."""
        if not self.write_enabled:
            QMessageBox.information(
                self,
                "Writes disabled",
                "Set RECEIPT_WIDGET_WRITE_ENABLED=true to enable bulk import.",
            )
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Receipt CSV", "", "CSV Files (*.csv)"
        )
        if not file_path:
            return
        try:
            import csv

            with open(file_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            if not rows:
                QMessageBox.information(
                    self, "Empty file", "CSV contains no data rows."
                )
                return
            # Expected columns: date, vendor, amount, description, gl_account
            # Optional: vehicle_id, employee_id, reserve_number
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
                    if (
                        "vehicle_id" in row
                        and row["vehicle_id"].strip().isdigit()
                    ):
                        vehicle_id = int(row["vehicle_id"])
                    if (
                        "employee_id" in row
                        and row["employee_id"].strip().isdigit()
                    ):
                        driver_id = int(row["employee_id"])
                    if "reserve_number" in row:
                        reserve_number = (
                            row["reserve_number"] or ""
                        ).strip() or None
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
                    if self._has_potential_duplicate(
                        vendor, date, amount, None
                    ):
                        skipped += 1
                        continue
                    cur = self.conn.cursor()
                    cols = [
                        "receipt_date",
                        "vendor_name",
                        "gross_amount",
                        "description",
                    ]
                    vals = [
                        date,
                        vendor,
                        float(amount),
                        desc or None,
                        gl_text or None,
                    ]
                    if "vehicle_id" in self.receipts_columns and vehicle_id:
                        cols.append("vehicle_id")
                        vals.append(vehicle_id)
                    if "employee_id" in self.receipts_columns and driver_id:
                        cols.append("employee_id")
                        vals.append(driver_id)
                    if (
                        "reserve_number" in self.receipts_columns
                        and reserve_number
                    ):
                        cols.append("reserve_number")
                        vals.append(reserve_number)
                    cols = self._validated_receipt_columns(cols)
                    placeholders = ", ".join(["%s"] * len(vals))
                    sql = (
                        f"INSERT INTO receipts ({', '.join(cols)}) "
                        f"SELECT {placeholders} "
                        "WHERE NOT EXISTS ("
                        "  SELECT 1 FROM receipts r "
                        "  WHERE r.vendor_name = %s AND r.receipt_date = %s "
                        "    AND r.gross_amount = %s"
                        ") RETURNING receipt_id"
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
                                    "csv_row": row_idx
                                    + 2,  # +2 for header + 1-based
                                    "receipt_date": str(date),
                                    "vendor_name": vendor,
                                    "gross_amount": float(amount),
                                    "description": desc or None,
                                },
                            )
                        except Exception as _e:
                            logger.debug('Suppressed: %s', _e)
                        inserted += 1
                except Exception:
                    skipped += 1
            QMessageBox.information(
                self,
                "Bulk Import Complete",
                f"Inserted {inserted}, skipped {skipped}.",
            )
            self._do_search()
        except Exception as e:
            QMessageBox.critical(
                self, "Bulk Import Error", f"Could not import CSV:\n\n{e}"
            )

    # ------------------------------------------------------------------
    # Quick reconciliation view
    # ------------------------------------------------------------------
    def _open_reconciliation_view(self) -> None:
        """Show unmatched receipts and banking transactions for quick "
        "matching."""

        if not self.write_enabled:
            QMessageBox.information(
                self,
                "Writes disabled",
                "Set RECEIPT_WIDGET_WRITE_ENABLED=true to enable "
                "reconciliation.",
            )
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Quick Reconciliation")
        dlg.resize(1000, 600)
        v = QVBoxLayout(dlg)
        try:
            cur = self.conn.cursor()
            # Local DB doesn't have banking_transaction_id - all receipts
            # appear unmatched
            cur.execute("""
                SELECT receipt_id, receipt_date, vendor_name, gross_amount,
                       description
                FROM receipts
                ORDER BY receipt_date DESC
                LIMIT 100
                """)
            unmatched_receipts = cur.fetchall()
            # Banking transactions (no link to check)
            cur.execute(
                """SELECT transaction_id, transaction_date, description,
                   COALESCE(debit_amount, 0)
                       - COALESCE(credit_amount, 0) AS net_amount
                FROM banking_transactions
                WHERE (
                    posted_date IS NULL
                    OR posted_date >= CURRENT_DATE - INTERVAL '90 days'
                )
                ORDER BY transaction_date DESC
                LIMIT 100
                """
            )
            unmatched_banking = cur.fetchall()
            cur.close()
            v.addWidget(
                QLabel(
                    f"🧾 Unmatched Receipts ({len(unmatched_receipts)}) | 🏦 "
                    f"Unmatched Banking ({len(unmatched_banking)})"
                )
            )
            # Side-by-side tables
            h = QHBoxLayout()
            # Receipts table
            receipts_table = QTableWidget(len(unmatched_receipts), 5)
            receipts_table.setHorizontalHeaderLabels(
                ["ID", "Date", "Vendor", "Amount", "Description"]
            )
            for r, (rid, rdate, vendor, amt, desc) in enumerate(
                unmatched_receipts
            ):
                receipts_table.setItem(r, 0, QTableWidgetItem(str(rid)))
                receipts_table.setItem(r, 1, QTableWidgetItem(str(rdate)))
                receipts_table.setItem(r, 2, QTableWidgetItem(vendor or ""))
                receipts_table.setItem(
                    r, 3, QTableWidgetItem(f"${amt:,.2f}" if amt else "")
                )
                receipts_table.setItem(r, 4, QTableWidgetItem(desc or ""))
            h.addWidget(receipts_table)
            # Banking table
            banking_table = QTableWidget(len(unmatched_banking), 4)
            banking_table.setHorizontalHeaderLabels(
                ["ID", "Date", "Description", "Amount"]
            )
            for r, (bid, bdate, bdesc, bamt) in enumerate(unmatched_banking):
                banking_table.setItem(r, 0, QTableWidgetItem(str(bid)))
                banking_table.setItem(r, 1, QTableWidgetItem(str(bdate)))
                banking_table.setItem(r, 2, QTableWidgetItem(bdesc or ""))
                banking_table.setItem(
                    r, 3, QTableWidgetItem(f"${bamt:,.2f}" if bamt else "")
                )
            h.addWidget(banking_table)
            v.addLayout(h)
            # Match button
            match_btn = QPushButton("↔️  Match Selected")

            def do_match() -> None:
                r_row = receipts_table.currentRow()
                b_row = banking_table.currentRow()
                if r_row < 0 or b_row < 0:
                    QMessageBox.information(
                        dlg,
                        "Select both",
                        "Select one receipt and one banking transaction.",
                    )
                    return
                int(receipts_table.item(r_row, 0).text())
                int(banking_table.item(b_row, 0).text())
                # Local DB doesn't have banking_transaction_id column
                QMessageBox.information(
                    dlg,
                    "Not Supported",
                    "Banking transaction linking is not available in local "
                    "database.",
                )
                return

            match_btn.clicked.connect(do_match)
            v.addWidget(match_btn)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Reconciliation Error",
                f"Could not load reconciliation data:\n\n{e}",
            )

    # ------------------------------------------------------------------
    # Split Matches Pane - Banking, Charter, Linked Matches
    # ------------------------------------------------------------------
    def _build_matches_pane(self) -> QWidget:
        """Build the split matches display pane for double-clicked receipts."""
        try:
            logger.debug("\n🔨 DEBUG: Building matches pane...")
            pane = QWidget()
            layout = QVBoxLayout(pane)
            layout.setContentsMargins(3, 3, 3, 3)
            layout.setSpacing(3)

            # Tab widget for banking / charter / linked matches
            from PyQt6.QtWidgets import QTabWidget

            self.matches_tabs = QTabWidget()

            # Banking matches tab
            self.banking_matches_list = QListWidget()
            self.matches_tabs.addTab(
                self.banking_matches_list, "🏦 Banking Matches"
            )

            # Charter matches tab
            self.charter_matches_list = QListWidget()
            self.matches_tabs.addTab(
                self.charter_matches_list, "🔗 Charter Matches"
            )

            # Linked receipts tab
            self.linked_receipts_list = QListWidget()
            self.matches_tabs.addTab(
                self.linked_receipts_list, "📎 Linked Receipts"
            )

            layout.addWidget(self.matches_tabs)

            # Close button
            close_btn = QPushButton("✖ Close")
            close_btn.setMaximumWidth(80)
            close_btn.clicked.connect(lambda: pane.setVisible(False))
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()
            btn_layout.addWidget(close_btn)
            layout.addLayout(btn_layout)

            logger.debug("✅ DEBUG: Matches pane built successfully!")
            return pane
        except Exception:
            import traceback

            logger.debug("❌ DEBUG: Exception in _build_matches_pane:")
            logger.debug(traceback.format_exc())
            # Return a placeholder widget so the UI doesn't crash
            return QWidget()

    def _on_result_double_clicked(self, item) -> None:
        """Handle double-click on results table to show split matches pane."""
        try:
            logger.debug(f"\n🔍 DEBUG: Double-click detected on item: {item}")
            row = self.results_table.row(item)
            logger.debug(f"🔍 DEBUG: Row number: {row}")
            rid_item = self.results_table.item(row, 0)
            if not rid_item:
                logger.debug("⚠️  DEBUG: No item found at row 0")
                return

            receipt_id = int(rid_item.text())
            logger.debug(f"🔍 DEBUG: Receipt ID: {receipt_id}")
            logger.debug(f"🔍 DEBUG: Calling _show_split_matches({receipt_id})")
            self._show_split_matches(receipt_id)
            logger.debug("✅ DEBUG: _show_split_matches completed successfully")
        except Exception as e:
            import traceback

            logger.debug("❌ DEBUG: Exception in _on_result_double_clicked:")
            logger.debug(traceback.format_exc())
            QMessageBox.warning(
                self,
                "Error",
                f"Could not load matches:\n{e}\n\n{traceback.format_exc()}",
            )

    def _fetch_banking_matches(self, receipt_id: int) -> list[tuple]:
        """Fetch banking transactions matching this receipt."""
        try:
            cur = self.conn.cursor()
            # Find the receipt first to get vendor/amount
            cur.execute(
                """SELECT vendor_name, gross_amount, receipt_date,
                          banking_transaction_id
                   FROM receipts WHERE receipt_id = %s""",
                (receipt_id,),
            )
            receipt = cur.fetchone()
            if not receipt:
                cur.close()
                return []

            vendor, amount, rdate, linked_txn_id = receipt[:4]

            bank_ids = set()
            if linked_txn_id:
                bank_ids.add(int(linked_txn_id))

            try:
                cur.execute(
                    "SELECT transaction_id FROM banking_transactions WHERE "
                    "receipt_id = %s",
                    (receipt_id,),
                )
                row = cur.fetchone()
                if row and row[0]:
                    bank_ids.add(int(row[0]))
            except Exception:
                try:
                    self.conn.rollback()
                except Exception as _e:
                    logger.debug('Suppressed: %s', _e)
            cur.close()

            if amount is None or rdate is None:
                return []

            cur = self.conn.cursor()
            cur.execute(
                """
                  SELECT bt.transaction_id, bt.transaction_date,
                         bt.description,
                      COALESCE(
                          NULLIF(bt.credit_amount, 0), bt.debit_amount, 0
                      ) AS amount,
                      COALESCE(bt.account_number, '') AS account_number,
                      '' AS reference_number
                FROM banking_transactions bt
                WHERE (
                    ABS(COALESCE(bt.debit_amount, 0) - %s) < 1.0
                    OR ABS(COALESCE(bt.credit_amount, 0) - %s) < 1.0
                )
                AND bt.transaction_date BETWEEN
                    %s - INTERVAL '7 days' AND %s + INTERVAL '7 days'
                ORDER BY bt.transaction_date DESC, bt.transaction_id DESC
                LIMIT 20
                """,
                (amount, amount, rdate, rdate),
            )
            rows = cur.fetchall()
            cur.close()

            if bank_ids:
                placeholders = ", ".join(["%s"] * len(bank_ids))
                cur = self.conn.cursor()
                cur.execute(
                    f"""
                          SELECT bt.transaction_id, bt.transaction_date,
                                 bt.description,
                              COALESCE(
                                  NULLIF(bt.credit_amount, 0),
                                  bt.debit_amount,
                                  0
                              ) AS amount,
                              COALESCE(bt.account_number, '')
                                  AS account_number,
                              '' AS reference_number
                    FROM banking_transactions bt
                    WHERE bt.transaction_id IN ({placeholders})
                    """,
                    list(bank_ids),
                )
                linked_rows = cur.fetchall()
                cur.close()

                seen = {row[0] for row in rows}
                for linked_row in linked_rows:
                    if linked_row[0] not in seen:
                        rows.insert(0, linked_row)
                        seen.add(linked_row[0])

            return rows
        except Exception as e:
            logger.error("Banking match error: %s", e)
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            return []

    def _fetch_charter_matches(self, receipt_id: int) -> list[tuple]:
        """Fetch charters matching this receipt."""
        try:
            cur = self.conn.cursor()
            # Find the receipt's charter number or linked charter
            cur.execute(
                """SELECT reserve_number FROM receipts WHERE receipt_id = "
                "%s""",
                (receipt_id,),
            )
            row = cur.fetchone()
            cur.close()

            if not row or not row[0]:
                return []

            charter_num = row[0]

            # Fetch charter details
            cur = self.conn.cursor()
            cur.execute(
                """SELECT charter_id, charter_number, charter_date, vehicle_id,
                          driver_id, customer_name, charter_amount
                   FROM charters
                   WHERE charter_number = %s OR reserve_number = %s
                   ORDER BY charter_date DESC
                   LIMIT 3""",
                (charter_num, charter_num),
            )
            matches = cur.fetchall()
            cur.close()
            return matches if matches else []
        except Exception as e:
            logger.error("Charter match error: %s", e)
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            return []

    def _fetch_linked_matches(self, receipt_id: int) -> list[tuple]:
        """Fetch receipts linked to same banking transaction or charter."""
        try:
            cur = self.conn.cursor()
            # Find the receipt's banking_transaction_id and charter
            cur.execute(
                """SELECT reserve_number, banking_transaction_id,
                          split_group_id,
                          COALESCE(is_split_receipt, false)
                   FROM receipts WHERE receipt_id = %s""",
                (receipt_id,),
            )
            row = cur.fetchone()
            if not row:
                cur.close()
                return []

            charter_num, receipt_bank_id, split_group_id, is_split_receipt = (
                row[:4]
            )

            bank_ids = set()
            if receipt_bank_id:
                bank_ids.add(int(receipt_bank_id))

            try:
                cur.execute(
                    "SELECT transaction_id FROM banking_transactions WHERE "
                    "receipt_id = %s",
                    (receipt_id,),
                )
                bank_row = cur.fetchone()
                if bank_row and bank_row[0]:
                    bank_ids.add(int(bank_row[0]))
            except Exception:
                try:
                    self.conn.rollback()
                except Exception as _e:
                    logger.debug('Suppressed: %s', _e)
            cur.close()

            conditions = []
            params = []

            if charter_num:
                conditions.append("r.reserve_number = %s")
                params.append(charter_num)

            if bank_ids:
                placeholders = ", ".join(["%s"] * len(bank_ids))
                conditions.append(
                    f"r.banking_transaction_id IN ({placeholders})"
                )
                params.extend(list(bank_ids))
                conditions.append(
                    f"r.receipt_id IN (SELECT bt2.receipt_id FROM "
                    f"banking_transactions bt2 "
                    f"WHERE bt2.transaction_id IN ({placeholders}))"
                )
                params.extend(list(bank_ids))

            # Split-link condition: show siblings in the same split group
            if split_group_id:
                conditions.append("r.split_group_id = %s")
                params.append(split_group_id)
                # Older pattern fallback: retained parent row where receipt_id
                # == split_group_id
                conditions.append("r.receipt_id = %s")
                params.append(split_group_id)
            elif is_split_receipt:
                # Defensive fallback if split row flag is true but group_id is
                # missing
                conditions.append("r.split_group_id = %s")
                params.append(receipt_id)

            if not conditions:
                return []

            cur = self.conn.cursor()
            where_clause = " OR ".join(conditions)
            sql = f"""SELECT r.receipt_id, r.receipt_date, r.vendor_name,
                             r.gross_amount,
                             COALESCE(r.reserve_number, ''),
                             r.banking_transaction_id
                      FROM receipts r
                      WHERE ({where_clause})
                        AND r.receipt_id <> %s
                      ORDER BY r.receipt_date DESC, r.receipt_id DESC
                      LIMIT 5"""
            params.append(receipt_id)
            cur.execute(sql, params)
            matches = cur.fetchall()
            cur.close()
            return matches
        except Exception as e:
            logger.error("Linked match error: %s", e)
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            return []

    def _show_split_matches(self, receipt_id: int) -> None:
        """Populate and show the split matches pane for a receipt."""
        try:
            logger.debug(
                f"\n📋 DEBUG: _show_split_matches called for "
                f"receipt_id={receipt_id}"
            )

            # Check if matches_pane exists
            if not hasattr(self, "matches_pane"):
                logger.debug("❌ DEBUG: self.matches_pane does not exist!")
                QMessageBox.critical(
                    self,
                    "Error",
                    "Matches pane was not initialized. This is a bug.",
                )
                return

            logger.debug(f"🔍 DEBUG: matches_pane exists: {self.matches_pane}")

            # Clear all lists
            self.banking_matches_list.clear()
            self.charter_matches_list.clear()
            self.linked_receipts_list.clear()
            logger.debug("✅ DEBUG: Lists cleared")

            # Fetch and display banking matches
            logger.debug("🔍 DEBUG: Fetching banking matches...")
            banking_matches = self._fetch_banking_matches(receipt_id)
            logger.debug(
                "🔍 DEBUG: Found "
                f"{len(banking_matches) if banking_matches else 0} "
                "banking matches"
            )
            if banking_matches:
                for (
                    btxn_id,
                    bdate,
                    bdesc,
                    bamount,
                    bacc,
                    bref,
                ) in banking_matches:
                    item_text = (
                        f"#{btxn_id}  • {bdate}  • {(bdesc or '')[:40]}"
                        f"  • ${float(bamount or 0):,.2f}"
                    )
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.ItemDataRole.UserRole, btxn_id)
                    self.banking_matches_list.addItem(item)
            else:
                self.banking_matches_list.addItem("No banking matches found")

            # Fetch and display charter matches
            logger.debug("🔍 DEBUG: Fetching charter matches...")
            charter_matches = self._fetch_charter_matches(receipt_id)
            logger.debug(
                "🔍 DEBUG: Found "
                f"{len(charter_matches) if charter_matches else 0} "
                "charter matches"
            )
            if charter_matches:
                for (
                    c_id,
                    c_num,
                    c_date,
                    v_id,
                    d_id,
                    cust,
                    c_amt,
                ) in charter_matches:
                    item_text = (
                        f"#{c_num}  • {c_date}  • {cust or 'N/A'}"
                        f"  • ${float(c_amt or 0):,.2f}"
                    )
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.ItemDataRole.UserRole, c_id)
                    self.charter_matches_list.addItem(item)
            else:
                self.charter_matches_list.addItem("No charter matches found")

            # Fetch and display linked receipts
            logger.debug("🔍 DEBUG: Fetching linked matches...")
            linked_matches = self._fetch_linked_matches(receipt_id)
            logger.debug(
                "🔍 DEBUG: Found "
                f"{len(linked_matches) if linked_matches else 0} "
                "linked matches"
            )
            if linked_matches:
                for rid, rdate, rvend, ramt, rchar, rbank in linked_matches:
                    safe_vendor = rvend or ""
                    bank_tag = f" • Bank {rbank}" if rbank else ""
                    charter_tag = f" • {rchar}" if rchar else ""
                    item_text = (
                        f"#{rid}  • {rdate}  • {safe_vendor[:25]}"
                        f"  • ${float(ramt or 0):,.2f}{bank_tag}{charter_tag}"
                    )
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.ItemDataRole.UserRole, rid)
                    self.linked_receipts_list.addItem(item)
            else:
                self.linked_receipts_list.addItem("No linked receipts found")

            # Show the pane
            logger.debug("🔍 DEBUG: Making matches_pane visible")
            self.matches_pane.setVisible(True)
            self.matches_tabs.setCurrentIndex(0)  # Default to banking matches
            logger.debug("✅ DEBUG: Matches pane should now be visible!")

        except Exception as e:
            import traceback

            logger.debug("❌ DEBUG: Exception in _show_split_matches:")
            logger.debug(traceback.format_exc())
            QMessageBox.critical(
                self,
                "Error",
                f"Could not load split "
                f"matches:\n{e}\n\n{traceback.format_exc()}",
            )

    def _on_payment_method_changed(self, method: str) -> None:
        """Update table colors when payment method changes in the form."""
        # FIX: Do NOT re-populate table when editing form fields
        # Re-populating causes selection change which clears the form
        # The payment method is a form field and shouldn't affect table display
        self._maybe_autoselect_david_reimbursement_gl(method)

    def _toggle_conditional_fields(self) -> None:
        """Show/hide fuel and odometer fields based on GL code selection."""
        try:
            # Get current GL text and code (either from combo or editable text)
            try:
                text = (self.new_gl.currentText() or "").lower()
                gl_code = self.new_gl.currentData()
            except Exception:
                text = (self.new_gl.text() or "").lower()
                gl_code = None

            # Show fuel row only for fuel/gas GL codes
            show_fuel = "fuel" in text or "gas" in text
            self._set_fuel_row_visible(show_fuel)

            # Show odometer only for vehicle maintenance/repair GL codes (5100,
            # 5120)
            show_odometer = (
                gl_code in (5100, 5120) or "5100" in text or "5120" in text
            )
            self._set_odometer_visible(show_odometer)
        except Exception as e:
            # Silently continue on error
            import traceback

            logger.debug(
                f"⚠️ Error in _toggle_conditional_fields: "
                f"{e}\n{traceback.format_exc()}"
            )

    def _set_fuel_row_visible(self, visible: bool) -> None:
        """Safely set fuel row visibility without hiding entire details "
        "panel."""

        try:
            # Show/hide only the fuel widgets, NOT the parent container
            if hasattr(self, "fuel_liters") and self.fuel_liters:
                self.fuel_liters.setVisible(visible)
            if hasattr(self, "fuel_label") and self.fuel_label:
                self.fuel_label.setVisible(visible)
        except Exception as e:
            # Silently continue - don't hide the entire UI
            import traceback

            logger.debug(
                f"⚠️ Error in _set_fuel_row_visible: "
                f"{e}\n{traceback.format_exc()}"
            )

    def _set_odometer_visible(self, visible: bool) -> None:
        """Safely set odometer field visibility."""
        try:
            if hasattr(self, "new_odometer") and self.new_odometer:
                self.new_odometer.setVisible(visible)
            if hasattr(self, "odometer_label") and self.odometer_label:
                self.odometer_label.setVisible(visible)
        except Exception as e:
            import traceback

            logger.debug(
                f"⚠️ Error in _set_odometer_visible: "
                f"{e}\n{traceback.format_exc()}"
            )

    # ------------------------------------------------------------------
    # Quick Load Methods (Lazy Loading)
    # ------------------------------------------------------------------
    def _quick_load_year(self, year: int) -> None:
        """Load all receipts for one or more selected years."""
        if year in self.selected_years:
            self.selected_years.remove(year)
        else:
            self.selected_years.add(year)

        self._update_year_button_styles()

        if not self.selected_years:
            return

        min_year = min(self.selected_years)
        max_year = max(self.selected_years)
        self.date_from.setDate(QDate(min_year, 1, 1))
        self.date_to.setDate(QDate(max_year, 12, 31))
        self.vendor_filter.clear()
        self.amount_filter.setValue(0)
        self._populate_vendor_lookup()
        self._do_search()

    def _quick_load_days(self, days: int) -> None:
        """Load receipts for last N days."""
        self.selected_years.clear()
        self._update_year_button_styles()
        self.date_from.setDate(QDate.currentDate().addDays(-days))
        self.date_to.setDate(QDate.currentDate())
        self.vendor_filter.clear()
        self.amount_filter.setValue(0)
        self._populate_vendor_lookup()
        self._do_search()

    def _quick_load_all(self) -> None:
        """Load all receipts."""
        self.selected_years.clear()
        self._update_year_button_styles()
        # Set very wide date range
        self.date_from.setDate(QDate(2010, 1, 1))
        self.date_to.setDate(QDate.currentDate())
        self.vendor_filter.clear()
        self.amount_filter.setValue(0)
        self._populate_vendor_lookup()
        self._do_search()

    def _update_year_button_styles(self) -> None:
        for year, btn in self.year_buttons.items():
            if year in self.selected_years:
                btn.setStyleSheet(self._year_btn_selected_style)
            else:
                btn.setStyleSheet(self._year_btn_style)

    def _populate_vendor_lookup(self) -> None:
        """Populate vendor lookup dropdown — deferred so it doesn't block the
        UI.
        """
        # Capture date values now (on the main thread), run the DB query in
        # background
        date_from_str = self.date_from.date().toString("yyyy-MM-dd")
        date_to_str = self.date_to.date().toString("yyyy-MM-dd")

        def _run() -> list[str]:
            try:
                import psycopg2 as _pg

                try:
                    _dsn = self.conn.get_dsn_parameters()
                except Exception:
                    _dsn = {}
                _kw = {
                    "host": _dsn.get("host", "localhost"),
                    "port": int(_dsn.get("port", 5432)),
                    "dbname": _dsn.get("dbname", "almsdata"),
                    "user": _dsn.get("user", "postgres"),
                    "password": os.environ.get("DB_PASSWORD", ""),
                    "connect_timeout": 5,
                }
                _sslm = os.environ.get("DB_SSLMODE", "")
                if _sslm:
                    _kw["sslmode"] = _sslm
                _vh = _kw.get("host", "")
                if not ("-pooler." in _vh or ".pooler." in _vh):
                    _kw["options"] = "-c statement_timeout=5000"
                with _pg.connect(**_kw) as _conn, _conn.cursor() as _cur:
                    _cur.execute(
                        "SELECT DISTINCT vendor_name FROM receipts "
                        "WHERE receipt_date BETWEEN %s AND %s "
                        "AND vendor_name IS NOT NULL AND vendor_name != "
                        "'' "
                        "ORDER BY vendor_name",
                        (date_from_str, date_to_str),
                    )
                    return [r[0] for r in _cur.fetchall()]
            except Exception:
                return []

        import threading

        def _thread_body() -> None:
            names = _run()
            self.vendor_lookup_names_ready.emit(names)

        threading.Thread(target=_thread_body, daemon=True).start()

    def _on_vendor_lookup_selected(self, index: int) -> None:
        """When a vendor is picked from the lookup dropdown, filter results to
        that vendor.
        """
        if index < 0:
            self.vendor_filter.clear()
            return
        text = self.vendor_lookup.itemText(index)
        if not text:
            self.vendor_filter.clear()
        else:
            self.vendor_filter.setText(text)
            self._do_search()
