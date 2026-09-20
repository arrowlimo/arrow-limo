"""Centralized CRA audit management dashboard.

Aggregates payroll remittance, PD7A, receipt/banking, and tax-variance audit
findings into one review workflow with flags, notes, and printable outputs.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from db_error_handling import DatabaseContext
from print_export_helper import PrintExportHelper
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor, QTextCursor, QTextDocument
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
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


class AuditManagementWidget(QWidget):
    """Unified audit findings and resolution manager."""

    def __init__(self, db, auth_user=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.auth_user = auth_user or {}
        self._all_rows = []
        self._rows = []
        self._build_ui()
        self._ensure_tables()
        self.year_spin.setValue(QDate.currentDate().year())
        self.refresh_findings()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>🧪 Audit (CRA / Payroll / Receipts / Banking)</h2>"))

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Year:"))
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2011, 2035)
        controls.addWidget(self.year_spin)

        refresh_btn = QPushButton("Refresh Findings")
        refresh_btn.clicked.connect(self.refresh_findings)
        controls.addWidget(refresh_btn)

        controls.addWidget(QLabel("Area:"))
        self.area_filter = QComboBox()
        self.area_filter.addItem("all")
        self.area_filter.currentTextChanged.connect(self._apply_filters)
        controls.addWidget(self.area_filter)

        controls.addWidget(QLabel("Severity:"))
        self.severity_filter = QComboBox()
        self.severity_filter.addItems(["all", "high", "medium", "low", "info"])
        self.severity_filter.currentTextChanged.connect(self._apply_filters)
        controls.addWidget(self.severity_filter)

        controls.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["all", "open", "investigating", "resolved", "accepted_risk"])
        self.status_filter.currentTextChanged.connect(self._apply_filters)
        controls.addWidget(self.status_filter)

        self.open_only_checkbox = QCheckBox("Open Only")
        self.open_only_checkbox.toggled.connect(self._apply_filters)
        controls.addWidget(self.open_only_checkbox)

        print_btn = QPushButton("Print Findings")
        print_btn.clicked.connect(self.print_findings)
        controls.addWidget(print_btn)

        filing_pack_btn = QPushButton("Audit Filing Pack")
        filing_pack_btn.clicked.connect(self.print_audit_filing_pack)
        controls.addWidget(filing_pack_btn)

        controls.addStretch(1)
        layout.addLayout(controls)

        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(
            [
                "Area",
                "Severity",
                "Category",
                "Ref",
                "Period",
                "Amount",
                "Warning",
                "Status",
                "Owner",
                "Note",
            ]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        layout.addWidget(self.table)

        edit = QFormLayout()
        self.status_combo = QComboBox()
        self.status_combo.addItems(["open", "investigating", "resolved", "accepted_risk"])
        edit.addRow("Set Status", self.status_combo)

        self.note_edit = QTextEdit()
        self.note_edit.setMaximumHeight(80)
        edit.addRow("Audit Note", self.note_edit)

        row = QHBoxLayout()
        save_btn = QPushButton("Save Resolution")
        save_btn.clicked.connect(self.save_resolution)
        row.addWidget(save_btn)
        clear_btn = QPushButton("Clear Resolution")
        clear_btn.clicked.connect(self.clear_resolution)
        row.addWidget(clear_btn)
        row.addStretch(1)
        edit.addRow(row)

        layout.addLayout(edit)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status_label.setStyleSheet(
            "color: #dc2626; font-weight: bold;" if error else "color: #2563eb; font-weight: bold;"
        )
        self.status_label.setText(text)

    def _ensure_tables(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_finding_overrides (
                        finding_key TEXT PRIMARY KEY,
                        status TEXT NOT NULL DEFAULT 'open',
                        note TEXT,
                        owner_name TEXT,
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
        except Exception as exc:
            logger.warning("Could not ensure audit override table: %s", exc)

    def _safe_float(self, value) -> float:
        try:
            return float(value or 0)
        except Exception:
            return 0.0

    def _get_columns(self, table_name: str) -> set[str]:
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

    def _load_overrides(self) -> dict[str, dict]:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT finding_key, status, note, owner_name
                    FROM audit_finding_overrides
                    """
                )
                rows = cur.fetchall()
            return {
                str(r[0]): {
                    "status": r[1] or "open",
                    "note": r[2] or "",
                    "owner": r[3] or "",
                }
                for r in rows
            }
        except Exception as exc:
            logger.warning("Failed loading audit overrides: %s", exc)
            return {}

    def _severity_from_amount(self, amount: float) -> str:
        abs_amt = abs(self._safe_float(amount))
        if abs_amt >= 500:
            return "high"
        if abs_amt >= 50:
            return "medium"
        return "low"

    def _scan_payroll_remittance_findings(self, year: int) -> list[dict]:
        out = []
        cols = self._get_columns("payroll_remittances")
        if not cols:
            return out
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT remittance_month,
                           COALESCE(calculated_total_remittance, 0),
                           COALESCE(payment_amount, 0),
                           COALESCE(variance, COALESCE(calculated_total_remittance,0)-COALESCE(payment_amount,0)),
                           COALESCE(status, 'pending'),
                           due_date,
                           payment_date,
                           COALESCE(is_late, FALSE),
                           COALESCE(payment_reference, '')
                    FROM payroll_remittances
                    WHERE fiscal_year = %s
                    ORDER BY remittance_month
                    """,
                    (year,),
                )
                rows = cur.fetchall()

            for m, due, paid, var, status, due_date, pay_date, is_late, ref in rows:
                variance = self._safe_float(var)
                warn_parts = []
                if abs(variance) > 0.009:
                    warn_parts.append("Variance between due and paid")
                if str(status).lower() in {"pending", "late"}:
                    warn_parts.append(f"Status={status}")
                if bool(is_late):
                    warn_parts.append("Late payment")
                if not warn_parts:
                    continue
                out.append(
                    {
                        "key": f"payroll_remit:{year}:{int(m)}",
                        "area": "Payroll Tax",
                        "severity": self._severity_from_amount(variance),
                        "category": "CRA/WCB Month",
                        "ref": ref or f"M{int(m):02d}",
                        "period": f"{year}-{int(m):02d}",
                        "amount": variance,
                        "warning": "; ".join(warn_parts),
                    }
                )
        except Exception as exc:
            logger.error("Payroll remittance scan failed: %s", exc)
        return out

    def _scan_pd7a_findings(self, year: int) -> list[dict]:
        out = []
        cols = self._get_columns("cra_pd7a_returns")
        if not cols:
            return out
        today = date.today()
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT reporting_month,
                           COALESCE(total_remittance_due, 0),
                           COALESCE(variance_from_payment, 0),
                           COALESCE(is_submitted, FALSE),
                           due_date
                    FROM cra_pd7a_returns
                    WHERE reporting_year = %s
                    ORDER BY reporting_month
                    """,
                    (year,),
                )
                rows = cur.fetchall()

            for m, total_due, variance, submitted, due_date in rows:
                warn_parts = []
                var_f = self._safe_float(variance)
                if abs(var_f) > 0.009:
                    warn_parts.append("PD7A variance")
                if not bool(submitted) and due_date and due_date < today:
                    warn_parts.append("PD7A overdue not submitted")
                if not warn_parts:
                    continue
                out.append(
                    {
                        "key": f"pd7a:{year}:{int(m)}",
                        "area": "Payroll Tax",
                        "severity": self._severity_from_amount(var_f or total_due),
                        "category": "PD7A",
                        "ref": f"PD7A-{int(m):02d}",
                        "period": f"{year}-{int(m):02d}",
                        "amount": var_f,
                        "warning": "; ".join(warn_parts),
                    }
                )
        except Exception as exc:
            logger.error("PD7A scan failed: %s", exc)
        return out

    def _scan_receipt_banking_findings(self, year: int) -> list[dict]:
        out = []
        rcols = self._get_columns("receipts")
        if not rcols:
            return out
        if "receipt_date" not in rcols:
            return out

        bank_col = "banking_transaction_id" if "banking_transaction_id" in rcols else None
        paper_col = "is_paper_verified" if "is_paper_verified" in rcols else None
        date_expr = "EXTRACT(YEAR FROM receipt_date) = %s"

        where_bits = [date_expr]
        if bank_col and paper_col:
            where_bits.append("(banking_transaction_id IS NULL AND COALESCE(is_paper_verified, FALSE) = FALSE)")
        elif bank_col:
            where_bits.append("banking_transaction_id IS NULL")

        if len(where_bits) <= 1:
            return out

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    f"""
                    SELECT receipt_id,
                           COALESCE(vendor_name, ''),
                           COALESCE(gross_amount, 0),
                           receipt_date
                    FROM receipts
                    WHERE {' AND '.join(where_bits)}
                    ORDER BY receipt_date DESC
                    LIMIT 200
                    """,
                    (year,),
                )
                rows = cur.fetchall()
            for receipt_id, vendor, gross, rdate in rows:
                amt = self._safe_float(gross)
                out.append(
                    {
                        "key": f"receipt_unmatched:{int(receipt_id)}",
                        "area": "Receipts/Banking",
                        "severity": self._severity_from_amount(amt),
                        "category": "Receipt Match",
                        "ref": f"R#{int(receipt_id)}",
                        "period": str(rdate),
                        "amount": amt,
                        "warning": f"Unmatched receipt for vendor {vendor or '-'}",
                    }
                )
        except Exception as exc:
            logger.error("Receipt banking scan failed: %s", exc)
        return out

    def _scan_tax_variance_findings(self, year: int) -> list[dict]:
        out = []
        tv_cols = self._get_columns("tax_variances")
        tr_cols = self._get_columns("tax_returns")
        tp_cols = self._get_columns("tax_periods")
        if not tv_cols or not tr_cols or not tp_cols:
            return out

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT COALESCE(tv.severity, 'info'),
                           COALESCE(tr.form_type, ''),
                           COALESCE(tv.field, ''),
                           COALESCE(tv.actual, 0),
                           COALESCE(tv.expected, 0),
                           COALESCE(tv.message, ''),
                           COALESCE(tp.label, '')
                    FROM tax_variances tv
                    JOIN tax_returns tr ON tr.id = tv.tax_return_id
                    JOIN tax_periods tp ON tp.id = tr.period_id
                    WHERE tp.label = %s
                    ORDER BY tv.id DESC
                    LIMIT 200
                    """,
                    (str(year),),
                )
                rows = cur.fetchall()
            for sev, form_type, field, actual, expected, message, label in rows:
                delta = self._safe_float(actual) - self._safe_float(expected)
                out.append(
                    {
                        "key": f"tax_variance:{year}:{form_type}:{field}:{abs(int(delta * 100))}",
                        "area": "Tax",
                        "severity": str(sev or "info").lower(),
                        "category": f"{form_type.upper()} variance",
                        "ref": field or "-",
                        "period": label or str(year),
                        "amount": delta,
                        "warning": message or "Tax variance requires review",
                    }
                )
        except Exception as exc:
            logger.error("Tax variance scan failed: %s", exc)
        return out

    def _scan_findings(self, year: int) -> list[dict]:
        findings = []
        findings.extend(self._scan_payroll_remittance_findings(year))
        findings.extend(self._scan_pd7a_findings(year))
        findings.extend(self._scan_receipt_banking_findings(year))
        findings.extend(self._scan_tax_variance_findings(year))
        return findings

    def _row_matches_filters(self, row: dict) -> bool:
        area_filter = self.area_filter.currentText().strip().lower()
        severity_filter = self.severity_filter.currentText().strip().lower()
        status_filter = self.status_filter.currentText().strip().lower()

        if area_filter != "all" and str(row.get("area", "")).strip().lower() != area_filter:
            return False
        if severity_filter != "all" and str(row.get("severity", "")).strip().lower() != severity_filter:
            return False
        if status_filter != "all" and str(row.get("status", "")).strip().lower() != status_filter:
            return False
        if self.open_only_checkbox.isChecked() and str(row.get("status", "")).strip().lower() != "open":
            return False
        return True

    def _severity_color(self, severity: str) -> QColor | None:
        sev = str(severity or "").lower().strip()
        if sev == "high":
            return QColor("#fee2e2")
        if sev == "medium":
            return QColor("#fef3c7")
        if sev == "low":
            return QColor("#dcfce7")
        return None

    def _status_color(self, status: str) -> QColor | None:
        st = str(status or "").lower().strip()
        if st == "resolved":
            return QColor("#dbeafe")
        if st == "accepted_risk":
            return QColor("#e9d5ff")
        return None

    def _render_table(self) -> None:
        self.table.setRowCount(len(self._rows))
        for r, row in enumerate(self._rows):
            row_items = []
            row_items.append(QTableWidgetItem(str(row["area"])))
            row_items.append(QTableWidgetItem(str(row["severity"])))
            row_items.append(QTableWidgetItem(str(row["category"])))
            ref_item = QTableWidgetItem(str(row["ref"]))
            ref_item.setData(Qt.ItemDataRole.UserRole, row["key"])
            row_items.append(ref_item)
            row_items.append(QTableWidgetItem(str(row["period"])))
            row_items.append(QTableWidgetItem(f"${self._safe_float(row['amount']):,.2f}"))
            row_items.append(QTableWidgetItem(str(row["warning"])))
            row_items.append(QTableWidgetItem(str(row["status"])))
            row_items.append(QTableWidgetItem(str(row["owner"])))
            row_items.append(QTableWidgetItem(str(row["note"])))

            color = self._severity_color(row.get("severity")) or self._status_color(row.get("status"))
            for col, item in enumerate(row_items):
                if color:
                    item.setBackground(color)
                self.table.setItem(r, col, item)

    def _apply_filters(self) -> None:
        self._rows = [row for row in self._all_rows if self._row_matches_filters(row)]
        self._render_table()
        self._set_status(f"Showing {len(self._rows)} of {len(self._all_rows)} findings after filters.")

    def refresh_findings(self) -> None:
        year = int(self.year_spin.value())
        findings = self._scan_findings(year)
        overrides = self._load_overrides()

        all_rows = []
        for finding in findings:
            ov = overrides.get(finding["key"], {})
            all_rows.append(
                {
                    **finding,
                    "status": ov.get("status", "open"),
                    "owner": ov.get("owner", ""),
                    "note": ov.get("note", ""),
                }
            )

        self._all_rows = all_rows
        area_values = sorted({str(r.get("area", "")).strip() for r in self._all_rows if r.get("area")})
        current_area = self.area_filter.currentText()
        self.area_filter.blockSignals(True)
        self.area_filter.clear()
        self.area_filter.addItem("all")
        self.area_filter.addItems(area_values)
        if current_area and self.area_filter.findText(current_area) >= 0:
            self.area_filter.setCurrentText(current_area)
        self.area_filter.blockSignals(False)

        self._apply_filters()

    def _build_summary_table(self, rows: list[dict]) -> QTableWidget:
        severity_counts = {}
        status_counts = {}
        area_counts = {}
        for row in rows:
            severity = str(row.get("severity", "unknown"))
            status = str(row.get("status", "open"))
            area = str(row.get("area", "Other"))
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            status_counts[status] = status_counts.get(status, 0) + 1
            area_counts[area] = area_counts.get(area, 0) + 1

        summary = QTableWidget()
        summary.setColumnCount(3)
        summary.setHorizontalHeaderLabels(["Group", "Key", "Count"])

        data_rows = []
        for key, value in sorted(severity_counts.items()):
            data_rows.append(("severity", key, str(value)))
        for key, value in sorted(status_counts.items()):
            data_rows.append(("status", key, str(value)))
        for key, value in sorted(area_counts.items()):
            data_rows.append(("area", key, str(value)))

        summary.setRowCount(len(data_rows))
        for idx, triple in enumerate(data_rows):
            summary.setItem(idx, 0, QTableWidgetItem(triple[0]))
            summary.setItem(idx, 1, QTableWidgetItem(triple[1]))
            summary.setItem(idx, 2, QTableWidgetItem(triple[2]))
        return summary

    def _count_query(self, query: str, params: tuple) -> int:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(query, params)
                row = cur.fetchone()
                return int(row[0] or 0) if row else 0
        except Exception:
            return 0

    def _build_source_coverage_table(self, year: int) -> QTableWidget:
        source_rows = []

        payroll_count = self._count_query(
            """
            SELECT COUNT(*)
            FROM payroll_remittances
            WHERE fiscal_year = %s
            """,
            (year,),
        )
        source_rows.append(("payroll_remittances", "monthly payroll remittance records", str(payroll_count)))

        pd7a_count = self._count_query(
            """
            SELECT COUNT(*)
            FROM cra_pd7a_returns
            WHERE reporting_year = %s
            """,
            (year,),
        )
        source_rows.append(("cra_pd7a_returns", "pd7a filing records", str(pd7a_count)))

        unmatched_receipts = self._count_query(
            """
            SELECT COUNT(*)
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = %s
              AND banking_transaction_id IS NULL
              AND COALESCE(is_paper_verified, FALSE) = FALSE
            """,
            (year,),
        )
        source_rows.append(("receipts", "unmatched receipt records", str(unmatched_receipts)))

        tax_variance_count = self._count_query(
            """
            SELECT COUNT(*)
            FROM tax_variances tv
            JOIN tax_returns tr ON tr.id = tv.tax_return_id
            JOIN tax_periods tp ON tp.id = tr.period_id
            WHERE tp.label = %s
            """,
            (str(year),),
        )
        source_rows.append(("tax_variances", "tax variance records", str(tax_variance_count)))

        findings_loaded = len(self._all_rows)
        source_rows.append(("audit_management", "findings loaded into pack", str(findings_loaded)))

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Source", "Coverage", "Rows"])
        table.setRowCount(len(source_rows))
        for idx, (source, coverage, rows) in enumerate(source_rows):
            table.setItem(idx, 0, QTableWidgetItem(source))
            table.setItem(idx, 1, QTableWidgetItem(coverage))
            table.setItem(idx, 2, QTableWidgetItem(rows))
        return table

    def _insert_section(self, cursor: QTextCursor, title: str, table: QTableWidget) -> None:
        cursor.insertText(f"\n{title}\n")
        data = PrintExportHelper._extract_table_data(table, selected_only=False)
        PrintExportHelper._insert_table_into_document(cursor, data, table)

    def print_audit_filing_pack(self) -> None:
        year = int(self.year_spin.value())
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Audit Filing Pack",
            f"Audit_Filing_Pack_{year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            "PDF Files (*.pdf);;All Files (*)",
        )
        if not filename:
            return

        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(filename)

            doc = QTextDocument()
            cursor = QTextCursor(doc)
            cursor.insertText(f"Audit Filing Pack - {year}\n")
            cursor.insertText(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            cursor.insertText(f"Total Findings: {len(self._all_rows)}\n")

            summary_table = self._build_summary_table(self._all_rows)
            self._insert_section(cursor, "Summary", summary_table)

            source_table = self._build_source_coverage_table(year)
            self._insert_section(cursor, "Pack Sources and Coverage", source_table)

            self._insert_section(cursor, "All Findings", self.table)

            open_rows = [r for r in self._all_rows if str(r.get("status", "")).lower() == "open"]
            if open_rows:
                open_table = self._build_temp_findings_table(open_rows)
                self._insert_section(cursor, "Open Findings", open_table)

            high_rows = [r for r in self._all_rows if str(r.get("severity", "")).lower() == "high"]
            if high_rows:
                high_table = self._build_temp_findings_table(high_rows)
                self._insert_section(cursor, "High Severity Findings", high_table)

            doc.print(printer)
            QMessageBox.information(self, "Audit Filing Pack", f"Saved filing pack:\n{filename}")
        except Exception as exc:
            logger.error("Failed to generate audit filing pack: %s", exc)
            QMessageBox.critical(self, "Audit Filing Pack", f"Failed to generate filing pack:\n{exc}")

    def _build_temp_findings_table(self, rows: list[dict]) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(10)
        table.setHorizontalHeaderLabels(
            [
                "Area",
                "Severity",
                "Category",
                "Ref",
                "Period",
                "Amount",
                "Warning",
                "Status",
                "Owner",
                "Note",
            ]
        )
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            table.setItem(r, 0, QTableWidgetItem(str(row.get("area", ""))))
            table.setItem(r, 1, QTableWidgetItem(str(row.get("severity", ""))))
            table.setItem(r, 2, QTableWidgetItem(str(row.get("category", ""))))
            table.setItem(r, 3, QTableWidgetItem(str(row.get("ref", ""))))
            table.setItem(r, 4, QTableWidgetItem(str(row.get("period", ""))))
            table.setItem(r, 5, QTableWidgetItem(f"${self._safe_float(row.get('amount')):,.2f}"))
            table.setItem(r, 6, QTableWidgetItem(str(row.get("warning", ""))))
            table.setItem(r, 7, QTableWidgetItem(str(row.get("status", ""))))
            table.setItem(r, 8, QTableWidgetItem(str(row.get("owner", ""))))
            table.setItem(r, 9, QTableWidgetItem(str(row.get("note", ""))))
        return table

    def _selected_key(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 3)
        if not item:
            return None
        return str(item.data(Qt.ItemDataRole.UserRole) or "")

    def _on_row_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        status_item = self.table.item(row, 7)
        note_item = self.table.item(row, 9)
        if status_item:
            idx = self.status_combo.findText(status_item.text())
            self.status_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.note_edit.setPlainText(note_item.text() if note_item else "")

    def save_resolution(self) -> None:
        key = self._selected_key()
        if not key:
            QMessageBox.information(self, "Audit", "Select a finding row first.")
            return

        status = self.status_combo.currentText().strip() or "open"
        note = self.note_edit.toPlainText().strip() or None
        owner = self.auth_user.get("username", "desktop_user")

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO audit_finding_overrides (
                        finding_key, status, note, owner_name, updated_at
                    ) VALUES (%s, %s, %s, %s, NOW())
                    ON CONFLICT (finding_key) DO UPDATE SET
                        status = EXCLUDED.status,
                        note = EXCLUDED.note,
                        owner_name = EXCLUDED.owner_name,
                        updated_at = NOW()
                    """,
                    (key, status, note, owner),
                )
            self.refresh_findings()
            self._set_status("Saved audit resolution.")
        except Exception as exc:
            logger.error("Failed to save audit resolution: %s", exc)
            QMessageBox.critical(self, "Save Error", f"Failed to save resolution:\n{exc}")

    def clear_resolution(self) -> None:
        key = self._selected_key()
        if not key:
            QMessageBox.information(self, "Audit", "Select a finding row first.")
            return
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "DELETE FROM audit_finding_overrides WHERE finding_key = %s",
                    (key,),
                )
            self.refresh_findings()
            self._set_status("Cleared audit resolution for selected finding.")
        except Exception as exc:
            logger.error("Failed clearing audit resolution: %s", exc)
            QMessageBox.critical(self, "Clear Error", f"Failed to clear resolution:\n{exc}")

    def print_findings(self) -> None:
        year = int(self.year_spin.value())
        PrintExportHelper.print_table(
            self.table,
            f"Audit Findings {year}",
            self,
        )
