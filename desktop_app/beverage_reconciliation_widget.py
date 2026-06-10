"""
Beverage Reconciliation Report
================================
Compares beverage charges billed on charters (revenue) against beverage
purchase
receipts recorded under GL 5116 / GL 5310 (cost).

Period selectors: All Time / By Year / By Month (calendar-style) / By Week
(calendar).

Summary shows net margin in GREEN (profitable) or RED (over-spent).
"""

from __future__ import annotations

import calendar as _calendar
import logging
from datetime import date
from decimal import Decimal

from db_error_handling import DatabaseContext
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCalendarWidget,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# GL codes that represent beverage costs (purchases / supplies)
BEV_COST_GL = ("5116", "5310")
GST_RATE = Decimal("0.05")

MONTHS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]

YEAR_MIN = 2009
YEAR_MAX = 2026


# ─────────────────────────────────────────────────────────────────────────────
# KPI card widget
# ─────────────────────────────────────────────────────────────────────────────


class _KpiCard(QFrame):
    """A simple boxed card showing a label + large dollar value."""

    COLOR_GREEN = "#27ae60"
    COLOR_RED = "#e74c3c"
    COLOR_ORANGE = "#e67e22"
    COLOR_BLUE = "#2980b9"
    COLOR_GREY = "#7f8c8d"

    def __init__(
        self, label: str, default_color: str = COLOR_GREY, parent=None
    ) -> None:
        super().__init__(parent)
        self._default_color = default_color
        self.setFrameShape(QFrame.Shape.Box)
        self.setLineWidth(2)
        self.setMinimumWidth(165)
        self.setMaximumWidth(220)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        self.setStyleSheet(
            "QFrame { border-radius: 6px; background: #f9f9f9; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(4)

        lbl_font = QFont()
        lbl_font.setPointSize(9)
        self._lbl = QLabel(label)
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl.setFont(lbl_font)
        self._lbl.setStyleSheet(
            "color: #444; border: none; background: transparent;"
        )
        self._lbl.setWordWrap(True)
        layout.addWidget(self._lbl)

        val_font = QFont()
        val_font.setPointSize(15)
        val_font.setBold(True)
        self._val = QLabel("—")
        self._val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._val.setFont(val_font)
        self._val.setStyleSheet(
            f"color: {self._default_color}; border: none; background:"
            f"transparent;"
        )
        layout.addWidget(self._val)

        cnt_font = QFont()
        cnt_font.setPointSize(8)
        self._cnt = QLabel("")
        self._cnt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cnt.setFont(cnt_font)
        self._cnt.setStyleSheet(
            "color: #888; border: none; background: transparent;"
        )
        layout.addWidget(self._cnt)

    def set_value(
        self,
        amount: Decimal,
        count: int | None = None,
        color: str | None = None,
    ) -> None:
        text = (
            f"${float(amount):,.2f}"
            if amount >= 0
            else f"-${float(abs(amount)):,.2f}"
        )
        self._val.setText(text)
        c = color or self._default_color
        self._val.setStyleSheet(
            f"color: {c}; border: none; background: transparent;"
        )
        if count is not None:
            self._cnt.setText(f"{count:,} entries")
        else:
            self._cnt.clear()

    def set_highlight(self, color: str) -> None:
        """Change the outer border colour (used on the net card)."""
        self.setStyleSheet(
            f"QFrame {{ border: 3px solid {color}; border-radius: 6px;"
            f"background: #f9f9f9; }}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Main widget
# ─────────────────────────────────────────────────────────────────────────────


class BeverageReconciliationWidget(QWidget):
    """Beverage billing vs. receipt reconciliation report with period"
    "selector."""

    def __init__(self, conn) -> None:
        super().__init__()
        self.conn = conn
        self._selected_month: int = QDate.currentDate().month()
        self._init_ui()
        self._refresh()

    # ── UI construction ──────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Title
        # ----------------------------------------------------------------
        title = QLabel("🍾 Beverage Reconciliation Report")
        title.setFont(QFont("Arial", 17, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        sub = QLabel(
            "Compares beverage charges billed on charters  vs.  "
            "beverage purchase receipts ( GL 5116 · GL 5310 )"
        )
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color: #666; font-size: 11px;")
        root.addWidget(sub)

        # Period selector
        # ------------------------------------------------------
        period_box = QGroupBox("Select Period")
        period_box.setStyleSheet("QGroupBox { font-weight: bold; }")
        period_layout = QVBoxLayout(period_box)
        period_layout.setSpacing(8)

        # Radio buttons
        radio_row = QHBoxLayout()
        self._mode_group = QButtonGroup(self)
        mode_labels = [
            "🗓  All Time",
            "📅  By Year",
            "📆  By Month",
            "🗓  By Week",
        ]
        for i, lbl in enumerate(mode_labels):
            rb = QRadioButton(lbl)
            rb.setStyleSheet("font-size: 12px;")
            if i == 0:
                rb.setChecked(True)
            self._mode_group.addButton(rb, i)
            radio_row.addWidget(rb)
        radio_row.addStretch()
        period_layout.addLayout(radio_row)

        # Stacked controls (one page per mode)
        self._stacked = QStackedWidget()

        # Page 0 — All Time
        p0 = QWidget()
        p0l = QHBoxLayout(p0)
        p0l.setContentsMargins(4, 4, 4, 4)
        info = QLabel(
            "📊  Showing all beverage data across all years (2009 – present)."
        )
        info.setStyleSheet("font-size: 12px; color: #555;")
        p0l.addWidget(info)
        p0l.addStretch()
        self._stacked.addWidget(p0)

        # Page 1 — By Year
        p1 = QWidget()
        p1l = QHBoxLayout(p1)
        p1l.setContentsMargins(4, 4, 4, 4)
        p1l.addWidget(QLabel("Year:"))
        self._year_combo = QComboBox()
        self._year_combo.setFixedWidth(90)
        for yr in range(YEAR_MAX, YEAR_MIN - 1, -1):
            self._year_combo.addItem(str(yr))
        self._year_combo.setCurrentText(str(QDate.currentDate().year()))
        self._year_combo.currentIndexChanged.connect(self._refresh)
        p1l.addWidget(self._year_combo)
        p1l.addStretch()
        self._stacked.addWidget(p1)

        # Page 2 — By Month
        p2 = QWidget()
        p2l = QVBoxLayout(p2)
        p2l.setContentsMargins(4, 4, 4, 4)
        p2l.setSpacing(6)

        yr_row = QHBoxLayout()
        yr_row.addWidget(QLabel("Year:"))
        self._month_year_combo = QComboBox()
        self._month_year_combo.setFixedWidth(90)
        for yr in range(YEAR_MAX, YEAR_MIN - 1, -1):
            self._month_year_combo.addItem(str(yr))
        self._month_year_combo.setCurrentText(str(QDate.currentDate().year()))
        self._month_year_combo.currentIndexChanged.connect(self._refresh)
        yr_row.addWidget(self._month_year_combo)
        yr_row.addStretch()
        p2l.addLayout(yr_row)

        month_grid = QGridLayout()
        month_grid.setHorizontalSpacing(6)
        month_grid.setVerticalSpacing(4)
        self._month_btns: list[QPushButton] = []
        cur_month = QDate.currentDate().month()
        for i, m_name in enumerate(MONTHS):
            btn = QPushButton(m_name)
            btn.setCheckable(True)
            btn.setFixedSize(54, 28)
            btn.setStyleSheet(
                "QPushButton { font-size: 11px; border: 1px solid #bbb;"
                "border-radius: 3px; }"
                "QPushButton:checked { background: #2980b9; color: white;"
                "font-weight: bold; border: 2px solid #1a5276; }"
            )
            if i + 1 == cur_month:
                btn.setChecked(True)
            btn.clicked.connect(
                lambda _checked, idx=i + 1: self._on_month_btn(idx)
            )
            self._month_btns.append(btn)
            month_grid.addWidget(btn, i // 6, i % 6)
        p2l.addLayout(month_grid)
        self._stacked.addWidget(p2)

        # Page 3 — By Week  (inline QCalendarWidget)
        p3 = QWidget()
        p3l = QHBoxLayout(p3)
        p3l.setContentsMargins(4, 4, 4, 4)
        p3l.setSpacing(16)

        self._week_calendar = QCalendarWidget()
        self._week_calendar.setGridVisible(True)
        self._week_calendar.setNavigationBarVisible(True)
        self._week_calendar.setMaximumWidth(310)
        self._week_calendar.setMaximumHeight(200)
        self._week_calendar.setSelectedDate(QDate.currentDate())
        self._week_calendar.selectionChanged.connect(self._on_week_selected)
        p3l.addWidget(self._week_calendar)

        week_info = QWidget()
        week_info_l = QVBoxLayout(week_info)
        week_info_l.setContentsMargins(0, 8, 0, 0)
        lbl_title = QLabel("Selected week:")
        lbl_title.setStyleSheet(
            "font-weight: bold; color: #333; font-size: 12px;"
        )
        week_info_l.addWidget(lbl_title)
        self._week_range_label = QLabel()
        self._week_range_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #2c3e50;"
        )
        week_info_l.addWidget(self._week_range_label)
        week_info_l.addStretch()
        p3l.addWidget(week_info)
        p3l.addStretch()
        self._stacked.addWidget(p3)

        period_layout.addWidget(self._stacked)
        self._mode_group.idClicked.connect(self._on_mode_changed)
        root.addWidget(period_box)

        # KPI cards row
        # --------------------------------------------------------
        kpi_frame = QFrame()
        kpi_frame.setFrameShape(QFrame.Shape.NoFrame)
        kpi_row = QHBoxLayout(kpi_frame)
        kpi_row.setSpacing(10)
        kpi_row.setContentsMargins(0, 0, 0, 0)

        self._card_billed = _KpiCard(
            "Billed to Clients\n(ex. GST)", _KpiCard.COLOR_GREEN
        )
        self._card_gst = _KpiCard(
            "Est. GST 5%\n(on billed)", _KpiCard.COLOR_BLUE
        )
        self._card_total_billed = _KpiCard(
            "Total Billed\n(incl. GST)", _KpiCard.COLOR_GREEN
        )
        self._card_cost = _KpiCard(
            "Bev Receipts\n(Cost of Goods)", _KpiCard.COLOR_ORANGE
        )
        self._card_margin_pct = _KpiCard(
            "Margin %\n(ex. GST)", _KpiCard.COLOR_GREY
        )
        self._card_net = _KpiCard(
            "NET MARGIN\n(Billed − Cost)", _KpiCard.COLOR_GREY
        )

        for card in [
            self._card_billed,
            self._card_gst,
            self._card_total_billed,
            self._card_cost,
            self._card_margin_pct,
            self._card_net,
        ]:
            kpi_row.addWidget(card)
        kpi_row.addStretch()
        root.addWidget(kpi_frame)

        # Status / summary strip
        # -----------------------------------------------
        self._status_lbl = QLabel()
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setStyleSheet(
            "font-size: 13px; font-weight: bold; padding: 6px; "
            "border-radius: 4px; background: #ecf0f1;"
        )
        root.addWidget(self._status_lbl)

        # Detail tabs
        # ----------------------------------------------------------
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        # Tab 1: Charter Billing
        self._bill_table = QTableWidget()
        self._bill_table.setColumnCount(6)
        self._bill_table.setHorizontalHeaderLabels(
            [
                "Reserve #",
                "Date",
                "Client",
                "Bev Amount (ex GST)",
                "Est. GST (5%)",
                "Total (incl. GST)",
            ]
        )
        self._bill_table.verticalHeader().setVisible(False)
        self._bill_table.setAlternatingRowColors(True)
        self._bill_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._bill_table.horizontalHeader().setStretchLastSection(True)
        self._bill_table.setSortingEnabled(True)
        self._tabs.addTab(self._bill_table, "🧾 Charter Billing")

        # Tab 2: Receipts (costs)
        self._rcpt_table = QTableWidget()
        self._rcpt_table.setColumnCount(6)
        self._rcpt_table.setHorizontalHeaderLabels(
            ["Date", "Vendor", "GL Code", "GL Name", "Amount", "Description"]
        )
        self._rcpt_table.verticalHeader().setVisible(False)
        self._rcpt_table.setAlternatingRowColors(True)
        self._rcpt_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._rcpt_table.horizontalHeader().setStretchLastSection(True)
        self._rcpt_table.setSortingEnabled(True)
        self._tabs.addTab(self._rcpt_table, "📦 Beverage Receipts (Cost)")

        root.addWidget(self._tabs)

        # Initialise week label
        self._on_week_selected()

    # ── Slot handlers ────────────────────────────────────────────────────────

    def _on_mode_changed(self, mode_id: int) -> None:
        self._stacked.setCurrentIndex(mode_id)
        self._refresh()

    def _on_month_btn(self, month: int) -> None:
        for i, btn in enumerate(self._month_btns):
            btn.setChecked(i + 1 == month)
        self._selected_month = month
        self._refresh()

    def _on_week_selected(self) -> None:
        qd = self._week_calendar.selectedDate()
        dow = qd.dayOfWeek()  # 1 = Monday … 7 = Sunday
        week_start = qd.addDays(1 - dow)
        week_end = qd.addDays(7 - dow)
        self._week_range_label.setText(
            f"{week_start.toString('MMM dd, yyyy')}  — "
            f"{week_end.toString('MMM dd, yyyy')}"
        )
        if self._mode_group.checkedId() == 3:
            self._refresh()

    # ── Date-range helper
    # ─────────────────────────────────────────────────────

    def _get_date_range(self) -> tuple[date, date]:
        mode = self._mode_group.checkedId()

        if mode == 0:  # All Time
            return date(2007, 1, 1), date(2099, 12, 31)

        elif mode == 1:  # Year
            yr = int(self._year_combo.currentText())
            return date(yr, 1, 1), date(yr, 12, 31)

        elif mode == 2:  # Month
            yr = int(self._month_year_combo.currentText())
            m = self._selected_month
            last = _calendar.monthrange(yr, m)[1]
            return date(yr, m, 1), date(yr, m, last)

        else:  # Week
            qd = self._week_calendar.selectedDate()
            dow = qd.dayOfWeek()
            qs = qd.addDays(1 - dow)
            qe = qd.addDays(7 - dow)
            return (
                date(qs.year(), qs.month(), qs.day()),
                date(qe.year(), qe.month(), qe.day()),
            )

    # ── Main data refresh
    # ─────────────────────────────────────────────────────

    def _refresh(self) -> None:
        start_d, end_d = self._get_date_range()

        with DatabaseContext(self.conn, auto_commit=False) as cur:
            if cur is None:
                return

            # ── Billing: charter_charges (type='beverage') ─────────────────
            cur.execute(
                """
                SELECT
                    c.reserve_number,
                    c.charter_date,
                    c.client_display_name,
                    SUM(cc.amount)  AS bev_amount
                FROM charter_charges cc
                JOIN charters c ON c.charter_id = cc.charter_id
                WHERE cc.charge_type = 'beverage'
                  AND cc.amount > 0
                  AND c.charter_date BETWEEN %s AND %s
                  AND (c.cancelled IS NULL OR c.cancelled = FALSE)
                GROUP BY c.reserve_number, c.charter_date,
                c.client_display_name, c.charter_id
                ORDER BY c.charter_date DESC
                """,
                (start_d, end_d),
            )
            bill_rows = cur.fetchall()

            # ── Costs: receipts under GL 5116 / 5310 ──────────────────────
            cur.execute(
                """
                SELECT
                    r.receipt_date,
                    r.vendor_name,
                    r.gl_account_code,
                    r.gl_account_name,
                    r.gross_amount,
                    r.description
                FROM receipts r
                WHERE r.gl_account_code = ANY(%s)
                  AND r.receipt_date BETWEEN %s AND %s
                ORDER BY r.receipt_date DESC
                """,
                (list(BEV_COST_GL), start_d, end_d),
            )
            rcpt_rows = cur.fetchall()

        # ── Totals
        # ────────────────────────────────────────────────────────────
        total_billed = sum(Decimal(str(r[3])) for r in bill_rows)
        gst_est = (total_billed * GST_RATE).quantize(Decimal("0.01"))
        total_with_gst = total_billed + gst_est
        total_cost = sum(Decimal(str(r[4])) for r in rcpt_rows if r[4])
        net = total_billed - total_cost
        margin_pct_val = (
            (net / total_billed * 100) if total_billed else Decimal("0")
        )

        in_green = net >= 0

        # ── KPI cards
        # ─────────────────────────────────────────────────────────
        self._card_billed.set_value(
            total_billed, count=len(bill_rows), color=_KpiCard.COLOR_GREEN
        )
        self._card_gst.set_value(gst_est, color=_KpiCard.COLOR_BLUE)
        self._card_total_billed.set_value(
            total_with_gst, color=_KpiCard.COLOR_GREEN
        )
        self._card_cost.set_value(
            total_cost, count=len(rcpt_rows), color=_KpiCard.COLOR_ORANGE
        )

        margin_color = _KpiCard.COLOR_GREEN if in_green else _KpiCard.COLOR_RED
        self._card_margin_pct._val.setText(f"{float(margin_pct_val):.1f}%")
        self._card_margin_pct._val.setStyleSheet(
            f"color: {margin_color}; border: none; background: transparent;"
        )
        self._card_net.set_value(net, color=margin_color)
        self._card_net.set_highlight(margin_color)

        # ── Status strip ─────────────────────────────────────────────────────
        if start_d.year == 2007:
            period_str = "All Time"
        else:
            period_str = f"{start_d}  →  {end_d}"

        verdict = (
            "✅  IN THE GREEN — Revenue exceeds costs"
            if in_green
            else "🔴  IN THE RED — Costs exceed billed revenue"
        )
        self._status_lbl.setText(
            f"{verdict}   |   Period: {period_str}   |   "
            f"Billed: ${float(total_billed):,.2f}  ·  Cost:"
            f"${float(total_cost):,.2f}  ·  Net: ${float(net):,.2f}"
        )
        status_bg = "#d5f5e3" if in_green else "#fde8e8"
        status_fg = "#1a7a40" if in_green else "#c0392b"
        self._status_lbl.setStyleSheet(
            f"font-size: 13px; font-weight: bold; padding: 6px; "
            f"border-radius: 4px; background: {status_bg}; color: {status_fg};"
        )

        # ── Charter billing table
        # ─────────────────────────────────────────────
        self._bill_table.setSortingEnabled(False)
        self._bill_table.setRowCount(len(bill_rows))
        for row_i, (rn, dt, client, amt) in enumerate(bill_rows):
            bev = Decimal(str(amt))
            gst = (bev * GST_RATE).quantize(Decimal("0.01"))
            ttl = bev + gst
            cells = [
                (str(rn or ""), Qt.AlignmentFlag.AlignLeft),
                (str(dt), Qt.AlignmentFlag.AlignCenter),
                (str(client or ""), Qt.AlignmentFlag.AlignLeft),
                (f"${bev:,.2f}", Qt.AlignmentFlag.AlignRight),
                (f"${gst:,.2f}", Qt.AlignmentFlag.AlignRight),
                (f"${ttl:,.2f}", Qt.AlignmentFlag.AlignRight),
            ]
            for col, (text, align) in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                self._bill_table.setItem(row_i, col, item)
        self._bill_table.resizeColumnsToContents()
        self._bill_table.setSortingEnabled(True)
        self._tabs.setTabText(
            0, f"🧾 Charter Billing  ({len(bill_rows)} charters)"
        )

        # ── Receipts cost table
        # ───────────────────────────────────────────────
        self._rcpt_table.setSortingEnabled(False)
        self._rcpt_table.setRowCount(len(rcpt_rows))
        for row_i, (dt, vendor, gl_code, gl_name, amount, desc) in enumerate(
            rcpt_rows
        ):
            amt = Decimal(str(amount)) if amount else Decimal("0")
            cells = [
                (str(dt), Qt.AlignmentFlag.AlignCenter),
                (str(vendor or ""), Qt.AlignmentFlag.AlignLeft),
                (str(gl_code or ""), Qt.AlignmentFlag.AlignCenter),
                (str(gl_name or ""), Qt.AlignmentFlag.AlignLeft),
                (f"${amt:,.2f}", Qt.AlignmentFlag.AlignRight),
                (str(desc or ""), Qt.AlignmentFlag.AlignLeft),
            ]
            for col, (text, align) in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                # Highlight GL 5310 rows slightly
                if gl_code == "5310":
                    item.setBackground(QColor("#fff8e8"))
                self._rcpt_table.setItem(row_i, col, item)
        self._rcpt_table.resizeColumnsToContents()
        self._rcpt_table.setSortingEnabled(True)
        self._tabs.setTabText(
            1, f"📦 Beverage Receipts  ({len(rcpt_rows)} receipts)"
        )
