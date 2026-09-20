"""
Dispatcher Calendar Widget
- Calendar view for dispatchers with day drill-down
- Shows bookings/quotes/charters; color codes unassigned,
driver/vehicle unavailable
- Tasks: create/verify, warning templates (e.g., ensure client pays before run)
- Payment pre-check via reserve_number using payments table if present
- Schema-safe: only uses columns that exist (via information_schema)
- Outlook sync integration: Color-coded sync status with right-click menu
actions
"""

import logging
import os
import re
from datetime import datetime, time, timedelta

from db_error_handling import DatabaseContext
from psycopg2 import sql

logger = logging.getLogger(__name__)

from PyQt6.QtCore import QDate, Qt, pyqtSlot
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QCalendarWidget,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class DispatcherCalendarWidget(QWidget):
    def __init__(self, db) -> None:
        super().__init__()
        self.db = db
        self._ensure_storage()
        self._init_ui()
        self._load_day(QDate.currentDate())

    def _ensure_storage(self) -> None:
        """Create dispatch_tasks table in DB if it does not exist."""
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS dispatch_tasks (
                        task_id        SERIAL PRIMARY KEY,
                        reserve_number TEXT,
                        task_date      TEXT,
                        task_text      TEXT,
                        status         TEXT DEFAULT 'open',
                        created_at     TIMESTAMP DEFAULT NOW()
                    )
                """)
        except Exception as e:
            logger.error(f"dispatch_tasks table creation failed: {e}")

    def _init_ui(self) -> None:
        layout = QVBoxLayout()
        title = QLabel("🗓️ Charter Dispatch Calendar")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left calendar
        left = QWidget()
        left_layout = QVBoxLayout()
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.selectionChanged.connect(
            lambda: self._load_day(self.calendar.selectedDate())
        )
        self.calendar.clicked.connect(self._load_day)
        self.calendar.currentPageChanged.connect(
            lambda _year, _month: self._highlight_charter_dates()
        )
        left_layout.addWidget(self.calendar)

        todo_box = QGroupBox("Daily To-Do (Selected Date)")
        todo_layout = QVBoxLayout()
        self.todo_list = QListWidget()
        self.todo_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.todo_list.customContextMenuRequested.connect(
            self._show_todo_context_menu
        )
        todo_layout.addWidget(self.todo_list)

        todo_actions = QHBoxLayout()
        self.btn_add_selected_todo = QPushButton("➕ Add Selected To-Do")
        self.btn_complete_todo = QPushButton("✅ Complete Selected")
        self.btn_delete_todo = QPushButton("🗑️ Delete Selected")
        self.btn_post_todo_outlook = QPushButton("📌 Post To-Do to Outlook")
        self.btn_add_selected_todo.clicked.connect(self._add_selected_to_todo)
        self.btn_complete_todo.clicked.connect(self._verify_selected_task)
        self.btn_delete_todo.clicked.connect(self._delete_selected_task)
        self.btn_post_todo_outlook.clicked.connect(
            self._post_selected_todo_to_outlook_task
        )
        todo_actions.addWidget(self.btn_add_selected_todo)
        todo_actions.addWidget(self.btn_complete_todo)
        todo_actions.addWidget(self.btn_delete_todo)
        todo_actions.addWidget(self.btn_post_todo_outlook)
        todo_layout.addLayout(todo_actions)
        todo_box.setLayout(todo_layout)
        left_layout.addWidget(todo_box)

        main_todo_box = QGroupBox("Main To-Do (All Open)")
        main_todo_layout = QVBoxLayout()
        self.main_todo_list = QListWidget()
        self.main_todo_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.main_todo_list.customContextMenuRequested.connect(
            self._show_todo_context_menu
        )
        main_todo_layout.addWidget(self.main_todo_list)

        main_actions = QHBoxLayout()
        self.btn_main_complete = QPushButton("✅ Complete")
        self.btn_main_delete = QPushButton("🗑️ Delete")
        self.btn_main_post = QPushButton("📌 Post Outlook")
        self.btn_main_complete.clicked.connect(self._verify_selected_task)
        self.btn_main_delete.clicked.connect(self._delete_selected_task)
        self.btn_main_post.clicked.connect(self._post_selected_todo_to_outlook_task)
        main_actions.addWidget(self.btn_main_complete)
        main_actions.addWidget(self.btn_main_delete)
        main_actions.addWidget(self.btn_main_post)
        main_todo_layout.addLayout(main_actions)
        main_todo_box.setLayout(main_todo_layout)
        left_layout.addWidget(main_todo_box)

        # Load initial month's charter dates
        self._highlight_charter_dates()

        left.setLayout(left_layout)
        splitter.addWidget(left)

        # Right panel: day table + task pane
        right = QWidget()
        right_layout = QVBoxLayout()

        self.day_table = QTableWidget()
        self.day_table.setColumnCount(12)
        self.day_table.setHorizontalHeaderLabels(
            [
                "Reserve #",
                "Client",
                "Type",
                "Charter ID",
                "Pickup",
                "Do Time",
                "Depart Yard",
                "Vehicle",
                "Driver",
                "Status",
                "Outlook",
                "Alerts",
            ]
        )
        self.day_table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.day_table.customContextMenuRequested.connect(
            self._show_context_menu
        )
        self.day_table.cellDoubleClicked.connect(
            self._open_booking_from_calendar
        )
        right_layout.addWidget(self.day_table)

        actions_top = QHBoxLayout()
        actions_bottom = QHBoxLayout()
        actions_stack = QVBoxLayout()

        self.btn_create_task = QPushButton("➕ Create\nTask")
        self.btn_verify_task = QPushButton("✅ Complete\nTask")
        self.btn_prepayment = QPushButton("⚠️ Check\nPayment")
        self.btn_sync_parse = QPushButton("⬇️ Compare\nArrow to ALMS")
        self.btn_update_calendar = QPushButton(
            f"🔄 Sync\nArrow Calendar\n({self._calendar_sync_scope_label()})"
        )
        self.btn_post_arrow_new = QPushButton("📤 Post to\nArrow Calendar")
        self.btn_post_outlook_task = QPushButton("📌 Post\nArrow Task")
        self.btn_add_and_post_task = QPushButton("⚡ To-Do +\nOutlook Task")
        self.btn_add_and_post_all = QPushButton("🚀 To-Do + Task\n+ Arrow Calendar")
        self.combo_combined_mode = QComboBox()
        self.combo_combined_mode.addItem(
            "To-Do + Task",
            "TODO_TASK",
        )
        self.combo_combined_mode.addItem(
            "To-Do + Arrow",
            "TODO_ARROW",
        )
        self.combo_combined_mode.addItem(
            "To-Do + Task + Arrow",
            "TODO_TASK_ARROW",
        )
        self.btn_run_combined_mode = QPushButton("▶ Run\nSelected")

        for _btn in (
            self.btn_create_task,
            self.btn_verify_task,
            self.btn_prepayment,
            self.btn_sync_parse,
            self.btn_update_calendar,
            self.btn_post_arrow_new,
            self.btn_post_outlook_task,
            self.btn_add_and_post_task,
            self.btn_add_and_post_all,
            self.btn_run_combined_mode,
        ):
            _btn.setMinimumWidth(110)
            _btn.setMinimumHeight(56)

        self.btn_create_task.setToolTip(
            "Create a dispatch task from selected charter row.\n"
            "Adds item to daily and main to-do lists."
        )
        self.btn_verify_task.setToolTip(
            "Mark the selected task as done.\n"
            "Completed tasks are removed from open list."
        )
        self.btn_prepayment.setToolTip(
            "Validate payment status before dispatch.\n"
            "Use for pre-run payment checks."
        )
        self.btn_sync_parse.setToolTip(
            "Compare Arrow calendar events against ALMS bookings.\n"
            "Use after edits or external calendar changes."
        )
        self.btn_update_calendar.setToolTip(
            "Review and apply selected charter updates to Arrow Calendar.\n"
            f"Forward scope: {self._calendar_sync_scope_label()}.\n"
            "Approvals are handled one event at a time."
        )
        self.btn_post_arrow_new.setToolTip(
            "Post selected charter row to Arrow Calendar.\n"
            "Creates/updates matching calendar entry."
        )
        self.btn_post_outlook_task.setToolTip(
            "Create Arrow task from selected charter row.\n"
            "Useful for reminders and follow-ups."
        )
        self.btn_add_and_post_task.setToolTip(
            "Add selected row to To-Do and post Outlook task.\n"
            "Two-step action in one click."
        )
        self.btn_add_and_post_all.setToolTip(
            "Add To-Do, post Outlook task, and post Arrow Calendar.\n"
            "Full combined action for selected row."
        )
        self.btn_run_combined_mode.setToolTip(
            "Run currently selected combined mode for chosen rows.\n"
            "Mode is selected in the adjacent dropdown."
        )
        self.btn_create_task.clicked.connect(self._create_task)
        self.btn_verify_task.clicked.connect(self._verify_selected_task)
        self.btn_prepayment.clicked.connect(self._prepayment_check_selected)
        self.btn_sync_parse.clicked.connect(self._parse_outlook_and_review)
        self.btn_update_calendar.clicked.connect(
            self._update_calendar_individual_approval
        )
        self.btn_post_arrow_new.clicked.connect(
            self._post_selected_row_to_outlook
        )
        self.btn_post_outlook_task.clicked.connect(
            self._post_selected_row_to_outlook_task
        )
        self.btn_add_and_post_task.clicked.connect(
            self._add_selected_to_todo_and_post_outlook_task
        )
        self.btn_add_and_post_all.clicked.connect(
            self._add_selected_to_todo_post_task_and_calendar
        )
        self.btn_run_combined_mode.clicked.connect(
            self._run_selected_combined_action
        )
        actions_top.addWidget(self.btn_create_task)
        actions_top.addWidget(self.btn_verify_task)
        actions_top.addWidget(self.btn_prepayment)
        actions_top.addWidget(self.btn_sync_parse)
        actions_top.addWidget(self.btn_update_calendar)
        actions_top.addWidget(self.btn_post_arrow_new)

        actions_bottom.addWidget(self.btn_post_outlook_task)
        actions_bottom.addWidget(self.btn_add_and_post_task)
        actions_bottom.addWidget(self.btn_add_and_post_all)
        actions_bottom.addWidget(self.combo_combined_mode)
        actions_bottom.addWidget(self.btn_run_combined_mode)

        actions_stack.addLayout(actions_top)
        actions_stack.addLayout(actions_bottom)
        right_layout.addLayout(actions_stack)

        box = QGroupBox("Tasks for Selected Date")
        box_layout = QVBoxLayout()
        self.task_list = QListWidget()
        self.task_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.task_list.customContextMenuRequested.connect(
            self._show_todo_context_menu
        )
        box_layout.addWidget(self.task_list)
        box.setLayout(box_layout)
        right_layout.addWidget(box)

        right.setLayout(right_layout)

        # ── Tab widget: Day View + Sync Review ────────────────────────────────
        self.right_tabs = QTabWidget()
        self.right_tabs.addTab(right, "📅 Day View")
        self.right_tabs.addTab(self._build_sync_review_tab(), "🔄 Sync Review")
        splitter.addWidget(self.right_tabs)

        splitter.setSizes([400, 600])
        layout.addWidget(splitter)
        self.setLayout(layout)

        # Populate the review tab badge after UI is built
        self._refresh_sync_review_badge()

    def _build_sync_review_tab(self) -> QWidget:
        """Build the Sync Review tab widget."""
        w = QWidget()
        vlay = QVBoxLayout()

        # Toolbar
        toolbar = QHBoxLayout()
        lbl = QLabel("Items from the last Outlook sync that need attention:")
        lbl.setStyleSheet("font-weight: bold;")
        toolbar.addWidget(lbl)
        toolbar.addStretch()
        self.btn_refresh_review = QPushButton("↺ Refresh")
        self.btn_refresh_review.clicked.connect(self._load_sync_review)
        toolbar.addWidget(self.btn_refresh_review)
        vlay.addLayout(toolbar)

        # Review table
        self.sync_review_table = QTableWidget()
        self.sync_review_table.setColumnCount(6)
        self.sync_review_table.setHorizontalHeaderLabels([
            "Type", "Reserve #", "Date", "Subject / Reason", "✅ Confirm", "🚫 Disregard"
        ])
        hdr = self.sync_review_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.sync_review_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.sync_review_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.sync_review_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.sync_review_table.cellDoubleClicked.connect(
            self._open_sync_review_item
        )
        self.sync_review_table.verticalHeader().setVisible(False)
        vlay.addWidget(self.sync_review_table)

        # Bottom action bar
        bot = QHBoxLayout()
        btn_confirm_all = QPushButton("✅ Confirm All")
        btn_confirm_all.clicked.connect(self._confirm_all_sync_items)
        btn_disregard_all = QPushButton("🚫 Disregard All")
        btn_disregard_all.clicked.connect(self._disregard_all_sync_items)
        btn_open_selected = QPushButton("📋 Open Selected")
        btn_open_selected.clicked.connect(self._open_selected_sync_item)
        btn_confirm_selected = QPushButton("✅ Confirm Selected")
        btn_confirm_selected.clicked.connect(self._confirm_selected_sync_item)
        btn_disregard_selected = QPushButton("🚫 Disregard Selected")
        btn_disregard_selected.clicked.connect(
            self._disregard_selected_sync_item
        )
        self.sync_review_count_lbl = QLabel("")
        bot.addWidget(btn_open_selected)
        bot.addWidget(btn_confirm_selected)
        bot.addWidget(btn_disregard_selected)
        bot.addWidget(btn_confirm_all)
        bot.addWidget(btn_disregard_all)
        bot.addStretch()
        bot.addWidget(self.sync_review_count_lbl)
        vlay.addLayout(bot)

        w.setLayout(vlay)

        # Load data
        self._load_sync_review()
        return w

    def _highlight_charter_dates(self) -> None:
        """Highlight dates that have charters and non-charter staff work."""
        try:
            year_month = self.calendar.selectedDate()
            start_date = QDate(year_month.year(), year_month.month(), 1)
            # Get last day of month
            if year_month.month() == 12:
                end_date = QDate(year_month.year() + 1, 1, 1).addDays(-1)
            else:
                end_date = QDate(
                    year_month.year(), year_month.month() + 1, 1
                ).addDays(-1)

            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT DISTINCT charter_date
                    FROM charters
                    WHERE charter_date >= %s AND charter_date <= %s
                        AND (status IS NULL OR status NOT IN
                            ('cancelled','no-show'))
                """,
                    (start_date.toPyDate(), end_date.toPyDate()),
                )

                charter_dates = set()
                for row in cur.fetchall():
                    if row[0]:
                        charter_dates.add(str(row[0]))

                staff_dates = set()
                scols = self._cols("employee_work_schedule")
                if {"work_date", "status"} <= scols:
                    cur.execute(
                        """
                        SELECT DISTINCT work_date
                        FROM employee_work_schedule
                        WHERE work_date >= %s AND work_date <= %s
                          AND COALESCE(status, 'SCHEDULED') <> 'CANCELLED'
                        """,
                        (start_date.toPyDate(), end_date.toPyDate()),
                    )
                    for row in cur.fetchall():
                        if row[0]:
                            staff_dates.add(str(row[0]))

                # Highlight each date with source-aware color.
                all_dates = charter_dates | staff_dates
                for date_str in all_dates:
                    date_obj = QDate.fromString(date_str, "yyyy-MM-dd")
                    if not date_obj.isValid():
                        continue
                    fmt = self.calendar.dateTextFormat(QDate())
                    fmt.setFontWeight(QFont.Weight.Bold)
                    if date_str in charter_dates and date_str in staff_dates:
                        fmt.setBackground(QBrush(QColor("#dbeafe")))
                        fmt.setForeground(QBrush(QColor("#065f46")))
                    elif date_str in charter_dates:
                        fmt.setBackground(QBrush(QColor(173, 216, 230)))
                    else:
                        fmt.setBackground(QBrush(QColor("#dcfce7")))
                    self.calendar.setDateTextFormat(date_obj, fmt)
        except Exception as e:
            logger.error("Failed to highlight charter dates: %s", e)

    # ===== Sync Review Tab =====

    @pyqtSlot()
    def _load_sync_review(self) -> None:
        """Load all items needing review into the Sync Review table."""
        try:
            items = []

            with DatabaseContext(self.db, auto_commit=False) as cur:
                # 1. Charter date/time mismatches
                self._ensure_calendar_events_table(cur)
                cur.execute("""
                    SELECT 'mismatch', reserve_number, charter_date,
                           COALESCE(calendar_notes, 'Date/time mismatch with Outlook'),
                           charter_id, NULL
                    FROM charters
                    WHERE calendar_sync_status = 'mismatch'
                    ORDER BY charter_date DESC
                """)
                for row in cur.fetchall():
                    items.append({
                        "kind": "mismatch",
                        "reserve": str(row[1] or ""),
                        "date": str(row[2] or ""),
                        "reason": str(row[3] or ""),
                        "charter_id": row[4],
                        "event_id": None,
                    })

                # 2. New placeholder charters (from latest sync)
                cur.execute("""
                    SELECT 'new_placeholder', reserve_number, charter_date,
                           COALESCE(client_display_name, 'New placeholder from Outlook'),
                           charter_id, NULL
                    FROM charters
                    WHERE is_placeholder = TRUE
                      AND calendar_sync_status = 'synced'
                      AND (calendar_notes IS NULL OR calendar_notes NOT LIKE '%confirmed%')
                    ORDER BY charter_date DESC
                """)
                for row in cur.fetchall():
                    items.append({
                        "kind": "new_placeholder",
                        "reserve": str(row[1] or ""),
                        "date": str(row[2] or ""),
                        "reason": str(row[3] or ""),
                        "charter_id": row[4],
                        "event_id": None,
                    })

                # 3. Calendar events flagged for manual review
                cur.execute("""
                    SELECT 'manual_review', reserve_number, event_date,
                           COALESCE(review_reason, event_title, 'Needs manual review'),
                           NULL, id
                    FROM calendar_events
                    WHERE needs_manual_review = TRUE
                    ORDER BY event_date DESC
                """)
                for row in cur.fetchall():
                    items.append({
                        "kind": "manual_review",
                        "reserve": str(row[1] or ""),
                        "date": str(row[2] or ""),
                        "reason": str(row[3] or ""),
                        "charter_id": None,
                        "event_id": row[5],
                    })

            self.sync_review_table.setRowCount(len(items))
            self._sync_review_items = items  # store for confirm/disregard

            kind_labels = {
                "mismatch": "⚠️ Mismatch",
                "new_placeholder": "🆕 New Charter",
                "manual_review": "🔍 Review",
            }
            kind_colors = {
                "mismatch": "#fff3cd",
                "new_placeholder": "#d1ecf1",
                "manual_review": "#f8d7da",
            }

            for row_idx, item in enumerate(items):
                kind = item["kind"]
                bg = QColor(kind_colors.get(kind, "#ffffff"))

                cells = [
                    kind_labels.get(kind, kind),
                    item["reserve"],
                    item["date"],
                    item["reason"],
                ]
                for col, text in enumerate(cells):
                    cell = QTableWidgetItem(str(text))
                    cell.setBackground(QBrush(bg))
                    self.sync_review_table.setItem(row_idx, col, cell)

                # Confirm button
                btn_confirm = QPushButton("✅")
                btn_confirm.setFixedWidth(36)
                btn_confirm.setToolTip("Confirm — remove from review list")
                btn_confirm.clicked.connect(
                    lambda checked, r=row_idx: self._confirm_sync_item(r)
                )
                self.sync_review_table.setCellWidget(row_idx, 4, btn_confirm)

                # Disregard button
                btn_disregard = QPushButton("🚫")
                btn_disregard.setFixedWidth(36)
                btn_disregard.setToolTip("Disregard — dismiss without action")
                btn_disregard.clicked.connect(
                    lambda checked, r=row_idx: self._disregard_sync_item(r)
                )
                self.sync_review_table.setCellWidget(row_idx, 5, btn_disregard)

            count = len(items)
            self.sync_review_count_lbl.setText(
                f"{count} item{'s' if count != 1 else ''} pending review"
            )
            self._refresh_sync_review_badge()

        except Exception as e:
            logger.error(f"Failed to load sync review: {e}")

    def _refresh_sync_review_badge(self) -> None:
        """Update the tab label with pending count."""
        try:
            count = len(getattr(self, "_sync_review_items", []))
            label = f"🔄 Sync Review ({count})" if count else "🔄 Sync Review"
            idx = self.right_tabs.indexOf(self.right_tabs.widget(1))
            if idx >= 0:
                self.right_tabs.setTabText(idx, label)
        except Exception:
            pass

    def _confirm_sync_item(self, row_idx: int) -> None:
        """Mark item as confirmed and remove from review list."""
        items = getattr(self, "_sync_review_items", [])
        if row_idx >= len(items):
            return
        item = items[row_idx]
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                if item["kind"] == "mismatch" and item["charter_id"]:
                    cur.execute("""
                        UPDATE charters
                        SET calendar_sync_status = 'confirmed',
                            calendar_color = 'green',
                            calendar_notes = COALESCE(calendar_notes,'') || ' [confirmed]',
                            updated_at = NOW()
                        WHERE charter_id = %s
                    """, (item["charter_id"],))
                elif item["kind"] == "new_placeholder" and item["charter_id"]:
                    cur.execute("""
                        UPDATE charters
                        SET calendar_notes = COALESCE(calendar_notes,'') || ' [confirmed]',
                            updated_at = NOW()
                        WHERE charter_id = %s
                    """, (item["charter_id"],))
                elif item["kind"] == "manual_review" and item["event_id"]:
                    cur.execute("""
                        UPDATE calendar_events
                        SET needs_manual_review = FALSE,
                            classification = 'confirmed',
                            updated_at = NOW()
                        WHERE id = %s
                    """, (item["event_id"],))
            self._load_sync_review()
        except Exception as e:
            QMessageBox.warning(self, "Confirm Error", str(e))

    def _disregard_sync_item(self, row_idx: int) -> None:
        """Mark item as disregarded and remove from review list."""
        items = getattr(self, "_sync_review_items", [])
        if row_idx >= len(items):
            return
        item = items[row_idx]
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                if item["kind"] in ("mismatch", "new_placeholder") and item["charter_id"]:
                    cur.execute("""
                        UPDATE charters
                        SET calendar_sync_status = 'disregarded',
                            calendar_notes = COALESCE(calendar_notes,'') || ' [disregarded]',
                            updated_at = NOW()
                        WHERE charter_id = %s
                    """, (item["charter_id"],))
                elif item["kind"] == "manual_review" and item["event_id"]:
                    cur.execute("""
                        UPDATE calendar_events
                        SET needs_manual_review = FALSE,
                            event_status = 'disregarded',
                            updated_at = NOW()
                        WHERE id = %s
                    """, (item["event_id"],))
            self._load_sync_review()
        except Exception as e:
            QMessageBox.warning(self, "Disregard Error", str(e))

    @pyqtSlot()
    def _confirm_all_sync_items(self) -> None:
        items = getattr(self, "_sync_review_items", [])
        if not items:
            return
        reply = QMessageBox.question(
            self, "Confirm All",
            f"Confirm all {len(items)} pending items?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for idx in range(len(items)):
            self._confirm_sync_item(0)  # list re-loads each time, always pick first

    @pyqtSlot()
    def _disregard_all_sync_items(self) -> None:
        items = getattr(self, "_sync_review_items", [])
        if not items:
            return
        reply = QMessageBox.question(
            self, "Disregard All",
            f"Disregard all {len(items)} pending items?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for idx in range(len(items)):
            self._disregard_sync_item(0)

    def _get_selected_sync_review_row(self) -> int | None:
        selection_model = self.sync_review_table.selectionModel()
        if not selection_model:
            return None
        rows = selection_model.selectedRows()
        if not rows:
            return None
        return rows[0].row()

    @pyqtSlot()
    def _open_selected_sync_item(self) -> None:
        row = self._get_selected_sync_review_row()
        if row is None:
            QMessageBox.information(
                self,
                "Open Sync Item",
                "Select one sync review row to open.",
            )
            return
        self._open_sync_review_item(row, 0)

    @pyqtSlot()
    def _confirm_selected_sync_item(self) -> None:
        row = self._get_selected_sync_review_row()
        if row is None:
            QMessageBox.information(
                self,
                "Confirm Sync Item",
                "Select one sync review row to confirm.",
            )
            return
        self._confirm_sync_item(row)

    def _disregard_selected_sync_item(self) -> None:
        row = self._get_selected_sync_review_row()
        if row is None:
            QMessageBox.information(
                self,
                "Disregard Sync Item",
                "Select one sync review row to disregard.",
            )
            return
        self._disregard_sync_item(row)

    def _open_sync_review_item(self, row, _column) -> None:
        items = getattr(self, "_sync_review_items", [])
        if row < 0 or row >= len(items):
            return

        item = items[row]
        reserve_number = str(item.get("reserve") or "").strip()
        charter_id = item.get("charter_id")

        # Open charter records directly so dispatcher can fix one mismatch at a time.
        if item.get("kind") in ("mismatch", "new_placeholder"):
            if reserve_number or charter_id:
                self._open_existing_charter(reserve_number, charter_id)
                return
            QMessageBox.information(
                self,
                "Open Sync Item",
                "No reserve number was found for this row.",
            )
            return

        if item.get("kind") == "manual_review":
            if reserve_number:
                self._open_existing_charter(reserve_number, charter_id)
                return
            QMessageBox.information(
                self,
                "Manual Review",
                "This review row has no linked reserve number yet.",
            )

    # ===== Data load =====
    def _cols(self, table) -> set[str]:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema='public' AND table_name=%s
                """,
                    (table,),
                )
                return {r[0] for r in cur.fetchall()}
        except Exception as e:
            logger.error(f"Failed to get columns for table {table}: {e}")
            return set()

    @pyqtSlot(QDate)
    def _load_day(self, qdate: QDate) -> None:
        # Convert to Python date object for database parameter binding
        date_py = qdate.toPyDate()
        try:
            ccols = self._cols("charters")
            ecols = self._cols("employees")
            vcols = self._cols("vehicles")

            # Check if calendar sync columns exist
            has_calendar_sync = all(
                col in ccols
                for col in [
                    "calendar_color",
                    "calendar_sync_status",
                    "calendar_notes",
                ]
            )

            desired = [
                "reserve_number",
                "charter_id",
                "status",
                "pickup_time",
                "do_time",
                "dropoff_time",
                "depart_yard_time",
                "vehicle_id",
                "employee_id",
                "client_display_name",
                "charter_type",
            ]
            # include optional expiration column if present
            if "quote_expires_at" in ccols:
                desired.append("quote_expires_at")
            if has_calendar_sync:
                desired.extend(
                    [
                        "calendar_color",
                        "calendar_sync_status",
                        "calendar_notes",
                    ]
                )

            select_cols = [c for c in desired if c in ccols]
            sel = (
                ", ".join(select_cols)
                if select_cols
                else "reserve_number, charter_id"
            )

            general_events = []
            staff_events = []
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    f"""
                    SELECT {sel}
                    FROM charters
                    WHERE charter_date = %s
                    AND (status IS NULL OR status NOT IN
                        ('cancelled','no-show'))
                    ORDER BY pickup_time NULLS LAST
                """,
                    (date_py,),
                )
                rows = cur.fetchall()

                # Optional: include non-booking/general calendar events
                # when the table exists.
                try:
                    self._ensure_calendar_events_table(cur)
                    cur.execute(
                        """
                        SELECT
                            id,
                            event_date,
                            event_time,
                            event_title,
                            driver_name,
                            vehicle_type,
                            event_notes,
                            event_status,
                            needs_manual_review,
                            review_reason
                        FROM calendar_events
                        WHERE event_date = %s
                          AND COALESCE(event_status, 'active') != 'cancelled'
                        ORDER BY event_time NULLS LAST, id
                        """,
                        (date_py,),
                    )
                    general_events = cur.fetchall()
                except Exception as ge:
                    logger.debug(
                        "Skipping calendar_events load for day view: %s", ge
                    )

                # Include non-charter staff schedule entries for the day.
                scols = self._cols("employee_work_schedule")
                if {
                    "schedule_id",
                    "employee_id",
                    "work_date",
                    "role_type",
                    "task_name",
                    "start_time",
                    "end_time",
                    "scheduled_hours",
                    "pay_type",
                    "rate_amount",
                    "status",
                    "notes",
                } <= scols:
                    cur.execute(
                        """
                        SELECT
                            s.schedule_id,
                            COALESCE(e.full_name, ''),
                            COALESCE(s.role_type, 'OTHER'),
                            COALESCE(s.task_name, ''),
                            TO_CHAR(s.start_time, 'HH24:MI'),
                            TO_CHAR(s.end_time, 'HH24:MI'),
                            COALESCE(s.scheduled_hours, 0),
                            COALESCE(s.pay_type, 'HOURLY'),
                            COALESCE(s.rate_amount, 0),
                            COALESCE(s.status, 'SCHEDULED'),
                            COALESCE(s.notes, '')
                        FROM employee_work_schedule s
                        LEFT JOIN employees e ON s.employee_id = e.employee_id
                        WHERE s.work_date = %s
                          AND COALESCE(s.status, 'SCHEDULED') <> 'CANCELLED'
                        ORDER BY s.start_time NULLS LAST, s.schedule_id
                        """,
                        (date_py,),
                    )
                    staff_events = cur.fetchall()

            # Pre-load driver double-booking conflicts for this date
            conflict_reserves = self._find_driver_conflicts_for_date(date_py)

            self.day_table.setRowCount(
                len(rows) + len(general_events) + len(staff_events)
            )
            self.task_list.clear()

            # load tasks for date (convert back to string for task file lookup)
            date_str = (
                date_py.isoformat()
            )  # Convert to YYYY-MM-DD format string
            tasks = self._read_tasks_for_date(date_str)
            for t in tasks:
                item = QListWidgetItem(
                    f"[{t.get('status', 'open')}] {t.get('text', '')}"
                    f"(reserve {t.get('reserve_number', '')})"
                )
                item.setData(Qt.ItemDataRole.UserRole, int(t.get("id") or 0))
                item.setData(Qt.ItemDataRole.UserRole + 1, t.get("date") or "")
                item.setData(
                    Qt.ItemDataRole.UserRole + 2,
                    t.get("reserve_number") or "",
                )
                item.setData(Qt.ItemDataRole.UserRole + 3, t.get("text") or "")
                item.setData(Qt.ItemDataRole.UserRole + 4, t.get("status") or "open")
                self.task_list.addItem(item)
                if hasattr(self, "todo_list") and self.todo_list is not None:
                    clone = QListWidgetItem(item.text())
                    clone.setData(
                        Qt.ItemDataRole.UserRole,
                        item.data(Qt.ItemDataRole.UserRole),
                    )
                    clone.setData(
                        Qt.ItemDataRole.UserRole + 1,
                        item.data(Qt.ItemDataRole.UserRole + 1),
                    )
                    clone.setData(
                        Qt.ItemDataRole.UserRole + 2,
                        item.data(Qt.ItemDataRole.UserRole + 2),
                    )
                    clone.setData(
                        Qt.ItemDataRole.UserRole + 3,
                        item.data(Qt.ItemDataRole.UserRole + 3),
                    )
                    clone.setData(
                        Qt.ItemDataRole.UserRole + 4,
                        item.data(Qt.ItemDataRole.UserRole + 4),
                    )
                    self.todo_list.addItem(clone)

            if hasattr(self, "main_todo_list") and self.main_todo_list is not None:
                self.main_todo_list.clear()
                all_open = [
                    t
                    for t in self._read_tasks()
                    if str(t.get("status") or "open").lower() != "done"
                ]
                all_open.sort(
                    key=lambda t: (
                        str(t.get("date") or ""),
                        int(t.get("id") or 0),
                    )
                )
                for t in all_open:
                    main_item = QListWidgetItem(
                        f"[{t.get('date', '')}] {t.get('text', '')} "
                        f"(reserve {t.get('reserve_number', '')})"
                    )
                    main_item.setData(
                        Qt.ItemDataRole.UserRole,
                        int(t.get("id") or 0),
                    )
                    main_item.setData(
                        Qt.ItemDataRole.UserRole + 1,
                        t.get("date") or "",
                    )
                    main_item.setData(
                        Qt.ItemDataRole.UserRole + 2,
                        t.get("reserve_number") or "",
                    )
                    main_item.setData(
                        Qt.ItemDataRole.UserRole + 3,
                        t.get("text") or "",
                    )
                    main_item.setData(
                        Qt.ItemDataRole.UserRole + 4,
                        t.get("status") or "open",
                    )
                    self.main_todo_list.addItem(main_item)

            for r, row in enumerate(rows):
                data = dict(zip(select_cols, row)) if select_cols else {}
                reserve = str(data.get("reserve_number") or "")
                charter_id = str(data.get("charter_id") or "")
                status = str(data.get("status") or "")
                pickup = str(data.get("pickup_time") or "")
                do_time_str = str(
                    data.get("do_time") or data.get("dropoff_time") or ""
                )
                depart = str(data.get("depart_yard_time") or "")
                client = str(
                    data.get("client_display_name")
                    or data.get("customer_name")
                    or ""
                )
                vehicle = self._vehicle_display(vcols, data.get("vehicle_id"))
                driver = self._driver_display(ecols, data.get("employee_id"))
                ctype = self._charter_type(data)

                # Outlook sync status (only if columns exist)
                if has_calendar_sync:
                    cal_color = str(data.get("calendar_color") or "")
                    cal_status = str(
                        data.get("calendar_sync_status") or "not_synced"
                    )
                    cal_notes = str(data.get("calendar_notes") or "")
                    outlook_indicator = self._outlook_status_display(
                        cal_color, cal_status
                    )
                else:
                    outlook_indicator = ""  # Empty if sync not enabled
                    cal_color = ""
                    cal_status = "not_enabled"
                    cal_notes = ""

                alerts = self._alerts_for_row(
                    status, driver, vehicle, date_str, reserve,
                    conflict_reserves,
                )

                # Expiration warning for quotes
                expired = False
                try:
                    qexp = data.get("quote_expires_at")
                    if qexp and (
                        isinstance(qexp, str) or hasattr(qexp, "isoformat")
                    ):
                        # normalize to datetime for comparison
                        from datetime import datetime as _dt

                        if isinstance(qexp, str):
                            # Accept common timestamp/date string formats
                            for fmt in (
                                "%Y-%m-%d %H:%M:%S",
                                "%Y-%m-%d %H:%M:%S.%",
                                "%Y-%m-%d",
                            ):
                                try:
                                    qexp_dt = _dt.strptime(qexp, fmt)
                                    break
                                except Exception:
                                    qexp_dt = None
                            if qexp_dt is None:
                                qexp_dt = (
                                    _dt.fromisoformat(qexp)
                                    if "T" in qexp
                                    else None
                                )
                        else:
                            qexp_dt = (
                                qexp if hasattr(qexp, "timestamp") else None
                            )
                        if (
                            qexp_dt
                            and (status.lower() == "quote")
                            and _dt.now() > qexp_dt
                        ):
                            expired = True
                except Exception:
                    expired = False

                if expired:
                    alerts = (
                        alerts + ", " if alerts else ""
                    ) + "Expired Quote"

                items = [
                    QTableWidgetItem(reserve),  # 0: Reserve #
                    QTableWidgetItem(client),  # 1: Client
                    QTableWidgetItem(ctype),  # 2: Type
                    QTableWidgetItem(charter_id),  # 3: Charter ID
                    QTableWidgetItem(pickup),  # 4: Pickup
                    QTableWidgetItem(do_time_str),  # 5: Do Time
                    QTableWidgetItem(depart),  # 6: Depart Yard
                    QTableWidgetItem(vehicle),  # 7: Vehicle
                    QTableWidgetItem(driver),  # 8: Driver
                    QTableWidgetItem(status),  # 9: Status
                    QTableWidgetItem(outlook_indicator),  # 10: Outlook
                    QTableWidgetItem(alerts),
                ]  # 11: Alerts
                for c, it in enumerate(items):
                    self.day_table.setItem(r, c, it)

                # Apply Outlook sync color to indicator column (column 10)
                outlook_item = items[10]
                if cal_color == "green":
                    outlook_item.setBackground(
                        QBrush(QColor("#d4edda"))
                    )  # light green
                    outlook_item.setForeground(
                        QBrush(QColor("#155724"))
                    )  # dark green text
                elif cal_color == "red":
                    outlook_item.setBackground(
                        QBrush(QColor("#f8d7da"))
                    )  # light red
                    outlook_item.setForeground(
                        QBrush(QColor("#721c24"))
                    )  # dark red text
                elif cal_color == "yellow":
                    outlook_item.setBackground(
                        QBrush(QColor("#fff3cd"))
                    )  # light yellow
                    outlook_item.setForeground(
                        QBrush(QColor("#856404"))
                    )  # dark yellow text
                elif cal_color == "blue":
                    outlook_item.setBackground(
                        QBrush(QColor("#d1ecf1"))
                    )  # light blue
                    outlook_item.setForeground(
                        QBrush(QColor("#0c5460"))
                    )  # dark blue text
                elif cal_color == "gray":
                    outlook_item.setBackground(
                        QBrush(QColor("#e2e3e5"))
                    )  # light gray
                    outlook_item.setForeground(
                        QBrush(QColor("#383d41"))
                    )  # dark gray text

                # Tooltip with sync details
                if cal_notes:
                    outlook_item.setToolTip(f"{cal_status}\n{cal_notes}")
                else:
                    outlook_item.setToolTip(cal_status)

                # color coding for row alerts
                if "unassigned" in alerts.lower():
                    self._paint_row_except_outlook(
                        r, QColor("#fff3cd")
                    )  # yellow
                elif "vehicle unavailable" in alerts.lower():
                    self._paint_row_except_outlook(r, QColor("#f8d7da"))  # red
                elif ctype == "Quote":
                    # Light blue for quotes; expired quotes slightly different
                    # tint
                    self._paint_row_except_outlook(
                        r, QColor("#e3f2fd" if not expired else "#fce4ec")
                    )

            # Append non-booking/general calendar events.
            start_row = len(rows)
            for idx, event in enumerate(general_events):
                (
                    _event_id,
                    _event_date,
                    event_time,
                    event_title,
                    driver_name,
                    vehicle_type,
                    event_notes,
                    event_status,
                    needs_manual_review,
                    review_reason,
                ) = event
                row_ix = start_row + idx

                pickup = str(event_time or "")
                client = str(event_title or "")
                notes = str(event_notes or "")
                status = str(event_status or "active")
                event_type = (
                    "Manual Review" if needs_manual_review else "General Event"
                )
                outlook_indicator = "🟡" if needs_manual_review else "⚪"
                alerts = str(review_reason or "")

                items = [
                    QTableWidgetItem(""),
                    QTableWidgetItem(client),
                    QTableWidgetItem(event_type),
                    QTableWidgetItem(""),
                    QTableWidgetItem(pickup),
                    QTableWidgetItem(""),
                    QTableWidgetItem(""),
                    QTableWidgetItem(str(vehicle_type or "")),
                    QTableWidgetItem(str(driver_name or "")),
                    QTableWidgetItem(status),
                    QTableWidgetItem(outlook_indicator),
                    QTableWidgetItem(alerts),
                ]
                for c, it in enumerate(items):
                    self.day_table.setItem(row_ix, c, it)

                if notes:
                    items[10].setToolTip(notes)

            # Append non-charter staff work schedule rows.
            start_row = len(rows) + len(general_events)
            for idx, item in enumerate(staff_events):
                (
                    _schedule_id,
                    employee_name,
                    role_type,
                    task_name,
                    start_time,
                    end_time,
                    scheduled_hours,
                    pay_type,
                    rate_amount,
                    status,
                    notes,
                ) = item
                row_ix = start_row + idx

                est_pay = (
                    float(scheduled_hours or 0.0) * float(rate_amount or 0.0)
                    if str(pay_type or "").upper() == "HOURLY"
                    else float(rate_amount or 0.0)
                )
                alerts = f"Est ${est_pay:,.2f} ({pay_type})"

                staff_items = [
                    QTableWidgetItem(""),
                    QTableWidgetItem(str(task_name or "")),
                    QTableWidgetItem("Staff Work"),
                    QTableWidgetItem(""),
                    QTableWidgetItem(str(start_time or "")),
                    QTableWidgetItem(str(end_time or "")),
                    QTableWidgetItem(""),
                    QTableWidgetItem(str(role_type or "")),
                    QTableWidgetItem(str(employee_name or "")),
                    QTableWidgetItem(str(status or "SCHEDULED")),
                    QTableWidgetItem("👷"),
                    QTableWidgetItem(alerts),
                ]
                for c, it in enumerate(staff_items):
                    self.day_table.setItem(row_ix, c, it)

                self._paint_row_except_outlook(row_ix, QColor("#ecfdf5"))
                if notes:
                    staff_items[10].setToolTip(str(notes))

                # General events get a subtle neutral tint.
                self._paint_row_except_outlook(row_ix, QColor("#f1f3f5"))
        except Exception as e:
            logger.error(f"Failed to load day: {e}")
            QMessageBox.warning(self, "Load Error", f"Failed to load: {e}")

    def _outlook_status_display(self, cal_color: str, cal_status: str) -> str:
        """Return emoji indicator for Outlook sync status."""
        emoji_map = {
            "green": "🟢",  # synced
            "red": "🔴",  # not in calendar
            "yellow": "🟡",  # mismatch
            "blue": "🔵",  # recently updated
            "gray": "⚫",  # cancelled
        }
        return emoji_map.get(cal_color, "⚪")  # white circle for unknown

    def _paint_row(self, row: int, color: QColor) -> None:
        for c in range(self.day_table.columnCount()):
            item = self.day_table.item(row, c)
            if item:
                item.setBackground(QBrush(color))

    def _paint_row_except_outlook(self, row: int, color: QColor) -> None:
        """Paint row background except Outlook column (col 10) which has its"
        "own colors."""

        for c in range(self.day_table.columnCount()):
            if c == 10:  # Skip Outlook column
                continue
            item = self.day_table.item(row, c)
            if item:
                item.setBackground(QBrush(color))

    def _charter_type(self, data) -> str:
        bt = str(data.get("booking_type") or "")
        if bt.lower() in ("quote", "quoted"):
            return "Quote"
        if bt.lower() in ("booking", "booked"):
            return "Booking"
        return "Charter"

    def _vehicle_display(self, vcols, vehicle_id) -> str:
        if not vehicle_id or "vehicle_id" not in vcols:
            return ""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    "SELECT vehicle_number, operational_status FROM vehicles "
                    "WHERE vehicle_id=%s",
                    (vehicle_id,),
                )
                r = cur.fetchone()
                if not r:
                    return ""
                parts = [str(x) for x in r[:-1] if x]
                status = str(r[-1] or "")
                disp = " / ".join(parts)
                if status and status.lower() not in ("active", "active "):
                    disp += f" (status: {status})"
                return disp
        except Exception as e:
            logger.error(f"Failed to display vehicle {vehicle_id}: {e}")
            return ""

    def _driver_display(self, ecols, employee_id) -> str:
        if not employee_id or "employee_id" not in ecols:
            return ""
        try:
            allowed_driver_cols = [
                "full_name",
                "phone_number",
                "employment_status",
                "is_active",
            ]
            selected_cols = [c for c in allowed_driver_cols if c in ecols]
            if not selected_cols:
                selected_cols = ["full_name"]
            select_clause = sql.SQL(", ").join(
                sql.Identifier(c) for c in selected_cols
            )
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    sql.SQL(
                        "SELECT {} FROM employees WHERE employee_id=%s"
                    ).format(select_clause),
                    (employee_id,),
                )
                r = cur.fetchone()
                if not r:
                    return ""
                return " / ".join([str(x) for x in r if x])
        except Exception as e:
            logger.error(f"Failed to display driver {employee_id}: {e}")
            return ""

    def _alerts_for_row(
        self, status, driver_disp, vehicle_disp, date_str, reserve,
        conflict_reserves: set | None = None,
    ) -> str:
        alerts = []
        if not driver_disp:
            alerts.append("Unassigned driver")
        if vehicle_disp.endswith(")") and "status:" in vehicle_disp:
            alerts.append("Vehicle unavailable")
        if not self._has_prepayment(reserve):
            alerts.append("Prepayment pending")
        if conflict_reserves and reserve in conflict_reserves:
            alerts.append("⚠️ Driver double-booked")
        # Add task count for day
        tasks = self._read_tasks_for_date(date_str)
        t_for_res = [
            t
            for t in tasks
            if t.get("reserve_number") == reserve
            and t.get("status", "open") == "open"
        ]
        if t_for_res:
            alerts.append(f"{len(t_for_res)} open task(s)")
        return ", ".join(alerts)

    # ===== Tasks =====
    def _read_tasks(self) -> list[dict]:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT task_id, reserve_number, task_date, task_text, status
                    FROM dispatch_tasks ORDER BY task_id
                """)
                return [
                    {
                        "id": str(r[0]),
                        "reserve_number": r[1] or "",
                        "date": r[2] or "",
                        "text": r[3] or "",
                        "status": r[4] or "open",
                    }
                    for r in cur.fetchall()
                ]
        except Exception:
            return []

    def _write_tasks(self, tasks) -> None:
        """Not used directly — tasks are written via _create_task / _verify_selected_task."""
        pass

    def _read_tasks_for_date(self, date_str) -> list[dict]:
        legacy = ""
        try:
            legacy = datetime.strptime(date_str, "%Y-%m-%d").strftime(
                "%m/%d/%Y"
            )
        except Exception:
            legacy = ""
        return [
            t
            for t in self._read_tasks()
            if t.get("date") in {date_str, legacy}
        ]

    @pyqtSlot()
    def _create_task(self) -> None:
        items = self.day_table.selectedItems()
        date_str = self.calendar.selectedDate().toPyDate().isoformat()
        reserve = items[0].text() if items else ""
        text = (
            "Buy beverages / Pre-start vehicle / Call client / Ensure payment."
        )
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "INSERT INTO dispatch_tasks (reserve_number, task_date, task_text, status) "
                    "VALUES (%s, %s, %s, 'open')",
                    (reserve, date_str, text),
                )
        except Exception as e:
            QMessageBox.warning(self, "Task Save Error", str(e))
        self._load_day(self.calendar.selectedDate())

    @pyqtSlot()
    def _verify_selected_task(self) -> None:
        selected_item = None
        if hasattr(self, "todo_list") and self.todo_list is not None:
            selected_item = self.todo_list.currentItem()
        if selected_item is None and hasattr(self, "task_list"):
            selected_item = self.task_list.currentItem()

        selected_task_id = (
            int(selected_item.data(Qt.ItemDataRole.UserRole))
            if selected_item
            and selected_item.data(Qt.ItemDataRole.UserRole)
            else 0
        )

        # Fallback: mark first open task for selected reserve.
        items = self.day_table.selectedItems()
        reserve = items[0].text() if items else ""
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                if selected_task_id:
                    cur.execute(
                        """
                        UPDATE dispatch_tasks
                        SET status='done'
                        WHERE task_id=%s
                        """,
                        (selected_task_id,),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE dispatch_tasks SET status='done'
                        WHERE task_id = (
                            SELECT task_id FROM dispatch_tasks
                            WHERE reserve_number=%s AND status='open'
                            ORDER BY task_id LIMIT 1
                        )
                        """,
                        (reserve,),
                    )
        except Exception as e:
            QMessageBox.warning(self, "Task Error", str(e))
        self._load_day(self.calendar.selectedDate())

    @pyqtSlot()
    def _delete_selected_task(self) -> None:
        selected_item = None
        if hasattr(self, "todo_list") and self.todo_list is not None:
            selected_item = self.todo_list.currentItem()
        if selected_item is None and hasattr(self, "task_list"):
            selected_item = self.task_list.currentItem()
        if selected_item is None:
            QMessageBox.information(
                self,
                "Delete To-Do",
                "Select a to-do item first.",
            )
            return

        task_id = int(selected_item.data(Qt.ItemDataRole.UserRole) or 0)
        if not task_id:
            QMessageBox.warning(
                self,
                "Delete To-Do",
                "Could not determine task id for this item.",
            )
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "DELETE FROM dispatch_tasks WHERE task_id=%s",
                    (task_id,),
                )
        except Exception as e:
            QMessageBox.warning(self, "Delete To-Do", str(e))
            return
        self._load_day(self.calendar.selectedDate())

    def _selected_row_payload(self) -> dict:
        row = self.day_table.currentRow()
        if row < 0:
            return {}
        def _txt(col: int) -> str:
            item = self.day_table.item(row, col)
            return (item.text() if item else "").strip()

        return {
            "reserve": _txt(0),
            "client": _txt(1),
            "entry_type": _txt(2),
            "pickup": _txt(4),
            "driver": _txt(8),
            "status": _txt(9),
            "alerts": _txt(11),
        }

    def _selected_todo_payload(self) -> dict:
        selected_item = None
        if hasattr(self, "main_todo_list") and self.main_todo_list is not None:
            selected_item = self.main_todo_list.currentItem()
        if hasattr(self, "todo_list") and self.todo_list is not None:
            selected_item = selected_item or self.todo_list.currentItem()
        if selected_item is None and hasattr(self, "task_list"):
            selected_item = self.task_list.currentItem()
        if selected_item is None:
            return {}

        return {
            "task_id": int(selected_item.data(Qt.ItemDataRole.UserRole) or 0),
            "date": str(
                selected_item.data(Qt.ItemDataRole.UserRole + 1) or ""
            ),
            "reserve": str(
                selected_item.data(Qt.ItemDataRole.UserRole + 2) or ""
            ),
            "text": str(selected_item.data(Qt.ItemDataRole.UserRole + 3) or ""),
            "status": str(
                selected_item.data(Qt.ItemDataRole.UserRole + 4) or "open"
            ),
        }

    def _focus_todo_item_by_task_id(self, task_id: int) -> None:
        """Keep both list views aligned on the same selected task."""
        if task_id <= 0:
            return
        for list_name in ("main_todo_list", "todo_list", "task_list"):
            widget = getattr(self, list_name, None)
            if widget is None:
                continue
            for i in range(widget.count()):
                item = widget.item(i)
                current_id = int(item.data(Qt.ItemDataRole.UserRole) or 0)
                if current_id == task_id:
                    widget.setCurrentRow(i)
                    break

    def _show_todo_context_menu(self, position) -> None:
        """Right-click context menu for to-do/task list items."""
        source = self.sender()
        if not isinstance(source, QListWidget):
            return

        item = source.itemAt(position)
        if item is None:
            return

        task_id = int(item.data(Qt.ItemDataRole.UserRole) or 0)
        self._focus_todo_item_by_task_id(task_id)

        menu = QMenu()
        post_task_action = menu.addAction("📌 Post Selected To-Do to Outlook")
        post_task_action.triggered.connect(
            self._post_selected_todo_to_outlook_task
        )

        complete_action = menu.addAction("✅ Complete Selected To-Do")
        complete_action.triggered.connect(self._verify_selected_task)

        delete_action = menu.addAction("🗑️ Delete Selected To-Do")
        delete_action.triggered.connect(self._delete_selected_task)

        menu.addSeparator()
        mode_label = str(self.combo_combined_mode.currentText() or "").strip()
        run_mode_action = menu.addAction(
            f"▶ Run Combined Mode On Selected Day Row ({mode_label})"
        )
        run_mode_action.triggered.connect(self._run_selected_combined_action)

        menu.exec(source.mapToGlobal(position))

    @pyqtSlot()
    def _add_selected_to_todo(self) -> None:
        payload = self._selected_row_payload()
        if not payload:
            QMessageBox.information(
                self,
                "Add To-Do",
                "Select a day-view row first.",
            )
            return

        if not self._insert_todo_for_payload(payload):
            return

        self._load_day(self.calendar.selectedDate())
        QMessageBox.information(self, "Add To-Do", "Added to daily to-do list.")

    def _insert_todo_for_payload(self, payload: dict) -> bool:
        """Insert a to-do row for selected calendar payload."""
        date_str = self.calendar.selectedDate().toPyDate().isoformat()
        reserve = payload.get("reserve", "")
        entry_type = payload.get("entry_type", "")
        client = payload.get("client", "")
        pickup = payload.get("pickup", "")
        alerts = payload.get("alerts", "")
        text = (
            f"{entry_type or 'Item'} {reserve or ''} {client or ''}"
            f" @ {pickup or 'TBD'}"
        ).strip()
        if alerts:
            text = f"{text} | {alerts}"

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO dispatch_tasks
                        (reserve_number, task_date, task_text, status)
                    VALUES (%s, %s, %s, 'open')
                    """,
                    (reserve, date_str, text),
                )
        except Exception as e:
            QMessageBox.warning(self, "Add To-Do", str(e))
            return False
        return True

    @pyqtSlot()
    def _prepayment_check_selected(self) -> None:
        items = self.day_table.selectedItems()
        reserve = items[0].text() if items else ""
        ok = self._has_prepayment(reserve)
        QMessageBox.information(
            self, "Prepayment", "Paid/OK" if ok else "Pending/Not found"
        )

    def _has_prepayment(self, reserve_number: str) -> bool:
        if not reserve_number:
            return False
        # Check payments table for any rows with reserve_number
        try:
            pcols = self._cols("payments")
            if "reserve_number" not in pcols:
                return False
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM payments WHERE reserve_number=%s",
                    (reserve_number,),
                )
                return (cur.fetchone() or [0])[0] > 0
        except Exception as e:
            logger.error(
                f"Failed to check prepayment for {reserve_number}: {e}"
            )
            return False

    def _find_driver_conflicts_for_date(self, date_py) -> set[str]:
        """Return set of reserve_numbers that have a driver double-booking."""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT DISTINCT c1.reserve_number, c2.reserve_number
                    FROM charters c1
                    JOIN charters c2
                        ON c1.employee_id = c2.employee_id
                        AND c1.charter_id < c2.charter_id
                        AND c1.charter_date = c2.charter_date
                        AND c1.pickup_time IS NOT NULL
                        AND c2.pickup_time IS NOT NULL
                        AND COALESCE(c1.do_time, c1.dropoff_time) IS NOT NULL
                        AND COALESCE(c2.do_time, c2.dropoff_time) IS NOT NULL
                        AND c1.pickup_time < COALESCE(c2.do_time, c2.dropoff_time)
                        AND c2.pickup_time < COALESCE(c1.do_time, c1.dropoff_time)
                    WHERE c1.charter_date = %s
                    AND c1.status NOT IN ('cancelled', 'no-show', 'Cancelled')
                    AND c2.status NOT IN ('cancelled', 'no-show', 'Cancelled')
                    AND c1.employee_id IS NOT NULL
                """, (date_py,))
                conflicts: set[str] = set()
                for r1, r2 in cur.fetchall():
                    if r1:
                        conflicts.add(str(r1))
                    if r2:
                        conflicts.add(str(r2))
                return conflicts
        except Exception as e:
            logger.error("Failed to check driver conflicts: %s", e)
            return set()


    def _show_context_menu(self, position) -> None:
        """Right-click context menu for Outlook sync actions."""
        menu = QMenu()

        # Get selected charter
        row = self.day_table.currentRow()
        if row < 0:
            return

        reserve_item = self.day_table.item(row, 0)
        outlook_item = self.day_table.item(row, 10)
        if not reserve_item or not outlook_item:
            return

        reserve_number = reserve_item.text()
        outlook_indicator = outlook_item.text()

        add_todo_action = menu.addAction("📝 Add Selected Row to Daily To-Do")
        add_todo_action.triggered.connect(self._add_selected_to_todo)

        post_outlook_action = menu.addAction(
            "📤 Post Selected Row to Arrow Calendar"
        )
        post_outlook_action.triggered.connect(self._post_selected_row_to_outlook)

        post_outlook_task_action = menu.addAction(
            "📌 Post Selected Row as Outlook Task"
        )
        post_outlook_task_action.triggered.connect(
            self._post_selected_row_to_outlook_task
        )

        add_and_post_action = menu.addAction(
            "⚡ Add To-Do + Post as Outlook Task"
        )
        add_and_post_action.triggered.connect(
            self._add_selected_to_todo_and_post_outlook_task
        )

        add_post_all_action = menu.addAction(
            "🚀 Add To-Do + Outlook Task + Arrow Calendar"
        )
        add_post_all_action.triggered.connect(
            self._add_selected_to_todo_post_task_and_calendar
        )

        mode_label = str(self.combo_combined_mode.currentText() or "").strip()
        run_mode_action = menu.addAction(
            f"▶ Run Combined Mode ({mode_label})"
        )
        run_mode_action.triggered.connect(self._run_selected_combined_action)

        menu.addSeparator()

        # Menu actions based on sync status
        if outlook_indicator == "🔴":  # not in calendar
            sync_action = menu.addAction(
                "🔄 Update ONLY This Charter to Outlook"
            )
            sync_action.triggered.connect(
                lambda: self._sync_to_outlook(reserve_number)
            )

        if outlook_indicator == "🟡":  # mismatch
            view_details = menu.addAction("📋 View Mismatch Details")
            view_details.triggered.connect(
                lambda: self._view_sync_details(reserve_number)
            )

        if outlook_indicator in ["🟢", "🔵"]:  # synced or updated
            mark_mismatch = menu.addAction("⚠️ Mark as Mismatch")
            mark_mismatch.triggered.connect(
                lambda: self._mark_mismatch(reserve_number)
            )

        # Always show refresh option
        menu.addSeparator()
        refresh_action = menu.addAction("🔄 Refresh Sync Status")
        refresh_action.triggered.connect(lambda: self._refresh_sync_status())

        # Show legend
        legend_action = menu.addAction("ℹ️ Color Legend")
        legend_action.triggered.connect(self._show_color_legend)

        menu.exec(self.day_table.mapToGlobal(position))

    @pyqtSlot()
    def _post_selected_row_to_outlook(self) -> None:
        payload = self._selected_row_payload()
        if not payload:
            QMessageBox.information(
                self,
                "Post to Outlook",
                "Select a day-view row first.",
            )
            return

        if self._post_payload_to_arrow_new(payload, quiet=False):
            QMessageBox.information(
                self,
                "Post to Outlook",
                "Posted selected item to Arrow Calendar.",
            )

    def _post_payload_to_arrow_new(self, payload: dict, quiet: bool = False) -> bool:
        reserve = str(payload.get("reserve") or "").strip()
        if reserve:
            return bool(self._sync_to_outlook(reserve, quiet=quiet))

        folder = self._find_outlook_calendar_folder("arrow new")
        if folder is None:
            if not quiet:
                QMessageBox.warning(
                    self,
                    "Post to Outlook",
                    "Could not find Outlook calendar 'arrow new'.",
                )
            return False

        selected_date = self.calendar.selectedDate().toPyDate()
        raw_pickup = payload.get("pickup", "")
        start_time = time(9, 0)
        try:
            if raw_pickup:
                start_time = datetime.strptime(raw_pickup[:5], "%H:%M").time()
        except Exception:
            start_time = time(9, 0)

        start_dt = datetime.combine(selected_date, start_time)
        end_dt = start_dt + timedelta(hours=1)
        subject = (
            f"{payload.get('entry_type') or 'Dispatch Item'} - "
            f"{payload.get('client') or 'No Client'}"
        )
        body = (
            f"Date: {selected_date.isoformat()}\n"
            f"Status: {payload.get('status') or ''}\n"
            f"Alerts: {payload.get('alerts') or ''}\n"
            "Created from Dispatcher Calendar day view."
        )

        try:
            appt = folder.Items.Add(1)  # olAppointmentItem
            appt.Subject = subject
            appt.Start = start_dt
            appt.End = end_dt
            appt.Body = body
            appt.Categories = "ALMS"
            appt.Save()
        except Exception as e:
            if not quiet:
                QMessageBox.warning(self, "Post to Outlook", str(e))
            return False
        return True

    def _parse_task_due_date(self, raw_value: str):
        text = str(raw_value or "").strip()
        if not text:
            return self.calendar.selectedDate().toPyDate()
        for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except Exception:
                continue
        return self.calendar.selectedDate().toPyDate()

    def _create_outlook_task(self, *, subject: str, body: str, due_date) -> bool:
        namespace = self._get_outlook_namespace()
        if namespace is None:
            QMessageBox.warning(
                self,
                "Outlook Task",
                (
                    "Outlook integration is unavailable. pywin32 may not "
                    "be installed."
                ),
            )
            return False
        try:
            task_folder = namespace.GetDefaultFolder(13)  # olFolderTasks
            task = task_folder.Items.Add(3)  # olTaskItem
            task.Subject = subject
            task.Body = body
            task.DueDate = due_date
            task.Categories = "ALMS"
            task.Save()
            return True
        except Exception as e:
            QMessageBox.warning(self, "Outlook Task", str(e))
            return False

    @pyqtSlot()
    def _post_selected_row_to_outlook_task(self) -> None:
        payload = self._selected_row_payload()
        if not payload:
            QMessageBox.information(
                self,
                "Outlook Task",
                "Select a day-view row first.",
            )
            return

        selected_date = self.calendar.selectedDate().toPyDate()
        reserve = payload.get("reserve", "")
        subject = (
            f"Dispatch: {payload.get('entry_type') or 'Item'} "
            f"{reserve or ''} {payload.get('client') or ''}"
        ).strip()
        body = (
            f"Date: {selected_date.isoformat()}\n"
            f"Pickup: {payload.get('pickup') or ''}\n"
            f"Driver: {payload.get('driver') or ''}\n"
            f"Status: {payload.get('status') or ''}\n"
            f"Alerts: {payload.get('alerts') or ''}\n"
            "Created from Dispatcher Calendar Day View."
        )
        if self._create_outlook_task(
            subject=subject,
            body=body,
            due_date=selected_date,
        ):
            QMessageBox.information(
                self,
                "Outlook Task",
                "Posted selected row as an Outlook task.",
            )

    @pyqtSlot()
    def _add_selected_to_todo_and_post_outlook_task(self) -> None:
        payload = self._selected_row_payload()
        if not payload:
            QMessageBox.information(
                self,
                "Add + Outlook Task",
                "Select a day-view row first.",
            )
            return

        if not self._insert_todo_for_payload(payload):
            return

        selected_date = self.calendar.selectedDate().toPyDate()
        reserve = payload.get("reserve", "")
        subject = (
            f"Dispatch: {payload.get('entry_type') or 'Item'} "
            f"{reserve or ''} {payload.get('client') or ''}"
        ).strip()
        body = (
            f"Date: {selected_date.isoformat()}\n"
            f"Pickup: {payload.get('pickup') or ''}\n"
            f"Driver: {payload.get('driver') or ''}\n"
            f"Status: {payload.get('status') or ''}\n"
            f"Alerts: {payload.get('alerts') or ''}\n"
            "Created from Dispatcher Calendar Day View."
        )
        posted = self._create_outlook_task(
            subject=subject,
            body=body,
            due_date=selected_date,
        )

        self._load_day(self.calendar.selectedDate())
        if posted:
            QMessageBox.information(
                self,
                "Add + Outlook Task",
                "Added to daily to-do list and posted as Outlook task.",
            )

    @pyqtSlot()
    def _add_selected_to_todo_and_post_arrow_new(self) -> None:
        payload = self._selected_row_payload()
        if not payload:
            QMessageBox.information(
                self,
                "Add + Arrow Calendar",
                "Select a day-view row first.",
            )
            return

        if not self._insert_todo_for_payload(payload):
            return

        cal_posted = self._post_payload_to_arrow_new(payload, quiet=True)
        self._load_day(self.calendar.selectedDate())
        if cal_posted:
            QMessageBox.information(
                self,
                "Add + Arrow Calendar",
                "Added to daily to-do list and posted to Arrow Calendar.",
            )
        else:
            QMessageBox.warning(
                self,
                "Add + Arrow Calendar",
                "Added to daily to-do list, but Arrow Calendar posting failed.",
            )

    @pyqtSlot()
    def _run_selected_combined_action(self) -> None:
        mode = str(self.combo_combined_mode.currentData() or "TODO_TASK")
        if mode == "TODO_TASK":
            self._add_selected_to_todo_and_post_outlook_task()
            return
        if mode == "TODO_ARROW":
            self._add_selected_to_todo_and_post_arrow_new()
            return
        self._add_selected_to_todo_post_task_and_calendar()

    @pyqtSlot()
    def _add_selected_to_todo_post_task_and_calendar(self) -> None:
        payload = self._selected_row_payload()
        if not payload:
            QMessageBox.information(
                self,
                "To-Do + Task + Arrow Calendar",
                "Select a day-view row first.",
            )
            return

        if not self._insert_todo_for_payload(payload):
            return

        selected_date = self.calendar.selectedDate().toPyDate()
        reserve = payload.get("reserve", "")
        subject = (
            f"Dispatch: {payload.get('entry_type') or 'Item'} "
            f"{reserve or ''} {payload.get('client') or ''}"
        ).strip()
        body = (
            f"Date: {selected_date.isoformat()}\n"
            f"Pickup: {payload.get('pickup') or ''}\n"
            f"Driver: {payload.get('driver') or ''}\n"
            f"Status: {payload.get('status') or ''}\n"
            f"Alerts: {payload.get('alerts') or ''}\n"
            "Created from Dispatcher Calendar Day View."
        )
        task_posted = self._create_outlook_task(
            subject=subject,
            body=body,
            due_date=selected_date,
        )
        cal_posted = self._post_payload_to_arrow_new(payload, quiet=True)

        self._load_day(self.calendar.selectedDate())
        if task_posted and cal_posted:
            QMessageBox.information(
                self,
                "To-Do + Task + Arrow Calendar",
                "Added to daily to-do list and posted to Outlook task + Arrow Calendar.",
            )
        elif task_posted or cal_posted:
            QMessageBox.information(
                self,
                "To-Do + Task + Arrow Calendar",
                "Added to daily to-do list. One Outlook post succeeded.",
            )
        else:
            QMessageBox.warning(
                self,
                "To-Do + Task + Arrow Calendar",
                "Added to daily to-do list, but Outlook posting failed.",
            )

    @pyqtSlot()
    def _post_selected_todo_to_outlook_task(self) -> None:
        payload = self._selected_todo_payload()
        if not payload:
            QMessageBox.information(
                self,
                "Outlook Task",
                "Select a to-do item first.",
            )
            return

        due_date = self._parse_task_due_date(payload.get("date", ""))
        reserve = payload.get("reserve", "")
        subject = (
            f"To-Do: {payload.get('text') or 'Dispatch Task'}"
            f" {f'(Reserve {reserve})' if reserve else ''}"
        ).strip()
        body = (
            f"Task ID: {payload.get('task_id') or ''}\n"
            f"Reserve: {reserve or ''}\n"
            f"Status: {payload.get('status') or ''}\n"
            f"Date: {due_date.isoformat()}\n"
            "Created from ALMS Daily To-Do panel."
        )
        if self._create_outlook_task(
            subject=subject,
            body=body,
            due_date=due_date,
        ):
            QMessageBox.information(
                self,
                "Outlook Task",
                "Posted selected to-do as an Outlook task.",
            )

    def _extract_reserve_number(self, text: str) -> str:
        """Extract reserve number from free-form Outlook text."""
        if not text:
            return ""
        match = re.search(r"\b(\d{5,6})\b", text)
        if not match:
            return ""
        return match.group(1).zfill(6)

    def _get_outlook_namespace(self) -> object | None:
        """Return the Outlook MAPI namespace when pywin32 is available."""
        try:
            import win32com.client
        except ModuleNotFoundError:
            return None

        return win32com.client.Dispatch("Outlook.Application").GetNamespace(
            "MAPI"
        )

    def _find_outlook_calendar_folder(
        self, calendar_name: str = "arrow new"
    ) -> object | None:
        """Find calendar folder by name across all Outlook stores."""
        namespace = self._get_outlook_namespace()
        if namespace is None:
            return None

        def normalize_name(value: str) -> str:
            return re.sub(r"[^a-z0-9]", "", (value or "").strip().lower())

        target_name = (calendar_name or "").strip().lower()
        target_norm = normalize_name(target_name)

        def name_matches(folder_name: str) -> bool:
            candidate = (folder_name or "").strip().lower()
            if not candidate:
                return False
            if candidate == target_name:
                return True

            candidate_norm = normalize_name(candidate)
            if not candidate_norm:
                return False

            # Outlook can include punctuation/spacing differences.
            return (
                candidate_norm == target_norm
                or target_norm in candidate_norm
                or candidate_norm in target_norm
            )

        def walk(folder) -> object | None:
            if folder is None:
                return None

            try:
                folder_name = str(getattr(folder, "Name", "")).strip().lower()
            except Exception:
                folder_name = ""

            if name_matches(folder_name):
                return folder

            try:
                children = getattr(folder, "Folders", None)
                if children is None:
                    return None
                for idx in range(1, children.Count + 1):
                    try:
                        child = children.Item(idx)
                    except Exception:
                        # Skip inaccessible child folders and keep scanning.
                        continue
                    found = walk(child)
                    if found is not None:
                        return found
            except Exception:
                return None
            return None

        try:
            stores = getattr(namespace, "Stores", None)
            if stores is not None:
                for idx in range(1, stores.Count + 1):
                    try:
                        root_folder = stores.Item(idx).GetRootFolder()
                    except Exception:
                        continue
                    found = walk(root_folder)
                    if found is not None:
                        return found
        except Exception:
            pass

        try:
            root_folders = getattr(namespace, "Folders", None)
            if root_folders is not None:
                for idx in range(1, root_folders.Count + 1):
                    try:
                        root_folder = root_folders.Item(idx)
                    except Exception:
                        continue
                    found = walk(root_folder)
                    if found is not None:
                        return found
        except Exception:
            pass

        try:
            default_calendar = namespace.GetDefaultFolder(9)
            if default_calendar is not None:
                logger.warning(
                    "Outlook calendar '%s' not found; using default calendar '%s'.",
                    calendar_name,
                    str(getattr(default_calendar, "Name", "")),
                )
                return default_calendar
        except Exception:
            pass

        return None

    def _collect_outlook_events(
        self, start_dt: datetime, end_dt: datetime
    ) -> tuple[object | None, dict[str, dict] | None, list[dict]]:
        """Collect Arrow New appointments and map by reserve number."""
        folder = self._find_outlook_calendar_folder("arrow new")
        if folder is None:
            return None, None, []

        reserve_map = {}
        events = []
        items = folder.Items
        items.IncludeRecurrences = True
        items.Sort("[Start]")

        restriction = (
            "[Start] >= '{start}' AND [Start] <= '{end}'".format(
                start=start_dt.strftime("%m/%d/%Y %H:%M"),
                end=end_dt.strftime("%m/%d/%Y %H:%M"),
            )
        )
        try:
            scoped_items = items.Restrict(restriction)
        except Exception:
            scoped_items = items

        count = 0
        for item in scoped_items:
            try:
                if getattr(item, "Class", None) != 26:
                    continue
                subject = str(getattr(item, "Subject", "") or "")
                body = str(getattr(item, "Body", "") or "")
                location = str(getattr(item, "Location", "") or "")
                start_val = getattr(item, "Start", None)
                entry_id = str(getattr(item, "EntryID", "") or "")

                reserve = self._extract_reserve_number(
                    f"{subject}\n{body}\n{location}"
                )
                event = {
                    "entry_id": entry_id,
                    "subject": subject,
                    "body": body,
                    "location": location,
                    "start": start_val,
                    "reserve_number": reserve,
                }
                events.append(event)
                if reserve and reserve not in reserve_map:
                    reserve_map[reserve] = event

                count += 1
                if count >= 10000:
                    break
            except Exception:
                continue

        return folder, reserve_map, events

    def _ensure_calendar_events_table(self, cur) -> None:
        """Ensure storage exists for non-booking/general Outlook events."""
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS calendar_events (
                id BIGSERIAL PRIMARY KEY,
                event_date DATE NOT NULL,
                event_time TIME NULL,
                event_title TEXT,
                driver_name TEXT,
                vehicle_type TEXT,
                event_notes TEXT,
                event_status VARCHAR(32) DEFAULT 'active',
                source VARCHAR(32) DEFAULT 'outlook',
                outlook_entry_id TEXT UNIQUE,
                reserve_number VARCHAR(16),
                classification VARCHAR(32) DEFAULT 'general',
                needs_manual_review BOOLEAN DEFAULT FALSE,
                review_reason TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_calendar_events_date
            ON calendar_events(event_date, event_time)
            """
        )

    def _is_quote_without_reserve(self, event: dict) -> bool:
        if event.get("reserve_number"):
            return False
        text = (
            f"{event.get('subject', '')}\n"
            f"{event.get('location', '')}\n"
            f"{event.get('body', '')}"
        )
        return bool(re.search(r"\bquote\b", text, re.IGNORECASE))

    def _extract_customer_from_subject(self, subject: str, reserve: str) -> str:
        text = str(subject or "").strip()
        if not text:
            return ""
        cleaned = re.sub(rf"\b{re.escape(str(reserve))}\b", "", text).strip()
        cleaned = re.sub(r"\s+-\s+", " ", cleaned).strip(" -")
        return cleaned or text

    def _build_event_notes(self, event: dict) -> str:
        parts = [
            f"Subject: {event.get('subject', '')}",
            f"Location: {event.get('location', '')}",
            f"Outlook Entry ID: {event.get('entry_id', '')}",
            "",
            str(event.get("body", "") or "").strip(),
        ]
        return "\n".join(parts).strip()

    def _upsert_general_calendar_event(
        self,
        event: dict,
        *,
        manual_review: bool,
        review_reason: str,
    ) -> None:
        start_val = event.get("start")
        event_date = start_val.date() if hasattr(start_val, "date") else None
        event_time = start_val.time() if hasattr(start_val, "time") else None
        if event_date is None:
            return

        entry_id = str(event.get("entry_id") or "").strip()
        title = str(event.get("subject") or "").strip()
        if not entry_id:
            entry_id = (
                f"auto::{event_date.isoformat()}::"
                f"{event_time or ''!s}::{title}"
            )
        notes = self._build_event_notes(event)

        with DatabaseContext(self.db, auto_commit=True) as cur:
            self._ensure_calendar_events_table(cur)
            cur.execute(
                """
                INSERT INTO calendar_events (
                    event_date,
                    event_time,
                    event_title,
                    event_notes,
                    event_status,
                    source,
                    outlook_entry_id,
                    reserve_number,
                    classification,
                    needs_manual_review,
                    review_reason,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, 'active', 'outlook', %s, %s,
                        %s, %s, %s, NOW())
                ON CONFLICT (outlook_entry_id)
                DO UPDATE SET
                    event_date = EXCLUDED.event_date,
                    event_time = EXCLUDED.event_time,
                    event_title = EXCLUDED.event_title,
                    event_notes = EXCLUDED.event_notes,
                    reserve_number = EXCLUDED.reserve_number,
                    classification = EXCLUDED.classification,
                    needs_manual_review = EXCLUDED.needs_manual_review,
                    review_reason = EXCLUDED.review_reason,
                    updated_at = NOW()
                """,
                (
                    event_date,
                    event_time,
                    title,
                    notes,
                    entry_id or None,
                    str(event.get("reserve_number") or "") or None,
                    "manual_review" if manual_review else "general",
                    manual_review,
                    review_reason,
                ),
            )

    def _get_latest_charter_by_reserve(
        self, reserve_number: str
    ) -> dict | None:
        reserve = str(reserve_number or "").strip()
        if not reserve:
            return None
        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT charter_id, reserve_number, charter_date, pickup_time,
                       outlook_entry_id
                FROM charters
                WHERE reserve_number = %s
                ORDER BY charter_id DESC
                LIMIT 1
                """,
                (reserve,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "charter_id": row[0],
            "reserve_number": str(row[1] or ""),
            "charter_date": row[2],
            "pickup_time": row[3],
            "outlook_entry_id": str(row[4] or ""),
        }

    def _mark_charter_mismatch(self, charter_id: int, reason: str) -> None:
        with DatabaseContext(self.db, auto_commit=True) as cur:
            cur.execute(
                """
                UPDATE charters
                SET calendar_sync_status = 'mismatch',
                    calendar_color = 'yellow',
                    calendar_notes = %s,
                    updated_at = NOW()
                WHERE charter_id = %s
                """,
                (reason, charter_id),
            )

    def _mark_charter_synced_from_event(
        self, charter_id: int, event: dict
    ) -> None:
        entry_id = str(event.get("entry_id") or "")
        note = (
            "Verified by full Outlook sync on "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        with DatabaseContext(self.db, auto_commit=True) as cur:
            cur.execute(
                """
                UPDATE charters
                SET calendar_sync_status = 'synced',
                    calendar_color = 'green',
                    outlook_entry_id = %s,
                    calendar_notes = %s,
                    updated_at = NOW()
                WHERE charter_id = %s
                """,
                (entry_id or None, note, charter_id),
            )

    def _sync_to_outlook(self, reserve_number: str, quiet: bool = False) -> bool:
        """Sync a single charter to Outlook calendar using COM directly."""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT reserve_number, charter_date, pickup_time,
                           client_display_name, calendar_notes, outlook_entry_id
                    FROM charters
                    WHERE reserve_number = %s
                    ORDER BY charter_id DESC
                    LIMIT 1
                    """,
                    (reserve_number,),
                )
                row = cur.fetchone()

            if not row:
                if not quiet:
                    QMessageBox.warning(
                        self,
                        "Sync Failed",
                        f"No charter found for reserve {reserve_number}.",
                    )
                return False

            reserve_number, charter_date, pickup_time, customer_name, notes, existing_entry_id = row
            folder = self._find_outlook_calendar_folder("arrow new")
            if folder is None:
                if not quiet:
                    QMessageBox.warning(
                        self,
                        "Sync Failed",
                        (
                            "Outlook integration is unavailable or could not "
                            "find calendar 'arrow new'."
                        ),
                    )
                return False

            namespace = self._get_outlook_namespace()
            if namespace is None:
                if not quiet:
                    QMessageBox.warning(
                        self,
                        "Sync Failed",
                        (
                            "Outlook review requires the pywin32 package, "
                            "which is not installed in this build."
                        ),
                    )
                return False

            appt = None
            if existing_entry_id:
                try:
                    appt = namespace.GetItemFromID(existing_entry_id)
                except Exception:
                    appt = None
            if appt is None:
                appt = folder.Items.Add(1)  # olAppointmentItem

            start_time = pickup_time or time(9, 0)
            start_dt = datetime.combine(charter_date, start_time)
            end_dt = start_dt + timedelta(hours=1)
            subject = f"Reserve {reserve_number} - {customer_name or 'Charter'}"

            appt.Subject = subject
            appt.Start = start_dt
            appt.End = end_dt
            appt.Location = ""
            appt.Body = (
                f"Reserve: {reserve_number}\n"
                f"Customer: {customer_name or ''}\n\n"
                f"{notes or ''}"
            )
            appt.Categories = "ALMS"
            appt.Save()

            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    UPDATE charters
                    SET calendar_sync_status = 'synced',
                        calendar_color = 'blue',
                        outlook_entry_id = %s,
                        calendar_notes = %s
                    WHERE reserve_number = %s
                    """,
                    (
                        str(getattr(appt, "EntryID", "") or ""),
                        f"Synced to Arrow New at {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                        reserve_number,
                    ),
                )

            if not quiet:
                QMessageBox.information(
                    self,
                    "Sync Success",
                    f"Reserve {reserve_number} synced to Arrow New Outlook calendar.",
                )
                self._load_day(self.calendar.selectedDate())
            return True
        except Exception as e:
            if not quiet:
                QMessageBox.warning(
                    self, "Sync Error", f"Error syncing to Outlook: {e}"
                )
            return False

    def _view_sync_details(self, reserve_number: str) -> None:
        """Show calendar_notes and sync status details."""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT calendar_sync_status, calendar_color,
                    calendar_notes, outlook_entry_id
                    FROM charters
                    WHERE reserve_number = %s
                """,
                    (reserve_number,),
                )
                row = cur.fetchone()

                if row:
                    status, color, notes, entry_id = row
                    details = f"Reserve Number: {reserve_number}\n\n"
                    details += f"Sync Status: {status or 'unknown'}\n"
                    details += f"Color Code: {color or 'none'}\n"
                    details += f"Outlook Entry ID: {entry_id or 'none'}\n\n"
                    details += f"Notes:\n{notes or 'No notes available'}"

                    QMessageBox.information(self, "Sync Details", details)
                else:
                    QMessageBox.warning(
                        self,
                        "Not Found",
                        f"Reserve {reserve_number} not found",
                    )
        except Exception as e:
            logger.error(
                f"Failed to load sync details for {reserve_number}: {e}"
            )
            QMessageBox.warning(self, "Error", f"Failed to load details: {e}")

    def _mark_mismatch(self, reserve_number: str) -> None:
        """Manually mark a charter as mismatch for re-verification."""
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    UPDATE charters
                    SET calendar_sync_status = 'mismatch',
                        calendar_color = 'yellow',
                        calendar_notes = 'Manually marked for verification'
                    WHERE reserve_number = %s
                """,
                    (reserve_number,),
                )
            QMessageBox.information(
                self, "Updated", f"Reserve {reserve_number} marked as mismatch"
            )
            self._load_day(self.calendar.selectedDate())
        except Exception as e:
            logger.error(f"Failed to mark mismatch for {reserve_number}: {e}")
            QMessageBox.warning(self, "Error", f"Failed to update: {e}")

    def _refresh_sync_status(self) -> None:
        """Refresh sync statuses by scanning Arrow New appointments directly."""
        try:
            selected_date = self.calendar.selectedDate()
            start_date = datetime(selected_date.year(), selected_date.month(), 1)
            if selected_date.month() == 12:
                end_date = datetime(selected_date.year() + 1, 1, 1) - timedelta(seconds=1)
            else:
                end_date = datetime(selected_date.year(), selected_date.month() + 1, 1) - timedelta(seconds=1)

            _, reserve_map, _ = self._collect_outlook_events(start_date, end_date)
            if reserve_map is None:
                QMessageBox.warning(
                    self,
                    "Refresh Failed",
                    "Could not find Outlook calendar 'arrow new'.",
                )
                return

            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    SELECT reserve_number
                    FROM charters
                    WHERE charter_date BETWEEN %s AND %s
                      AND (status IS NULL OR status NOT IN ('cancelled','no-show'))
                    """,
                    (start_date.date(), end_date.date()),
                )
                reserves = [str(r[0]) for r in cur.fetchall() if r and r[0]]

                synced = 0
                missing = 0
                for reserve in reserves:
                    evt = reserve_map.get(str(reserve).zfill(6))
                    if evt:
                        cur.execute(
                            """
                            UPDATE charters
                            SET calendar_sync_status = 'synced',
                                calendar_color = 'green',
                                outlook_entry_id = %s,
                                calendar_notes = %s
                            WHERE reserve_number = %s
                            """,
                            (
                                evt.get("entry_id") or "",
                                f"Arrow New match: {evt.get('subject', '')}",
                                reserve,
                            ),
                        )
                        synced += 1
                    else:
                        cur.execute(
                            """
                            UPDATE charters
                            SET calendar_sync_status = 'not_in_calendar',
                                calendar_color = 'red',
                                calendar_notes = %s
                            WHERE reserve_number = %s
                            """,
                            (
                                "No Arrow New match during refresh",
                                reserve,
                            ),
                        )
                        missing += 1

            QMessageBox.information(
                self,
                "Refresh Complete",
                f"Sync status refreshed. Synced: {synced}, Not in calendar: {missing}.",
            )
            self._load_day(self.calendar.selectedDate())
        except Exception as e:
            logger.error(f"Failed to refresh sync status: {e}")
            QMessageBox.warning(
                self, "Refresh Error", f"Error refreshing: {e}"
            )

    @pyqtSlot()
    def _show_color_legend(self) -> None:
        """Display explanation of Outlook sync color indicators."""
        legend = """Outlook Sync Color Legend:

