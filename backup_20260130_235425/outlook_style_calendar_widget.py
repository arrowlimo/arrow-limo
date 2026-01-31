"""
Outlook-Style Calendar Widget
- Day/Week/Month views with visual time blocks
- Color-coded appointments based on sync status and charter type
- Click to view/edit charter details
- Drag-and-drop support for rescheduling (future)
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QFrame, QToolTip, QMenu, QMessageBox, QButtonGroup, QCheckBox
)
from PyQt6.QtCore import Qt, QDate, QTime, QDateTime, QRect, QPoint, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QMouseEvent
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys


class OutlookStyleCalendarWidget(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.current_date = QDate.currentDate()
        self.view_mode = 'week'  # year, month, week, day
        self.charters = []
        self._init_ui()
        self._load_charters()
        
    def _init_ui(self):
        layout = QVBoxLayout()
        
        # Header with view toggles and navigation
        header = QHBoxLayout()
        
        title = QLabel("📅 Calendar")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.addWidget(title)
        
        header.addStretch()
        
        # Navigation buttons
        prev_btn = QPushButton("◀")
        prev_btn.setFixedWidth(40)
        prev_btn.clicked.connect(self._go_previous)
        header.addWidget(prev_btn)
        
        self.date_label = QLabel()
        self.date_label.setFont(QFont("Segoe UI", 12))
        self.date_label.setMinimumWidth(250)
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.date_label)
        
        next_btn = QPushButton("▶")
        next_btn.setFixedWidth(40)
        next_btn.clicked.connect(self._go_next)
        header.addWidget(next_btn)
        
        today_btn = QPushButton("Today")
        today_btn.clicked.connect(self._go_today)
        header.addWidget(today_btn)
        
        header.addStretch()
        
        # View mode buttons
        self.view_group = QButtonGroup()
        
        self.day_btn = QPushButton("Day")
        self.day_btn.setCheckable(True)
        self.day_btn.clicked.connect(lambda: self._set_view('day'))
        self.view_group.addButton(self.day_btn)
        header.addWidget(self.day_btn)
        
        self.week_btn = QPushButton("Week")
        self.week_btn.setCheckable(True)
        self.week_btn.setChecked(True)
        self.week_btn.clicked.connect(lambda: self._set_view('week'))
        self.view_group.addButton(self.week_btn)
        header.addWidget(self.week_btn)
        
        self.month_btn = QPushButton("Month")
        self.month_btn.setCheckable(True)
        self.month_btn.clicked.connect(lambda: self._set_view('month'))
        self.view_group.addButton(self.month_btn)
        header.addWidget(self.month_btn)

        self.year_btn = QPushButton("Year")
        self.year_btn.setCheckable(True)
        self.year_btn.clicked.connect(lambda: self._set_view('year'))
        self.view_group.addButton(self.year_btn)
        header.addWidget(self.year_btn)
        
        # Add appointment button
        add_btn = QPushButton("+ New Appointment")
        add_btn.setStyleSheet("background-color: #0078d4; color: white; padding: 5px 10px;")
        add_btn.clicked.connect(self._create_appointment)
        header.addWidget(add_btn)
        
        layout.addLayout(header)
        
        # Filter toolbar
        filter_toolbar = QHBoxLayout()
        filter_toolbar.setSpacing(15)
        
        filter_label = QLabel("Show:")
        filter_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        filter_toolbar.addWidget(filter_label)
        
        self.filter_bookings = QCheckBox("Bookings")
        self.filter_bookings.setChecked(True)
        self.filter_bookings.toggled.connect(self._refresh_view)
        filter_toolbar.addWidget(self.filter_bookings)
        
        self.filter_quotes = QCheckBox("Quotes")
        self.filter_quotes.setChecked(True)
        self.filter_quotes.toggled.connect(self._refresh_view)
        filter_toolbar.addWidget(self.filter_quotes)
        
        self.filter_cancelled = QCheckBox("Cancelled")
        self.filter_cancelled.setChecked(False)
        self.filter_cancelled.toggled.connect(self._refresh_view)
        filter_toolbar.addWidget(self.filter_cancelled)
        
        self.filter_assigned = QCheckBox("Assigned Only")
        self.filter_assigned.setChecked(False)
        self.filter_assigned.toggled.connect(self._refresh_view)
        filter_toolbar.addWidget(self.filter_assigned)
        
        self.filter_unassigned = QCheckBox("Unassigned")
        self.filter_unassigned.setChecked(True)
        self.filter_unassigned.toggled.connect(self._refresh_view)
        filter_toolbar.addWidget(self.filter_unassigned)
        
        filter_toolbar.addStretch()
        layout.addLayout(filter_toolbar)
        
        # Calendar view area (scrollable)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.calendar_view = CalendarViewWidget(self.db, self.view_mode, self.current_date, self)
        self.scroll_area.setWidget(self.calendar_view)
        
        layout.addWidget(self.scroll_area)
        
        # Color legend at bottom
        legend = QHBoxLayout()
        legend.addStretch()
        
        legend_items = [
            ("🟢 Synced", "#2e7d32"),
            ("🔴 Not in Outlook", "#c62828"),
            ("🟡 Mismatch", "#f57f17"),
            ("🔵 Recently Synced", "#1565c0"),
            ("⚫ Cancelled", "#616161"),
            ("🟪 Quote", "#6a1b9a"),
            ("🟧 Unassigned", "#e65100")
        ]
        
        for label_text, color in legend_items:
            lbl = QLabel(f"  {label_text}  ")
            lbl.setStyleSheet(f"background-color: {color}; color: white; padding: 3px 8px; border-radius: 3px;")
            legend.addWidget(lbl)
        
        legend.addStretch()
        layout.addLayout(legend)
        
        self.setLayout(layout)
        self._update_date_label()
        
    def _set_view(self, mode):
        self.view_mode = mode
        self.calendar_view.set_view_mode(mode, self.current_date, self._get_active_filters())
        if mode == 'day':
            self.day_btn.setChecked(True)
        elif mode == 'week':
            self.week_btn.setChecked(True)
        elif mode == 'month':
            self.month_btn.setChecked(True)
        elif mode == 'year':
            self.year_btn.setChecked(True)
        self._update_date_label()
    
    def _refresh_view(self):
        """Refresh the calendar view with current filter settings"""
        self.calendar_view.set_view_mode(self.view_mode, self.current_date, self._get_active_filters())
    
    def _get_active_filters(self):
        """Get current filter settings as a dict"""
        return {
            'bookings': self.filter_bookings.isChecked(),
            'quotes': self.filter_quotes.isChecked(),
            'cancelled': self.filter_cancelled.isChecked(),
            'assigned_only': self.filter_assigned.isChecked(),
            'unassigned': self.filter_unassigned.isChecked()
        }
        
    def _go_previous(self):
        if self.view_mode == 'day':
            self.current_date = self.current_date.addDays(-1)
        elif self.view_mode == 'week':
            self.current_date = self.current_date.addDays(-7)
        elif self.view_mode == 'year':
            self.current_date = self.current_date.addYears(-1)
        else:  # month
            self.current_date = self.current_date.addMonths(-1)
        
        self.calendar_view.set_view_mode(self.view_mode, self.current_date, self._get_active_filters())
        self._update_date_label()
        
    def _go_next(self):
        if self.view_mode == 'day':
            self.current_date = self.current_date.addDays(1)
        elif self.view_mode == 'week':
            self.current_date = self.current_date.addDays(7)
        elif self.view_mode == 'year':
            self.current_date = self.current_date.addYears(1)
        else:  # month
            self.current_date = self.current_date.addMonths(1)
        
        self.calendar_view.set_view_mode(self.view_mode, self.current_date, self._get_active_filters())
        self._update_date_label()
        
    def _go_today(self):
        self.current_date = QDate.currentDate()
        self.calendar_view.set_view_mode(self.view_mode, self.current_date, self._get_active_filters())
        self._update_date_label()
        
    def _update_date_label(self):
        if self.view_mode == 'day':
            self.date_label.setText(self.current_date.toString("dddd, MMMM d, yyyy"))
        elif self.view_mode == 'week':
            # Get start of week (Sunday)
            day_of_week = self.current_date.dayOfWeek()
            if day_of_week == 7:  # Sunday
                week_start = self.current_date
            else:
                week_start = self.current_date.addDays(-day_of_week)
            week_end = week_start.addDays(6)
            
            if week_start.month() == week_end.month():
                self.date_label.setText(f"{week_start.toString('MMMM d')} - {week_end.toString('d, yyyy')}")
            else:
                self.date_label.setText(f"{week_start.toString('MMM d')} - {week_end.toString('MMM d, yyyy')}")
        elif self.view_mode == 'month':
            self.date_label.setText(self.current_date.toString("MMMM yyyy"))
        else:  # year
            self.date_label.setText(self.current_date.toString("yyyy"))

    def drill_to_month(self, date: QDate):
        self.current_date = QDate(date.year(), date.month(), 1)
        self._set_view('month')

    def drill_to_week(self, date: QDate):
        self.current_date = date
        self._set_view('week')

    def drill_to_day(self, date: QDate):
        self.current_date = date
        self._set_view('day')
    
    def _load_charters(self):
        """Load charters for current view period."""
        # This will be called by the CalendarViewWidget
        pass
    
    def _create_appointment(self):
        """Open dialog to create new charter/appointment."""
        QMessageBox.information(self, "Create Appointment", 
            "This will open a dialog to create a new charter.\n\n"
            "Would you like me to implement the full charter creation form?")


class CalendarViewWidget(QWidget):
    """Actual calendar grid that draws appointments like Outlook."""
    
    def __init__(self, db, view_mode, current_date, parent_widget=None):
        super().__init__()
        self.db = db
        self.view_mode = view_mode
        self.current_date = current_date
        self.parent_widget = parent_widget
        self.charters = []
        self.appointment_rects = []  # Store rectangles for click detection
        self.day_cell_rects = []  # (rect, date) in month view
        self.week_header_rects = []  # (rect, date) in week view
        self.month_cell_rects = []  # (rect, date) in year view
        self.active_filters = {
            'bookings': True,
            'quotes': True,
            'cancelled': False,
            'assigned_only': False,
            'unassigned': True
        }
        
        # Time range for day/week views
        self.start_hour = 5  # 5 AM
        self.end_hour = 22   # 10 PM
        self.hour_height = 60  # pixels per hour
        
        self.setMinimumSize(800, 600)
        self.setMouseTracking(True)
        self._load_charters()
        
    def set_view_mode(self, mode, date, filters=None):
        self.view_mode = mode
        self.current_date = date
        if filters:
            self.active_filters = filters
        self._load_charters()
        self.update()
        
    def _load_charters(self):
        """Load charters from database for current view period."""
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                try:
                    self.db.rollback()
                except:
                    pass
                pass
            
            cur = self.db.get_cursor()
            
            # Determine date range based on view mode
            if self.view_mode == 'day':
                start_date = self.current_date
                end_date = self.current_date
            elif self.view_mode == 'week':
                day_of_week = self.current_date.dayOfWeek()
                if day_of_week == 7:  # Sunday
                    start_date = self.current_date
                else:
                    start_date = self.current_date.addDays(-day_of_week)
                end_date = start_date.addDays(6)
            elif self.view_mode == 'year':
                start_date = QDate(self.current_date.year(), 1, 1)
                end_date = QDate(self.current_date.year(), 12, 31)
            else:  # month
                start_date = QDate(self.current_date.year(), self.current_date.month(), 1)
                end_date = QDate(self.current_date.year(), self.current_date.month(), 
                                start_date.daysInMonth())
            
            # Check if optional columns exist to include them safely
            cur.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='charters' AND column_name='quote_expires_at'
                """
            )
            has_expiry = cur.fetchone() is not None

            cur.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='charters' AND column_name='dropoff_time'
                """
            )
            has_dropoff_time = cur.fetchone() is not None

            cur.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='charters' AND column_name='charter_hours'
                """
            )
            has_charter_hours = cur.fetchone() is not None

            # Query charters - database uses YYYY-MM-DD format
            select_cols = [
                "c.charter_id", "c.reserve_number", "c.charter_date", 
                "c.pickup_time",
                "c.client_display_name", "c.pickup_address", "c.dropoff_address",
                "c.status", "c.booking_status",
                "COALESCE(c.calendar_color, '') as calendar_color",
                "v.vehicle_number", "e.full_name as driver_name"
            ]

            if has_dropoff_time:
                select_cols.insert(4, "c.dropoff_time")
            else:
                select_cols.insert(4, "NULL as dropoff_time")

            if has_charter_hours:
                select_cols.insert(5, "c.charter_hours")
            else:
                select_cols.insert(5, "NULL as charter_hours")
            if has_expiry:
                select_cols.append("c.quote_expires_at")

            query = f"""
                SELECT {', '.join(select_cols)}
                FROM charters c
                LEFT JOIN vehicles v ON c.vehicle_id = v.vehicle_id
                LEFT JOIN employees e ON c.employee_id = e.employee_id
                WHERE c.charter_date >= %s AND c.charter_date <= %s
                ORDER BY c.charter_date, c.pickup_time NULLS LAST
            """
            
            # Convert dates to Python date objects for proper parameter binding
            from datetime import date as py_date
            start_py = start_date.toPyDate() if hasattr(start_date, 'toPyDate') else py_date.fromisoformat(start_date.toString("yyyy-MM-dd"))
            end_py = end_date.toPyDate() if hasattr(end_date, 'toPyDate') else py_date.fromisoformat(end_date.toString("yyyy-MM-dd"))
            cur.execute(query, (start_py, end_py))
            
            columns = [desc[0] for desc in cur.description]
            all_charters = [dict(zip(columns, row)) for row in cur.fetchall()]

            # Normalize charter_date to date objects for comparisons
            for charter in all_charters:
                cd = charter.get('charter_date')
                if cd is None:
                    continue
                try:
                    if hasattr(cd, 'date'):
                        charter['charter_date'] = cd.date()
                    elif isinstance(cd, str):
                        from datetime import datetime as _dt
                        charter['charter_date'] = _dt.strptime(cd, "%Y-%m-%d").date()
                except Exception:
                    pass
            
            # Load charter routes (for split runs)
            charter_ids = [c['charter_id'] for c in all_charters]
            routes_map = {}
            if charter_ids:
                placeholders = ','.join(['%s'] * len(charter_ids))
                cur.execute(f"""
                    SELECT cr.charter_id, cr.route_sequence, COALESCE(ret.event_code, 'unknown'),
                           cr.stop_time, cr.address, cr.pickup_location, cr.dropoff_location
                    FROM charter_routes cr
                    LEFT JOIN route_event_types ret ON cr.event_type_id = ret.event_type_id
                    WHERE cr.charter_id IN ({placeholders})
                    ORDER BY cr.charter_id, cr.route_sequence
                """, charter_ids)
                
                for row in cur.fetchall():
                    charter_id = row[0]
                    if charter_id not in routes_map:
                        routes_map[charter_id] = []
                    routes_map[charter_id].append({
                        'route_sequence': row[1],
                        'event_type_code': row[2],
                        'stop_time': row[3],
                        'address': row[4],
                        'pickup_location': row[5],
                        'dropoff_location': row[6]
                    })
            
            # Attach routes to charters
            for charter in all_charters:
                charter['_route_events'] = routes_map.get(charter['charter_id'], [])
            
            # Apply filters
            self.charters = []
            for charter in all_charters:
                # Filter by booking/quote type
                booking_type = (charter.get('booking_status') or charter.get('booking_type') or '').lower()
                is_quote = 'quote' in booking_type
                is_booking = not is_quote
                
                if is_quote and not self.active_filters.get('quotes', True):
                    continue
                if is_booking and not self.active_filters.get('bookings', True):
                    continue
                
                # Filter by cancelled status
                status = (charter.get('status') or '').lower()
                is_cancelled = 'cancel' in status
                if is_cancelled and not self.active_filters.get('cancelled', False):
                    continue
                
                # Filter by assigned/unassigned
                has_driver = charter.get('driver_name') is not None
                has_vehicle = charter.get('vehicle_number') is not None
                is_assigned = has_driver or has_vehicle
                
                if self.active_filters.get('assigned_only', False) and not is_assigned:
                    continue
                if not self.active_filters.get('unassigned', True) and not is_assigned:
                    continue
                
                # Calculate duration from actual times
                charter['estimated_duration_hours'] = self._calculate_duration(charter)
                self.charters.append(charter)
            
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            print(f"Error loading charters: {e}")
            self.charters = []
    
    def _calculate_duration(self, charter):
        """Calculate actual charter duration from database times."""
        # First try charter_hours if available
        charter_hours = charter.get('charter_hours')
        if charter_hours and charter_hours > 0:
            return float(charter_hours)
        
        # Next try to calculate from pickup_time and dropoff_time
        pickup_time = charter.get('pickup_time')
        dropoff_time = charter.get('dropoff_time')
        
        if pickup_time and dropoff_time:
            try:
                # Parse times
                if isinstance(pickup_time, str):
                    pickup_dt = datetime.strptime(pickup_time, "%H:%M:%S").time()
                else:
                    pickup_dt = pickup_time
                    
                if isinstance(dropoff_time, str):
                    dropoff_dt = datetime.strptime(dropoff_time, "%H:%M:%S").time()
                else:
                    dropoff_dt = dropoff_time
                
                # Calculate duration in hours
                pickup_minutes = pickup_dt.hour * 60 + pickup_dt.minute
                dropoff_minutes = dropoff_dt.hour * 60 + dropoff_dt.minute
                
                # Handle overnight charters (dropoff next day)
                if dropoff_minutes < pickup_minutes:
                    dropoff_minutes += 24 * 60
                
                duration_minutes = dropoff_minutes - pickup_minutes
                return duration_minutes / 60.0
            except:
                pass
        
        # Fallback to estimated duration based on type
        booking_type = (charter.get('booking_status') or charter.get('booking_type') or '').lower()
        
        if 'airport' in booking_type:
            return 2.0  # Airport runs typically 2 hours
        elif 'wedding' in booking_type:
            return 4.0  # Weddings typically 4 hours
        elif 'hourly' in booking_type:
            return 3.0  # Default hourly booking
        elif 'quote' in booking_type:
            return 1.5  # Quotes typically shorter
        else:
            return 2.0  # Default duration
    
    def _get_route_events(self, charter):
        """Get route events for split run display.
        
        Returns list of dicts with 'start_time', 'end_time', 'event_type', 'label' for each segment.
        For split runs, returns multiple segments with gaps between them.
        """
        route_events = charter.get('_route_events', [])
        
        if not route_events or len(route_events) <= 1:
            # No split run - return single event using charter times
            pickup_time = charter.get('pickup_time')
            dropoff_time = charter.get('dropoff_time')
            
            if pickup_time and dropoff_time:
                return [{
                    'start_time': pickup_time,
                    'end_time': dropoff_time,
                    'event_type': 'full_charter',
                    'label': ''
                }]
            return []
        
        # Split run - create segments from route events
        segments = []
        current_start = None
        
        for i, event in enumerate(route_events):
            event_type = event.get('event_type_code', '')
            stop_time = event.get('stop_time')
            
            if not stop_time:
                continue
            
            if event_type == 'pickup':
                current_start = stop_time
            elif event_type in ['dropoff', 'dropoff_split'] and current_start:
                # End of a segment
                label = f"Leg {len(segments) + 1}" if len(segments) > 0 else ""
                segments.append({
                    'start_time': current_start,
                    'end_time': stop_time,
                    'event_type': event_type,
                    'label': label
                })
                
                # Check if next event is another pickup (continuation of split run)
                if i + 1 < len(route_events) and route_events[i + 1].get('event_type_code') == 'pickup':
                    current_start = None  # Will be set by next pickup
                else:
                    current_start = None
        
        return segments if segments else []
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if self.view_mode == 'day':
            self._paint_day_view(painter)
        elif self.view_mode == 'week':
            self._paint_week_view(painter)
        elif self.view_mode == 'year':
            self._paint_year_view(painter)
        else:
            self._paint_month_view(painter)
    
    def _paint_day_view(self, painter):
        """Paint single day view with time slots."""
        width = self.width()
        
        # Header with date
        painter.fillRect(0, 0, width, 40, QColor("#f0f0f0"))
        painter.setPen(QPen(Qt.GlobalColor.black))
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        painter.drawText(10, 25, self.current_date.toString("dddd, MMMM d"))
        
        y_offset = 50
        self.appointment_rects = []
        
        # Draw time grid
        for hour in range(self.start_hour, self.end_hour + 1):
            y = y_offset + (hour - self.start_hour) * self.hour_height
            
            # Hour line
            painter.setPen(QPen(QColor("#cccccc"), 1))
            painter.drawLine(60, y, width - 10, y)
            
            # Time label
            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(QPen(Qt.GlobalColor.black))
            time_str = QTime(hour, 0).toString("h:mm AP")
            painter.drawText(5, y + 4, time_str)
        
        # Draw appointments
        current_date_obj = self.current_date.toPyDate()
        day_charters = [c for c in self.charters if c['charter_date'] == current_date_obj]
        
        for charter in day_charters:
            self._draw_appointment_block(painter, charter, 80, width - 90, y_offset)
        
        # Set widget height
        total_height = y_offset + (self.end_hour - self.start_hour + 1) * self.hour_height + 20
        self.setMinimumHeight(total_height)
    
    def _paint_week_view(self, painter):
        """Paint week view with 7 columns."""
        width = self.width()
        day_of_week = self.current_date.dayOfWeek()
        
        if day_of_week == 7:  # Sunday
            week_start = self.current_date
        else:
            week_start = self.current_date.addDays(-day_of_week)
        
        # Column headers
        col_width = (width - 60) / 7
        painter.fillRect(0, 0, width, 40, QColor("#f0f0f0"))

        self.week_header_rects = []
        
        for i in range(7):
            date = week_start.addDays(i)
            x = 60 + i * col_width
            
            # Highlight today
            if date == QDate.currentDate():
                painter.fillRect(int(x), 0, int(col_width), 40, QColor("#0078d4"))
                painter.setPen(QPen(Qt.GlobalColor.white))
            else:
                painter.setPen(QPen(Qt.GlobalColor.black))
            
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            day_name = date.toString("ddd")
            day_num = date.toString("d")
            
            text_rect = QRect(int(x), 5, int(col_width), 30)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, f"{day_name}\n{day_num}")
            self.week_header_rects.append((text_rect, date))
        
        y_offset = 50
        self.appointment_rects = []
        
        # Draw time grid
        for hour in range(self.start_hour, self.end_hour + 1):
            y = y_offset + (hour - self.start_hour) * self.hour_height
            
            painter.setPen(QPen(QColor("#cccccc"), 1))
            painter.drawLine(60, y, width - 10, y)
            
            # Time label
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QPen(Qt.GlobalColor.black))
            time_str = QTime(hour, 0).toString("h AP")
            painter.drawText(5, y + 4, time_str)
            
            # Vertical column dividers
            for i in range(1, 7):
                x = int(60 + i * col_width)
                painter.setPen(QPen(QColor("#e0e0e0"), 1))
                painter.drawLine(x, 40, x, y + self.hour_height)
        
        # Draw appointments for each day
        for i in range(7):
            date = week_start.addDays(i)
            date_obj = date.toPyDate()
            day_charters = [c for c in self.charters if c['charter_date'] == date_obj]
            
            x_start = 60 + i * col_width + 2
            x_width = col_width - 4
            
            for charter in day_charters:
                self._draw_appointment_block(painter, charter, int(x_start), int(x_width), y_offset)
        
        total_height = y_offset + (self.end_hour - self.start_hour + 1) * self.hour_height + 20
        self.setMinimumHeight(total_height)
    
    def _paint_month_view(self, painter):
        """Paint month view with date cells."""
        width = self.width()
        height = max(self.height(), 600)
        
        # Month grid: 5-6 rows, 7 columns
        cell_width = width / 7
        cell_height = (height - 40) / 6
        
        # Day headers
        painter.fillRect(0, 0, width, 30, QColor("#f0f0f0"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        
        days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        for i, day in enumerate(days):
            x = i * cell_width
            painter.setPen(QPen(Qt.GlobalColor.black))
            painter.drawText(QRect(int(x), 0, int(cell_width), 30), 
                           Qt.AlignmentFlag.AlignCenter, day[:3])
        
        # Get first day of month
        first_day = QDate(self.current_date.year(), self.current_date.month(), 1)
        first_day_of_week = first_day.dayOfWeek()
        if first_day_of_week == 7:  # Sunday
            first_day_of_week = 0
        
        # Calculate start date (may be in previous month)
        calendar_start = first_day.addDays(-first_day_of_week)
        
        self.appointment_rects = []
        self.day_cell_rects = []
        
        # Draw 42 days (6 weeks)
        for week in range(6):
            for day in range(7):
                current_date = calendar_start.addDays(week * 7 + day)
                x = day * cell_width
                y = 30 + week * cell_height
                
                # Cell background
                if current_date.month() != self.current_date.month():
                    # Other month - lighter background
                    painter.fillRect(int(x), int(y), int(cell_width), int(cell_height), 
                                   QColor("#fafafa"))
                else:
                    painter.fillRect(int(x), int(y), int(cell_width), int(cell_height), 
                                   QColor("#ffffff"))
                
                # Today highlight
                if current_date == QDate.currentDate():
                    painter.fillRect(int(x), int(y), int(cell_width), int(cell_height), 
                                   QColor("#e3f2fd"))
                
                # Cell border
                painter.setPen(QPen(QColor("#e0e0e0"), 1))
                painter.drawRect(int(x), int(y), int(cell_width), int(cell_height))

                self.day_cell_rects.append((QRect(int(x), int(y), int(cell_width), int(cell_height)), current_date))
                
                # Date number
                painter.setFont(QFont("Segoe UI", 10))
                if current_date == QDate.currentDate():
                    painter.setPen(QPen(QColor("#0078d4")))
                    painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                else:
                    painter.setPen(QPen(Qt.GlobalColor.black))
                
                painter.drawText(int(x + 5), int(y + 18), current_date.toString("d"))
                
                # Draw appointments as small blocks
                date_obj = current_date.toPyDate()
                day_charters = [c for c in self.charters if c['charter_date'] == date_obj]
                
                y_apt = int(y + 25)
                for idx, charter in enumerate(day_charters[:6]):  # Max 6 per day
                    color = self._get_charter_color(charter)
                    painter.fillRect(int(x + 3), y_apt, int(cell_width - 6), 16, color)
                    
                    # Appointment text
                    painter.setPen(QPen(Qt.GlobalColor.white))
                    painter.setFont(QFont("Segoe UI", 7))
                    
                    time_str = ""
                    if charter.get('pickup_time'):
                        try:
                            t = charter['pickup_time']
                            if isinstance(t, str):
                                time_str = datetime.strptime(t, "%H:%M:%S").strftime("%I:%M%p ")
                            else:
                                time_str = t.strftime("%I:%M%p ")
                        except:
                            pass
                    
                    client = charter.get('client_display_name') or 'Unknown'
                    text = f"{time_str}{client[:15]}"
                    painter.drawText(int(x + 5), y_apt + 11, text)
                    
                    y_apt += 18
                
                # Show "+N more" if too many
                if len(day_charters) > 6:
                    painter.setPen(QPen(QColor("#666666")))
                    painter.setFont(QFont("Segoe UI", 7))
                    painter.drawText(int(x + 5), y_apt + 11, f"+{len(day_charters) - 6} more")
        
        self.setMinimumHeight(int(height))

    def _paint_year_view(self, painter):
        """Paint year view with 12 month cells for drilldown."""
        width = self.width()
        height = max(self.height(), 600)

        painter.fillRect(0, 0, width, 40, QColor("#f0f0f0"))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.setPen(QPen(Qt.GlobalColor.black))
        painter.drawText(10, 25, self.current_date.toString("yyyy"))

        cols = 3
        rows = 4
        cell_width = width / cols
        cell_height = (height - 40) / rows

        self.month_cell_rects = []

        month_idx = 1
        for r in range(rows):
            for c in range(cols):
                x = c * cell_width
                y = 40 + r * cell_height
                rect = QRect(int(x), int(y), int(cell_width), int(cell_height))

                painter.setPen(QPen(QColor("#e0e0e0"), 1))
                painter.drawRect(rect)

                month_date = QDate(self.current_date.year(), month_idx, 1)
                painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
                painter.setPen(QPen(Qt.GlobalColor.black))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, month_date.toString("MMMM"))

                self.month_cell_rects.append((rect, month_date))
                month_idx += 1

        self.setMinimumHeight(int(height))
    
    def _draw_appointment_block(self, painter, charter, x_start, x_width, y_offset):
        """Draw appointment block(s) - multiple blocks for split runs with gaps."""
        # Get route events (splits for split runs)
        route_segments = self._get_route_events(charter)
        
        if not route_segments:
            # No time data - draw simple placeholder
            self._draw_single_block(painter, charter, x_start, x_width, y_offset, None, None, "")
            return
        
        # Draw each segment
        for segment in route_segments:
            self._draw_single_block(
                painter, charter, x_start, x_width, y_offset,
                segment['start_time'], segment['end_time'], segment['label']
            )
    
    def _draw_single_block(self, painter, charter, x_start, x_width, y_offset, start_time, end_time, label):
        """Draw a single calendar block for one segment of a charter."""
        if not start_time or not end_time:
            # All-day or no time - draw at top
            y = y_offset
            height = 40
        else:
            try:
                # Parse start time
                if isinstance(start_time, str):
                    t_start = datetime.strptime(start_time, "%H:%M:%S").time()
                else:
                    t_start = start_time
                
                # Parse end time
                if isinstance(end_time, str):
                    t_end = datetime.strptime(end_time, "%H:%M:%S").time()
                else:
                    t_end = end_time
                
                # Calculate Y position from start time
                hour_start = t_start.hour + t_start.minute / 60.0
                if hour_start < self.start_hour:
                    hour_start = self.start_hour
                if hour_start > self.end_hour:
                    hour_start = self.end_hour
                
                y = y_offset + int((hour_start - self.start_hour) * self.hour_height)
                
                # Calculate duration
                duration_minutes = (t_end.hour * 60 + t_end.minute) - (t_start.hour * 60 + t_start.minute)
                if duration_minutes < 0:  # Overnight
                    duration_minutes += 24 * 60
                duration_hours = duration_minutes / 60.0
                
                height = int(self.hour_height * duration_hours)
                
                # Ensure event doesn't go past end of day
                max_y = y_offset + (self.end_hour - self.start_hour) * self.hour_height
                if y + height > max_y:
                    height = max_y - y
                
                # Minimum height for visibility
                if height < 40:
                    height = 40
                
            except Exception as e:
                y = y_offset
                height = 40
        
        # Get color based on sync status and charter type
        color = self._get_charter_color(charter)
        
        # Draw appointment rectangle
        rect = QRect(x_start, y, x_width, height)
        painter.fillRect(rect, color)
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.drawRect(rect)
        
        # Store for click detection
        charter_copy = charter.copy()
        charter_copy['_rect'] = rect
        self.appointment_rects.append(charter_copy)
        
        # Draw text - Outlook-style title format
        painter.setPen(QPen(Qt.GlobalColor.white))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        
        # Build title: "Vehicle - Client Name" (exclude notes - they're billing/email data)
        vehicle = charter.get('vehicle_number') or ''
        client = charter.get('client_display_name') or 'Unknown'
        
        title_parts = []
        if label:  # Add leg label for split runs
            title_parts.append(label)
        if vehicle:
            title_parts.append(vehicle)
        title_parts.append(client)
        
        title = ' - '.join(title_parts)
        painter.drawText(rect.adjusted(5, 5, -5, -5), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, 
                        title)
        
        # Time and reserve number on second line (+ expired flag)
        painter.setFont(QFont("Segoe UI", 8))
        reserve = charter.get('reserve_number', '')
        time_str = ""
        if start_time:
            try:
                if isinstance(start_time, str):
                    t = datetime.strptime(start_time, "%H:%M:%S").time()
                else:
                    t = start_time
                time_str = t.strftime("%I:%M %p")
            except:
                pass

        expired_flag = ""
        try:
            qexp = charter.get('quote_expires_at')
            if qexp and (charter.get('booking_status','') or '').lower() in ('quote','quoted'):
                from datetime import datetime as _dt
                qexp_dt = None
                if isinstance(qexp, str):
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
                        try:
                            qexp_dt = _dt.strptime(qexp, fmt)
                            break
                        except Exception:
                            qexp_dt = None
                    if qexp_dt is None and 'T' in qexp:
                        try:
                            qexp_dt = _dt.fromisoformat(qexp)
                        except Exception:
                            qexp_dt = None
                else:
                    qexp_dt = qexp if hasattr(qexp, 'timestamp') else None
                if qexp_dt and _dt.now() > qexp_dt:
                    expired_flag = "  ⚠ Expired"
        except Exception:
            expired_flag = ""

        painter.drawText(
            rect.adjusted(5, 25, -5, -5),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            f"{time_str} • #{reserve}{expired_flag}"
        )
    
    def _get_charter_color(self, charter):
        """Determine color based on sync status, status, and type."""
        status = charter.get('status', '')
        booking_type = charter.get('booking_type', '')
        sync_color = charter.get('calendar_color', '')
        
        # Cancelled - gray
        if status and 'cancel' in status.lower():
            return QColor("#757575")
        
        # Quote - purple (darker if expired)
        if booking_type and 'quote' in booking_type.lower():
            expired = False
            try:
                qexp = charter.get('quote_expires_at')
                if qexp:
                    from datetime import datetime as _dt
                    qexp_dt = None
                    if isinstance(qexp, str):
                        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
                            try:
                                qexp_dt = _dt.strptime(qexp, fmt)
                                break
                            except Exception:
                                qexp_dt = None
                        if qexp_dt is None and 'T' in qexp:
                            try:
                                qexp_dt = _dt.fromisoformat(qexp)
                            except Exception:
                                qexp_dt = None
                    else:
                        qexp_dt = qexp if hasattr(qexp, 'timestamp') else None
                    expired = qexp_dt is not None and _dt.now() > qexp_dt
            except Exception:
                expired = False
            return QColor("#6a1b9a") if not expired else QColor("#4a148c")
        
        # Sync status colors
        if sync_color == 'green':
            return QColor("#4caf50")  # Green - synced
        elif sync_color == 'red':
            return QColor("#f44336")  # Red - not in calendar
        elif sync_color == 'yellow':
            return QColor("#ff9800")  # Orange/yellow - mismatch
        elif sync_color == 'blue':
            return QColor("#2196f3")  # Blue - recently synced
        elif sync_color == 'gray':
            return QColor("#9e9e9e")  # Gray - cancelled
        
        # Default - teal (no sync status)
        return QColor("#009688")
    
    def mousePressEvent(self, event: QMouseEvent):
        """Handle clicks on appointments."""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            
            # Check if clicked on an appointment
            for charter in self.appointment_rects:
                if '_rect' in charter and charter['_rect'].contains(pos):
                    self._show_charter_details(charter)
                    return

            # Drilldown: Year -> Month
            if self.view_mode == 'year':
                for rect, date in self.month_cell_rects:
                    if rect.contains(pos) and self.parent_widget:
                        self.parent_widget.drill_to_month(date)
                        return

            # Drilldown: Month -> Week
            if self.view_mode == 'month':
                for rect, date in self.day_cell_rects:
                    if rect.contains(pos) and self.parent_widget:
                        self.parent_widget.drill_to_week(date)
                        return

            # Drilldown: Week -> Day (click on day header)
            if self.view_mode == 'week':
                for rect, date in self.week_header_rects:
                    if rect.contains(pos) and self.parent_widget:
                        self.parent_widget.drill_to_day(date)
                        return
    
    def _show_charter_details(self, charter):
        """Open Charter Details dialog for the selected event."""
        reserve_number = charter.get('reserve_number')
        if not reserve_number:
            QMessageBox.information(self, "Charter Details", "Missing reserve number for this event.")
            return

        try:
            from drill_down_widgets import CharterDetailDialog
            dialog = CharterDetailDialog(self.db, reserve_number, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(self, "Charter Details", f"Failed to open details: {e}")
