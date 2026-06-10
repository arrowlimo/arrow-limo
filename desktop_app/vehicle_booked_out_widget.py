"""
Vehicle Booked Out View
Day/Week/Month schedule with active vehicles on rows and hour columns.
"""

import json
import logging
from datetime import date, datetime, time, timedelta

from db_error_handling import DatabaseContext

logger = logging.getLogger(__name__)

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QCalendarWidget,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class VehicleBookedOutWidget(QWidget):
    def __init__(self, db) -> None:
        super().__init__()
        self.db = db
        self._vehicle_rows: dict[int, int] = {}
        self._vehicles: dict[int, dict] = {}
        self._vehicle_lookup: dict[str, int] = {}
        self._charter_columns: set | None = None
        self._vehicle_columns: set | None = None
        self._init_ui()
        self._load_active_vehicles()
        self._load_day_view()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("Vehicle Booked Out"))
        header.addStretch()

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(self._on_date_changed)
        header.addWidget(self.date_edit)

        prev_btn = QPushButton("<")
        prev_btn.setFixedWidth(30)
        prev_btn.clicked.connect(lambda: self._shift_days(-1))
        header.addWidget(prev_btn)

        next_btn = QPushButton(">")
        next_btn.setFixedWidth(30)
        next_btn.clicked.connect(lambda: self._shift_days(1))
        header.addWidget(next_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh_view)
        header.addWidget(self.refresh_btn)

        layout.addLayout(header)

        # Create status_label early — must exist before view_tabs fires
        # currentChanged during addTab calls below
        self.status_label = QLabel("")

        self.view_tabs = QTabWidget()
        self.view_tabs.currentChanged.connect(self._refresh_view)

        self.day_table = QTableWidget()
        self.day_table.setColumnCount(24)
        self.day_table.setHorizontalHeaderLabels(
            [f"{h:02d}:00" for h in range(24)]
        )
        self.day_table.verticalHeader().setDefaultSectionSize(26)
        self.day_table.horizontalHeader().setDefaultSectionSize(60)
        self.day_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.day_table.cellDoubleClicked.connect(self._on_day_cell_double_click)
        self.view_tabs.addTab(self.day_table, "Day")

        self.week_table = QTableWidget()
        self.week_table.setColumnCount(6)
        self.week_table.setHorizontalHeaderLabels(
            ["Date", "Vehicle", "Start", "End", "Reserve", "Status"]
        )
        self.week_table.itemDoubleClicked.connect(
            self._on_week_row_double_click
        )
        self.view_tabs.addTab(self.week_table, "Week")

        month_widget = QWidget()
        month_layout = QVBoxLayout(month_widget)
        self.month_calendar = QCalendarWidget()
        self.month_calendar.selectionChanged.connect(self._on_month_selection)
        month_layout.addWidget(self.month_calendar)
        self.month_table = QTableWidget()
        self.month_table.setColumnCount(2)
        self.month_table.setHorizontalHeaderLabels(["Date", "Booked Vehicles"])
        self.month_table.itemDoubleClicked.connect(
            self._on_month_row_double_click
        )
        month_layout.addWidget(self.month_table)
        self.view_tabs.addTab(month_widget, "Month")

        layout.addWidget(self.status_label)
        layout.addWidget(self.view_tabs)

    def _on_date_changed(self) -> None:
        self._refresh_view()

    def _shift_days(self, days: int) -> None:
        self.date_edit.setDate(self.date_edit.date().addDays(days))

    def _refresh_view(self) -> None:
        idx = self.view_tabs.currentIndex()
        if idx == 0:
            self._load_day_view()
        elif idx == 1:
            self._load_week_view()
        else:
            self._load_month_view()

    def _get_columns(self, table_name: str) -> set:
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
        except Exception as e:
            logger.error(f"Failed to get columns for {table_name}: {e}")
            return set()

    def _load_active_vehicles(self) -> None:
        if self._vehicle_columns is None:
            self._vehicle_columns = self._get_columns("vehicles")

        status_col = (
            "status"
            if "status" in self._vehicle_columns
            else "operational_status"
        )
        if status_col not in self._vehicle_columns:
            status_col = "status"

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(f"""
                    SELECT vehicle_id, vehicle_number, {status_col} AS status,
                    vehicle_type
                    FROM vehicles
                    ORDER BY
                        CASE WHEN LOWER(
                            COALESCE({status_col}, '')
                        ) = 'active' THEN 0 ELSE 1 END,
                        CASE
                            WHEN vehicle_number ~ '^[Ll]-?\\d+$'
                                THEN CAST(regexp_replace(
                                    vehicle_number, '[^0-9]', '', 'g'
                                ) AS INT)
                            ELSE 9999
                        END,
                        vehicle_number
                    """)
                rows = cur.fetchall()
            self._vehicles = {}
            self._vehicle_rows = {}
            self._vehicle_lookup = {}
            for idx, (vid, num, status, vtype) in enumerate(rows):
                self._vehicles[vid] = {
                    "vehicle_number": num or f"Vehicle {vid}",
                    "status": status or "",
                    "vehicle_type": vtype or "",
                }
                self._vehicle_rows[vid] = idx
                norm = self._normalize_vehicle_label(num)
                if norm and norm not in self._vehicle_lookup:
                    self._vehicle_lookup[norm] = vid
        except Exception as e:
            logger.error(f"Failed to load active vehicles: {e}")
            self._vehicles = {}
            self._vehicle_rows = {}
            self._vehicle_lookup = {}

    def _normalize_vehicle_label(self, value: str | None) -> str:
        if not value:
            return ""
        return "".join(ch for ch in str(value).upper() if ch.isalnum())

    def _resolve_vehicle_id(self, row: dict) -> int | None:
        vehicle_id = row.get("vehicle_id")
        if vehicle_id in self._vehicle_rows:
            return vehicle_id

        vehicle_text = row.get("vehicle")
        norm = self._normalize_vehicle_label(vehicle_text)
        if norm and norm in self._vehicle_lookup:
            return self._vehicle_lookup[norm]
        return None

    def _load_charters(self, start_date: date, end_date: date) -> list[dict]:
        if self._charter_columns is None:
            self._charter_columns = self._get_columns("charters")

        cols = [
            "charter_id",
            "reserve_number",
            "charter_date",
            "pickup_time",
            "do_time",
            "depart_yard_time",
            "dropoff_time",
            "status",
            "vehicle_id",
            "passenger_count",
            "is_out_of_town",
        ]
        optional = [
            "return_by_time",
            "wait_start_time",
            "wait_end_time",
            "split_run_dropoff_time",
            "split_run_pickup_time",
            "charter_data",
            "charter_data_json",
            "vehicle",
        ]
        select_cols = [c for c in cols if c in self._charter_columns]
        select_cols.extend([c for c in optional if c in self._charter_columns])

        select_clause = ", ".join(select_cols)

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    f"""
                    SELECT {select_clause}
                    FROM charters
                    WHERE charter_date BETWEEN %s AND %s
                      AND (status IS NULL
                          OR status NOT IN ('cancelled', 'no-show'))
                    """,
                    (start_date, end_date),
                )
                rows = cur.fetchall()
        except Exception as e:
            logger.error(
                f"Failed to load charters between {start_date} and"
                f"{end_date}: {e}"
            )
            return []

        results = []
        for row in rows:
            entry = dict(zip(select_cols, row))
            results.append(entry)
        return results

    def _parse_time(self, value) -> time | None:
        if value is None:
            return None
        if isinstance(value, time):
            return value
        if isinstance(value, datetime):
            return value.time()
        if isinstance(value, str):
            try:
                return datetime.strptime(value.strip(), "%H:%M").time()
            except Exception:
                try:
                    return datetime.strptime(value.strip(), "%H:%M:%S").time()
                except Exception:
                    return None
        return None

    def _extract_charter_json(self, row: dict) -> dict:
        for key in ("charter_data", "charter_data_json"):
            if row.get(key):
                try:
                    if isinstance(row[key], dict):
                        return row[key]
                    return json.loads(row[key])
                except Exception:
                    return {}
        return {}

    def _get_charter_times(
        self, row: dict
    ) -> tuple[datetime | None, datetime | None]:
        charter_date = row.get("charter_date")
        if not charter_date:
            return (None, None)

        # Business rule: booked-out span is pickup -> do_time
        # (fallback only when one side is missing).
        start_time = self._parse_time(row.get("pickup_time"))
        if start_time is None:
            start_time = self._parse_time(row.get("depart_yard_time"))

        end_time = self._parse_time(row.get("do_time"))
        if end_time is None:
            end_time = self._parse_time(row.get("dropoff_time"))
        if end_time is None:
            end_time = self._parse_time(row.get("return_by_time"))

        charter_json = self._extract_charter_json(row)
        if end_time is None:
            planned_end = charter_json.get("planned_end_time")
            if planned_end:
                try:
                    end_dt = datetime.fromisoformat(planned_end)
                    end_time = end_dt.time()
                except Exception:
                    pass

        # Also try charter_data JSON for start time
        if start_time is None:
            planned_start = charter_json.get("planned_start_time")
            if planned_start:
                try:
                    start_time = datetime.fromisoformat(planned_start).time()
                except Exception:
                    pass

        # Fall back to full-day block (0:00 – 23:59) so vehicle still shows
        if start_time is None:
            start_dt = datetime.combine(charter_date, time(0, 0))
            end_dt = datetime.combine(charter_date, time(23, 59))
            return (start_dt, end_dt)

        start_dt = datetime.combine(charter_date, start_time)
        if end_time is None:
            end_dt = start_dt + timedelta(hours=1)
        else:
            end_dt = datetime.combine(charter_date, end_time)
            if end_dt <= start_dt:
                end_dt = end_dt + timedelta(days=1)

        return (start_dt, end_dt)

    def _extract_segments(
        self, row: dict, start_dt: datetime, end_dt: datetime
    ) -> list[tuple[datetime, datetime, str]]:
        segments: list[tuple[datetime, datetime, str]] = [
            (start_dt, end_dt, "normal")
        ]
        wait_start = self._parse_time(row.get("wait_start_time"))
        wait_end = self._parse_time(row.get("wait_end_time"))

        if wait_start and wait_end:
            wait_start_dt = datetime.combine(start_dt.date(), wait_start)
            wait_end_dt = datetime.combine(start_dt.date(), wait_end)
            if wait_end_dt <= wait_start_dt:
                wait_end_dt += timedelta(days=1)
            segments = self._split_with_wait(
                segments, wait_start_dt, wait_end_dt
            )

        split_drop = self._parse_time(row.get("split_run_dropoff_time"))
        split_pick = self._parse_time(row.get("split_run_pickup_time"))
        if split_drop and split_pick:
            split_start_dt = datetime.combine(start_dt.date(), split_drop)
            split_end_dt = datetime.combine(start_dt.date(), split_pick)
            if split_end_dt <= split_start_dt:
                split_end_dt += timedelta(days=1)
            segments = self._split_with_gap(
                segments, split_start_dt, split_end_dt
            )

        return segments

    def _split_with_wait(self, segments, wait_start, wait_end) -> object:
        result = []
        for seg_start, seg_end, kind in segments:
            if wait_end <= seg_start or wait_start >= seg_end:
                result.append((seg_start, seg_end, kind))
                continue
            if seg_start < wait_start:
                result.append((seg_start, wait_start, kind))
            result.append(
                (max(seg_start, wait_start), min(seg_end, wait_end), "wait")
            )
            if wait_end < seg_end:
                result.append((wait_end, seg_end, kind))
        return result

    def _split_with_gap(self, segments, gap_start, gap_end) -> object:
        result = []
        for seg_start, seg_end, kind in segments:
            if gap_end <= seg_start or gap_start >= seg_end:
                result.append((seg_start, seg_end, kind))
                continue
            if seg_start < gap_start:
                result.append((seg_start, gap_start, kind))
            if gap_end < seg_end:
                result.append((gap_end, seg_end, kind))
        return result

    def _load_day_view(self) -> None:
        self._load_active_vehicles()
        self.day_table.clearContents()

        selected_date = self.date_edit.date().toPyDate()
        day_start = selected_date
        day_end = selected_date
        charters = self._load_charters(day_start - timedelta(days=1), day_end)

        # Separate matched vs unassigned charters
        matched_charters = []
        unassigned_charters = []
        for row in charters:
            if self._resolve_vehicle_id(row) is not None:
                matched_charters.append(row)
            else:
                unassigned_charters.append(row)

        # Build row labels: vehicles first, then one "Unassigned" row per
        # unassigned charter (so multiple unassigned don't collide)
        num_vehicle_rows = len(self._vehicles)
        num_unassigned_rows = len(unassigned_charters)
        total_rows = num_vehicle_rows + num_unassigned_rows
        self.day_table.setRowCount(total_rows)

        row_labels = []
        for vid in self._vehicle_rows.keys():
            vehicle = self._vehicles.get(vid, {})
            label = vehicle.get("vehicle_number", "")
            vtype = vehicle.get("vehicle_type", "")
            if vtype:
                label = f"{label} - {vtype}" if label else vtype
            row_labels.append(label)
        for i in range(num_unassigned_rows):
            row_labels.append("— Unassigned —" if num_unassigned_rows == 1
                               else f"— Unassigned {i + 1} —")
        self.day_table.setVerticalHeaderLabels(row_labels)

        # Colour unassigned rows distinctly (light red background on header)
        for i in range(num_unassigned_rows):
            row_idx = num_vehicle_rows + i
            header_item = self.day_table.verticalHeaderItem(row_idx)
            if header_item:
                header_item.setBackground(QBrush(QColor(255, 200, 200)))

        rendered = 0
        day_min = datetime.combine(selected_date, time(0, 0))
        day_max = day_min + timedelta(days=1)

        for row in matched_charters:
            vehicle_id = self._resolve_vehicle_id(row)
            start_dt, end_dt = self._get_charter_times(row)
            if not start_dt or not end_dt:
                continue
            if end_dt <= day_min or start_dt >= day_max:
                continue
            span_start = max(start_dt, day_min)
            span_end = min(end_dt, day_max)
            segments = self._extract_segments(row, span_start, span_end)
            rendered += 1
            for seg_start, seg_end, kind in segments:
                self._render_segment(vehicle_id, row, seg_start, seg_end, kind)

        for i, row in enumerate(unassigned_charters):
            start_dt, end_dt = self._get_charter_times(row)
            if not start_dt or not end_dt:
                # No time at all — put a marker in col 0
                start_dt = day_min
                end_dt = day_min + timedelta(hours=1)
            if end_dt <= day_min or start_dt >= day_max:
                continue
            span_start = max(start_dt, day_min)
            span_end = min(end_dt, day_max)
            row_idx = num_vehicle_rows + i
            start_col = span_start.hour
            duration_hours = (span_end - span_start).total_seconds() / 3600.0
            span_cols = max(1, int(duration_hours + 0.999))
            if start_col >= 24:
                continue
            if start_col + span_cols > 24:
                span_cols = 24 - start_col
            reserve = row.get("reserve_number") or "?"
            pax = row.get("passenger_count") or ""
            label = f"{reserve} (no vehicle)" + (f" {pax} pax" if pax else "")
            item = QTableWidgetItem(label)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setToolTip(self._format_event_tooltip(row, span_start, span_end))
            item.setBackground(QBrush(QColor(255, 160, 160)))
            reserve = row.get("reserve_number")
            if reserve:
                item.setData(Qt.ItemDataRole.UserRole, reserve)
            self.day_table.setItem(row_idx, start_col, item)
            self.day_table.setSpan(row_idx, start_col, 1, span_cols)
            rendered += 1

        total = len(charters)
        msg = f"{rendered} charter(s) shown for {selected_date}"
        if num_unassigned_rows:
            msg += f"  ({num_unassigned_rows} unassigned – no vehicle)"
        if total == 0:
            msg = f"No charters found for {selected_date}"
        self.status_label.setText(msg)

    def _render_segment(
        self,
        vehicle_id: int,
        row: dict,
        seg_start: datetime,
        seg_end: datetime,
        kind: str,
    ) -> None:
        row_idx = self._vehicle_rows.get(vehicle_id)
        if row_idx is None:
            return

        start_col = seg_start.hour
        duration_hours = (seg_end - seg_start).total_seconds() / 3600.0
        span_cols = max(1, int(duration_hours + 0.999))
        if start_col >= 24:
            return
        if start_col + span_cols > 24:
            span_cols = 24 - start_col

        label = self._format_event_label(row, vehicle_id)
        item = QTableWidgetItem(label if kind == "normal" else "")
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setToolTip(self._format_event_tooltip(row, seg_start, seg_end))

        base_color = self._color_for_vehicle(vehicle_id)
        if kind == "wait":
            base_color = self._lighten_color(base_color, 0.6)
        item.setBackground(QBrush(base_color))
        reserve = row.get("reserve_number")
        if reserve:
            item.setData(Qt.ItemDataRole.UserRole, reserve)

        self.day_table.setItem(row_idx, start_col, item)
        self.day_table.setSpan(row_idx, start_col, 1, span_cols)

    def _format_event_label(self, row: dict, vehicle_id: int) -> str:
        reserve = row.get("reserve_number") or ""
        passenger_count = row.get("passenger_count") or ""
        vehicle = self._vehicles.get(vehicle_id, {})
        vehicle_num = vehicle.get("vehicle_number", "")
        vehicle_type = vehicle.get("vehicle_type", "")
        pax = f"{passenger_count} pax" if passenger_count else ""
        parts = [reserve, vehicle_num, vehicle_type, pax]
        return " ".join([p for p in parts if p]).strip()

    def _format_event_tooltip(
        self, row: dict, start_dt: datetime, end_dt: datetime
    ) -> str:
        reserve = row.get("reserve_number") or ""
        status = row.get("status") or ""
        return (
            f"Reserve {reserve} | {start_dt:%H:%M} - {end_dt:%H:%M} | {status}"
        )

    def _color_for_vehicle(self, vehicle_id: int) -> QColor:
        vehicle = self._vehicles.get(vehicle_id, {})
        vtype = (vehicle.get("vehicle_type") or "").lower()
        seed = sum(ord(ch) for ch in vtype) or vehicle_id
        r = 80 + (seed * 37) % 140
        g = 80 + (seed * 57) % 140
        b = 80 + (seed * 77) % 140
        return QColor(r, g, b)

    def _lighten_color(self, color: QColor, factor: float) -> QColor:
        r = color.red() + int((255 - color.red()) * factor)
        g = color.green() + int((255 - color.green()) * factor)
        b = color.blue() + int((255 - color.blue()) * factor)
        return QColor(r, g, b)

    def _load_week_view(self) -> None:
        selected = self.date_edit.date().toPyDate()
        week_start = selected - timedelta(days=selected.weekday())
        week_end = week_start + timedelta(days=6)

        rows = []
        for row in self._load_charters(week_start, week_end):
            vehicle_id = self._resolve_vehicle_id(row)
            if vehicle_id is None:
                continue
            start_dt, end_dt = self._get_charter_times(row)
            if not start_dt or not end_dt:
                continue
            rows.append((row, vehicle_id, start_dt, end_dt))

        rows.sort(
            key=lambda r: (
                self._vehicles[r[1]]["vehicle_number"],
                r[2],
            )
        )

        self.week_table.setRowCount(len(rows))
        for idx, (row, vehicle_id, start_dt, end_dt) in enumerate(rows):
            vehicle = self._vehicles.get(vehicle_id, {})
            self.week_table.setItem(
                idx, 0, QTableWidgetItem(str(row.get("charter_date") or ""))
            )
            self.week_table.setItem(
                idx, 1, QTableWidgetItem(vehicle.get("vehicle_number", ""))
            )
            self.week_table.setItem(
                idx, 2, QTableWidgetItem(start_dt.strftime("%H:%M"))
            )
            self.week_table.setItem(
                idx, 3, QTableWidgetItem(end_dt.strftime("%H:%M"))
            )
            self.week_table.setItem(
                idx, 4, QTableWidgetItem(str(row.get("reserve_number") or ""))
            )
            self.week_table.setItem(
                idx, 5, QTableWidgetItem(str(row.get("status") or ""))
            )

    def _load_month_view(self) -> None:
        selected = self.date_edit.date().toPyDate()
        month_start = selected.replace(day=1)
        if selected.month == 12:
            next_month = selected.replace(
                year=selected.year + 1, month=1, day=1
            )
        else:
            next_month = selected.replace(month=selected.month + 1, day=1)
        month_end = next_month - timedelta(days=1)

        counts: dict[date, int] = {}
        for row in self._load_charters(month_start, month_end):
            d = row.get("charter_date")
            if not d:
                continue
            if self._resolve_vehicle_id(row) is None:
                continue
            counts[d] = counts.get(d, 0) + 1

        items = sorted(counts.items(), key=lambda x: x[0])
        self.month_table.setRowCount(len(items))
        for idx, (d, cnt) in enumerate(items):
            self.month_table.setItem(idx, 0, QTableWidgetItem(str(d)))
            self.month_table.setItem(idx, 1, QTableWidgetItem(str(cnt)))

        self.month_calendar.setSelectedDate(
            QDate(selected.year, selected.month, selected.day)
        )

    def _on_day_cell_double_click(self, row, col) -> None:
        item = self.day_table.item(row, col)
        if not item:
            return
        reserve_number = item.data(Qt.ItemDataRole.UserRole)
        if reserve_number:
            self._open_charter_for_edit(reserve_number)

    def _open_charter_for_edit(self, reserve_number: str) -> None:
        try:
            from main import CharterFormWidget
            charter_form = CharterFormWidget(self.db)
            charter_form.load_charter_by_reserve(reserve_number)
            charter_form.show()
            self._open_charter_windows = getattr(
                self, "_open_charter_windows", []
            )
            self._open_charter_windows.append(charter_form)
        except Exception as e:
            logger.error(f"Failed to open charter {reserve_number}: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Open Charter",
                f"Could not open charter {reserve_number}:\n{e}",
            )

    def _on_week_row_double_click(self, item) -> None:
        row = item.row()
        date_item = self.week_table.item(row, 0)
        if not date_item:
            return
        try:
            d = datetime.strptime(date_item.text(), "%Y-%m-%d").date()
        except Exception:
            return
        self.date_edit.setDate(QDate(d.year, d.month, d.day))
        self.view_tabs.setCurrentIndex(0)

    def _on_month_selection(self) -> None:
        qdate = self.month_calendar.selectedDate()
        self.date_edit.setDate(qdate)
        self.view_tabs.setCurrentIndex(0)

    def _on_month_row_double_click(self, item) -> None:
        row = item.row()
        date_item = self.month_table.item(row, 0)
        if not date_item:
            return
        try:
            d = datetime.strptime(date_item.text(), "%Y-%m-%d").date()
        except Exception:
            return
        self.date_edit.setDate(QDate(d.year, d.month, d.day))
        self.view_tabs.setCurrentIndex(0)
