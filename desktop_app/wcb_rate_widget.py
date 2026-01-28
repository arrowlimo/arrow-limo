"""
WCB Premium Rate Management Widget
Allows creating, editing, saving, and printing WCB Alberta premium rates
stored in wcb_ab_premium_rates (year + industry_code primary key).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextDocument
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFormLayout,
    QSpinBox,
    QLineEdit,
    QDoubleSpinBox,
    QPushButton,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QGroupBox,
)
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog


class WCBRateEntryWidget(QWidget):
    """Create, edit, save, and print WCB premium rates."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._build_ui()
        self.load_rates()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel("<h2>🛡️ WCB Premium Rates</h2>")
        header.setStyleSheet("padding: 6px; color: #1f2937;")
        layout.addWidget(header)

        layout.addWidget(QLabel("Create or edit WCB Alberta premium rates (per $100 of insurable earnings)."))

        form_group = QGroupBox("Rate Details")
        form = QFormLayout(form_group)

        self.year_spin = QSpinBox()
        self.year_spin.setRange(2005, 2040)
        self.year_spin.setValue(2025)

        self.industry_input = QLineEdit("74100")
        self.description_input = QLineEdit("Charter / Limousine Services")

        self.base_rate_spin = QDoubleSpinBox()
        self.base_rate_spin.setDecimals(4)
        self.base_rate_spin.setRange(0.0, 50.0)
        self.base_rate_spin.setSingleStep(0.01)
        self.base_rate_spin.setPrefix("$")

        self.exp_rate_spin = QDoubleSpinBox()
        self.exp_rate_spin.setDecimals(4)
        self.exp_rate_spin.setRange(0.0, 50.0)
        self.exp_rate_spin.setSingleStep(0.01)
        self.exp_rate_spin.setPrefix("$")

        form.addRow("Year", self.year_spin)
        form.addRow("Industry Code", self.industry_input)
        form.addRow("Description", self.description_input)
        form.addRow("Base Rate / $100", self.base_rate_spin)
        form.addRow("Experience Rate / $100", self.exp_rate_spin)

        layout.addWidget(form_group)

        btn_row = QHBoxLayout()
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self.load_entry)
        btn_row.addWidget(load_btn)

        save_btn = QPushButton("Save / Upsert")
        save_btn.setStyleSheet("background-color: #2563eb; color: white;")
        save_btn.clicked.connect(self.save_entry)
        btn_row.addWidget(save_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.setStyleSheet("background-color: #dc2626; color: white;")
        delete_btn.clicked.connect(self.delete_entry)
        btn_row.addWidget(delete_btn)

        print_btn = QPushButton("Print")
        print_btn.clicked.connect(self.print_entry)
        btn_row.addWidget(print_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #2563eb; font-weight: bold;")
        layout.addWidget(self.status_label)

        table_group = QGroupBox("Existing Rates")
        table_layout = QVBoxLayout(table_group)
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Year", "Industry", "Base / $100", "Experience / $100", "Description"
        ])
        self.table.cellDoubleClicked.connect(self._load_from_table)
        table_layout.addWidget(self.table)
        layout.addWidget(table_group)

    def _set_status(self, text, error=False):
        if error:
            self.status_label.setStyleSheet("color: #dc2626; font-weight: bold;")
        else:
            self.status_label.setStyleSheet("color: #2563eb; font-weight: bold;")
        self.status_label.setText(text)

    def load_rates(self):
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                try:
                    self.db.rollback()
                except:
                    pass
                pass
            
            cur = self.db.get_cursor()
            cur.execute(
                """
                SELECT year, industry_code, base_premium_rate_per_100, experience_adjusted_rate_per_100, description
                FROM wcb_ab_premium_rates
                ORDER BY year DESC, industry_code
                """
            )
            rows = cur.fetchall()
            self.table.setRowCount(len(rows))
            for idx, (yr, code, base, exp, desc) in enumerate(rows):
                for col, val in enumerate([
                    yr,
                    code,
                    f"{float(base):.4f}" if base is not None else "",
                    f"{float(exp):.4f}" if exp is not None else "",
                    desc or "",
                ]):
                    item = QTableWidgetItem(str(val))
                    item.setData(Qt.ItemDataRole.UserRole, (yr, code))
                    self.table.setItem(idx, col, item)
            self._set_status(f"Loaded {len(rows)} rate rows.")
        except Exception as exc:
            try:
                self.db.rollback()
            except:
                pass
            self._set_status(f"Failed to load rates: {exc}", error=True)

    def _load_from_table(self, row, column):
        item = self.table.item(row, 0)
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        yr, code = data
        self.year_spin.setValue(int(yr))
        self.industry_input.setText(str(code))
        self.load_entry()

    def load_entry(self):
        year = self.year_spin.value()
        code = self.industry_input.text().strip()
        if not code:
            QMessageBox.warning(self, "Missing Code", "Enter an industry code.")
            return

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                try:
                    self.db.rollback()
                except:
                    pass
                pass
            
            cur = self.db.get_cursor()
            cur.execute(
                """
                SELECT base_premium_rate_per_100, experience_adjusted_rate_per_100, description
                FROM wcb_ab_premium_rates
                WHERE year = %s AND industry_code = %s
                LIMIT 1
                """,
                (year, code),
            )
            row = cur.fetchone()
            if not row:
                self.base_rate_spin.setValue(0)
                self.exp_rate_spin.setValue(0)
                self.description_input.setText("")
                self._set_status("No record found. Enter details and Save to create.")
                return

            base, exp, desc = row
            self.base_rate_spin.setValue(float(base or 0))
            self.exp_rate_spin.setValue(float(exp or 0))
            self.description_input.setText(desc or "")
            self._set_status(f"Loaded {year} / {code}.")
        except Exception as exc:
            try:
                self.db.rollback()
            except:
                pass
            self._set_status(f"Failed to load entry: {exc}", error=True)

    def save_entry(self):
        year = self.year_spin.value()
        code = self.industry_input.text().strip()
        if not code:
            QMessageBox.warning(self, "Missing Code", "Enter an industry code.")
            return

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                try:
                    self.db.rollback()
                except:
                    pass
                pass
            
            cur = self.db.get_cursor()
            cur.execute(
                """
                INSERT INTO wcb_ab_premium_rates (
                    year, industry_code, description, base_premium_rate_per_100, experience_adjusted_rate_per_100
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (year, industry_code) DO UPDATE SET
                    description = EXCLUDED.description,
                    base_premium_rate_per_100 = EXCLUDED.base_premium_rate_per_100,
                    experience_adjusted_rate_per_100 = EXCLUDED.experience_adjusted_rate_per_100
                """,
                (
                    year,
                    code,
                    self.description_input.text().strip() or None,
                    self.base_rate_spin.value() or None,
                    self.exp_rate_spin.value() or None,
                ),
            )
            self.db.commit()
            self._set_status(f"Saved {year} / {code}.")
            self.load_rates()
        except Exception as exc:
            self.db.rollback()
            self._set_status(f"Failed to save: {exc}", error=True)

    def delete_entry(self):
        year = self.year_spin.value()
        code = self.industry_input.text().strip()
        if not code:
            QMessageBox.warning(self, "Missing Code", "Enter an industry code.")
            return

        confirm = QMessageBox.question(
            self,
            "Delete Rate",
            f"Delete WCB rate for {year} / {code}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                try:
                    self.db.rollback()
                except:
                    pass
                pass
            
            cur = self.db.get_cursor()
            cur.execute(
                "DELETE FROM wcb_ab_premium_rates WHERE year = %s AND industry_code = %s",
                (year, code),
            )
            self.db.commit()
            self._set_status(f"Deleted {year} / {code}.")
            self.load_rates()
        except Exception as exc:
            self.db.rollback()
            self._set_status(f"Failed to delete: {exc}", error=True)

    def print_entry(self):
        year = self.year_spin.value()
        code = self.industry_input.text().strip() or "(code missing)"
        base = f"${self.base_rate_spin.value():.4f} per $100"
        exp = self.exp_rate_spin.value()
        exp_txt = f"${exp:.4f} per $100" if exp else "(not set)"
        desc = self.description_input.text().strip() or ""

        summary = (
            f"WCB Premium Rate\n"
            f"Year: {year}\n"
            f"Industry Code: {code}\n"
            f"Description: {desc}\n"
            f"Base Rate: {base}\n"
            f"Experience Rate: {exp_txt}\n"
        )

        printer = QPrinter()
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QPrintDialog.DialogCode.Accepted:
            doc = QTextDocument()
            doc.setPlainText(summary)
            doc.print(printer)
            self._set_status("Printed current entry.")

