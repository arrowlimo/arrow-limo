"""
Driver Calendar Widget
Monthly calendar with drill-down: charters per day, vehicle/driver assignment, yard depart time, pickup time,
customer info, customer notes, dispatch-only notes. Includes buttons to print charter documentation and open a
simple driver entry form (times, odometer, fuel receipts, floats, HOS).

Note: This implementation reads common columns if present and safely skips missing ones using information_schema.
It does not alter database schema. Driver entry form currently saves to JSON under reports/driver_logs_submissions/.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCalendarWidget, QTableWidget,
    QTableWidgetItem, QPushButton, QSplitter, QGroupBox, QFormLayout, QLineEdit,
    QTextEdit, QTimeEdit, QSpinBox, QDialog, QDialogButtonBox, QMessageBox, QCheckBox
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont
from datetime import datetime
import os
import json

class DriverCalendarWidget(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self._init_ui()
        self._ensure_submission_dir()
        self.load_day_events(QDate.currentDate())

    def _ensure_submission_dir(self):
        try:
            base = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'reports', 'driver_logs_submissions')
            os.makedirs(base, exist_ok=True)
            self.submission_dir = base
        except Exception:
            self.submission_dir = os.path.join(os.getcwd(), 'driver_logs_submissions')
            os.makedirs(self.submission_dir, exist_ok=True)

    def _init_ui(self):
        layout = QVBoxLayout()
        
        # Header with title and filters
        header_layout = QHBoxLayout()
        title = QLabel("🗓️ Driver Calendar")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        # Filter checkboxes
        filter_label = QLabel("Show:")
        filter_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header_layout.addWidget(filter_label)
        
        from PyQt6.QtWidgets import QCheckBox
        self.filter_my_charters = QCheckBox("My Charters Only")
        self.filter_my_charters.setChecked(False)
        self.filter_my_charters.toggled.connect(lambda: self.load_day_events(self.calendar.selectedDate()))
        header_layout.addWidget(self.filter_my_charters)
        
        self.filter_unassigned = QCheckBox("Unassigned")
        self.filter_unassigned.setChecked(True)
        self.filter_unassigned.toggled.connect(lambda: self.load_day_events(self.calendar.selectedDate()))
        header_layout.addWidget(self.filter_unassigned)
        
        self.filter_all = QCheckBox("All Drivers")
        self.filter_all.setChecked(True)
        self.filter_all.toggled.connect(lambda: self.load_day_events(self.calendar.selectedDate()))
        header_layout.addWidget(self.filter_all)
        
        layout.addLayout(header_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: month calendar
        left = QWidget()
        left_layout = QVBoxLayout()
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.selectionChanged.connect(self._on_date_changed)
        left_layout.addWidget(self.calendar)
        left.setLayout(left_layout)
        splitter.addWidget(left)

        # Right: day details
        right = QWidget()
        right_layout = QVBoxLayout()

        # Day summary table
        self.day_table = QTableWidget()
        self.day_table.setColumnCount(8)
        self.day_table.setHorizontalHeaderLabels([
            "Reserve #", "Charter ID", "Pickup", "Depart Yard", "Vehicle", "Driver",
            "Customer", "Status"
        ])
        self.day_table.itemSelectionChanged.connect(self._load_selected_charter)
        right_layout.addWidget(self.day_table)

        # Charter details + actions
        box = QGroupBox("Charter Details")
        form = QFormLayout()
        self.detail_reserve = QLineEdit(); self.detail_reserve.setReadOnly(True)
        self.detail_charter_id = QLineEdit(); self.detail_charter_id.setReadOnly(True)
        self.detail_pickup_time = QLineEdit(); self.detail_pickup_time.setReadOnly(True)
        self.detail_depart_yard = QLineEdit(); self.detail_depart_yard.setReadOnly(True)
        self.detail_vehicle = QLineEdit(); self.detail_vehicle.setReadOnly(True)
        self.detail_driver = QLineEdit(); self.detail_driver.setReadOnly(True)
        self.detail_customer = QLineEdit(); self.detail_customer.setReadOnly(True)
        self.detail_customer_notes = QTextEdit(); self.detail_customer_notes.setReadOnly(True)
        self.detail_dispatch_notes = QTextEdit(); self.detail_dispatch_notes.setReadOnly(True)
        form.addRow("Reserve #", self.detail_reserve)
        form.addRow("Charter ID", self.detail_charter_id)
        form.addRow("Pickup Time", self.detail_pickup_time)
        form.addRow("Depart Yard", self.detail_depart_yard)
        form.addRow("Vehicle", self.detail_vehicle)
        form.addRow("Driver", self.detail_driver)
        form.addRow("Customer", self.detail_customer)
        form.addRow("Customer Notes", self.detail_customer_notes)
        form.addRow("Dispatch Notes", self.detail_dispatch_notes)

        action_layout = QHBoxLayout()
        self.print_btn = QPushButton("🖨️ Print Charter")
        self.print_btn.clicked.connect(self._print_charter)
        self.driver_form_btn = QPushButton("✍️ Driver Entry Form")
        self.driver_form_btn.clicked.connect(self._open_driver_form)
        action_layout.addWidget(self.print_btn)
        action_layout.addWidget(self.driver_form_btn)
        form.addRow(action_layout)

        box.setLayout(form)
        right_layout.addWidget(box)

        right.setLayout(right_layout)
        splitter.addWidget(right)

        splitter.setSizes([400, 600])
        layout.addWidget(splitter)
        self.setLayout(layout)

    def _on_date_changed(self):
        self.load_day_events(self.calendar.selectedDate())

    def _get_columns(self, table_name):
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
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name=%s
                """,
                (table_name,)
            )
            cols = {r[0] for r in cur.fetchall()}
            return cols
        except Exception:
            return set()

    def load_day_events(self, qdate: QDate):
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
            # Convert QDate to Python date object for proper parameter binding
            date_py = qdate.toPyDate()
            # Build safe select
            ccols = self._get_columns('charters')
            ecols = self._get_columns('employees')
            vcols = self._get_columns('vehicles')
            cols = [
                'charter_id', 'reserve_number', 'pickup_time', 'depart_yard_time', 'status',
                'vehicle_id', 'employee_id', 'customer_name',
            ]
            select_cols = [c for c in cols if c in ccols]
            select_clause = ", ".join(select_cols) if select_cols else "charter_id, reserve_number"
            
            # Build WHERE clause based on filters
            where_conditions = ["charter_date = %s"]
            where_params = [date_py]
            
            # Apply filters
            if hasattr(self, 'filter_my_charters') and self.filter_my_charters.isChecked():
                # Filter to current user's charters only (would need current_user_id)
                # For now, show assigned charters
                where_conditions.append("employee_id IS NOT NULL")
            
            if hasattr(self, 'filter_unassigned') and not self.filter_unassigned.isChecked():
                # Hide unassigned
                where_conditions.append("employee_id IS NOT NULL")
            
            if hasattr(self, 'filter_all') and not self.filter_all.isChecked():
                # If "All Drivers" is unchecked, only show assigned ones
                where_conditions.append("employee_id IS NOT NULL")
            
            # Always exclude cancelled/no-show
            where_conditions.append("(status IS NULL OR status NOT IN ('cancelled','no-show'))")
            
            where_clause = " AND ".join(where_conditions)
            
            cur.execute(
                f"""
                SELECT {select_clause}
                FROM charters
                WHERE {where_clause}
                ORDER BY pickup_time NULLS LAST
                """,
                where_params
            )
            rows = cur.fetchall()
            self.day_table.setRowCount(len(rows))
            # Map
            for r, row in enumerate(rows):
                data = dict(zip(select_cols, row)) if select_cols else {}
                reserve = str(data.get('reserve_number') or '')
                charter_id = str(data.get('charter_id') or '')
                pickup = str(data.get('pickup_time') or '')
                depart = str(data.get('depart_yard_time') or '')
                vehicle = self._lookup_vehicle(vcols, data.get('vehicle_id'))
                driver = self._lookup_driver(ecols, data.get('employee_id'))
                customer = str(data.get('customer_name') or '')
                status = str(data.get('status') or '')
                items = [
                    QTableWidgetItem(reserve),
                    QTableWidgetItem(charter_id),
                    QTableWidgetItem(pickup),
                    QTableWidgetItem(depart),
                    QTableWidgetItem(vehicle),
                    QTableWidgetItem(driver),
                    QTableWidgetItem(customer),
                    QTableWidgetItem(status),
                ]
                for c, it in enumerate(items):
                    self.day_table.setItem(r, c, it)
        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Failed to load day events: {e}")

    def _lookup_vehicle(self, vcols, vehicle_id):
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
            # Always prefer vehicle_number for display
            sel = 'vehicle_number'
            cur.execute(f"SELECT {sel} FROM vehicles WHERE vehicle_id=%s LIMIT 1", (vehicle_id,))
            r = cur.fetchone()
            if not r:
                return ''
            parts = [str(x) for x in r if x]
            return " / ".join(parts)
        except Exception:
            return ''

    def _lookup_driver(self, ecols, employee_id):
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
            cols = ['full_name','phone_number']
            existing = [c for c in cols if c in ecols]
            sel = ", ".join(existing) if existing else 'full_name'
            cur.execute(f"SELECT {sel} FROM employees WHERE employee_id=%s LIMIT 1", (employee_id,))
            r = cur.fetchone()
            if not r:
                return ''
            parts = [str(x) for x in r if x]
            return " / ".join(parts)
        except Exception:
            return ''

    def _load_selected_charter(self):
        items = self.day_table.selectedItems()
        if not items:
            return
        row = self.day_table.row(items[0])
        reserve = self.day_table.item(row, 0).text()
        charter_id = self.day_table.item(row, 1).text()
        self.detail_reserve.setText(reserve)
        self.detail_charter_id.setText(charter_id)
        # Fill the rest from table directly
        self.detail_pickup_time.setText(self.day_table.item(row, 2).text())
        self.detail_depart_yard.setText(self.day_table.item(row, 3).text())
        self.detail_vehicle.setText(self.day_table.item(row, 4).text())
        self.detail_driver.setText(self.day_table.item(row, 5).text())
        self.detail_customer.setText(self.day_table.item(row, 6).text())
        # Load notes if available
        try:
            ccols = self._get_columns('charters')
            if {'customer_notes','dispatch_notes'} & ccols:
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
                fields = [f for f in ['customer_notes','dispatch_notes'] if f in ccols]
                sel = ", ".join(fields)
                cur.execute(f"SELECT {sel} FROM charters WHERE reserve_number=%s LIMIT 1", (reserve,))
                r = cur.fetchone()
                vals = dict(zip(fields, r)) if r else {}
                self.detail_customer_notes.setPlainText(str(vals.get('customer_notes') or ''))
                self.detail_dispatch_notes.setPlainText(str(vals.get('dispatch_notes') or ''))
        except Exception:
            pass
        
        # Load driver logs if available
        self._load_and_display_driver_logs(reserve)

    def _load_and_display_driver_logs(self, reserve_number: str):
        """Load and display driver logs for the selected charter"""
        try:
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT depart_time, pickup_time, start_odometer, end_odometer, 
                       fuel_liters, fuel_amount, float_amount, hos_notes, driver_notes, submitted_at
                FROM charter_driver_logs
                WHERE reserve_number = %s
                ORDER BY submitted_at DESC
                LIMIT 1
            """, (reserve_number,))
            
            row = cur.fetchone()
            if row:
                # Extract values
                depart_time, pickup_time, start_odo, end_odo, fuel_liters, fuel_amt, float_amt, hos_notes, driver_notes, submitted_at = row
                
                # Create a formatted summary
                driver_log_text = f"✅ Driver Log Found (Submitted: {submitted_at})\n"
                driver_log_text += f"\nTimes:\n"
                driver_log_text += f"  Depart Yard: {depart_time or 'N/A'}\n"
                driver_log_text += f"  Pickup Time: {pickup_time or 'N/A'}\n"
                driver_log_text += f"\nOdometer:\n"
                driver_log_text += f"  Start: {start_odo or 'N/A'} km\n"
                driver_log_text += f"  End: {end_odo or 'N/A'} km\n"
                if start_odo and end_odo:
                    distance = end_odo - start_odo
                    driver_log_text += f"  Distance: {distance} km\n"
                driver_log_text += f"\nFuel & Float:\n"
                driver_log_text += f"  Fuel: {fuel_liters or 'N/A'} L @ ${fuel_amt or 0:.2f}\n"
                driver_log_text += f"  Float Used: ${float_amt or 0:.2f}\n"
                if hos_notes:
                    driver_log_text += f"\nHOS Notes:\n{hos_notes}\n"
                if driver_notes:
                    driver_log_text += f"\nDriver Notes:\n{driver_notes}\n"
                
                # Update dispatch notes to show driver log info
                self.detail_dispatch_notes.setPlainText(driver_log_text)
            else:
                # No driver logs yet
                self.detail_dispatch_notes.setPlainText("⏳ No driver log submitted yet")
        
        except Exception as e:
            # Silently fail if driver logs table doesn't exist
            try:
                self.detail_dispatch_notes.setPlainText(f"⚠️ Could not load driver logs: {str(e)}")
            except:
                pass

    def _print_charter(self):
        reserve = self.detail_reserve.text().strip()
        if not reserve:
            QMessageBox.information(self, "Print", "Select a charter first")
            return
        # Placeholder: emit JSON for now; integrate PDF generator later
        out = {
            'reserve_number': reserve,
            'charter_id': self.detail_charter_id.text(),
            'vehicle': self.detail_vehicle.text(),
            'driver': self.detail_driver.text(),
            'pickup_time': self.detail_pickup_time.text(),
            'depart_yard': self.detail_depart_yard.text(),
            'customer': self.detail_customer.text(),
            'notes': {
                'customer': self.detail_customer_notes.toPlainText(),
                'dispatch': self.detail_dispatch_notes.toPlainText(),
            }
        }
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        path = os.path.join(self.submission_dir, f"charter_print_{reserve}_{ts}.json")
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(out, f, indent=2)
            QMessageBox.information(self, "Print", f"Saved charter doc to {path}")
        except Exception as e:
            QMessageBox.warning(self, "Print", f"Failed to save: {e}")

    def _open_driver_form(self):
        reserve = self.detail_reserve.text().strip()
        if not reserve:
            QMessageBox.information(self, "Driver Form", "Select a charter first")
            return
        dlg = DriverEntryDialog(reserve, self.submission_dir, self.db, self)
        dlg.exec()


class DriverEntryDialog(QDialog):
    def __init__(self, reserve_number: str, submission_dir: str, db=None, parent=None):
        super().__init__(parent)
        self.reserve_number = reserve_number
        self.submission_dir = submission_dir
        self.db = db
        self.setWindowTitle(f"Driver Entry - {reserve_number}")
        self._init_ui()

    def _init_ui(self):
        layout = QFormLayout(self)
        self.depart_time = QTimeEdit(); self.depart_time.setDisplayFormat('HH:mm')
        self.pickup_time = QTimeEdit(); self.pickup_time.setDisplayFormat('HH:mm')
        self.start_odometer = QSpinBox(); self.start_odometer.setMaximum(9999999)
        self.end_odometer = QSpinBox(); self.end_odometer.setMaximum(9999999)
        self.fuel_liters = QSpinBox(); self.fuel_liters.setMaximum(2000)
        self.fuel_amount = QSpinBox(); self.fuel_amount.setMaximum(100000)
        self.float_amount = QSpinBox(); self.float_amount.setMaximum(100000)
        self.hos_notes = QTextEdit()
        self.driver_notes = QTextEdit()
        
        # Add HOS warning label
        from PyQt6.QtWidgets import QLabel
        self.hos_warning = QLabel("⏰ HOS Regulations: Max 14 hrs driving, 11 hrs on duty per day")
        self.hos_warning.setStyleSheet("color: #FF8C00; font-weight: bold;")
        
        layout.addRow("Depart Yard", self.depart_time)
        layout.addRow("Pickup Time", self.pickup_time)
        layout.addRow("", self.hos_warning)
        layout.addRow("Start Odometer", self.start_odometer)
        layout.addRow("End Odometer", self.end_odometer)
        layout.addRow("Fuel Liters", self.fuel_liters)
        layout.addRow("Fuel Amount", self.fuel_amount)
        layout.addRow("Float Used", self.float_amount)
        layout.addRow("HOS Notes", self.hos_notes)
        layout.addRow("Driver Notes", self.driver_notes)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _save(self):
        # Calculate HOS (Hours of Service) and warn if violations
        depart_time = self.depart_time.time()
        pickup_time = self.pickup_time.time()
        
        hos_warnings = self._validate_hos(depart_time, pickup_time)
        
        if hos_warnings:
            reply = QMessageBox.warning(
                self,
                "HOS Violation Warning",
                f"Hours of Service violations detected:\n\n{hos_warnings}\n\nContinue saving?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        payload = {
            'reserve_number': self.reserve_number,
            'depart_yard': self.depart_time.text(),
            'pickup_time': self.pickup_time.text(),
            'start_odometer': self.start_odometer.value(),
            'end_odometer': self.end_odometer.value(),
            'fuel_liters': self.fuel_liters.value(),
            'fuel_amount': self.fuel_amount.value(),
            'float_amount': self.float_amount.value(),
            'hos_notes': self.hos_notes.toPlainText(),
            'driver_notes': self.driver_notes.toPlainText(),
            'submitted_at': datetime.now().isoformat(),
            'hos_warnings': hos_warnings,  # Include warnings in payload
        }
        
        # Save to database if connection available
        db_saved = False
        if self.db:
            try:
                cur = self.db.get_cursor()
                cur.execute(
                    """
                    INSERT INTO charter_driver_logs (
                        reserve_number, depart_time, pickup_time, 
                        start_odometer, end_odometer, fuel_liters, fuel_amount, 
                        float_amount, hos_notes, driver_notes, json_backup
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (reserve_number, submitted_at) DO UPDATE SET
                        depart_time = EXCLUDED.depart_time,
                        pickup_time = EXCLUDED.pickup_time,
                        start_odometer = EXCLUDED.start_odometer,
                        end_odometer = EXCLUDED.end_odometer,
                        fuel_liters = EXCLUDED.fuel_liters,
                        fuel_amount = EXCLUDED.fuel_amount,
                        float_amount = EXCLUDED.float_amount,
                        hos_notes = EXCLUDED.hos_notes,
                        driver_notes = EXCLUDED.driver_notes,
                        json_backup = EXCLUDED.json_backup,
                        updated_at = NOW()
                    """,
                    (
                        self.reserve_number,
                        self.depart_time.time().isoformat() if self.depart_time.time().hour() > 0 or self.depart_time.time().minute() > 0 else None,
                        self.pickup_time.time().isoformat() if self.pickup_time.time().hour() > 0 or self.pickup_time.time().minute() > 0 else None,
                        self.start_odometer.value() if self.start_odometer.value() > 0 else None,
                        self.end_odometer.value() if self.end_odometer.value() > 0 else None,
                        self.fuel_liters.value() if self.fuel_liters.value() > 0 else None,
                        float(self.fuel_amount.value()) if self.fuel_amount.value() > 0 else None,
                        float(self.float_amount.value()) if self.float_amount.value() > 0 else None,
                        self.hos_notes.toPlainText() or None,
                        self.driver_notes.toPlainText() or None,
                        json.dumps(payload),
                    ),
                )
                self.db.commit()
                db_saved = True
            except Exception as e:
                try:
                    self.db.rollback()
                except:
                    pass
                QMessageBox.warning(self, "Database Error", f"Failed to save to database:\n\n{str(e)}\n\nWill save to JSON only.")
        
        # Always save to JSON as backup
        path = os.path.join(self.submission_dir, f"driver_log_{self.reserve_number}_{ts}.json")
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2)
            
            if db_saved:
                QMessageBox.information(self, "Saved", f"✅ Driver entry saved to database and JSON backup")
            else:
                QMessageBox.information(self, "Saved", f"Driver entry saved to {path}")
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save JSON backup: {e}")
    def _validate_hos(self, depart_time, pickup_time):
        """
        Validate Hours of Service (HOS) regulations.
        Returns warning string if violations detected, empty string if OK.
        
        HOS Regulations (Canadian/Alberta):
        - Max 14 hours on duty per day (includes driving + other work)
        - Max 11 hours continuous driving per day
        - Minimum 8 hours off-duty between shifts
        """
        warnings = []
        
        # Calculate hours between depart and pickup
        if depart_time.hour() > 0 or depart_time.minute() > 0:
            if pickup_time.hour() > 0 or pickup_time.minute() > 0:
                # Calculate time difference
                depart_minutes = depart_time.hour() * 60 + depart_time.minute()
                pickup_minutes = pickup_time.hour() * 60 + pickup_time.minute()
                
                # Handle day boundary (e.g., 22:00 to 06:00 next day)
                if pickup_minutes < depart_minutes:
                    pickup_minutes += 24 * 60
                
                hours_worked = (pickup_minutes - depart_minutes) / 60.0
                
                if hours_worked > 14:
                    warnings.append(f"⚠️ On-duty time: {hours_worked:.1f} hours (max 14 allowed)")
                
                if hours_worked > 11:
                    warnings.append(f"⚠️ Driving time: {hours_worked:.1f} hours (max 11 continuous allowed)")
        
        return "\n".join(warnings) if warnings else ""