🟢 Green = Synced
   Charter perfectly matches Outlook calendar appointment.
   No action needed.

🔴 Red = Not in Calendar
   Charter exists in database but no Outlook appointment found.
   Right-click → "Sync to Outlook Now" to create.

🟡 Yellow = Mismatch
   Charter exists but details differ (driver, time, location).
   Right-click → "View Mismatch Details" for specifics.

🔵 Blue = Recently Updated
   Charter was just synced to Outlook.
   Will turn green after next verification run.

⚫ Gray = Cancelled
   Charter or appointment has been cancelled.

⚪ White = Unknown
   Sync status not yet determined.
   Run "Refresh Sync Status" to update.
"""
        QMessageBox.information(self, "Outlook Sync Legend", legend)

    # ===== Outlook Parse & Review =====

    def _calendar_sync_lower_bound_date(self):
        """Return forward-only lower bound date for Arrow sync actions.

        Env override:
          - ALMS_ARROW_SYNC_SCOPE=today  -> today forward (default)
          - ALMS_ARROW_SYNC_SCOPE=week   -> this week forward (Mon)
        """
        today = datetime.now().date()
        scope = (os.getenv("ALMS_ARROW_SYNC_SCOPE", "today") or "today").strip().lower()
        if scope in {"week", "this_week", "week_forward"}:
            return today - timedelta(days=today.weekday())
        return today

    def _calendar_sync_scope_label(self) -> str:
        """Describe the visible forward-only Arrow sync scope."""
        scope = (os.getenv("ALMS_ARROW_SYNC_SCOPE", "today") or "today").strip().lower()
        if scope in {"week", "this_week", "week_forward"}:
            return "this week forward"
        return "today forward"

    def _apply_forward_sync_window(self, month_start: datetime, month_end: datetime):
        """Clamp month window to forward-only sync bounds."""
        lower = self._calendar_sync_lower_bound_date()
        effective_start = max(month_start, datetime.combine(lower, time(0, 0)))
        return effective_start, month_end

    @pyqtSlot()
    def _parse_outlook_and_review(self) -> None:
        """Full month sync from Outlook into ALMS review data and charters."""
        try:
            selected_date = self.calendar.selectedDate()
            start_date = datetime(selected_date.year(), selected_date.month(), 1)
            if selected_date.month() == 12:
                end_date = datetime(selected_date.year() + 1, 1, 1) - timedelta(seconds=1)
            else:
                end_date = datetime(selected_date.year(), selected_date.month() + 1, 1) - timedelta(seconds=1)

            start_date, end_date = self._apply_forward_sync_window(start_date, end_date)
            if start_date > end_date:
                QMessageBox.information(
                    self,
                    "Compare Arrow to ALMS",
                    "No forward dates in this month to compare.",
                )
                return

            _, reserve_map, events = self._collect_outlook_events(start_date, end_date)
            if reserve_map is None:
                QMessageBox.warning(
                    self,
                    "Outlook Parse",
                    "Could not find Outlook calendar 'arrow new'.",
                )
                return

            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT reserve_number
                    FROM charters
                    WHERE charter_date BETWEEN %s AND %s
                      AND (status IS NULL OR status NOT IN ('cancelled','no-show'))
                    """,
                    (start_date.date(), end_date.date()),
                )
                reserves = [str(r[0]).zfill(6) for r in cur.fetchall() if r and r[0]]

            reserve_set = set(reserves)
            matched = sum(1 for reserve in reserves if reserve in reserve_map)
            unmatched_charters = len(reserves) - matched

            created_charters = 0
            verified_charter_events = 0
            general_events_added = 0
            quotes_marked_review = 0
            mismatched_charter_events = 0
            duplicate_reserve_events = 0
            seen_event_reserves = set()

            for event in events:
                reserve = str(event.get("reserve_number") or "").strip()
                if reserve.isdigit():
                    reserve = reserve.zfill(6)
                start_val = event.get("start")
                pickup_text = (
                    start_val.strftime("%H:%M")
                    if hasattr(start_val, "strftime")
                    else ""
                )

                if reserve:
                    if reserve in seen_event_reserves:
                        duplicate_reserve_events += 1
                        self._upsert_general_calendar_event(
                            event,
                            manual_review=True,
                            review_reason=(
                                "Duplicate Outlook events share reserve "
                                f"{reserve}; manual review required"
                            ),
                        )
                        continue
                    seen_event_reserves.add(reserve)

                    existing = self._get_latest_charter_by_reserve(reserve)
                    if existing:
                        verified_charter_events += 1

                        event_date = (
                            start_val.date()
                            if hasattr(start_val, "date")
                            else None
                        )
                        event_time = (
                            start_val.strftime("%H:%M")
                            if hasattr(start_val, "strftime")
                            else ""
                        )
                        charter_date = existing.get("charter_date")
                        charter_time = existing.get("pickup_time")
                        charter_time_hhmm = (
                            charter_time.strftime("%H:%M")
                            if hasattr(charter_time, "strftime")
                            else ""
                        )

                        if (
                            (event_date and charter_date and event_date != charter_date)
                            or (
                                event_time
                                and charter_time_hhmm
                                and event_time != charter_time_hhmm
                            )
                        ):
                            mismatched_charter_events += 1
                            self._mark_charter_mismatch(
                                int(existing["charter_id"]),
                                (
                                    "Outlook reserve matches existing charter but "
                                    "date/time differs. "
                                    f"Outlook={event_date} {event_time}, "
                                    f"ALMS={charter_date} {charter_time_hhmm}"
                                ),
                            )
                        else:
                            self._mark_charter_synced_from_event(
                                int(existing["charter_id"]),
                                event,
                            )
                        reserve_set.add(reserve)
                        continue

                    details = {
                        "customer_name": self._extract_customer_from_subject(
                            str(event.get("subject") or ""), reserve
                        ),
                        "booking_type": "Booking",
                        "outlook_entry_id": str(event.get("entry_id") or ""),
                    }
                    created, _charter_id = self._ensure_calendar_placeholder_charter(
                        reserve,
                        pickup_text,
                        self._build_event_notes(event),
                        details,
                        status_hint="Booked",
                    )
                    if created:
                        created_charters += 1
                        reserve_set.add(reserve)
                    continue

                is_quote = self._is_quote_without_reserve(event)
                reason = (
                    "Quote event missing reserve number; manual review required"
                    if is_quote
                    else ""
                )
                self._upsert_general_calendar_event(
                    event,
                    manual_review=is_quote,
                    review_reason=reason,
                )
                if is_quote:
                    quotes_marked_review += 1
                else:
                    general_events_added += 1

            events_with_reserve = sum(1 for e in events if e.get("reserve_number"))
            events_without_reserve = len(events) - events_with_reserve

            scope_lower = start_date.date()
            summary = "Arrow to ALMS compare complete.\n\n"
            summary += f"Scope start: {scope_lower} (forward only)\n"
            summary += f"ALMS charters in scope: {len(reserves)}\n"
            summary += f"Matched by reserve number: {matched}\n"
            summary += f"Unmatched charters: {unmatched_charters}\n"
            summary += f"Arrow Calendar events scanned: {len(events)}\n"
            summary += f"Events with reserve number: {events_with_reserve}\n"
            summary += f"Events without reserve number: {events_without_reserve}\n"
            summary += f"Verified charter events: {verified_charter_events}\n"
            summary += f"New charters created from calendar: {created_charters}\n"
            summary += f"General calendar events added/updated: {general_events_added}\n"
            summary += f"Quote events flagged for manual review: {quotes_marked_review}\n"
            summary += f"Reserve date/time mismatches flagged: {mismatched_charter_events}\n"
            summary += f"Duplicate reserve events flagged: {duplicate_reserve_events}\n"
            summary += "Auto-generated reserve numbers used: 0"

            QMessageBox.information(self, "Compare Arrow to ALMS", summary)
            self._load_day(self.calendar.selectedDate())
            # Refresh the sync review tab so new items appear immediately
            try:
                self._load_sync_review()
            except Exception:
                pass
        except Exception as e:
            QMessageBox.warning(
                self, "Compare Arrow to ALMS", f"Error during Outlook review: {e}"
            )

    def _update_calendar_individual_approval(self) -> None:
        """
        Compare ALMS charters with Outlook calendar and request individual
        approval
        for each discrepancy before updating.
        """
        try:

            # Get current date range (visible month)
            selected_date = self.calendar.selectedDate()
            start_date = QDate(selected_date.year(), selected_date.month(), 1)
            if selected_date.month() == 12:
                end_date = QDate(selected_date.year() + 1, 1, 1).addDays(-1)
            else:
                end_date = QDate(
                    selected_date.year(), selected_date.month() + 1, 1
                ).addDays(-1)

            month_start_dt = datetime.combine(start_date.toPyDate(), time(0, 0))
            month_end_dt = datetime.combine(end_date.toPyDate(), time(23, 59))
            effective_start_dt, effective_end_dt = self._apply_forward_sync_window(
                month_start_dt,
                month_end_dt,
            )
            if effective_start_dt > effective_end_dt:
                QMessageBox.information(
                    self,
                    "Sync Arrow Calendar",
                    "No forward dates in this month to sync.",
                )
                return

            effective_start_date = effective_start_dt.date()
            effective_end_date = effective_end_dt.date()

            _, reserve_map, outlook_events = self._collect_outlook_events(
                effective_start_dt,
                effective_end_dt,
            )
            if reserve_map is None:
                QMessageBox.warning(
                    self,
                    "Outlook Extract",
                    "Could not find Outlook calendar 'arrow new'.",
                )
                return

            # Get ALMS charters for date range
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT reserve_number, charter_date, pickup_time,
                           client_display_name,
                           vehicle_id, employee_id, calendar_notes,
                           calendar_sync_status,
                           outlook_entry_id
                    FROM charters
                    WHERE charter_date BETWEEN %s AND %s
                      AND (status IS NULL OR status NOT IN
                          ('cancelled','no-show'))
                    ORDER BY charter_date, pickup_time
                """,
                    (effective_start_date, effective_end_date),
                )

                alms_charters = cur.fetchall()

            # Find discrepancies
            discrepancies = []
            outlook_dict = {
                evt.get("reserve_number"): evt
                for evt in outlook_events
                if evt.get("reserve_number")
            }

            for charter in alms_charters:
                (
                    reserve_num,
                    date,
                    pickup,
                    customer,
                    vehicle_id,
                    employee_id,
                    notes,
                    sync_status,
                    outlook_id,
                ) = charter

                # Find matching Outlook event
                outlook_match = None
                reserve_key = str(reserve_num).zfill(6)
                if reserve_key in outlook_dict:
                    outlook_match = outlook_dict[reserve_key]
                elif outlook_id:
                    outlook_match = next(
                        (
                            e
                            for e in outlook_events
                            if e.get("entry_id") == outlook_id
                        ),
                        None,
                    )

                # Compare fields
                if outlook_match:
                    differences = []

                    # Compare date
                    outlook_start = outlook_match.get("start")
                    outlook_date = (
                        outlook_start.date().isoformat()
                        if hasattr(outlook_start, "date")
                        else ""
                    )
                    if str(date) != str(outlook_date):
                        differences.append(
                            f"Date: ALMS={date}, Outlook={outlook_date}"
                        )

                    # Compare time
                    outlook_time = (
                        outlook_start.strftime("%H:%M")
                        if hasattr(outlook_start, "strftime")
                        else ""
                    )
                    if str(pickup or "")[:5] != outlook_time:
                        differences.append(
                            f"Time: ALMS={pickup}, Outlook={outlook_time}"
                        )

                    # Compare location
                    alms_location = notes.split("\n")[0] if notes else ""
                    outlook_location = outlook_match.get("location", "")
                    if (
                        alms_location
                        and outlook_location
                        and alms_location != outlook_location
                    ):
                        differences.append(
                            f"Location: ALMS={alms_location},"
                            f"Outlook={outlook_location}"
                        )

                    if differences:
                        discrepancies.append(
                            {
                                "reserve_number": reserve_num,
                                "charter_date": str(date),
                                "customer": customer,
                                "differences": differences,
                                "alms_data": charter,
                                "outlook_data": outlook_match,
                            }
                        )
                else:
                    # Charter exists in ALMS but not in Outlook
                    discrepancies.append(
                        {
                            "reserve_number": reserve_num,
                            "charter_date": str(date),
                            "customer": customer,
                            "differences": [
                                "Charter not found in Outlook calendar"
                            ],
                            "alms_data": charter,
                            "outlook_data": None,
                        }
                    )

            if not discrepancies:
                QMessageBox.information(
                    self,
                    "Calendar Sync",
                    "No discrepancies found between ALMS and Arrow"
                    " in forward-only scope.",
                )
                return

            # Show individual approval dialog for each discrepancy
            approved_updates = []
            skipped_updates = []

            for i, disc in enumerate(discrepancies, 1):
                reply = self._show_discrepancy_approval_dialog(
                    disc, i, len(discrepancies)
                )

                if reply == "approve":
                    approved_updates.append(disc)
                elif reply == "skip":
                    skipped_updates.append(disc)
                elif reply == "cancel":
                    break

            # Apply approved updates
            if approved_updates:
                self._apply_calendar_updates(approved_updates)
                QMessageBox.information(
                    self,
                    "Updates Applied",
                    f"Updated {len(approved_updates)} calendar events "
                    f"({effective_start_date} to {effective_end_date}).\n"
                    f"Skipped {len(skipped_updates)} events.",
                )
            else:
                QMessageBox.information(
                    self, "No Updates", "No updates were approved."
                )

            # Reload view
            self._load_day(self.calendar.selectedDate())

        except Exception as e:
            logger.error(f"Failed during calendar update: {e}")
            QMessageBox.warning(
                self, "Calendar Update", f"Error during calendar update: {e}"
            )

    def _show_discrepancy_approval_dialog(
        self, discrepancy, current, total
    ) -> str:
        """Show dialog asking for approval of individual calendar update"""
        from PyQt6.QtWidgets import QDialog

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Calendar Update Approval ({current}/{total})")
        dialog.setMinimumWidth(600)

        layout = QVBoxLayout()

        # Title
        title = QLabel(
            f"<b>Reserve #{discrepancy['reserve_number']} -"
            f"{discrepancy['customer']}</b>"
        )
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        # Discrepancies
        disc_group = QGroupBox("Discrepancies Found")
        disc_layout = QVBoxLayout()

        for diff in discrepancy["differences"]:
            diff_label = QLabel(f"⚠️ {diff}")
            diff_label.setStyleSheet("color: red;")
            disc_layout.addWidget(diff_label)

        disc_group.setLayout(disc_layout)
        layout.addWidget(disc_group)

        # Action question
        question = QLabel("<b>Update Outlook calendar to match ALMS data?</b>")
        layout.addWidget(question)

        # Buttons
        button_layout = QHBoxLayout()

        approve_btn = QPushButton("✅ Approve Update")
        approve_btn.clicked.connect(lambda: dialog.done(1))
        button_layout.addWidget(approve_btn)

        skip_btn = QPushButton("⏭️ Skip This One")
        skip_btn.clicked.connect(lambda: dialog.done(2))
        button_layout.addWidget(skip_btn)

        cancel_btn = QPushButton("❌ Cancel All")
        cancel_btn.clicked.connect(lambda: dialog.done(0))
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)
        dialog.setLayout(layout)

        result = dialog.exec()
        if result == 1:
            return "approve"
        elif result == 2:
            return "skip"
        else:
            return "cancel"

    def _apply_calendar_updates(self, approved_updates) -> None:
        """Apply approved calendar updates to Outlook."""
        for update in approved_updates:
            reserve_num = str(update.get("reserve_number") or "").zfill(6)
            try:
                ok = self._sync_to_outlook(reserve_num, quiet=True)
                if not ok:
                    logger.error(f"Failed to update {reserve_num}")
            except Exception as e:
                logger.error(
                    f"Error updating {update.get('reserve_number')}: {e}"
                )

    def _open_booking_from_calendar(self, row, column) -> None:
        """
        Double-click handler: Open calendar event details dialog.
        Shows event information and action options:
        - View/edit calendar details
        - Open charter (if exists)
        - Open employee calendar (if driver event)
        - Add to new booking
        - Set alerts
        """
        try:
            # Get event data from table
            reserve_item = self.day_table.item(row, 0)
            reserve_number = reserve_item.text() if reserve_item else ""

            type_item = self.day_table.item(row, 2)
            event_type = type_item.text() if type_item else ""

            charter_id_item = self.day_table.item(row, 3)
            charter_id = charter_id_item.text() if charter_id_item else ""

            pickup_item = self.day_table.item(row, 4)
            pickup_time = pickup_item.text() if pickup_item else ""

            depart_item = self.day_table.item(row, 6)
            depart_time = depart_item.text() if depart_item else ""

            vehicle_item = self.day_table.item(row, 7)
            vehicle = vehicle_item.text() if vehicle_item else ""

            driver_item = self.day_table.item(row, 8)
            driver = driver_item.text() if driver_item else ""

            status_item = self.day_table.item(row, 9)
            status = status_item.text() if status_item else ""

            outlook_item = self.day_table.item(row, 10)
            outlook_status = outlook_item.text() if outlook_item else ""

            alerts_item = self.day_table.item(row, 11)
            alerts = alerts_item.text() if alerts_item else ""

            # Get full event details from database
            date_str = self.calendar.selectedDate().toString("yyyy-MM-dd")
            event_details = self._get_event_details(
                date_str, pickup_time, reserve_number
            )

            # Show calendar event dialog
            self._show_calendar_event_dialog(
                reserve_number,
                charter_id,
                event_type,
                pickup_time,
                depart_time,
                vehicle,
                driver,
                status,
                outlook_status,
                alerts,
                event_details,
            )

        except Exception as e:
            logger.error(f"Failed to open calendar event: {e}")
            QMessageBox.warning(
                self, "Open Event", f"Failed to open calendar event: {e}"
            )

    def _get_event_details(self, date_str, pickup_time, reserve_number) -> dict:
        """Fetch full event details from database"""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                # Try to find event by reserve number first, then by date+time
                if reserve_number:
                    cur.execute(
                        """
                        SELECT calendar_notes, calendar_color,
                        calendar_sync_status,
                               client_display_name, charter_type, quote_expires_at
                        FROM charters
                        WHERE reserve_number = %s
                        LIMIT 1
                    """,
                        (reserve_number,),
                    )
                else:
                    # Convert date_str back to Python date if it's a string
                    # (from
                    # calendar.selectedDate().toString())
                    from datetime import date as py_date

                    date_param = (
                        py_date.fromisoformat(date_str)
                        if isinstance(date_str, str)
                        else date_str
                    )
                    cur.execute(
                        """
                        SELECT calendar_notes, calendar_color,
                        calendar_sync_status,
                               client_display_name, charter_type, quote_expires_at
                        FROM charters
                        WHERE charter_date = %s AND pickup_time = %s
                        LIMIT 1
                    """,
                        (date_param, pickup_time if pickup_time else None),
                    )

                row = cur.fetchone()
                if row:
                    return {
                        "calendar_notes": row[0] or "",
                        "calendar_color": row[1] or "",
                        "calendar_sync_status": row[2] or "",
                        "customer_name": row[3] or "",  # key kept for UI compat
                        "booking_type": row[4] or "",   # key kept for UI compat
                        "quote_expires_at": str(row[5]) if row[5] else "",
                    }
                return {}
        except Exception as e:
            logger.error("Error fetching event details: %s", e)
            return {}

    def _show_calendar_event_dialog(
        self,
        reserve_number,
        charter_id,
        event_type,
        pickup_time,
        depart_time,
        vehicle,
        driver,
        status,
        outlook_status,
        alerts,
        event_details,
    ) -> None:
        """Show dialog with calendar event details and action buttons"""
        from PyQt6.QtWidgets import QCheckBox, QDialog

        dialog = QDialog(self)
        dialog.setWindowTitle("Calendar Event Details")
        dialog.setMinimumWidth(600)
        dialog.resize(900, 620)
        dialog.setSizeGripEnabled(True)

        layout = QVBoxLayout()

        # Event Information Section
        info_group = QGroupBox("Event Information")
        info_layout = QFormLayout()

        info_layout.addRow(
            "Date:",
            QLabel(
                self.calendar.selectedDate().toString("dddd, MMMM d, yyyy")
            ),
        )
        info_layout.addRow("Type:", QLabel(event_type or "Calendar Event"))
        info_layout.addRow(
            "Reserve #:", QLabel(reserve_number or "None (Not Booked)")
        )
        info_layout.addRow("Charter ID:", QLabel(charter_id or "N/A"))
        info_layout.addRow("Status:", QLabel(status or "Not Scheduled"))
        info_layout.addRow("Pickup Time:", QLabel(pickup_time or "Not Set"))
        info_layout.addRow("Depart Yard:", QLabel(depart_time or "Not Set"))
        info_layout.addRow("Vehicle:", QLabel(vehicle or "Unassigned"))
        info_layout.addRow("Driver:", QLabel(driver or "Unassigned"))
        info_layout.addRow(
            "Outlook Sync:", QLabel(outlook_status or "Not Synced")
        )

        if alerts:
            alerts_label = QLabel(alerts)
            alerts_label.setStyleSheet("color: red; font-weight: bold;")
            info_layout.addRow("⚠️ Alerts:", alerts_label)

        if event_details.get("customer_name"):
            info_layout.addRow(
                "Customer:", QLabel(event_details["customer_name"])
            )

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Calendar Notes Section
        notes_group = QGroupBox("Calendar Notes / Email Data")
        notes_layout = QVBoxLayout()

        notes_edit = QTextEdit()
        notes_edit.setPlainText(event_details.get("calendar_notes", ""))
        notes_edit.setPlaceholderText(
            "Calendar notes, pasted email content, special instructions..."
        )
        notes_layout.addWidget(notes_edit)

        notes_group.setLayout(notes_layout)
        layout.addWidget(notes_group)

        # Alert Settings Section
        alerts_group = QGroupBox("Alert Settings")
        alerts_layout = QVBoxLayout()

        alert_prepayment = QCheckBox("⚠️ Prepayment Required")
        alert_vehicle = QCheckBox("⚠️ Specific Vehicle Required")
        alert_driver = QCheckBox("⚠️ Specific Driver Requested")
        alert_special = QCheckBox("⚠️ Special Requirements")

        alerts_layout.addWidget(alert_prepayment)
        alerts_layout.addWidget(alert_vehicle)
        alerts_layout.addWidget(alert_driver)
        alerts_layout.addWidget(alert_special)

        alerts_group.setLayout(alerts_layout)
        layout.addWidget(alerts_group)

        # Action Buttons
        actions_layout = QHBoxLayout()

        # Save Calendar Details button
        save_btn = QPushButton("💾 Save Calendar Details")
        save_btn.clicked.connect(
            lambda: self._save_calendar_details(
                reserve_number,
                charter_id,
                notes_edit.toPlainText(),
                alert_prepayment.isChecked(),
                dialog,
            )
        )
        actions_layout.addWidget(save_btn)

        # Open Charter button (if charter exists)
        if reserve_number:
            open_charter_btn = QPushButton("📋 Open Charter")
            open_charter_btn.clicked.connect(
                lambda: self._open_existing_charter_dialog(
                    reserve_number, charter_id, dialog
                )
            )
            actions_layout.addWidget(open_charter_btn)

        # Open Employee Calendar (if driver assigned)
        if driver and driver != "Unassigned":
            open_driver_btn = QPushButton("👤 Open Employee Calendar")
            open_driver_btn.clicked.connect(
                lambda: self._open_employee_calendar(driver, dialog)
            )
            actions_layout.addWidget(open_driver_btn)

        # Add to New Booking button
        add_booking_btn = QPushButton("➕ Add to New Booking")
        add_booking_btn.clicked.connect(
            lambda: self._create_charter_from_calendar_dialog(
                reserve_number,
                pickup_time,
                notes_edit.toPlainText(),
                event_details,
                dialog,
            )
        )
        actions_layout.addWidget(add_booking_btn)

        layout.addLayout(actions_layout)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.setLayout(layout)
        dialog.exec()

    def _save_calendar_details(
        self, reserve_number, charter_id, notes, prepayment_alert, dialog
    ) -> None:
        """Save calendar notes and alert settings"""
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                if reserve_number:
                    cur.execute(
                        """
                        UPDATE charters
                        SET calendar_notes = %s,
                            updated_at = NOW()
                        WHERE reserve_number = %s
                    """,
                        (notes, reserve_number),
                    )
                else:
                    # Update by date and time if no reserve number
                    date_str = self.calendar.selectedDate().toString(
                        "yyyy-MM-dd"
                    )
                    cur.execute(
                        """
                        UPDATE charters
                        SET calendar_notes = %s,
                            updated_at = NOW()
                        WHERE charter_date = %s
                        LIMIT 1
                    """,
                        (notes, date_str),
                    )

            QMessageBox.information(
                dialog, "Saved", "Calendar details saved successfully."
            )
            self._load_day(self.calendar.selectedDate())

        except Exception as e:
            logger.error(f"Failed to save calendar details: {e}")
            QMessageBox.warning(
                dialog, "Save Failed", f"Failed to save calendar details: {e}"
            )

    def _open_existing_charter_dialog(
        self, reserve_number, charter_id, parent_dialog
    ) -> None:
        """Open existing charter for editing"""
        try:
            self._open_existing_charter(reserve_number, charter_id)
            parent_dialog.accept()

        except Exception as e:
            logger.error(f"Failed to open charter: {e}")
            QMessageBox.warning(
                parent_dialog, "Open Charter", f"Failed to open charter: {e}"
            )

    def _open_employee_calendar(self, driver_name, parent_dialog) -> None:
        """Open a month view of charters assigned to the selected driver."""
        try:
            from PyQt6.QtWidgets import QDialog

            driver_label = (driver_name or "").strip()
            if not driver_label:
                QMessageBox.information(
                    parent_dialog,
                    "Employee Calendar",
                    "No driver name was provided for this event.",
                )
                return

            dialog = QDialog(self)
            dialog.setWindowTitle(f"Employee Calendar - {driver_label}")
            dialog.setMinimumWidth(900)
            dialog.resize(1100, 720)
            dialog.setSizeGripEnabled(True)

            layout = QVBoxLayout(dialog)
            header = QLabel(
                f"<b>Driver:</b> {driver_label}<br>"
                f"<b>Period:</b> {self.calendar.selectedDate().toString('MMMM yyyy')}"
            )
            header.setWordWrap(True)
            layout.addWidget(header)

            self._employee_calendar_table = QTableWidget(0, 6)
            self._employee_calendar_table.setHorizontalHeaderLabels(
                [
                    "Date",
                    "Reserve #",
                    "Pickup",
                    "Customer",
                    "Status",
                    "Charter ID",
                ]
            )
            hdr = self._employee_calendar_table.horizontalHeader()
            hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
            hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
            self._employee_calendar_table.setSelectionBehavior(
                QTableWidget.SelectionBehavior.SelectRows
            )
            self._employee_calendar_table.setSelectionMode(
                QTableWidget.SelectionMode.SingleSelection
            )
            self._employee_calendar_table.setEditTriggers(
                QTableWidget.EditTrigger.NoEditTriggers
            )
            self._employee_calendar_table.cellDoubleClicked.connect(
                self._open_employee_calendar_charter
            )
            layout.addWidget(self._employee_calendar_table)

            buttons = QHBoxLayout()
            refresh_btn = QPushButton("↺ Refresh")
            refresh_btn.clicked.connect(
                lambda: self._load_employee_calendar_rows(driver_label)
            )
            open_btn = QPushButton("📋 Open Charter")
            open_btn.clicked.connect(self._open_selected_employee_charter)
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dialog.accept)
            buttons.addWidget(refresh_btn)
            buttons.addWidget(open_btn)
            buttons.addStretch()
            buttons.addWidget(close_btn)
            layout.addLayout(buttons)

            self._employee_calendar_driver_label = driver_label
            self._load_employee_calendar_rows(driver_label)
            dialog.exec()
        except Exception as e:
            logger.error("Failed to open employee calendar: %s", e)
            QMessageBox.warning(
                parent_dialog,
                "Employee Calendar",
                f"Could not open employee calendar for {driver_name}: {e}",
            )

    def _load_employee_calendar_rows(self, driver_label: str) -> None:
        """Load this month's charters for the selected driver."""
        table = getattr(self, "_employee_calendar_table", None)
        if table is None:
            return

        selected_date = self.calendar.selectedDate()
        start_date = datetime(selected_date.year(), selected_date.month(), 1).date()
        if selected_date.month() == 12:
            end_date = datetime(selected_date.year() + 1, 1, 1).date() - timedelta(days=1)
        else:
            end_date = datetime(selected_date.year(), selected_date.month() + 1, 1).date() - timedelta(days=1)

        name_part = (driver_label or "").split("/")[0].strip() or (driver_label or "").strip()
        rows = []
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT c.charter_date, c.reserve_number, c.pickup_time,
                           c.client_display_name, c.status, c.charter_id
                    FROM charters c
                    LEFT JOIN employees e ON c.employee_id = e.employee_id
                    WHERE c.charter_date BETWEEN %s AND %s
                      AND (
                          e.full_name ILIKE %s
                          OR COALESCE(e.phone_number::text, '') ILIKE %s
                      )
                    ORDER BY c.charter_date, c.pickup_time NULLS LAST, c.charter_id
                    """,
                    (
                        start_date,
                        end_date,
                        f"%{name_part}%",
                        f"%{name_part}%",
                    ),
                )
                rows = cur.fetchall()
        except Exception as e:
            logger.error("Failed to load employee calendar rows: %s", e)
            QMessageBox.warning(
                self,
                "Employee Calendar",
                f"Could not load calendar rows for {driver_label}: {e}",
            )

        table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            charter_date, reserve_number, pickup_time, customer, status, charter_id = row
            values = [
                str(charter_date or ""),
                str(reserve_number or ""),
                str(pickup_time or ""),
                str(customer or ""),
                str(status or ""),
                str(charter_id or ""),
            ]
            for col_idx, value in enumerate(values):
                table.setItem(row_idx, col_idx, QTableWidgetItem(value))

    def _selected_employee_calendar_row(self) -> int | None:
        table = getattr(self, "_employee_calendar_table", None)
        if table is None:
            return None
        selection_model = table.selectionModel()
        if not selection_model:
            return None
        rows = selection_model.selectedRows()
        if not rows:
            return None
        return rows[0].row()

    def _open_selected_employee_charter(self) -> None:
        row = self._selected_employee_calendar_row()
        if row is None:
            QMessageBox.information(
                self,
                "Employee Calendar",
                "Select one charter row first.",
            )
            return
        self._open_employee_calendar_charter(row, 0)

    def _open_employee_calendar_charter(self, row: int, _column: int) -> None:
        table = getattr(self, "_employee_calendar_table", None)
        if table is None or row < 0 or row >= table.rowCount():
            return

        reserve_item = table.item(row, 1)
        charter_id_item = table.item(row, 5)
        reserve_number = reserve_item.text().strip() if reserve_item else ""
        charter_id = charter_id_item.text().strip() if charter_id_item else ""

        if not reserve_number and not charter_id:
            QMessageBox.information(
                self,
                "Employee Calendar",
                "This row has no charter reference to open.",
            )
            return

        try:
            from main import CharterFormWidget

            charter_form = CharterFormWidget(self.db)
            if reserve_number and hasattr(charter_form, "load_charter_by_reserve"):
                charter_form.load_charter_by_reserve(reserve_number)
            elif charter_id and hasattr(charter_form, "load_charter"):
                try:
                    charter_form.load_charter(int(charter_id))
                except Exception:
                    pass

            dialog = QDialog(self)
            dialog.setWindowTitle(f"Charter {reserve_number or charter_id}")
            dialog.setMinimumWidth(1100)
            dialog.resize(1200, 760)
            dialog.setSizeGripEnabled(True)
            layout = QVBoxLayout(dialog)
            layout.addWidget(charter_form)
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)
            dialog.exec()
        except Exception as e:
            logger.error("Failed to open charter from employee calendar: %s", e)
            QMessageBox.warning(
                self,
                "Open Charter",
                f"Could not open charter {reserve_number or charter_id}: {e}",
            )

    def _create_charter_from_calendar_dialog(
        self, reserve_number, pickup_time, notes, event_details, parent_dialog
    ) -> None:
        """Create new charter from calendar event"""
        try:
            from main import CharterFormWidget

            charter_form = CharterFormWidget(self.db)

            normalized_reserve = (reserve_number or "").strip()
            if normalized_reserve.isdigit():
                normalized_reserve = normalized_reserve.zfill(6)

            placeholder_created = False
            if normalized_reserve:
                placeholder_created, _charter_id = (
                    self._ensure_calendar_placeholder_charter(
                        normalized_reserve,
                        pickup_time,
                        notes,
                        event_details,
                    )
                )

                # Open exact reserve record so edits stay tied to calendar
                # reserve number.
                try:
                    charter_form.load_charter_by_reserve(normalized_reserve)
                except Exception:
                    pass

            # Auto-populate available information
            self._set_charter_form_datetime_from_calendar(
                charter_form,
                self.calendar.selectedDate(),
                pickup_time,
            )

            # Copy calendar notes to dispatch notes (confidential)
            if notes:
                notes_text = (
                    f"[From Calendar Event - "
                    f"{self.calendar.selectedDate().toString('yyyy-MM-dd')}]\n"
                    f"{notes}"
                )
                if hasattr(charter_form, "dispatch_notes_input"):
                    charter_form.dispatch_notes_input.setPlainText(notes_text)

            # Set customer name if available
            customer_name = event_details.get("customer_name", "")
            if customer_name and hasattr(charter_form, "customer_widget"):
                charter_form.customer_widget.search_input.setText(
                    customer_name
                )

            charter_form.show()
            parent_dialog.accept()

            QMessageBox.information(
                parent_dialog,
                "Create Booking",
                (
                    "Charter form opened with calendar data pre-populated.\n"
                    + (
                        f"Placeholder charter created for reserve "
                        f"{normalized_reserve}."
                        if placeholder_created
                        else (
                            f"Loaded existing charter reserve "
                            f"{normalized_reserve}."
                            if normalized_reserve
                            else ""
                        )
                    )
                ).strip(),
            )

        except Exception as e:
            logger.error(f"Failed to create charter from calendar: {e}")
            QMessageBox.warning(
                parent_dialog,
                "Create Charter",
                f"Failed to create charter: {e}",
            )

    def _parse_qtime(self, value) -> object | None:
        from PyQt6.QtCore import QTime

        if not value:
            return None
        txt = str(value).strip()
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                dt = datetime.strptime(txt, fmt)
                return QTime(dt.hour, dt.minute, dt.second)
            except Exception:
                continue
        return None

    def _set_charter_form_datetime_from_calendar(
        self,
        charter_form,
        selected_date: QDate,
        pickup_time,
    ) -> None:
        """Populate date/time fields regardless of widget class aliases."""
        from PyQt6.QtCore import QDateTime, QTime

        service_widget = getattr(charter_form, "service_date", None)
        if service_widget is not None and hasattr(service_widget, "setDate"):
            service_widget.setDate(selected_date)

        pickup_widget = getattr(charter_form, "pickup_time_input", None)
        if pickup_widget is None:
            return

        parsed_qtime = self._parse_qtime(pickup_time)
        if hasattr(pickup_widget, "setDateTime"):
            pickup_widget.setDateTime(
                QDateTime(selected_date, parsed_qtime or QTime(9, 0))
            )
        elif hasattr(pickup_widget, "setTime") and parsed_qtime is not None:
            pickup_widget.setTime(parsed_qtime)
        elif hasattr(pickup_widget, "setText") and pickup_time:
            pickup_widget.setText(str(pickup_time))

    def _parse_calendar_time(self, value) -> time | None:
        if not value:
            return None
        txt = str(value).strip()
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(txt, fmt).time()
            except Exception:
                continue
        return None

    def _ensure_calendar_placeholder_charter(
        self,
        reserve_number,
        pickup_time,
        notes,
        event_details,
        status_hint="Quote",
    ) -> tuple[bool, int | None]:
        """Ensure a minimal charter exists for this reserve number.

        Returns: (created_new: bool, charter_id: Optional[int])
        """
        reserve = (reserve_number or "").strip()
        if not reserve:
            return (False, None)
        if reserve.isdigit():
            reserve = reserve.zfill(6)

        charter_date = self.calendar.selectedDate().toPyDate()
        pickup_val = self._parse_calendar_time(pickup_time)
        customer_name = str(event_details.get("customer_name") or "").strip()
        event_type = str(event_details.get("booking_type") or "").strip()
        outlook_entry_id = str(event_details.get("outlook_entry_id") or "").strip()

        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        note_prefix = f"[Calendar placeholder {stamp}]"
        merged_notes = (
            f"{note_prefix}\n{str(notes).strip()}".strip()
            if notes
            else note_prefix
        )

        ccols = self._cols("charters")

        with DatabaseContext(self.db, auto_commit=True) as cur:
            cur.execute(
                """
                SELECT charter_id
                FROM charters
                WHERE reserve_number = %s
                ORDER BY charter_id DESC
                LIMIT 1
                """,
                (reserve,),
            )
            existing = cur.fetchone()
            if existing:
                return (False, int(existing[0]))

            insert_cols = ["reserve_number"]
            insert_vals = [reserve]

            if "charter_date" in ccols:
                insert_cols.append("charter_date")
                insert_vals.append(charter_date)

            if "pickup_time" in ccols and pickup_val is not None:
                insert_cols.append("pickup_time")
                insert_vals.append(pickup_val)

            if "status" in ccols:
                insert_cols.append("status")
                insert_vals.append(status_hint or "Quote")

            if "charter_type" in ccols and event_type:
                insert_cols.append("charter_type")
                insert_vals.append(event_type)

            if "client_display_name" in ccols and customer_name:
                insert_cols.append("client_display_name")
                insert_vals.append(customer_name)

            if "calendar_notes" in ccols:
                insert_cols.append("calendar_notes")
                insert_vals.append(merged_notes)
            elif "booking_notes" in ccols:
                insert_cols.append("booking_notes")
                insert_vals.append(merged_notes)
            elif "notes" in ccols:
                insert_cols.append("notes")
                insert_vals.append(merged_notes)

            if "calendar_sync_status" in ccols:
                insert_cols.append("calendar_sync_status")
                insert_vals.append("synced")
            if "calendar_color" in ccols:
                insert_cols.append("calendar_color")
                insert_vals.append("green")
            if "outlook_entry_id" in ccols and outlook_entry_id:
                insert_cols.append("outlook_entry_id")
                insert_vals.append(outlook_entry_id)

            col_sql = sql.SQL(", ").join(sql.Identifier(c) for c in insert_cols)
            val_sql = sql.SQL(", ").join(
                sql.Placeholder() for _ in insert_cols
            )
            cur.execute(
                sql.SQL(
                    "INSERT INTO charters ({}) VALUES ({}) RETURNING charter_id"
                ).format(col_sql, val_sql),
                insert_vals,
            )
            row = cur.fetchone()
            return (True, int(row[0]) if row else None)

    def _create_charter_from_calendar(self, row) -> None:
        """Create new charter from calendar event data"""
        try:
            # Get calendar event data
            date_str = self.calendar.selectedDate().toString("yyyy-MM-dd")
            pickup_item = self.day_table.item(row, 4)
            pickup_time = pickup_item.text() if pickup_item else ""

            # Get calendar notes if they exist
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT calendar_notes, calendar_color, client_display_name,
                    charter_type
                    FROM charters
                    WHERE charter_date = %s AND pickup_time = %s
                    LIMIT 1
                """,
                    (date_str, pickup_time if pickup_time else None),
                )

                event_data = cur.fetchone()
                calendar_notes = (
                    event_data[0] if event_data and event_data[0] else ""
                )
                event_data[1] if event_data and event_data[1] else ""
                customer_name = (
                    event_data[2] if event_data and event_data[2] else ""
                )
                event_data[3] if event_data and event_data[3] else ""

            # Import and create charter form
            from main import CharterFormWidget

            charter_form = CharterFormWidget(self.db)

            # Auto-populate available information
            self._set_charter_form_datetime_from_calendar(
                charter_form,
                self.calendar.selectedDate(),
                pickup_time,
            )

            # Copy calendar notes to dispatch notes (confidential)
            if calendar_notes:
                notes_text = f"[From Calendar Event]\n{calendar_notes}"
                if hasattr(charter_form, "dispatch_notes_input"):
                    charter_form.dispatch_notes_input.setPlainText(notes_text)

            # Set customer name if available
            if customer_name and hasattr(charter_form, "customer_widget"):
                # Try to find and select customer
                charter_form.customer_widget.search_input.setText(
                    customer_name
                )

            # Show form
            charter_form.show()

            QMessageBox.information(
                self,
                "Create Booking",
                "New charter form opened.\nCalendar data has been"
                "pre-populated.\n"
                "Complete the booking and save to link it to this calendar"
                "event.",
            )

        except Exception as e:
            logger.error(f"Failed to create charter from calendar: {e}")
            QMessageBox.warning(
                self,
                "Create Charter",
                f"Failed to create charter from calendar: {e}",
            )

    def _open_existing_charter(self, reserve_number, charter_id) -> None:
        """Open the drill-down Charter Detail dialog for the selected event."""
        try:
            from drill_down_widgets import CharterDetailDialog

            normalized_reserve = str(reserve_number or "").strip()
            if normalized_reserve.isdigit():
                normalized_reserve = normalized_reserve.zfill(6)

            charter_id_int = None
            try:
                charter_id_int = (
                    int(charter_id) if str(charter_id).strip() else None
                )
            except Exception:
                charter_id_int = None

            if not normalized_reserve and not charter_id_int:
                raise ValueError(
                    "Could not load charter for the selected calendar row."
                )

            dialog = CharterDetailDialog(
                self.db,
                reserve_number=normalized_reserve or None,
                parent=self,
                charter_id=charter_id_int,
            )
            dialog.exec()

        except Exception as e:
            logger.error(f"Failed to open existing charter: {e}")
            QMessageBox.warning(
                self, "Open Charter", f"Failed to open charter: {e}"
            )

    def _charter_fields_changed(self, charter_form) -> bool:
        """Check if charter fields differ from original calendar data"""
        # Compare key fields: date, time, vehicle, driver
        # This is a simplified check - expand as needed
        return True  # For now, always ask

    def _update_calendar_from_charter(self, charter_form) -> None:
        """Update calendar event to match charter changes"""
        try:
            # Update calendar_sync_status to indicate manual update needed
            reserve_number = charter_form._original_calendar_data.get(
                "reserve_number"
            )

            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    UPDATE charters
                    SET calendar_sync_status = 'needs_update',
                        updated_at = NOW()
                    WHERE reserve_number = %s
                """,
                    (reserve_number,),
                )

            QMessageBox.information(
                charter_form,
                "Calendar Updated",
                "Calendar event marked for sync update.",
            )

        except Exception as e:
            logger.error(f"Failed to update calendar from charter: {e}")
            QMessageBox.warning(
                charter_form,
                "Calendar Update",
                f"Failed to update calendar status: {e}",
            )
