"""Bank statement import dialog.

Verifies the statement folders exist (creating them when the admin agrees),
then reports which monthly statements have been downloaded and which are still
missing for each registered account.
"""

from __future__ import annotations

import logging
from pathlib import Path

import bank_statement_folders as bsf
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

logger = logging.getLogger(__name__)

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class BankStatementImportDialog(QDialog):
    """Verify statement folders and show download status per account."""

    def __init__(self, conn, parent=None) -> None:
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Bank Statement Import")
        self.resize(900, 620)
        self._build_ui()
        self._verify_root(prompt=True)

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Download each bank statement one month at a time and save it into "
            "the matching bank folder below, named "
            "<b>&lt;last4&gt;&lt;mon&gt;&lt;year&gt;</b> "
            "(for example <b>1615jan2026.xls</b>)."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Folder:"))
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        path_row.addWidget(self.path_edit, 1)

        browse_btn = QPushButton("Change...")
        browse_btn.clicked.connect(self._choose_root)
        path_row.addWidget(browse_btn)

        open_btn = QPushButton("📂 Open")
        open_btn.clicked.connect(self._open_root)
        path_row.addWidget(open_btn)
        layout.addLayout(path_row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Account", "Downloaded", "Missing", "Details"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(self.tree, 1)

        buttons = QHBoxLayout()
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh)
        buttons.addWidget(refresh_btn)

        create_btn = QPushButton("📁 Create Missing Folders")
        create_btn.clicked.connect(self._create_folders)
        buttons.addWidget(create_btn)

        buttons.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

    # --------------------------------------------------------------- logic

    def _verify_root(self, prompt: bool = False) -> None:
        """Check the configured root, offering to create or relocate it."""
        root = bsf.get_statements_root()
        self.path_edit.setText(str(root))

        if root.exists():
            self._create_folders(silent=True)
            self.refresh()
            return

        if not prompt:
            self.refresh()
            return

        choice = QMessageBox.question(
            self,
            "Statement Folder Not Found",
            f"The bank statement folder does not exist:\n\n{root}\n\n"
            "Create it now?\n\n"
            "Choose 'No' to pick a different location.",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if choice == QMessageBox.StandardButton.Yes:
            self._create_folders()
        elif choice == QMessageBox.StandardButton.No:
            self._choose_root()
        else:
            self.refresh()

    def _choose_root(self) -> None:
        current = self.path_edit.text() or str(bsf.get_statements_root())
        selected = QFileDialog.getExistingDirectory(
            self, "Select Bank Statement Folder", current
        )
        if not selected:
            return
        bsf.set_statements_root(selected)
        self.path_edit.setText(selected)
        self._create_folders(silent=True)
        self.refresh()

    def _open_root(self) -> None:
        root = Path(self.path_edit.text())
        if not root.exists():
            QMessageBox.information(
                self, "Not Found", f"Folder does not exist yet:\n{root}"
            )
            return
        import os

        os.startfile(str(root))

    def _create_folders(self, silent: bool = False) -> None:
        try:
            base, _accounts, created = bsf.ensure_folders(self.conn)
        except Exception as exc:  # pragma: no cover - filesystem/permission
            logger.exception("Failed to create statement folders")
            QMessageBox.critical(
                self, "Error", f"Could not create statement folders:\n{exc}"
            )
            return

        self.path_edit.setText(str(base))
        if not silent:
            if created:
                QMessageBox.information(
                    self,
                    "Folders Ready",
                    "Created:\n\n" + "\n".join(str(p) for p in created),
                )
            else:
                QMessageBox.information(
                    self, "Folders Ready", "All bank folders already exist."
                )
        self.refresh()

    def refresh(self) -> None:
        self.tree.clear()
        root = Path(self.path_edit.text()) if self.path_edit.text() else None

        if root is None or not root.exists():
            self.status_label.setText(
                "⚠️ Statement folder does not exist yet. "
                "Use 'Create Missing Folders' or 'Change...' to pick a location."
            )
            return

        try:
            _base, accounts, found, missing, unknown = bsf.missing_months(self.conn)
        except Exception as exc:  # pragma: no cover - DB failure
            logger.exception("Failed to scan statement folders")
            self.status_label.setText(f"🔴 Could not scan statements: {exc}")
            return

        total_found = sum(len(v) for v in found.values())
        total_missing = sum(len(v) for v in missing.values())

        current_slug = None
        parent_item = None
        for account in accounts:
            slug = bsf.institution_slug(account.institution)
            if slug != current_slug:
                parent_item = QTreeWidgetItem(self.tree, [slug, "", "", ""])
                parent_item.setExpanded(True)
                current_slug = slug

            downloaded = found.get(account.bank_id, [])
            outstanding = missing.get(account.bank_id, [])
            example = bsf.statement_name(account.account_number, 2026, 1, ".xls")

            item = QTreeWidgetItem(
                parent_item,
                [
                    f"{account.last4} — {account.account_name}",
                    str(len(downloaded)),
                    str(len(outstanding)),
                    f"e.g. {example}",
                ],
            )
            if outstanding:
                item.setForeground(2, Qt.GlobalColor.red)

            for year, month, path, _size in downloaded:
                QTreeWidgetItem(
                    item,
                    [f"✅ {MONTH_NAMES[month - 1]} {year}", "", "", path.name],
                )
            for year, month in outstanding:
                needed = bsf.statement_name(account.account_number, year, month, ".xls")
                child = QTreeWidgetItem(
                    item, [f"⬜ {MONTH_NAMES[month - 1]} {year}", "", "", needed]
                )
                child.setForeground(0, Qt.GlobalColor.darkYellow)

        if unknown:
            node = QTreeWidgetItem(
                self.tree, ["⚠️ Unrecognized files", "", str(len(unknown)), ""]
            )
            node.setExpanded(True)
            for path in unknown:
                QTreeWidgetItem(node, [path.name, "", "", str(path.parent)])

        summary = (
            f"{total_found} statement(s) found, {total_missing} still to download."
        )
        if unknown:
            summary += (
                f"  ⚠️ {len(unknown)} file(s) did not match any account — "
                "check the name matches <last4><mon><year>."
            )
        self.status_label.setText(summary)
