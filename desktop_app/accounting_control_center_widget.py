"""
Accounting Control Center

Single-screen accounting hub tailored to Arrow Limo's actual data model:
- Charter booking is separate from cash receipt.
- Mixed personal/business banking means deposits are review items, not revenue.
- Payroll and source deductions are separate from charter operations.
- Expense deductibility and ITC readiness need explicit visibility.
"""

import csv
import json
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from db_error_handling import DatabaseContext
from PyQt6.QtCore import QPointF, QRectF, QSettings, Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class DonutChartWidget(QWidget):
    """Simple native PyQt donut chart for compact operational summaries."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.title = title
        self.slices = []
        self.total = 0.0
        self.subtitle = ""
        self.setMinimumHeight(250)
        self.setMinimumWidth(280)

    def set_data(self, slices: list[dict], subtitle: str = "") -> None:
        self.slices = [s for s in slices if float(s.get("value", 0) or 0) > 0]
        self.total = sum(float(s.get("value", 0) or 0) for s in self.slices)
        self.subtitle = subtitle
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(10, 10, -10, -10)
        painter.fillRect(rect, QColor("#ffffff"))

        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor("#1f2937"))
        painter.drawText(
            rect.adjusted(4, 0, -4, 0),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
            self.title,
        )

        chart_rect = QRectF(rect.left() + 18, rect.top() + 34, 150, 150)
        legend_left = int(chart_rect.right()) + 18
        legend_top = int(chart_rect.top())

        if self.total <= 0:
            pen = QPen(QColor("#d1d5db"), 18)
            painter.setPen(pen)
            painter.drawArc(chart_rect, 0, 360 * 16)
            painter.setPen(QColor("#6b7280"))
            painter.drawText(
                chart_rect,
                Qt.AlignmentFlag.AlignCenter,
                "No data",
            )
            return

        start_angle = 90 * 16
        for slice_info in self.slices:
            value = float(slice_info.get("value", 0) or 0)
            span_angle = int(round((value / self.total) * 360 * 16))
            pen = QPen(
                QColor(slice_info.get("color", "#2563eb")),
                18,
            )
            painter.setPen(pen)
            painter.drawArc(chart_rect, start_angle, -span_angle)
            start_angle -= span_angle

        center_rect = chart_rect.adjusted(34, 34, -34, -34)
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center_rect)

        painter.setPen(QColor("#111827"))
        center_font = QFont()
        center_font.setPointSize(14)
        center_font.setBold(True)
        painter.setFont(center_font)
        painter.drawText(
            center_rect,
            Qt.AlignmentFlag.AlignCenter,
            f"{int(round(self.total))}",
        )

        legend_font = QFont()
        legend_font.setPointSize(9)
        painter.setFont(legend_font)
        for idx, slice_info in enumerate(self.slices):
            y = legend_top + idx * 28
            painter.setBrush(QColor(slice_info.get("color", "#2563eb")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(legend_left + 7, y + 10), 5, 5)
            painter.setPen(QColor("#111827"))
            label = str(slice_info.get("label", ""))
            value = float(slice_info.get("value", 0) or 0)
            pct = (value / self.total * 100.0) if self.total else 0.0
            painter.drawText(
                legend_left + 18,
                y + 6,
                130,
                18,
                Qt.AlignmentFlag.AlignLeft,
                label,
            )
            painter.setPen(QColor("#4b5563"))
            painter.drawText(
                legend_left + 18,
                y + 18,
                150,
                18,
                Qt.AlignmentFlag.AlignLeft,
                f"{value:,.0f} ({pct:.0f}%)",
            )

        if self.subtitle:
            painter.setPen(QColor("#6b7280"))
            wrap_flags = (
                int(Qt.AlignmentFlag.AlignLeft)
                | int(Qt.TextFlag.TextWordWrap)
            )
            painter.drawText(
                rect.adjusted(8, 192, -8, -4),
                wrap_flags,
                self.subtitle,
            )


class MetricCard(QFrame):
    """Compact metric card used by the accounting hub."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { background: #f8fafc; border: 1px solid #dbe3ef; "
            "border-radius: 8px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #475569; font-size: 10pt;")
        layout.addWidget(self.title_label)

        self.value_label = QLabel("-")
        self.value_label.setStyleSheet(
            "color: #0f172a; font-size: 18pt; font-weight: bold;"
        )
        layout.addWidget(self.value_label)

        self.caption_label = QLabel("")
        self.caption_label.setWordWrap(True)
        self.caption_label.setStyleSheet("color: #64748b; font-size: 9pt;")
        layout.addWidget(self.caption_label)

    def set_metric(self, value: str, caption: str = "") -> None:
        self.value_label.setText(value)
        self.caption_label.setText(caption)


