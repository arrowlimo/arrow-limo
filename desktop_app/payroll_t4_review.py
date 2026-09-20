from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class T4ManualOverrideDialog(QDialog):
    def __init__(self, host, emp_id: int, tax_year: int, display_name: str, default_values: dict[str, float], actual_values: dict[str, float]) -> None:
        super().__init__(host)
        self._host = host
        self.emp_id = emp_id
        self.tax_year = tax_year
        self.setWindowTitle(f"T4 Manual Override - {tax_year}")
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        header = QLabel(
            f"Employee: {display_name} (ID {emp_id})\n"
            "Manual values saved here override payroll-calculated totals when printing Official T4."
        )
        header.setWordWrap(True)
        header.setStyleSheet("color: #1f2937;")
        layout.addWidget(header)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.fields: dict[str, QDoubleSpinBox] = {}
        self.compare_labels: dict[str, QLabel] = {}
        for key, label in (
            ("box14", "Box 14 - Employment Income"),
            ("box16", "Box 16 - CPP Employee"),
            ("box18", "Box 18 - EI Employee"),
            ("box22", "Box 22 - Income Tax"),
            ("box24", "Box 24 - EI Insurable"),
            ("box26", "Box 26 - CPP Pensionable"),
            ("box44", "Box 44 - Union Dues"),
            ("box46", "Box 46 - Other Remuneration"),
            ("box52", "Box 52 - Pension Adjustment"),
        ):
            field = QDoubleSpinBox()
            field.setMaximum(99_999_999.99)
            field.setValue(float(default_values.get(key, 0.0) or 0.0))
            self.fields[key] = field

            actual_label = QLabel(f"Actual: ${float(actual_values.get(key, 0.0) or 0.0):,.2f}")
            actual_label.setStyleSheet("color: #1f2937; font-weight: bold;")

            compare_label = QLabel("")
            self.compare_labels[key] = compare_label

            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            row_layout.addWidget(field)
            row_layout.addWidget(actual_label)
            row_layout.addWidget(compare_label)
            row_layout.addStretch(1)
            form.addRow(f"{label}:", row_widget)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Reason for adjustment.")
        self.notes_edit.setMaximumHeight(100)
        self.notes_edit.setPlainText(str(default_values.get("notes", "") or ""))
        form.addRow("Notes:", self.notes_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.confirm_btn = QPushButton("Save & Confirm as Source of Truth")
        self.confirm_btn.setStyleSheet("background-color: #065f46; color: white;")
        buttons.addButton(self.confirm_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.confirmed = False
        self.confirm_btn.clicked.connect(lambda: setattr(self, "confirmed", True))
        for key, field in self.fields.items():
            field.valueChanged.connect(lambda _value, k=key: self._refresh_compare_label(k, actual_values))
            self._refresh_compare_label(key, actual_values)

    def _refresh_compare_label(self, box_key: str, actual_values: dict[str, float]) -> None:
        entered_value = float(self.fields[box_key].value())
        actual_value = float(actual_values.get(box_key, 0.0) or 0.0)
        delta = entered_value - actual_value
        if self._host._is_value_match(entered_value, actual_value):
            self.compare_labels[box_key].setText("MATCH")
            self.compare_labels[box_key].setStyleSheet("color: #065f46; font-weight: bold;")
        else:
            self.compare_labels[box_key].setText(f"DIFF {delta:+,.2f}")
            self.compare_labels[box_key].setStyleSheet("color: #b91c1c; font-weight: bold;")

    def values(self) -> dict[str, float]:
        return {key: float(widget.value()) for key, widget in self.fields.items()}

    def notes(self) -> str:
        return self.notes_edit.toPlainText().strip()


def build_t4_readiness_lines(payload: dict, emp_id: int) -> list[str]:
    readiness_lines = [
        f"Employee: {payload['full_name'] or emp_id}",
        f"Tax Year: {payload['tax_year']}",
        "",
        f"SIN: {'OK' if payload['sin_ok'] else 'MISSING/INVALID'}",
        f"Address: {'OK' if payload['address_ok'] else 'INCOMPLETE'}",
        f"Payroll rows in year: {payload['payroll_rows']}",
        f"Distinct pay periods loaded: {payload['period_count']}",
        "Year gross currently loaded (T4 Box 14): "
        f"${payload['gross_sum']:,.2f}",
    ]

    if payload["payroll_rows"] == 0:
        readiness_lines.append("")
        readiness_lines.append("No payroll rows found for this year.")
    elif payload["period_count"] <= 1:
        readiness_lines.append("")
        readiness_lines.append(
            "Only one pay period is loaded; T4 may look like January-only totals."
        )

    return readiness_lines
