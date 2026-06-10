"""
Custom form widgets with smart validation, autocomplete, and formatting.

Widgets:
- VendorSelector: Smart vendor combobox with autocomplete and historical lookup
- DateInput: Flexible date input accepting multiple formats
- CurrencyInput: Currency input with validation and formatting
- AmountSpinBox: QDoubleSpinBox with select-all on focus
"""

import logging

from db_error_handling import DatabaseContext
from PyQt6.QtCore import QDate, Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDoubleSpinBox,
    QLineEdit,
)

logger = logging.getLogger(__name__)


class VendorSelector(QComboBox):
    """Smart vendor selector with autocomplete, historical category/GL"
    "lookup, validation colors"""

    def __init__(self, db_conn, parent=None) -> None:
        super().__init__(parent)
        self.db_conn = db_conn
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        # Track selected vendor data
        self.selected_vendor = None
        self.suggested_category = None
        self.suggested_gl_code = None

        # Validation color support
        self._validation_state = "neutral"
        self.lineEdit().setToolTip(
            "<b>🏢 Vendor Name</b><br>"
            "Select from approved vendors. Type to search.<br>"
            "Names auto-normalize to UPPERCASE.<br>"
            "<font color='green'>✓ Valid</font> when selected from list.<br>"
            "<font color='blue'>✓ Keyboard:</font> Down arrow to list, type"
            "to filter"
        )

        self.vendors = []
        self.load_vendor_list()
        self.currentTextChanged.connect(self._on_vendor_changed)
        self.lineEdit().textChanged.connect(self._update_validation_color)

    def load_vendor_list(self) -> None:
        """Load approved vendor list from vendor_accounts (the master clean"
        "list)"""

        try:
            with DatabaseContext(self.db_conn, auto_commit=False) as cur:
                cur.execute("""
                    SELECT canonical_vendor
                    FROM vendor_accounts
                    WHERE canonical_vendor IS NOT NULL
                    ORDER BY canonical_vendor
                """)
                vendors = [row[0] for row in cur.fetchall()]

            self.vendors = vendors
            self.clear()
            self.addItems(vendors)
            # Smart autocomplete (contains, case-insensitive)
            completer = QCompleter(self.vendors)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCompletionMode(
                QCompleter.CompletionMode.PopupCompletion
            )
            self.setCompleter(completer)
        except Exception as e:
            logger.error(f"Error loading vendor list: {e}")
            print(f"Error loading vendor list: {e}")

    def _update_validation_color(self) -> None:
        """Update field color based on validation state"""
        text = self.lineEdit().text()
        if not text:
            self._set_field_style("neutral")  # Gray - empty/optional
            return

        # Check if text is in vendor list (valid if exact match)
        vendor_upper = text.upper()
        is_in_list = any(
            vendor_upper == self.itemText(i).upper()
            for i in range(self.count())
        )

        if is_in_list:
            self._set_field_style("valid")  # Green - valid
        else:
            # Yellow - not in list but might be typed
            self._set_field_style("warning")

    def _set_field_style(self, state) -> None:
        """Apply color style to field based on validation state"""
        self._validation_state = state
        line_edit = self.lineEdit()

        if state == "valid":
            # Green border and subtle green background
            line_edit.setStyleSheet(
                "QLineEdit { border: 2px solid #4CAF50; background-color:"
                "#f0fdf4;}"
            )
        elif state == "warning":
            # Yellow border and subtle yellow background
            line_edit.setStyleSheet(
                "QLineEdit { border: 2px solid #FFC107; background-color:"
                "#fffbf0;}"
            )
        elif state == "error":
            # Red border and subtle red background
            line_edit.setStyleSheet(
                "QLineEdit { border: 2px solid #f44336; background-color:"
                "#fdf0f0;}"
            )
        else:  # neutral
            # Gray border and normal background
            line_edit.setStyleSheet(
                "QLineEdit { border: 1px solid #ccc; background-color: white;}"
            )

    def _on_vendor_changed(self, text) -> None:
        """When vendor changes, lookup historical category and GL code"""
        if not text:
            self.selected_vendor = None
            self.suggested_category = None
            self.suggested_gl_code = None
            self._update_validation_color()
            return

        # Normalize to uppercase
        vendor_upper = text.upper()
        self.blockSignals(True)
        self.lineEdit().setText(vendor_upper)
        self.blockSignals(False)

        # Lookup historical data for this vendor
        self._lookup_vendor_history(vendor_upper)
        self._update_validation_color()

    def _lookup_vendor_history(self, vendor) -> None:
        """Find default GL code and category for this vendor.
        Priority: 1) vendor_accounts.default_gl_code  2) most common from
        receipt history
        """
        try:
            with DatabaseContext(self.db_conn, auto_commit=False) as cur:
                # 1. Check vendor_accounts for a defined default
                cur.execute(
                    """
                    SELECT default_gl_code, default_category
                    FROM vendor_accounts
                    WHERE canonical_vendor = %s
                    LIMIT 1
                """,
                    (vendor,),
                )
                row = cur.fetchone()
                if row and row[0]:
                    self.suggested_gl_code = row[0]
                    self.suggested_category = row[1]
                    self.selected_vendor = vendor
                    return

                # 2. Fall back to most common values in receipt history
                cur.execute(
                    """
                    SELECT category, COUNT(*) AS cnt
                    FROM receipts
                    WHERE canonical_vendor = %s AND category IS NOT NULL
                    GROUP BY category ORDER BY cnt DESC LIMIT 1
                """,
                    (vendor,),
                )
                result = cur.fetchone()
                self.suggested_category = result[0] if result else None

                cur.execute(
                    """
                    SELECT gl_account_code, COUNT(*) AS cnt
                    FROM receipts
                    WHERE canonical_vendor = %s AND gl_account_code IS NOT NULL
                    GROUP BY gl_account_code ORDER BY cnt DESC LIMIT 1
                """,
                    (vendor,),
                )
                result = cur.fetchone()
                self.suggested_gl_code = result[0] if result else None

            self.selected_vendor = vendor

        except Exception as e:
            logger.error(f"Error looking up vendor history: {e}")
            print(f"Error looking up vendor history: {e}")

    def get_vendor(self) -> object:
        """Get normalized vendor name (uppercase)"""
        return self.lineEdit().text().upper()

    def get_suggested_category(self) -> object:
        """Get historically most common category for this vendor"""
        return self.suggested_category

    def get_suggested_gl_code(self) -> object:
        """Get historically most common GL code for this vendor"""
        return self.suggested_gl_code