class AccountingControlCenterWidget(QWidget):
    """Operator-first accounting home screen for Arrow Limo."""

    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self._settings = QSettings()
        self._sequence_actions: list[str] = []
        self._sequence_status: list[str] = []
        self._sequence_index: int = -1
        self._sequence_title: str = ""
        self._sequence_loaded_year: int | None = None
        self._tab_hooks_installed = False
        self._build_ui()
        self._load_sequence_state(int(self.year_spin.value()))
        self.refresh_dashboard()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        container = QWidget()
        self.layout_main = QVBoxLayout(container)
        self.layout_main.setContentsMargins(10, 10, 10, 10)
        self.layout_main.setSpacing(10)
        scroll.setWidget(container)

        header = QGroupBox()
        header_layout = QVBoxLayout(header)
        title = QLabel("<h2>🎯 Accounting Hub</h2>")
        subtitle = QLabel(
            "One screen for the way Arrow Limo actually works: charter cash, "
            "mixed banking, separate payroll, deductible receipts, and CRA "
            "filing blockers."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #475569;")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Year:"))
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2011, 2035)
        self.year_spin.setValue(2025)
        self.year_spin.valueChanged.connect(self.refresh_dashboard)
        controls.addWidget(self.year_spin)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_dashboard)
        controls.addWidget(refresh_btn)

        export_snapshot_btn = QPushButton("Export Hub Snapshot")
        export_snapshot_btn.clicked.connect(self._export_hub_snapshot)
        controls.addWidget(export_snapshot_btn)

        export_snapshot_csv_btn = QPushButton("Export Snapshot CSV")
        export_snapshot_csv_btn.clicked.connect(self._export_hub_snapshot_csv)
        controls.addWidget(export_snapshot_csv_btn)

        open_snapshot_folder_btn = QPushButton("Open Snapshot Folder")
        open_snapshot_folder_btn.clicked.connect(self._open_snapshot_folder)
        controls.addWidget(open_snapshot_folder_btn)

        controls.addStretch()

        # "Run ... Fix Sequence" buttons on their own row to avoid a toolbar
        # that runs off the right edge.
        fix_controls = QHBoxLayout()
        run_fix_btn = QPushButton("Run High-Priority Fix Sequence")
        run_fix_btn.clicked.connect(
            self._run_overview_fix_sequence
        )
        fix_controls.addWidget(run_fix_btn)

        run_t2_fix_btn = QPushButton("Run T2 Fix Sequence")
        run_t2_fix_btn.clicked.connect(self._run_t2_fix_sequence)
        fix_controls.addWidget(run_t2_fix_btn)

        run_payroll_fix_btn = QPushButton("Run Payroll Fix Sequence")
        run_payroll_fix_btn.clicked.connect(self._run_payroll_fix_sequence)
        fix_controls.addWidget(run_payroll_fix_btn)

        fix_controls.addStretch()

        # Navigation buttons live on their own row so the toolbar never runs
        # past the right edge (the single row overflowed horizontally).
        nav_controls = QHBoxLayout()
        for label, tab_name in [
            ("Open Receipts", "💰 Receipts & Invoices"),
            ("Open Vendor Invoices", "📋 Vendor Invoice Manager"),
            ("Open Payroll", "💵 Payroll Entry"),
            ("Open Remittances", "🧮 Payroll Remittances"),
            ("Open GST", "🧮 GST Remittance"),
            ("Open Tax", "🏛️ Tax Management"),
            ("Open Reports", "📊 Financial Reports"),
        ]:
            button = QPushButton(label)
            button.clicked.connect(
                lambda _checked=False, target=tab_name: (
                    self._jump_to_accounting_subtab(target)
                )
            )
            nav_controls.addWidget(button)
        nav_controls.addStretch()

        header_layout.addLayout(controls)
        header_layout.addLayout(fix_controls)
        header_layout.addLayout(nav_controls)
        self.layout_main.addWidget(header)

        self.panel_tabs = QTabWidget()
        self.panel_tabs.setMinimumHeight(560)
        self.layout_main.addWidget(self.panel_tabs)

        overview_panel = QWidget()
        overview_layout = QVBoxLayout(overview_panel)

        metrics_group = QGroupBox("Year Summary")
        metrics_layout = QGridLayout(metrics_group)
        self.card_revenue = MetricCard("Charter Cash Revenue")
        self.card_payments = MetricCard("Charter Cash Rows")
        self.card_expenses = MetricCard("Business Receipt Gross")
        self.card_flags = MetricCard("Fix-Now Flags")
        metrics_layout.addWidget(self.card_revenue, 0, 0)
        metrics_layout.addWidget(self.card_payments, 0, 1)
        metrics_layout.addWidget(self.card_expenses, 0, 2)
        metrics_layout.addWidget(self.card_flags, 0, 3)
        overview_layout.addWidget(metrics_group)

        chart_row = QHBoxLayout()
        self.chart_payments = DonutChartWidget("Charter Cash Link Health")
        self.chart_receipts = DonutChartWidget("Receipt Reporting Status")
        self.chart_remit = DonutChartWidget("Source Deduction Status")
        chart_row.addWidget(self.chart_payments)
        chart_row.addWidget(self.chart_receipts)
        chart_row.addWidget(self.chart_remit)
        overview_layout.addLayout(chart_row)

        self.warning_group = QGroupBox("Fix Now")
        warning_layout = QVBoxLayout(self.warning_group)
        self.warning_table = QTableWidget()
        self.warning_table.setColumnCount(4)
        self.warning_table.setHorizontalHeaderLabels(
            ["Priority", "Area", "Count", "Action"]
        )
        self.warning_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.warning_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.warning_table.setAlternatingRowColors(True)
        self.warning_table.cellDoubleClicked.connect(
            self._on_warning_row_activated
        )
        warning_layout.addWidget(self.warning_table)
        overview_layout.addWidget(self.warning_group)

        self.notes_group = QGroupBox("Operator Rules")
        notes_layout = QVBoxLayout(self.notes_group)
        self.notes_label = QLabel()
        self.notes_label.setWordWrap(True)
        self.notes_label.setStyleSheet("color: #334155;")
        notes_layout.addWidget(self.notes_label)
        overview_layout.addWidget(self.notes_group)

        self.panel_tabs.addTab(overview_panel, "Overview")
        self.panel_tabs.addTab(
            self._create_banking_panel(), "Mixed Banking"
        )
        self.panel_tabs.addTab(
            self._create_t2_panel(), "T2 Readiness"
        )
        self.panel_tabs.addTab(
            self._create_payroll_panel(), "Payroll Close"
        )
        self.panel_tabs.addTab(
            self._create_gst_panel(), "GST Remittance"
        )

        self.sequence_group = QGroupBox("Fix Sequence Tracker")
        sequence_layout = QVBoxLayout(self.sequence_group)

        self.sequence_info_label = QLabel(
            "No active sequence. Use one of the fix-sequence buttons above "
            "to start guided remediation."
        )
        self.sequence_info_label.setWordWrap(True)
        self.sequence_info_label.setStyleSheet(
            "color: #334155;"
        )
        sequence_layout.addWidget(self.sequence_info_label)

        self.sequence_table = QTableWidget()
        self.sequence_table.setColumnCount(3)
        self.sequence_table.setHorizontalHeaderLabels(
            ["Step", "Action", "Status"]
        )
        self.sequence_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.sequence_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.sequence_table.setAlternatingRowColors(True)
        self.sequence_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.sequence_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.sequence_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        sequence_layout.addWidget(self.sequence_table)

        sequence_controls = QHBoxLayout()
        self.sequence_mark_done_btn = QPushButton(
            "Mark Step Complete + Refresh"
        )
        self.sequence_mark_done_btn.clicked.connect(
            self._mark_sequence_step_complete
        )
        self.sequence_mark_done_btn.setEnabled(False)
        sequence_controls.addWidget(self.sequence_mark_done_btn)

        self.sequence_open_current_btn = QPushButton("Open Current Step")
        self.sequence_open_current_btn.clicked.connect(
            self._open_current_sequence_step
        )
        self.sequence_open_current_btn.setEnabled(False)
        sequence_controls.addWidget(self.sequence_open_current_btn)

        self.sequence_cancel_btn = QPushButton("Cancel Sequence")
        self.sequence_cancel_btn.clicked.connect(self._clear_sequence)
        self.sequence_cancel_btn.setEnabled(False)
        sequence_controls.addWidget(self.sequence_cancel_btn)

        sequence_controls.addStretch()
        sequence_layout.addLayout(sequence_controls)

        history_label = QLabel("Recent Sequence History")
        history_label.setStyleSheet(
            "color: #334155; font-weight: bold;"
        )
        sequence_layout.addWidget(history_label)

        self.sequence_history_table = QTableWidget()
        self.sequence_history_table.setColumnCount(5)
        self.sequence_history_table.setHorizontalHeaderLabels(
            ["Year", "Last Updated", "Sequence", "Progress", "State"]
        )
        self.sequence_history_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.sequence_history_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.sequence_history_table.setAlternatingRowColors(True)
        self.sequence_history_table.setMaximumHeight(210)
        self.sequence_history_table.cellDoubleClicked.connect(
            self._on_sequence_history_row_activated
        )
        self.sequence_history_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.sequence_history_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.sequence_history_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.sequence_history_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.sequence_history_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        sequence_layout.addWidget(self.sequence_history_table)

        history_controls = QHBoxLayout()
        self.sequence_history_load_btn = QPushButton("Load Selected Year")
        self.sequence_history_load_btn.clicked.connect(
            self._load_selected_history_year
        )
        history_controls.addWidget(self.sequence_history_load_btn)

        self.sequence_history_resume_btn = QPushButton("Resume Selected Year")
        self.sequence_history_resume_btn.clicked.connect(
            self._resume_selected_history_year
        )
        history_controls.addWidget(self.sequence_history_resume_btn)
        history_controls.addStretch()
        sequence_layout.addLayout(history_controls)

        self.sequence_history_trend_label = QLabel("Completion trend: -")
        self.sequence_history_trend_label.setWordWrap(True)
        self.sequence_history_trend_label.setStyleSheet(
            "color: #475569;"
        )
        sequence_layout.addWidget(self.sequence_history_trend_label)

        history_visuals = QHBoxLayout()
        self.sequence_state_mix_chart = DonutChartWidget("Sequence State Mix")
        self.sequence_state_mix_chart.setMinimumHeight(210)
        self.sequence_state_mix_chart.setMinimumWidth(260)
        history_visuals.addWidget(self.sequence_state_mix_chart)

        self.sequence_completion_bucket_chart = DonutChartWidget(
            "Completion Buckets"
        )
        self.sequence_completion_bucket_chart.setMinimumHeight(210)
        self.sequence_completion_bucket_chart.setMinimumWidth(260)
        history_visuals.addWidget(self.sequence_completion_bucket_chart)
        sequence_layout.addLayout(history_visuals)

        self.panel_tabs.addTab(self.sequence_group, "Fix Sequence")

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            "color: #2563eb; font-weight: bold;"
        )
        self.layout_main.addWidget(self.status_label)
        self.layout_main.addStretch()

        self._latest_snapshot = None

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._ensure_tab_hooks()

    def _ensure_tab_hooks(self) -> None:
        if self._tab_hooks_installed:
            return
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QTabWidget):
                try:
                    parent.currentChanged.connect(self._on_parent_tab_changed)
                except Exception as _e:
                    logger.debug('Suppressed: %s', _e)
            parent = parent.parentWidget()
        self._tab_hooks_installed = True

    def _on_parent_tab_changed(self, _index: int) -> None:
        # Auto-refresh when the operator returns to this hub view
        # during an active fix sequence.
        if self.isVisible() and self._sequence_actions:
            self.refresh_dashboard()
            self._set_status(
                
                    f"{self._sequence_title} active. "
                    "Data refreshed on return to hub."
                
            )

    def _create_banking_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        summary = QLabel(
            "Classifies mixed-bank inflows so deposits are not treated as "
            "automatic revenue. "
            "Use this to isolate charter settlements, transfers, "
            "personal/owner "
            "flows, and unknowns."
        )
        summary.setWordWrap(True)
        summary.setStyleSheet("color: #475569;")
        layout.addWidget(summary)

        cards = QHBoxLayout()
        self.bank_total_card = MetricCard("Credit Inflows")
        self.bank_unknown_card = MetricCard("Unknown Inflows")
        self.bank_transfer_card = MetricCard("Transfer Inflows")
        self.bank_charter_card = MetricCard("Charter-Linked Inflows")
        cards.addWidget(self.bank_total_card)
        cards.addWidget(self.bank_unknown_card)
        cards.addWidget(self.bank_transfer_card)
        cards.addWidget(self.bank_charter_card)
        layout.addLayout(cards)

        self.banking_chart = DonutChartWidget("Bank Inflow Classification")
        layout.addWidget(self.banking_chart)

        self.banking_table = QTableWidget()
        self.banking_table.setColumnCount(4)
        self.banking_table.setHorizontalHeaderLabels(
            ["Class", "Count", "Amount", "Rule"]
        )
        self.banking_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.banking_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.banking_table.setAlternatingRowColors(True)
        self.banking_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.banking_table)

        self.banking_unknown_table = QTableWidget()
        self.banking_unknown_table.setColumnCount(4)
        self.banking_unknown_table.setHorizontalHeaderLabels(
            ["Date", "Description", "Amount", "Category"]
        )
        self.banking_unknown_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.banking_unknown_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.banking_unknown_table.setAlternatingRowColors(True)
        self.banking_unknown_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.banking_unknown_table)

        return panel

    def _create_t2_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        summary = QLabel(
            "Pass/fail checks for CRA-ready T2 support "
            "using Arrow Limo rules: "
            "charter cash as revenue source, deductible receipt controls, "
            "and unresolved "
            "risk buckets."
        )
        summary.setWordWrap(True)
        summary.setStyleSheet("color: #475569;")
        layout.addWidget(summary)

        cards = QHBoxLayout()
        self.t2_status_card = MetricCard("Overall")
        self.t2_revenue_card = MetricCard("Revenue Basis")
        self.t2_receipt_card = MetricCard("Receipt Controls")
        self.t2_risk_card = MetricCard("Risk Buckets")
        cards.addWidget(self.t2_status_card)
        cards.addWidget(self.t2_revenue_card)
        cards.addWidget(self.t2_receipt_card)
        cards.addWidget(self.t2_risk_card)
        layout.addLayout(cards)

        self.t2_table = QTableWidget()
        self.t2_table.setColumnCount(4)
        self.t2_table.setHorizontalHeaderLabels(
            ["Check", "Status", "Detail", "Action"]
        )
        self.t2_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.t2_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.t2_table.setAlternatingRowColors(True)
        self.t2_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.t2_table.cellDoubleClicked.connect(self._on_check_row_activated)
        layout.addWidget(self.t2_table)
        return panel

    def _create_payroll_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        summary = QLabel(
            "Annual payroll close checks: payroll master totals vs T4 records "
            "and monthly source deduction closure "
            "(due/paid/PD7A/reconciled)."
        )
        summary.setWordWrap(True)
        summary.setStyleSheet("color: #475569;")
        layout.addWidget(summary)

        cards = QHBoxLayout()
        self.payroll_total_card = MetricCard("Payroll Gross")
        self.payroll_t4_card = MetricCard("T4 Gross")
        self.payroll_remit_card = MetricCard("Remittance Due")
        self.payroll_var_card = MetricCard("Close Variance")
        cards.addWidget(self.payroll_total_card)
        cards.addWidget(self.payroll_t4_card)
        cards.addWidget(self.payroll_remit_card)
        cards.addWidget(self.payroll_var_card)
        layout.addLayout(cards)

        self.payroll_table = QTableWidget()
        self.payroll_table.setColumnCount(4)
        self.payroll_table.setHorizontalHeaderLabels(
            ["Check", "Status", "Detail", "Action"]
        )
        self.payroll_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.payroll_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.payroll_table.setAlternatingRowColors(True)
        self.payroll_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.payroll_table.cellDoubleClicked.connect(
            self._on_check_row_activated
        )
        layout.addWidget(self.payroll_table)
        return panel

    def _create_gst_panel(self) -> QWidget:
        """GST Remittance tracking panel for CRA payments"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        summary = QLabel(
            "GST remittance tracking: GST collected by period vs payments made to CRA. "
            "Supports manual entry for payments at other banks and multi-bank tracking. "
            "CRA requires 6-year record retention (Income Tax Act Section 230)."
        )
        summary.setWordWrap(True)
        summary.setStyleSheet("color: #475569;")
        layout.addWidget(summary)

        # Try to import and display GST manager
        try:
            from gst_remittance_manager import GSTRemittanceManager
            gst_manager = GSTRemittanceManager(self)
            layout.addWidget(gst_manager)
        except Exception as e:
            logger.warning(f"GST Remittance Manager not available: {e}")
            error_label = QLabel(
                f"GST Remittance Manager not available.\n\nError: {e}"
            )
            error_label.setStyleSheet("color: #dc2626;")
            layout.addWidget(error_label)

        layout.addStretch()
        return panel

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status_label.setStyleSheet(
            "color: #dc2626; font-weight: bold;"
            if error
            else "color: #2563eb; font-weight: bold;"
        )
        self.status_label.setText(text)

    def _json_default(self, obj) -> object:
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)

    def _export_hub_snapshot(self) -> None:
        if not self._latest_snapshot:
            self.refresh_dashboard()

        if not self._latest_snapshot:
            QMessageBox.warning(
                self,
                "Export Hub Snapshot",
                "No dashboard data available to export.",
            )
            return

        try:
            out_dir = self._snapshot_output_dir()
            out_dir.mkdir(parents=True, exist_ok=True)

            year = int(self.year_spin.value())
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = out_dir / f"accounting_hub_snapshot_{year}_{stamp}.json"

            with out_path.open("w", encoding="utf-8") as fh:
                json.dump(
                    self._latest_snapshot,
                    fh,
                    indent=2,
                    default=self._json_default,
                )

            self._set_status(f"Exported hub snapshot: {out_path}")
            QMessageBox.information(
                self,
                "Export Hub Snapshot",
                f"Snapshot saved to:\n{out_path}",
            )
        except Exception as exc:
            logger.error(f"Failed to export hub snapshot: {exc}")
            QMessageBox.warning(
                self,
                "Export Hub Snapshot",
                f"Failed to export snapshot: {exc}",
            )

    def _export_hub_snapshot_csv(self) -> None:
        if not self._latest_snapshot:
            self.refresh_dashboard()

        if not self._latest_snapshot:
            QMessageBox.warning(
                self,
                "Export Snapshot CSV",
                "No dashboard data available to export.",
            )
            return

        try:
            out_dir = self._snapshot_output_dir()
            out_dir.mkdir(parents=True, exist_ok=True)

            year = int(self.year_spin.value())
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = out_dir / f"accounting_hub_snapshot_{year}_{stamp}.csv"

            dashboard = (
                self._latest_snapshot.get("dashboard", {})
                if isinstance(self._latest_snapshot, dict)
                else {}
            )
            banking = (
                self._latest_snapshot.get("banking", {})
                if isinstance(self._latest_snapshot, dict)
                else {}
            )
            t2 = (
                self._latest_snapshot.get("t2", {})
                if isinstance(self._latest_snapshot, dict)
                else {}
            )
            payroll = (
                self._latest_snapshot.get("payroll", {})
                if isinstance(self._latest_snapshot, dict)
                else {}
            )

            row = {
                "generated_at": self._latest_snapshot.get("generated_at", ""),
                "year": year,
                "charter_revenue": dashboard.get("charter_revenue", 0),
                "charter_count": dashboard.get("charter_count", 0),
                "linked_payments": dashboard.get("linked_payments", 0),
                "unlinked_payments": dashboard.get("unlinked_payments", 0),
                "square_unmatched": dashboard.get("square_unmatched", 0),
                "business_receipts": dashboard.get("business_receipts", 0),
                "missing_gl": dashboard.get("missing_gl", 0),
                "risky_receipts": dashboard.get("risky_receipts", 0),
                "open_remittance_months": dashboard.get("open_months", 0),
                "total_flag_count": dashboard.get("total_flag_count", 0),
                "bank_unknown_count": (
                    (banking.get("totals") or {}).get("unknown_count", 0)
                ),
                "bank_unknown_amount": (
                    (banking.get("totals") or {}).get("unknown_amount", 0)
                ),
                "t2_fail_count": (
                    (t2.get("status_counts") or {}).get("FAIL", 0)
                ),
                "t2_warn_count": (
                    (t2.get("status_counts") or {}).get("WARN", 0)
                ),
                "payroll_check_count": (
                    len(payroll.get("checks", []))
                    if isinstance(payroll, dict)
                    else 0
                ),
            }

            with out_path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
                writer.writeheader()
                writer.writerow(
                    {k: self._json_default(v) for k, v in row.items()}
                )

            self._set_status(f"Exported snapshot CSV: {out_path}")
            QMessageBox.information(
                self,
                "Export Snapshot CSV",
                f"Snapshot CSV saved to:\n{out_path}",
            )
        except Exception as exc:
            logger.error(f"Failed to export snapshot CSV: {exc}")
            QMessageBox.warning(
                self,
                "Export Snapshot CSV",
                f"Failed to export snapshot CSV: {exc}",
            )

    def _snapshot_output_dir(self) -> Path:
        root = Path(__file__).resolve().parents[1]
        return root / "reports" / "accounting_hub_snapshots"

    def _open_snapshot_folder(self) -> None:
        try:
            out_dir = self._snapshot_output_dir()
            out_dir.mkdir(parents=True, exist_ok=True)
            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(out_dir)))
            if opened:
                self._set_status(f"Opened snapshot folder: {out_dir}")
                return

            QMessageBox.information(
                self,
                "Open Snapshot Folder",
                f"Snapshot folder:\n{out_dir}",
            )
        except Exception as exc:
            logger.error(f"Failed to open snapshot folder: {exc}")
            QMessageBox.warning(
                self,
                "Open Snapshot Folder",
                f"Failed to open snapshot folder: {exc}",
            )

    def _money(self, amount) -> str:
        return f"${float(amount or 0):,.2f}"

    def _jump_to_accounting_subtab(self, target_text: str) -> None:
        root = self.window()
        if root is None:
            QMessageBox.information(
                self,
                "Navigation",
                "Could not locate main window.",
            )
            return

        tab_widgets = (
            root.findChildren(type(getattr(root, "tabs", None)))
            if hasattr(root, "tabs")
            else []
        )
        if not tab_widgets:
            from PyQt6.QtWidgets import QTabWidget

            tab_widgets = root.findChildren(QTabWidget)

        for tabs in tab_widgets:
            for idx in range(tabs.count()):
                if tabs.tabText(idx) != target_text:
                    continue

                tabs.setCurrentIndex(idx)
                if hasattr(root, "_on_accounting_subtab_changed"):
                    try:
                        root._on_accounting_subtab_changed(tabs, idx)
                    except Exception as _e:
                        logger.debug('Suppressed: %s', _e)
                self._set_status(f"Opened {target_text}.")
                return

        QMessageBox.information(
            self,
            "Navigation",
            f"Could not find tab: {target_text}",
        )

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

    def _status_level(self, ok: bool, warn: bool = False) -> str:
        if ok:
            return "PASS"
        if warn:
            return "WARN"
        return "FAIL"

    def _status_rank(self, status: str) -> int:
        ranks = {"FAIL": 0, "WARN": 1, "PASS": 2}
        return ranks.get((status or "").upper(), 3)

    def _priority_rank(self, priority: str) -> int:
        ranks = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        return ranks.get((priority or "").upper(), 3)

    def _populate_check_table(self, table: QTableWidget, rows: list[tuple]) -> None:
        rows_sorted = sorted(
            rows,
            key=lambda r: (self._status_rank(r[1]), str(r[0]).lower()),
        )
        table.setRowCount(len(rows_sorted))
        for idx, row in enumerate(rows_sorted):
            check_name, status, detail, action = row
            table.setItem(idx, 0, QTableWidgetItem(check_name))
            status_text = (status or "").upper()
            status_item = QTableWidgetItem(
                {
                    "PASS": "[OK] PASS",
                    "WARN": "[WARN] WARN",
                    "FAIL": "[FAIL] FAIL",
                }.get(status_text, status_text)
            )
            if status_text == "PASS":
                status_item.setForeground(QColor("#166534"))
                row_bg = QColor("#ecfdf3")
            elif status_text == "WARN":
                status_item.setForeground(QColor("#b45309"))
                row_bg = QColor("#fffbeb")
            else:
                status_item.setForeground(QColor("#b91c1c"))
                row_bg = QColor("#fef2f2")
            table.setItem(idx, 1, status_item)
            table.setItem(idx, 2, QTableWidgetItem(detail))
            table.setItem(idx, 3, QTableWidgetItem(action))

            for col in range(4):
                item = table.item(idx, col)
                if item:
                    item.setBackground(row_bg)

    def _on_warning_row_activated(self, row: int, _column: int) -> None:
        action_item = self.warning_table.item(row, 3)
        if not action_item:
            return
        action_text = (action_item.text() or "").strip()
        self._open_action_target(action_text)

    def _on_check_row_activated(self, row: int, _column: int) -> None:
        table = self.sender()
        if not isinstance(table, QTableWidget):
            return
        action_item = table.item(row, 3)
        if not action_item:
            return
        action_text = (action_item.text() or "").strip()
        self._open_action_target(action_text)

    def _open_action_target(self, action_text: str) -> None:
        mapping = {
            "Open Receipts": "💰 Receipts & Invoices",
            "Open Remittances": "🧮 Payroll Remittances",
            "Open Reports": "📊 Financial Reports",
            "Open Tax": "🏛️ Tax Management",
            "Open Payroll": "💵 Payroll Entry",
        }
        target = mapping.get(action_text)
        if target:
            self._jump_to_accounting_subtab(target)

    def _render_sequence_table(self) -> None:
        self.sequence_table.setRowCount(len(self._sequence_actions))
        for idx, action in enumerate(self._sequence_actions):
            status = (
                self._sequence_status[idx]
                if idx < len(self._sequence_status)
                else "PENDING"
            )
            self.sequence_table.setItem(idx, 0, QTableWidgetItem(str(idx + 1)))
            self.sequence_table.setItem(idx, 1, QTableWidgetItem(action))
            status_item = QTableWidgetItem(status)
            self.sequence_table.setItem(idx, 2, status_item)

            if status == "DONE":
                color = QColor("#ecfdf3")
                status_item.setForeground(QColor("#166534"))
            elif status == "CURRENT":
                color = QColor("#e0f2fe")
                status_item.setForeground(QColor("#075985"))
            else:
                color = QColor("#fffbeb")
                status_item.setForeground(QColor("#92400e"))

            for col in range(3):
                item = self.sequence_table.item(idx, col)
                if item:
                    item.setBackground(color)

        self.sequence_mark_done_btn.setEnabled(
            bool(self._sequence_actions) and self._sequence_index >= 0
        )
        self.sequence_open_current_btn.setEnabled(
            bool(self._sequence_actions) and self._sequence_index >= 0
        )
        self.sequence_cancel_btn.setEnabled(bool(self._sequence_actions))

    def _sequence_settings_key(self, year: int) -> str:
        return f"accounting_hub/sequence_state/{year}"

    def _sequence_history_key(self, year: int) -> str:
        return f"accounting_hub/sequence_history/{year}"

    def _write_sequence_history(
        self,
        year: int,
        title: str,
        done_steps: int,
        total_steps: int,
        state: str,
    ) -> None:
        payload = {
            "title": str(title or "Fix Sequence"),
            "done_steps": int(done_steps or 0),
            "total_steps": int(total_steps or 0),
            "state": str(state or "ACTIVE").upper(),
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._settings.setValue(
            self._sequence_history_key(year), json.dumps(payload)
        )

    def _read_sequence_history(self, year: int) -> dict | None:
        raw = self._settings.value(self._sequence_history_key(year), "")
        if not raw:
            return None
        try:
            payload = json.loads(str(raw))
            if not isinstance(payload, dict):
                return None
            return payload
        except Exception:
            return None

    def _render_sequence_history(self) -> None:
        selected_year = int(self.year_spin.value())
        years = set()
        history_rows = []

        self._settings.beginGroup("accounting_hub/sequence_history")
        for key in self._settings.childKeys():
            try:
                years.add(int(str(key)))
            except Exception:
                continue
        self._settings.endGroup()

        years.add(selected_year)
        ordered_years = sorted(years, reverse=True)
        if selected_year in ordered_years:
            ordered_years.remove(selected_year)
        ordered_years.insert(0, selected_year)
        ordered_years = ordered_years[:6]

        self.sequence_history_table.setRowCount(len(ordered_years))
        for row, year in enumerate(ordered_years):
            payload = self._read_sequence_history(year) or {}
            title = str(payload.get("title") or "No sequence history")
            done_steps = int(payload.get("done_steps") or 0)
            total_steps = int(payload.get("total_steps") or 0)
            state = str(payload.get("state") or "NONE").upper()
            updated = str(payload.get("last_updated") or "-")

            history_rows.append((year, done_steps, total_steps, state))

            if total_steps > 0:
                progress = (
                    f"{done_steps}/{total_steps} "
                    f"({round((done_steps / total_steps) * 100)}%)"
                )
            else:
                progress = "-"

            self.sequence_history_table.setItem(
                row, 0, QTableWidgetItem(str(year)))
            self.sequence_history_table.setItem(
                row, 1, QTableWidgetItem(updated))
            self.sequence_history_table.setItem(
                row, 2, QTableWidgetItem(title))
            self.sequence_history_table.setItem(
                row, 3, QTableWidgetItem(progress)
            )
            self.sequence_history_table.setItem(
                row, 4, QTableWidgetItem(state)
            )

            if year == selected_year:
                for col in range(5):
                    item = self.sequence_history_table.item(row, col)
                    if item:
                        item.setBackground(QColor("#eef2ff"))

            state_item = self.sequence_history_table.item(row, 4)
            if state_item:
                if state == "COMPLETE":
                    state_item.setForeground(QColor("#166534"))
                elif state == "ACTIVE":
                    state_item.setForeground(QColor("#075985"))
                elif state == "CANCELED":
                    state_item.setForeground(QColor("#b45309"))
                else:
                    state_item.setForeground(QColor("#6b7280"))

        trend_parts = []
        complete_count = 0
        active_count = 0
        for year, done_steps, total_steps, state in history_rows:
            if total_steps > 0:
                pct = round((done_steps / total_steps) * 100)
                trend_parts.append(f"{year}: {pct}%")
            if state == "COMPLETE":
                complete_count += 1
            if state == "ACTIVE":
                active_count += 1

        if trend_parts:
            trend_text = " | ".join(trend_parts[:6])
            self.sequence_history_trend_label.setText(
                "Completion trend (latest): "
                f"{trend_text}  |  Complete years: {complete_count} | "
                f"Active years: {active_count}"
            )
        else:
            self.sequence_history_trend_label.setText(
                "Completion trend: no saved sequence history yet."
            )

        state_none = max(
            len(history_rows) - (complete_count + active_count),
            0,
        )
        canceled_count = sum(
            1
            for _year, _done, _total, state in history_rows
            if state == "CANCELED"
        )
        state_none = max(state_none - canceled_count, 0)
        self.sequence_state_mix_chart.set_data(
            [
                {
                    "label": "Complete",
                    "value": complete_count,
                    "color": "#16a34a",
                },
                {
                    "label": "Active",
                    "value": active_count,
                    "color": "#2563eb",
                },
                {
                    "label": "Canceled",
                    "value": canceled_count,
                    "color": "#f59e0b",
                },
                {
                    "label": "None",
                    "value": state_none,
                    "color": "#94a3b8",
                },
            ],
            subtitle="State mix for listed years.",
        )

        high = 0
        mid = 0
        low = 0
        nodata = 0
        for _year, done_steps, total_steps, _state in history_rows:
            if total_steps <= 0:
                nodata += 1
                continue
            pct = round((done_steps / total_steps) * 100)
            if pct >= 90:
                high += 1
            elif pct >= 50:
                mid += 1
            else:
                low += 1

        self.sequence_completion_bucket_chart.set_data(
            [
                {"label": "90-100%", "value": high, "color": "#16a34a"},
                {"label": "50-89%", "value": mid, "color": "#f59e0b"},
                {"label": "0-49%", "value": low, "color": "#dc2626"},
                {"label": "No data", "value": nodata, "color": "#94a3b8"},
            ],
            subtitle="Completion buckets for listed years.",
        )

    def _on_sequence_history_row_activated(self, row: int, _column: int) -> None:
        selected_year = self._get_history_row_year(row)
        if selected_year is None:
            return

        current_year = int(self.year_spin.value())
        if selected_year != current_year:
            self.year_spin.setValue(selected_year)
            return

        self._load_sequence_state(selected_year)
        self.refresh_dashboard()
        self._set_status(f"Loaded sequence history for {selected_year}.")

    def _get_history_row_year(self, row: int) -> int | None:
        year_item = self.sequence_history_table.item(row, 0)
        if not year_item:
            return None
        try:
            return int((year_item.text() or "").strip())
        except Exception:
            return None

    def _get_selected_history_year(self) -> int | None:
        row = self.sequence_history_table.currentRow()
        if row < 0:
            QMessageBox.information(
                self,
                "Sequence History",
                "Select a history row first.",
            )
            return None
        return self._get_history_row_year(row)

    def _load_selected_history_year(self) -> None:
        selected_year = self._get_selected_history_year()
        if selected_year is None:
            return

        current_year = int(self.year_spin.value())
        if selected_year != current_year:
            self.year_spin.setValue(selected_year)
            self._set_status(f"Loaded history year {selected_year}.")
            return

        self._load_sequence_state(selected_year)
        self.refresh_dashboard()
        self._set_status(
            f"Loaded sequence history for {selected_year}."
        )

    def _resume_selected_history_year(self) -> None:
        selected_year = self._get_selected_history_year()
        if selected_year is None:
            return

        current_year = int(self.year_spin.value())
        if selected_year != current_year:
            self.year_spin.setValue(selected_year)

        self._load_sequence_state(selected_year)
        self.refresh_dashboard()

        if self._sequence_actions and self._sequence_index >= 0:
            self._open_current_sequence_step()
            self._set_status(
                f"Resumed {self._sequence_title} for {selected_year}."
            )
            return

        self._set_status(
            f"No active sequence to resume for {selected_year}."
        )

    def _save_sequence_state(self) -> None:
        year = int(self.year_spin.value())
        key = self._sequence_settings_key(year)

        if not self._sequence_actions:
            self._settings.remove(key)
            self._sequence_loaded_year = year
            self._render_sequence_history()
            return

        payload = {
            "title": self._sequence_title,
            "actions": self._sequence_actions,
            "status": self._sequence_status,
            "index": self._sequence_index,
        }
        self._settings.setValue(key, json.dumps(payload))
        done_steps = sum(
            1 for token in self._sequence_status if token == "DONE"
        )
        total_steps = len(self._sequence_actions)
        state = (
            "COMPLETE"
            if total_steps > 0 and done_steps >= total_steps
            else "ACTIVE"
        )
        self._write_sequence_history(
            year,
            self._sequence_title,
            done_steps,
            total_steps,
            state,
        )
        self._sequence_loaded_year = year
        self._render_sequence_history()

    def _load_sequence_state(self, year: int) -> None:
        key = self._sequence_settings_key(year)
        raw = self._settings.value(key, "")
        self._sequence_loaded_year = year

        if not raw:
            self._clear_sequence(reset_message=True, persist=False)
            return

        try:
            payload = json.loads(str(raw))
        except Exception:
            self._settings.remove(key)
            self._clear_sequence(reset_message=True, persist=False)
            return

        actions = payload.get("actions") if isinstance(payload, dict) else None
        status = payload.get("status") if isinstance(payload, dict) else None
        title = (
            str(payload.get("title") or "Fix Sequence")
            if isinstance(payload, dict)
            else "Fix Sequence"
        )
        index = int(payload.get("index", 0)) if isinstance(
            payload, dict) else 0

        if not isinstance(actions, list) or not actions:
            self._settings.remove(key)
            self._clear_sequence(reset_message=True, persist=False)
            return

        normalized_actions = [
            str(action).strip()
            for action in actions
            if str(action).strip()
        ]
        if not normalized_actions:
            self._settings.remove(key)
            self._clear_sequence(reset_message=True, persist=False)
            return

        valid_status = {"PENDING", "CURRENT", "DONE"}
        normalized_status = []
        if isinstance(status, list):
            for idx, _action in enumerate(normalized_actions):
                token = (
                    str(status[idx]).upper()
                    if idx < len(status)
                    else "PENDING"
                )
                normalized_status.append(
                    token if token in valid_status else "PENDING"
                )
        else:
            normalized_status = ["PENDING" for _ in normalized_actions]

        if index < 0 or index >= len(normalized_actions):
            done_idx = [
                idx
                for idx, status_value in enumerate(normalized_status)
                if status_value != "DONE"
            ]
            index = done_idx[0] if done_idx else -1

        if index >= 0:
            for idx in range(len(normalized_status)):
                if normalized_status[idx] != "DONE":
                    normalized_status[idx] = (
                        "CURRENT" if idx == index else "PENDING"
                    )

        self._sequence_title = title
        self._sequence_actions = normalized_actions
        self._sequence_status = normalized_status
        self._sequence_index = index
        if self._sequence_index >= 0:
            self.sequence_info_label.setText(
                f"{self._sequence_title} resumed. Complete each step, "
                "return to this hub, then click 'Mark Step Complete + "
                "Refresh'."
            )
        else:
            self.sequence_info_label.setText(
                f"{self._sequence_title} is fully complete for this year."
            )
        self._render_sequence_table()
        self._render_sequence_history()

    def _start_fix_sequence(self, title: str, actions: list[str]) -> None:
        if not actions:
            QMessageBox.information(
                self,
                "Fix Sequence",
                "No actions are available for this sequence.",
            )
            return

        self._sequence_title = title
        self._sequence_actions = list(actions)
        self._sequence_status = ["PENDING" for _ in actions]
        self._sequence_index = 0
        self._sequence_status[0] = "CURRENT"

        self.sequence_info_label.setText(
            f"{title} active. Complete each step, return to this hub, "
            "then click 'Mark Step Complete + Refresh'."
        )
        self._save_sequence_state()
        self._render_sequence_table()

        self._open_current_sequence_step()
        QMessageBox.information(
            self,
            title,
            "Run these in order:\n\n"
            + "\n".join(
                f"{idx + 1}. {act}" for idx, act in enumerate(actions)
            ),
        )

    def _open_current_sequence_step(self) -> None:
        if not self._sequence_actions or self._sequence_index < 0:
            QMessageBox.information(
                self, "Fix Sequence", "No active sequence."
            )
            return
        action = self._sequence_actions[self._sequence_index]
        self._open_action_target(action)

    def _mark_sequence_step_complete(self) -> None:
        if not self._sequence_actions or self._sequence_index < 0:
            QMessageBox.information(
                self, "Fix Sequence", "No active sequence."
            )
            return

        current = self._sequence_index
        self._sequence_status[current] = "DONE"

        next_idx = -1
        for idx in range(current + 1, len(self._sequence_actions)):
            if self._sequence_status[idx] != "DONE":
                next_idx = idx
                break

        self.refresh_dashboard()

        if next_idx >= 0:
            self._sequence_index = next_idx
            self._sequence_status[next_idx] = "CURRENT"
            self._save_sequence_state()
            self._render_sequence_table()
            self._open_current_sequence_step()
            self._set_status(
                f"{self._sequence_title}: completed step {current + 1}, "
                f"now on step {next_idx + 1}."
            )
            return

        self._save_sequence_state()
        self._render_sequence_table()
        QMessageBox.information(
            self,
            "Sequence Complete",
            f"{self._sequence_title} is complete for this pass.",
        )
        self._set_status(
            f"{self._sequence_title} complete for current pass."
        )
        self._clear_sequence(reset_message=False)

    def _clear_sequence(
        self,
        reset_message: bool = True,
        persist: bool = True,
    ) -> None:
        year = int(self.year_spin.value())
        prev_actions = list(self._sequence_actions)
        prev_status = list(self._sequence_status)
        prev_title = self._sequence_title
        self._sequence_actions = []
        self._sequence_status = []
        self._sequence_index = -1
        self._sequence_title = ""
        if persist:
            if prev_actions:
                done_steps = sum(1 for token in prev_status if token == "DONE")
                total_steps = len(prev_actions)
                state = (
                    "COMPLETE"
                    if total_steps > 0 and done_steps >= total_steps
                    else "CANCELED"
                )
                self._write_sequence_history(
                    year,
                    prev_title,
                    done_steps,
                    total_steps,
                    state,
                )
            self._save_sequence_state()
        if reset_message:
            self.sequence_info_label.setText(
                "No active sequence. Use one of the fix-sequence buttons "
                "above to start guided remediation."
            )
        self._render_sequence_table()
        self._render_sequence_history()

    def _collect_actions_from_table(
        self,
        table: QTableWidget,
        include_status_tokens: tuple[str, ...],
    ) -> list[str]:
        actions = []
        seen = set()
        for row in range(table.rowCount()):
            status_item = table.item(row, 1)
            action_item = table.item(row, 3)
            if not action_item:
                continue

            status_text = (status_item.text() if status_item else "").upper()
            if include_status_tokens and not any(
                token in status_text for token in include_status_tokens
            ):
                continue

            action_text = (action_item.text() or "").strip()
            if not action_text or action_text in seen:
                continue
            seen.add(action_text)
            actions.append(action_text)
        return actions

    def _run_overview_fix_sequence(self) -> None:
        actions = []
        seen = set()

        # First pass: HIGH warnings only
        for row in range(self.warning_table.rowCount()):
            priority_item = self.warning_table.item(row, 0)
            action_item = self.warning_table.item(row, 3)
            if not priority_item or not action_item:
                continue
            if "[HIGH]" not in (priority_item.text() or ""):
                continue
            action_text = (action_item.text() or "").strip()
            if action_text and action_text not in seen:
                seen.add(action_text)
                actions.append(action_text)

        # Fallback: include all warnings if no HIGH rows
        if not actions:
            for row in range(self.warning_table.rowCount()):
                action_item = self.warning_table.item(row, 3)
                if not action_item:
                    continue
                action_text = (action_item.text() or "").strip()
                if action_text and action_text not in seen:
                    seen.add(action_text)
                    actions.append(action_text)

        self._start_fix_sequence("High-Priority Fix Sequence", actions)

    def _run_t2_fix_sequence(self) -> None:
        actions = self._collect_actions_from_table(
            self.t2_table,
            include_status_tokens=("FAIL", "WARN"),
        )
        if not actions:
            QMessageBox.information(
                self,
                "T2 Fix Sequence",
                "T2 checks are clean for this year.",
            )
            return
        self._start_fix_sequence("T2 Fix Sequence", actions)

    def _run_payroll_fix_sequence(self) -> None:
        actions = self._collect_actions_from_table(
            self.payroll_table,
            include_status_tokens=("FAIL", "WARN"),
        )
        if not actions:
            QMessageBox.information(
                self,
                "Payroll Fix Sequence",
                "Payroll close checks are clean for this year.",
            )
            return
        self._start_fix_sequence("Payroll Fix Sequence", actions)

    def _fetch_banking_classification_data(self, year: int) -> dict:
        data = {
            "rows": [],
            "unknown_samples": [],
            "totals": {
                "total_count": 0,
                "total_amount": Decimal("0"),
                "unknown_count": 0,
                "unknown_amount": Decimal("0"),
                "transfer_count": 0,
                "transfer_amount": Decimal("0"),
                "charter_count": 0,
                "charter_amount": Decimal("0"),
            },
        }

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    WITH classified AS (
                        SELECT
                            CASE
                                WHEN COALESCE(is_transfer, FALSE)
                                     OR LOWER(COALESCE(category, ''))
                                        LIKE '%%transfer%%'
                                     OR LOWER(COALESCE(description, '')) ~
                                        '(transfer|xfer|interac transfer)'
                                    THEN 'Inter-Account Transfer'
                                WHEN reconciled_payment_id IS NOT NULL
                                     OR reconciled_charter_id IS NOT NULL
                                     OR LOWER(
                                         COALESCE(reconciliation_status, '')
                                     )
                                        IN ('reconciled', 'matched', 'linked')
                                    THEN 'Charter-Linked Settlement'
                                WHEN LOWER(COALESCE(business_personal, ''))
                                     LIKE '%%personal%%'
                                     OR LOWER(COALESCE(description, '')) ~
                                        '(owner|shareholder|capital|'
                                        'contribution|loan advance)'
                                    THEN 'Personal/Owner Inflow'
                                WHEN LOWER(COALESCE(description, '')) ~
                                      '(square|global|vcard|mcard|acard|'
                                      'card deposit|merchant)'
                                    THEN 'Processor Settlement'
                                ELSE 'Unknown Inflow'
                            END AS class_name,
                            COALESCE(credit_amount, 0) AS amount,
                            description,
                            transaction_date,
                            category
                        FROM banking_transactions
                        WHERE EXTRACT(YEAR FROM transaction_date) = %s
                          AND COALESCE(credit_amount, 0) > 0
                    )
                    SELECT class_name, COUNT(*), COALESCE(SUM(amount), 0)
                    FROM classified
                    GROUP BY class_name
                    ORDER BY COALESCE(SUM(amount), 0) DESC
                    """,
                    (year,),
                )
                grouped = cur.fetchall()

                for class_name, cnt, amt in grouped:
                    count_v = int(cnt or 0)
                    amt_v = Decimal(str(amt or 0))
                    rule = {
                        "Inter-Account Transfer": (
                            "is_transfer/category/description markers"
                        ),
                        "Charter-Linked Settlement": (
                            "linked or reconciled to payment/charter"
                        ),
                        "Personal/Owner Inflow": (
                            "personal/owner/capital/loan markers"
                        ),
                        "Processor Settlement": (
                            "Square/card settlement markers"
                        ),
                        "Unknown Inflow": (
                            "No reliable classification rule hit"
                        ),
                    }.get(class_name, "Heuristic")
                    data["rows"].append(
                        (class_name, count_v, amt_v, rule)
                    )

                    data["totals"]["total_count"] += count_v
                    data["totals"]["total_amount"] += amt_v
                    if class_name == "Unknown Inflow":
                        data["totals"]["unknown_count"] += count_v
                        data["totals"]["unknown_amount"] += amt_v
                    elif class_name == "Inter-Account Transfer":
                        data["totals"]["transfer_count"] += count_v
                        data["totals"]["transfer_amount"] += amt_v
                    elif class_name == "Charter-Linked Settlement":
                        data["totals"]["charter_count"] += count_v
                        data["totals"]["charter_amount"] += amt_v

                cur.execute(
                    """
                    WITH classified AS (
                        SELECT
                            transaction_date,
                            description,
                            category,
                            COALESCE(credit_amount, 0) AS amount,
                            CASE
                                WHEN COALESCE(is_transfer, FALSE)
                                     OR LOWER(COALESCE(category, ''))
                                        LIKE '%%transfer%%'
                                     OR LOWER(COALESCE(description, '')) ~
                                        '(transfer|xfer|interac transfer)'
                                    THEN 'Inter-Account Transfer'
                                WHEN reconciled_payment_id IS NOT NULL
                                     OR reconciled_charter_id IS NOT NULL
                                     OR LOWER(
                                         COALESCE(reconciliation_status, '')
                                     )
                                        IN ('reconciled', 'matched', 'linked')
                                    THEN 'Charter-Linked Settlement'
                                WHEN LOWER(COALESCE(business_personal, ''))
                                     LIKE '%%personal%%'
                                     OR LOWER(COALESCE(description, '')) ~
                                        '(owner|shareholder|capital|'
                                        'contribution|loan advance)'
                                    THEN 'Personal/Owner Inflow'
                                WHEN LOWER(COALESCE(description, '')) ~
                                      '(square|global|vcard|mcard|acard|'
                                      'card deposit|merchant)'
                                    THEN 'Processor Settlement'
                                ELSE 'Unknown Inflow'
                            END AS class_name
                        FROM banking_transactions
                        WHERE EXTRACT(YEAR FROM transaction_date) = %s
                          AND COALESCE(credit_amount, 0) > 0
                    )
                    SELECT
                        transaction_date,
                        COALESCE(description, ''),
                        amount,
                        COALESCE(category, '')
                    FROM classified
                    WHERE class_name = 'Unknown Inflow'
                    ORDER BY amount DESC, transaction_date DESC
                    LIMIT 40
                    """,
                    (year,),
                )
                data["unknown_samples"] = cur.fetchall()
        except Exception as exc:
            logger.error(
                f"Failed loading banking classification data: {exc}"
            )
            raise

        return data

    def _fetch_t2_readiness_data(
        self,
        year: int,
        dashboard_data: dict,
    ) -> dict:
        checks = []
        status_counts = {
            "PASS": 0,
            "WARN": 0,
            "FAIL": 0,
        }
        summary = {
            "income_ledger_rows": 0,
            "income_ledger_amount": Decimal("0"),
            "charter_payment_rows": dashboard_data.get("charter_count", 0),
            "charter_payment_amount": Decimal(str(
                dashboard_data.get("charter_revenue", 0)
            )),
            "risk_count": 0,
        }

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
                    FROM income_ledger
                    WHERE fiscal_year = %s
                      AND source_system = 'charter_payments'
                    """,
                    (year,),
                )
                row = cur.fetchone() or (0, 0)
                summary["income_ledger_rows"] = int(row[0] or 0)
                summary["income_ledger_amount"] = Decimal(str(row[1] or 0))
        except Exception as exc:
            logger.error(f"Failed T2 readiness fetch: {exc}")

        cp_rows = int(summary["charter_payment_rows"])
        cp_amt = summary["charter_payment_amount"]
        il_rows = int(summary["income_ledger_rows"])
        il_amt = summary["income_ledger_amount"]

        checks.append((
            "Charter cash rows present",
            self._status_level(cp_rows > 0),
            f"charter_payments rows={cp_rows:,}",
            "Open Reports",
        ))

        checks.append((
            "Income ledger backfilled",
            self._status_level(il_rows > 0, warn=True),
            f"income_ledger rows={il_rows:,} (source_system=charter_payments)",
            "Open Tax",
        ))

        delta = abs(float(cp_amt - il_amt)) if il_rows > 0 else float(cp_amt)
        delta_ok = delta < 1.0
        checks.append((
            "Revenue ledger vs cash variance",
            self._status_level(delta_ok, warn=True),
            (
                f"delta={self._money(delta)} "
                f"(cash={self._money(cp_amt)}, "
                f"ledger={self._money(il_amt)})"
            ),
            "Open Tax",
        ))

        missing_gl = int(dashboard_data.get("missing_gl", 0))
        checks.append((
            "Business receipts have GL coding",
            self._status_level(missing_gl == 0, warn=True),
            f"missing_gl={missing_gl:,}",
            "Open Receipts",
        ))

        risky_receipts = int(dashboard_data.get("risky_receipts", 0))
        checks.append((
            "Risk wording in expense stream",
            self._status_level(risky_receipts == 0, warn=True),
            f"keyword_hits={risky_receipts:,}",
            "Open Tax",
        ))

        unmatched_square = int(dashboard_data.get("square_unmatched", 0))
        checks.append((
            "Unmatched Square cash",
            self._status_level(unmatched_square == 0, warn=True),
            f"unmatched_square={unmatched_square:,}",
            "Open Reports",
        ))

        unlinked_cash = int(dashboard_data.get("unlinked_payments", 0))
        checks.append((
            "Unlinked charter cash rows",
            self._status_level(unlinked_cash == 0, warn=True),
            f"unlinked_cash={unlinked_cash:,}",
            "Open Reports",
        ))

        for _, status, _, _ in checks:
            status_counts[status] += 1

        summary["risk_count"] = status_counts["WARN"] + status_counts["FAIL"]
        return {
            "checks": checks,
            "status_counts": status_counts,
            "summary": summary,
        }

    def _fetch_payroll_close_data(self, year: int) -> dict:
        data = {
            "payroll": {
                "gross": 0.0,
                "cpp": 0.0,
                "ei": 0.0,
                "tax": 0.0,
                "rows": 0,
            },
            "t4": {
                "gross": 0.0,
                "cpp": 0.0,
                "ei": 0.0,
                "tax": 0.0,
                "rows": 0,
            },
            "remit": {
                "due": 0.0,
                "paid": 0.0,
                "open_months": 0,
                "reconciled_months": 0,
                "pd7a_missing": 0,
            },
            "checks": [],
        }

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*),
                        COALESCE(SUM(epm.gross_pay), 0),
                        COALESCE(SUM(epm.cpp_employee), 0),
                        COALESCE(SUM(epm.ei_employee), 0),
                        COALESCE(SUM(epm.federal_tax + epm.provincial_tax), 0)
                    FROM employee_pay_master epm
                    JOIN pay_periods pp ON pp.pay_period_id = epm.pay_period_id
                    WHERE EXTRACT(YEAR FROM pp.pay_date) = %s
                    """,
                    (year,),
                )
                row = cur.fetchone() or (0, 0, 0, 0, 0)
                data["payroll"] = {
                    "rows": int(row[0] or 0),
                    "gross": float(row[1] or 0),
                    "cpp": float(row[2] or 0),
                    "ei": float(row[3] or 0),
                    "tax": float(row[4] or 0),
                }

                cur.execute(
                    """
                    SELECT
                        COUNT(*),
                        COALESCE(SUM(box_14_employment_income), 0),
                        COALESCE(SUM(box_16_cpp_contributions), 0),
                        COALESCE(SUM(box_18_ei_premiums), 0),
                        COALESCE(SUM(box_22_income_tax), 0)
                    FROM employee_t4_records
                    WHERE tax_year = %s
                    """,
                    (year,),
                )
                row = cur.fetchone() or (0, 0, 0, 0, 0)
                data["t4"] = {
                    "rows": int(row[0] or 0),
                    "gross": float(row[1] or 0),
                    "cpp": float(row[2] or 0),
                    "ei": float(row[3] or 0),
                    "tax": float(row[4] or 0),
                }

                cur.execute(
                    """
                    SELECT
                        COALESCE(SUM(calculated_total_remittance), 0),
                        COALESCE(SUM(payment_amount), 0),
                        COUNT(*) FILTER (
                            WHERE COALESCE(
                                calculated_total_remittance,
                                0
                            ) > 0
                              AND COALESCE(reconciled, FALSE) = FALSE
                        ),
                        COUNT(*) FILTER (
                            WHERE COALESCE(reconciled, FALSE) = TRUE
                        ),
                        COUNT(*) FILTER (
                            WHERE COALESCE(calculated_total_remittance, 0) > 0
                              AND COALESCE(pd7a_statement_amount, 0) = 0
                        )
                    FROM payroll_remittances
                    WHERE fiscal_year = %s
                    """,
                    (year,),
                )
                row = cur.fetchone() or (0, 0, 0, 0, 0)
                data["remit"] = {
                    "due": float(row[0] or 0),
                    "paid": float(row[1] or 0),
                    "open_months": int(row[2] or 0),
                    "reconciled_months": int(row[3] or 0),
                    "pd7a_missing": int(row[4] or 0),
                }
        except Exception as exc:
            logger.error(f"Failed payroll close data fetch: {exc}")

        p = data["payroll"]
        t = data["t4"]
        r = data["remit"]

        gross_var = abs(p["gross"] - t["gross"])
        cpp_var = abs(p["cpp"] - t["cpp"])
        ei_var = abs(p["ei"] - t["ei"])
        tax_var = abs(p["tax"] - t["tax"])
        remit_var = abs(r["due"] - r["paid"])

        data["checks"] = [
            (
                "Payroll source rows present",
                self._status_level(p["rows"] > 0),
                f"employee_pay_master rows={p['rows']:,}",
                "Open Payroll",
            ),
            (
                "T4 rows present",
                self._status_level(t["rows"] > 0, warn=True),
                f"employee_t4_records rows={t['rows']:,}",
                "Open Tax",
            ),
            (
                "T4 gross matches payroll gross",
                self._status_level(gross_var < 1.0, warn=True),
                f"variance={self._money(gross_var)}",
                "Open Tax",
            ),
            (
                "CPP/EI/Tax totals aligned",
                self._status_level(
                    cpp_var < 1.0 and ei_var < 1.0 and tax_var < 1.0,
                    warn=True,
                ),
                (
                    f"CPP {self._money(cpp_var)} | "
                    f"EI {self._money(ei_var)} | "
                    f"TAX {self._money(tax_var)}"
                ),
                "Open Tax",
            ),
            (
                "Remittance paid vs due",
                self._status_level(remit_var < 1.0, warn=True),
                (
                    f"due={self._money(r['due'])} "
                    f"paid={self._money(r['paid'])} "
                    f"var={self._money(remit_var)}"
                ),
                "Open Remittances",
            ),
            (
                "PD7A statements entered",
                self._status_level(r["pd7a_missing"] == 0, warn=True),
                f"months_missing_pd7a={r['pd7a_missing']:,}",
                "Open Remittances",
            ),
            (
                "Remittance months reconciled",
                self._status_level(r["open_months"] == 0, warn=True),
                (
                    f"open_months={r['open_months']:,}, "
                    f"reconciled_months={r['reconciled_months']:,}"
                ),
                "Open Remittances",
            ),
        ]
        return data

    def _fetch_dashboard_data(self, year: int) -> dict:
        data = {
            "charter_revenue": Decimal("0"),
            "charter_count": 0,
            "linked_payments": 0,
            "unlinked_payments": 0,
            "unlinked_payment_amount": Decimal("0"),
            "square_unmatched": 0,
            "square_unmatched_amount": Decimal("0"),
            "business_receipts": 0,
            "business_receipt_amount": Decimal("0"),
            "excluded_receipts": 0,
            "excluded_receipt_amount": Decimal("0"),
            "missing_gl": 0,
            "risky_receipts": 0,
            "reconciled_months": 0,
            "open_months": 0,
            "total_flag_count": 0,
            "warnings": [],
        }

        def _row_value(row, index, default=0) -> object:
            """Read row[index] with a safe default fallback."""
            if row is None:
                return default
            try:
                return row[index]
            except Exception:
                return default

        receipt_cols = self._get_columns("receipts")
        has_exclude = "exclude_from_reports" in receipt_cols
        has_personal = "is_personal_purchase" in receipt_cols
        has_owner_personal_amount = (
            "owner_personal_amount" in receipt_cols
        )
        has_business_personal = "business_personal" in receipt_cols

        excluded_expr = []
        if has_exclude:
            excluded_expr.append("COALESCE(exclude_from_reports, FALSE)")
        if has_personal:
            excluded_expr.append("COALESCE(is_personal_purchase, FALSE)")
        if has_owner_personal_amount:
            excluded_expr.append("COALESCE(owner_personal_amount, 0) > 0")
        if has_business_personal:
            excluded_expr.append(
                "LOWER(COALESCE(business_personal, '')) LIKE '%%personal%%'"
            )

        excluded_sql = " OR ".join(excluded_expr) if excluded_expr else "FALSE"

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*),
                        COALESCE(SUM(amount), 0),
                        COUNT(*) FILTER (
                            WHERE COALESCE(
                                NULLIF(TRIM(charter_id::text), ''),
                                ''
                            ) <> ''
                        ),
                        COUNT(*) FILTER (
                            WHERE COALESCE(
                                NULLIF(TRIM(charter_id::text), ''),
                                ''
                            ) = ''
                        ),
                        COALESCE(
                            SUM(
                                CASE
                                    WHEN COALESCE(
                                        NULLIF(TRIM(charter_id::text), ''),
                                        ''
                                    ) = ''
                                    THEN amount
                                    ELSE 0
                                END
                            ),
                            0
                        )
                    FROM charter_payments
                    WHERE EXTRACT(YEAR FROM payment_date) = %s
                    """,
                    (year,),
                )
                row = cur.fetchone() or (0, 0, 0, 0, 0)
                data["charter_count"] = int(_row_value(row, 0, 0) or 0)
                data["charter_revenue"] = Decimal(
                    str(_row_value(row, 1, 0) or 0))
                data["linked_payments"] = int(_row_value(row, 2, 0) or 0)
                data["unlinked_payments"] = int(_row_value(row, 3, 0) or 0)
                data["unlinked_payment_amount"] = Decimal(
                    str(_row_value(row, 4, 0) or 0)
                )

                cur.execute(
                    """
                    SELECT COUNT(*), COALESCE(SUM(amount), 0)
                    FROM charter_payments
                    WHERE source = 'SQUARE_UNMATCHED'
                      AND charter_id IS NULL
                      AND EXTRACT(YEAR FROM payment_date) = %s
                    """,
                    (year,),
                )
                row = cur.fetchone() or (0, 0)
                data["square_unmatched"] = int(_row_value(row, 0, 0) or 0)
                data["square_unmatched_amount"] = Decimal(
                    str(_row_value(row, 1, 0) or 0)
                )

                cur.execute(
                    f"""
                    SELECT
                        COUNT(*) FILTER (WHERE NOT ({excluded_sql})),
                        COALESCE(
                            SUM(
                                CASE
                                    WHEN NOT ({excluded_sql})
                                    THEN gross_amount
                                    ELSE 0
                                END
                            ),
                            0
                        ),
                        COUNT(*) FILTER (WHERE ({excluded_sql})),
                        COALESCE(
                            SUM(
                                CASE
                                    WHEN ({excluded_sql})
                                    THEN gross_amount
                                    ELSE 0
                                END
                            ),
                            0
                        ),
                        COUNT(*) FILTER (
                            WHERE COALESCE(
                                NULLIF(TRIM(gl_account_code), ''),
                                ''
                            ) = ''
                               OR LOWER(COALESCE(gl_account_code, ''))
                                  IN ('n/a', 'na', 'unassigned')
                        ),
                        COUNT(*) FILTER (
                            WHERE (
                                COALESCE(vendor_name, '')
                                || ' '
                                || COALESCE(description, '')
                            ) ~* (
                                'director|shareholder|loan|personal|'
                                'owner[ ]*draw'
                            )
                        )
                    FROM receipts
                    WHERE EXTRACT(YEAR FROM receipt_date) = %s
                    """,
                    (year,),
                )
                row = cur.fetchone() or (0, 0, 0, 0, 0, 0)
                data["business_receipts"] = int(_row_value(row, 0, 0) or 0)
                data["business_receipt_amount"] = Decimal(
                    str(_row_value(row, 1, 0) or 0)
                )
                data["excluded_receipts"] = int(_row_value(row, 2, 0) or 0)
                data["excluded_receipt_amount"] = Decimal(
                    str(_row_value(row, 3, 0) or 0)
                )
                data["missing_gl"] = int(_row_value(row, 4, 0) or 0)
                data["risky_receipts"] = int(_row_value(row, 5, 0) or 0)

                remittance_cols = self._get_columns("payroll_remittances")
                if remittance_cols:
                    cur.execute(
                        """
                        SELECT
                            COUNT(*) FILTER (
                                WHERE COALESCE(reconciled, FALSE) = TRUE
                            ),
                            COUNT(*) FILTER (
                                WHERE COALESCE(
                                    calculated_total_remittance,
                                    0
                                ) > 0
                                  AND COALESCE(reconciled, FALSE) = FALSE
                            )
                        FROM payroll_remittances
                        WHERE fiscal_year = %s
                        """,
                        (year,),
                    )
                    row = cur.fetchone() or (0, 0)
                    data["reconciled_months"] = int(_row_value(row, 0, 0) or 0)
                    data["open_months"] = int(_row_value(row, 1, 0) or 0)
        except Exception as exc:
            logger.error(
                f"Failed loading accounting hub data: {exc}"
            )
            raise

        warnings = []
        if data["unlinked_payments"]:
            warnings.append(
                (
                    "HIGH",
                    "Unlinked charter cash",
                    data["unlinked_payments"],
                    "Open Reports",
                )
            )
        if data["square_unmatched"]:
            warnings.append(
                (
                    "HIGH",
                    "Square unmatched cash",
                    data["square_unmatched"],
                    "Open Reports",
                )
            )
        if data["missing_gl"]:
            warnings.append(
                (
                    "MEDIUM",
                    "Receipts missing GL",
                    data["missing_gl"],
                    "Open Receipts",
                )
            )
        if data["risky_receipts"]:
            warnings.append(
                (
                    "MEDIUM",
                    "Risk wording in receipts",
                    data["risky_receipts"],
                    "Open Tax",
                )
            )
        if data["open_months"]:
            warnings.append(
                (
                    "HIGH",
                    "Open CRA remittance months",
                    data["open_months"],
                    "Open Remittances",
                )
            )

        data["warnings"] = warnings
        data["total_flag_count"] = sum(int(item[2]) for item in warnings)
        return data

    def refresh_dashboard(self) -> None:
        year = int(self.year_spin.value())
        if self._sequence_loaded_year != year:
            self._load_sequence_state(year)
        try:
            data = self._fetch_dashboard_data(year)
        except Exception as exc:
            self._set_status(
                f"Failed loading accounting hub: {exc}", error=True)
            return

        self.card_revenue.set_metric(
            self._money(data["charter_revenue"]),
            (
                "Cash actually received from charter payments. "
                "Not bank deposits. Not raw bookings."
            ),
        )
        self.card_payments.set_metric(
            f"{data['charter_count']:,}",
            (
                f"Linked {data['linked_payments']:,} | "
                f"Unlinked {data['unlinked_payments']:,}"
            ),
        )
        self.card_expenses.set_metric(
            self._money(data["business_receipt_amount"]),
            (
                f"Business receipts {data['business_receipts']:,} | "
                f"Excluded/personal {data['excluded_receipts']:,}"
            ),
        )
        self.card_flags.set_metric(
            f"{data['total_flag_count']:,}",
            (
                "Counts unresolved filing blockers and review items "
                "for the selected year."
            ),
        )

        self.chart_payments.set_data(
            [
                {
                    "label": "Linked",
                    "value": data["linked_payments"],
                    "color": "#16a34a",
                },
                {
                    "label": "Unlinked",
                    "value": data["unlinked_payments"],
                    "color": "#dc2626",
                },
            ],
            subtitle=(
                f"Unlinked amount: "
                f"{self._money(data['unlinked_payment_amount'])}"
            ),
        )
        self.chart_receipts.set_data(
            [
                {
                    "label": "Business",
                    "value": data["business_receipts"],
                    "color": "#2563eb",
                },
                {
                    "label": "Excluded",
                    "value": data["excluded_receipts"],
                    "color": "#f59e0b",
                },
                {
                    "label": "Missing GL",
                    "value": data["missing_gl"],
                    "color": "#7c3aed",
                },
            ],
            subtitle=(
                f"Risk wording hits: {data['risky_receipts']:,}"
            ),
        )
        remit_total = data["reconciled_months"] + data["open_months"]
        if remit_total == 0:
            self.chart_remit.set_data(
                [
                    {
                        "label": "No remittance rows",
                        "value": 1,
                        "color": "#94a3b8",
                    }
                ],
                subtitle=(
                    "Load or sync payroll remittance months to track "
                    "PD7A/source deduction closure."
                ),
            )
        else:
            self.chart_remit.set_data(
                [
                    {
                        "label": "Reconciled",
                        "value": data["reconciled_months"],
                        "color": "#16a34a",
                    },
                    {
                        "label": "Open",
                        "value": data["open_months"],
                        "color": "#dc2626",
                    },
                ],
                subtitle=(
                    "Payroll is separate from dispatch/HOS. "
                    "This chart only reflects remittance closure."
                ),
            )

        warnings_sorted = sorted(
            data["warnings"],
            key=lambda w: (
                self._priority_rank(w[0]),
                -int(w[2] or 0),
                str(w[1]).lower(),
            ),
        )
        self.warning_table.setRowCount(len(warnings_sorted))
        for row_idx, warning in enumerate(warnings_sorted):
            priority, area, count, action = warning
            priority_badge = {
                "HIGH": "[HIGH]",
                "MEDIUM": "[MED]",
                "LOW": "[LOW]",
            }.get(priority, priority)
            self.warning_table.setItem(
                row_idx,
                0,
                QTableWidgetItem(priority_badge),
            )
            self.warning_table.setItem(row_idx, 1, QTableWidgetItem(area))
            self.warning_table.setItem(
                row_idx,
                2,
                QTableWidgetItem(f"{count:,}"),
            )
            self.warning_table.setItem(
                row_idx,
                3,
                QTableWidgetItem(action),
            )
            if priority == "HIGH":
                for col in range(4):
                    item = self.warning_table.item(row_idx, col)
                    if item:
                        item.setForeground(QColor("#b91c1c"))
                        item.setBackground(QColor("#fef2f2"))
            elif priority == "MEDIUM":
                for col in range(4):
                    item = self.warning_table.item(row_idx, col)
                    if item:
                        item.setBackground(QColor("#fffbeb"))

        self.notes_label.setText(
            "\n".join(
                [
                    (
                        "1. Charter cash is revenue. Bank deposits are "
                        "evidence and classification work, not automatic "
                        "revenue."
                    ),
                    (
                        "2. Payroll, PD7A, and T4 closure are separate "
                        "from charter dispatch and HOS data."
                    ),
                    (
                        "3. Business expenses can support T2 and ITC only "
                        "after personal, owner, loan, and unsupported "
                        "rows are stripped out."
                    ),
                    (
                        "4. Merchant fee reality matters: processor net "
                        "deposits are not the same thing as client gross "
                        "payments."
                    ),
                    (
                        "5. Filing years should be rebuilt from controlled "
                        "ledgers and exception lists, not trusted imported "
                        "journals alone."
                    ),
                ]
            )
        )

        self.warning_table.resizeColumnsToContents()

        # 1) Mixed banking classification panel
        banking_data = self._fetch_banking_classification_data(year)
        rows = sorted(
            banking_data["rows"],
            key=lambda r: (
                0 if r[0] == "Unknown Inflow" else 1,
                0 if r[0] == "Charter-Linked Settlement" else 1,
                -float(r[2] or 0),
            ),
        )
        self.banking_table.setRowCount(len(rows))
        for idx, (class_name, count_v, amt_v, rule) in enumerate(rows):
            self.banking_table.setItem(idx, 0, QTableWidgetItem(class_name))
            self.banking_table.setItem(
                idx, 1, QTableWidgetItem(f"{count_v:,}"))
            self.banking_table.setItem(
                idx, 2, QTableWidgetItem(self._money(amt_v)))
            self.banking_table.setItem(idx, 3, QTableWidgetItem(rule))
            if class_name == "Unknown Inflow":
                for col in range(4):
                    item = self.banking_table.item(idx, col)
                    if item:
                        item.setForeground(QColor("#b91c1c"))
                        item.setBackground(QColor("#fef2f2"))

        samples = banking_data["unknown_samples"]
        self.banking_unknown_table.setRowCount(len(samples))
        for idx, row in enumerate(samples):
            dt, desc, amt, category = row
            self.banking_unknown_table.setItem(
                idx,
                0,
                QTableWidgetItem(str(dt or "")),
            )
            self.banking_unknown_table.setItem(
                idx,
                1,
                QTableWidgetItem(str(desc or "")),
            )
            self.banking_unknown_table.setItem(
                idx,
                2,
                QTableWidgetItem(self._money(amt)),
            )
            self.banking_unknown_table.setItem(
                idx,
                3,
                QTableWidgetItem(str(category or "")),
            )

        t = banking_data["totals"]
        self.bank_total_card.set_metric(
            f"{t['total_count']:,}",
            f"{self._money(t['total_amount'])} inflow total",
        )
        self.bank_unknown_card.set_metric(
            f"{t['unknown_count']:,}",
            f"{self._money(t['unknown_amount'])} needs review",
        )
        self.bank_transfer_card.set_metric(
            f"{t['transfer_count']:,}",
            f"{self._money(t['transfer_amount'])} transfer tagged",
        )
        self.bank_charter_card.set_metric(
            f"{t['charter_count']:,}",
            f"{self._money(t['charter_amount'])} linked to charter cash",
        )
        self.banking_chart.set_data(
            [
                {
                    "label": "Charter-Linked",
                    "value": t["charter_count"],
                    "color": "#16a34a",
                },
                {
                    "label": "Processor",
                    "value": next(
                        (
                            x[1]
                            for x in rows
                            if x[0] == "Processor Settlement"
                        ),
                        0,
                    ),
                    "color": "#2563eb",
                },
                {
                    "label": "Transfers",
                    "value": t["transfer_count"],
                    "color": "#f59e0b",
                },
                {
                    "label": "Personal/Owner",
                    "value": next(
                        (
                            x[1]
                            for x in rows
                            if x[0] == "Personal/Owner Inflow"
                        ),
                        0,
                    ),
                    "color": "#7c3aed",
                },
                {
                    "label": "Unknown",
                    "value": t["unknown_count"],
                    "color": "#dc2626",
                },
            ],
            subtitle=(
                "Unknown inflows are fix-now items before filing support "
                "packages are finalized."
            ),
        )

        # 2) T2 readiness panel
        t2 = self._fetch_t2_readiness_data(year, data)
        self._populate_check_table(self.t2_table, t2["checks"])
        status_counts = t2["status_counts"]
        overall = (
            "PASS"
            if status_counts["FAIL"] == 0 and status_counts["WARN"] == 0
            else (
                "WARN"
                if status_counts["FAIL"] == 0
                else "FAIL"
            )
        )
        self.t2_status_card.set_metric(
            overall,
            (
                f"PASS {status_counts['PASS']} | "
                f"WARN {status_counts['WARN']} | "
                f"FAIL {status_counts['FAIL']}"
            ),
        )
        self.t2_revenue_card.set_metric(
            self._money(t2["summary"]["charter_payment_amount"]),
            (
                f"cash rows {t2['summary']['charter_payment_rows']:,} | "
                f"income_ledger rows "
                f"{t2['summary']['income_ledger_rows']:,}"
            ),
        )
        self.t2_receipt_card.set_metric(
            f"{data['business_receipts']:,}",
            (
                "business receipts | "
                f"missing GL {data['missing_gl']:,}"
            ),
        )
        self.t2_risk_card.set_metric(
            f"{t2['summary']['risk_count']:,}",
            (
                f"risk buckets: square {data['square_unmatched']:,}, "
                f"unlinked cash {data['unlinked_payments']:,}"
            ),
        )

        # 3) Payroll close panel
        payroll = self._fetch_payroll_close_data(year)
        self._populate_check_table(self.payroll_table, payroll["checks"])
        p = payroll["payroll"]
        t4 = payroll["t4"]
        rmt = payroll["remit"]
        self.payroll_total_card.set_metric(
            self._money(p["gross"]),
            f"rows {p['rows']:,}",
        )
        self.payroll_t4_card.set_metric(
            self._money(t4["gross"]),
            f"T4 rows {t4['rows']:,}",
        )
        self.payroll_remit_card.set_metric(
            self._money(rmt["due"]),
            f"paid {self._money(rmt['paid'])}",
        )
        close_variance = (
            abs(p["gross"] - t4["gross"])
            + abs(rmt["due"] - rmt["paid"])
        )
        self.payroll_var_card.set_metric(
            self._money(close_variance),
            (
                f"open months {rmt['open_months']:,} | "
                f"PD7A missing {rmt['pd7a_missing']:,}"
            ),
        )

        self._latest_snapshot = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "year": year,
            "dashboard": data,
            "banking": banking_data,
            "t2": t2,
            "payroll": payroll,
            "sequence": {
                "title": self._sequence_title,
                "actions": self._sequence_actions,
                "status": self._sequence_status,
                "index": self._sequence_index,
            },
        }

        self._set_status(f"Accounting hub loaded for {year}.")
