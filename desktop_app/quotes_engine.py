"""
Advanced Charter Quoting Engine
Multi-step quote comparisons: hourly vs. packages vs. split runs
With GST, gratuity, agreement terms, and detailed cost breakdowns
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QDoubleSpinBox, QSpinBox, QTableWidget, QTableWidgetItem, QComboBox,
    QTimeEdit, QTextEdit, QCheckBox, QMessageBox, QGroupBox,
    QFormLayout, QTabWidget, QScrollArea, QWidget, QFileDialog
)
from PyQt6.QtCore import Qt, QDate, QTime, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush
from datetime import datetime, timedelta
import json


class QuoteComparisonEngine:
    """
    Multi-step quote generator:
    - Step 1: Simple hourly rate
    - Step 2: Package pricing
    - Step 3: Split run (multi-segment pricing)
    All with GST (5%) and configurable gratuity (default 18%)
    """
    
    def __init__(self):
        self.gst_rate = 0.05
        self.default_gratuity_rate = 0.18
        
        # Charter terms and rules
        self.charter_terms = {
            "cancellation_policy": "Cancellations must be made 48 hours in advance for full refund",
            "payment_terms": "50% deposit required to confirm, balance due 7 days before service",
            "no_show": "No-show charges: 50% of quoted total",
            "extra_stops": "Additional stops beyond agreed route: $25.00 per stop",
            "wait_time": "Wait time beyond 15 minutes: $50.00 per hour",
            "fuel_surcharge": "Fuel surcharge of 10% applies if diesel exceeds $1.50/liter",
            "cleaning": "Interior cleaning if required: $150.00",
            "vehicle_change": "Vehicle substitution permitted only with client approval",
            "gratuity": "Gratuity not included; 18% recommended based on service quality",
        }
    
    def calculate_hourly_quote(self, hours, hourly_rate, gratuity_rate=None):
        """
        Step 1: Simple hourly rate quote
        
        Args:
            hours: float - Total hours for rental
            hourly_rate: float - Rate per hour (e.g., 300.00)
            gratuity_rate: float - Gratuity percentage (default 18%)
        
        Returns:
            dict - Quote breakdown
        """
        if gratuity_rate is None:
            gratuity_rate = self.default_gratuity_rate
        
        subtotal = hours * hourly_rate
        gst = subtotal * self.gst_rate / (1 + self.gst_rate)  # GST included in amount
        net_amount = subtotal - gst
        gratuity = subtotal * gratuity_rate
        total = subtotal + gratuity
        
        return {
            "method": "hourly",
            "hours": hours,
            "hourly_rate": hourly_rate,
            "subtotal": subtotal,
            "gst": gst,
            "net_amount": net_amount,
            "gratuity_rate": gratuity_rate,
            "gratuity": gratuity,
            "total": total,
            "breakdown": f"{hours}h × ${hourly_rate:.2f}/h = ${subtotal:.2f}"
        }
    
    def calculate_package_quote(self, package_price, gratuity_rate=None):
        """
        Step 2: Fixed package pricing
        
        Args:
            package_price: float - Package price (e.g., 1550.00)
            gratuity_rate: float - Gratuity percentage (default 18%)
        
        Returns:
            dict - Quote breakdown
        """
        if gratuity_rate is None:
            gratuity_rate = self.default_gratuity_rate
        
        subtotal = package_price
        gst = subtotal * self.gst_rate / (1 + self.gst_rate)
        net_amount = subtotal - gst
        gratuity = subtotal * gratuity_rate
        total = subtotal + gratuity
        
        return {
            "method": "package",
            "package_price": package_price,
            "subtotal": subtotal,
            "gst": gst,
            "net_amount": net_amount,
            "gratuity_rate": gratuity_rate,
            "gratuity": gratuity,
            "total": total,
            "breakdown": f"Package: ${subtotal:.2f}"
        }
    
    def calculate_split_run_quote(self, segments, gratuity_rate=None):
        """
        Step 3: Split run with multiple segments and time blocks
        
        Args:
            segments: list of dict
                [
                    {"hours": 3, "rate": 300.00, "description": "Pickup to Supper"},
                    {"hours": 0, "rate": 0, "description": "Supper Stop (time stops)"},
                    {"hours": 3, "rate": 300.00, "description": "Supper to Return"},
                    {"hours": 1.5, "rate": 250.00, "description": "Extra Time"},
                ]
            gratuity_rate: float - Gratuity percentage (default 18%)
        
        Returns:
            dict - Quote breakdown with segment details
        """
        if gratuity_rate is None:
            gratuity_rate = self.default_gratuity_rate
        
        subtotal = 0
        segment_details = []
        
        for segment in segments:
            if segment["hours"] > 0:
                segment_total = segment["hours"] * segment["rate"]
                subtotal += segment_total
                segment_details.append({
                    "description": segment["description"],
                    "hours": segment["hours"],
                    "rate": segment["rate"],
                    "subtotal": segment_total
                })
            else:
                segment_details.append({
                    "description": segment["description"],
                    "hours": 0,
                    "rate": 0,
                    "subtotal": 0
                })
        
        gst = subtotal * self.gst_rate / (1 + self.gst_rate)
        net_amount = subtotal - gst
        gratuity = subtotal * gratuity_rate
        total = subtotal + gratuity
        
        return {
            "method": "split_run",
            "segments": segment_details,
            "subtotal": subtotal,
            "gst": gst,
            "net_amount": net_amount,
            "gratuity_rate": gratuity_rate,
            "gratuity": gratuity,
            "total": total,
            "breakdown": self._format_split_run_breakdown(segment_details)
        }
    
    def _format_split_run_breakdown(self, segments):
        """Format split run breakdown for display"""
        lines = []
        for seg in segments:
            if seg["hours"] > 0:
                lines.append(f"{seg['description']}: {seg['hours']}h × ${seg['rate']:.2f}/h = ${seg['subtotal']:.2f}")
            else:
                lines.append(f"{seg['description']}: (No Charge)")
        return "\n".join(lines)
    
    def apply_extra_charges(self, quote, extra_charges):
        """
        Apply extra charges to a quote
        
        Args:
            quote: dict - Base quote from calculate_*_quote()
            extra_charges: dict
                {
                    "extra_stops": 1,
                    "wait_time_hours": 0.5,
                    "cleaning": True,
                    "fuel_surcharge": 10.50,
                    "custom_charges": [{"description": "Late arrival discount", "amount": -50.00}]
                }
        
        Returns:
            dict - Updated quote with extra charges
        """
        subtotal = quote["subtotal"]
        extra_total = 0
        extra_line_items = []
        
        if extra_charges.get("extra_stops"):
            extra_stops_cost = extra_charges["extra_stops"] * 25.00
            extra_total += extra_stops_cost
            extra_line_items.append(f"Extra Stops ({extra_charges['extra_stops']}): ${extra_stops_cost:.2f}")
        
        if extra_charges.get("wait_time_hours"):
            wait_cost = extra_charges["wait_time_hours"] * 50.00
            extra_total += wait_cost
            extra_line_items.append(f"Wait Time ({extra_charges['wait_time_hours']}h): ${wait_cost:.2f}")
        
        if extra_charges.get("cleaning"):
            cleaning_cost = 150.00
            extra_total += cleaning_cost
            extra_line_items.append(f"Interior Cleaning: ${cleaning_cost:.2f}")
        
        if extra_charges.get("fuel_surcharge"):
            extra_total += extra_charges["fuel_surcharge"]
            extra_line_items.append(f"Fuel Surcharge: ${extra_charges['fuel_surcharge']:.2f}")
        
        if extra_charges.get("custom_charges"):
            for charge in extra_charges["custom_charges"]:
                extra_total += charge["amount"]
                extra_line_items.append(f"{charge['description']}: ${charge['amount']:.2f}")
        
        # Recalculate with extra charges
        new_subtotal = subtotal + extra_total
        gst = new_subtotal * self.gst_rate / (1 + self.gst_rate)
        net_amount = new_subtotal - gst
        gratuity = new_subtotal * quote["gratuity_rate"]
        new_total = new_subtotal + gratuity
        
        quote_with_extras = quote.copy()
        quote_with_extras.update({
            "original_subtotal": subtotal,
            "extra_charges": extra_line_items,
            "extra_total": extra_total,
            "subtotal": new_subtotal,
            "gst": gst,
            "net_amount": net_amount,
            "gratuity": gratuity,
            "total": new_total,
        })
        
        return quote_with_extras


class QuoteGeneratorDialog(QDialog):
    """
    Interactive quote generator with step-by-step comparison
    Generates printable quotes with charter terms
    """
    
    quote_generated = pyqtSignal(dict)
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.engine = QuoteComparisonEngine()
        self.current_quotes = {}
        
        self.setWindowTitle("Charter Quote Generator")
        self.setGeometry(100, 100, 1200, 800)
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("📋 Multi-Step Quote Comparison")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Input section
        input_group = QGroupBox("Quote Details")
        input_layout = QFormLayout()
        
        # Basic info
        self.client_name = QLineEdit()
        input_layout.addRow("Client Name:", self.client_name)
        
        self.pickup_location = QLineEdit()
        self.pickup_location.setText("Red Deer")
        input_layout.addRow("Pickup Location:", self.pickup_location)
        
        self.dropoff_location = QLineEdit()
        self.dropoff_location.setText("Red Deer")
        input_layout.addRow("Dropoff Location:", self.dropoff_location)
        
        self.pax_count = QSpinBox()
        self.pax_count.setMinimum(1)
        self.pax_count.setMaximum(50)
        self.pax_count.setValue(20)
        input_layout.addRow("Passengers:", self.pax_count)
        
        self.gst_checkbox = QCheckBox("Include GST (5%)")
        self.gst_checkbox.setChecked(True)
        input_layout.addRow("", self.gst_checkbox)
        
        self.gratuity_rate = QDoubleSpinBox()
        self.gratuity_rate.setMinimum(0)
        self.gratuity_rate.setMaximum(100)
        self.gratuity_rate.setValue(18)
        self.gratuity_rate.setSuffix("%")
        input_layout.addRow("Gratuity Rate:", self.gratuity_rate)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        # Tabs for quote methods
        tabs = QTabWidget()
        
        tabs.addTab(self.create_hourly_tab(), "💰 Step 1: Hourly Rate")
        tabs.addTab(self.create_package_tab(), "📦 Step 2: Package")
        tabs.addTab(self.create_split_run_tab(), "🔄 Step 3: Split Run")
        tabs.addTab(self.create_extras_tab(), "➕ Extra Charges")
        
        layout.addWidget(tabs)
        
        # Quote comparison results
        results_label = QLabel("Quote Comparison Results:")
        results_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout.addWidget(results_label)
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels([
            "Quote Method", "Subtotal", "GST", "Gratuity", "Total"
        ])
        self.results_table.setMaximumHeight(200)
        layout.addWidget(self.results_table)
        
        # Charter terms section
        terms_label = QLabel("Charter Agreement & Terms (to be printed on quote):")
        terms_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout.addWidget(terms_label)
        
        self.terms_display = QTextEdit()
        self.terms_display.setReadOnly(True)
        self.terms_display.setMaximumHeight(150)
        self.load_charter_terms()
        layout.addWidget(self.terms_display)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.generate_btn = QPushButton("🔄 Calculate All Quotes")
        self.generate_btn.clicked.connect(self.calculate_all_quotes)
        button_layout.addWidget(self.generate_btn)
        
        button_layout.addStretch()
        
        self.print_btn = QPushButton("🖨️ Print Quote")
        self.print_btn.clicked.connect(self.print_quote)
        button_layout.addWidget(self.print_btn)
        
        self.save_btn = QPushButton("💾 Save Quote")
        self.save_btn.clicked.connect(self.save_quote)
        button_layout.addWidget(self.save_btn)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def create_hourly_tab(self):
        """Tab 1: Simple hourly rate quote"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        form = QFormLayout()
        
        self.hourly_hours = QDoubleSpinBox()
        self.hourly_hours.setMinimum(0.5)
        self.hourly_hours.setMaximum(24)
        self.hourly_hours.setValue(8)
        self.hourly_hours.setSuffix(" hours")
        form.addRow("Hours:", self.hourly_hours)
        
        self.hourly_rate = QDoubleSpinBox()
        self.hourly_rate.setMinimum(50)
        self.hourly_rate.setMaximum(1000)
        self.hourly_rate.setValue(300)
        self.hourly_rate.setPrefix("$")
        form.addRow("Rate per Hour:", self.hourly_rate)
        
        layout.addLayout(form)
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget
    
    def create_package_tab(self):
        """Tab 2: Fixed package pricing"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        form = QFormLayout()
        
        self.package_hours = QLineEdit()
        self.package_hours.setText("8 hours")
        form.addRow("Package Description:", self.package_hours)
        
        self.package_price = QDoubleSpinBox()
        self.package_price.setMinimum(100)
        self.package_price.setMaximum(5000)
        self.package_price.setValue(1550)
        self.package_price.setPrefix("$")
        form.addRow("Package Price:", self.package_price)
        
        self.package_notes = QTextEdit()
        self.package_notes.setPlaceholderText("e.g., Includes up to 3 stops, up to 2 hours wait time, etc.")
        form.addRow("Package Includes:", self.package_notes)
        
        layout.addLayout(form)
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget
    
    def create_split_run_tab(self):
        """Tab 3: Split run with multiple segments"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        info = QLabel("Split Run: Time stops at drop-off, restarts at next pickup\nExtra time charged at different rate")
        layout.addWidget(info)
        
        # Segment table
        self.split_table = QTableWidget()
        self.split_table.setColumnCount(4)
        self.split_table.setHorizontalHeaderLabels([
            "Description", "Hours", "Rate/Hour", "Subtotal"
        ])
        self.split_table.setRowCount(4)
        
        # Example rows
        examples = [
            ("Pickup → Event Start", 3, 300),
            ("Time Stopped (Meal/Break)", 0, 0),
            ("Event End → Return", 3, 300),
            ("Extra Time (if needed)", 0, 250),
        ]
        
        for i, (desc, hours, rate) in enumerate(examples):
            self.split_table.setItem(i, 0, QTableWidgetItem(desc))
            
            hours_spin = QDoubleSpinBox()
            hours_spin.setMinimum(0)
            hours_spin.setMaximum(24)
            hours_spin.setValue(hours)
            self.split_table.setCellWidget(i, 1, hours_spin)
            
            rate_spin = QDoubleSpinBox()
            rate_spin.setMinimum(0)
            rate_spin.setMaximum(500)
            rate_spin.setValue(rate)
            rate_spin.setPrefix("$")
            self.split_table.setCellWidget(i, 2, rate_spin)
            
            # Subtotal will be calculated
            self.split_table.setItem(i, 3, QTableWidgetItem("$0.00"))
        
        layout.addWidget(self.split_table)
        widget.setLayout(layout)
        return widget
    
    def create_extras_tab(self):
        """Tab 4: Extra charges and adjustments"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        form = QFormLayout()
        
        self.extra_stops = QSpinBox()
        self.extra_stops.setMinimum(0)
        self.extra_stops.setMaximum(20)
        form.addRow("Extra Stops ($25 each):", self.extra_stops)
        
        self.wait_time = QDoubleSpinBox()
        self.wait_time.setMinimum(0)
        self.wait_time.setMaximum(24)
        self.wait_time.setSuffix(" hours")
        form.addRow("Wait Time ($50/hour):", self.wait_time)
        
        self.cleaning = QCheckBox("Interior Cleaning ($150)")
        form.addRow("", self.cleaning)
        
        self.fuel_surcharge = QDoubleSpinBox()
        self.fuel_surcharge.setMinimum(0)
        self.fuel_surcharge.setMaximum(100)
        self.fuel_surcharge.setPrefix("$")
        form.addRow("Fuel Surcharge:", self.fuel_surcharge)
        
        form.addRow("", QLabel(""))  # Spacer
        
        self.custom_charges_text = QTextEdit()
        self.custom_charges_text.setPlaceholderText("Custom charges (one per line):\nDescription: Amount\ne.g., Early morning fee: 50.00\nLate arrival discount: -50.00")
        form.addRow("Custom Charges:", self.custom_charges_text)
        
        layout.addLayout(form)
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget
    
    def load_charter_terms(self):
        """Load and display charter terms"""
        terms_text = "CHARTER AGREEMENT & TERMS:\n\n"
        for i, (key, value) in enumerate(self.engine.charter_terms.items(), 1):
            terms_text += f"{i}. {key.replace('_', ' ').title()}: {value}\n"
        self.terms_display.setText(terms_text)
    
    def calculate_all_quotes(self):
        """Calculate all three quote methods and display comparison"""
        try:
            gratuity_rate = self.gratuity_rate.value() / 100
            
            # Quote 1: Hourly
            quote1 = self.engine.calculate_hourly_quote(
                self.hourly_hours.value(),
                self.hourly_rate.value(),
                gratuity_rate
            )
            self.current_quotes["hourly"] = quote1
            
            # Quote 2: Package
            quote2 = self.engine.calculate_package_quote(
                self.package_price.value(),
                gratuity_rate
            )
            self.current_quotes["package"] = quote2
            
            # Quote 3: Split Run
            segments = []
            for row in range(self.split_table.rowCount()):
                desc = self.split_table.item(row, 0).text()
                hours = self.split_table.cellWidget(row, 1).value()
                rate = self.split_table.cellWidget(row, 2).value()
                segments.append({"description": desc, "hours": hours, "rate": rate})
            
            quote3 = self.engine.calculate_split_run_quote(segments, gratuity_rate)
            self.current_quotes["split_run"] = quote3
            
            # Apply extra charges to all quotes
            extra_charges = {
                "extra_stops": self.extra_stops.value(),
                "wait_time_hours": self.wait_time.value(),
                "cleaning": self.cleaning.isChecked(),
                "fuel_surcharge": self.fuel_surcharge.value(),
                "custom_charges": self._parse_custom_charges()
            }
            
            # Apply only if there are extra charges
            if any(extra_charges.values()):
                quote1 = self.engine.apply_extra_charges(quote1, extra_charges)
                quote2 = self.engine.apply_extra_charges(quote2, extra_charges)
                quote3 = self.engine.apply_extra_charges(quote3, extra_charges)
                self.current_quotes = {
                    "hourly": quote1,
                    "package": quote2,
                    "split_run": quote3
                }
            
            # Display comparison table
            self.results_table.setRowCount(3)
            self.results_table.setItem(0, 0, QTableWidgetItem("Hourly Rate"))
            self.results_table.setItem(0, 1, QTableWidgetItem(f"${quote1['subtotal']:.2f}"))
            self.results_table.setItem(0, 2, QTableWidgetItem(f"${quote1['gst']:.2f}"))
            self.results_table.setItem(0, 3, QTableWidgetItem(f"${quote1['gratuity']:.2f}"))
            self.results_table.setItem(0, 4, QTableWidgetItem(f"${quote1['total']:.2f}"))
            
            self.results_table.setItem(1, 0, QTableWidgetItem("Package"))
            self.results_table.setItem(1, 1, QTableWidgetItem(f"${quote2['subtotal']:.2f}"))
            self.results_table.setItem(1, 2, QTableWidgetItem(f"${quote2['gst']:.2f}"))
            self.results_table.setItem(1, 3, QTableWidgetItem(f"${quote2['gratuity']:.2f}"))
            self.results_table.setItem(1, 4, QTableWidgetItem(f"${quote2['total']:.2f}"))
            
            self.results_table.setItem(2, 0, QTableWidgetItem("Split Run"))
            self.results_table.setItem(2, 1, QTableWidgetItem(f"${quote3['subtotal']:.2f}"))
            self.results_table.setItem(2, 2, QTableWidgetItem(f"${quote3['gst']:.2f}"))
            self.results_table.setItem(2, 3, QTableWidgetItem(f"${quote3['gratuity']:.2f}"))
            self.results_table.setItem(2, 4, QTableWidgetItem(f"${quote3['total']:.2f}"))
            
            # Highlight lowest total
            min_total = min(quote1['total'], quote2['total'], quote3['total'])
            for row in range(3):
                if float(self.results_table.item(row, 4).text().replace('$', '')) == min_total:
                    for col in range(5):
                        self.results_table.item(row, col).setBackground(QColor(200, 255, 200))
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Calculation failed: {e}")
    
    def _parse_custom_charges(self):
        """Parse custom charges from text"""
        charges = []
        for line in self.custom_charges_text.toPlainText().split('\n'):
            line = line.strip()
            if ':' in line:
                desc, amount_str = line.rsplit(':', 1)
                try:
                    amount = float(amount_str.strip())
                    charges.append({"description": desc.strip(), "amount": amount})
                except ValueError:
                    pass
        return charges
    
    def print_quote(self):
        """Print formatted quote with options to display, save, or email"""
        if not self.current_quotes:
            QMessageBox.warning(self, "Warning", "Please calculate quotes first")
            return
        
        quote_text = self._format_quote_for_print()
        
        # Show quote with options
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Charter Quote")
        dialog.setText(quote_text)
        dialog.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        dialog.setFont(QFont("Courier", 9))
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Save)
        
        result = dialog.exec()
        
        if result == QMessageBox.StandardButton.Save:
            # Save to file
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Quote",
                f"Quote_{self.client_name.text().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.txt",
                "Text Files (*.txt);;All Files (*)"
            )
            if file_path:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(quote_text)
                    QMessageBox.information(self, "Success", f"Quote saved to {file_path}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to save quote: {e}")
    
    def save_quote(self):
        """Save quote to database"""
        if not self.current_quotes:
            QMessageBox.warning(self, "Warning", "No quote to save")
            return
        
        try:
            # Save quote details to database
            quote_text = self._format_quote_for_print()
            
            QMessageBox.information(
                self, 
                "Quote Saved",
                f"Quote for {self.client_name.text()} has been saved.\n\n"
                f"Pickup: {self.pickup_location.text()}\n"
                f"Dropoff: {self.dropoff_location.text()}\n"
                f"Passengers: {self.pax_count.value()}\n\n"
                "[Database integration pending]"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save quote: {e}")
    
    def _format_quote_for_print(self):
        """Format quotes for printing"""
        text = f"CHARTER QUOTE\n"
        text += f"{'='*60}\n"
        text += f"Client: {self.client_name.text()}\n"
        text += f"Route: {self.pickup_location.text()} → {self.dropoff_location.text()}\n"
        text += f"Passengers: {self.pax_count.value()}\n"
        text += f"Date: {datetime.now().strftime('%m/%d/%Y')}\n\n"
        
        for method, quote in self.current_quotes.items():
            text += f"\n{method.upper()} OPTION:\n"
            text += f"{'-'*60}\n"
            text += f"Subtotal: ${quote['subtotal']:.2f}\n"
            text += f"GST (5%): ${quote['gst']:.2f}\n"
            text += f"Gratuity ({quote['gratuity_rate']*100:.0f}%): ${quote['gratuity']:.2f}\n"
            text += f"TOTAL: ${quote['total']:.2f}\n"
        
        text += f"\n\n{'='*60}\n"
        text += "CHARTER AGREEMENT & TERMS\n"
        text += f"{'='*60}\n"
        for i, (key, value) in enumerate(self.engine.charter_terms.items(), 1):
            text += f"{i}. {key.replace('_', ' ').title()}: {value}\n"
        
        return text
