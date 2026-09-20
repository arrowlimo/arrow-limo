"""Unified staff loan account ledger.

Combines staff-funded receipts, e-transfer loan flows, manual cash entries,
opening balance forward, and vehicle-loan payment totals into one view.
"""

from __future__ import annotations

import csv
import logging
from datetime import date

from db_error_handling import DatabaseContext
from print_export_helper import PrintExportHelper
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

STAFF_LOAN_GL_CODE = "2550"


class StaffLoanAccountWidget(QWidget):
    """Single-page ledger for non-owner staff loan activity."""

    def __init__(self, db, auth_user=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.auth_user = auth_user or {}
        self._ledger_rows = []
        self._current_balance = 0.0
        self._editing_entry_id = None
        self._build_ui()
        self._ensure_tables()
        self.refresh_ledger()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>🏦 Staff Loan Account (Balance Forward + Receipts + E-Transfer + Cash)</h2>"))

        controls = QHBoxLayout()
        controls.addWidget(QLabel("From:"))
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate().addYears(-1))
        controls.addWidget(self.from_date)

        controls.addWidget(QLabel("To:"))
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate().addYears(1))
        controls.addWidget(self.to_date)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_ledger)
        controls.addWidget(refresh_btn)

        print_btn = QPushButton("Print Ledger")
        print_btn.clicked.connect(self.print_ledger)
        controls.addWidget(print_btn)

        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(self.export_csv)
        controls.addWidget(export_btn)

        controls.addStretch(1)
        layout.addLayout(controls)

        summary_grid = QGridLayout()
        self.opening_label = QLabel("Opening Balance: $0.00")
        self.in_label = QLabel("Total IN: $0.00")
        self.out_label = QLabel("Total OUT: $0.00")
        self.balance_label = QLabel("Current Balance: $0.00")
        self.vehicle_loans_label = QLabel("Vehicle Loans Included: $0.00")

        summary_grid.addWidget(self.opening_label, 0, 0)
        summary_grid.addWidget(self.in_label, 0, 1)
        summary_grid.addWidget(self.out_label, 1, 0)
        summary_grid.addWidget(self.balance_label, 1, 1)
        summary_grid.addWidget(self.vehicle_loans_label, 2, 0, 1, 2)
        layout.addLayout(summary_grid)

        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels(
            [
                "Date",
                "Source",
                "Direction",
                "Method",
                "Amount",
                "Signed",
                "Running Balance",
                "GL",
                "Reserve #",
                "Reference",
                "Notes",
            ]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        layout.addWidget(self.table)

        self._build_opening_balance_section(layout)
        self._build_manual_entry_section(layout)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def _build_opening_balance_section(self, parent_layout: QVBoxLayout) -> None:
        section = QFormLayout()

        row = QHBoxLayout()
        self.opening_amount_input = QLineEdit()
        self.opening_amount_input.setPlaceholderText("0.00")
        row.addWidget(self.opening_amount_input)

        self.opening_date_input = QDateEdit()
        self.opening_date_input.setCalendarPopup(True)
        self.opening_date_input.setDate(QDate.currentDate())
        row.addWidget(self.opening_date_input)

        save_btn = QPushButton("Save Opening Balance")
        save_btn.clicked.connect(self.save_opening_balance)
        row.addWidget(save_btn)

        section.addRow("Balance Forward", row)
        parent_layout.addLayout(section)

    def _build_manual_entry_section(self, parent_layout: QVBoxLayout) -> None:
        section = QFormLayout()

        self.entry_type = QComboBox()
        self.entry_type.addItems(
            [
                "staff advance to business",
                "business repayment to staff",
                "incident payout to client",
                "vehicle loan payment",
                "other",
            ]
        )
        self.entry_type.currentTextChanged.connect(self._apply_entry_type_defaults)
        section.addRow("Transaction Type", self.entry_type)

        date_row = QHBoxLayout()
        self.entry_date = QDateEdit()
        self.entry_date.setCalendarPopup(True)
        self.entry_date.setDate(QDate.currentDate())
        date_row.addWidget(self.entry_date)

        self.entry_direction = QComboBox()
        self.entry_direction.addItems(["IN", "OUT"])
        date_row.addWidget(self.entry_direction)

        self.entry_method = QComboBox()
        self.entry_method.addItems(["cash", "etransfer", "cheque", "other"])
        date_row.addWidget(self.entry_method)

        section.addRow("Date / Direction / Method", date_row)

        amount_row = QHBoxLayout()
        self.entry_amount = QLineEdit()
        self.entry_amount.setPlaceholderText("0.00")
        amount_row.addWidget(self.entry_amount)

        self.entry_reserve = QLineEdit()
        self.entry_reserve.setPlaceholderText("Reserve # (optional)")
        amount_row.addWidget(self.entry_reserve)

        self.entry_reference = QLineEdit()
        self.entry_reference.setPlaceholderText("Ref (txn id / note)")
        amount_row.addWidget(self.entry_reference)

        section.addRow("Amount / Reserve / Ref", amount_row)

        self.entry_notes = QTextEdit()
        self.entry_notes.setMaximumHeight(70)
        section.addRow("Notes", self.entry_notes)

        self.entry_preview_label = QLabel("Balance after entry: $0.00")
        section.addRow("Preview", self.entry_preview_label)

        action_row = QHBoxLayout()
        add_btn = QPushButton("Add Transaction")
        add_btn.clicked.connect(self.add_manual_entry)
        action_row.addWidget(add_btn)

        incident_btn = QPushButton("Incident Shortcut")
        incident_btn.clicked.connect(self._fill_incident_shortcut)
        action_row.addWidget(incident_btn)

        self.recover_btn = QPushButton("Recover From Client")
        self.recover_btn.setToolTip("Create an IN recovery transaction from selected OUT/incident row")
        self.recover_btn.setEnabled(False)
        self.recover_btn.clicked.connect(self.recover_from_client)
        action_row.addWidget(self.recover_btn)

        self.update_btn = QPushButton("Update Selected")
        self.update_btn.setEnabled(False)
        self.update_btn.clicked.connect(self.update_manual_entry)
        action_row.addWidget(self.update_btn)

        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self.delete_selected_transaction)
        action_row.addWidget(self.delete_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_manual_form)
        action_row.addWidget(clear_btn)
        action_row.addStretch(1)

        section.addRow(action_row)
        parent_layout.addLayout(section)
        self._apply_entry_type_defaults(self.entry_type.currentText())
        self.entry_amount.textChanged.connect(self._update_entry_preview)
        self.entry_direction.currentTextChanged.connect(self._update_entry_preview)

        self.editing_hint = QLabel("Selected transaction: none")
        parent_layout.addWidget(self.editing_hint)

    def _apply_entry_type_defaults(self, tx_type: str) -> None:
        tx = (tx_type or "").strip().lower()
        if tx == "staff advance to business":
            self.entry_direction.setCurrentText("IN")
            self.entry_method.setCurrentText("etransfer")
        elif tx == "business repayment to staff":
            self.entry_direction.setCurrentText("OUT")
            self.entry_method.setCurrentText("etransfer")
        elif tx in {"incident payout to client", "vehicle loan payment"}:
            self.entry_direction.setCurrentText("OUT")
            if tx == "incident payout to client":
                self.entry_method.setCurrentText("etransfer")
        elif tx == "other":
            self.entry_method.setCurrentText("other")
        self._update_entry_preview()

    def _fill_incident_shortcut(self) -> None:
        self.entry_type.setCurrentText("incident payout to client")
        self.entry_direction.setCurrentText("OUT")
        self.entry_method.setCurrentText("etransfer")
        if not self.entry_reference.text().strip():
            self.entry_reference.setText("INCIDENT")
        if not self.entry_notes.toPlainText().strip():
            self.entry_notes.setPlainText("Incident payout to client; awaiting charge-back/billing recovery.")
        self._update_entry_preview()

    def _entry_amount_value(self) -> float:
        raw = (self.entry_amount.text() or "").replace("$", "").replace(",", "").strip()
        return self._safe_float(raw)

    def _update_entry_preview(self) -> None:
        amount = self._entry_amount_value()
        direction = (self.entry_direction.currentText() or "OUT").upper()
        signed = amount if direction == "IN" else -amount
        projected = self._current_balance + signed
        self.entry_preview_label.setText(f"Balance after entry: ${projected:,.2f}")

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status_label.setStyleSheet(
            "color: #b91c1c; font-weight: bold;" if error else "color: #1d4ed8; font-weight: bold;"
        )
        self.status_label.setText(text)

    def _safe_float(self, value) -> float:
        try:
            return float(value or 0)
        except Exception:
            return 0.0

    def _table_has_columns(self, table_name: str, required: list[str]) -> bool:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    """,
                    (table_name,),
                )
                cols = {row[0] for row in cur.fetchall()}
            return all(c in cols for c in required)
        except Exception:
            return False

    def _get_table_columns(self, table_name: str) -> set[str]:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    """,
                    (table_name,),
                )
                return {row[0] for row in cur.fetchall()}
        except Exception:
            return set()

    def _ensure_tables(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS staff_loan_opening_balance (
                        id INTEGER PRIMARY KEY,
                        as_of_date DATE NOT NULL,
                        opening_balance NUMERIC(12,2) NOT NULL,
                        note TEXT,
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS staff_loan_manual_entries (
                        entry_id BIGSERIAL PRIMARY KEY,
                        entry_date DATE NOT NULL,
                        direction TEXT NOT NULL CHECK (direction IN ('IN','OUT')),
                        method TEXT,
                        amount NUMERIC(12,2) NOT NULL,
                        reserve_number TEXT,
                        reference_text TEXT,
                        notes TEXT,
                        created_by TEXT,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
        except Exception as exc:
            logger.error("Failed ensuring staff loan tables: %s", exc)
            self._set_status(f"Table setup failed: {exc}", error=True)

    def _load_opening_balance(self) -> tuple[float, date | None]:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT opening_balance, as_of_date
                    FROM staff_loan_opening_balance
                    WHERE id = 1
                    """
                )
                row = cur.fetchone()
            if not row:
                return 0.0, None
            return self._safe_float(row[0]), row[1]
        except Exception:
            return 0.0, None

    def save_opening_balance(self) -> None:
        amount = self._safe_float(self.opening_amount_input.text().strip())
        as_of = self.opening_date_input.date().toPyDate()
        note = f"Updated by {self.auth_user.get('username', 'desktop_user')}"
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO staff_loan_opening_balance (
                        id, as_of_date, opening_balance, note, updated_at
                    ) VALUES (1, %s, %s, %s, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        as_of_date = EXCLUDED.as_of_date,
                        opening_balance = EXCLUDED.opening_balance,
                        note = EXCLUDED.note,
                        updated_at = NOW()
                    """,
                    (as_of, amount, note),
                )
            self.refresh_ledger()
            self._set_status("Opening balance saved.")
        except Exception as exc:
            logger.error("Failed saving opening balance: %s", exc)
            QMessageBox.critical(self, "Save Error", f"Could not save opening balance:\n{exc}")

    def _clear_manual_form(self) -> None:
        self.entry_amount.clear()
        self.entry_reserve.clear()
        self.entry_reference.clear()
        self.entry_notes.clear()
        self.entry_type.setCurrentIndex(0)
        self.entry_direction.setCurrentIndex(0)
        self.entry_method.setCurrentIndex(0)
        self._editing_entry_id = None
        self.update_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.recover_btn.setEnabled(False)
        self.editing_hint.setText("Selected transaction: none")
        self._update_entry_preview()

    def _find_potential_duplicate_manual_entry(
        self,
        entry_date: date,
        direction: str,
        amount: float,
        reference_text: str,
        exclude_entry_id=None,
    ):
        if not self._table_has_columns(
            "staff_loan_manual_entries",
            ["entry_id", "entry_date", "direction", "amount", "reference_text"],
        ):
            return None
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                sql = """
                    SELECT entry_id,
                           entry_date,
                           direction,
                           amount,
                           COALESCE(reference_text, '')
                    FROM staff_loan_manual_entries
                    WHERE entry_date = %s
                      AND direction = %s
                      AND ABS(COALESCE(amount, 0) - %s) < 0.005
                """
                params = [entry_date, direction, amount]

                ref = (reference_text or "").strip()
                if ref:
                    sql += " AND LOWER(COALESCE(reference_text, '')) = LOWER(%s)"
                    params.append(ref)

                if exclude_entry_id is not None:
                    sql += " AND entry_id <> %s"
                    params.append(exclude_entry_id)

                sql += " ORDER BY entry_id DESC LIMIT 1"
                cur.execute(sql, tuple(params))
                return cur.fetchone()
        except Exception as exc:
            logger.warning("Duplicate check failed: %s", exc)
            return None

    def _fetch_manual_rows(self, start: date, end: date) -> list[dict]:
        out = []
        if not self._table_has_columns(
            "staff_loan_manual_entries",
            ["entry_date", "direction", "method", "amount"],
        ):
            return out
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT entry_id,
                           entry_date,
                           direction,
                           method,
                           amount,
                           COALESCE(reserve_number, ''),
                           COALESCE(reference_text, ''),
                           COALESCE(notes, '')
                    FROM staff_loan_manual_entries
                    WHERE entry_date BETWEEN %s AND %s
                    ORDER BY entry_date ASC, entry_id ASC
                    """,
                    (start, end),
                )
                rows = cur.fetchall()
            for row in rows:
                amount = self._safe_float(row[4])
                out.append(
                    {
                        "entry_id": row[0],
                        "date": row[1],
                        "source": "manual",
                        "direction": row[2],
                        "method": row[3] or "other",
                        "amount": amount,
                        "signed": amount if str(row[2]).upper() == "IN" else -amount,
                        "gl": STAFF_LOAN_GL_CODE,
                        "reserve": row[5],
                        "reference": row[6],
                        "notes": row[7],
                    }
                )
        except Exception as exc:
            logger.warning("Manual rows load failed: %s", exc)
        return out

    def _extract_type_from_notes(self, notes: str) -> tuple[str, str]:
        text = (notes or "").strip()
        if text.startswith("[") and "]" in text:
            close_idx = text.find("]")
            raw_type = text[1:close_idx].strip().lower()
            remainder = text[close_idx + 1 :].strip()
            return raw_type, remainder
        return "other", text

    def _on_table_selection_changed(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            self._clear_manual_form()
            return

        ref_item = self.table.item(row, 9)
        meta = ref_item.data(Qt.ItemDataRole.UserRole) if ref_item else None
        if not isinstance(meta, dict):
            self._clear_manual_form()
            return

        if meta.get("source") != "manual":
            self._editing_entry_id = None
            self.update_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            can_recover = str(meta.get("direction") or "").upper() == "OUT"
            self.recover_btn.setEnabled(can_recover)
            self.editing_hint.setText("Selected transaction: read-only (imported source)")
            return

        self._editing_entry_id = meta.get("entry_id")
        self.update_btn.setEnabled(self._editing_entry_id is not None)
        self.delete_btn.setEnabled(self._editing_entry_id is not None)
        self.recover_btn.setEnabled(str(meta.get("direction") or "").upper() == "OUT")

        self.entry_date.setDate(QDate.fromString(str(meta.get("date") or ""), "yyyy-MM-dd"))
        self.entry_direction.setCurrentText(str(meta.get("direction") or "OUT"))
        self.entry_method.setCurrentText(str(meta.get("method") or "other"))
        self.entry_amount.setText(f"{self._safe_float(meta.get('amount')):.2f}")
        self.entry_reserve.setText(str(meta.get("reserve") or ""))
        self.entry_reference.setText(str(meta.get("reference") or ""))

        tx_type, note_text = self._extract_type_from_notes(str(meta.get("notes") or ""))
        idx = self.entry_type.findText(tx_type)
        self.entry_type.setCurrentIndex(idx if idx >= 0 else self.entry_type.findText("other"))
        self.entry_notes.setPlainText(note_text)
        self.editing_hint.setText(f"Selected transaction: manual entry #{self._editing_entry_id}")

    def update_manual_entry(self) -> None:
        if not self._editing_entry_id:
            QMessageBox.information(self, "Update", "Select a manual transaction row first.")
            return

        amount = self._safe_float(self.entry_amount.text().strip())
        if amount <= 0:
            QMessageBox.warning(self, "Validation", "Amount must be greater than zero.")
            return

        entry_date = self.entry_date.date().toPyDate()
        direction = self.entry_direction.currentText().strip() or "OUT"
        reference_text = self.entry_reference.text().strip()

        duplicate = self._find_potential_duplicate_manual_entry(
            entry_date=entry_date,
            direction=direction,
            amount=amount,
            reference_text=reference_text,
            exclude_entry_id=self._editing_entry_id,
        )
        if duplicate:
            dup_id, dup_date, dup_direction, dup_amount, dup_ref = duplicate
            decision = QMessageBox.question(
                self,
                "Potential Duplicate",
                "Another similar transaction already exists:\n"
                f"Entry #{dup_id} | Date: {dup_date} | Direction: {dup_direction} | "
                f"Amount: ${self._safe_float(dup_amount):,.2f} | Ref: {dup_ref or '-'}\n\n"
                "Update anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if decision != QMessageBox.StandardButton.Yes:
                self._set_status("Update cancelled due to duplicate warning.", error=True)
                return

        tx_type = self.entry_type.currentText().strip()
        note_prefix = f"[{tx_type}] " if tx_type else ""
        note_text = self.entry_notes.toPlainText().strip()

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    UPDATE staff_loan_manual_entries
                    SET entry_date = %s,
                        direction = %s,
                        method = %s,
                        amount = %s,
                        reserve_number = %s,
                        reference_text = %s,
                        notes = %s
                    WHERE entry_id = %s
                    """,
                    (
                        entry_date,
                        direction,
                        self.entry_method.currentText(),
                        amount,
                        self.entry_reserve.text().strip() or None,
                        reference_text or None,
                        (note_prefix + note_text).strip() or None,
                        self._editing_entry_id,
                    ),
                )
            self.refresh_ledger()
            self._set_status("Manual transaction updated.")
        except Exception as exc:
            logger.error("Failed updating manual entry: %s", exc)
            QMessageBox.critical(self, "Update Error", f"Could not update entry:\n{exc}")

    def delete_selected_transaction(self) -> None:
        if not self._editing_entry_id:
            QMessageBox.information(self, "Delete", "Select a manual transaction row first.")
            return

        confirm = QMessageBox.question(
            self,
            "Delete Transaction",
            f"Delete manual transaction #{self._editing_entry_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "DELETE FROM staff_loan_manual_entries WHERE entry_id = %s",
                    (self._editing_entry_id,),
                )
            self._clear_manual_form()
            self.refresh_ledger()
            self._set_status("Manual transaction deleted.")
        except Exception as exc:
            logger.error("Failed deleting manual entry: %s", exc)
            QMessageBox.critical(self, "Delete Error", f"Could not delete entry:\n{exc}")

    def _selected_row_meta(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        ref_item = self.table.item(row, 9)
        if not ref_item:
            return None
        meta = ref_item.data(Qt.ItemDataRole.UserRole)
        return meta if isinstance(meta, dict) else None

    def _save_current_form_as_manual_transaction(self) -> bool:
        amount = self._safe_float(self.entry_amount.text().strip())
        if amount <= 0:
            QMessageBox.warning(self, "Validation", "Amount must be greater than zero.")
            return False

        entry_date = self.entry_date.date().toPyDate()
        direction = self.entry_direction.currentText().strip() or "OUT"
        reference_text = self.entry_reference.text().strip()

        duplicate = self._find_potential_duplicate_manual_entry(
            entry_date=entry_date,
            direction=direction,
            amount=amount,
            reference_text=reference_text,
        )
        if duplicate:
            dup_id, dup_date, dup_direction, dup_amount, dup_ref = duplicate
            decision = QMessageBox.question(
                self,
                "Potential Duplicate",
                "A similar transaction already exists:\n"
                f"Entry #{dup_id} | Date: {dup_date} | Direction: {dup_direction} | "
                f"Amount: ${self._safe_float(dup_amount):,.2f} | Ref: {dup_ref or '-'}\n\n"
                "Add anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if decision != QMessageBox.StandardButton.Yes:
                self._set_status("Add cancelled due to duplicate warning.", error=True)
                return False

        try:
            tx_type = self.entry_type.currentText().strip()
            note_prefix = f"[{tx_type}] " if tx_type else ""
            note_text = self.entry_notes.toPlainText().strip()

            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO staff_loan_manual_entries (
                        entry_date,
                        direction,
                        method,
                        amount,
                        reserve_number,
                        reference_text,
                        notes,
                        created_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        entry_date,
                        direction,
                        self.entry_method.currentText(),
                        amount,
                        self.entry_reserve.text().strip() or None,
                        reference_text or None,
                        (note_prefix + note_text).strip() or None,
                        self.auth_user.get("username", "desktop_user"),
                    ),
                )
            self._clear_manual_form()
            self.refresh_ledger()
            self._set_status("Transaction added to staff loan ledger.")
            return True
        except Exception as exc:
            logger.error("Failed adding manual entry: %s", exc)
            QMessageBox.critical(self, "Save Error", f"Could not add manual entry:\n{exc}")
            return False

    def add_manual_entry(self) -> None:
        self._save_current_form_as_manual_transaction()

    def recover_from_client(self) -> None:
        meta = self._selected_row_meta()
        if not meta:
            QMessageBox.information(self, "Recover", "Select an OUT transaction row first.")
            return

        if str(meta.get("direction") or "").upper() != "OUT":
            QMessageBox.information(self, "Recover", "Selected row is not an OUT transaction.")
            return

        amount = self._safe_float(meta.get("amount"))
        if amount <= 0:
            QMessageBox.warning(self, "Recover", "Selected row has no valid amount.")
            return

        self._editing_entry_id = None
        self.update_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)

        self.entry_type.setCurrentText("staff advance to business")
        self.entry_direction.setCurrentText("IN")
        self.entry_method.setCurrentText("etransfer")
        self.entry_amount.setText(f"{amount:.2f}")
        self.entry_reserve.setText(str(meta.get("reserve") or ""))

        orig_ref = str(meta.get("reference") or "").strip()
        recovery_ref = f"RECOVER/{orig_ref}" if orig_ref else "RECOVER"
        self.entry_reference.setText(recovery_ref)

        note = (
            "Client recovery against prior payout"
            f" | source={meta.get('source') or '-'}"
            f" | original_ref={orig_ref or '-'}"
        )
        self.entry_notes.setPlainText(note)

        confirm = QMessageBox.question(
            self,
            "Recover From Client",
            f"Create IN recovery transaction for ${amount:,.2f}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            self._set_status("Recovery creation cancelled.", error=True)
            return

        if self._save_current_form_as_manual_transaction():
            self._set_status("Recovery transaction created from selected payout.")

    def _fetch_etransfer_rows(self, start: date, end: date) -> list[dict]:
        out = []
        et_cols = self._get_table_columns("etransfer_transactions")
        if not {"transaction_date", "direction", "amount"}.issubset(et_cols):
            return out

        has_gl_code = "gl_account_code" in et_cols
        has_category = "category" in et_cols
        has_flow = "david_loan_flow" in et_cols

        gl_select = (
            "COALESCE(et.gl_account_code, '')"
            if has_gl_code
            else f"'{STAFF_LOAN_GL_CODE}'"
        )

        where_clauses = ["et.transaction_date BETWEEN %s AND %s"]
        params: list[object] = [start, end]

        if has_gl_code and has_category:
            where_clauses.append("(et.gl_account_code = %s OR et.category = 'loan_payment')")
            params.append(STAFF_LOAN_GL_CODE)
        elif has_gl_code:
            where_clauses.append("et.gl_account_code = %s")
            params.append(STAFF_LOAN_GL_CODE)
        elif has_category:
            where_clauses.append("et.category = 'loan_payment'")
        else:
            return out

        if has_flow and has_category:
            flow_guard = "(et.category = 'loan_payment' OR et.david_loan_flow IN ('DAVID_LOAN_IN','DAVID_LOAN_OUT'))"
            where_clauses.append(flow_guard)

        where_sql = " AND ".join(where_clauses)

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    f"""
                    SELECT et.transaction_date,
                           et.direction,
                           COALESCE(et.amount, 0),
                           {gl_select},
                           COALESCE(et.etransfer_id::TEXT, ''),
                           COALESCE(bt.description, ''),
                           COALESCE(et.category, '')
                    FROM etransfer_transactions et
                    LEFT JOIN banking_transactions bt
                    ON bt.transaction_id = et.banking_transaction_id
                    WHERE {where_sql}
                    ORDER BY et.transaction_date ASC, et.etransfer_id ASC
                    """,
                    tuple(params),
                )
                rows = cur.fetchall()
            for row in rows:
                amount = self._safe_float(row[2])
                direction = str(row[1] or "OUT").upper()
                out.append(
                    {
                        "date": row[0],
                        "source": "etransfer",
                        "direction": direction,
                        "method": "etransfer",
                        "amount": amount,
                        "signed": amount if direction == "IN" else -amount,
                        "gl": row[3] or STAFF_LOAN_GL_CODE,
                        "reserve": "",
                        "reference": f"ET#{row[4]}" if row[4] else "",
                        "notes": row[5] or row[6] or "",
                    }
                )
        except Exception as exc:
            logger.warning("E-transfer rows load failed: %s", exc)
        return out

    def _fetch_receipt_rows(self, start: date, end: date) -> list[dict]:
        out = []
        if not self._table_has_columns(
            "receipts",
            ["receipt_date", "gross_amount", "gl_account_code"],
        ):
            return out

        # Staff-funded receipts are treated as loan OUT until reimbursed.
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT receipt_date,
                           COALESCE(gross_amount, 0),
                           COALESCE(payment_method, ''),
                           COALESCE(reimbursed_via, ''),
                           COALESCE(reserve_number, ''),
                           COALESCE(receipt_id::TEXT, ''),
                           COALESCE(description, ''),
                           COALESCE(vendor_name, '')
                    FROM receipts
                    WHERE receipt_date BETWEEN %s AND %s
                      AND gl_account_code = %s
                    ORDER BY receipt_date ASC, receipt_id ASC
                    """,
                    (start, end, STAFF_LOAN_GL_CODE),
                )
                rows = cur.fetchall()
            for row in rows:
                amount = self._safe_float(row[1])
                method_value = (row[2] or "receipt").strip().lower()
                reimbursed_via_value = (row[3] or "").strip().lower()
                is_rpr_payment = method_value == "rpr payment" or (
                    method_value == "reimbursement"
                    and reimbursed_via_value == "rpr payment"
                )
                if is_rpr_payment:
                    direction = "IN"
                    signed_amount = amount
                else:
                    # Default staff-funded and reimbursement purchases to OUT.
                    direction = "OUT"
                    signed_amount = -amount
                method_display = (
                    row[3] if row[3] in ("RPR purchase", "RPR payment") else row[2]
                )
                desc = row[6] or ""
                vendor = row[7] or ""
                note = f"{vendor} {desc}".strip()
                out.append(
                    {
                        "date": row[0],
                        "source": "receipt",
                        "direction": direction,
                        "method": (method_display or "receipt").strip().lower(),
                        "amount": amount,
                        "signed": signed_amount,
                        "gl": STAFF_LOAN_GL_CODE,
                        "reserve": row[4],
                        "reference": f"R#{row[5]}" if row[5] else "",
                        "notes": note,
                    }
                )
        except Exception as exc:
            logger.warning("Receipt rows load failed: %s", exc)
        return out

    def _fetch_vehicle_loan_total(self, start: date, end: date) -> float:
        if not self._table_has_columns("vehicle_loan_payments", ["payment_date"]):
            return 0.0

        amount_candidates = ["payment_amount", "amount", "total_payment", "principal_amount"]
        chosen_amount = None
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'vehicle_loan_payments'
                    """
                )
                cols = {r[0] for r in cur.fetchall()}
            for col in amount_candidates:
                if col in cols:
                    chosen_amount = col
                    break
            if not chosen_amount:
                return 0.0

            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    f"""
                    SELECT COALESCE(SUM({chosen_amount}), 0)
                    FROM vehicle_loan_payments
                    WHERE payment_date BETWEEN %s AND %s
                    """,
                    (start, end),
                )
                row = cur.fetchone()
            return self._safe_float(row[0] if row else 0)
        except Exception:
            return 0.0

    def refresh_ledger(self) -> None:
        start = self.from_date.date().toPyDate()
        end = self.to_date.date().toPyDate()
        opening_balance, opening_date = self._load_opening_balance()

        rows = []
        rows.extend(self._fetch_manual_rows(start, end))
        rows.extend(self._fetch_etransfer_rows(start, end))
        rows.extend(self._fetch_receipt_rows(start, end))

        rows.sort(key=lambda r: (r.get("date") or date.min, r.get("source", ""), r.get("reference", "")))

        running = opening_balance
        total_in = 0.0
        total_out = 0.0
        for row in rows:
            signed = self._safe_float(row.get("signed"))
            if signed >= 0:
                total_in += signed
            else:
                total_out += abs(signed)
            running += signed
            row["running"] = running

        self._ledger_rows = rows
        self._render_table()

        self.opening_label.setText(
            f"Opening Balance: ${opening_balance:,.2f}"
            + (f" (as of {opening_date})" if opening_date else "")
        )
        self.in_label.setText(f"Total IN: ${total_in:,.2f}")
        self.out_label.setText(f"Total OUT: ${total_out:,.2f}")
        self.balance_label.setText(f"Current Balance: ${running:,.2f}")
        self._current_balance = running

        vehicle_total = self._fetch_vehicle_loan_total(start, end)
        self.vehicle_loans_label.setText(f"Vehicle Loans Included: ${vehicle_total:,.2f}")

        self._set_status(f"Loaded {len(rows)} staff-loan ledger rows.")
        self._update_entry_preview()

    def _render_table(self) -> None:
        self.table.setRowCount(len(self._ledger_rows))
        for i, row in enumerate(self._ledger_rows):
            self.table.setItem(i, 0, QTableWidgetItem(str(row.get("date") or "")))
            self.table.setItem(i, 1, QTableWidgetItem(str(row.get("source") or "")))
            self.table.setItem(i, 2, QTableWidgetItem(str(row.get("direction") or "")))
            self.table.setItem(i, 3, QTableWidgetItem(str(row.get("method") or "")))
            self.table.setItem(i, 4, QTableWidgetItem(f"${self._safe_float(row.get('amount')):,.2f}"))
            self.table.setItem(i, 5, QTableWidgetItem(f"${self._safe_float(row.get('signed')):,.2f}"))
            self.table.setItem(i, 6, QTableWidgetItem(f"${self._safe_float(row.get('running')):,.2f}"))
            self.table.setItem(i, 7, QTableWidgetItem(str(row.get("gl") or "")))
            self.table.setItem(i, 8, QTableWidgetItem(str(row.get("reserve") or "")))
            ref_item = QTableWidgetItem(str(row.get("reference") or ""))
            ref_item.setData(
                Qt.ItemDataRole.UserRole,
                {
                    "entry_id": row.get("entry_id"),
                    "source": row.get("source"),
                    "date": row.get("date"),
                    "direction": row.get("direction"),
                    "method": row.get("method"),
                    "amount": row.get("amount"),
                    "reserve": row.get("reserve"),
                    "reference": row.get("reference"),
                    "notes": row.get("notes"),
                },
            )
            self.table.setItem(i, 9, ref_item)
            self.table.setItem(i, 10, QTableWidgetItem(str(row.get("notes") or "")))

    def print_ledger(self) -> None:
        PrintExportHelper.print_table(self.table, "Staff Loan Account Ledger", self)

    def export_csv(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Staff Loan Ledger CSV",
            "staff_loan_ledger.csv",
            "CSV Files (*.csv);;All Files (*)",
        )
        if not filename:
            return

        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "date",
                        "source",
                        "direction",
                        "method",
                        "amount",
                        "signed",
                        "running_balance",
                        "gl",
                        "reserve_number",
                        "reference",
                        "notes",
                    ]
                )
                for row in self._ledger_rows:
                    writer.writerow(
                        [
                            row.get("date") or "",
                            row.get("source") or "",
                            row.get("direction") or "",
                            row.get("method") or "",
                            f"{self._safe_float(row.get('amount')):.2f}",
                            f"{self._safe_float(row.get('signed')):.2f}",
                            f"{self._safe_float(row.get('running')):.2f}",
                            row.get("gl") or "",
                            row.get("reserve") or "",
                            row.get("reference") or "",
                            row.get("notes") or "",
                        ]
                    )
            QMessageBox.information(self, "Export CSV", f"Ledger exported to:\n{filename}")
        except Exception as exc:
            logger.error("Failed exporting staff loan CSV: %s", exc)
            QMessageBox.critical(self, "Export CSV", f"Failed exporting CSV:\n{exc}")
