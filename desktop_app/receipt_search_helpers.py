from decimal import Decimal

from PyQt6.QtCore import QDate, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QDoubleValidator, QFont, QPainter
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QStyledItemDelegate,
    QTableWidgetItem,
    QVBoxLayout,
)


class NumericSortItem(QTableWidgetItem):
    """QTableWidgetItem that sorts by a stored numeric value."""

    def __init__(self, display_text: str, sort_value: float) -> None:
        super().__init__(display_text)
        self._sort_value = sort_value

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, NumericSortItem):
            return self._sort_value < other._sort_value
        try:
            return self._sort_value < float(other.text().replace("$", "").replace(",", ""))
        except (ValueError, AttributeError):
            return super().__lt__(other)


class DateInput(QLineEdit):
    """Flexible date input like Excel: supports multiple formats and shortcuts."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_date = QDate.currentDate()
        self.setText(self._current_date.toString("dd-MMM-yyyy"))
        self.setPlaceholderText("DD-Mon-YYYY or 31012013")
        self.setToolTip(
            "Displays: 17-Jan-2026. Accepts: 17/01/2026, 2026-01-17, 17012026,\n"
            "Jan 17 2026, 17 Jan 2026, January 17 2026, t (today), y (yesterday)"
        )
        self.textChanged.connect(self._on_text_changed)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        text = self.text().strip()
        parsed = self._parse_date(text)
        if parsed is not None:
            self.setDate(parsed)
        elif text:
            from common_widgets import describe_invalid_date

            self.setToolTip(describe_invalid_date(text))
            self.setDate(self._current_date)

    def _on_text_changed(self, text: str) -> None:
        parsed = self._parse_date(text.strip())
        if parsed is None:
            self.setStyleSheet("background-color: #ffecec; border: 1px solid #cc0000;")
        else:
            self._current_date = parsed
            self.setStyleSheet("background-color: #eaffea; border: 1px solid #00aa00;")

    def _parse_date(self, s: str) -> QDate | None:
        from common_widgets import parse_flexible_date

        parsed = parse_flexible_date(s)
        return parsed if parsed.isValid() else None

    def date(self) -> QDate:
        return self._current_date

    def setDate(self, qdate: QDate) -> None:
        if not isinstance(qdate, QDate):
            return
        self._current_date = qdate
        self.setText(qdate.toString("dd-MMM-yyyy"))


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
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def evaluate(self) -> Decimal | None:
        text = (self.input.text() or "").strip()
        if not text:
            return None
        allowed = set("0123456789.+-*/() ")
        if any(ch not in allowed for ch in text):
            return None
        try:
            result = eval(text, {"__builtins__": {}}, {})
            return Decimal(str(result))
        except Exception:
            return None


class CurrencyInput(QLineEdit):
    """Simple currency field with 2-decimal validation."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        validator = QDoubleValidator(-1_000_000_000.0, 1_000_000_000.0, 2, self)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.setValidator(validator)
        self.setPlaceholderText("0.00")
        self.setMaxLength(20)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def value(self) -> Decimal:
        text = (self.text() or "0").replace(",", "").strip()
        try:
            return Decimal(text)
        except Exception:
            return Decimal("0")


class ReceiptCompactDelegate(QStyledItemDelegate):
    """Renders a compact 4-line summary in the Vendor column."""

    def paint(self, painter: QPainter, option, index) -> None:
        if index.column() != 2:
            super().paint(painter, option, index)
            return
        try:
            data = index.data(Qt.ItemDataRole.UserRole) or {}
            date = data.get("date") or ""
            vendor = data.get("vendor") or ""
            amount = data.get("amount")
            amount_str = (
                f"${amount:,.2f}" if isinstance(amount, (int, float)) else (str(amount) if amount else "")
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

            lines = [
                f"{date} • {vendor} • {amount_str} • {gl}",
                desc,
                " • ".join([p for p in (matched_str, source_str, charter_str) if p]),
                payment_str,
            ]
            text = "\n".join([line for line in lines if line])

            painter.save()
            if option.state & option.StateFlag.State_Selected:
                painter.fillRect(option.rect, option.palette.highlight())
                pen_color = option.palette.highlightedText().color()
            else:
                pen_color = option.palette.text().color()

            base_font = option.font
            small_font = QFont(base_font)
            small_font.setPointSize(max(8, base_font.pointSize() - 1))
            painter.setFont(small_font)
            painter.setPen(pen_color)
            rect = option.rect.adjusted(6, 4, -6, -4)
            painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
            painter.restore()
        except Exception:
            super().paint(painter, option, index)

    def sizeHint(self, option, index) -> QSize:
        try:
            fm = option.fontMetrics
            return QSize(option.rect.width(), (fm.height() * 4) + 8)
        except Exception:
            return super().sizeHint(option, index)
