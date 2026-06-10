"""
Accountant Year Notes Widget
Per-year notes for the accountant covering revenue, expenses, payroll, GST,
reimbursements, vehicles, and general observations.
Covers tax years 2012–2025.
"""

import logging

import psycopg2
from db_error_handling import DatabaseContext
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# Sections shown per year — field name -> display label
SECTIONS = [
    ("general_notes",       "📋 General / Overview"),
    ("revenue_notes",       "💰 Revenue & Income"),
    ("expense_notes",       "🧾 Expenses & Receipts"),
    ("payroll_notes",       "👷 Payroll & T4s"),
    ("gst_notes",           "🏛️ GST / CRA Remittances"),
    ("reimbursement_notes", "🔄 Related Party Reimbursements"),
    ("vehicles_notes",      "🚗 Vehicles & Asset Changes"),
    ("other_notes",         "📎 Other Notes"),
]


class _SectionEditor(QWidget):
    """One collapsible section with a label and a text editor."""

    def __init__(self, field: str, label: str, parent=None) -> None:
        super().__init__(parent)
        self.field = field
        self._expanded = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(2)

        # Header row
        header = QHBoxLayout()
        self.toggle_btn = QPushButton("▼  " + label)
        self.toggle_btn.setFlat(True)
        font = QFont()
        font.setBold(True)
        self.toggle_btn.setFont(font)
        self.toggle_btn.setStyleSheet(
            "text-align:left; padding:4px 6px; "
            "background:#f0f4ff; border:1px solid #c8d0e8;"
            " border-radius:4px;"
        )
        self.toggle_btn.clicked.connect(self._toggle)
        header.addWidget(self.toggle_btn)
        layout.addLayout(header)

        # Text editor
        self.editor = QTextEdit()
        self.editor.setPlaceholderText(
            f"Enter notes for {label.split(' ', 1)[-1]}…"
        )
        self.editor.setMinimumHeight(90)
        self.editor.setMaximumHeight(240)
        self.editor.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        layout.addWidget(self.editor)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#d0d8e8;")
        layout.addWidget(line)

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self.editor.setVisible(self._expanded)
        label = self.toggle_btn.text()[3:]
        self.toggle_btn.setText(("▼  " if self._expanded else "▶  ") + label)

    def get_text(self) -> str:
        return self.editor.toPlainText().strip() or None

    def set_text(self, text: str) -> None:
        self.editor.setPlainText(text or "")


