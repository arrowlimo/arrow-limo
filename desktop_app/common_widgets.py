#!/usr/bin/env python
"""
Common reusable widgets for the desktop application.
Provides standardized input fields with consistent behavior.
"""

from PyQt6.QtCore import QDate, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QLineEdit,
    QPushButton,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

PAYMENT_METHOD_LABELS = {
    "cash": "Cash",
    "cheque": "Cheque",
    "credit_card": "Credit Card",
    "debit_card": "Debit Card",
    "bank_debit": "Bank Debit",
    "bank_transfer": "Bank Transfer",
    "pre_authorized_debit": "Pre-authorized Debit",
    "bank_deposit": "Bank Deposit",
    "bank_draft": "Bank Draft",
    "loan": "Related Personal Loan",
    "reimbursement": "Reimbursement",
    "trade": "Trade",
    "escrow_hold": "Escrow Hold",
    "credit_adjustment": "Credit Adjustment",
    "other": "Other",
}

PAYMENT_METHOD_CHOICES = [""] + list(PAYMENT_METHOD_LABELS.values())

_PAYMENT_METHOD_ALIASES = {
    "cash": "cash",
    "cheque": "cheque",
    "check": "cheque",
    "credit": "credit_card",
    "credit card": "credit_card",
    "credit_card": "credit_card",
    "debit": "debit_card",
    "debit card": "debit_card",
    "debit_card": "debit_card",
    "debit/credit_card": "debit_card",
    "bank debit": "bank_debit",
    "bank_debit": "bank_debit",
    "bank charge": "bank_debit",
    "cibc banking": "bank_debit",
    "transfer": "bank_transfer",
    "bank transfer": "bank_transfer",
    "bank_transfer": "bank_transfer",
    "etransfer": "bank_transfer",
    "e-transfer": "bank_transfer",
    "pre-authorized debit": "pre_authorized_debit",
    "pre authorized debit": "pre_authorized_debit",
    "pre_authorized_debit": "pre_authorized_debit",
    "bank deposit": "bank_deposit",
    "bank_deposit": "bank_deposit",
    "deposit": "bank_deposit",
    "bank draft": "bank_draft",
    "bank_draft": "bank_draft",
    "loan": "loan",
    "related personal loan": "loan",
    "rpl": "loan",
    "reimbursement": "reimbursement",
    "reimburse_other": "reimbursement",
    "trade": "trade",
    "trade of services": "trade",
    "trade_of_services": "trade",
    "escrow hold": "escrow_hold",
    "escrow_hold": "escrow_hold",
    "credit adjustment": "credit_adjustment",
    "credit_adjustment": "credit_adjustment",
    "other": "other",
    "unknown": "other",
}


def normalize_payment_method(method: str | None) -> str:
    """Return the canonical database value for a payment method."""
    value = str(method or "").strip()
    if not value:
        return ""
    lowered = value.lower()
    if lowered.startswith("bank draft"):
        return "bank_draft"
    return _PAYMENT_METHOD_ALIASES.get(lowered, "other")


def display_payment_method(method: str | None) -> str:
    """Return the standard user-facing label for a payment method."""
    canonical = normalize_payment_method(method)
    return PAYMENT_METHOD_LABELS.get(canonical, "")


STANDARD_DATE_DISPLAY_FORMAT = "dd-MMM-yyyy"

