"""
Dispatcher Calendar Widget
- Calendar view for dispatchers with day drill-down
- Shows bookings/quotes/charters; color codes unassigned, driver/vehicle unavailable
- Tasks: create/verify, warning templates (e.g., ensure client pays before run)
- Payment pre-check via reserve_number using payments table if present
- Schema-safe: only uses columns that exist (via information_schema)
- Outlook sync integration: Color-coded sync status with right-click menu actions
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCalendarWidget, QTableWidget,
    QTableWidgetItem, QPushButton, QSplitter, QGroupBox, QFormLayout, QLineEdit,
    QTextEdit, QListWidget, QListWidgetItem, QMessageBox, QMenu
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QBrush, QColor
from pathlib import Path
import json
from datetime import datetime
from PyQt6.QtGui import QFont, QColor, QBrush
from datetime import datetime
import os
import json

class DispatcherCalendarWidget(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self._ensure_storage()
        self._init_ui()
        self._load_day(QDate.currentDate())

    def _ensure_storage(self):
        base = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'reports')
        os.makedirs(base, exist_ok=True)
        self.task_path = os.path.join(base, 'dispatch_tasks.json')
        if not os.path.exists(self.task_path):
            with open(self.task_path, 'w', encoding='utf-8') as f:
                json.dump([], f)

    def _init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("🗓️ Charter Dispatch Calendar")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left calendar
        left = QWidget(); left_layout = QVBoxLayout()
        self.calendar = QCalendarWidget(); self.calendar.setGridVisible(True)
        self.calendar.selectionChanged.connect(lambda: self._load_day(self.calendar.selectedDate()))
        self.calendar.clicked.connect(self._load_day)
        left_layout.addWidget(self.calendar)
        
        # Load initial month's charter dates
        self._highlight_charter_dates()
        
        left.setLayout(left_layout)
        splitter.addWidget(left)

        # Right panel: day table + task pane
        right = QWidget(); right_layout = QVBoxLayout()

        self.day_table = QTableWidget()
        self.day_table.setColumnCount(10)
        self.day_table.setHorizontalHeaderLabels([
            "Reserve #", "Type", "Charter ID", "Pickup", "Depart Yard", "Vehicle", "Driver", "Status", "Outlook", "Alerts"
        ])
        self.day_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.day_table.customContextMenuRequested.connect(self._show_context_menu)
        self.day_table.cellDoubleClicked.connect(self._open_booking_from_calendar)
        right_layout.addWidget(self.day_table)

        actions = QHBoxLayout()
        self.btn_create_task = QPushButton("➕ Create Task")
        self.btn_verify_task = QPushButton("✅ Mark Task Done")
        self.btn_prepayment = QPushButton("⚠️ Prepayment Check")
        self.btn_sync_parse = QPushButton("⬇️ Parse Outlook (Review)")
        self.btn_update_calendar = QPushButton("🔄 Update Calendar (Individual)")
        self.btn_create_task.clicked.connect(self._create_task)
        self.btn_verify_task.clicked.connect(self._verify_selected_task)
        self.btn_prepayment.clicked.connect(self._prepayment_check_selected)
        self.btn_sync_parse.clicked.connect(self._parse_outlook_and_review)
        self.btn_update_calendar.clicked.connect(self._update_calendar_individual_approval)
        actions.addWidget(self.btn_create_task)
        actions.addWidget(self.btn_verify_task)
        actions.addWidget(self.btn_prepayment)
        actions.addWidget(self.btn_sync_parse)
        actions.addWidget(self.btn_update_calendar)
        right_layout.addLayout(actions)

        box = QGroupBox("Tasks for Selected Date")
        box_layout = QVBoxLayout()
        self.task_list = QListWidget()
        box_layout.addWidget(self.task_list)
        box.setLayout(box_layout)
        right_layout.addWidget(box)

        right.setLayout(right_layout)
        splitter.addWidget(right)

        splitter.setSizes([400, 600])
        layout.addWidget(splitter)
        self.setLayout(layout)

    def _highlight_charter_dates(self):
        """Highlight dates that have charters in the current month"""
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
            year_month = self.calendar.selectedDate()
            start_date = QDate(year_month.year(), year_month.month(), 1)
            # Get last day of month
            if year_month.month() == 12:
                end_date = QDate(year_month.year() + 1, 1, 1).addDays(-1)
            else:
                end_date = QDate(year_month.year(), year_month.month() + 1, 1).addDays(-1)
            
            cur.execute("""
                SELECT DISTINCT charter_date 
                FROM charters 
                WHERE charter_date >= %s AND charter_date <= %s
                    AND (status IS NULL OR status NOT IN ('cancelled','no-show'))
            """, (start_date.toString("yyyy-MM-dd"), end_date.toString("yyyy-MM-dd")))
            
            # Highlight each date with charters
            date_format = self.calendar.dateTextFormat(QDate())
            charter_format = self.calendar.dateTextFormat(QDate())
            charter_format.setBackground(QBrush(QColor(173, 216, 230)))  # Light blue
            charter_format.setFontWeight(QFont.Weight.Bold)
            
            for row in cur.fetchall():
                if row[0]:
                    # Convert database date to QDate
                    date_obj = QDate.fromString(str(row[0]), "yyyy-MM-dd")
                    if date_obj.isValid():
                        self.calendar.setDateTextFormat(date_obj, charter_format)
        except Exception as e:
            print(f"Failed to highlight charter dates: {e}")

    # ===== Data load =====
    def _cols(self, table):
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
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name=%s
            """, (table,))
            return {r[0] for r in cur.fetchall()}
        except Exception:
            return set()

    def _load_day(self, qdate: QDate):
        # Convert to database-compatible date format (YYYY-MM-DD)
        date_str = qdate.toString("yyyy-MM-dd")
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
            ccols = self._cols('charters'); ecols = self._cols('employees'); vcols = self._cols('vehicles')
            
            # Check if calendar sync columns exist
            has_calendar_sync = all(col in ccols for col in ['calendar_color', 'calendar_sync_status', 'calendar_notes'])
            
            desired = ['reserve_number','charter_id','status','pickup_time','depart_yard_time','vehicle_id','employee_id','customer_name','booking_type']
            # include optional expiration column if present
            if 'quote_expires_at' in ccols:
                desired.append('quote_expires_at')
            if has_calendar_sync:
                desired.extend(['calendar_color','calendar_sync_status','calendar_notes'])
            
            select_cols = [c for c in desired if c in ccols]
            sel = ", ".join(select_cols) if select_cols else 'reserve_number, charter_id'
            cur.execute(f"""
                SELECT {sel}
                FROM charters
                WHERE charter_date = %s AND (status IS NULL OR status NOT IN ('cancelled','no-show'))
                ORDER BY pickup_time NULLS LAST
            """, (date_str,))
            rows = cur.fetchall()
            self.day_table.setRowCount(len(rows))
            self.task_list.clear()

            # load tasks for date
            tasks = self._read_tasks_for_date(date_str)
            for t in tasks:
                item = QListWidgetItem(f"[{t.get('status','open')}] {t.get('text','')} (reserve {t.get('reserve_number','')})")
                self.task_list.addItem(item)

            for r, row in enumerate(rows):
                data = dict(zip(select_cols, row)) if select_cols else {}
                reserve = str(data.get('reserve_number') or '')
                charter_id = str(data.get('charter_id') or '')
                status = str(data.get('status') or '')
                pickup = str(data.get('pickup_time') or '')
                depart = str(data.get('depart_yard_time') or '')
                vehicle = self._vehicle_display(vcols, data.get('vehicle_id'))
                driver = self._driver_display(ecols, data.get('employee_id'))
                ctype = self._charter_type(data)
                
                # Outlook sync status (only if columns exist)
                if has_calendar_sync:
                    cal_color = str(data.get('calendar_color') or '')
                    cal_status = str(data.get('calendar_sync_status') or 'not_synced')
                    cal_notes = str(data.get('calendar_notes') or '')
                    outlook_indicator = self._outlook_status_display(cal_color, cal_status)
                else:
                    outlook_indicator = ''  # Empty if sync not enabled
                    cal_color = ''
                    cal_status = 'not_enabled'
                    cal_notes = ''
                
                alerts = self._alerts_for_row(status, driver, vehicle, date_str, reserve)

                # Expiration warning for quotes
                expired = False
                try:
                    qexp = data.get('quote_expires_at')
                    if qexp and (isinstance(qexp, str) or hasattr(qexp, 'isoformat')):
                        # normalize to datetime for comparison
                        from datetime import datetime as _dt
                        if isinstance(qexp, str):
                            # Accept common timestamp/date string formats
                            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
                                try:
                                    qexp_dt = _dt.strptime(qexp, fmt)
                                    break
                                except Exception:
                                    qexp_dt = None
                            if qexp_dt is None:
                                qexp_dt = _dt.fromisoformat(qexp) if 'T' in qexp else None
                        else:
                            qexp_dt = qexp if hasattr(qexp, 'timestamp') else None
                        if qexp_dt and (status.lower() == 'quote') and _dt.now() > qexp_dt:
                            expired = True
                except Exception:
                    expired = False

                if expired:
                    alerts = (alerts + ", " if alerts else "") + "Expired Quote"

                items = [
                    QTableWidgetItem(reserve), QTableWidgetItem(ctype), QTableWidgetItem(charter_id),
                    QTableWidgetItem(pickup), QTableWidgetItem(depart), QTableWidgetItem(vehicle),
                    QTableWidgetItem(driver), QTableWidgetItem(status), QTableWidgetItem(outlook_indicator), QTableWidgetItem(alerts)
                ]
                for c, it in enumerate(items):
                    self.day_table.setItem(r, c, it)
                
                # Apply Outlook sync color to indicator column (column 8)
                outlook_item = items[8]
                if cal_color == 'green':
                    outlook_item.setBackground(QBrush(QColor('#d4edda')))  # light green
                    outlook_item.setForeground(QBrush(QColor('#155724')))  # dark green text
                elif cal_color == 'red':
                    outlook_item.setBackground(QBrush(QColor('#f8d7da')))  # light red
                    outlook_item.setForeground(QBrush(QColor('#721c24')))  # dark red text
                elif cal_color == 'yellow':
                    outlook_item.setBackground(QBrush(QColor('#fff3cd')))  # light yellow
                    outlook_item.setForeground(QBrush(QColor('#856404')))  # dark yellow text
                elif cal_color == 'blue':
                    outlook_item.setBackground(QBrush(QColor('#d1ecf1')))  # light blue
                    outlook_item.setForeground(QBrush(QColor('#0c5460')))  # dark blue text
                elif cal_color == 'gray':
                    outlook_item.setBackground(QBrush(QColor('#e2e3e5')))  # light gray
                    outlook_item.setForeground(QBrush(QColor('#383d41')))  # dark gray text
                
                # Tooltip with sync details
                if cal_notes:
                    outlook_item.setToolTip(f"{cal_status}\n{cal_notes}")
                else:
                    outlook_item.setToolTip(cal_status)

                # color coding for row alerts
                if 'unassigned' in alerts.lower():
                    self._paint_row_except_outlook(r, QColor('#fff3cd'))  # yellow
                elif 'vehicle unavailable' in alerts.lower():
                    self._paint_row_except_outlook(r, QColor('#f8d7da'))  # red
                elif ctype == 'Quote':
                    # Light blue for quotes; expired quotes slightly different tint
                    self._paint_row_except_outlook(r, QColor('#e3f2fd' if not expired else '#fce4ec'))
        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Failed to load: {e}")

    def _outlook_status_display(self, cal_color: str, cal_status: str) -> str:
        """Return emoji indicator for Outlook sync status."""
        emoji_map = {
            'green': '🟢',   # synced
            'red': '🔴',      # not in calendar
            'yellow': '🟡',   # mismatch
            'blue': '🔵',     # recently updated
            'gray': '⚫'       # cancelled
        }
        return emoji_map.get(cal_color, '⚪')  # white circle for unknown
    
    def _paint_row(self, row: int, color: QColor):
        for c in range(self.day_table.columnCount()):
            item = self.day_table.item(row, c)
            if item:
                item.setBackground(QBrush(color))
    
    def _paint_row_except_outlook(self, row: int, color: QColor):
        """Paint row background except Outlook column (col 8) which has its own colors."""
        for c in range(self.day_table.columnCount()):
            if c == 8:  # Skip Outlook column
                continue
            item = self.day_table.item(row, c)
            if item:
                item.setBackground(QBrush(color))

    def _charter_type(self, data):
        bt = str(data.get('booking_type') or '')
        if bt.lower() in ('quote','quoted'): return 'Quote'
        if bt.lower() in ('booking','booked'): return 'Booking'
        return 'Charter'

    def _vehicle_display(self, vcols, vehicle_id):
        if not vehicle_id or 'vehicle_id' not in vcols:
            return ''
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
            # Force use of vehicle_number for consistency across reports
            sel = 'vehicle_number'
            cur.execute(f"SELECT {sel}, operational_status FROM vehicles WHERE vehicle_id=%s", (vehicle_id,))
            r = cur.fetchone()
            if not r: return ''
            parts = [str(x) for x in r[:-1] if x]
            status = str(r[-1] or '')
            disp = ' / '.join(parts)
            if status and status.lower() not in ('active','active '):
                disp += f" (status: {status})"
            return disp
        except Exception:
            return ''

    def _driver_display(self, ecols, employee_id):
        if not employee_id or 'employee_id' not in ecols:
            return ''
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
            cols = [c for c in ['full_name','phone_number','employment_status','is_active'] if c in ecols]
            sel = ', '.join(cols) if cols else 'full_name'
            cur.execute(f"SELECT {sel} FROM employees WHERE employee_id=%s", (employee_id,))
            r = cur.fetchone()
            if not r: return ''
            return ' / '.join([str(x) for x in r if x])
        except Exception:
            return ''

    def _alerts_for_row(self, status, driver_disp, vehicle_disp, date_str, reserve):
        alerts = []
        if not driver_disp:
            alerts.append('Unassigned driver')
        if vehicle_disp.endswith(')') and 'status:' in vehicle_disp:
            alerts.append('Vehicle unavailable')
        if not self._has_prepayment(reserve):
            alerts.append('Prepayment pending')
        # Add task count for day
        tasks = self._read_tasks_for_date(date_str)
        t_for_res = [t for t in tasks if t.get('reserve_number') == reserve and t.get('status','open') == 'open']
        if t_for_res:
            alerts.append(f"{len(t_for_res)} open task(s)")
        return ', '.join(alerts)

    # ===== Tasks =====
    def _read_tasks(self):
        try:
            with open(self.task_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def _write_tasks(self, tasks):
        try:
            with open(self.task_path, 'w', encoding='utf-8') as f:
                json.dump(tasks, f, indent=2)
        except Exception as e:
            QMessageBox.warning(self, 'Task Save Error', str(e))

    def _read_tasks_for_date(self, date_str):
        return [t for t in self._read_tasks() if t.get('date') == date_str]

    def _create_task(self):
        items = self.day_table.selectedItems()
        date_str = self.calendar.selectedDate().toString('MM/dd/yyyy')
        reserve = items[0].text() if items else ''
        text = 'Buy beverages / Pre-start vehicle / Call client / Ensure payment.'
        tasks = self._read_tasks()
        tasks.append({
            'id': f"{reserve}_{int(datetime.now().timestamp())}",
            'reserve_number': reserve,
            'date': date_str,
            'text': text,
            'status': 'open'
        })
        self._write_tasks(tasks)
        self._load_day(self.calendar.selectedDate())

    def _verify_selected_task(self):
        # Mark first open task done for the selected reserve
        items = self.day_table.selectedItems()
        reserve = items[0].text() if items else ''
        tasks = self._read_tasks()
        for t in tasks:
            if t.get('reserve_number') == reserve and t.get('status','open') == 'open':
                t['status'] = 'done'
                break
        self._write_tasks(tasks)
        self._load_day(self.calendar.selectedDate())

    def _prepayment_check_selected(self):
        items = self.day_table.selectedItems()
        reserve = items[0].text() if items else ''
        ok = self._has_prepayment(reserve)
        QMessageBox.information(self, 'Prepayment', 'Paid/OK' if ok else 'Pending/Not found')

    def _has_prepayment(self, reserve_number: str) -> bool:
        if not reserve_number:
            return False
        # Check payments table for any rows with reserve_number
        try:
            pcols = self._cols('payments')
            if 'reserve_number' not in pcols:
                return False
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
            cur.execute("SELECT COUNT(*) FROM payments WHERE reserve_number=%s", (reserve_number,))
            return (cur.fetchone() or [0])[0] > 0
        except Exception:
            return False
    
    # ===== Outlook Sync Context Menu =====
    def _show_context_menu(self, position):
        """Right-click context menu for Outlook sync actions."""
        menu = QMenu()
        
        # Get selected charter
        row = self.day_table.currentRow()
        if row < 0:
            return
        
        reserve_item = self.day_table.item(row, 0)
        outlook_item = self.day_table.item(row, 8)
        if not reserve_item or not outlook_item:
            return
        
        reserve_number = reserve_item.text()
        outlook_indicator = outlook_item.text()
        
        # Menu actions based on sync status
        if outlook_indicator == '🔴':  # not in calendar
            sync_action = menu.addAction("🔄 Update ONLY This Charter to Outlook")
            sync_action.triggered.connect(lambda: self._sync_to_outlook(reserve_number))
        
        if outlook_indicator == '🟡':  # mismatch
            view_details = menu.addAction("📋 View Mismatch Details")
            view_details.triggered.connect(lambda: self._view_sync_details(reserve_number))
            
        if outlook_indicator in ['🟢', '🔵']:  # synced or updated
            mark_mismatch = menu.addAction("⚠️ Mark as Mismatch")
            mark_mismatch.triggered.connect(lambda: self._mark_mismatch(reserve_number))
        
        # Always show refresh option
        menu.addSeparator()
        refresh_action = menu.addAction("🔄 Refresh Sync Status")
        refresh_action.triggered.connect(lambda: self._refresh_sync_status())
        
        # Show legend
        legend_action = menu.addAction("ℹ️ Color Legend")
        legend_action.triggered.connect(self._show_color_legend)
        
        menu.exec(self.day_table.mapToGlobal(position))
    
    def _sync_to_outlook(self, reserve_number: str):
        """Sync a single charter to Outlook calendar."""
        try:
            import subprocess
            import sys
            
            # Call create_missing_outlook_appointments.py for this specific charter
            script_path = Path(__file__).parent.parent / 'scripts' / 'create_missing_outlook_appointments.py'
            result = subprocess.run(
                [sys.executable, str(script_path), '--reserve', reserve_number, '--write'],
                capture_output=True, text=True, encoding='utf-8'
            )
            
            if result.returncode == 0:
                QMessageBox.information(self, "Sync Success", 
                    f"Reserve {reserve_number} synced to Outlook.\n\n{result.stdout}")
                self._load_day(self.calendar.selectedDate())  # Refresh display
            else:
                QMessageBox.warning(self, "Sync Failed", 
                    f"Failed to sync reserve {reserve_number}.\n\n{result.stderr}")
        except Exception as e:
            QMessageBox.warning(self, "Sync Error", f"Error syncing to Outlook: {e}")
    
    def _view_sync_details(self, reserve_number: str):
        """Show calendar_notes and sync status details."""
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
            cur.execute("""
                SELECT calendar_sync_status, calendar_color, calendar_notes, outlook_entry_id
                FROM charters
                WHERE reserve_number = %s
            """, (reserve_number,))
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
                QMessageBox.warning(self, "Not Found", f"Reserve {reserve_number} not found")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load details: {e}")
    
    def _mark_mismatch(self, reserve_number: str):
        """Manually mark a charter as mismatch for re-verification."""
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
            cur.execute("""
                UPDATE charters
                SET calendar_sync_status = 'mismatch',
                    calendar_color = 'yellow',
                    calendar_notes = 'Manually marked for verification'
                WHERE reserve_number = %s
            """, (reserve_number,))
            self.db.connection.commit()
            QMessageBox.information(self, "Updated", f"Reserve {reserve_number} marked as mismatch")
            self._load_day(self.calendar.selectedDate())
        except Exception as e:
            self.db.connection.rollback()
            QMessageBox.warning(self, "Error", f"Failed to update: {e}")
    
    def _refresh_sync_status(self):
        """Re-run match_outlook_with_colors.py to refresh all sync statuses."""
        try:
            import subprocess
            import sys
            
            script_path = Path(__file__).parent.parent / 'scripts' / 'match_outlook_with_colors.py'
            result = subprocess.run(
                [sys.executable, str(script_path), '--year', '2026', '--apply-colors'],
                capture_output=True, text=True, encoding='utf-8'
            )
            
            if result.returncode == 0:
                QMessageBox.information(self, "Refresh Complete", 
                    f"Sync status refreshed.\n\n{result.stdout}")
                self._load_day(self.calendar.selectedDate())
            else:
                QMessageBox.warning(self, "Refresh Failed", 
                    f"Failed to refresh sync status.\n\n{result.stderr}")
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.warning(self, "Refresh Error", f"Error refreshing: {e}")
    
    def _show_color_legend(self):
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
    def _parse_outlook_and_review(self):
        """Extract Outlook calendar, run matcher, and prompt to add clients when needed."""
        try:
            import subprocess, sys, json
            from pathlib import Path
            base = Path(__file__).parent.parent
            extract = base / 'scripts' / 'extract_outlook_calendar.py'
            match = base / 'scripts' / 'match_outlook_calendar_to_charters.py'
            reports_dir = base / 'reports'
            reports_dir.mkdir(exist_ok=True)
            cal_json = reports_dir / 'outlook_calendar_arrow_new.json'
            mismatches_json = reports_dir / 'outlook_calendar_mismatches.json'

            # Step 1: Extract calendar
            r1 = subprocess.run([sys.executable, str(extract), '--calendar', 'arrow new', '--output', str(cal_json)],
                                capture_output=True, text=True, encoding='utf-8')
            if r1.returncode != 0:
                QMessageBox.warning(self, 'Outlook Parse', f'Failed to extract calendar.\n\n{r1.stderr}')
                return

            # Step 2: Match to DB (dry-run) and produce mismatches JSON
            r2 = subprocess.run([sys.executable, str(match), '--input', str(cal_json), '--excel', str(reports_dir / 'outlook_calendar_mismatches.xlsx'), '--json', str(mismatches_json)],
                                capture_output=True, text=True, encoding='utf-8')
            if r2.returncode != 0:
                QMessageBox.warning(self, 'Outlook Match', f'Failed to match calendar.\n\n{r2.stderr}')
                return

            # Load mismatches JSON
            if mismatches_json.exists():
                with open(mismatches_json, 'r', encoding='utf-8') as f:
                    mm = json.load(f)
            else:
                mm = {}

            # Show summary (all charters already created, just reviewing sync status)
            matched = mm.get('no_charter_found') or []
            needs = mm.get('needs_client_creation') or []
            email_matched = mm.get('client_email_matched') or []
            
            summary = f"Outlook sync review complete.\n\n"
            summary += f"Appointments with reserve numbers: {len([a for a in mm.get('no_charter_found', []) if a.get('reserve_number')])}\n"
            summary += f"Client email matches found: {len(email_matched)}\n"
            summary += f"Unmatched (may need review): {len(needs)}\n\n"
            summary += f"Excel report: reports/outlook_calendar_mismatches.xlsx\n"
            summary += f"JSON report: reports/outlook_calendar_mismatches.json"
            
            QMessageBox.information(self, 'Outlook Review', summary)
            # Reload day view to show updated colors
            self._load_day(self.calendar.selectedDate())
        except Exception as e:
            QMessageBox.warning(self, 'Outlook Parse', f'Error during Outlook review: {e}')
    
    def _update_calendar_individual_approval(self):
        """
        Compare ALMS charters with Outlook calendar and request individual approval
        for each discrepancy before updating.
        """
        try:
            import subprocess, sys, json
            from pathlib import Path
            from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QGridLayout
            
            # Get current date range (visible month)
            selected_date = self.calendar.selectedDate()
            start_date = QDate(selected_date.year(), selected_date.month(), 1)
            if selected_date.month() == 12:
                end_date = QDate(selected_date.year() + 1, 1, 1).addDays(-1)
            else:
                end_date = QDate(selected_date.year(), selected_date.month() + 1, 1).addDays(-1)
            
            # Extract Outlook calendar
            base = Path(__file__).parent.parent
            extract = base / 'scripts' / 'extract_outlook_calendar.py'
            reports_dir = base / 'reports'
            reports_dir.mkdir(exist_ok=True)
            cal_json = reports_dir / 'outlook_calendar_arrow_new.json'
            
            r1 = subprocess.run([sys.executable, str(extract), '--calendar', 'arrow new', '--output', str(cal_json)],
                                capture_output=True, text=True, encoding='utf-8')
            if r1.returncode != 0:
                QMessageBox.warning(self, 'Outlook Extract', f'Failed to extract Outlook calendar.\n\n{r1.stderr}')
                return
            
            # Load Outlook calendar data
            with open(cal_json, 'r', encoding='utf-8') as f:
                outlook_events = json.load(f)
            
            # Get ALMS charters for date range
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT reserve_number, charter_date, pickup_time, customer_name, 
                       vehicle_id, employee_id, calendar_notes, calendar_sync_status,
                       outlook_entry_id
                FROM charters
                WHERE charter_date BETWEEN %s AND %s
                  AND (status IS NULL OR status NOT IN ('cancelled','no-show'))
                ORDER BY charter_date, pickup_time
            """, (start_date.toString("yyyy-MM-dd"), end_date.toString("yyyy-MM-dd")))
            
            alms_charters = cur.fetchall()
            
            # Find discrepancies
            discrepancies = []
            outlook_dict = {evt.get('subject', '').split()[-1] if evt.get('subject') else '': evt 
                           for evt in outlook_events}
            
            for charter in alms_charters:
                reserve_num, date, pickup, customer, vehicle_id, employee_id, notes, sync_status, outlook_id = charter
                
                # Find matching Outlook event
                outlook_match = None
                if reserve_num in outlook_dict:
                    outlook_match = outlook_dict[reserve_num]
                elif outlook_id:
                    outlook_match = next((e for e in outlook_events if e.get('entry_id') == outlook_id), None)
                
                # Compare fields
                if outlook_match:
                    differences = []
                    
                    # Compare date
                    outlook_date = outlook_match.get('start', '').split('T')[0] if outlook_match.get('start') else ''
                    if str(date) != outlook_date:
                        differences.append(f"Date: ALMS={date}, Outlook={outlook_date}")
                    
                    # Compare time
                    outlook_time = outlook_match.get('start', '').split('T')[1][:5] if 'T' in outlook_match.get('start', '') else ''
                    if str(pickup) != outlook_time:
                        differences.append(f"Time: ALMS={pickup}, Outlook={outlook_time}")
                    
                    # Compare location
                    alms_location = notes.split('\n')[0] if notes else ''
                    outlook_location = outlook_match.get('location', '')
                    if alms_location and outlook_location and alms_location != outlook_location:
                        differences.append(f"Location: ALMS={alms_location}, Outlook={outlook_location}")
                    
                    if differences:
                        discrepancies.append({
                            'reserve_number': reserve_num,
                            'charter_date': str(date),
                            'customer': customer,
                            'differences': differences,
                            'alms_data': charter,
                            'outlook_data': outlook_match
                        })
                else:
                    # Charter exists in ALMS but not in Outlook
                    discrepancies.append({
                        'reserve_number': reserve_num,
                        'charter_date': str(date),
                        'customer': customer,
                        'differences': ['Charter not found in Outlook calendar'],
                        'alms_data': charter,
                        'outlook_data': None
                    })
            
            if not discrepancies:
                QMessageBox.information(self, 'Calendar Sync', 
                    'No discrepancies found between ALMS and Outlook calendars.')
                return
            
            # Show individual approval dialog for each discrepancy
            approved_updates = []
            skipped_updates = []
            
            for i, disc in enumerate(discrepancies, 1):
                reply = self._show_discrepancy_approval_dialog(
                    disc, i, len(discrepancies)
                )
                
                if reply == 'approve':
                    approved_updates.append(disc)
                elif reply == 'skip':
                    skipped_updates.append(disc)
                elif reply == 'cancel':
                    break
            
            # Apply approved updates
            if approved_updates:
                self._apply_calendar_updates(approved_updates)
                QMessageBox.information(self, 'Updates Applied',
                    f"Updated {len(approved_updates)} calendar events.\n"
                    f"Skipped {len(skipped_updates)} events.")
            else:
                QMessageBox.information(self, 'No Updates', 
                    'No updates were approved.')
            
            # Reload view
            self._load_day(self.calendar.selectedDate())
            
        except Exception as e:
            QMessageBox.warning(self, 'Calendar Update', f'Error during calendar update: {e}')
    
    def _show_discrepancy_approval_dialog(self, discrepancy, current, total):
        """Show dialog asking for approval of individual calendar update"""
        from PyQt6.QtWidgets import QDialog
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Calendar Update Approval ({current}/{total})")
        dialog.setMinimumWidth(600)
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel(f"<b>Reserve #{discrepancy['reserve_number']} - {discrepancy['customer']}</b>")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Discrepancies
        disc_group = QGroupBox("Discrepancies Found")
        disc_layout = QVBoxLayout()
        
        for diff in discrepancy['differences']:
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
            return 'approve'
        elif result == 2:
            return 'skip'
        else:
            return 'cancel'
    
    def _apply_calendar_updates(self, approved_updates):
        """Apply approved calendar updates to Outlook"""
        import subprocess
        import sys
        from pathlib import Path
        
        base = Path(__file__).parent.parent
        update_script = base / 'scripts' / 'update_outlook_calendar_event.py'
        
        for update in approved_updates:
            try:
                reserve_num = update['reserve_number']
                
                # Run update script for this charter
                result = subprocess.run(
                    [sys.executable, str(update_script), '--reserve', reserve_num],
                    capture_output=True, text=True, encoding='utf-8'
                )
                
                if result.returncode == 0:
                    # Update sync status in database
                    try:
                        self.db.rollback()
                    except:
                        pass
                    
                    cur = self.db.get_cursor()
                    cur.execute("""
                        UPDATE charters
                        SET calendar_sync_status = 'synced',
                            calendar_color = 'green',
                            updated_at = NOW()
                        WHERE reserve_number = %s
                    """, (reserve_num,))
                    self.db.commit()
                else:
                    print(f"Failed to update {reserve_num}: {result.stderr}")
                    
            except Exception as e:
                print(f"Error updating {update.get('reserve_number')}: {e}")
    
    def _open_booking_from_calendar(self, row, column):
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
            
            type_item = self.day_table.item(row, 1)
            event_type = type_item.text() if type_item else ""
            
            charter_id_item = self.day_table.item(row, 2)
            charter_id = charter_id_item.text() if charter_id_item else ""
            
            pickup_item = self.day_table.item(row, 3)
            pickup_time = pickup_item.text() if pickup_item else ""
            
            depart_item = self.day_table.item(row, 4)
            depart_time = depart_item.text() if depart_item else ""
            
            vehicle_item = self.day_table.item(row, 5)
            vehicle = vehicle_item.text() if vehicle_item else ""
            
            driver_item = self.day_table.item(row, 6)
            driver = driver_item.text() if driver_item else ""
            
            status_item = self.day_table.item(row, 7)
            status = status_item.text() if status_item else ""
            
            outlook_item = self.day_table.item(row, 8)
            outlook_status = outlook_item.text() if outlook_item else ""
            
            alerts_item = self.day_table.item(row, 9)
            alerts = alerts_item.text() if alerts_item else ""
            
            # Get full event details from database
            date_str = self.calendar.selectedDate().toString("yyyy-MM-dd")
            event_details = self._get_event_details(date_str, pickup_time, reserve_number)
            
            # Show calendar event dialog
            self._show_calendar_event_dialog(
                reserve_number, charter_id, event_type, pickup_time, 
                depart_time, vehicle, driver, status, outlook_status, 
                alerts, event_details
            )
                
        except Exception as e:
            QMessageBox.warning(self, "Open Event", f"Failed to open calendar event: {e}")
    
    def _get_event_details(self, date_str, pickup_time, reserve_number):
        """Fetch full event details from database"""
        try:
            self.db.rollback()
        except:
            pass
        
        try:
            cur = self.db.get_cursor()
            
            # Try to find event by reserve number first, then by date+time
            if reserve_number:
                cur.execute("""
                    SELECT calendar_notes, calendar_color, calendar_sync_status,
                           customer_name, booking_type, quote_expires_at
                    FROM charters
                    WHERE reserve_number = %s
                    LIMIT 1
                """, (reserve_number,))
            else:
                cur.execute("""
                    SELECT calendar_notes, calendar_color, calendar_sync_status,
                           customer_name, booking_type, quote_expires_at
                    FROM charters
                    WHERE charter_date = %s AND pickup_time = %s
                    LIMIT 1
                """, (date_str, pickup_time if pickup_time else None))
            
            row = cur.fetchone()
            if row:
                return {
                    'calendar_notes': row[0] or '',
                    'calendar_color': row[1] or '',
                    'calendar_sync_status': row[2] or '',
                    'customer_name': row[3] or '',
                    'booking_type': row[4] or '',
                    'quote_expires_at': str(row[5]) if row[5] else ''
                }
            return {}
        except Exception as e:
            print(f"Error fetching event details: {e}")
            return {}
    
    def _show_calendar_event_dialog(self, reserve_number, charter_id, event_type, 
                                     pickup_time, depart_time, vehicle, driver, 
                                     status, outlook_status, alerts, event_details):
        """Show dialog with calendar event details and action buttons"""
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QGridLayout, QCheckBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Calendar Event Details")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(500)
        
        layout = QVBoxLayout()
        
        # Event Information Section
        info_group = QGroupBox("Event Information")
        info_layout = QFormLayout()
        
        info_layout.addRow("Date:", QLabel(self.calendar.selectedDate().toString("dddd, MMMM d, yyyy")))
        info_layout.addRow("Type:", QLabel(event_type or "Calendar Event"))
        info_layout.addRow("Reserve #:", QLabel(reserve_number or "None (Not Booked)"))
        info_layout.addRow("Charter ID:", QLabel(charter_id or "N/A"))
        info_layout.addRow("Status:", QLabel(status or "Not Scheduled"))
        info_layout.addRow("Pickup Time:", QLabel(pickup_time or "Not Set"))
        info_layout.addRow("Depart Yard:", QLabel(depart_time or "Not Set"))
        info_layout.addRow("Vehicle:", QLabel(vehicle or "Unassigned"))
        info_layout.addRow("Driver:", QLabel(driver or "Unassigned"))
        info_layout.addRow("Outlook Sync:", QLabel(outlook_status or "Not Synced"))
        
        if alerts:
            alerts_label = QLabel(alerts)
            alerts_label.setStyleSheet("color: red; font-weight: bold;")
            info_layout.addRow("⚠️ Alerts:", alerts_label)
        
        if event_details.get('customer_name'):
            info_layout.addRow("Customer:", QLabel(event_details['customer_name']))
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Calendar Notes Section
        notes_group = QGroupBox("Calendar Notes / Email Data")
        notes_layout = QVBoxLayout()
        
        notes_edit = QTextEdit()
        notes_edit.setPlainText(event_details.get('calendar_notes', ''))
        notes_edit.setPlaceholderText("Calendar notes, pasted email content, special instructions...")
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
        save_btn.clicked.connect(lambda: self._save_calendar_details(
            reserve_number, charter_id, notes_edit.toPlainText(), 
            alert_prepayment.isChecked(), dialog
        ))
        actions_layout.addWidget(save_btn)
        
        # Open Charter button (if charter exists)
        if reserve_number:
            open_charter_btn = QPushButton("📋 Open Charter")
            open_charter_btn.clicked.connect(lambda: self._open_existing_charter_dialog(
                reserve_number, charter_id, dialog
            ))
            actions_layout.addWidget(open_charter_btn)
        
        # Open Employee Calendar (if driver assigned)
        if driver and driver != "Unassigned":
            open_driver_btn = QPushButton("👤 Open Employee Calendar")
            open_driver_btn.clicked.connect(lambda: self._open_employee_calendar(driver, dialog))
            actions_layout.addWidget(open_driver_btn)
        
        # Add to New Booking button
        add_booking_btn = QPushButton("➕ Add to New Booking")
        add_booking_btn.clicked.connect(lambda: self._create_charter_from_calendar_dialog(
            pickup_time, notes_edit.toPlainText(), event_details, dialog
        ))
        actions_layout.addWidget(add_booking_btn)
        
        layout.addLayout(actions_layout)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.setLayout(layout)
        dialog.exec()
    
    def _save_calendar_details(self, reserve_number, charter_id, notes, prepayment_alert, dialog):
        """Save calendar notes and alert settings"""
        try:
            self.db.rollback()
        except:
            pass
        
        try:
            cur = self.db.get_cursor()
            
            if reserve_number:
                cur.execute("""
                    UPDATE charters
                    SET calendar_notes = %s,
                        updated_at = NOW()
                    WHERE reserve_number = %s
                """, (notes, reserve_number))
            else:
                # Update by date and time if no reserve number
                date_str = self.calendar.selectedDate().toString("yyyy-MM-dd")
                cur.execute("""
                    UPDATE charters
                    SET calendar_notes = %s,
                        updated_at = NOW()
                    WHERE charter_date = %s
                    LIMIT 1
                """, (notes, date_str))
            
            self.db.commit()
            QMessageBox.information(dialog, "Saved", "Calendar details saved successfully.")
            self._load_day(self.calendar.selectedDate())
            
        except Exception as e:
            QMessageBox.warning(dialog, "Save Failed", f"Failed to save calendar details: {e}")
    
    def _open_existing_charter_dialog(self, reserve_number, charter_id, parent_dialog):
        """Open existing charter for editing"""
        try:
            from main import CharterFormWidget
            charter_form = CharterFormWidget(self.db)
            
            # TODO: Load charter data by reserve number
            # charter_form.load_charter(reserve_number)
            
            charter_form.show()
            parent_dialog.accept()
            
        except Exception as e:
            QMessageBox.warning(parent_dialog, "Open Charter", f"Failed to open charter: {e}")
    
    def _open_employee_calendar(self, driver_name, parent_dialog):
        """Open employee calendar/availability view"""
        QMessageBox.information(parent_dialog, "Employee Calendar", 
            f"Opening calendar for {driver_name}\n(Employee calendar view coming soon)")
        # TODO: Implement employee calendar widget
    
    def _create_charter_from_calendar_dialog(self, pickup_time, notes, event_details, parent_dialog):
        """Create new charter from calendar event"""
        try:
            from main import CharterFormWidget
            charter_form = CharterFormWidget(self.db)
            
            # Auto-populate available information
            charter_form.service_date.setDate(self.calendar.selectedDate())
            if pickup_time:
                charter_form.pickup_time_input.setText(pickup_time)
            
            # Copy calendar notes to dispatch notes (confidential)
            if notes:
                notes_text = f"[From Calendar Event - {self.calendar.selectedDate().toString('yyyy-MM-dd')}]\n{notes}"
                if hasattr(charter_form, 'dispatch_notes_input'):
                    charter_form.dispatch_notes_input.setPlainText(notes_text)
            
            # Set customer name if available
            customer_name = event_details.get('customer_name', '')
            if customer_name and hasattr(charter_form, 'customer_widget'):
                charter_form.customer_widget.search_input.setText(customer_name)
            
            charter_form.show()
            parent_dialog.accept()
            
            QMessageBox.information(parent_dialog, "Create Booking", 
                "New charter form opened with calendar data pre-populated.")
                
        except Exception as e:
            QMessageBox.warning(parent_dialog, "Create Charter", f"Failed to create charter: {e}")
    
    def _create_charter_from_calendar(self, row):
        """Create new charter from calendar event data"""
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            
            # Get calendar event data
            date_str = self.calendar.selectedDate().toString("yyyy-MM-dd")
            pickup_item = self.day_table.item(row, 3)
            pickup_time = pickup_item.text() if pickup_item else ""
            
            # Get calendar notes if they exist
            cur.execute("""
                SELECT calendar_notes, calendar_color, customer_name, booking_type
                FROM charters
                WHERE charter_date = %s AND pickup_time = %s
                LIMIT 1
            """, (date_str, pickup_time if pickup_time else None))
            
            event_data = cur.fetchone()
            calendar_notes = event_data[0] if event_data and event_data[0] else ""
            calendar_color = event_data[1] if event_data and event_data[1] else ""
            customer_name = event_data[2] if event_data and event_data[2] else ""
            booking_type = event_data[3] if event_data and event_data[3] else ""
            
            # Import and create charter form
            from main import CharterFormWidget
            charter_form = CharterFormWidget(self.db)
            
            # Auto-populate available information
            charter_form.service_date.setDate(self.calendar.selectedDate())
            if pickup_time:
                charter_form.pickup_time_input.setText(pickup_time)
            
            # Copy calendar notes to dispatch notes (confidential)
            if calendar_notes:
                notes_text = f"[From Calendar Event]\n{calendar_notes}"
                if hasattr(charter_form, 'dispatch_notes_input'):
                    charter_form.dispatch_notes_input.setPlainText(notes_text)
            
            # Set customer name if available
            if customer_name and hasattr(charter_form, 'customer_widget'):
                # Try to find and select customer
                charter_form.customer_widget.search_input.setText(customer_name)
            
            # Show form
            charter_form.show()
            
            QMessageBox.information(self, "Create Booking", 
                f"New charter form opened.\nCalendar data has been pre-populated.\n"
                f"Complete the booking and save to link it to this calendar event.")
                
        except Exception as e:
            QMessageBox.warning(self, "Create Charter", f"Failed to create charter from calendar: {e}")
    
    def _open_existing_charter(self, reserve_number, charter_id):
        """Open existing charter for editing with change tracking"""
        try:
            # Import and create charter form
            from main import CharterFormWidget
            charter_form = CharterFormWidget(self.db)
            
            # Load charter data by reserve number
            # (This would need a load_charter method in CharterFormWidget)
            
            # Track original values for change detection
            charter_form._original_calendar_data = {
                'reserve_number': reserve_number,
                'charter_id': charter_id
            }
            
            # Override save method to ask for calendar update confirmation
            original_save = charter_form.save_charter
            def save_with_calendar_check():
                # Check if key fields changed
                if self._charter_fields_changed(charter_form):
                    reply = QMessageBox.question(charter_form, "Calendar Update",
                        "Charter details have changed.\nUpdate the calendar event to match?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.Yes)
                    
                    if reply == QMessageBox.StandardButton.Yes:
                        self._update_calendar_from_charter(charter_form)
                
                # Call original save
                original_save()
            
            charter_form.save_charter = save_with_calendar_check
            charter_form.show()
            
        except Exception as e:
            QMessageBox.warning(self, "Open Charter", f"Failed to open charter: {e}")
    
    def _charter_fields_changed(self, charter_form) -> bool:
        """Check if charter fields differ from original calendar data"""
        # Compare key fields: date, time, vehicle, driver
        # This is a simplified check - expand as needed
        return True  # For now, always ask
    
    def _update_calendar_from_charter(self, charter_form):
        """Update calendar event to match charter changes"""
        try:
            # Update calendar_sync_status to indicate manual update needed
            cur = self.db.get_cursor()
            reserve_number = charter_form._original_calendar_data.get('reserve_number')
            
            cur.execute("""
                UPDATE charters
                SET calendar_sync_status = 'needs_update',
                    updated_at = NOW()
                WHERE reserve_number = %s
            """, (reserve_number,))
            
            self.db.commit()
            QMessageBox.information(charter_form, "Calendar Updated",
                "Calendar event marked for sync update.")
                
        except Exception as e:
            QMessageBox.warning(charter_form, "Calendar Update", 
                f"Failed to update calendar status: {e}")
