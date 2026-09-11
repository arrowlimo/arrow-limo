"""Employee qualification and document records.

Holds the licences, permits, certificates and forms kept for each employee in
``driver_documents``: driver's licence, Red Deer driver-for-hire permit,
ProServe, medical, abstracts, training certificates and general paperwork.

Rows carry the issue and expiry dates that drive compliance, so this widget
supports full add, edit and delete rather than being a read-only list.
"""

import logging
from datetime import date

from db_error_handling import DatabaseContext
from PyQt6.QtCore import QDate, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
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

DOCUMENT_TYPES = [
    ("license", "Driver's Licence"),
    ("chauffeur_permit", "Driver-for-Hire / Chauffeur Permit"),
    ("proserve", "ProServe Certification"),
    ("medical_certificate", "Medical / Fitness"),
    ("driver_abstract", "Driver Abstract"),
    ("vulnerable_sector", "Vulnerable Sector / Police Check"),
    ("background_check", "Background Check"),
    ("drug_test", "Drug Test"),
    ("training_certificate", "Training Certificate"),
    ("insurance", "Insurance"),
    ("t4", "T4 / Tax Slip"),
    ("employment_contract", "Employment Contract"),
    ("roe", "Record of Employment"),
    ("other", "Other"),
]
TYPE_LABELS = dict(DOCUMENT_TYPES)

# Records created before the portal existed stored free-form types that do not
# match the current vocabulary. Map the ones actually present so they render
# with a proper label instead of falling back to the raw column value.
LEGACY_TYPE_LABELS = {
    "licence": "Driver's Licence",
    "permit": "Driver-for-Hire / Chauffeur Permit",
    "medical": "Medical / Fitness",
    "abstract": "Driver Abstract",
    "training": "Training Certificate",
}


def _type_label(document_type) -> str:
    if not document_type:
        return ""
    key = str(document_type)
    return (
        TYPE_LABELS.get(key)
        or TYPE_LABELS.get(key.lower())
        or LEGACY_TYPE_LABELS.get(key.lower())
        or key
    )


# Constrained by driver_documents_status_check.
STATUS_CHOICES = ["pending", "active", "expired", "revoked"]

COL_TYPE = 0
COL_NAME = 1
COL_NUMBER = 2
COL_ISSUED = 3
COL_EXPIRY = 4
COL_AUTHORITY = 5
COL_STATUS = 6

COLOR_EXPIRED = QColor(254, 226, 226)
COLOR_SOON = QColor(254, 243, 199)


def _date_edit(value):
    edit = QDateEdit()
    edit.setCalendarPopup(True)
    edit.setDisplayFormat("yyyy-MM-dd")
    edit.setSpecialValueText("(none)")
    edit.setMinimumDate(QDate(1900, 1, 1))
    if value:
        edit.setDate(QDate(value.year, value.month, value.day))
    else:
        edit.setDate(edit.minimumDate())
    return edit


def _date_value(edit):
    if edit.date() == edit.minimumDate():
        return None
    return edit.date().toString("yyyy-MM-dd")


