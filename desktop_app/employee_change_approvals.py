"""Administrator review queue for driver-submitted record changes.

Drivers edit their compliance records in the web portal, but those edits land
in ``employee_change_requests`` instead of the live ``employees`` row. This
widget shows the administrator the current value beside the requested value so
nothing (for example a licence class upgrade) goes live without authorization.
"""

import logging

from db_error_handling import DatabaseContext
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# Mirrors the portal whitelist. A field key that is not listed here is never
# written to the employees table, even if a row somehow appears in the queue.
APPROVABLE_FIELDS = {
    "driver_license_number",
    "driver_license_class",
    "driver_license_expiry",
    "chauffeur_permit_number",
    "chauffeur_permit_expiry",
    "proserve_number",
    "proserve_expiry",
    "medical_fitness_expiry",
    "drivers_abstract_date",
    "vulnerable_sector_check_date",
    "phone",
    "cell_phone",
    "email",
    "street_address",
    "city",
    "province",
    "postal_code",
    "emergency_contact_name",
    "emergency_contact_phone",
}

DATE_FIELDS = {
    "driver_license_expiry",
    "chauffeur_permit_expiry",
    "proserve_expiry",
    "medical_fitness_expiry",
    "drivers_abstract_date",
    "vulnerable_sector_check_date",
}

COL_SELECT = 0
COL_DRIVER = 1
COL_FIELD = 2
COL_CURRENT = 3
COL_REQUESTED = 4
COL_SUBMITTED = 5


