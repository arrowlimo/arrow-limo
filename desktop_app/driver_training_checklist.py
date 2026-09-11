"""Per-driver training and onboarding checklist.

``training_programs`` and ``training_checklist_items`` describe WHAT training
exists. This widget records WHICH DRIVER has done WHICH training, as a
step-by-step sequence from hire date onward, grouped into the municipal
(bylaw), provincial, federal and company checklists.

Completion dates drive expiry automatically: the ``training_set_expiry``
trigger derives ``expiry_date`` from each program's ``expiry_months``, so a
yearly program renewed today is next due in twelve months without anyone
having to calculate it.
"""

import logging

from db_error_handling import DatabaseContext
from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
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
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

STATUS_CHOICES = ["not_started", "in_progress", "completed", "expired", "waived"]

STATUS_LABELS = {
    "not_started": "⬜ Not started",
    "in_progress": "🟡 In progress",
    "completed": "✅ Completed",
    "expired": "🔴 Expired",
    "waived": "➖ Waived",
}

CATEGORY_LABELS = {
    "municipal": "🏛️ Municipal / Bylaw",
    "provincial": "📋 Provincial",
    "federal": "🇨🇦 Federal",
    "company": "🏢 Company",
}

COL_STEP = 0
COL_CATEGORY = 1
COL_PROGRAM = 2
COL_REQUIRED = 3
COL_STATUS = 4
COL_STARTED = 5
COL_COMPLETED = 6
COL_EXPIRY = 7
COL_DUE = 8

COLOR_EXPIRED = QColor(255, 205, 205)
COLOR_SOON = QColor(255, 235, 190)
COLOR_DONE = QColor(210, 245, 210)
COLOR_MISSING = QColor(240, 240, 240)

EXPIRY_WARNING_DAYS = 60