class AccountantNotesWidget(QWidget):
    """Browse and edit per-year accountant/auditor notes."""

    def __init__(self, conn: psycopg2.extensions.connection, parent=None) -> None:
        super().__init__(parent)
        self.conn = conn
        self._current_year = None
        self._sections: dict[str, _SectionEditor] = {}
        self._dirty = False
        self._build_ui()
        self._load_year(2025)

    # ── UI Construction ─────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)

        # ── Left: year list ──────────────────────────────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(6, 6, 6, 6)

        title = QLabel("Tax Year")
        title.setFont(QFont("", 11, QFont.Weight.Bold))
        left_layout.addWidget(title)

        self.year_list = QListWidget()
        self.year_list.setMaximumWidth(110)
        for yr in range(2025, 2011, -1):
            item = QListWidgetItem(str(yr))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.year_list.addItem(item)
        self.year_list.currentItemChanged.connect(self._on_year_changed)
        left_layout.addWidget(self.year_list)
        splitter.addWidget(left)

        # ── Right: notes editor ──────────────────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 6, 8, 6)

        # Toolbar
        toolbar = QHBoxLayout()
        self.year_label = QLabel("Year: —")
        self.year_label.setFont(QFont("", 13, QFont.Weight.Bold))
        toolbar.addWidget(self.year_label)
        toolbar.addStretch()

        self.last_updated_label = QLabel("")
        self.last_updated_label.setStyleSheet("color:#888; font-size:11px;")
        toolbar.addWidget(self.last_updated_label)

        save_btn = QPushButton("💾  Save Notes")
        save_btn.setStyleSheet(
            "background:#2e7d32; color:white; font-weight:bold; "
            "padding:5px 16px; border-radius:4px;"
        )
        save_btn.clicked.connect(self._save)
        toolbar.addWidget(save_btn)

        right_layout.addLayout(toolbar)

        # Scroll area containing all section editors
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_contents = QWidget()
        self.sections_layout = QVBoxLayout(scroll_contents)
        self.sections_layout.setContentsMargins(0, 0, 8, 0)

        for field, label in SECTIONS:
            sec = _SectionEditor(field, label)
            sec.editor.textChanged.connect(self._mark_dirty)
            self._sections[field] = sec
            self.sections_layout.addWidget(sec)

        self.sections_layout.addStretch()
        scroll.setWidget(scroll_contents)
        right_layout.addWidget(scroll)

        # Dirty indicator
        self.dirty_label = QLabel("")
        self.dirty_label.setStyleSheet("color:#c0392b; font-size:11px;")
        right_layout.addWidget(self.dirty_label)

        splitter.addWidget(right)
        splitter.setSizes([110, 900])
        root.addWidget(splitter)

    # ── Data Loading ────────────────────────────────────────────────────────

    def _on_year_changed(self, current, previous) -> None:
        if current is None:
            return
        yr = int(current.text())
        if self._dirty and self._current_year is not None:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                (
                    f"You have unsaved changes for {self._current_year}. "
                    "Save before switching?"
                ),
                (
                    QMessageBox.StandardButton.Save
                    | QMessageBox.StandardButton.Discard
                ) |
                QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                self._save()
            elif reply == QMessageBox.StandardButton.Cancel:
                # Revert selection
                for i in range(self.year_list.count()):
                    if (
                        self.year_list.item(i).text()
                        == str(self._current_year)
                    ):
                        self.year_list.blockSignals(True)
                        self.year_list.setCurrentRow(i)
                        self.year_list.blockSignals(False)
                        return
        self._load_year(yr)

    def _load_year(self, year: int) -> None:
        try:
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                fields = ", ".join(f for f, _ in SECTIONS)
                cur.execute(
                    (
                        f"SELECT {fields}, last_updated, updated_by "
                        "FROM accountant_year_notes WHERE year = %s"
                    ),
                    (year,),
                )
                row = cur.fetchone()

            self._current_year = year
            self.year_label.setText(f"Tax Year {year}")

            if row:
                for i, (field, _) in enumerate(SECTIONS):
                    self._sections[field].set_text(row[i] or "")
                ts = row[len(SECTIONS)]
                by = row[len(SECTIONS) + 1]
                ts_str = str(ts)[:16] if ts else "never"
                self.last_updated_label.setText(
                    f"Last saved: {ts_str}  by {by or '—'}"
                )
            else:
                for field, _ in SECTIONS:
                    self._sections[field].set_text("")
                self.last_updated_label.setText("No data yet")

            # Select matching row in list
            for i in range(self.year_list.count()):
                if self.year_list.item(i).text() == str(year):
                    self.year_list.blockSignals(True)
                    self.year_list.setCurrentRow(i)
                    self.year_list.blockSignals(False)
                    break

            self._dirty = False
            self.dirty_label.setText("")

        except Exception as e:
            logger.error(f"Failed to load year notes: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to load notes:\n{e}"
            )

    # ── Saving ──────────────────────────────────────────────────────────────

    def _save(self) -> None:
        if self._current_year is None:
            return
        try:
            values = {
                field: self._sections[field].get_text()
                for field, _ in SECTIONS
            }
            set_clause = ", ".join(f"{f} = %s" for f in values)
            params = list(values.values()) + [self._current_year]

            with DatabaseContext(self.conn, auto_commit=True) as cur:
                cur.execute(
                    (
                        "UPDATE accountant_year_notes "
                        f"SET {set_clause}, last_updated = NOW(), "
                        "updated_by = 'desktop' "
                        "WHERE year = %s"
                    ),
                    params,
                )
                if cur.rowcount == 0:
                    # Row didn't exist — insert it
                    cols = ", ".join(values.keys())
                    placeholders = ", ".join(["%s"] * len(values))
                    cur.execute(
                        (
                            "INSERT INTO accountant_year_notes "
                            f"(year, {cols}) "
                            f"VALUES (%s, {placeholders})"
                        ),
                        [self._current_year]
                        + list(values.values()),
                    )

            self._dirty = False
            self.dirty_label.setText("")
            self.last_updated_label.setText(
                "Last saved: just now  by desktop"
            )

        except Exception as e:
            logger.error(
                f"Failed to save year notes: {e}"
            )
            QMessageBox.critical(
                self, "Error", f"Failed to save notes:\n{e}"
            )

    def _mark_dirty(self) -> None:
        if not self._dirty:
            self._dirty = True
            self.dirty_label.setText("● Unsaved changes")
