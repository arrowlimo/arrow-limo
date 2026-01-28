"""
Payroll Entry Widget
Manual payroll data entry and editing for employee_pay_master.
Allows selecting an employee and pay period, loading existing records, editing hours/pay/deductions,
and saving back with transaction safety.
"""

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QFormLayout,
    QDoubleSpinBox,
    QTextEdit,
    QMessageBox,
    QGroupBox,
    QAbstractSpinBox,
)


class PayrollEntryWidget(QWidget):
    """Manual payroll entry and edit form."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.pay_periods = []
        self.employee_lookup = {}
        self._build_ui()
        self.load_employees()
        current_year = QDate.currentDate().year()
        self._populate_years(current_year)
        self.load_pay_periods(current_year)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel("<h2>🧾 Payroll Entry</h2>")
        header.setStyleSheet("padding: 6px; color: #1f2937;")
        layout.addWidget(header)

        layout.addWidget(QLabel("Select an employee and pay period, load the record, edit fields, then save."))

        lookup = self._build_lookup_row()
        layout.addLayout(lookup)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #2563eb; font-weight: bold;")
        layout.addWidget(self.status_label)

        layout.addWidget(self._build_hours_group())
        layout.addWidget(self._build_pay_group())
        layout.addWidget(self._build_deductions_group())
        layout.addWidget(self._build_metadata_group())

        layout.addStretch()

    def _build_lookup_row(self):
        row = QHBoxLayout()

        self.employee_combo = QComboBox()
        self.employee_combo.setEditable(True)
        self.employee_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.employee_combo.setPlaceholderText("Employee")
        row.addWidget(QLabel("Employee:"))
        row.addWidget(self.employee_combo, stretch=2)

        self.year_combo = QComboBox()
        self.year_combo.currentTextChanged.connect(self._on_year_changed)
        row.addWidget(QLabel("Year:"))
        row.addWidget(self.year_combo)

        self.pay_period_combo = QComboBox()
        row.addWidget(QLabel("Pay Period:"))
        row.addWidget(self.pay_period_combo, stretch=2)

        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self.load_entry)
        row.addWidget(load_btn)

        self.save_btn = QPushButton("Save")
        self.save_btn.setStyleSheet("background-color: #2563eb; color: white;")
        self.save_btn.clicked.connect(self.save_entry)
        row.addWidget(self.save_btn)

        reset_btn = QPushButton("Clear")
        reset_btn.clicked.connect(self.clear_form)
        row.addWidget(reset_btn)

        recalc_btn = QPushButton("Recalculate")
        recalc_btn.clicked.connect(self.recalculate_totals)
        row.addWidget(recalc_btn)

        return row

    def _build_hours_group(self):
        group = QGroupBox("Hours & Rates")
        form = QFormLayout(group)

        self.charter_hours = self._spin(1_000, 2)
        self.approved_hours = self._spin(1_000, 2)
        self.overtime_hours = self._spin(1_000, 2)
        self.manual_hours_adjustment = self._spin(1_000, 2)
        self.total_hours_worked = self._spin(1_000, 2, read_only=True)
        self.hourly_rate = self._spin(1_000, 2)

        self.rate_source_combo = QComboBox()
        self.rate_source_combo.addItems(["employee_master", "charter_default", "manual_override"])

        form.addRow("Charter Hours", self.charter_hours)
        form.addRow("Approved Hours", self.approved_hours)
        form.addRow("Overtime Hours", self.overtime_hours)
        form.addRow("Manual Hours Adj", self.manual_hours_adjustment)
        form.addRow("Total Hours (auto)", self.total_hours_worked)
        form.addRow("Hourly Rate", self.hourly_rate)
        form.addRow("Rate Source", self.rate_source_combo)

        return group

    def _build_pay_group(self):
        group = QGroupBox("Pay Components")
        form = QFormLayout(group)

        self.base_pay = self._money_spin()
        self.gratuity_percent = self._spin(100, 2)
        self.gratuity_amount = self._money_spin()
        self.float_draw = self._money_spin()
        self.reimbursements = self._money_spin()
        self.other_income = self._money_spin()
        self.gross_pay = self._money_spin(read_only=True)

        form.addRow("Base Pay", self.base_pay)
        form.addRow("Gratuity %", self.gratuity_percent)
        form.addRow("Gratuity Amount", self.gratuity_amount)
        form.addRow("Float/Draw", self.float_draw)
        form.addRow("Reimbursements", self.reimbursements)
        form.addRow("Other Income", self.other_income)
        form.addRow("Gross (auto)", self.gross_pay)

        return group

    def _build_deductions_group(self):
        group = QGroupBox("Deductions & Net")
        form = QFormLayout(group)

        self.federal_tax = self._money_spin()
        self.provincial_tax = self._money_spin()
        self.cpp_employee = self._money_spin()
        self.ei_employee = self._money_spin()
        self.union_dues = self._money_spin()
        self.radio_dues = self._money_spin()
        self.voucher_deductions = self._money_spin()
        self.misc_deductions = self._money_spin()
        self.total_deductions = self._money_spin(read_only=True)
        self.net_pay = self._money_spin(read_only=True)

        form.addRow("Federal Tax", self.federal_tax)
        form.addRow("Provincial Tax", self.provincial_tax)
        form.addRow("CPP", self.cpp_employee)
        form.addRow("EI", self.ei_employee)
        form.addRow("Union Dues", self.union_dues)
        form.addRow("Radio Dues", self.radio_dues)
        form.addRow("Voucher Deduct", self.voucher_deductions)
        form.addRow("Misc Deductions", self.misc_deductions)
        form.addRow("Total Deductions (auto)", self.total_deductions)
        form.addRow("Net Pay (auto)", self.net_pay)

        return group

    def _build_metadata_group(self):
        group = QGroupBox("Data Quality & Notes")
        form = QFormLayout(group)

        self.data_completeness = self._spin(100, 2)
        self.data_completeness.setValue(100.0)
        self.data_source_combo = QComboBox()
        self.data_source_combo.addItems(["manual_entry", "charter_hours", "reconstructed", "mixed"])
        self.confidence_level = self._spin(100, 2)
        self.confidence_level.setValue(100.0)
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Optional notes or evidence for this pay entry...")

        form.addRow("Data Completeness %", self.data_completeness)
        form.addRow("Data Source", self.data_source_combo)
        form.addRow("Confidence %", self.confidence_level)
        form.addRow("Notes", self.notes_edit)

        return group

    def _money_spin(self, read_only=False):
        spin = QDoubleSpinBox()
        spin.setDecimals(2)
        spin.setMaximum(1_000_000.00)
        spin.setMinimum(0.00)
        spin.setPrefix("$")
        spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons if read_only else QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        spin.setReadOnly(read_only)
        return spin

    def _spin(self, maximum, decimals=0, read_only=False):
        spin = QDoubleSpinBox()
        spin.setDecimals(decimals)
        spin.setMaximum(maximum)
        spin.setMinimum(0)
        spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons if read_only else QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        spin.setReadOnly(read_only)
        return spin

    def _populate_years(self, default_year):
        years = list(range(2011, 2031))
        for yr in years:
            self.year_combo.addItem(str(yr))
        default_idx = self.year_combo.findText(str(default_year))
        if default_idx >= 0:
            self.year_combo.setCurrentIndex(default_idx)

    def _on_year_changed(self, text):
        try:
            year = int(text)
        except ValueError:
            return
        self.load_pay_periods(year)

    def load_employees(self):
        """Load employees into the combo box."""
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
                SELECT employee_id, COALESCE(employee_number, ''), COALESCE(full_name, '')
                FROM employees
                WHERE employment_status IS NULL OR employment_status != 'inactive'
                ORDER BY full_name
                LIMIT 500
                """
            )
            self.employee_combo.clear()
            self.employee_lookup = {}
            for emp_id, emp_num, name in cur.fetchall():
                label = f"{name} ({emp_num})" if emp_num else name
                self.employee_combo.addItem(label, emp_id)
                self.employee_lookup[emp_id] = label
        except Exception as exc:
            self._set_status(f"Failed to load employees: {exc}", error=True)

    def load_pay_periods(self, fiscal_year: int):
        """Load pay periods for selected year."""
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
                SELECT pay_period_id, period_number, period_start_date, period_end_date, pay_date
                FROM pay_periods
                WHERE fiscal_year = %s
                ORDER BY period_number
                """,
                (fiscal_year,),
            )
            self.pay_period_combo.clear()
            self.pay_periods = []
            for pp_id, num, start, end, pay in cur.fetchall():
                label = f"P{num:02d} • {start} → {end} (Pay {pay})"
                self.pay_period_combo.addItem(label, pp_id)
                self.pay_periods.append((pp_id, fiscal_year, num, start, end, pay))
            if self.pay_period_combo.count() > 0:
                self.pay_period_combo.setCurrentIndex(0)
        except Exception as exc:
            try:
                self.db.rollback()
            except:
                pass
            self._set_status(f"Failed to load pay periods: {exc}", error=True)

    def _selected_employee_id(self):
        return self.employee_combo.currentData()

    def _selected_pay_period(self):
        idx = self.pay_period_combo.currentIndex()
        if idx < 0:
            return None
        pp_id = self.pay_period_combo.itemData(idx)
        for pp in self.pay_periods:
            if pp[0] == pp_id:
                return pp
        return None

    def clear_form(self):
        """Reset fields to zero/defaults."""
        for spin in [
            self.charter_hours,
            self.approved_hours,
            self.overtime_hours,
            self.manual_hours_adjustment,
            self.total_hours_worked,
            self.hourly_rate,
            self.base_pay,
            self.gratuity_percent,
            self.gratuity_amount,
            self.float_draw,
            self.reimbursements,
            self.other_income,
            self.gross_pay,
            self.federal_tax,
            self.provincial_tax,
            self.cpp_employee,
            self.ei_employee,
            self.union_dues,
            self.radio_dues,
            self.voucher_deductions,
            self.misc_deductions,
            self.total_deductions,
            self.net_pay,
        ]:
            spin.setValue(0)
        self.data_completeness.setValue(100.0)
        self.confidence_level.setValue(100.0)
        self.data_source_combo.setCurrentIndex(0)
        self.rate_source_combo.setCurrentIndex(0)
        self.notes_edit.clear()
        self._set_status("Form cleared. Load an employee + pay period to edit.")

    def load_entry(self):
        emp_id = self._selected_employee_id()
        pay_period = self._selected_pay_period()
        if not emp_id or not pay_period:
            QMessageBox.warning(self, "Missing Selection", "Select an employee and pay period first.")
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
                SELECT employee_pay_id, charter_hours_sum, approved_hours, overtime_hours,
                       manual_hours_adjustment, total_hours_worked, hourly_rate, rate_source,
                       base_pay, gratuity_percent, gratuity_amount, float_draw, reimbursements,
                       other_income, gross_pay, federal_tax, provincial_tax, cpp_employee,
                       ei_employee, union_dues, radio_dues, voucher_deductions, misc_deductions,
                       total_deductions, net_pay, data_completeness, data_source, confidence_level,
                       notes
                FROM employee_pay_master
                WHERE employee_id = %s AND pay_period_id = %s
                LIMIT 1
                """,
                (emp_id, pay_period[0]),
            )
            row = cur.fetchone()
            if not row:
                self.clear_form()
                self._set_status("No record yet. Enter values and Save to create.")
                return

            (
                employee_pay_id,
                charter_hours_sum,
                approved_hours,
                overtime_hours,
                manual_hours_adjustment,
                total_hours_worked,
                hourly_rate,
                rate_source,
                base_pay,
                gratuity_percent,
                gratuity_amount,
                float_draw,
                reimbursements,
                other_income,
                gross_pay,
                federal_tax,
                provincial_tax,
                cpp_employee,
                ei_employee,
                union_dues,
                radio_dues,
                voucher_deductions,
                misc_deductions,
                total_deductions,
                net_pay,
                data_completeness,
                data_source,
                confidence_level,
                notes,
            ) = row

            self.charter_hours.setValue(float(charter_hours_sum or 0))
            self.approved_hours.setValue(float(approved_hours or 0))
            self.overtime_hours.setValue(float(overtime_hours or 0))
            self.manual_hours_adjustment.setValue(float(manual_hours_adjustment or 0))
            self.total_hours_worked.setValue(float(total_hours_worked or 0))
            self.hourly_rate.setValue(float(hourly_rate or 0))
            self._set_combo_value(self.rate_source_combo, rate_source)

            self.base_pay.setValue(float(base_pay or 0))
            self.gratuity_percent.setValue(float(gratuity_percent or 0))
            self.gratuity_amount.setValue(float(gratuity_amount or 0))
            self.float_draw.setValue(float(float_draw or 0))
            self.reimbursements.setValue(float(reimbursements or 0))
            self.other_income.setValue(float(other_income or 0))
            self.gross_pay.setValue(float(gross_pay or 0))

            self.federal_tax.setValue(float(federal_tax or 0))
            self.provincial_tax.setValue(float(provincial_tax or 0))
            self.cpp_employee.setValue(float(cpp_employee or 0))
            self.ei_employee.setValue(float(ei_employee or 0))
            self.union_dues.setValue(float(union_dues or 0))
            self.radio_dues.setValue(float(radio_dues or 0))
            self.voucher_deductions.setValue(float(voucher_deductions or 0))
            self.misc_deductions.setValue(float(misc_deductions or 0))
            self.total_deductions.setValue(float(total_deductions or 0))
            self.net_pay.setValue(float(net_pay or 0))

            self.data_completeness.setValue(float(data_completeness or 0))
            self._set_combo_value(self.data_source_combo, data_source)
            self.confidence_level.setValue(float(confidence_level or 0))
            self.notes_edit.setPlainText(notes or "")

            self._set_status(f"Loaded employee_pay_id {employee_pay_id} for P{pay_period[2]:02d}.")
            self.recalculate_totals()
        except Exception as exc:
            self._set_status(f"Failed to load: {exc}", error=True)

    def save_entry(self):
        emp_id = self._selected_employee_id()
        pay_period = self._selected_pay_period()
        if not emp_id or not pay_period:
            QMessageBox.warning(self, "Missing Selection", "Select an employee and pay period first.")
            return

        fiscal_year = pay_period[1]
        values = self._gather_values()

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
                INSERT INTO employee_pay_master (
                    employee_id, pay_period_id, fiscal_year,
                    charter_hours_sum, approved_hours, overtime_hours, manual_hours_adjustment, total_hours_worked,
                    hourly_rate, rate_source,
                    base_pay, gratuity_percent, gratuity_amount, float_draw, reimbursements, other_income, gross_pay,
                    federal_tax, provincial_tax, cpp_employee, ei_employee, union_dues, radio_dues, voucher_deductions,
                    misc_deductions, total_deductions, net_pay,
                    data_completeness, data_source, confidence_level, notes, updated_at, created_by
                )
                VALUES (
                    %(employee_id)s, %(pay_period_id)s, %(fiscal_year)s,
                    %(charter_hours_sum)s, %(approved_hours)s, %(overtime_hours)s, %(manual_hours_adjustment)s, %(total_hours_worked)s,
                    %(hourly_rate)s, %(rate_source)s,
                    %(base_pay)s, %(gratuity_percent)s, %(gratuity_amount)s, %(float_draw)s, %(reimbursements)s, %(other_income)s, %(gross_pay)s,
                    %(federal_tax)s, %(provincial_tax)s, %(cpp_employee)s, %(ei_employee)s, %(union_dues)s, %(radio_dues)s, %(voucher_deductions)s,
                    %(misc_deductions)s, %(total_deductions)s, %(net_pay)s,
                    %(data_completeness)s, %(data_source)s, %(confidence_level)s, %(notes)s, NOW(), %(created_by)s
                )
                ON CONFLICT (employee_id, pay_period_id) DO UPDATE SET
                    charter_hours_sum = EXCLUDED.charter_hours_sum,
                    approved_hours = EXCLUDED.approved_hours,
                    overtime_hours = EXCLUDED.overtime_hours,
                    manual_hours_adjustment = EXCLUDED.manual_hours_adjustment,
                    total_hours_worked = EXCLUDED.total_hours_worked,
                    hourly_rate = EXCLUDED.hourly_rate,
                    rate_source = EXCLUDED.rate_source,
                    base_pay = EXCLUDED.base_pay,
                    gratuity_percent = EXCLUDED.gratuity_percent,
                    gratuity_amount = EXCLUDED.gratuity_amount,
                    float_draw = EXCLUDED.float_draw,
                    reimbursements = EXCLUDED.reimbursements,
                    other_income = EXCLUDED.other_income,
                    gross_pay = EXCLUDED.gross_pay,
                    federal_tax = EXCLUDED.federal_tax,
                    provincial_tax = EXCLUDED.provincial_tax,
                    cpp_employee = EXCLUDED.cpp_employee,
                    ei_employee = EXCLUDED.ei_employee,
                    union_dues = EXCLUDED.union_dues,
                    radio_dues = EXCLUDED.radio_dues,
                    voucher_deductions = EXCLUDED.voucher_deductions,
                    misc_deductions = EXCLUDED.misc_deductions,
                    total_deductions = EXCLUDED.total_deductions,
                    net_pay = EXCLUDED.net_pay,
                    data_completeness = EXCLUDED.data_completeness,
                    data_source = EXCLUDED.data_source,
                    confidence_level = EXCLUDED.confidence_level,
                    notes = EXCLUDED.notes,
                    updated_at = NOW(),
                    created_by = EXCLUDED.created_by,
                    fiscal_year = EXCLUDED.fiscal_year
                RETURNING employee_pay_id
                """,
                {
                    **values,
                    "employee_id": emp_id,
                    "pay_period_id": pay_period[0],
                    "fiscal_year": fiscal_year,
                    "created_by": "desktop_app",
                },
            )
            saved_id = cur.fetchone()[0]
            self.db.commit()
            self._set_status(f"Saved employee_pay_id {saved_id} for P{pay_period[2]:02d} ({fiscal_year}).")
            self.recalculate_totals()
        except Exception as exc:
            self.db.rollback()
            self._set_status(f"Failed to save: {exc}", error=True)

    def recalculate_totals(self):
        """Recalculate totals without overwriting manual overrides unless zero."""
        total_hours = (
            self.approved_hours.value()
            + self.overtime_hours.value()
            + self.manual_hours_adjustment.value()
        )
        if total_hours < 0:
            total_hours = 0
        self.total_hours_worked.setValue(round(total_hours, 2))

        suggested_base = round(self.hourly_rate.value() * total_hours, 2)
        if abs(self.base_pay.value()) < 0.005:
            self.base_pay.setValue(suggested_base)

        if abs(self.gratuity_amount.value()) < 0.005 and self.gratuity_percent.value() > 0:
            gratuity_amt = round(self.base_pay.value() * (self.gratuity_percent.value() / 100), 2)
            self.gratuity_amount.setValue(gratuity_amt)

        gross = (
            self.base_pay.value()
            + self.gratuity_amount.value()
            + self.float_draw.value()
            + self.reimbursements.value()
            + self.other_income.value()
        )
        self.gross_pay.setValue(round(gross, 2))

        total_deductions = (
            self.federal_tax.value()
            + self.provincial_tax.value()
            + self.cpp_employee.value()
            + self.ei_employee.value()
            + self.union_dues.value()
            + self.radio_dues.value()
            + self.voucher_deductions.value()
            + self.misc_deductions.value()
        )
        self.total_deductions.setValue(round(total_deductions, 2))

        net = gross - total_deductions
        self.net_pay.setValue(round(net, 2))

    def _gather_values(self):
        return {
            "charter_hours_sum": self.charter_hours.value(),
            "approved_hours": self.approved_hours.value(),
            "overtime_hours": self.overtime_hours.value(),
            "manual_hours_adjustment": self.manual_hours_adjustment.value(),
            "total_hours_worked": self.total_hours_worked.value(),
            "hourly_rate": self.hourly_rate.value(),
            "rate_source": self.rate_source_combo.currentText() or None,
            "base_pay": self.base_pay.value(),
            "gratuity_percent": self.gratuity_percent.value(),
            "gratuity_amount": self.gratuity_amount.value(),
            "float_draw": self.float_draw.value(),
            "reimbursements": self.reimbursements.value(),
            "other_income": self.other_income.value(),
            "gross_pay": self.gross_pay.value(),
            "federal_tax": self.federal_tax.value(),
            "provincial_tax": self.provincial_tax.value(),
            "cpp_employee": self.cpp_employee.value(),
            "ei_employee": self.ei_employee.value(),
            "union_dues": self.union_dues.value(),
            "radio_dues": self.radio_dues.value(),
            "voucher_deductions": self.voucher_deductions.value(),
            "misc_deductions": self.misc_deductions.value(),
            "total_deductions": self.total_deductions.value(),
            "net_pay": self.net_pay.value(),
            "data_completeness": self.data_completeness.value(),
            "data_source": self.data_source_combo.currentText() or None,
            "confidence_level": self.confidence_level.value(),
            "notes": self.notes_edit.toPlainText().strip() or None,
        }

    def _set_status(self, text, error=False):
        if error:
            self.status_label.setStyleSheet("color: #dc2626; font-weight: bold;")
        else:
            self.status_label.setStyleSheet("color: #2563eb; font-weight: bold;")
        self.status_label.setText(text)

    def _set_combo_value(self, combo: QComboBox, value):
        if value is None:
            return
        idx = combo.findText(str(value))
        if idx >= 0:
            combo.setCurrentIndex(idx)