class TrainingEntryDialog(QDialog):
    """Record or update one driver's progress on a single program."""

    def __init__(self, program_name, record, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Training — {program_name}")
        self.setMinimumWidth(420)

        form = QFormLayout()

        self.status_combo = QComboBox()
        for key in STATUS_CHOICES:
            self.status_combo.addItem(STATUS_LABELS[key], key)
        current = (record or {}).get("status") or "not_started"
        idx = self.status_combo.findData(current)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)
        form.addRow("Status:", self.status_combo)

        self.started_edit = self._date_edit((record or {}).get("started_date"))
        form.addRow("Started:", self._with_clear(self.started_edit))

        self.completed_edit = self._date_edit((record or {}).get("completed_date"))
        form.addRow("Completed:", self._with_clear(self.completed_edit))

        self.trainer_edit = QLineEdit((record or {}).get("trainer_name") or "")
        form.addRow("Trainer:", self.trainer_edit)

        self.score_edit = QLineEdit(
            "" if (record or {}).get("score") is None else str(record["score"])
        )
        self.score_edit.setPlaceholderText("optional, e.g. 92.5")
        form.addRow("Score:", self.score_edit)

        self.notes_edit = QTextEdit((record or {}).get("notes") or "")
        self.notes_edit.setMaximumHeight(70)
        form.addRow("Notes:", self.notes_edit)

        hint = QLabel(
            "Expiry is calculated automatically from the program's renewal "
            "interval when a completion date is set."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555; font-size: 11px;")
        form.addRow("", hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    @staticmethod
    def _date_edit(value):
        edit = QDateEdit()
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("yyyy-MM-dd")
        edit.setSpecialValueText(" ")
        edit.setMinimumDate(QDate(1900, 1, 1))
        if value:
            edit.setDate(QDate(value.year, value.month, value.day))
        else:
            edit.setDate(edit.minimumDate())
        return edit

    @staticmethod
    def _with_clear(edit):
        box = QWidget()
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(edit)
        clear = QPushButton("Clear")
        clear.setMaximumWidth(60)
        clear.clicked.connect(lambda: edit.setDate(edit.minimumDate()))
        row.addWidget(clear)
        box.setLayout(row)
        return box

    @staticmethod
    def _value(edit):
        if edit.date() == edit.minimumDate():
            return None
        return edit.date().toPyDate()

    def values(self):
        score_text = self.score_edit.text().strip()
        try:
            score = float(score_text) if score_text else None
        except ValueError:
            score = None
        return {
            "status": self.status_combo.currentData(),
            "started_date": self._value(self.started_edit),
            "completed_date": self._value(self.completed_edit),
            "trainer_name": self.trainer_edit.text().strip() or None,
            "score": score,
            "notes": self.notes_edit.toPlainText().strip() or None,
        }


class DriverTrainingChecklistWidget(QWidget):
    """Step-by-step training checklist for one driver."""

    progress_changed = pyqtSignal()

    def __init__(self, db, employee_id=None, auth_user=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.employee_id = employee_id
        self.auth_user = auth_user
        self._rows = []
        self._build_ui()
        self.reload()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        layout = QVBoxLayout()

        self.summary_label = QLabel()
        self.summary_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        controls = QHBoxLayout()
        assign_btn = QPushButton("➕ Assign All Mandatory")
        assign_btn.setToolTip(
            "Create checklist rows for every mandatory program this driver "
            "is missing. Existing progress is never overwritten."
        )
        assign_btn.clicked.connect(self._assign_mandatory)
        controls.addWidget(assign_btn)

        edit_btn = QPushButton("✏️ Record / Update Selected")
        edit_btn.clicked.connect(self._edit_selected)
        controls.addWidget(edit_btn)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.reload)
        controls.addWidget(refresh_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(
            [
                "Step",
                "Checklist",
                "Program",
                "Required",
                "Status",
                "Started",
                "Completed",
                "Expires",
                "Days Left",
            ]
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._edit_selected)
        self.table.itemSelectionChanged.connect(self._load_items)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_PROGRAM, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, stretch=3)

        self.items_group = QGroupBox("Checklist items for selected program")
        items_layout = QVBoxLayout()
        self.items_list = QListWidget()
        self.items_list.itemChanged.connect(self._item_toggled)
        items_layout.addWidget(self.items_list)
        self.items_group.setLayout(items_layout)
        layout.addWidget(self.items_group, stretch=1)

        self.setLayout(layout)

    # --------------------------------------------------------------- loading
    def reload(self) -> None:
        self.table.setRowCount(0)
        self._rows = []
        if not self.employee_id:
            self.summary_label.setText("Save this employee before tracking training.")
            return

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT step_number, category, program_name, is_mandatory,
                           effective_status, started_date, completed_date,
                           expiry_date, days_until_expiry, program_id
                      FROM v_employee_training_status
                     WHERE employee_id = %s
                     ORDER BY step_number
                    """,
                    (self.employee_id,),
                )
                self._rows = cur.fetchall() or []

                cur.execute(
                    "SELECT hire_date FROM employees WHERE employee_id = %s",
                    (self.employee_id,),
                )
                hire = cur.fetchone()
        except Exception as exc:
            logger.exception("Failed to load training checklist")
            self.summary_label.setText(f"Could not load training checklist: {exc}")
            return

        self._render(self._rows, hire[0] if hire else None)

    def _render(self, rows, hire_date) -> None:
        self.table.setRowCount(len(rows))
        done = expired = in_progress = outstanding = 0

        for i, row in enumerate(rows):
            (
                step,
                category,
                program,
                mandatory,
                status,
                started,
                completed,
                expiry,
                days_left,
                _pid,
            ) = row

            if status == "completed":
                done += 1
            elif status == "expired":
                expired += 1
            elif status == "in_progress":
                in_progress += 1
            elif status == "not_started" and mandatory:
                outstanding += 1

            cells = [
                str(step or ""),
                CATEGORY_LABELS.get(category, category or ""),
                str(program or ""),
                "Yes" if mandatory else "Optional",
                STATUS_LABELS.get(status, status or ""),
                str(started or ""),
                str(completed or ""),
                str(expiry or ""),
                "" if days_left is None else str(days_left),
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if status == "expired":
                    item.setBackground(QBrush(COLOR_EXPIRED))
                elif status == "completed":
                    if days_left is not None and days_left <= EXPIRY_WARNING_DAYS:
                        item.setBackground(QBrush(COLOR_SOON))
                    else:
                        item.setBackground(QBrush(COLOR_DONE))
                elif status == "not_started" and mandatory:
                    item.setBackground(QBrush(COLOR_MISSING))
                self.table.setItem(i, col, item)

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(
            COL_PROGRAM, QHeaderView.ResizeMode.Stretch
        )

        hire_text = f"Hired {hire_date}" if hire_date else "Hire date not recorded"
        parts = [
            hire_text,
            f"✅ {done} complete",
            f"🟡 {in_progress} in progress",
        ]
        if expired:
            parts.append(f"🔴 {expired} EXPIRED")
        if outstanding:
            parts.append(f"⬜ {outstanding} mandatory outstanding")
        self.summary_label.setText("   |   ".join(parts))

    def _selected_program(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._rows):
            return None
        return self._rows[row]

    def _load_items(self) -> None:
        """Show the tick-off items belonging to the selected program."""
        self.items_list.blockSignals(True)
        self.items_list.clear()
        self.items_list.blockSignals(False)

        selected = self._selected_program()
        if not selected or not self.employee_id:
            return
        program_id = selected[9]

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT i.item_id, i.item_name, i.is_required,
                           COALESCE(p.completed, FALSE), p.completed_date
                      FROM training_checklist_items i
                      LEFT JOIN employee_checklist_progress p
                             ON p.item_id = i.item_id
                            AND p.employee_id = %s
                     WHERE i.program_id = %s
                     ORDER BY i.sort_order, i.item_id
                    """,
                    (self.employee_id, program_id),
                )
                items = cur.fetchall() or []
        except Exception as exc:
            logger.exception("Failed to load checklist items")
            self.items_list.addItem(f"Could not load items: {exc}")
            return

        self.items_list.blockSignals(True)
        if not items:
            placeholder = QListWidgetItem(
                "No individual checklist items defined for this program."
            )
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.items_list.addItem(placeholder)
        for item_id, name, required, completed, completed_date in items:
            label = name if required else f"{name} (optional)"
            if completed and completed_date:
                label = f"{label}  —  {completed_date}"
            entry = QListWidgetItem(label)
            entry.setFlags(entry.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            entry.setCheckState(
                Qt.CheckState.Checked if completed else Qt.CheckState.Unchecked
            )
            entry.setData(Qt.ItemDataRole.UserRole, item_id)
            self.items_list.addItem(entry)
        self.items_list.blockSignals(False)

    # --------------------------------------------------------------- actions
    def _assign_mandatory(self) -> None:
        if not self.employee_id:
            return
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO employee_training_records (employee_id, program_id, status)
                    SELECT %s, p.program_id, 'not_started'
                      FROM training_programs p
                     WHERE p.is_mandatory IS TRUE
                       AND p.is_active IS NOT FALSE
                    ON CONFLICT (employee_id, program_id) DO NOTHING
                    """,
                    (self.employee_id,),
                )
                added = cur.rowcount
        except Exception as exc:
            logger.exception("Failed to assign mandatory training")
            QMessageBox.critical(self, "Assign Failed", str(exc))
            return

        QMessageBox.information(
            self,
            "Checklist Assigned",
            f"Added {added} mandatory program(s).\n\n"
            "Existing progress was left untouched.",
        )
        self.reload()
        self.progress_changed.emit()

    def _edit_selected(self) -> None:
        selected = self._selected_program()
        if not selected:
            QMessageBox.information(
                self, "No Selection", "Select a program row first."
            )
            return

        program_id = selected[9]
        program_name = selected[2]

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT status, started_date, completed_date, trainer_name,
                           score, notes
                      FROM employee_training_records
                     WHERE employee_id = %s AND program_id = %s
                    """,
                    (self.employee_id, program_id),
                )
                found = cur.fetchone()
        except Exception as exc:
            logger.exception("Failed to read training record")
            QMessageBox.critical(self, "Load Failed", str(exc))
            return

        record = None
        if found:
            record = {
                "status": found[0],
                "started_date": found[1],
                "completed_date": found[2],
                "trainer_name": found[3],
                "score": found[4],
                "notes": found[5],
            }

        dialog = TrainingEntryDialog(program_name, record, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values = dialog.values()
        if values["status"] == "completed" and not values["completed_date"]:
            QMessageBox.warning(
                self,
                "Completion Date Required",
                "A completed program needs a completion date so its renewal "
                "date can be calculated.",
            )
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO employee_training_records
                        (employee_id, program_id, status, started_date,
                         completed_date, trainer_name, score, notes,
                         verified_by, verified_at)
                    VALUES (%s, %s, %s, %s::date, %s::date, %s, %s, %s, %s, NOW())
                    ON CONFLICT (employee_id, program_id) DO UPDATE SET
                        status         = EXCLUDED.status,
                        started_date   = EXCLUDED.started_date,
                        completed_date = EXCLUDED.completed_date,
                        trainer_name   = EXCLUDED.trainer_name,
                        score          = EXCLUDED.score,
                        notes          = EXCLUDED.notes,
                        verified_by    = EXCLUDED.verified_by,
                        verified_at    = NOW()
                    RETURNING expiry_date
                    """,
                    (
                        self.employee_id,
                        program_id,
                        values["status"],
                        values["started_date"],
                        values["completed_date"],
                        values["trainer_name"],
                        values["score"],
                        values["notes"],
                        self.auth_user,
                    ),
                )
                expiry = (cur.fetchone() or [None])[0]

                # Completions are appended to history so a renewed yearly
                # program keeps every previous cycle on record.
                if values["status"] == "completed" and values["completed_date"]:
                    cur.execute(
                        """
                        INSERT INTO employee_training_history
                            (employee_id, program_id, completed_date, expiry_date,
                             trainer_name, score, recorded_by, notes)
                        VALUES (%s, %s, %s::date, %s::date, %s, %s, %s, %s)
                        """,
                        (
                            self.employee_id,
                            program_id,
                            values["completed_date"],
                            expiry,
                            values["trainer_name"],
                            values["score"],
                            self.auth_user,
                            values["notes"],
                        ),
                    )
        except Exception as exc:
            logger.exception("Failed to save training record")
            QMessageBox.critical(self, "Save Failed", str(exc))
            return

        self.reload()
        self.progress_changed.emit()

    def _item_toggled(self, item) -> None:
        item_id = item.data(Qt.ItemDataRole.UserRole)
        if item_id is None or not self.employee_id:
            return
        completed = item.checkState() == Qt.CheckState.Checked

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO employee_checklist_progress
                        (employee_id, item_id, completed, completed_date,
                         verified_by, verified_at)
                    VALUES (%s, %s, %s,
                            CASE WHEN %s THEN CURRENT_DATE ELSE NULL END,
                            %s, NOW())
                    ON CONFLICT (employee_id, item_id) DO UPDATE SET
                        completed      = EXCLUDED.completed,
                        completed_date = EXCLUDED.completed_date,
                        verified_by    = EXCLUDED.verified_by,
                        verified_at    = NOW(),
                        updated_at     = NOW()
                    """,
                    (
                        self.employee_id,
                        item_id,
                        completed,
                        completed,
                        self.auth_user,
                    ),
                )
        except Exception as exc:
            logger.exception("Failed to save checklist item")
            QMessageBox.critical(self, "Save Failed", str(exc))

        self._load_items()
        self.progress_changed.emit()
