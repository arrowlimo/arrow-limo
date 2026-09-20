from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QDialog, QLineEdit, QPushButton, QHBoxLayout, QVBoxLayout


class CurrencyInput(QLineEdit):
    """Currency input field with validation (compact 6-digit max)."""

    def __init__(self, parent=None, compact=False) -> None:
        super().__init__(parent)
        self.setPlaceholderText("0.00")
        self.setText("0.00")
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.compact = compact
        if compact:
            self.setMaxLength(10)
            self.setMaximumWidth(100)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self.selectAll()

    def mousePressEvent(self, event) -> None:
        if not self.hasFocus():
            super().mousePressEvent(event)
        self.selectAll()
        event.accept()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self._format()

    def _format(self) -> None:
        text = self.text().replace(",", "").replace("$", "").strip()
        try:
            val = float(text)
            self.setText(f"{val:.2f}")
        except Exception:
            self.setText("0.00")

    def get_value(self) -> float:
        try:
            return float(self.text().replace(",", ""))
        except Exception:
            return 0.0


class SimpleCalculator(QDialog):
    """Simple calculator dialog with number pad."""

    def __init__(self, initial_value=0.0, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calculator")
        self.setMinimumWidth(300)
        self.setMinimumHeight(400)
        self.display_value = str(initial_value)
        self.pending_operation = None
        self.pending_value = None
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
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

        grid = QVBoxLayout()
        for row_buttons in (["7", "8", "9", "÷"], ["4", "5", "6", "×"], ["1", "2", "3", "−"]):
            row = QHBoxLayout()
            for btn_text in row_buttons:
                btn = QPushButton(btn_text)
                btn.setMinimumHeight(50)
                btn.setFont(QFont(pointSize=14, weight=QFont.Weight.Bold))
                btn.clicked.connect(lambda checked, t=btn_text: self._on_button_click(t))
                row.addWidget(btn)
            grid.addLayout(row)

        row4 = QHBoxLayout()
        for label in ("0", ".", "=", "+"):
            btn = QPushButton(label)
            btn.setMinimumHeight(50)
            btn.setFont(QFont(pointSize=14, weight=QFont.Weight.Bold))
            if label == "=":
                btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
                btn.clicked.connect(self._on_equals)
            else:
                btn.clicked.connect(lambda checked, t=label: self._on_button_click(t))
            row4.addWidget(btn)
        grid.addLayout(row4)
        layout.addLayout(grid)

        bottom_row = QHBoxLayout()
        clear_btn = QPushButton("C (Clear)")
        clear_btn.setMinimumHeight(40)
        clear_btn.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")
        clear_btn.clicked.connect(self._clear)
        bottom_row.addWidget(clear_btn)

        ok_btn = QPushButton("✓ OK")
        ok_btn.setMinimumHeight(40)
        ok_btn.setStyleSheet("background-color: #007bff; color: white; font-weight: bold;")
        ok_btn.clicked.connect(self.accept)
        bottom_row.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(40)
        cancel_btn.clicked.connect(self.reject)
        bottom_row.addWidget(cancel_btn)
        layout.addLayout(bottom_row)

    def _on_button_click(self, label: str) -> None:
        self.display.setText((self.display.text() or "") + label)

    def _on_equals(self) -> None:
        try:
            value = eval(self.display.text(), {"__builtins__": {}}, {})
            self.display.setText(str(value))
        except Exception:
            self.display.setText("0")

    def _clear(self) -> None:
        self.display.setText("0")
