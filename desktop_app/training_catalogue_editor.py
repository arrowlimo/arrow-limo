"""Training catalogue editor.

Lets an administrator review the programs and checklist items, correct the
municipal/provincial/federal/company categories, add or remove programs and
reorder the step sequence.

Deletion is guarded. A program any driver has ever completed cannot be
deleted, because ``employee_training_history`` is the permanent proof of that
completion and the database now refuses the delete (ON DELETE RESTRICT).
Deactivating is offered instead: it hides the program from every checklist
while preserving the completion history.
"""

import logging

from db_error_handling import DatabaseContext
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

CATEGORIES = [
    ("municipal", "🏛️ Municipal / Bylaw"),
    ("provincial", "📋 Provincial"),
    ("federal", "🇨🇦 Federal"),
    ("company", "🏢 Company"),
]
CATEGORY_LABELS = dict(CATEGORIES)

COL_STEP = 0
COL_NAME = 1
COL_CATEGORY = 2
COL_MANDATORY = 3
COL_RENEWS = 4
COL_HOURS = 5
COL_ACTIVE = 6
COL_ASSIGNED = 7
COL_HISTORY = 8

COLOR_INACTIVE = QColor(235, 235, 235)
COLOR_LOCKED = QColor(255, 245, 215)


class ProgramEditDialog(QDialog):
    """Add or edit one training program."""

    def __init__(self, record=None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Program" if record else "Add Program")
        self.setMinimumWidth(430)
        record = record or {}

        form = QFormLayout()

        self.name_edit = QLineEdit(record.get("program_name") or "")
        form.addRow("Program name:", self.name_edit)

        self.category_combo = QComboBox()
        for key, label in CATEGORIES:
            self.category_combo.addItem(label, key)
        idx = self.category_combo.findData(record.get("category") or "company")
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        form.addRow("Checklist:", self.category_combo)

        self.mandatory_check = QCheckBox("Mandatory for all drivers")
        self.mandatory_check.setChecked(bool(record.get("is_mandatory", True)))
        form.addRow("", self.mandatory_check)

        self.red_deer_check = QCheckBox("Required by Red Deer bylaw")
        self.red_deer_check.setChecked(bool(record.get("red_deer_required", False)))
        form.addRow("", self.red_deer_check)

        self.expiry_spin = QSpinBox()
        self.expiry_spin.setRange(0, 120)
        self.expiry_spin.setSuffix(" months")
        self.expiry_spin.setSpecialValueText("Never expires")
        self.expiry_spin.setValue(int(record.get("expiry_months") or 0))
        form.addRow("Renews every:", self.expiry_spin)

        self.hours_spin = QDoubleSpinBox()
        self.hours_spin.setRange(0, 999)
        self.hours_spin.setDecimals(2)
        self.hours_spin.setSuffix(" hrs")
        self.hours_spin.setValue(float(record.get("duration_hours") or 0))
        form.addRow("Duration:", self.hours_spin)

        self.step_spin = QSpinBox()
        self.step_spin.setRange(0, 999)
        self.step_spin.setValue(int(record.get("sort_order") or 0))
        form.addRow("Step number:", self.step_spin)

        self.active_check = QCheckBox("Active (shown on driver checklists)")
        self.active_check.setChecked(bool(record.get("is_active", True)))
        form.addRow("", self.active_check)

        self.desc_edit = QTextEdit(record.get("description") or "")
        self.desc_edit.setMaximumHeight(70)
        form.addRow("Description:", self.desc_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _validate(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Name Required", "Enter a program name.")
            return
        self.accept()

    def values(self) -> dict:
        return {
            "program_name": self.name_edit.text().strip(),
            "category": self.category_combo.currentData(),
            "is_mandatory": self.mandatory_check.isChecked(),
            "red_deer_required": self.red_deer_check.isChecked(),
            "expiry_months": self.expiry_spin.value() or None,
            "duration_hours": self.hours_spin.value() or None,
            "sort_order": self.step_spin.value(),
            "is_active": self.active_check.isChecked(),
            "description": self.desc_edit.toPlainText().strip() or None,
        }


class TrainingCatalogueWidget(QWidget):
    """Review and maintain the training program catalogue."""

    catalogue_changed = pyqtSignal()

    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self._rows = []
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout()

        note = QLabel(
            "Review the checklist each program belongs to and remove anything "
            "that does not apply. Programs a driver has already completed "
            "cannot be deleted — deactivate them instead, which hides them "
            "from every checklist while keeping the completion history."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            "background:#fef9c3;border:1px solid #fde047;"
            "border-radius:6px;padding:8px;color:#713f12;"
        )
        layout.addWidget(note)

        self.summary_label = QLabel()
        self.summary_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(self.summary_label)

        controls = QHBoxLayout()
        for text, slot in (
            ("➕ Add Program", self._add),
            ("✏️ Edit Selected", self._edit),
            ("🚫 Deactivate Selected", self._deactivate),
            ("🗑️ Delete Selected", self._delete),
            ("📋 Edit Items", self._edit_items),
            ("🔄 Refresh", self.reload),
        ):
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            controls.addWidget(btn)
        controls.addStretch()
        layout.addLayout(controls)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(
            [
                "Step",
                "Program",
                "Checklist",
                "Mandatory",
                "Renews",
                "Hours",
                "Active",
                "Drivers Assigned",
                "Completions Recorded",
            ]
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._edit)
        self.table.horizontalHeader().setSectionResizeMode(
            COL_NAME, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.table)

        self.setLayout(layout)

    # --------------------------------------------------------------- loading
    def reload(self) -> None:
        self.table.setRowCount(0)
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT p.program_id, p.sort_order, p.program_name, p.category,
                           p.is_mandatory, p.expiry_months, p.duration_hours,
                           p.is_active, p.red_deer_required, p.description,
                           (SELECT COUNT(*) FROM employee_training_records r
                             WHERE r.program_id = p.program_id),
                           (SELECT COUNT(*) FROM employee_training_history h
                             WHERE h.program_id = p.program_id)
                      FROM training_programs p
                     ORDER BY p.sort_order, p.program_name
                    """
                )
                self._rows = cur.fetchall() or []
        except Exception as exc:
            logger.exception("Failed to load training catalogue")
            self.summary_label.setText(f"Could not load catalogue: {exc}")
            return

        self.table.setRowCount(len(self._rows))
        active = locked = 0

        for i, row in enumerate(self._rows):
            (
                _pid, step, name, category, mandatory, months, hours,
                is_active, _rd, _desc, assigned, history,
            ) = row
            if is_active:
                active += 1
            if history:
                locked += 1

            cells = [
                str(step or ""),
                str(name or ""),
                CATEGORY_LABELS.get(category, category or ""),
                "Yes" if mandatory else "Optional",
                f"{months} mo" if months else "Never",
                "" if hours is None else f"{float(hours):g}",
                "Yes" if is_active else "No",
                str(assigned),
                str(history),
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if not is_active:
                    item.setBackground(QBrush(COLOR_INACTIVE))
                elif history:
                    item.setBackground(QBrush(COLOR_LOCKED))
                self.table.setItem(i, col, item)

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(
            COL_NAME, QHeaderView.ResizeMode.Stretch
        )
        self.summary_label.setText(
            f"{len(self._rows)} program(s)   |   {active} active   |   "
            f"{locked} with recorded completions (delete blocked, "
            f"deactivate instead)"
        )

    def _selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._rows):
            QMessageBox.information(self, "No Selection", "Select a program first.")
            return None
        return self._rows[row]

    # --------------------------------------------------------------- actions
    def _add(self) -> None:
        dialog = ProgramEditDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO training_programs
                        (program_name, category, is_mandatory, red_deer_required,
                         expiry_months, duration_hours, sort_order, is_active,
                         description)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        values["program_name"], values["category"],
                        values["is_mandatory"], values["red_deer_required"],
                        values["expiry_months"], values["duration_hours"],
                        values["sort_order"], values["is_active"],
                        values["description"],
                    ),
                )
        except Exception as exc:
            if "uq_training_programs_name" in str(exc):
                QMessageBox.warning(
                    self,
                    "Duplicate Program",
                    f"A program named '{values['program_name']}' already exists.",
                )
            else:
                logger.exception("Failed to add program")
                QMessageBox.critical(self, "Add Failed", str(exc))
            return
        self.reload()
        self.catalogue_changed.emit()

    def _edit(self) -> None:
        selected = self._selected()
        if not selected:
            return
        record = {
            "program_name": selected[2], "category": selected[3],
            "is_mandatory": selected[4], "expiry_months": selected[5],
            "duration_hours": selected[6], "is_active": selected[7],
            "red_deer_required": selected[8], "description": selected[9],
            "sort_order": selected[1],
        }
        dialog = ProgramEditDialog(record, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()

        # Changing the renewal interval does not retroactively move expiry
        # dates already calculated for drivers, so say so rather than let the
        # admin assume every record silently updated.
        if (selected[5] or 0) != (values["expiry_months"] or 0) and selected[10]:
            confirm = QMessageBox.question(
                self,
                "Renewal Interval Changed",
                f"{selected[10]} driver record(s) already exist for this "
                "program.\n\nExisting expiry dates are NOT recalculated — the "
                "new interval applies the next time each driver's completion "
                "date is recorded.\n\nContinue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    UPDATE training_programs
                       SET program_name = %s, category = %s, is_mandatory = %s,
                           red_deer_required = %s, expiry_months = %s,
                           duration_hours = %s, sort_order = %s, is_active = %s,
                           description = %s
                     WHERE program_id = %s
                    """,
                    (
                        values["program_name"], values["category"],
                        values["is_mandatory"], values["red_deer_required"],
                        values["expiry_months"], values["duration_hours"],
                        values["sort_order"], values["is_active"],
                        values["description"], selected[0],
                    ),
                )
        except Exception as exc:
            logger.exception("Failed to update program")
            QMessageBox.critical(self, "Save Failed", str(exc))
            return
        self.reload()
        self.catalogue_changed.emit()

    def _deactivate(self) -> None:
        selected = self._selected()
        if not selected:
            return
        if not selected[7]:
            QMessageBox.information(
                self, "Already Inactive", f"'{selected[2]}' is already inactive."
            )
            return
        confirm = QMessageBox.question(
            self,
            "Deactivate Program",
            f"Hide '{selected[2]}' from all driver checklists?\n\n"
            f"{selected[10]} assignment(s) and {selected[11]} completion "
            "record(s) are preserved and can be restored by reactivating.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "UPDATE training_programs SET is_active = FALSE WHERE program_id = %s",
                    (selected[0],),
                )
        except Exception as exc:
            logger.exception("Failed to deactivate program")
            QMessageBox.critical(self, "Deactivate Failed", str(exc))
            return
        self.reload()
        self.catalogue_changed.emit()

    def _delete(self) -> None:
        selected = self._selected()
        if not selected:
            return
        program_id, name, assigned, history = (
            selected[0], selected[2], selected[10], selected[11],
        )

        if history:
            QMessageBox.warning(
                self,
                "Cannot Delete",
                f"'{name}' has {history} recorded completion(s).\n\n"
                "Deleting it would destroy the proof that those drivers "
                "completed this training, so the database blocks it.\n\n"
                "Use Deactivate instead — the program disappears from every "
                "checklist and the completion history is kept.",
            )
            return

        confirm = QMessageBox.question(
            self,
            "Delete Program",
            f"Permanently delete '{name}'?\n\n"
            f"This also removes its checklist items and {assigned} driver "
            "assignment(s). No completions have been recorded, so no training "
            "history is lost.\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "DELETE FROM training_programs WHERE program_id = %s",
                    (program_id,),
                )
        except Exception as exc:
            logger.exception("Failed to delete program")
            QMessageBox.critical(
                self,
                "Delete Failed",
                f"{exc}\n\nIf this mentions a foreign key, the program has "
                "completion history and must be deactivated instead.",
            )
            return
        self.reload()
        self.catalogue_changed.emit()

    def _edit_items(self) -> None:
        selected = self._selected()
        if not selected:
            return
        dialog = ChecklistItemsDialog(self.db, selected[0], selected[2], parent=self)
        dialog.exec()
        self.reload()
        self.catalogue_changed.emit()


class ChecklistItemsDialog(QDialog):
    """Maintain the tick-off items belonging to one program."""

    def __init__(self, db, program_id, program_name, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.program_id = program_id
        self.setWindowTitle(f"Checklist Items — {program_name}")
        self.setMinimumSize(520, 420)

        layout = QVBoxLayout()
        layout.addWidget(
            QLabel("Items a driver ticks off while completing this program.")
        )

        self.list = QListWidget()
        layout.addWidget(self.list)

        buttons = QHBoxLayout()
        for text, slot in (
            ("➕ Add", self._add),
            ("✏️ Rename", self._rename),
            ("🗑️ Remove", self._remove),
        ):
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            buttons.addWidget(btn)
        buttons.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        self.setLayout(layout)
        self._load()

    def _load(self) -> None:
        self.list.clear()
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT i.item_id, i.item_name, i.sort_order,
                           (SELECT COUNT(*) FROM employee_checklist_progress p
                             WHERE p.item_id = i.item_id AND p.completed)
                      FROM training_checklist_items i
                     WHERE i.program_id = %s
                     ORDER BY i.sort_order, i.item_id
                    """,
                    (self.program_id,),
                )
                rows = cur.fetchall() or []
        except Exception as exc:
            logger.exception("Failed to load checklist items")
            QMessageBox.critical(self, "Load Failed", str(exc))
            return

        for item_id, name, order, done in rows:
            label = f"{order}. {name}"
            if done:
                label += f"   ({done} driver(s) completed)"
            entry = QListWidgetItem(label)
            entry.setData(Qt.ItemDataRole.UserRole, item_id)
            entry.setData(Qt.ItemDataRole.UserRole + 1, done)
            entry.setData(Qt.ItemDataRole.UserRole + 2, name)
            self.list.addItem(entry)

    def _add(self) -> None:
        name, ok = QInputDialog.getText(self, "Add Item", "Item name:")
        if not ok or not name.strip():
            return
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO training_checklist_items
                        (program_id, item_name, is_required, sort_order)
                    VALUES (%s, %s, TRUE,
                            COALESCE((SELECT MAX(sort_order) + 1
                                        FROM training_checklist_items
                                       WHERE program_id = %s), 1))
                    """,
                    (self.program_id, name.strip(), self.program_id),
                )
        except Exception as exc:
            if "uq_training_checklist_items_program_name" in str(exc):
                QMessageBox.warning(
                    self, "Duplicate Item", f"'{name.strip()}' already exists."
                )
            else:
                logger.exception("Failed to add item")
                QMessageBox.critical(self, "Add Failed", str(exc))
            return
        self._load()

    def _rename(self) -> None:
        entry = self.list.currentItem()
        if not entry:
            return
        current = entry.data(Qt.ItemDataRole.UserRole + 2)
        name, ok = QInputDialog.getText(
            self, "Rename Item", "Item name:", text=current
        )
        if not ok or not name.strip():
            return
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "UPDATE training_checklist_items SET item_name = %s WHERE item_id = %s",
                    (name.strip(), entry.data(Qt.ItemDataRole.UserRole)),
                )
        except Exception as exc:
            logger.exception("Failed to rename item")
            QMessageBox.critical(self, "Rename Failed", str(exc))
            return
        self._load()

    def _remove(self) -> None:
        entry = self.list.currentItem()
        if not entry:
            return
        done = entry.data(Qt.ItemDataRole.UserRole + 1) or 0
        message = f"Remove '{entry.data(Qt.ItemDataRole.UserRole + 2)}'?"
        if done:
            message += (
                f"\n\n{done} driver(s) have ticked this item off. That "
                "progress will be removed with it."
            )
        confirm = QMessageBox.question(
            self,
            "Remove Item",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "DELETE FROM training_checklist_items WHERE item_id = %s",
                    (entry.data(Qt.ItemDataRole.UserRole),),
                )
        except Exception as exc:
            logger.exception("Failed to remove item")
            QMessageBox.critical(self, "Remove Failed", str(exc))
            return
        self._load()