class DateInput(QLineEdit):
    """Flexible date input field that accepts multiple formats like Excel"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        today = QDate.currentDate()
        self._current_date = today
        self.setText(today.toString("MM/dd/yyyy"))
        self.setPlaceholderText("MM/DD/YYYY or Jan 01 2012")
        self.setMaxLength(50)  # Allow long text formats

        # Validation color support
        self._validation_state = "valid"
        self.setStyleSheet(
            "QLineEdit { border: 1px solid #ccc; background-color: white;}"
        )

        # Rich tooltip with format examples
        self.setToolTip(
            "<b>📅 Date Input</b><br>"
            "<font color='green'><b>Flexible formats:</b></font><br>"
            "• 01/15/2012 or 01-15-2012<br>"
            "• Jan 01 2012 or January 1 2012<br>"
            "• 20120115 (compact)<br>"
            "• 2012-01-15 (ISO)<br>"
            "<font color='blue'><b>Shortcuts:</b> t=today,"
            "y=yesterday</font><br>"
            "Just type and press Enter or Tab"
        )

    def setDate(self, date) -> None:
        """Set date and update display"""
        self._current_date = date
        self.setText(date.toString("MM/dd/yyyy"))

    def getDate(self) -> object:
        """Get current date as QDate"""
        return self._current_date

    def focusInEvent(self, event) -> None:
        """Select all text when field gets focus for easy replacement"""
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def mouseDoubleClickEvent(self, event) -> None:
        """Allow double-click to position cursor for editing"""
        # Don't select all on double-click, let user position cursor
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event) -> None:
        """Parse and format when user leaves the field"""
        super().focusOutEvent(event)
        self._parse_and_format()

    def keyPressEvent(self, event) -> None:
        """Handle shortcuts and Enter key"""
        text = self.text().strip()

        # Shortcuts
        if text.lower() == "t" and event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Tab,
        ):
            self.setDate(QDate.currentDate())
            self._set_field_style("valid")
            event.accept()
            return
        elif text.lower() == "y" and event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Tab,
        ):
            self.setDate(QDate.currentDate().addDays(-1))
            self._set_field_style("valid")
            event.accept()
            return

        super().keyPressEvent(event)

    def _parse_and_format(self) -> None:
        """Parse flexible date formats and format for database storage"""
        text = self.text().strip()

        if not text:
            self.setText(self._current_date.toString("MM/dd/yyyy"))
            self._set_field_style("neutral")
            return

        # Try multiple formats
        parsed = None

        # Format 1: MM/dd/yyyy or MM-dd-yyyy
        for fmt in ["MM/dd/yyyy", "MM-dd-yyyy", "M/d/yyyy", "M-d-yyyy"]:
            parsed = QDate.fromString(text, fmt)
            if parsed.isValid():
                break

        # Format 2: yyyymmdd (compact)
        if not parsed or not parsed.isValid():
            if len(text) == 8 and text.isdigit():
                parsed = QDate.fromString(text, "yyyyMMdd")

        # Format 3: "Jan 01 2012" or "January 1 2012"
        if not parsed or not parsed.isValid():
            for fmt in [
                "MMM dd yyyy",
                "MMMM d yyyy",
                "MMM d yyyy",
                "MMMM dd yyyy",
            ]:
                parsed = QDate.fromString(text, fmt)
                if parsed.isValid():
                    break

        # Format 4: "01 Jan 2012" (day first)
        if not parsed or not parsed.isValid():
            for fmt in [
                "dd MMM yyyy",
                "d MMM yyyy",
                "dd MMMM yyyy",
                "d MMMM yyyy",
            ]:
                parsed = QDate.fromString(text, fmt)
                if parsed.isValid():
                    break

        # Format 5: ISO format yyyy-MM-dd
        if not parsed or not parsed.isValid():
            parsed = QDate.fromString(text, "yyyy-MM-dd")

        # If valid, update and format
        if parsed and parsed.isValid():
            self._current_date = parsed
            self.setText(parsed.toString("MM/dd/yyyy"))
            self._set_field_style("valid")
        else:
            # Invalid date - restore previous
            self.setText(self._current_date.toString("MM/dd/yyyy"))
            self._set_field_style("error")
            QTimer.singleShot(2000, lambda: self._set_field_style("neutral"))

    def _set_field_style(self, state) -> None:
        """Apply color style based on validation state"""
        self._validation_state = state
        if state == "valid":
            self.setStyleSheet(
                "QLineEdit { border: 2px solid #4CAF50; background-color:"
                "#f0fdf4;}"
            )
        elif state == "warning":
            self.setStyleSheet(
                "QLineEdit { border: 2px solid #FFC107; background-color:"
                "#fffbf0;}"
            )
        elif state == "error":
            self.setStyleSheet(
                "QLineEdit { border: 2px solid #f44336; background-color:"
                "#fdf0f0;}"
            )
        else:  # neutral
            self.setStyleSheet(
                "QLineEdit { border: 1px solid #ccc; background-color: white;}"
            )


class CurrencyInput(QLineEdit):
    """Custom currency input field with validation colors and helpful"
    "tooltips"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setPlaceholderText("0.00")
        self.setText("0.00")
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        # Up to $999,999.99 (15 chars max with formatting buffer)
        self.setMaxLength(15)
        self.setMinimumWidth(150)  # Standard width for currency fields
        self.setMaximumWidth(200)  # Cap the max width
        self._is_formatting = False  # Flag to prevent recursive formatting
        self.textChanged.connect(self._on_text_changed)

        # Validation color support
        self._validation_state = "valid"
        self.setStyleSheet(
            "QLineEdit { border: 1px solid #ccc; background-color: white;"
            "text-align: right;}"
        )

        # Rich tooltip with currency examples
        self.setToolTip(
            "<b>💵 Currency Input</b><br>"
            "Enter amounts in any format:<br>"
            "<font color='green'><b>✓ Valid formats:</b></font><br>"
            "• 10 → $10.00<br>"
            "• 10.50 → $10.50<br>"
            "• .50 → $0.50<br>"
            "• 250 → $250.00<br>"
            "<font color='blue'><b>Limits:</b> $0.00 - $999,999.99</font><br>"
            "Auto-formats to 2 decimal places."
        )

    def focusInEvent(self, event) -> None:
        """Select all text when field gets focus"""
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def mouseDoubleClickEvent(self, event) -> None:
        """Allow double-click to position cursor for editing"""
        # Don't select all - let user position cursor for editing
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event) -> None:
        """Format when leaving the field"""
        super().focusOutEvent(event)
        if self.text().strip():
            self._do_format()

    def keyPressEvent(self, event) -> None:
        """Handle Enter key to move to next field"""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Format the value first
            if self.text().strip():
                self._do_format()
            # Move to next widget
            self.focusNextChild()
            event.accept()
            return
        super().keyPressEvent(event)

    def _set_field_style(self, state) -> None:
        """Apply color style based on validation state"""
        self._validation_state = state
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

    def _on_text_changed(self) -> None:
        """Handle text changes - validate on focus out, not during typing"""
        # Just validate the input as the user types, don't reformat yet
        text = self.text()
        if text == "":
            return

        # Quick validation: only allow digits and one decimal point
        cleaned = ""
        decimal_count = 0
        for char in text:
            if char.isdigit():
                cleaned += char
            elif char == "." and decimal_count == 0:
                cleaned += char
                decimal_count += 1

        # If the cleaned version is different, update it (removes invalid
        # chars)
        if cleaned != text and cleaned != "":
            self._is_formatting = True
            self.setText(cleaned)
            self._is_formatting = False

    def _do_format(self) -> None:
        """
        Format currency with validation colors: 10→10.00, 10.10→10.10,
        .50→0.50, 1706.25→1706.25
        Validates against currency column requirements (0-999,999.99)
        """
        text = self.text()
        if not text:
            self._set_field_style("neutral")
            return

        # Remove any non-numeric characters except decimal point
        cleaned = ""
        decimal_count = 0

        for char in text:
            if char.isdigit():
                cleaned += char
            elif char == "." and decimal_count == 0:
                cleaned += char
                decimal_count += 1

        if not cleaned:
            self._set_field_style("neutral")
            return

        # If user typed a decimal point, respect it (they know what they want)
        if "." in cleaned:
            parts = cleaned.split(".")
            dollars = parts[0] or "0"  # Handle ".03" case
            cents = (
                parts[1][:2] if len(parts) > 1 else "00"
            )  # Limit to 2 decimals

            # Pad cents with zeros if needed (e.g., ".1" → "0.10")
            cents = cents.ljust(2, "0")
            formatted = f"{dollars}.{cents}"
        else:
            # No decimal typed - user meant dollars, not cents
            formatted = f"{cleaned}.00"

        # Validate against column max (999,999.99)
        try:
            amount = float(formatted)
            if amount > 999999.99:
                # Truncate to max
                formatted = "999999.99"
                self._set_field_style("warning")
            else:
                self._set_field_style("valid")
        except Exception:
            formatted = "0.00"
            self._set_field_style("error")

        self._is_formatting = True
        self.setText(formatted)
        self._is_formatting = False

    def get_value(self) -> object:
        """Get the numeric value as a string, validated"""
        text = self.text().strip()
        if not text or text == "0.00":
            return "0.00"
        try:
            amount = float(text)
            # Ensure within valid range (0 to 999,999.99)
            amount = max(0, min(999999.99, amount))
            return f"{amount:.2f}"
        except Exception:
            return "0.00"

    def setValue(self, value) -> None:
        """Set the numeric value (convenience method for QDoubleSpinBox"
        "compatibility)"""

        if isinstance(value, (int, float)):
            self.setText(f"{float(value):.2f}")
        else:
            self.setText(str(value))


class AmountSpinBox(QDoubleSpinBox):
    """Custom QDoubleSpinBox that selects all on focus/click for easy"
    "replacement"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setDecimals(2)
        self.setMaximum(999999.99)
        self.setMinimum(0.00)
        self.setPrefix("$")

    def focusInEvent(self, event) -> None:
        """Select all text when field gets focus"""
        super().focusInEvent(event)
        self.selectAll()

    def mousePressEvent(self, event) -> None:
        """Select all on any mouse click"""
        if not self.hasFocus():
            super().mousePressEvent(event)
        self.selectAll()
        event.accept()