# Day-first separated formats are tried before month-first ones so a receipt
# date like 20/07/2013 reads as 20 July. Unambiguous month-first values such as
# 12/25/2013 are invalid day-first and still fall through to the legacy forms.
DATE_INPUT_FORMATS = (
    "dd-MMM-yyyy",
    "d-MMM-yyyy",
    "dd/MMM/yyyy",
    "d/MMM/yyyy",
    "dd-MMMM-yyyy",
    "d-MMMM-yyyy",
    "dd/MM/yyyy",
    "d/M/yyyy",
    "dd-MM-yyyy",
    "d-M-yyyy",
    "dd.MM.yyyy",
    "d.M.yyyy",
    "yyyy-MM-dd",
    "yyyy/MM/dd",
    "yyyy/MMM/dd",
    "yyyy/MMMM/d",
    "MM/dd/yyyy",
    "M/d/yyyy",
    "MM-dd-yyyy",
    "M-d-yyyy",
    "dd MMM yyyy",
    "d MMM yyyy",
    "dd MMMM yyyy",
    "d MMMM yyyy",
    "MMM dd yyyy",
    "MMM d yyyy",
    "MMMM dd yyyy",
    "MMMM d yyyy",
)

_MONTH_LENGTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def parse_flexible_date(text: str) -> QDate:
    """Parse user-typed date text, preferring day-first interpretation."""
    text = str(text or "").strip()
    if not text:
        return QDate()

    lowered = text.lower()
    if lowered == "t":
        return QDate.currentDate()
    if lowered == "y":
        return QDate.currentDate().addDays(-1)

    for fmt in DATE_INPUT_FORMATS:
        parsed = QDate.fromString(text, fmt)
        if parsed.isValid():
            return parsed

    digits = "".join(c for c in text if c.isdigit())
    if len(digits) == 8:
        for fmt in ("ddMMyyyy", "yyyyMMdd"):
            parsed = QDate.fromString(digits, fmt)
            if parsed.isValid():
                return parsed
    return QDate()


def describe_invalid_date(text: str) -> str:
    """Explain in plain language why typed date text was not accepted."""
    text = str(text or "").strip()
    if not text:
        return "Enter a date such as 20-Jul-2013, 20/07/2013, or 20072013."

    digits = [part for part in "".join(
        c if c.isdigit() else " " for c in text
    ).split() if part]

    day = month = year = None
    if len(digits) == 3:
        first, second, third = digits
        if len(first) == 4:
            year, month, day = int(first), int(second), int(third)
        else:
            day, month, year = int(first), int(second), int(third)
    elif len(digits) == 1 and len(digits[0]) == 8:
        day, month, year = (
            int(digits[0][:2]),
            int(digits[0][2:4]),
            int(digits[0][4:]),
        )

    if day is not None and month is not None and year is not None:
        if 1 <= month <= 12 and day >= 1:
            days_in_month = QDate(year, month, 1).daysInMonth()
            if days_in_month and day > days_in_month:
                return (
                    f"{_MONTH_LENGTH_NAMES[month - 1]} {year} has only "
                    f"{days_in_month} days, so day {day} does not exist. "
                    "The previous date was kept."
                )
        if month > 12:
            return (
                f"There is no month {month}. Dates are read day first, "
                "for example 20/07/2013 is 20-Jul-2013."
            )

    return (
        "Date not recognized. Use day first, for example 20-Jul-2013, "
        "20/07/2013, or 20072013."
    )


def format_date_display(value) -> str:
    """Format a date-like value as DD-Mon-YYYY without changing storage."""
    if value in (None, ""):
        return ""
    if isinstance(value, QDate):
        return value.toString(STANDARD_DATE_DISPLAY_FORMAT) if value.isValid() else ""
    if hasattr(value, "strftime"):
        return value.strftime("%d-%b-%Y")
    text = str(value).strip()
    iso = QDate.fromString(text[:10], "yyyy-MM-dd")
    if iso.isValid():
        return iso.toString(STANDARD_DATE_DISPLAY_FORMAT)
    parsed = parse_flexible_date(text)
    if parsed.isValid():
        return parsed.toString(STANDARD_DATE_DISPLAY_FORMAT)
    return text


