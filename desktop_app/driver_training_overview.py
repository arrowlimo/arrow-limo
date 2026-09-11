"""Fleet-wide training checklist overview and bulk assignment.

The per-driver view lives in ``driver_training_checklist``. This module answers
the other half of the question: which checklists are outstanding across every
driver, and how do you attach a checklist to many drivers at once instead of
opening each employee in turn.
"""

import logging

from db_error_handling import DatabaseContext
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

CATEGORY_LABELS = {
    "municipal": "🏛️ Municipal / Bylaw",
    "provincial": "📋 Provincial",
    "federal": "🇨🇦 Federal",
    "company": "🏢 Company",
}

STATUS_FILTERS = [
    "All drivers",
    "Has expired training",
    "Has outstanding mandatory",
    "Fully compliant",
]

COLOR_EXPIRED = QColor(255, 205, 205)
COLOR_OUTSTANDING = QColor(255, 235, 190)
COLOR_OK = QColor(210, 245, 210)


class BulkAssignDialog(QDialog):
    """Pick which programs to attach to which drivers."""

    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Assign Training Checklist to Drivers")
        self.setMinimumSize(720, 520)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout()

        intro = QLabel(
            "Select the programs to assign and the drivers to assign them to. "
            "Drivers who already have a row for a program keep their existing "
            "progress — nothing is overwritten or reset."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        columns = QHBoxLayout()

        prog_box = QGroupBox("Programs")
        prog_layout = QVBoxLayout()
        self.program_list = QListWidget()
        prog_layout.addWidget(self.program_list)
        prog_btns = QHBoxLayout()
        mandatory_btn = QPushButton("Select mandatory")
        mandatory_btn.clicked.connect(self._select_mandatory)
        prog_btns.addWidget(mandatory_btn)
        none_btn = QPushButton("Clear")
        none_btn.clicked.connect(
            lambda: self._set_all(self.program_list, Qt.CheckState.Unchecked)
        )
        prog_btns.addWidget(none_btn)
        prog_layout.addLayout(prog_btns)
        prog_box.setLayout(prog_layout)
        columns.addWidget(prog_box)

        drv_box = QGroupBox("Drivers")
        drv_layout = QVBoxLayout()
        self.active_only = QCheckBox("Active employees only")
        self.active_only.setChecked(True)
        self.active_only.stateChanged.connect(self._load_drivers)
        drv_layout.addWidget(self.active_only)
        self.driver_list = QListWidget()
        drv_layout.addWidget(self.driver_list)
        drv_btns = QHBoxLayout()
        all_btn = QPushButton("Select all")
        all_btn.clicked.connect(
            lambda: self._set_all(self.driver_list, Qt.CheckState.Checked)
        )
        drv_btns.addWidget(all_btn)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(
            lambda: self._set_all(self.driver_list, Qt.CheckState.Unchecked)
        )
        drv_btns.addWidget(clear_btn)
        drv_layout.addLayout(drv_btns)
        drv_box.setLayout(drv_layout)
        columns.addWidget(drv_box)

        layout.addLayout(columns)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Assign")
        buttons.accepted.connect(self._assign)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    @staticmethod
    def _set_all(widget, state) -> None:
        for i in range(widget.count()):
            widget.item(i).setCheckState(state)

    def _select_mandatory(self) -> None:
        for i in range(self.program_list.count()):
            item = self.program_list.item(i)
            mandatory = item.data(Qt.ItemDataRole.UserRole + 1)
            item.setCheckState(
                Qt.CheckState.Checked if mandatory else Qt.CheckState.Unchecked
            )

    def _load(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT program_id, program_name, category, is_mandatory,
                           sort_order
                      FROM training_programs
                     WHERE is_active IS NOT FALSE
                     ORDER BY sort_order
                    """
                )
                programs = cur.fetchall() or []
        except Exception as exc:
            logger.exception("Failed to load programs")
            QMessageBox.critical(self, "Load Failed", str(exc))
            return

        for pid, name, category, mandatory, step in programs:
            label = f"{step}. {name}  [{CATEGORY_LABELS.get(category, category)}]"
            if mandatory:
                label += "  ★"
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, pid)
            item.setData(Qt.ItemDataRole.UserRole + 1, bool(mandatory))
            self.program_list.addItem(item)

        self._load_drivers()

    def _load_drivers(self) -> None:
        self.driver_list.clear()
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                if self.active_only.isChecked():
                    cur.execute(
                        """
                        SELECT employee_id, first_name, last_name, driver_code
                          FROM employees
                         WHERE employment_status = 'active'
                         ORDER BY last_name, first_name
                        """
                    )
                else:
                    cur.execute(
                        """
                        SELECT employee_id, first_name, last_name, driver_code
                          FROM employees
                         ORDER BY last_name, first_name
                        """
                    )
                drivers = cur.fetchall() or []
        except Exception as exc:
            logger.exception("Failed to load drivers")
            QMessageBox.critical(self, "Load Failed", str(exc))
            return

        for eid, first, last, code in drivers:
            label = f"{last or ''}, {first or ''}".strip(", ")
            if code:
                label += f"  ({code})"
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, eid)
            self.driver_list.addItem(item)

    @staticmethod
    def _checked_ids(widget):
        return [
            widget.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(widget.count())
            if widget.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _assign(self) -> None:
        program_ids = self._checked_ids(self.program_list)
        driver_ids = self._checked_ids(self.driver_list)

        if not program_ids or not driver_ids:
            QMessageBox.information(
                self,
                "Nothing Selected",
                "Select at least one program and one driver.",
            )
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO employee_training_records
                        (employee_id, program_id, status)
                    SELECT e.id, p.id, 'not_started'
                      FROM UNNEST(%s::int[]) AS e(id)
                     CROSS JOIN UNNEST(%s::int[]) AS p(id)
                    ON CONFLICT (employee_id, program_id) DO NOTHING
                    """,
                    (driver_ids, program_ids),
                )
                added = cur.rowcount
        except Exception as exc:
            logger.exception("Bulk assign failed")
            QMessageBox.critical(self, "Assign Failed", str(exc))
            return

        skipped = len(program_ids) * len(driver_ids) - added
        QMessageBox.information(
            self,
            "Checklists Assigned",
            f"Added {added} new checklist row(s).\n"
            f"{skipped} already existed and were left untouched.",
        )
        self.accept()


class TrainingOverviewWidget(QWidget):
    """Company-wide training compliance grid."""

    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout()

        self.summary_label = QLabel()
        self.summary_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Show:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(STATUS_FILTERS)
        self.filter_combo.currentIndexChanged.connect(self.reload)
        controls.addWidget(self.filter_combo)

        self.active_only = QCheckBox("Active only")
        self.active_only.setChecked(True)
        self.active_only.stateChanged.connect(self.reload)
        controls.addWidget(self.active_only)

        assign_btn = QPushButton("➕ Assign Checklist to Drivers")
        assign_btn.clicked.connect(self._bulk_assign)
        controls.addWidget(assign_btn)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.reload)
        controls.addWidget(refresh_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                "Driver",
                "Hired",
                "Complete",
                "In Progress",
                "Outstanding",
                "Expired",
                "Next Renewal Due",
            ]
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.table)

        self.setLayout(layout)

    def reload(self) -> None:
        self.table.setRowCount(0)
        active_clause = (
            "WHERE v.employment_status = 'active'"
            if self.active_only.isChecked()
            else ""
        )
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    f"""
                    SELECT v.employee_id,
                           v.first_name,
                           v.last_name,
                           e.hire_date,
                           COUNT(*) FILTER (WHERE v.effective_status = 'completed')   AS complete,
                           COUNT(*) FILTER (WHERE v.effective_status = 'in_progress') AS in_progress,
                           COUNT(*) FILTER (WHERE v.effective_status = 'not_started'
                                              AND v.is_mandatory IS TRUE)             AS outstanding,
                           COUNT(*) FILTER (WHERE v.effective_status = 'expired')     AS expired,
                           MIN(v.expiry_date) FILTER (
                               WHERE v.expiry_date >= CURRENT_DATE)                   AS next_due
                      FROM v_employee_training_status v
                      JOIN employees e ON e.employee_id = v.employee_id
                    {active_clause}
                     GROUP BY v.employee_id, v.first_name, v.last_name, e.hire_date
                     ORDER BY expired DESC, outstanding DESC, v.last_name
                    """
                )
                rows = cur.fetchall() or []
        except Exception as exc:
            logger.exception("Failed to load training overview")
            self.summary_label.setText(f"Could not load overview: {exc}")
            return

        chosen = self.filter_combo.currentText()
        if chosen == "Has expired training":
            rows = [r for r in rows if r[7]]
        elif chosen == "Has outstanding mandatory":
            rows = [r for r in rows if r[6]]
        elif chosen == "Fully compliant":
            rows = [r for r in rows if not r[6] and not r[7]]

        self.table.setRowCount(len(rows))
        drivers_expired = drivers_outstanding = 0

        for i, row in enumerate(rows):
            (_eid, first, last, hired, complete, in_prog, outstanding,
             expired, next_due) = row
            if expired:
                drivers_expired += 1
            if outstanding:
                drivers_outstanding += 1

            cells = [
                f"{last or ''}, {first or ''}".strip(", "),
                str(hired or ""),
                str(complete),
                str(in_prog),
                str(outstanding),
                str(expired),
                str(next_due or ""),
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if expired:
                    item.setBackground(QBrush(COLOR_EXPIRED))
                elif outstanding:
                    item.setBackground(QBrush(COLOR_OUTSTANDING))
                else:
                    item.setBackground(QBrush(COLOR_OK))
                self.table.setItem(i, col, item)

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.summary_label.setText(
            f"{len(rows)} driver(s) shown   |   "
            f"🔴 {drivers_expired} with expired training   |   "
            f"⬜ {drivers_outstanding} with outstanding mandatory training"
        )

    def _bulk_assign(self) -> None:
        dialog = BulkAssignDialog(self.db, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.reload()
