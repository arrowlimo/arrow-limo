"""
Red Deer Bylaw Compliance & Vehicle Incident Tracking
- Red Deer bylaw validation (no bylaw if Leave RD → Return to RD)
- Driver badge checking
- Vehicle breakdown incident tracking with costs
- Discomfort rebate management
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QDoubleSpinBox, QDateTimeEdit, QComboBox,
    QMessageBox, QCheckBox, QTextEdit, QGroupBox, QFormLayout, QSpinBox
)
from PyQt6.QtCore import Qt, QDateTime
from PyQt6.QtGui import QFont, QColor
from datetime import datetime, timedelta


class RedDeerBylawValidator:
    """
    Red Deer bylaw compliance checking
    Rules:
    - If route: Leave Red Deer → Return to Red Deer = NO bylaw applies
    - Otherwise: Verify driver badge valid and check badge rate
    - Badge rate: per hour (no split) or per hour split run
    - Split run: time stops at drop-off, time starts at next pickup
    """
    
    def __init__(self):
        self.requires_badge = True
        self.bylaw_applies = False
    
    def check_compliance(self, pickup_location, dropoff_location, route_legs=None):
        """
        Check if Red Deer bylaw applies
        
        Args:
            pickup_location: str - Pickup location (e.g., "Red Deer")
            dropoff_location: str - Dropoff location (e.g., "Red Deer" or "Calgary")
            route_legs: list - List of route stops (optional)
        
        Returns:
            dict - Compliance status
        """
        # Normalize location names
        pickup = pickup_location.lower().strip()
        dropoff = dropoff_location.lower().strip()
        
        # Check if both pickup and dropoff are Red Deer
        rd_in_pickup = "red deer" in pickup
        rd_in_dropoff = "red deer" in dropoff
        
        # Rule: If leave RD and return to RD, NO bylaw
        if rd_in_pickup and rd_in_dropoff:
            self.bylaw_applies = False
            return {
                "bylaw_applies": False,
                "requires_badge": False,
                "reason": "Leave Red Deer → Return to Red Deer: Bylaw does NOT apply",
                "compliance_status": "✅ Compliant",
                "message": "No badging required for this route"
            }
        
        # If any leg leaves or enters Red Deer, bylaw applies
        if rd_in_pickup or rd_in_dropoff:
            self.bylaw_applies = True
            return {
                "bylaw_applies": True,
                "requires_badge": True,
                "reason": f"Route involves Red Deer: Verify driver badge valid",
                "compliance_status": "⚠️ Check Required",
                "message": "Driver must have valid Red Deer business license badge"
            }
        
        # Route doesn't involve Red Deer
        self.bylaw_applies = False
        return {
            "bylaw_applies": False,
            "requires_badge": False,
            "reason": "Route outside Red Deer: Bylaw does NOT apply",
            "compliance_status": "✅ Compliant",
            "message": "No Red Deer badging required"
        }
    
    def validate_badge(self, driver_badge_number, badge_expiry_date):
        """Validate driver badge"""
        if not driver_badge_number:
            return {
                "valid": False,
                "message": "❌ No badge number on file"
            }
        
        today = datetime.now().date()
        expiry = badge_expiry_date if isinstance(badge_expiry_date, type(today)) else datetime.fromisoformat(str(badge_expiry_date)).date()
        
        if expiry < today:
            days_expired = (today - expiry).days
            return {
                "valid": False,
                "message": f"❌ Badge expired {days_expired} days ago"
            }
        
        days_until_expiry = (expiry - today).days
        if days_until_expiry < 30:
            return {
                "valid": True,
                "message": f"⚠️ Badge valid but expires in {days_until_expiry} days",
                "warning": True
            }
        
        return {
            "valid": True,
            "message": f"✅ Badge valid until {expiry.strftime('%m/%d/%Y')}"
        }


class VehicleIncidentDialog(QDialog):
    """
    Track vehicle breakdown incidents with associated costs
    - Time reported vs. replacement vehicle arrival
    - Costs paid (taxi, bar tab, etc.)
    - Discomfort rebate/compensation
    - Repair and towing costs
    """
    
    incident_saved = pyqtSignal(dict)
    
    def __init__(self, db, charter_id, parent=None):
        super().__init__(parent)
        self.db = db
        self.charter_id = charter_id
        
        self.setWindowTitle("Vehicle Breakdown Incident Report")
        self.setGeometry(100, 100, 1000, 800)
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("🚗 Vehicle Breakdown Incident Report")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Incident details
        details_group = QGroupBox("Incident Details")
        details_form = QFormLayout()
        
        self.incident_date = QDateTimeEdit()
        self.incident_date.setDateTime(QDateTime.currentDateTime())
        details_form.addRow("Date/Time Reported:", self.incident_date)
        
        self.vehicle_current = QLineEdit()
        details_form.addRow("Vehicle (Current):", self.vehicle_current)
        
        self.breakdown_location = QLineEdit()
        details_form.addRow("Breakdown Location:", self.breakdown_location)
        
        self.replacement_arrival = QDateTimeEdit()
        details_form.addRow("Replacement Vehicle Arrived:", self.replacement_arrival)
        
        self.replacement_vehicle = QLineEdit()
        details_form.addRow("Vehicle (Replacement):", self.replacement_vehicle)
        
        self.downtime_minutes = QSpinBox()
        self.downtime_minutes.setMinimum(0)
        self.downtime_minutes.setMaximum(480)  # 8 hours max
        self.downtime_minutes.setSuffix(" minutes")
        details_form.addRow("Downtime Duration:", self.downtime_minutes)
        
        details_group.setLayout(details_form)
        layout.addWidget(details_group)
        
        # Costs incurred
        costs_group = QGroupBox("Costs Incurred (To be rebated to guest)")
        costs_form = QFormLayout()
        
        self.taxi_cost = QDoubleSpinBox()
        self.taxi_cost.setMaximum(10000)
        self.taxi_cost.setPrefix("$")
        costs_form.addRow("Taxi/Transportation:", self.taxi_cost)
        
        self.bar_tab = QDoubleSpinBox()
        self.bar_tab.setMaximum(10000)
        self.bar_tab.setPrefix("$")
        costs_form.addRow("Bar Tab/Refreshments:", self.bar_tab)
        
        self.hotel_cost = QDoubleSpinBox()
        self.hotel_cost.setMaximum(10000)
        self.hotel_cost.setPrefix("$")
        costs_form.addRow("Hotel/Lodging:", self.hotel_cost)
        
        self.other_cost = QDoubleSpinBox()
        self.other_cost.setMaximum(10000)
        self.other_cost.setPrefix("$")
        costs_form.addRow("Other Costs:", self.other_cost)
        
        self.total_costs = QDoubleSpinBox()
        self.total_costs.setReadOnly(True)
        self.total_costs.setPrefix("$")
        self.total_costs.setStyleSheet("font-weight: bold;")
        costs_form.addRow("TOTAL COSTS INCURRED:", self.total_costs)
        
        costs_group.setLayout(costs_form)
        layout.addWidget(costs_group)
        
        # Discomfort/inconvenience rebate
        rebate_group = QGroupBox("Discomfort Rebate (Guest Compensation)")
        rebate_form = QFormLayout()
        
        self.rebate_amount = QDoubleSpinBox()
        self.rebate_amount.setMaximum(10000)
        self.rebate_amount.setPrefix("$")
        rebate_form.addRow("Compensation/Rebate Amount:", self.rebate_amount)
        
        self.rebate_reason = QComboBox()
        self.rebate_reason.addItems([
            "Breakdown (1-3 hrs)",
            "Breakdown (3+ hrs)",
            "Service cancelled",
            "Partial service provided",
            "Other (specify below)"
        ])
        rebate_form.addRow("Reason for Rebate:", self.rebate_reason)
        
        self.rebate_notes = QTextEdit()
        self.rebate_notes.setPlaceholderText("Details about the incident and rebate decision...")
        self.rebate_notes.setMaximumHeight(100)
        rebate_form.addRow("Notes:", self.rebate_notes)
        
        rebate_group.setLayout(rebate_form)
        layout.addWidget(rebate_group)
        
        # Repair/towing costs
        repair_group = QGroupBox("Vehicle Repair & Towing Costs")
        repair_form = QFormLayout()
        
        self.towing_cost = QDoubleSpinBox()
        self.towing_cost.setMaximum(10000)
        self.towing_cost.setPrefix("$")
        repair_form.addRow("Towing Charge:", self.towing_cost)
        
        self.repair_estimate = QDoubleSpinBox()
        self.repair_estimate.setMaximum(50000)
        self.repair_estimate.setPrefix("$")
        repair_form.addRow("Repair Estimate:", self.repair_estimate)
        
        self.insurance_claim = QCheckBox("File Insurance Claim")
        repair_form.addRow("", self.insurance_claim)
        
        repair_group.setLayout(repair_form)
        layout.addWidget(repair_group)
        
        # Financial summary
        summary_group = QGroupBox("Financial Summary")
        summary_form = QFormLayout()
        
        self.guest_rebate_display = QLabel("$0.00")
        self.guest_rebate_display.setStyleSheet("color: red; font-weight: bold;")
        summary_form.addRow("Guest Rebate:", self.guest_rebate_display)
        
        self.repair_cost_display = QLabel("$0.00")
        summary_form.addRow("Repair/Towing Cost:", self.repair_cost_display)
        
        self.total_impact = QLabel("$0.00")
        self.total_impact.setStyleSheet("color: red; font-weight: bold; font-size: 12pt;")
        summary_form.addRow("TOTAL FINANCIAL IMPACT:", self.total_impact)
        
        summary_group.setLayout(summary_form)
        layout.addWidget(summary_group)
        
        # Connect cost changes to recalculation
        self.taxi_cost.valueChanged.connect(self.update_costs)
        self.bar_tab.valueChanged.connect(self.update_costs)
        self.hotel_cost.valueChanged.connect(self.update_costs)
        self.other_cost.valueChanged.connect(self.update_costs)
        self.rebate_amount.valueChanged.connect(self.update_costs)
        self.towing_cost.valueChanged.connect(self.update_costs)
        self.repair_estimate.valueChanged.connect(self.update_costs)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        button_layout.addStretch()
        
        save_btn = QPushButton("💾 Save Incident Report")
        save_btn.clicked.connect(self.save_incident)
        button_layout.addWidget(save_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def update_costs(self):
        """Recalculate cost totals"""
        total_costs = (
            self.taxi_cost.value() +
            self.bar_tab.value() +
            self.hotel_cost.value() +
            self.other_cost.value()
        )
        
        self.total_costs.setValue(total_costs)
        self.guest_rebate_display.setText(f"${self.rebate_amount.value():.2f}")
        
        repair_total = self.towing_cost.value() + self.repair_estimate.value()
        self.repair_cost_display.setText(f"${repair_total:.2f}")
        
        total_impact = total_costs + self.rebate_amount.value() + repair_total
        self.total_impact.setText(f"${total_impact:.2f}")
    
    def save_incident(self):
        """Save incident report to database"""
        incident_data = {
            "charter_id": self.charter_id,
            "date_reported": self.incident_date.dateTime().toPython(),
            "current_vehicle": self.vehicle_current.text(),
            "location": self.breakdown_location.text(),
            "replacement_arrival": self.replacement_arrival.dateTime().toPython(),
            "replacement_vehicle": self.replacement_vehicle.text(),
            "downtime_minutes": self.downtime_minutes.value(),
            "guest_costs": {
                "taxi": self.taxi_cost.value(),
                "bar_tab": self.bar_tab.value(),
                "hotel": self.hotel_cost.value(),
                "other": self.other_cost.value(),
                "total": self.total_costs.value()
            },
            "rebate": {
                "amount": self.rebate_amount.value(),
                "reason": self.rebate_reason.currentText(),
                "notes": self.rebate_notes.toPlainText()
            },
            "repair": {
                "towing": self.towing_cost.value(),
                "estimate": self.repair_estimate.value(),
                "insurance_claim": self.insurance_claim.isChecked()
            }
        }
        
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
                INSERT INTO vehicle_incidents 
                (charter_id, date_reported, current_vehicle, location, 
                 replacement_arrival, replacement_vehicle, downtime_minutes,
                 guest_costs_json, rebate_json, repair_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                incident_data["charter_id"],
                incident_data["date_reported"],
                incident_data["current_vehicle"],
                incident_data["location"],
                incident_data["replacement_arrival"],
                incident_data["replacement_vehicle"],
                incident_data["downtime_minutes"],
                json.dumps(incident_data["guest_costs"]),
                json.dumps(incident_data["rebate"]),
                json.dumps(incident_data["repair"])
            ))
            self.db.get_connection().commit()
            cur.close()
            
            QMessageBox.information(
                self, "Success",
                f"Incident report saved\n"
                f"Total Impact: ${self.total_impact.text()}"
            )
            
            self.incident_saved.emit(incident_data)
            
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")


# Import json at the top if needed
import json