class DateSortItem(QTableWidgetItem):
    """Display DD-Mon-YYYY while retaining chronological table sorting."""

    def __init__(self, value) -> None:
        super().__init__(format_date_display(value))
        if isinstance(value, QDate):
            sort_key = value.toString("yyyy-MM-dd")
        elif hasattr(value, "strftime"):
            sort_key = value.strftime("%Y-%m-%d")
        else:
            sort_key = str(value or "")[:10]
        self._sort_key = sort_key
        self.setData(Qt.ItemDataRole.UserRole, sort_key)

    def __lt__(self, other) -> bool:
        if isinstance(other, DateSortItem):
            return self._sort_key < other._sort_key
        return super().__lt__(other)


class CurrencyInput(QLineEdit):
    """
    Standardized currency input field with:
    - Auto-select all on click/focus
    - Auto-formatting to 2 decimal places
    - Validation colors (optional)
    - Number pad support
    - Delete/replace selected text on keypress
    """

    def __init__(self, parent=None, compact=False, show_validation=False) -> None:
        super().__init__(parent)
        self.setPlaceholderText("0.00")
        self.setText("0.00")
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.show_validation = show_validation
        self.compact = compact

        if compact:
            self.setMaxLength(10)  # "999999.99" = 9 chars
            self.setMaximumWidth(100)
        else:
            self.setMaxLength(12)  # Up to $999,999.99

        # Default style
        self._set_style("neutral")

        # Tooltip
        self.setToolTip(
            "<b>💵 Currency Input</b><br>"
            "Enter amounts in any format:<br>"
            "<font color='green'><b>✓ Valid:</b></font> 10, 10.50, .50,"
            "250<br>"
            "<font color='blue'><b>Limits:</b> $0.00 - $999,999.99</font><br>"
            "Auto-formats to 2 decimal places."
        )
        # No side-effects here; focus selection handled in focusInEvent

    def mousePressEvent(self, event) -> None:
        """Select all on any mouse click"""
        super().mousePressEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def focusInEvent(self, event) -> None:
        """Select the complete amount for immediate replacement."""
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def mouseDoubleClickEvent(self, event) -> None:
        """Select all on double click"""
        self.selectAll()

    def focusOutEvent(self, event) -> None:
        """Format when leaving the field"""
        super().focusOutEvent(event)
        self._validate_and_format()

    def keyPressEvent(self, event) -> None:
        """Handle numeric input - support paste and direct replacement"""
        # If text is selected and user types, replace it
        if (
            self.selectedText()
            and event.text()
            and (event.text()[0].isdigit() or event.text()[0] == ".")
        ):
            self.clear()
        super().keyPressEvent(event)

    def _validate_and_format(self) -> None:
        """Format currency: 10→10.00, 10.10→10.10, .50→0.50"""
        text = self.text().replace(",", "").replace("$", "").strip()

        if not text:
            self.setText("0.00")
            self._set_style("neutral")
            return

        try:
            val = float(text)
            if val < 0:
                val = 0.0
            elif val > 999999.99:
                val = 999999.99
                self._set_style("warning")
            else:
                self._set_style("valid")

            self.setText(f"{val:.2f}")
        except ValueError:
            self.setText("0.00")
            self._set_style("error")

    def _set_style(self, state) -> None:
        """Apply color style based on validation state"""
        if not self.show_validation:
            self.setStyleSheet("QLineEdit { text-align: right;}")
            return

        if state == "valid":
            self.setStyleSheet(
                "QLineEdit { border: 2px solid #4CAF50; background-color:"
                "#f0fdf4; text-align: right;}"
            )
        elif state == "warning":
            self.setStyleSheet(
                "QLineEdit { border: 2px solid #FFC107; background-color:"
                "#fffbf0; text-align: right;}"
            )
        elif state == "error":
            self.setStyleSheet(
                "QLineEdit { border: 2px solid #f44336; background-color:"
                "#fdf0f0; text-align: right;}"
            )
        else:  # neutral
            self.setStyleSheet(
                "QLineEdit { border: 1px solid #ccc; background-color: white;"
                "text-align: right;}"
            )

    def get_value(self) -> object:
        """Get numeric value"""
        try:
            return float(self.text().replace(",", "").replace("$", ""))
        except Exception:
            return 0.0

    def set_value(self, value) -> None:
        """Set numeric value"""
        try:
            val = float(value)
            self.setText(f"{val:.2f}")
        except Exception:
            self.setText("0.00")