class DocumentEditDialog(QDialog):
    """Add or edit one qualification / document record."""

    def __init__(self, record=None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Record" if record else "Add Record")
        self.setMinimumWidth(430)
        record = record or {}

        form = QFormLayout()

        self.type_combo = QComboBox()
        for key, label in DOCUMENT_TYPES:
            self.type_combo.addItem(label, key)
        current_type = record.get("document_type")
        idx = self.type_combo.findData(current_type)
        if idx < 0 and current_type:
            # Keep a legacy type selectable so editing another field cannot
            # silently retype the record.
            self.type_combo.addItem(
                f"{_type_label(current_type)} (existing)", current_type
            )
            idx = self.type_combo.count() - 1
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        form.addRow("Type:", self.type_combo)

        self.name_edit = QLineEdit(record.get("document_name") or "")
        form.addRow("Description:", self.name_edit)

        self.number_edit = QLineEdit(record.get("document_number") or "")
        form.addRow("Number:", self.number_edit)

        self.issued_edit = _date_edit(record.get("issued_date"))
        form.addRow("Issued:", self.issued_edit)

        self.expiry_edit = _date_edit(record.get("expiry_date"))
        form.addRow("Expires:", self.expiry_edit)

        self.authority_edit = QLineEdit(record.get("issuing_authority") or "")
        form.addRow("Issued by:", self.authority_edit)

        self.status_combo = QComboBox()
        self.status_combo.addItems(STATUS_CHOICES)
        current = record.get("status") or "pending"
        if current in STATUS_CHOICES:
            self.status_combo.setCurrentText(current)
        form.addRow("Status:", self.status_combo)

        self.notes_edit = QTextEdit(record.get("notes") or "")
        self.notes_edit.setMaximumHeight(70)
        form.addRow("Notes:", self.notes_edit)

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
            QMessageBox.warning(
                self, "Description Required", "Enter a short description."
            )
            return
        issued, expiry = _date_value(self.issued_edit), _date_value(self.expiry_edit)
        if issued and expiry and expiry < issued:
            QMessageBox.warning(
                self,
                "Dates Reversed",
                "The expiry date cannot be before the issue date.",
            )
            return
        self.accept()

    def values(self) -> dict:
        return {
            "document_type": self.type_combo.currentData(),
            "document_name": self.name_edit.text().strip(),
            "document_number": self.number_edit.text().strip() or None,
            "issued_date": _date_value(self.issued_edit),
            "expiry_date": _date_value(self.expiry_edit),
            "issuing_authority": self.authority_edit.text().strip() or None,
            "status": self.status_combo.currentText(),
            "notes": self.notes_edit.toPlainText().strip() or None,
        }


class EmployeeDocumentsWidget(QWidget):
    """Add, edit and delete an employee's qualifications and documents."""

    records_changed = pyqtSignal()

    def __init__(self, db, employee_id=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.employee_id = employee_id
        self._rows = []
        self._build_ui()
        self.reload()

    def set_employee(self, employee_id) -> None:
        self.employee_id = employee_id
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self.summary_label = QLabel()
        layout.addWidget(self.summary_label)

        controls = QHBoxLayout()
        controls.setSpacing(6)
        for text, slot in (
            ("➕ Add", self._add),
            ("✏️ Edit", self._edit),
            ("🗑️ Delete", self._delete),
            ("🔄 Refresh", self.reload),
        ):
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            controls.addWidget(btn)
        controls.addStretch()
        layout.addLayout(controls)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                "Type",
                "Description",
                "Number",
                "Issued",
                "Expires",
                "Issued By",
                "Status",
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

    def reload(self) -> None:
        self.table.setRowCount(0)
        self._rows = []
        if not self.employee_id:
            self.summary_label.setText("Select an employee to see their records.")
            return

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT id, document_type, document_name, document_number,
                           issued_date, expiry_date, issuing_authority, status,
                           notes
                      FROM driver_documents
                     WHERE employee_id = %s
                     ORDER BY expiry_date NULLS LAST, document_type
                    """,
                    (self.employee_id,),
                )
                self._rows = cur.fetchall() or []
        except Exception as exc:
            logger.exception("Failed to load employee documents")
            self.summary_label.setText(f"Could not load records: {exc}")
            return

        today = date.today()
        expired = expiring = 0
        self.table.setRowCount(len(self._rows))

        for i, row in enumerate(self._rows):
            (
                _doc_id, doc_type, name, number, issued, expiry,
                authority, status, _notes,
            ) = row

            highlight = None
            if expiry:
                days = (expiry - today).days
                if days < 0:
                    expired += 1
                    highlight = COLOR_EXPIRED
                elif days <= 60:
                    expiring += 1
                    highlight = COLOR_SOON

            cells = [
                _type_label(doc_type),
                name or "",
                number or "",
                issued.isoformat() if issued else "",
                expiry.isoformat() if expiry else "",
                authority or "",
                status or "",
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if highlight:
                    item.setBackground(QBrush(highlight))
                self.table.setItem(i, col, item)

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(
            COL_NAME, QHeaderView.ResizeMode.Stretch
        )

        summary = f"{len(self._rows)} record(s)"
        if expired:
            summary += f"   |   ⛔ {expired} EXPIRED"
        if expiring:
            summary += f"   |   ⚠️ {expiring} expiring within 60 days"
        if not self._rows:
            summary = "No licences, certificates or documents recorded yet."
        self.summary_label.setText(summary)

    def _selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._rows):
            QMessageBox.information(self, "No Selection", "Select a record first.")
            return None
        return self._rows[row]

    def _add(self) -> None:
        if not self.employee_id:
            QMessageBox.information(
                self, "No Employee", "Select an employee first."
            )
            return
        dialog = DocumentEditDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO driver_documents
                        (employee_id, document_type, document_name,
                         document_number, issued_date, expiry_date,
                         issuing_authority, status, notes)
                    VALUES (%s, %s, %s, %s, %s::date, %s::date, %s, %s, %s)
                    """,
                    (
                        self.employee_id,
                        values["document_type"], values["document_name"],
                        values["document_number"], values["issued_date"],
                        values["expiry_date"], values["issuing_authority"],
                        values["status"], values["notes"],
                    ),
                )
        except Exception as exc:
            if "uq_driver_documents_no_exact_dupes" in str(exc):
                QMessageBox.warning(
                    self,
                    "Duplicate Record",
                    "An identical record already exists for this employee.",
                )
            else:
                logger.exception("Failed to add document record")
                QMessageBox.critical(self, "Add Failed", str(exc))
            return
        self.reload()
        self.records_changed.emit()

    def _edit(self) -> None:
        selected = self._selected()
        if not selected:
            return
        record = {
            "document_type": selected[1], "document_name": selected[2],
            "document_number": selected[3], "issued_date": selected[4],
            "expiry_date": selected[5], "issuing_authority": selected[6],
            "status": selected[7], "notes": selected[8],
        }
        dialog = DocumentEditDialog(record, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    UPDATE driver_documents
                       SET document_type = %s, document_name = %s,
                           document_number = %s, issued_date = %s::date,
                           expiry_date = %s::date, issuing_authority = %s,
                           status = %s, notes = %s, updated_at = NOW()
                     WHERE id = %s
                    """,
                    (
                        values["document_type"], values["document_name"],
                        values["document_number"], values["issued_date"],
                        values["expiry_date"], values["issuing_authority"],
                        values["status"], values["notes"], selected[0],
                    ),
                )
        except Exception as exc:
            if "uq_driver_documents_no_exact_dupes" in str(exc):
                QMessageBox.warning(
                    self,
                    "Duplicate Record",
                    "That would make this record identical to another one.",
                )
            else:
                logger.exception("Failed to update document record")
                QMessageBox.critical(self, "Save Failed", str(exc))
            return
        self.reload()
        self.records_changed.emit()

    def _delete(self) -> None:
        selected = self._selected()
        if not selected:
            return
        label = _type_label(selected[1]) or "record"
        confirm = QMessageBox.question(
            self,
            "Delete Record",
            f"Permanently delete this {label} record"
            f" ({selected[2] or 'no description'})?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "DELETE FROM driver_documents WHERE id = %s", (selected[0],)
                )
        except Exception as exc:
            logger.exception("Failed to delete document record")
            QMessageBox.critical(self, "Delete Failed", str(exc))
            return
        self.reload()
        self.records_changed.emit()