class EmployeeChangeApprovalsWidget(QWidget):
    """Pending driver record changes awaiting administrator authorization."""

    changes_applied = pyqtSignal()

    def __init__(self, db, employee_id=None, auth_user=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.employee_id = employee_id
        self._reviewer = (
            auth_user.get("username", "admin") if auth_user else "admin"
        )
        self._requests = []
        self._documents = []
        self._init_ui()
        self.refresh()

    # ------------------------------------------------------------------ UI
    def _init_ui(self) -> None:
        layout = QVBoxLayout()

        header = QLabel("🔐 Driver Record Changes Awaiting Authorization")
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            [
                "Apply",
                "Driver",
                "Field",
                "Current Value",
                "Requested Value",
                "Submitted",
            ]
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setAlternatingRowColors(True)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(COL_SELECT, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(COL_SELECT, 55)
        for column in (COL_DRIVER, COL_FIELD, COL_CURRENT, COL_REQUESTED, COL_SUBMITTED):
            header_view.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        button_row = QHBoxLayout()

        self.select_all_btn = QPushButton("☑️ Select All")
        self.select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        button_row.addWidget(self.select_all_btn)

        self.select_none_btn = QPushButton("☐ Select None")
        self.select_none_btn.clicked.connect(lambda: self._set_all_checked(False))
        button_row.addWidget(self.select_none_btn)

        button_row.addStretch()

        self.approve_selected_btn = QPushButton("✅ Authorize Selected")
        self.approve_selected_btn.clicked.connect(self.approve_selected)
        button_row.addWidget(self.approve_selected_btn)

        self.approve_all_btn = QPushButton("✅ Authorize All")
        self.approve_all_btn.clicked.connect(self.approve_all)
        button_row.addWidget(self.approve_all_btn)

        self.reject_selected_btn = QPushButton("❌ Reject Selected")
        self.reject_selected_btn.clicked.connect(self.reject_selected)
        button_row.addWidget(self.reject_selected_btn)

        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        button_row.addWidget(self.refresh_btn)

        layout.addLayout(button_row)

        doc_header = QLabel("📎 Uploaded Documents Awaiting Review")
        doc_font = QFont()
        doc_font.setBold(True)
        doc_header.setFont(doc_font)
        layout.addWidget(doc_header)

        self.doc_table = QTableWidget()
        self.doc_table.setColumnCount(6)
        self.doc_table.setHorizontalHeaderLabels(
            ["Driver", "Type", "File", "Size", "Expiry", "Uploaded"]
        )
        self.doc_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.doc_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.doc_table.setMaximumHeight(180)
        doc_header_view = self.doc_table.horizontalHeader()
        for column in range(6):
            doc_header_view.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.doc_table)

        doc_buttons = QHBoxLayout()
        doc_buttons.addStretch()
        self.save_doc_btn = QPushButton("💾 Save Document to File")
        self.save_doc_btn.clicked.connect(self.save_selected_document)
        doc_buttons.addWidget(self.save_doc_btn)

        self.accept_doc_btn = QPushButton("✅ Accept Document")
        self.accept_doc_btn.clicked.connect(lambda: self._review_document("APPROVED"))
        doc_buttons.addWidget(self.accept_doc_btn)

        self.reject_doc_btn = QPushButton("❌ Reject Document")
        self.reject_doc_btn.clicked.connect(lambda: self._review_document("REJECTED"))
        doc_buttons.addWidget(self.reject_doc_btn)
        layout.addLayout(doc_buttons)

        audit_header = QLabel("📜 Authorization Log")
        audit_header.setFont(doc_font)
        layout.addWidget(audit_header)

        self.audit_table = QTableWidget()
        self.audit_table.setColumnCount(1)
        self.audit_table.setHorizontalHeaderLabels(["Activity"])
        self.audit_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.audit_table.setMaximumHeight(160)
        self.audit_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.audit_table)

        self.setLayout(layout)

    # ------------------------------------------------------------- loading
    def refresh(self) -> None:
        """Reload pending requests, documents and the audit trail."""
        self._load_requests()
        self._load_documents()
        self._load_audit()

    def _load_requests(self) -> None:
        where = "r.status = 'PENDING'"
        params: list = []
        if self.employee_id:
            where += " AND r.employee_id = %s"
            params.append(self.employee_id)

        rows = []
        try:
            with DatabaseContext(self.db) as cur:
                cur.execute(
                    f"""
                    SELECT r.request_id, r.employee_id, r.field_key, r.field_label,
                           r.old_value, r.new_value, r.submitted_at,
                           r.submitted_by_username,
                           COALESCE(e.first_name || ' ' || e.last_name, 'Employee '
                               || r.employee_id::text) AS driver_name
                    FROM employee_change_requests r
                    LEFT JOIN employees e ON e.employee_id = r.employee_id
                    WHERE {where}
                    ORDER BY r.submitted_at DESC, r.request_id DESC
                    """,
                    params,
                )
                rows = cur.fetchall() or []
        except Exception as exc:
            logger.exception("Failed to load pending change requests")
            self.summary_label.setText(f"⚠️ Could not load pending changes: {exc}")
            return

        self._requests = rows
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            (
                _request_id,
                _employee_id,
                _field_key,
                field_label,
                old_value,
                new_value,
                submitted_at,
                submitted_by,
                driver_name,
            ) = row

            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            )
            checkbox_item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row_index, COL_SELECT, checkbox_item)

            driver_text = driver_name or ""
            if submitted_by:
                driver_text = f"{driver_text} ({submitted_by})"
            self.table.setItem(row_index, COL_DRIVER, QTableWidgetItem(driver_text))
            self.table.setItem(
                row_index, COL_FIELD, QTableWidgetItem(field_label or "")
            )

            current_item = QTableWidgetItem(old_value or "(blank)")
            current_item.setForeground(QBrush(QColor("#6b7280")))
            self.table.setItem(row_index, COL_CURRENT, current_item)

            requested_item = QTableWidgetItem(new_value or "(cleared)")
            requested_font = QFont()
            requested_font.setBold(True)
            requested_item.setFont(requested_font)
            requested_item.setForeground(QBrush(QColor("#b45309")))
            self.table.setItem(row_index, COL_REQUESTED, requested_item)

            submitted_text = (
                submitted_at.strftime("%Y-%m-%d %H:%M") if submitted_at else ""
            )
            self.table.setItem(
                row_index, COL_SUBMITTED, QTableWidgetItem(submitted_text)
            )

        scope = "this driver" if self.employee_id else "all drivers"
        if rows:
            self.summary_label.setText(
                f"{len(rows)} change(s) submitted for {scope} are waiting for "
                "authorization. Tick the rows you accept, then choose Authorize "
                "Selected — or use Authorize All to accept every change."
            )
        else:
            self.summary_label.setText(
                f"✅ No record changes are waiting for authorization for {scope}."
            )
        self._update_button_state()

    def _load_documents(self) -> None:
        where = "d.status = 'PENDING'"
        params: list = []
        if self.employee_id:
            where += " AND d.employee_id = %s"
            params.append(self.employee_id)

        rows = []
        try:
            with DatabaseContext(self.db) as cur:
                cur.execute(
                    f"""
                    SELECT d.upload_id, d.employee_id, d.document_type,
                           d.document_name, d.file_size, d.expiry_date,
                           d.uploaded_at,
                           COALESCE(e.first_name || ' ' || e.last_name, 'Employee '
                               || d.employee_id::text) AS driver_name
                    FROM employee_document_uploads d
                    LEFT JOIN employees e ON e.employee_id = d.employee_id
                    WHERE {where}
                    ORDER BY d.uploaded_at DESC
                    """,
                    params,
                )
                rows = cur.fetchall() or []
        except Exception:
            logger.exception("Failed to load pending document uploads")
            return

        self._documents = rows
        self.doc_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            (
                _upload_id,
                _employee_id,
                document_type,
                document_name,
                file_size,
                expiry_date,
                uploaded_at,
                driver_name,
            ) = row
            size_kb = f"{(file_size or 0) / 1024:.0f} KB"
            values = [
                driver_name or "",
                document_type or "",
                document_name or "",
                size_kb,
                expiry_date.isoformat() if expiry_date else "",
                uploaded_at.strftime("%Y-%m-%d %H:%M") if uploaded_at else "",
            ]
            for column, value in enumerate(values):
                self.doc_table.setItem(row_index, column, QTableWidgetItem(value))

    def _load_audit(self) -> None:
        where = "1=1"
        params: list = []
        if self.employee_id:
            where = "a.employee_id = %s"
            params.append(self.employee_id)

        rows = []
        try:
            with DatabaseContext(self.db) as cur:
                cur.execute(
                    f"""
                    SELECT a.field_label, a.field_key, a.old_value, a.new_value,
                           a.action, a.submitted_by_username,
                           a.reviewed_by_username, a.reviewed_at, a.note
                    FROM employee_change_audit a
                    WHERE {where}
                    ORDER BY a.reviewed_at DESC
                    LIMIT 200
                    """,
                    params,
                )
                rows = cur.fetchall() or []
        except Exception:
            logger.exception("Failed to load change audit log")
            return

        self.audit_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            (
                field_label,
                field_key,
                old_value,
                new_value,
                action,
                submitted_by,
                reviewed_by,
                reviewed_at,
                note,
            ) = row
            when = reviewed_at.strftime("%Y-%m-%d %H:%M") if reviewed_at else ""
            verb = "authorized by" if action == "APPROVED" else "rejected by"
            text = (
                f"{when} — {submitted_by or 'driver'} changed "
                f"{field_label or field_key} from '{old_value or '(blank)'}' "
                f"to '{new_value or '(cleared)'}' — {verb} {reviewed_by or 'admin'}"
            )
            if note:
                text = f"{text} ({note})"
            item = QTableWidgetItem(text)
            if action != "APPROVED":
                item.setForeground(QBrush(QColor("#b91c1c")))
            self.audit_table.setItem(row_index, 0, item)

    # ------------------------------------------------------------- helpers
    def _update_button_state(self) -> None:
        has_rows = bool(self._requests)
        for button in (
            self.approve_selected_btn,
            self.approve_all_btn,
            self.reject_selected_btn,
            self.select_all_btn,
            self.select_none_btn,
        ):
            button.setEnabled(has_rows)

    def _set_all_checked(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row_index in range(self.table.rowCount()):
            item = self.table.item(row_index, COL_SELECT)
            if item is not None:
                item.setCheckState(state)

    def _checked_requests(self) -> list:
        selected = []
        for row_index, request in enumerate(self._requests):
            item = self.table.item(row_index, COL_SELECT)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                selected.append(request)
        return selected

    @staticmethod
    def _describe(request) -> str:
        (
            _request_id,
            _employee_id,
            field_key,
            field_label,
            old_value,
            new_value,
            _submitted_at,
            submitted_by,
            driver_name,
        ) = request
        return (
            f"{submitted_by or driver_name} changed "
            f"{field_label or field_key} from '{old_value or '(blank)'}' "
            f"to '{new_value or '(cleared)'}'"
        )

    # ------------------------------------------------------------- actions
    def approve_all(self) -> None:
        if not self._requests:
            return
        self._process(list(self._requests), approve=True)

    def approve_selected(self) -> None:
        selected = self._checked_requests()
        if not selected:
            QMessageBox.information(
                self,
                "Nothing Selected",
                "Tick the Apply box on the changes you want to authorize.",
            )
            return
        self._process(selected, approve=True)

    def reject_selected(self) -> None:
        selected = self._checked_requests()
        if not selected:
            QMessageBox.information(
                self,
                "Nothing Selected",
                "Tick the Apply box on the changes you want to reject.",
            )
            return
        reason, ok = QInputDialog.getText(
            self,
            "Reject Changes",
            "Reason shown to the driver (optional):",
        )
        if not ok:
            return
        self._process(selected, approve=False, note=reason.strip() or None)

    def _process(self, requests, approve: bool, note=None) -> None:
        action_word = "authorize" if approve else "reject"
        lines = "\n".join(f"  • {self._describe(r)}" for r in requests[:15])
        if len(requests) > 15:
            lines += f"\n  • ...and {len(requests) - 15} more"

        confirm = QMessageBox.question(
            self,
            f"Confirm {action_word.title()}",
            f"{action_word.title()} {len(requests)} change(s)?\n\n{lines}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        applied = 0
        skipped = []
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                for request in requests:
                    (
                        request_id,
                        employee_id,
                        field_key,
                        field_label,
                        old_value,
                        new_value,
                        _submitted_at,
                        submitted_by,
                        _driver_name,
                    ) = request

                    if approve:
                        if field_key not in APPROVABLE_FIELDS:
                            skipped.append(field_label or field_key)
                            continue
                        stored_value = new_value or None
                        if field_key in DATE_FIELDS:
                            cur.execute(
                                f"UPDATE employees SET {field_key} = %s::date "  # nosec
                                "WHERE employee_id = %s",
                                (stored_value, employee_id),
                            )
                        else:
                            cur.execute(
                                f"UPDATE employees SET {field_key} = %s "  # nosec
                                "WHERE employee_id = %s",
                                (stored_value, employee_id),
                            )

                    cur.execute(
                        """
                        UPDATE employee_change_requests
                        SET status = %s,
                            reviewed_by_username = %s,
                            reviewed_at = NOW(),
                            review_notes = %s
                        WHERE request_id = %s AND status = 'PENDING'
                        """,
                        (
                            "APPROVED" if approve else "REJECTED",
                            self._reviewer,
                            note,
                            request_id,
                        ),
                    )
                    cur.execute(
                        """
                        INSERT INTO employee_change_audit (
                            request_id, employee_id, field_key, field_label,
                            old_value, new_value, action,
                            submitted_by_username, reviewed_by_username, note
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            request_id,
                            employee_id,
                            field_key,
                            field_label,
                            old_value,
                            new_value,
                            "APPROVED" if approve else "REJECTED",
                            submitted_by,
                            self._reviewer,
                            note,
                        ),
                    )
                    applied += 1
        except Exception as exc:
            logger.exception("Failed to process change requests")
            QMessageBox.critical(
                self,
                "Authorization Failed",
                f"The changes could not be {action_word}d:\n\n{exc}",
            )
            return

        message = f"{applied} change(s) {action_word}d by {self._reviewer}."
        if skipped:
            message += (
                "\n\nSkipped (not permitted from the driver portal): "
                + ", ".join(skipped)
            )
        QMessageBox.information(self, "Done", message)
        self.refresh()
        self.changes_applied.emit()

    # ----------------------------------------------------------- documents
    def _selected_document(self):
        row_index = self.doc_table.currentRow()
        if row_index < 0 or row_index >= len(self._documents):
            QMessageBox.information(
                self, "No Document", "Select a document row first."
            )
            return None
        return self._documents[row_index]

    def save_selected_document(self) -> None:
        document = self._selected_document()
        if not document:
            return
        upload_id, _employee_id, _doc_type, document_name = document[:4]

        target, _ = QFileDialog.getSaveFileName(
            self, "Save Document", document_name or f"document_{upload_id}"
        )
        if not target:
            return
        try:
            with DatabaseContext(self.db) as cur:
                cur.execute(
                    "SELECT file_data FROM employee_document_uploads "
                    "WHERE upload_id = %s",
                    (upload_id,),
                )
                row = cur.fetchone()
            if not row or row[0] is None:
                QMessageBox.warning(self, "Not Found", "Document data is missing.")
                return
            with open(target, "wb") as handle:
                handle.write(bytes(row[0]))
        except Exception as exc:
            logger.exception("Failed to save document")
            QMessageBox.critical(self, "Save Failed", str(exc))
            return
        QMessageBox.information(self, "Saved", f"Document saved to:\n{target}")

    def _review_document(self, status: str) -> None:
        document = self._selected_document()
        if not document:
            return
        upload_id = document[0]
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    UPDATE employee_document_uploads
                    SET status = %s,
                        reviewed_by_username = %s,
                        reviewed_at = NOW()
                    WHERE upload_id = %s AND status = 'PENDING'
                    """,
                    (status, self._reviewer, upload_id),
                )
        except Exception as exc:
            logger.exception("Failed to review document")
            QMessageBox.critical(self, "Review Failed", str(exc))
            return
        self.refresh()
        self.changes_applied.emit()