class StandardDateEdit(QLineEdit):
    """Unified date input with full-value replacement and QDate helpers.

    Dates display as ``dd-MMM-yyyy`` so the month is always unambiguous.
    Drop-in replacement for prior QDateEdit usage in this app.
    """

    # Compatibility signal: matches QDateEdit's dateChanged signature
    dateChanged = pyqtSignal(QDate)

    def __init__(
        self,
        parent=None,
        prefer_month_text=False,
        allow_blank: bool = False,
        select_all_on_click: bool = True,
    ) -> None:
        super().__init__(parent)
        self._allow_blank = allow_blank
        self._select_all_on_click = select_all_on_click
        self._has_value = not allow_blank
        self._current_date = QDate.currentDate()
        self._is_formatting = False
        self.display_format = "dd-MMM-yyyy"
        self.setMaxLength(20)
        if allow_blank:
            self.setText("")
        else:
            self.setText(self._current_date.toString(self.display_format))
        self.setPlaceholderText("DD-Mon-YYYY")
        self.setClearButtonEnabled(True)
        self.setMaximumWidth(130)
        # QDateEdit compatibility fields
        # Qt default Gregorian switch, harmless
        self._min_date = QDate(1752, 9, 14)
        self._max_date = QDate(7999, 12, 31)
        self._special_value_text = None
        self.setToolTip(
            "<b>📅 Date Input</b><br>"
            "Type 07-Jul-2007, 07072007, or 07/07/2007.<br>"
            "The month is displayed as text. +/- keys change day."
        )
        self.textChanged.connect(self._on_text_changed)

    # Compatibility shims with previous QDateEdit usage
    def setCalendarPopup(self, enabled: bool) -> None:
        self._calendar_popup_enabled = bool(enabled)

    def calendarPopup(self) -> bool:
        return bool(getattr(self, "_calendar_popup_enabled", False))

    def setDisplayFormat(self, fmt: str) -> None:
        self.display_format = "dd-MMM-yyyy"
        if self._has_value:
            self.setDate(self._current_date)

    def lineEdit(self) -> object:
        return self

    def setDate(self, qdate) -> None:
        # Accept Python datetime.date / datetime objects and convert to QDate
        import datetime as _dt

        if isinstance(qdate, (_dt.datetime, _dt.date)) and not isinstance(
            qdate, QDate
        ):
            qdate = QDate(qdate.year, qdate.month, qdate.day)
        if qdate is None and self._allow_blank:
            self._has_value = False
            self._is_formatting = True
            self.setText("")
            self._is_formatting = False
            return

        if qdate is None:
            qdate = QDate.currentDate()

        # clamp to range
        if qdate < self._min_date:
            qdate = self._min_date
        elif qdate > self._max_date:
            qdate = self._max_date

        self._current_date = qdate
        self._has_value = True
        self._is_formatting = True
        if self._special_value_text and qdate == self._min_date:
            self.setText(self._special_value_text)
        else:
            self.setText(qdate.toString(self.display_format))
        self._is_formatting = False
        # Emit compatibility signal
        self.dateChanged.emit(self._current_date)

    def date(self) -> QDate | None:
        return self._current_date if self._has_value else None

    # New helper used elsewhere in app
    def getDate(self) -> QDate | None:
        return self._current_date if self._has_value else None

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        if self._select_all_on_click:
            QTimer.singleShot(0, self.selectAll)

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        if self._select_all_on_click:
            QTimer.singleShot(0, self.selectAll)

    def keyPressEvent(self, event) -> None:
        # Support +/- day adjustments
        if event.key() == Qt.Key.Key_Plus:
            self.setDate(self._current_date.addDays(1))
            return
        if event.key() == Qt.Key.Key_Minus:
            self.setDate(self._current_date.addDays(-1))
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self._validate_final()

    def _on_text_changed(self, text: str) -> None:
        if self._is_formatting:
            return
        if self._allow_blank and not text.strip():
            self._has_value = False
        # Leave text untouched while typing; normalize only on focus-out.

    def _validate_final(self) -> None:
        try:
            text = self.text().strip()
            if not text:
                if self._allow_blank:
                    self._has_value = False
                    self._is_formatting = True
                    self.setText("")
                    self._is_formatting = False
                    return
                self._is_formatting = True
                if (
                    self._special_value_text
                    and self._current_date == self._min_date
                ):
                    self.setText(self._special_value_text)
                else:
                    self.setText(
                        self._current_date.toString(self.display_format)
                    )
                self._is_formatting = False
                return
            parsed = self._parse_date_text(text)
            if parsed.isValid():
                changed = parsed != self._current_date
                self._current_date = parsed
                self._has_value = True
                self._is_formatting = True
                if self._special_value_text and parsed == self._min_date:
                    self.setText(self._special_value_text)
                else:
                    self.setText(parsed.toString(self.display_format))
                self._is_formatting = False
                if changed:
                    self.dateChanged.emit(self._current_date)
            else:
                # restore previous on failure and explain why
                self.setToolTip(describe_invalid_date(text))
                self._is_formatting = True
                if (
                    self._special_value_text
                    and self._current_date == self._min_date
                ):
                    self.setText(self._special_value_text)
                else:
                    self.setText(
                        self._current_date.toString(self.display_format)
                    )
                self._is_formatting = False
        except Exception:
            self._is_formatting = False

    @staticmethod
    def _parse_date_text(text: str) -> QDate:
        return parse_flexible_date(text)

    # QDateEdit compatibility helpers
    def setSpecialValueText(self, text: str) -> None:
        self._special_value_text = text
        # refresh display to reflect special text possibly
        self._is_formatting = True
        if self._current_date == self._min_date and text:
            self.setText(text)
        else:
            self.setText(self._current_date.toString(self.display_format))
        self._is_formatting = False

    def specialValueText(self) -> str | None:
        return self._special_value_text

    def setMinimumDate(self, qdate: QDate) -> None:
        self._min_date = qdate
        # Clamp current date
        if self._current_date < qdate:
            self.setDate(qdate)

    def setMaximumDate(self, qdate: QDate) -> None:
        self._max_date = qdate
        if self._current_date > qdate:
            self.setDate(qdate)

    def setDateRange(self, min_date: QDate, max_date: QDate) -> None:
        self._min_date = min_date
        self._max_date = max_date
        if self._current_date < min_date:
            self.setDate(min_date)
        elif self._current_date > max_date:
            self.setDate(max_date)


