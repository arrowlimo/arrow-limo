"""NSF Pair Manager widget.

Find likely NSF reversal pairs in banking transactions and mark them as
internal transfers with a consistent audit note for T2 exclusion.
"""

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import psycopg2
from common_widgets import StandardDateEdit
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


@dataclass
class PairCandidate:
    left_id: int
    right_id: int
    left_date: date
    right_date: date
    left_desc: str
    right_desc: str
    left_amount: Decimal
    right_amount: Decimal
    abs_amount: Decimal
    days_apart: int
    reason: str


class NsfPairManagerWidget(QWidget):
    """Identify and mark NSF reversal pairs as internal transfers."""

    DEFAULT_GLCODE = "5715"

    def __init__(self, conn: psycopg2.extensions.connection, parent=None) -> None:
        super().__init__(parent)
        self.conn = conn
        self._pairs: list[PairCandidate] = []
        self._build_ui()
        self._load_pairs()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        instructions = QLabel(
            "Use this tool for NSF/STOP/CANCELLED reversal pairs that net to"
            "zero. "
            "It marks both rows as internal transfer and adds an audit note "
            "so they are treated as non-T2 internal movement."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        filters_group = QGroupBox("Pair Detection")
        filters = QFormLayout(filters_group)

        self.date_from = StandardDateEdit(allow_blank=True)
        self.date_to = StandardDateEdit(allow_blank=True)
        self.date_from.setDate(QDate.currentDate().addYears(-1))
        self.date_to.setDate(QDate.currentDate())

        self.max_days = QSpinBox()
        self.max_days.setRange(1, 365)
        self.max_days.setValue(90)

        self.amount_tolerance = QLineEdit("0.01")
        self.amount_tolerance.setMaximumWidth(90)

        self.desc_filter = QLineEdit()
        self.desc_filter.setPlaceholderText("Optional keyword filter")

        self.include_already_marked = QCheckBox(
            "Include already marked transfers"
        )

        self.gl_code = QLineEdit(self.DEFAULT_GLCODE)
        self.gl_code.setMaximumWidth(90)
        self.gl_code.setToolTip(
            "Audit GL marker used in notes (for review traceability)."
        )

        self.status_value = QComboBox()
        self.status_value.addItems(["matched", "reconciled"])

        filters.addRow("Date from", self.date_from)
        filters.addRow("Date to", self.date_to)
        filters.addRow("Max days apart", self.max_days)
        filters.addRow("Amount tolerance", self.amount_tolerance)
        filters.addRow("Keyword", self.desc_filter)
        filters.addRow("GL code marker", self.gl_code)
        filters.addRow("Reconciliation status", self.status_value)
        filters.addRow("", self.include_already_marked)

        layout.addWidget(filters_group)

        actions = QHBoxLayout()
        refresh_btn = QPushButton("Find Pairs")
        refresh_btn.clicked.connect(self._load_pairs)
        actions.addWidget(refresh_btn)

        auto_select_btn = QPushButton("Auto-Select Suggested")
        auto_select_btn.setToolTip(
            "Select all currently listed candidate pairs."
        )
        auto_select_btn.clicked.connect(self._auto_select_suggested)
        actions.addWidget(auto_select_btn)

        clear_select_btn = QPushButton("Clear Selection")
        clear_select_btn.clicked.connect(self._clear_selection)
        actions.addWidget(clear_select_btn)

        apply_btn = QPushButton("Mark Selected As Internal Transfer")
        apply_btn.setStyleSheet(
            "background-color: #2e7d32; color: white; font-weight: bold;"
        )
        apply_btn.clicked.connect(self._apply_selected_pairs)
        actions.addWidget(apply_btn)

        auto_apply_btn = QPushButton("One-Click Apply All Suggested")
        auto_apply_btn.setStyleSheet(
            "background-color: #1565c0; color: white; font-weight: bold;"
        )
        auto_apply_btn.setToolTip(
            "Auto-select all shown candidates and apply internal-transfer"
            "marking in one step."
        )
        auto_apply_btn.clicked.connect(self._auto_apply_suggested)
        actions.addWidget(auto_apply_btn)

        actions.addStretch()
        self.summary_label = QLabel("No pairs loaded")
        actions.addWidget(self.summary_label)
        layout.addLayout(actions)

        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels(
            [
                "Pick",
                "Abs Amount",
                "Days",
                "Reason",
                "Left ID",
                "Left Date",
                "Left Desc",
                "Right ID",
                "Right Date",
                "Right Desc",
                "Pair Key",
            ]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setColumnHidden(10, True)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

    def _extract_ref(self, description: str) -> str:
        match = re.search(r"(\d{10,})", description or "")
        return match.group(1) if match else ""

    def _contains_nsf(self, text: str) -> bool:
        upper = (text or "").upper()
        return "NSF" in upper

    def _pair_marker(self, left_desc: str, right_desc: str) -> str:
        text = f"{left_desc} {right_desc}".upper()
        if "NSF" in text:
            return "NSF_PAIR_INTERNAL_TRANSFER"
        if "STOP" in text:
            return "STOP_PAIR_INTERNAL_TRANSFER"
        if "CANCEL" in text or "REVERS" in text:
            return "CANCELLED_PAIR_INTERNAL_TRANSFER"
        return "REVERSAL_PAIR_INTERNAL_TRANSFER"

    def _to_signed(
        self, debit: Decimal | None, credit: Decimal | None
    ) -> Decimal:
        if debit and debit != 0:
            return Decimal(debit)
        if credit and credit != 0:
            return Decimal(credit) * Decimal("-1")
        return Decimal("0")

    def _load_raw_rows(self) -> object:
        sql = ["""
            SELECT
                bt.transaction_id,
                bt.transaction_date,
                COALESCE(bt.description, ''),
                COALESCE(bt.debit_amount, 0),
                COALESCE(bt.credit_amount, 0),
                COALESCE(bt.is_transfer, false),
                COALESCE(bt.is_nsf_charge, false),
                COALESCE(bt.reconciliation_status, '')
            FROM banking_transactions bt
            WHERE bt.receipt_id IS NULL
              AND bt.reconciled_receipt_id IS NULL
              AND (
                                    bt.description ILIKE '%%NSF%%'
                                    OR bt.description ILIKE '%%RETURN%%'
                                    OR bt.description ILIKE '%%STOP%%'
                                    OR bt.description ILIKE '%%CANCEL%%'
                                    OR bt.description ILIKE '%%REVERS%%'
                                    OR bt.description ILIKE '%%REVERSE%%'
                                    OR bt.description ILIKE '%%E-TRANSFER%%'
                                    OR bt.description ILIKE '%%ETRANSFER%%'
              )
            """]
        params: list[object] = []

        d_from = self.date_from.getDate()
        if d_from:
            sql.append("AND bt.transaction_date >= %s")
            params.append(
                d_from.toPyDate() if hasattr(d_from, "toPyDate") else d_from
            )

        d_to = self.date_to.getDate()
        if d_to:
            sql.append("AND bt.transaction_date <= %s")
            params.append(
                d_to.toPyDate() if hasattr(d_to, "toPyDate") else d_to
            )

        keyword = (self.desc_filter.text() or "").strip()
        if keyword:
            sql.append("AND bt.description ILIKE %s")
            params.append(f"%{keyword}%")

        if not self.include_already_marked.isChecked():
            sql.append("AND COALESCE(bt.is_transfer, false) = false")

        sql.append("ORDER BY bt.transaction_date ASC, bt.transaction_id ASC")

        cur = self.conn.cursor()
        cur.execute("\n".join(sql), params)
        rows = cur.fetchall()
        cur.close()
        return rows

    def _build_pair_candidates(self, rows) -> list[PairCandidate]:
        tolerance = Decimal(
            (self.amount_tolerance.text() or "0.01").strip() or "0.01"
        )
        max_days = int(self.max_days.value())

        positives = []
        negatives = []
        for row in rows:
            # Guard against unexpected row shapes from older schemas/adapters.
            if not isinstance(row, (list, tuple)) or len(row) < 5:
                continue

            try:
                tid = row[0]
                tdate = row[1]
                desc = row[2]
                debit = row[3]
                credit = row[4]
            except Exception:
                continue

            if tid is None or tdate is None:
                continue

            signed = self._to_signed(debit, credit)
            if signed == 0:
                continue
            item = {
                "id": int(tid),
                "date": tdate,
                "desc": desc,
                "signed": signed,
                "abs": abs(signed),
                "ref": self._extract_ref(desc),
            }
            if signed > 0:
                positives.append(item)
            else:
                negatives.append(item)

        used_neg_ids: set[int] = set()
        candidates: list[PairCandidate] = []

        for p in positives:
            best = None
            best_score = None
            for n in negatives:
                if n["id"] in used_neg_ids:
                    continue
                amount_gap = abs(p["abs"] - n["abs"])
                if amount_gap > tolerance:
                    continue
                try:
                    days_apart = abs((p["date"] - n["date"]).days)
                except Exception:
                    continue
                if days_apart > max_days:
                    continue

                same_ref = bool(p["ref"] and p["ref"] == n["ref"])
                score = (
                    0 if same_ref else 1,
                    days_apart,
                    float(amount_gap),
                    n["id"],
                )
                if best_score is None or score < best_score:
                    best_score = score
                    best = (n, days_apart, amount_gap, same_ref)

            if best is None:
                continue

            n, days_apart, _amount_gap, same_ref = best
            used_neg_ids.add(n["id"])

            reason = "same_ref" if same_ref else "amount+date_window"
            candidates.append(
                PairCandidate(
                    left_id=p["id"],
                    right_id=n["id"],
                    left_date=p["date"],
                    right_date=n["date"],
                    left_desc=p["desc"],
                    right_desc=n["desc"],
                    left_amount=p["signed"],
                    right_amount=n["signed"],
                    abs_amount=p["abs"],
                    days_apart=days_apart,
                    reason=reason,
                )
            )

        return candidates

    def _load_pairs(self) -> None:
        try:
            rows = self._load_raw_rows()
            self._pairs = self._build_pair_candidates(rows)
            self._populate_table()
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.critical(
                self, "Load Error", f"Failed to load NSF pairs:\n{e}"
            )

    def _populate_table(self) -> None:
        self.table.setRowCount(len(self._pairs))
        for r, pair in enumerate(self._pairs):
            pick_item = QTableWidgetItem()
            pick_item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(r, 0, pick_item)
            self.table.setItem(
                r, 1, QTableWidgetItem(f"${pair.abs_amount:,.2f}")
            )
            self.table.setItem(r, 2, QTableWidgetItem(str(pair.days_apart)))
            self.table.setItem(r, 3, QTableWidgetItem(pair.reason))
            self.table.setItem(r, 4, QTableWidgetItem(str(pair.left_id)))
            self.table.setItem(r, 5, QTableWidgetItem(str(pair.left_date)))
            self.table.setItem(r, 6, QTableWidgetItem(pair.left_desc))
            self.table.setItem(r, 7, QTableWidgetItem(str(pair.right_id)))
            self.table.setItem(r, 8, QTableWidgetItem(str(pair.right_date)))
            self.table.setItem(r, 9, QTableWidgetItem(pair.right_desc))
            self.table.setItem(
                r, 10, QTableWidgetItem(f"{pair.left_id}:{pair.right_id}")
            )

        self.summary_label.setText(f"Pairs found: {len(self._pairs)}")

    def _selected_pairs(self) -> list[PairCandidate]:
        selected: list[PairCandidate] = []
        for r, pair in enumerate(self._pairs):
            item = self.table.item(r, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                selected.append(pair)
        return selected

    def _auto_select_suggested(self) -> None:
        if self.table.rowCount() == 0:
            return
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked)

    def _clear_selection(self) -> None:
        if self.table.rowCount() == 0:
            return
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)

    def _auto_apply_suggested(self) -> None:
        if self.table.rowCount() == 0:
            QMessageBox.information(
                self, "No Candidates", "No suggested pairs to apply."
            )
            return
        self._auto_select_suggested()
        self._apply_selected_pairs()

    def _apply_selected_pairs(self) -> None:
        selected = self._selected_pairs()
        if not selected:
            QMessageBox.information(
                self, "No Selection", "Check at least one pair to apply."
            )
            return

        gl_code = (self.gl_code.text() or "").strip() or self.DEFAULT_GLCODE
        status_value = (self.status_value.currentText() or "matched").strip()

        confirm = QMessageBox.question(
            self,
            "Confirm Apply",
            f"Apply internal-transfer reversal marking to {len(selected)}"
            f"pair(s)?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        updated_rows = 0
        cur = self.conn.cursor()
        try:
            for pair in selected:
                ids = [pair.left_id, pair.right_id]
                marker = self._pair_marker(pair.left_desc, pair.right_desc)
                for txn_id in ids:
                    is_nsf_row = self._contains_nsf(
                        pair.left_desc
                    ) or self._contains_nsf(pair.right_desc)
                    note = (
                        f"{marker}; pair={pair.left_id}:{pair.right_id}; "
                        f"gl={gl_code}; t2_exclude=true"
                    )
                    cur.execute(
                        """
                        UPDATE banking_transactions
                           SET is_transfer = TRUE,
                               is_nsf_charge = %s,
                               category = COALESCE(
                                   NULLIF(category, ''),
                                   'INTERNAL_TRANSFER_REVERSAL'
                               ),
                               reconciliation_status = %s,
                               reconciliation_notes = CASE
                                   WHEN COALESCE(
                                       reconciliation_notes, ''
                                   ) = '' THEN %s
                                   WHEN reconciliation_notes ILIKE %s THEN
                                   reconciliation_notes
                                   ELSE reconciliation_notes || E'\n' || %s
                               END,
                               updated_at = NOW()
                         WHERE transaction_id = %s
                        """,
                        [
                            is_nsf_row,
                            status_value,
                            note,
                            f"%{marker}%",
                            note,
                            txn_id,
                        ],
                    )
                    updated_rows += cur.rowcount

            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            cur.close()
            QMessageBox.critical(
                self, "Update Error", f"Failed to apply NSF pairing:\n{e}"
            )
            return

        cur.close()
        QMessageBox.information(
            self,
            "Applied",
            f"Updated {updated_rows} transaction row(s).",
        )
        self._load_pairs()