class SimpleCalculator(QDialog):
    """Simple calculator dialog with number pad for currency input"""

    def __init__(self, initial_value=0.0, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calculator")
        self.setMinimumWidth(300)
        self.setMinimumHeight(400)
        self.display_value = (
            str(initial_value) if initial_value != 0.0 else "0"
        )
        self.pending_operation = None
        self.pending_value = None
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Display
        self.display = QLineEdit()
        self.display.setReadOnly(True)
        self.display.setText(self.display_value)
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight)
        display_font = QFont()
        display_font.setPointSize(18)
        display_font.setBold(True)
        self.display.setFont(display_font)
        self.display.setStyleSheet(
            "padding: 10px; background-color: #f0f0f0; border: 2px solid #333;"
        )
        layout.addWidget(self.display)

        # Button grid
        grid = QGridLayout()
        grid.setSpacing(5)

        buttons = [
            ("7", 0, 0),
            ("8", 0, 1),
            ("9", 0, 2),
            ("÷", 0, 3),
            ("4", 1, 0),
            ("5", 1, 1),
            ("6", 1, 2),
            ("×", 1, 3),
            ("1", 2, 0),
            ("2", 2, 1),
            ("3", 2, 2),
            ("-", 2, 3),
            ("0", 3, 0),
            (".", 3, 1),
            ("C", 3, 2),
            ("+", 3, 3),
            ("=", 4, 0, 1, 4),  # Equals spans 4 columns
        ]

        for btn_data in buttons:
            if len(btn_data) == 5:  # Spanning button
                text, row, col, rowspan, colspan = btn_data
            else:
                text, row, col = btn_data
                rowspan, colspan = 1, 1

            btn = QPushButton(text)
            btn.setMinimumHeight(50)
            btn.setStyleSheet("font-size: 16px; font-weight: bold;")
            btn.clicked.connect(lambda checked, t=text: self.button_clicked(t))
            grid.addWidget(btn, row, col, rowspan, colspan)

        layout.addLayout(grid)

    def button_clicked(self, text) -> None:
        """Handle button clicks"""
        if text.isdigit():
            if self.display_value == "0" or self.pending_operation == "=":
                self.display_value = text
                if self.pending_operation == "=":
                    self.pending_operation = None
            else:
                self.display_value += text

        elif text == ".":
            if "." not in self.display_value:
                self.display_value += "."

        elif text == "C":
            self.display_value = "0"
            self.pending_operation = None
            self.pending_value = None

        elif text in ["+", "-", "×", "÷"]:
            if self.pending_operation and self.pending_value is not None:
                self.calculate()
            self.pending_value = float(self.display_value)
            self.pending_operation = text
            self.display_value = "0"

        elif text == "=":
            self.calculate()
            self.pending_operation = "="

        self.display.setText(self.display_value)

    def calculate(self) -> None:
        """Perform calculation"""
        if self.pending_operation is None or self.pending_value is None:
            return

        try:
            current = float(self.display_value)
            if self.pending_operation == "+":
                result = self.pending_value + current
            elif self.pending_operation == "-":
                result = self.pending_value - current
            elif self.pending_operation == "×":
                result = self.pending_value * current
            elif self.pending_operation == "÷":
                result = self.pending_value / current if current != 0 else 0
            else:
                return

            self.display_value = f"{result:.2f}"
            self.pending_value = result
        except Exception:
            self.display_value = "ERROR"

    def get_result(self) -> object:
        """Get final result"""
        try:
            return float(self.display_value)
        except Exception:
            return 0.0


class CalculatorButton(QPushButton):
    """Calculator button that opens calculator dialog for a currency input"""

    def __init__(self, currency_input, parent=None) -> None:
        super().__init__("🧮", parent)
        self.currency_input = currency_input
        self.setMaximumWidth(30)
        self.setToolTip("Open Calculator")
        self.clicked.connect(self.open_calculator)

    def open_calculator(self) -> None:
        """Open calculator dialog"""
        initial_value = self.currency_input.get_value()
        calc = SimpleCalculator(initial_value, self)
        if calc.exec() == QDialog.DialogCode.Accepted:
            result = calc.get_result()
            self.currency_input.set_value(result)


class StandardTextEdit(QTextEdit):
    """
    Standardized multi-line text input with:
    - Consistent font (Segoe UI, 9pt)
    - Plain text only (strips formatting on paste)
    - Optional height constraint
    """

    def __init__(self, parent=None, max_height=None) -> None:
        super().__init__(parent)

        # Set standard font
        font = QFont("Segoe UI", 9)
        self.setFont(font)

        # Disable rich text to strip formatting on paste
        self.setAcceptRichText(False)

        # Optional height limit
        if max_height:
            self.setMaximumHeight(max_height)

        # Tooltip
        self.setToolTip(
            "<b>📝 Text Input</b><br>"
            "Multi-line text field.<br>"
            "Pasted content will be converted to plain text."
        )
