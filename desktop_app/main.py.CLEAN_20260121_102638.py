"""
Arrow Limousine Management System - Desktop Application (PyQt6)
Form-based UI with tab navigation, auto-fill, print, drill-down reports

CRITICAL BUSINESS RULES IMPLEMENTED:
- reserve_number is ALWAYS the business key for charter-payment matching
- GST is INCLUDED in gross amounts (Alberta 5% GST)
- Always commit database changes (conn.commit())
- Duplicate prevention: check for existing records before import
- Protected patterns: recurring payments, NSF charges, inter-account transfers
"""

import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QTextEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QGroupBox, QFormLayout, QSplitter, QTreeWidget, QTreeWidgetItem,
    QMessageBox, QFileDialog, QScrollArea, QHeaderView, QInputDialog, QDialog,
    QAbstractSpinBox, QMenu, QAbstractItemView, QCompleter,
    QProgressBar, QStatusBar, QFrame
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal, QTimer, QSettings
from PyQt6.QtGui import QFont, QKeySequence, QShortcut, QColor, QBrush, QAction, QUndoStack, QUndoCommand, QPixmap
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
import psycopg2
from psycopg2 import extensions
from decimal import Decimal
import json
from datetime import datetime, timedelta
import hashlib
import hmac
import binascii
from typing import Optional, List, Dict, Tuple

# Add current directory and project root to path for module imports
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, os.pardir))
for path_candidate in (current_dir, project_root):
    if path_candidate not in sys.path:
        sys.path.insert(0, path_candidate)

# Mega Menu Navigation
from mega_menu_widget import MegaMenuWidget
from report_explorer_widget import ReportExplorerWidget
from employee_management_widget import EmployeeManagementWidget
from vehicle_management_widget import VehicleManagementWidget
from dispatch_management_widget import DispatchManagementWidget
from document_management_widget import DocumentManagementWidget
from admin_management_widget import AdminManagementWidget
from asset_management_widget import AssetManagementWidget
from beverage_management_widget import BeverageManagementWidget
from beverage_management_widget import BeverageManagementWidget
from beverage_ordering import BeverageSelectionDialog

# Enhanced Drill-Down Widgets
from enhanced_charter_widget import EnhancedCharterListWidget
from enhanced_employee_widget import EnhancedEmployeeListWidget
from enhanced_vehicle_widget import EnhancedVehicleListWidget
from enhanced_client_widget import EnhancedClientListWidget
from business_entity_drill_down import BusinessEntityDialog
from tax_management_widget import TaxManagementWidget
from receipt_search_match_widget import ReceiptSearchMatchWidget
from driver_calendar_widget import DriverCalendarWidget
from dispatcher_calendar_widget import DispatcherCalendarWidget
from vendor_invoice_manager import VendorInvoiceManager
from wcb_rate_widget import WCBRateEntryWidget
from payroll_entry_widget import PayrollEntryWidget
from roe_form_widget import ROEFormWidget

# Consolidated dashboard imports (7 domain-organized files)
from dashboards_core import (
    FleetManagementWidget, DriverPerformanceWidget,
    FinancialDashboardWidget, PaymentReconciliationWidget,
    VehicleAnalyticsWidget, EmployeePayrollAuditWidget,
    QuickBooksReconciliationWidget, CharterAnalyticsWidget,
    ComplianceTrackingWidget, BudgetAnalysisWidget,
    InsuranceTrackingWidget,
    VehicleFleetCostAnalysisWidget, VehicleMaintenanceTrackingWidget,
    FuelEfficiencyTrackingWidget, VehicleUtilizationWidget,
    FleetAgeAnalysisWidget
)

from dashboards_operations import (
    DriverPayAnalysisWidget, EmployeePerformanceMetricsWidget,
    PayrollTaxComplianceWidget, DriverScheduleManagementWidget,
    PaymentReconciliationAdvancedWidget, ARAgingDashboardWidget,
    CashFlowReportWidget, ProfitLossReportWidget,
    CharterAnalyticsAdvancedWidget,
    CharterManagementDashboardWidget, CustomerLifetimeValueWidget,
    CharterCancellationAnalysisWidget, BookingLeadTimeAnalysisWidget,
    CustomerSegmentationWidget, RouteProfitabilityWidget,
    GeographicRevenueDistributionWidget, HosComplianceTrackingWidget,
    AdvancedMaintenanceScheduleWidget, SafetyIncidentTrackingWidget,
    VendorPerformanceWidget, RealTimeFleetMonitoringWidget,
    SystemHealthDashboardWidget, DataQualityAuditWidget
)

from dashboards_predictive import (
    DemandForecastingWidget, ChurnPredictionWidget,
    RevenueOptimizationWidget, CustomerWorthWidget,
    NextBestActionWidget, SeasonalityAnalysisWidget,
    CostBehaviorAnalysisWidget, BreakEvenAnalysisWidget,
    EmailCampaignPerformanceWidget, CustomerJourneyAnalysisWidget,
    CompetitiveIntelligenceWidget, RegulatoryComplianceTrackingWidget,
    CRAComplianceReportWidget, EmployeeProductivityTrackingWidget,
    PromotionalEffectivenessWidget,
    RealTimeFleetTrackingMapWidget, LiveDispatchMonitorWidget,
    MobileCustomerPortalWidget, MobileDriverDashboardWidget,
    APIEndpointPerformanceWidget, ThirdPartyIntegrationMonitorWidget,
    AdvancedTimeSeriesChartWidget, InteractiveHeatmapWidget,
    ComparativeAnalysisChartWidget, DistributionAnalysisChartWidget,
    CorrelationMatrixWidget, AutomationWorkflowsWidget,
    AlertManagementWidget
)

from dashboards_optimization import (
    DriverShiftOptimizationWidget, RouteSchedulingWidget,
    VehicleAssignmentPlannerWidget, CalendarForecasitngWidget,
    BreakComplianceScheduleWidget, MaintenanceSchedulingWidget,
    CrewRotationAnalysisWidget, LoadBalancingOptimizerWidget,
    DynamicPricingScheduleWidget, HistoricalSchedulingPatternsWidget,
    PredictiveSchedulingWidget, CapacityUtilizationWidget,
    BranchLocationConsolidationWidget, InterBranchPerformanceComparisonWidget,
    ConsolidatedProfitLossWidget, ResourceAllocationAcrossPropertiesWidget,
    CrossBranchCharteringWidget, SharedVehicleTrackingWidget,
    UnifiedInventoryManagementWidget, MultiLocationPayrollWidget,
    TerritoryMappingWidget, MarketOverlapAnalysisWidget,
    RegionalPerformanceMetricsWidget, PropertyLevelKPIWidget,
    FranchiseIntegrationWidget, LicenseTrackingWidget,
    OperationsConsolidationWidget
)

from dashboards_customer import (
    SelfServiceBookingPortalWidget, TripHistoryWidget,
    InvoiceReceiptManagementWidget, AccountSettingsWidget,
    LoyaltyProgramTrackingWidget, ReferralAnalyticsWidget,
    SubscriptionManagementWidget, CorporateAccountManagementWidget,
    RecurringBookingManagementWidget, AutomatedQuoteGeneratorWidget,
    ChatIntegrationWidget, SupportTicketManagementWidget,
    RatingReviewManagementWidget, SavedPreferencesWidget,
    FleetPreferencesWidget, DriverFeedbackWidget,
    CustomerCommunicationsWidget
)

from dashboards_analytics import (
    CustomReportBuilderWidget, ExecutiveDashboardWidget,
    BudgetVsActualWidget, TrendAnalysisWidget,
    AnomalyDetectionWidget, SegmentationAnalysisWidget,
    CompetitiveAnalysisWidget, OperationalMetricsWidget,
    DataQualityReportWidget, ROIAnalysisWidget,
    ForecastingWidget, ReportSchedulerWidget,
    ComplianceReportingWidget, ExportManagementWidget,
    AuditTrailWidget
)

from dashboards_ml import (
    DemandForecastingMLWidget, ChurnPredictionMLWidget,
    PricingOptimizationMLWidget, CustomerClusteringMLWidget,
    AnomalyDetectionMLWidget, RecommendationEngineWidget,
    ResourceOptimizationMLWidget, MarketingMLWidget,
    ModelPerformanceWidget, PredictiveMaintenanceMLWidget
)

# Accounting-focused reports
import accounting_reports
from accounting_reports import (
    TrialBalanceWidget, JournalExplorerWidget, BankReconciliationWidget,
    PLSummaryWidget, PLCategoryWidget, VehiclePerformanceWidget, DriverCostWidget,
    FleetMaintenanceWidget, VehicleInsuranceWidget, VehicleDamageWidget,
    DriverMonthlyCostWidget, DriverRevenueVsPayWidget, BankRecSuggestionsWidget,
)

# ============================================================================
# DATABASE CONNECTION
# ============================================================================

class VendorSelector(QComboBox):
    """Smart vendor selector with autocomplete, historical category/GL lookup, validation colors"""
    
    def __init__(self, db_conn, parent=None):
        super().__init__(parent)
        self.db_conn = db_conn
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        
        # Track selected vendor data
        self.selected_vendor = None
        self.suggested_category = None
        self.suggested_gl_code = None
        
        # Validation color support
        self._validation_state = 'neutral'
        self.lineEdit().setToolTip(
            "<b>🏢 Vendor Name</b><br>"
            "Select from approved vendors. Type to search.<br>"
            "Names auto-normalize to UPPERCASE.<br>"
            "<font color='green'>✓ Valid</font> when selected from list.<br>"
            "<font color='blue'>✓ Keyboard:</font> Down arrow to list, type to filter"
        )
        
        self.vendors = []
        self.load_vendor_list()
        self.currentTextChanged.connect(self._on_vendor_changed)
        self.lineEdit().textChanged.connect(self._update_validation_color)
    
    def load_vendor_list(self):
        """Load approved vendor list from database"""
        try:
            cur = self.db_conn.cursor()
            cur.execute("""
                SELECT DISTINCT canonical_vendor 
                FROM receipts 
                WHERE canonical_vendor IS NOT NULL 
                  AND canonical_vendor != ''
                ORDER BY canonical_vendor
            """)
            vendors = [row[0] for row in cur.fetchall()]
            cur.close()
            
            self.vendors = vendors
            self.clear()
            self.addItems(vendors)
            # Smart autocomplete (contains, case-insensitive)
            completer = QCompleter(self.vendors)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            self.setCompleter(completer)
        except Exception as e:
            print(f"Error loading vendor list: {e}")
    
    def _update_validation_color(self):
        """Update field color based on validation state"""
        text = self.lineEdit().text()
        if not text:
            self._set_field_style('neutral')  # Gray - empty/optional
            return
        
        # Check if text is in vendor list (valid if exact match)
        vendor_upper = text.upper()
        is_in_list = any(vendor_upper == self.itemText(i).upper() for i in range(self.count()))
        
        if is_in_list:
            self._set_field_style('valid')  # Green - valid
        else:
            self._set_field_style('warning')  # Yellow - not in list but might be typed
    
    def _set_field_style(self, state):
        """Apply color style to field based on validation state"""
        self._validation_state = state
        line_edit = self.lineEdit()
        
        if state == 'valid':
            # Green border and subtle green background
            line_edit.setStyleSheet("QLineEdit { border: 2px solid #4CAF50; background-color: #f0fdf4; }")
        elif state == 'warning':
            # Yellow border and subtle yellow background
            line_edit.setStyleSheet("QLineEdit { border: 2px solid #FFC107; background-color: #fffbf0; }")
        elif state == 'error':
            # Red border and subtle red background
            line_edit.setStyleSheet("QLineEdit { border: 2px solid #f44336; background-color: #fdf0f0; }")
        else:  # neutral
            # Gray border and normal background
            line_edit.setStyleSheet("QLineEdit { border: 1px solid #ccc; background-color: white; }")
    
    def _on_vendor_changed(self, text):
        """When vendor changes, lookup historical category and GL code"""
        if not text:
            self.selected_vendor = None
            self.suggested_category = None
            self.suggested_gl_code = None
            self._update_validation_color()
            return
        
        # Normalize to uppercase
        vendor_upper = text.upper()
        self.blockSignals(True)
        self.lineEdit().setText(vendor_upper)
        self.blockSignals(False)
        
        # Lookup historical data for this vendor
        self._lookup_vendor_history(vendor_upper)
        self._update_validation_color()
    
    def _lookup_vendor_history(self, vendor):
        """Find most common category and GL code for this vendor"""
        try:
            cur = self.db_conn.cursor()
            
            # Find most common category for this vendor
            cur.execute("""
                SELECT category, COUNT(*) as cnt
                FROM receipts
                WHERE canonical_vendor = %s AND category IS NOT NULL
                GROUP BY category
                ORDER BY cnt DESC
                LIMIT 1
            """, (vendor,))
            result = cur.fetchone()
            self.suggested_category = result[0] if result else None
            
            # Find most common GL code for this vendor
            cur.execute("""
                SELECT gl_account_code, COUNT(*) as cnt
                FROM receipts
                WHERE canonical_vendor = %s AND gl_account_code IS NOT NULL
                GROUP BY gl_account_code
                ORDER BY cnt DESC
                LIMIT 1
            """, (vendor,))
            result = cur.fetchone()
            self.suggested_gl_code = result[0] if result else None
            
            cur.close()
            self.selected_vendor = vendor
            
        except Exception as e:
            print(f"Error looking up vendor history: {e}")
    
    def get_vendor(self):
        """Get normalized vendor name (uppercase)"""
        return self.lineEdit().text().upper()
    
    def get_suggested_category(self):
        """Get historically most common category for this vendor"""
        return self.suggested_category
    
    def get_suggested_gl_code(self):
        """Get historically most common GL code for this vendor"""
        return self.suggested_gl_code


class DateInput(QLineEdit):
    """Flexible date input field that accepts multiple formats like Excel"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        today = QDate.currentDate()
        self._current_date = today
        self.setText(today.toString("MM/dd/yyyy"))
        self.setPlaceholderText("MM/DD/YYYY or Jan 01 2012")
        self.setMaxLength(50)  # Allow long text formats
        
        # Validation color support
        self._validation_state = 'valid'
        self.setStyleSheet("QLineEdit { border: 1px solid #ccc; background-color: white; }")
        
        # Rich tooltip with format examples
        self.setToolTip(
            "<b>📅 Date Input</b><br>"
            "<font color='green'><b>Flexible formats:</b></font><br>"
            "• 01/15/2012 or 01-15-2012<br>"
            "• Jan 01 2012 or January 1 2012<br>"
            "• 20120115 (compact)<br>"
            "• 2012-01-15 (ISO)<br>"
            "<font color='blue'><b>Shortcuts:</b> t=today, y=yesterday</font><br>"
            "Just type and press Enter or Tab"
        )
    
    def setDate(self, date):
        """Set date and update display"""
        self._current_date = date
        self.setText(date.toString("MM/dd/yyyy"))
    
    def getDate(self):
        """Get current date as QDate"""
        return self._current_date
    
    def focusInEvent(self, event):
        """Select all text when field gets focus for easy replacement"""
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)
    
    def mouseDoubleClickEvent(self, event):
        """Allow double-click to position cursor for editing"""
        # Don't select all on double-click, let user position cursor
        super().mouseDoubleClickEvent(event)
    
    def focusOutEvent(self, event):
        """Parse and format when user leaves the field"""
        super().focusOutEvent(event)
        self._parse_and_format()
    
    def keyPressEvent(self, event):
        """Handle shortcuts and Enter key"""
        text = self.text().strip()
        
        # Shortcuts
        if text.lower() == 't' and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
            self.setDate(QDate.currentDate())
            self._set_field_style('valid')
            event.accept()
            return
        elif text.lower() == 'y' and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
            self.setDate(QDate.currentDate().addDays(-1))
            self._set_field_style('valid')
            event.accept()
            return
        
        super().keyPressEvent(event)
    
    def _parse_and_format(self):
        """Parse flexible date formats and format for database storage"""
        text = self.text().strip()

        if not text:
            self.setText(self._current_date.toString("MM/dd/yyyy"))
            self._set_field_style('neutral')
            return

        # Try multiple formats
        parsed = None
        
        # Format 1: MM/dd/yyyy or MM-dd-yyyy
        for fmt in ["MM/dd/yyyy", "MM-dd-yyyy", "M/d/yyyy", "M-d-yyyy"]:
            parsed = QDate.fromString(text, fmt)
            if parsed.isValid():
                break
        
        # Format 2: yyyymmdd (compact)
        if not parsed or not parsed.isValid():
            if len(text) == 8 and text.isdigit():
                parsed = QDate.fromString(text, "yyyyMMdd")
        
        # Format 3: "Jan 01 2012" or "January 1 2012"
        if not parsed or not parsed.isValid():
            for fmt in ["MMM dd yyyy", "MMMM d yyyy", "MMM d yyyy", "MMMM dd yyyy"]:
                parsed = QDate.fromString(text, fmt)
                if parsed.isValid():
                    break
        
        # Format 4: "01 Jan 2012" (day first)
        if not parsed or not parsed.isValid():
            for fmt in ["dd MMM yyyy", "d MMM yyyy", "dd MMMM yyyy", "d MMMM yyyy"]:
                parsed = QDate.fromString(text, fmt)
                if parsed.isValid():
                    break
        
        # Format 5: ISO format yyyy-MM-dd
        if not parsed or not parsed.isValid():
            parsed = QDate.fromString(text, "yyyy-MM-dd")
        
        # If valid, update and format
        if parsed and parsed.isValid():
            self._current_date = parsed
            self.setText(parsed.toString("MM/dd/yyyy"))
            self._set_field_style('valid')
        else:
            # Invalid date - restore previous
            self.setText(self._current_date.toString("MM/dd/yyyy"))
            self._set_field_style('error')
            QTimer.singleShot(2000, lambda: self._set_field_style('neutral'))
    
    def _set_field_style(self, state):
        """Apply color style based on validation state"""
        self._validation_state = state
        if state == 'valid':
            self.setStyleSheet("QLineEdit { border: 2px solid #4CAF50; background-color: #f0fdf4; }")
        elif state == 'warning':
            self.setStyleSheet("QLineEdit { border: 2px solid #FFC107; background-color: #fffbf0; }")
        elif state == 'error':
            self.setStyleSheet("QLineEdit { border: 2px solid #f44336; background-color: #fdf0f0; }")
        else:  # neutral
            self.setStyleSheet("QLineEdit { border: 1px solid #ccc; background-color: white; }")


class CurrencyInput(QLineEdit):
    """Custom currency input field with validation colors and helpful tooltips"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("0.00")
        self.setText("0.00")
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setMaxLength(15)  # Up to $999,999.99 (15 chars max with formatting buffer)
        self.setMinimumWidth(150)  # Standard width for currency fields
        self.setMaximumWidth(200)  # Cap the max width
        self._is_formatting = False  # Flag to prevent recursive formatting
        self.textChanged.connect(self._on_text_changed)
        
        # Validation color support
        self._validation_state = 'valid'
        self.setStyleSheet("QLineEdit { border: 1px solid #ccc; background-color: white; text-align: right; }")
        
        # Rich tooltip with currency examples
        self.setToolTip(
            "<b>💵 Currency Input</b><br>"
            "Enter amounts in any format:<br>"
            "<font color='green'><b>✓ Valid formats:</b></font><br>"
            "• 10 → $10.00<br>"
            "• 10.50 → $10.50<br>"
            "• .50 → $0.50<br>"
            "• 250 → $250.00<br>"
            "<font color='blue'><b>Limits:</b> $0.00 - $999,999.99</font><br>"
            "Auto-formats to 2 decimal places."
        )
    
    def focusInEvent(self, event):
        """Select all text when field gets focus"""
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)
    
    def mouseDoubleClickEvent(self, event):
        """Allow double-click to position cursor for editing"""
        # Don't select all - let user position cursor for editing
        super().mouseDoubleClickEvent(event)
    
    def focusOutEvent(self, event):
        """Format when leaving the field"""
        super().focusOutEvent(event)
        if self.text().strip():
            self._do_format()
    
    def keyPressEvent(self, event):
        """Handle Enter key to move to next field"""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Format the value first
            if self.text().strip():
                self._do_format()
            # Move to next widget
            self.focusNextChild()
            event.accept()
            return
        super().keyPressEvent(event)
    
    def _set_field_style(self, state):
        """Apply color style based on validation state"""
        self._validation_state = state
        if state == 'valid':
            self.setStyleSheet("QLineEdit { border: 2px solid #4CAF50; background-color: #f0fdf4; text-align: right; }")
        elif state == 'warning':
            self.setStyleSheet("QLineEdit { border: 2px solid #FFC107; background-color: #fffbf0; text-align: right; }")
        elif state == 'error':
            self.setStyleSheet("QLineEdit { border: 2px solid #f44336; background-color: #fdf0f0; text-align: right; }")
        else:  # neutral
            self.setStyleSheet("QLineEdit { border: 1px solid #ccc; background-color: white; text-align: right; }")
    
    def _on_text_changed(self):
        """Handle text changes - validate on focus out, not during typing"""
        # Just validate the input as the user types, don't reformat yet
        text = self.text()
        if text == "":
            return
        
        # Quick validation: only allow digits and one decimal point
        cleaned = ""
        decimal_count = 0
        for char in text:
            if char.isdigit():
                cleaned += char
            elif char == "." and decimal_count == 0:
                cleaned += char
                decimal_count += 1
        
        # If the cleaned version is different, update it (removes invalid chars)
        if cleaned != text and cleaned != "":
            self._is_formatting = True
            self.setText(cleaned)
            self._is_formatting = False
    
    def _do_format(self):
        """
        Format currency with validation colors: 10→10.00, 10.10→10.10, .50→0.50, 1706.25→1706.25
        Validates against currency column requirements (0-999,999.99)
        """
        text = self.text()
        if not text:
            self._set_field_style('neutral')
            return
        
        # Remove any non-numeric characters except decimal point
        cleaned = ""
        decimal_count = 0
        
        for char in text:
            if char.isdigit():
                cleaned += char
            elif char == "." and decimal_count == 0:
                cleaned += char
                decimal_count += 1
        
        if not cleaned:
            self._set_field_style('neutral')
            return
        
        # If user typed a decimal point, respect it (they know what they want)
        if "." in cleaned:
            parts = cleaned.split(".")
            dollars = parts[0] or "0"  # Handle ".03" case
            cents = parts[1][:2] if len(parts) > 1 else "00"  # Limit to 2 decimals
            
            # Pad cents with zeros if needed (e.g., ".1" → "0.10")
            cents = cents.ljust(2, '0')
            formatted = f"{dollars}.{cents}"
        else:
            # No decimal typed - user meant dollars, not cents
            formatted = f"{cleaned}.00"
        
        # Validate against column max (999,999.99)
        try:
            amount = float(formatted)
            if amount > 999999.99:
                # Truncate to max
                formatted = "999999.99"
                self._set_field_style('warning')
            else:
                self._set_field_style('valid')
        except:
            formatted = "0.00"
            self._set_field_style('error')
        
        self._is_formatting = True
        self.setText(formatted)
        self._is_formatting = False
    
    def get_value(self):
        """Get the numeric value as a string, validated"""
        text = self.text().strip()
        if not text or text == "0.00":
            return "0.00"
        try:
            amount = float(text)
            # Ensure within valid range (0 to 999,999.99)
            amount = max(0, min(999999.99, amount))
            return f"{amount:.2f}"
        except:
            return "0.00"
    
    def setValue(self, value):
        """Set the numeric value (convenience method for QDoubleSpinBox compatibility)"""
        if isinstance(value, (int, float)):
            self.setText(f"{float(value):.2f}")
        else:
            self.setText(str(value))


class AmountSpinBox(QDoubleSpinBox):
    """Custom QDoubleSpinBox that selects all on focus/click for easy replacement"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDecimals(2)
        self.setMaximum(999999.99)
        self.setMinimum(0.00)
        self.setPrefix("$")
        
    def focusInEvent(self, event):
        """Select all text when field gets focus"""
        super().focusInEvent(event)
        self.selectAll()
    
    def mousePressEvent(self, event):
        """Select all on any mouse click"""
        if not self.hasFocus():
            super().mousePressEvent(event)
        self.selectAll()
        event.accept()


class DatabaseConnection:
    """PostgreSQL database connection manager with transaction safety"""
    
    def __init__(self):
        try:
            self.conn = psycopg2.connect(
                host=os.getenv("DB_HOST", "localhost"),
                port=os.getenv("DB_PORT", "5432"),
                database=os.getenv("DB_NAME", "almsdata"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", "***REDACTED***")
            )
            self.conn.autocommit = False
        except psycopg2.Error as e:
            raise Exception(f"Database connection failed: {e}")
    
    def get_cursor(self):
        """Get database cursor"""
        # Auto-recover from aborted transactions to prevent cascade
        try:
            if self.conn.get_transaction_status() == extensions.TRANSACTION_STATUS_INERROR:
                self.conn.rollback()
        except Exception:
            pass
        return self.conn.cursor()
    
    def commit(self):
        """Commit transaction - ALWAYS call this after modifications"""
        self.conn.commit()
    
    def rollback(self):
        """Rollback transaction on error"""
        self.conn.rollback()
    
    def close(self):
        """Close database connection"""
        self.conn.close()


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored hash (pbkdf2_sha256 only).

    Stored format: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
    """
    if not stored_hash or password is None:
        return False

    if not stored_hash.startswith("pbkdf2_sha256$"):
        return False

    try:
        _, iteration_str, salt_hex, hash_hex = stored_hash.split("$", 3)
        iterations = int(iteration_str)
        salt = binascii.unhexlify(salt_hex)
        expected = binascii.unhexlify(hash_hex)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(candidate, expected)
    except Exception:
        return False


# ============================================================================
# GST CALCULATION UTILITIES
# ============================================================================

class GSTCalculator:
    """GST calculation utilities (Alberta 5% GST, tax-included)"""
    
    GST_RATE = 0.05
    
    @staticmethod
    def calculate_gst(gross_amount: float) -> Tuple[float, float]:
        """
        Calculate GST from tax-included amount.
        GST is INCLUDED in the gross amount (not added).
        
        Returns: (gst_amount, net_amount)
        
        Example:
            $682.50 total INCLUDES $32.50 GST
            gst, net = calculate_gst(682.50)  # returns (32.50, 650.00)
        """
        gst_amount = gross_amount * GSTCalculator.GST_RATE / (1 + GSTCalculator.GST_RATE)
        net_amount = gross_amount - gst_amount
        return (round(gst_amount, 2), round(net_amount, 2))
    
    @staticmethod
    def add_gst(net_amount: float) -> float:
        """Calculate gross amount from net (adds GST)"""
        return round(net_amount * (1 + GSTCalculator.GST_RATE), 2)

# ============================================================================
# CHARTER FORM WIDGET
# ============================================================================

class CharterFormWidget(QWidget):
    """
    Main charter/booking form with grouped sections:
    - Customer Information (with auto-fill search)
    - Itinerary/Routing (line-by-line pickup/dropoff)
    - Vehicle & Driver Assignment
    - Invoicing & Charges (with GST calculation)
    - Notes & Special Instructions
    - Status tracking
    
    BUSINESS RULES:
    - reserve_number is read-only (auto-generated)
    - GST is calculated as tax-included
    - All changes must be committed to database
    """
    
    saved = pyqtSignal(int)  # Signal emitted when charter is saved (charter_id)
    
    def __init__(self, db: DatabaseConnection, charter_id: Optional[int] = None):
        super().__init__()
        self.db = db
        self.charter_id = charter_id
        self.charges_data = []  # Track charges for proper calculation
        self.init_ui()
        if charter_id:
            self.load_charter(charter_id)
    
    def init_ui(self):
        """Initialize UI layout"""
        layout = QVBoxLayout()
        
        # ===== QUICK CHARTER LOOKUP (NEW) =====
        from quick_charter_lookup_widget import QuickCharterLookupWidget
        self.quick_lookup = QuickCharterLookupWidget(self.db, self)
        layout.addWidget(self.quick_lookup)
        
        # ===== HEADER WITH ACTION BUTTONS =====
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("<h2>Charter/Booking Form</h2>"))
        header_layout.addStretch()
        
        self.save_btn = QPushButton("💾 Save (Ctrl+S)")
        self.save_btn.clicked.connect(self.save_charter)
        self.save_btn.setShortcut(QKeySequence("Ctrl+S"))
        
        self.new_btn = QPushButton("➕ New Charter (Ctrl+N)")
        self.new_btn.clicked.connect(self.new_charter)
        self.new_btn.setShortcut(QKeySequence("Ctrl+N"))
        
        self.print_btn = QPushButton("🖨️ Print Confirmation (Ctrl+P)")
        self.print_btn.clicked.connect(self.print_confirmation)
        self.print_btn.setShortcut(QKeySequence("Ctrl+P"))
        
        self.print_invoice_btn = QPushButton("📄 Print Invoice")
        self.print_invoice_btn.clicked.connect(self.print_invoice)
        
        # Beverage print buttons
        self.print_dispatch_btn = QPushButton("🍷 Print Dispatch Order")
        self.print_dispatch_btn.clicked.connect(self.print_beverage_dispatch_order)
        
        self.print_guest_invoice_btn = QPushButton("🍷 Print Guest Invoice")
        self.print_guest_invoice_btn.clicked.connect(self.print_beverage_guest_invoice)
        
        self.print_driver_sheet_btn = QPushButton("🍷 Print Driver Sheet")
        self.print_driver_sheet_btn.clicked.connect(self.print_beverage_driver_sheet)
        
        header_layout.addWidget(self.save_btn)
        header_layout.addWidget(self.new_btn)
        header_layout.addWidget(self.print_btn)
        header_layout.addWidget(self.print_invoice_btn)
        header_layout.addWidget(self.print_dispatch_btn)
        header_layout.addWidget(self.print_guest_invoice_btn)
        header_layout.addWidget(self.print_driver_sheet_btn)
        layout.addLayout(header_layout)
        
        # ===== SCROLLABLE FORM AREA =====
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_container = QWidget()
        form_layout = QVBoxLayout()
        
        # ===== GROUP 1: CUSTOMER INFORMATION =====
        customer_group = self.create_customer_section()
        form_layout.addWidget(customer_group)
        
        # ===== GROUP 2: ITINERARY & ROUTING =====
        itinerary_group = self.create_itinerary_section()
        form_layout.addWidget(itinerary_group)
        
        # ===== GROUP 3: VEHICLE & DRIVER ASSIGNMENT =====
        assignment_group = self.create_assignment_section()
        form_layout.addWidget(assignment_group)
        
        # ===== GROUP 4: INVOICING & CHARGES =====
        charges_group = self.create_charges_section()
        form_layout.addWidget(charges_group)
        
        # ===== GROUP 5: NOTES =====
        notes_group = self.create_notes_section()
        form_layout.addWidget(notes_group)
        
        # ===== STATUS & FOOTER =====
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Charter Status:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Quote", "Confirmed", "In Progress", "Completed", "Cancelled"])
        status_layout.addWidget(self.status_combo)
        status_layout.addStretch()
        form_layout.addLayout(status_layout)
        
        form_container.setLayout(form_layout)
        scroll.setWidget(form_container)
        
        # ===== CREATE TABS: BOOKING FORM + BEVERAGE MANAGEMENT =====
        tab_widget = QTabWidget()
        tab_widget.addTab(scroll, "📋 Booking/Charter")
        
        # Add Beverage Management as a tab
        beverage_tab = BeverageManagementWidget(self.db)
        tab_widget.addTab(beverage_tab, "🍷 Beverage Management")
        
        layout.addWidget(tab_widget)
        
        self.setLayout(layout)
    
    def create_customer_section(self) -> QGroupBox:
        """Customer Information section with auto-fill search"""
        customer_group = QGroupBox("Customer Information")
        customer_layout = QFormLayout()
        
        # Reserve number (read-only, auto-generated)
        self.reserve_number = QLineEdit()
        self.reserve_number.setReadOnly(True)
        self.reserve_number.setPlaceholderText("Auto-generated on save")
        customer_layout.addRow("Reserve Number:", self.reserve_number)
        
        # Customer search with auto-fill
        self.customer_search = QLineEdit()
        self.customer_search.setPlaceholderText("Search customer by name or phone... (min 3 chars)")
        self.customer_search.textChanged.connect(self.search_customer)
        customer_layout.addRow("Customer Search:", self.customer_search)
        
        # Customer details
        self.customer_name = QLineEdit()
        self.customer_name.setPlaceholderText("Full name")
        customer_layout.addRow("Customer Name: *", self.customer_name)
        
        self.customer_phone = QLineEdit()
        self.customer_phone.setPlaceholderText("(403) 555-1234")
        customer_layout.addRow("Phone: *", self.customer_phone)
        
        self.customer_email = QLineEdit()
        self.customer_email.setPlaceholderText("email@example.com")
        customer_layout.addRow("Email:", self.customer_email)
        
        self.customer_address = QTextEdit()
        self.customer_address.setMaximumHeight(60)
        self.customer_address.setPlaceholderText("Street address")
        customer_layout.addRow("Address:", self.customer_address)
        
        customer_group.setLayout(customer_layout)
        return customer_group
    
    def create_itinerary_section(self) -> QGroupBox:
        """Itinerary & Routing section with line-by-line pickup/dropoff"""
        itinerary_group = QGroupBox("Itinerary & Routing")
        itinerary_layout = QVBoxLayout()
        
        # Route table
        routing_header = QHBoxLayout()
        routing_header.addWidget(QLabel("<b>Route Lines (Pickup/Dropoff Locations)</b>"))
        add_route_btn = QPushButton("+ Add Route Line")
        add_route_btn.clicked.connect(self.add_route_line)
        routing_header.addWidget(add_route_btn)
        itinerary_layout.addLayout(routing_header)
        
        self.route_table = QTableWidget()
        self.route_table.setColumnCount(6)
        self.route_table.setHorizontalHeaderLabels([
            "Order", "Pickup Location", "Pickup Time", "Dropoff Location", "Dropoff Time", "Notes"
        ])
        self.route_table.setMinimumHeight(150)
        self.route_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        itinerary_layout.addWidget(self.route_table)
        
        # Charter date, pickup time, passengers
        route_dates = QHBoxLayout()
        
        route_dates.addWidget(QLabel("Charter Date: *"))
        self.charter_date = DateInput()  # Use standardized DateInput
        route_dates.addWidget(self.charter_date)
        
        route_dates.addWidget(QLabel("Pickup Time: *"))
        self.pickup_time = QLineEdit()
        self.pickup_time.setPlaceholderText("HH:MM AM/PM")
        route_dates.addWidget(self.pickup_time)
        
        route_dates.addWidget(QLabel("# Passengers: *"))
        self.num_passengers = QSpinBox()
        self.num_passengers.setMinimum(1)
        self.num_passengers.setMaximum(100)
        self.num_passengers.setValue(1)
        route_dates.addWidget(self.num_passengers)
        
        route_dates.addStretch()
        itinerary_layout.addLayout(route_dates)
        
        itinerary_group.setLayout(itinerary_layout)
        return itinerary_group
    
    def create_assignment_section(self) -> QGroupBox:
        """Vehicle & Driver Assignment section"""
        assignment_group = QGroupBox("Vehicle & Driver Assignment")
        assignment_layout = QFormLayout()
        
        self.vehicle_combo = QComboBox()
        self.load_vehicles()
        assignment_layout.addRow("Vehicle: *", self.vehicle_combo)
        
        self.driver_combo = QComboBox()
        self.load_drivers()
        assignment_layout.addRow("Driver: *", self.driver_combo)
        
        assignment_group.setLayout(assignment_layout)
        return assignment_group
    
    def create_charges_section(self) -> QGroupBox:
        """Invoicing & Charges section with GST calculation"""
        charges_group = QGroupBox("Invoicing & Charges (GST-Included)")
        charges_layout = QVBoxLayout()
        
        # Charges table
        charges_header = QHBoxLayout()
        charges_header.addWidget(QLabel("<b>Charge Lines</b>"))
        
        add_charge_btn = QPushButton("+ Add Charge Line")
        add_charge_btn.clicked.connect(self.add_charge_line)
        charges_header.addWidget(add_charge_btn)
        
        beverage_btn = QPushButton("🍷 Add Beverage Items")
        beverage_btn.clicked.connect(self.open_beverage_lookup)
        charges_header.addWidget(beverage_btn)
        
        charges_header.addStretch()
        charges_layout.addLayout(charges_header)
        
        self.charges_table = QTableWidget()
        self.charges_table.setColumnCount(5)
        self.charges_table.setHorizontalHeaderLabels([
            "Description", "Quantity", "Unit Price (Net)", "Gross (inc GST)", "Total (Gross)"
        ])
        self.charges_table.setMinimumHeight(150)
        self.charges_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.charges_table.itemChanged.connect(self.recalculate_totals)
        charges_layout.addWidget(self.charges_table)
        
        # Totals display (GST-included)
        totals_layout = QFormLayout()
        self.net_total = QLabel("$0.00")
        self.gst_total = QLabel("$0.00")
        self.gross_total = QLabel("$0.00")
        self.gross_total.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        
        totals_layout.addRow("Net Total:", self.net_total)
        totals_layout.addRow("GST (5% included):", self.gst_total)
        totals_layout.addRow("Gross Total (inc GST):", self.gross_total)
        charges_layout.addLayout(totals_layout)
        
        charges_group.setLayout(charges_layout)
        return charges_group
    
    def create_notes_section(self) -> QGroupBox:
        """Notes & Special Instructions section"""
        notes_group = QGroupBox("Notes & Special Instructions")
        notes_layout = QVBoxLayout()
        self.notes_field = QTextEdit()
        self.notes_field.setPlaceholderText("Enter special instructions, flight info, restrictions, etc.")
        self.notes_field.setMaximumHeight(80)
        notes_layout.addWidget(self.notes_field)
        notes_group.setLayout(notes_layout)
        return notes_group
    
    def load_vehicles(self):
        """Load active vehicles from database"""
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT vehicle_id, COALESCE(unit_number, 'Vehicle ' || vehicle_id) as nickname, COALESCE(license_plate, '') as license_plate
                FROM vehicles 
                WHERE status = 'active' OR status IS NULL
                ORDER BY unit_number
            """)
            for row in cur.fetchall():
                self.vehicle_combo.addItem(f"{row[1]} ({row[2]})", row[0])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load vehicles: {e}")
    
    def load_drivers(self):
        """Load active drivers from database"""
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT employee_id, first_name, last_name 
                FROM employees 
                WHERE employment_status = 'active' AND is_chauffeur = true
                ORDER BY last_name
            """)
            for row in cur.fetchall():
                self.driver_combo.addItem(f"{row[1]} {row[2]}", row[0])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load drivers: {e}")
    
    def add_route_line(self):
        """Add new route line to table"""
        row = self.route_table.rowCount()
        self.route_table.insertRow(row)
        self.route_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
    
    def add_charge_line(self):
        """Add new charge line with default values"""
        row = self.charges_table.rowCount()
        self.charges_table.insertRow(row)
        # Default values
        self.charges_table.setItem(row, 0, QTableWidgetItem("New Charge"))
        self.charges_table.setItem(row, 1, QTableWidgetItem("1"))
        self.charges_table.setItem(row, 2, QTableWidgetItem("0.00"))
        self.charges_table.setItem(row, 3, QTableWidgetItem("0.00"))
        self.charges_table.setItem(row, 4, QTableWidgetItem("0.00"))
    
    def recalculate_totals(self):
        """
        Recalculate invoice totals when charges change.
        
        BUSINESS RULE: GST is INCLUDED in gross amounts
        Net is what we charge before tax, Gross includes tax
        """
        net_total = 0.0
        
        # Sum all charge lines
        for row in range(self.charges_table.rowCount()):
            try:
                qty_item = self.charges_table.item(row, 1)
                price_item = self.charges_table.item(row, 2)
                
                qty = float(qty_item.text()) if qty_item else 1.0
                net_price = float(price_item.text()) if price_item else 0.0
                
                line_net = qty * net_price
                line_gross = GSTCalculator.add_gst(line_net)
                
                net_total += line_net
                
                # Update gross column
                self.charges_table.setItem(row, 3, QTableWidgetItem(f"${line_gross:.2f}"))
                self.charges_table.setItem(row, 4, QTableWidgetItem(f"${line_gross:.2f}"))
                
            except (ValueError, AttributeError):
                pass
        
        # Calculate totals
        gross_total = GSTCalculator.add_gst(net_total)
        gst_amount = gross_total - net_total
        
        self.net_total.setText(f"${net_total:,.2f}")
        self.gst_total.setText(f"${gst_amount:,.2f}")
        self.gross_total.setText(f"${gross_total:,.2f}")
    
    def search_customer(self, text: str):
        """
        Auto-fill customer data from search (minimum 3 characters).
        Uses customer_name ILIKE for partial matching.
        """
        if len(text) < 3:
            return
        
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT customer_id, customer_name, phone, email, address 
                FROM customers 
                WHERE customer_name ILIKE %s OR phone ILIKE %s 
                LIMIT 10
            """, (f"%{text}%", f"%{text}%"))
            
            results = cur.fetchall()
            if results:
                # Auto-fill first match
                customer = results[0]
                self.customer_name.setText(str(customer[1] or ""))
                self.customer_phone.setText(str(customer[2] or ""))
                self.customer_email.setText(str(customer[3] or ""))
                self.customer_address.setText(str(customer[4] or ""))
        except Exception as e:
            pass  # Silently fail on search
    
    def save_charter(self):
        """
        Save charter to database with validation.
        
        BUSINESS RULES:
        - reserve_number is auto-generated on insert
        - Customer name and phone are required
        - Must commit after insert/update
        """
        # Validation
        if not self.customer_name.text().strip():
            QMessageBox.warning(self, "Validation Error", "Customer name is required")
            self.customer_name.setFocus()
            return
        
        if not self.customer_phone.text().strip():
            QMessageBox.warning(self, "Validation Error", "Customer phone is required")
            self.customer_phone.setFocus()
            return
        
        if not self.pickup_time.text().strip():
            QMessageBox.warning(self, "Validation Error", "Pickup time is required")
            self.pickup_time.setFocus()
            return
        
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            
            if self.charter_id:
                # ===== UPDATE EXISTING =====
                cur.execute("""
                    UPDATE charters 
                    SET customer_name = %s, 
                        phone = %s, 
                        email = %s, 
                        charter_date = %s, 
                        pickup_time = %s, 
                        num_passengers = %s, 
                        notes = %s, 
                        status = %s,
                        updated_at = NOW()
                    WHERE charter_id = %s
                """, (
                    self.customer_name.text().strip(),
                    self.customer_phone.text().strip(),
                    self.customer_email.text().strip(),
                    self.charter_date.getDate().toPyDate(),
                    self.pickup_time.text().strip(),
                    self.num_passengers.value(),
                    self.notes_field.toPlainText(),
                    self.status_combo.currentText(),
                    self.charter_id
                ))
                # ✨ SAVE ROUTES & CHARGES ✨
                self.save_charter_routes(cur)
                self.save_charter_charges(cur)
                self.db.commit()
                
                QMessageBox.information(self, "Success", f"Charter #{self.charter_id} updated successfully")
                
            else:
                # ===== CREATE NEW (WITH RESERVE_NUMBER AUTO-GENERATION) =====
                cur.execute("""
                    INSERT INTO charters (
                        customer_name, phone, email, charter_date, 
                        pickup_time, num_passengers, notes, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING charter_id, reserve_number
                """, (
                    self.customer_name.text().strip(),
                    self.customer_phone.text().strip(),
                    self.customer_email.text().strip(),
                    self.charter_date.getDate().toPyDate(),
                    self.pickup_time.text().strip(),
                    self.num_passengers.value(),
                    self.notes_field.toPlainText(),
                    self.status_combo.currentText()
                ))
                
                result = cur.fetchone()
                self.charter_id = result[0]
                reserve_num = result[1]
                
                # ✨ SAVE ROUTES & CHARGES ✨
                self.save_charter_routes(cur)
                self.save_charter_charges(cur)
                self.db.commit()
                
                self.reserve_number.setText(str(reserve_num))
                QMessageBox.information(
                    self, "Success", 
                    f"New charter created!\n\nReserve #: {reserve_num}\nCharter ID: {self.charter_id}"
                )
            
            self.saved.emit(self.charter_id)
            
        except psycopg2.Error as e:
            self.db.rollback()
            QMessageBox.critical(self, "Database Error", f"Failed to save charter:\n\n{e.diag.message_primary if hasattr(e, 'diag') else str(e)}")
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save charter:\n\n{str(e)}")
    
    def load_charter_by_id(self, charter_id: int):
        """Convenience method for loading charter from lookup widgets"""
        self.charter_id = charter_id
        self.load_charter(charter_id)
    
    def load_charter(self, charter_id: int):
        """Load existing charter data from database"""
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT reserve_number, customer_name, phone, email, charter_date,
                       pickup_time, num_passengers, notes, status
                FROM charters 
                WHERE charter_id = %s
            """, (charter_id,))
            
            row = cur.fetchone()
            if row:
                self.reserve_number.setText(str(row[0] or ""))
                self.customer_name.setText(str(row[1] or ""))
                self.customer_phone.setText(str(row[2] or ""))
                self.customer_email.setText(str(row[3] or ""))
                if row[4]:
                    self.charter_date.setDate(QDate(row[4]))
                self.pickup_time.setText(str(row[5] or ""))
                self.num_passengers.setValue(int(row[6] or 1))
                self.notes_field.setText(str(row[7] or ""))
                if row[8]:
                    self.status_combo.setCurrentText(row[8])
                
                # ✨ LOAD ROUTES & CHARGES & BEVERAGES ✨
                self.load_charter_routes(charter_id, cur)
                self.load_charter_charges(charter_id, cur)
                self.load_charter_beverages(charter_id, cur)  # 🍷 NEW: Load saved beverages
                
        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
            QMessageBox.warning(self, "Error", f"Failed to load charter: {e}")
    
    def new_charter(self):
        """Clear form for new charter entry"""
        response = QMessageBox.question(
            self, "New Charter",
            "Clear form for new charter entry?\n(Any unsaved changes will be lost)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if response == QMessageBox.StandardButton.Yes:
            self.charter_id = None
            self.reserve_number.setText("")
            self.customer_search.setText("")
            self.customer_name.setText("")
            self.customer_phone.setText("")
            self.customer_email.setText("")
            self.customer_address.setText("")
            self.charter_date.setDate(QDate.currentDate())
            self.pickup_time.setText("")
            self.num_passengers.setValue(1)
            self.notes_field.setText("")
            self.status_combo.setCurrentText("Quote")
            self.route_table.setRowCount(0)
            self.charges_table.setRowCount(0)
            self.net_total.setText("$0.00")
            self.gst_total.setText("$0.00")
            self.gross_total.setText("$0.00")
            self.customer_name.setFocus()
    
    def print_confirmation(self):
        """
        Print charter confirmation form (pre-charter document for customer)
        Shows booking summary, route, timing, special requirements
        """
        if not self.charter_id:
            QMessageBox.warning(self, "Warning", "Please save charter first")
            return
        
        try:
            text = "═" * 80 + "\n"
            text += "CHARTER CONFIRMATION FORM\n"
            text += "Arrow Limousine Service\n"
            text += "═" * 80 + "\n\n"
            
            text += "BOOKING REFERENCE & TIMELINE\n"
            text += "─" * 80 + "\n"
            text += f"Charter ID: {self.charter_id}\n"
            text += f"Booking Date: {datetime.now().strftime('%B %d, %Y')}\n"
            text += f"Service Date: {self.charter_date.text()}\n"
            text += f"Pickup Time: {self.pickup_time.text()}\n\n"
            
            text += "CUSTOMER INFORMATION\n"
            text += "─" * 80 + "\n"
            text += f"Name: {self.customer_name.text()}\n"
            text += f"Phone: {self.customer_phone.text()}\n"
            text += f"Email: {self.customer_email.text()}\n"
            text += f"Passengers: {self.num_passengers.value()}\n\n"
            
            text += "SERVICE DETAILS\n"
            text += "─" * 80 + "\n"
            text += f"Pickup Location: {self.pickup_time.text() or 'TBD'}\n"
            text += f"Dropoff Location: TBD\n"
            text += f"Driver: {self.driver_combo.currentText() or 'To be assigned'}\n"
            text += f"Vehicle: {self.vehicle_combo.currentText() or 'To be assigned'}\n\n"
            
            text += "SPECIAL REQUESTS & REQUIREMENTS\n"
            text += "─" * 80 + "\n"
            text += f"{self.notes_field.toPlainText() or 'None noted'}\n\n"
            
            text += "ESTIMATED CHARGES\n"
            text += "─" * 80 + "\n"
            text += "Charges (pending final calculation):\n"
            for row in range(self.charges_table.rowCount()):
                desc = self.charges_table.item(row, 0)
                amt = self.charges_table.item(row, 3)
                if desc and amt:
                    text += f"  • {desc.text():<50} {amt.text()}\n"
            
            text += "\n═" * 80 + "\n"
            text += "CONFIRMATION CHECKLIST\n"
            text += "─" * 80 + "\n"
            text += "☐ Customer contact information verified\n"
            text += "☐ Pickup/dropoff locations confirmed\n"
            text += "☐ Special requirements documented\n"
            text += "☐ Vehicle type appropriate for group size\n"
            text += "☐ Driver assigned and briefed\n"
            text += "☐ Weather conditions reviewed\n"
            text += "☐ Payment method confirmed\n\n"
            
            text += "CUSTOMER ACKNOWLEDGMENT\n"
            text += "─" * 80 + "\n"
            text += "By booking this charter, you confirm:\n"
            text += "• Passenger count is accurate\n"
            text += "• Pickup/dropoff locations are correct\n"
            text += "• You understand cancellation policy\n"
            text += "• Contact information is valid\n\n"
            text += f"Customer Signature: _______________________  Date: __________\n"
            text += f"Company Representative: ___________________  Date: __________\n"
            text += "═" * 80 + "\n"
            
            self.show_print_dialog("Charter Confirmation", text)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate confirmation: {e}")
    
    def print_invoice(self):
        """
        Print final charter invoice with all charges and beverages
        Shows itemized list, payments, balance due, terms
        """
        if not self.charter_id:
            QMessageBox.warning(self, "Warning", "Please save charter first")
            return
        
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            
            # Get charter details
            cur.execute("""
                SELECT charter_id, reserve_number, client_display_name, phone, email,
                       charter_date, pickup_time, total_amount_due, paid_amount, payment_status
                FROM charters WHERE charter_id = %s
            """, (self.charter_id,))
            
            charter_data = cur.fetchone()
            if not charter_data:
                QMessageBox.warning(self, "Error", "Charter data not found")
                return
            
            charter_id, reserve, customer, phone, email, charter_date, pickup_time, total_due, paid, pay_status = charter_data
            
            text = "═" * 90 + "\n"
            text += " " * 30 + "CHARTER INVOICE\n"
            text += " " * 25 + "Arrow Limousine Service\n"
            text += "═" * 90 + "\n\n"
            
            text += "INVOICE INFORMATION\n"
            text += "─" * 90 + "\n"
            text += f"Invoice #: {charter_id:06d}   Reserve #: {reserve}\n"
            text += f"Invoice Date: {datetime.now().strftime('%B %d, %Y')}\n"
            text += f"Service Date: {charter_date}\n"
            text += f"Pickup Time: {pickup_time}\n\n"
            
            text += "CUSTOMER INFORMATION\n"
            text += "─" * 90 + "\n"
            text += f"Name: {customer}\n"
            text += f"Phone: {phone}\n"
            text += f"Email: {email}\n"
            text += f"Passengers: {self.num_passengers.value()}\n\n"
            
            text += "SERVICE & BEVERAGE CHARGES\n"
            text += "─" * 90 + "\n"
            text += f"{'Description':<60} {'Qty':<6} {'Amount':>20}\n"
            text += "─" * 90 + "\n"
            
            grand_total = 0.0
            
            # Charter charges (services)
            for row in range(self.charges_table.rowCount()):
                desc_item = self.charges_table.item(row, 0)
                qty_item = self.charges_table.item(row, 1)
                amt_item = self.charges_table.item(row, 3)
                
                if desc_item and amt_item:
                    desc = desc_item.text()
                    qty = qty_item.text() if qty_item else "1"
                    amt_text = amt_item.text()
                    try:
                        amt = float(amt_text.replace("$", ""))
                        grand_total += amt
                        text += f"{desc:<60} {qty:<6} ${amt:>18.2f}\n"
                    except ValueError:
                        pass
            
            # Beverage charges (from charter_beverages)
            cur.execute("""
                SELECT item_name, quantity, line_amount_charged
                FROM charter_beverages
                WHERE charter_id = %s
                ORDER BY created_at
            """, (self.charter_id,))
            
            beverages = cur.fetchall()
            if beverages:
                text += "\nBeverages:\n"
                for item_name, qty, line_amt in beverages:
                    line_amt = float(line_amt)
                    grand_total += line_amt
                    text += f"  {item_name:<56} {qty:<6} ${line_amt:>18.2f}\n"
            
            text += "─" * 90 + "\n"
            
            # Calculate GST (5% included in prices)
            gst_amount = grand_total * 0.05 / 1.05
            subtotal = grand_total - gst_amount
            
            text += f"{'Subtotal (before GST)':<60} {'':6} ${subtotal:>18.2f}\n"
            text += f"{'GST (5% included)':<60} {'':6} ${gst_amount:>18.2f}\n"
            text += "═" * 90 + "\n"
            text += f"{'TOTAL CHARGES':<60} {'':6} ${grand_total:>18.2f}\n"
            text += "═" * 90 + "\n\n"
            
            # Payment information
            text += "PAYMENT INFORMATION\n"
            text += "─" * 90 + "\n"
            balance = (grand_total or 0) - (paid or 0)
            text += f"Total Due:        ${grand_total:.2f}\n"
            text += f"Paid Amount:      ${paid or 0:.2f}\n"
            text += f"Balance Due:      ${balance:.2f}\n"
            text += f"Payment Status:   {pay_status or 'Pending'}\n\n"
            
            text += "PAYMENT TERMS\n"
            text += "─" * 90 + "\n"
            text += "• Payment is due upon completion of service\n"
            text += "• Accepted methods: Cash, Check, Credit Card, Bank Transfer\n"
            text += "• Late payment may result in service holds on future bookings\n"
            text += "• Cancellations must be made 24 hours in advance for refund\n\n"
            
            text += "THANK YOU FOR YOUR BUSINESS!\n"
            text += "For questions, contact: info@arrowlimo.ca or (780) 555-1234\n"
            text += "═" * 90 + "\n"
            
            self.show_print_dialog("Charter Invoice", text)
            cur.close()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate invoice: {e}")
    
    def open_beverage_lookup(self):
        """Open beverage selection dialog for adding beverages to charter"""
        if not self.charter_id:
            QMessageBox.warning(self, "Warning", "Please save charter first before adding beverages")
            return
        
        dialog = BeverageSelectionDialog(self.db, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            totals = dialog.get_cart_totals()
            if totals["items"]:
                self.save_beverages_to_charter(totals)
    
    def save_beverages_to_charter(self, totals):
        """Save selected beverages as SNAPSHOTS to charter_beverages table"""
        if not self.charter_id or not totals["items"]:
            return
        
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            
            # Save each beverage as a snapshot (prices locked, not linked to master list)
            for item in totals["items"]:
                # Get beverage_item_id if available
                beverage_item_id = item.get("id")
                
                # Calculate unit prices (need to reverse from item totals)
                unit_price_charged = item["charged_price"]
                unit_our_cost = item["our_cost"]
                deposit_per_unit = item.get("deposit_amount", 0) or 0
                
                # Insert into charter_beverages (SNAPSHOT TABLE)
                cur.execute("""
                    INSERT INTO charter_beverages 
                    (charter_id, beverage_item_id, item_name, quantity, 
                     unit_price_charged, unit_our_cost, deposit_per_unit, notes, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """, (
                    self.charter_id,
                    beverage_item_id,
                    item["name"],
                    item["quantity"],
                    unit_price_charged,
                    unit_our_cost,
                    deposit_per_unit,
                    "Added via beverage selection dialog"
                ))
                
                # Also add to charter_charges for backwards compatibility
                cur.execute("""
                    INSERT INTO charter_charges 
                    (charter_id, charge_type, charge_description, quantity, charge_amount)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    self.charter_id,
                    'beverage',
                    item["name"],
                    item["quantity"],
                    item["item_charged"]
                ))
            
            self.db.conn.commit()
            
            # Add charge lines to UI
            for item in totals["items"]:
                row = self.charges_table.rowCount()
                self.charges_table.insertRow(row)
                self.charges_table.setItem(row, 0, QTableWidgetItem(item["name"]))
                self.charges_table.setItem(row, 1, QTableWidgetItem(str(item["quantity"])))
                self.charges_table.setItem(row, 2, QTableWidgetItem(f"${item['our_cost']:.2f}"))
                self.charges_table.setItem(row, 3, QTableWidgetItem(f"${item['charged_price']:.2f}"))
                self.charges_table.setItem(row, 4, QTableWidgetItem(f"${item['item_charged']:.2f}"))
            
            self.recalculate_totals()
            QMessageBox.information(self, "Success", f"✅ Added {len(totals['items'])} beverage items to charter")
            
        except Exception as e:
            self.db.conn.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save beverages: {e}")
    
    def print_beverage_dispatch_order(self):
        """
        Print dispatch copy with OUR COSTS (internal, for buying)
        Includes itemization and checkboxes for vehicle load verification
        Uses charter_beverages SNAPSHOT (locked prices)
        """
        if not self.charter_id:
            QMessageBox.warning(self, "Warning", "Please save charter first")
            return
        
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT item_name, quantity, unit_our_cost, line_cost
                FROM charter_beverages
                WHERE charter_id = %s
                ORDER BY item_name
            """, (self.charter_id,))
            
            items = cur.fetchall()
            if not items:
                QMessageBox.warning(self, "No Beverages", "No beverage items in this charter")
                return
            
            # Build dispatch order text
            text = "═" * 70 + "\n"
            text += "🍷 BEVERAGE DISPATCH ORDER (INTERNAL - OUR COSTS)\n"
            text += "═" * 70 + "\n\n"
            text += f"Charter ID: {self.charter_id}\n"
            text += f"Reserve Number: {self.reserve_number.text()}\n"
            text += f"Customer: {self.customer_name.text()}\n"
            text += f"Date: {datetime.now().strftime('%m/%d/%Y %H:%M')}\n"
            text += f"Driver: {self.driver_combo.currentText()}\n"
            text += f"Vehicle: {self.vehicle_combo.currentText()}\n\n"
            
            text += "ITEMS TO PURCHASE (Our Wholesale Costs - SNAPSHOT)\n"
            text += "─" * 70 + "\n"
            text += f"{'☐':<2} {'Item':<40} {'Qty':<6} {'Cost Each':<12} {'Total':<10}\n"
            text += "─" * 70 + "\n"
            
            total_cost = 0
            for item_name, qty, unit_cost, line_cost in items:
                total_cost += line_cost
                text += f"☐  {item_name:<37} {qty:<6} ${unit_cost:<11.2f} ${line_cost:<9.2f}\n"
            
            text += "─" * 70 + "\n"
            text += f"TOTAL COST TO PURCHASE: ${total_cost:.2f}\n"
            text += "═" * 70 + "\n"
            text += "\nVERIFICATION AT VEHICLE LOAD:\n"
            text += "─" * 70 + "\n"
            for i, (item_name, qty, _, _) in enumerate(items, 1):
                text += f"☐ {i}. {item_name:<50} Qty: {qty} ✓ Loaded\n"
            
            text += "\n" + "─" * 70 + "\n"
            text += "Driver Signature: ________________  Date: ________  Time: ________\n"
            text += "═" * 70 + "\n"
            text += "\nNote: Prices locked from charter creation. Edits to quantities/prices\n"
            text += "are reflected in this cart but do NOT affect master beverage_products.\n"
            
            # Display in dialog
            self.show_print_dialog("Beverage Dispatch Order (Internal)", text)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate dispatch order: {e}")
    
    def print_beverage_guest_invoice(self):
        """
        Print guest invoice - ONLY guest prices, NO internal costs
        Shows itemized list and total to collect
        Uses charter_beverages SNAPSHOT (locked prices)
        """
        if not self.charter_id:
            QMessageBox.warning(self, "Warning", "Please save charter first")
            return
        
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT item_name, quantity, unit_price_charged, line_amount_charged, deposit_per_unit
                FROM charter_beverages
                WHERE charter_id = %s
                ORDER BY item_name
            """, (self.charter_id,))
            
            items = cur.fetchall()
            if not items:
                QMessageBox.warning(self, "No Beverages", "No beverage items in this charter")
                return
            
            # Build guest invoice
            text = "═" * 70 + "\n"
            text += "🍷 BEVERAGE INVOICE (GUEST COPY)\n"
            text += "═" * 70 + "\n\n"
            text += f"Charter ID: {self.charter_id}\n"
            text += f"Reserve Number: {self.reserve_number.text()}\n"
            text += f"Customer: {self.customer_name.text()}\n"
            text += f"Date: {datetime.now().strftime('%m/%d/%Y %H:%M')}\n\n"
            
            text += "BEVERAGES PROVIDED (SNAPSHOT PRICES)\n"
            text += "─" * 70 + "\n"
            text += f"{'Item':<45} {'Qty':<6} {'Price Each':<10} {'Total':<10}\n"
            text += "─" * 70 + "\n"
            
            subtotal = 0
            gst_total = 0
            for item_name, qty, unit_price, line_amount, deposit in items:
                subtotal += line_amount
                gst_portion = line_amount * 0.05 / 1.05
                gst_total += gst_portion
                
                text += f"{item_name:<45} {qty:<6} ${unit_price:<9.2f} ${line_amount:<9.2f}\n"
            
            text += "─" * 70 + "\n"
            text += f"Subtotal (before GST):            ${(subtotal - gst_total):<35.2f}\n"
            text += f"GST (5% included):                ${gst_total:<35.2f}\n"
            text += "═" * 70 + "\n"
            text += f"TOTAL DUE FROM GUEST:             ${subtotal:<35.2f}\n"
            text += "═" * 70 + "\n"
            text += "\nPrices locked at time of charter creation.\n"
            text += "For historical accuracy and dispute resolution.\n"
            
            # Display
            self.show_print_dialog("Beverage Guest Invoice", text)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate guest invoice: {e}")
    
    def print_beverage_driver_sheet(self):
        """
        Print driver verification sheet
        Includes checkboxes for each item, signature line
        Uses charter_beverages SNAPSHOT
        """
        if not self.charter_id:
            QMessageBox.warning(self, "Warning", "Please save charter first")
            return
        
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT item_name, quantity
                FROM charter_beverages
                WHERE charter_id = %s
                ORDER BY item_name
            """, (self.charter_id,))
            
            items = cur.fetchall()
            if not items:
                QMessageBox.warning(self, "No Beverages", "No beverage items in this charter")
                return
            
            # Build driver sheet
            text = "═" * 70 + "\n"
            text += "🍷 DRIVER BEVERAGE VERIFICATION SHEET\n"
            text += "═" * 70 + "\n\n"
            text += f"Charter ID: {self.charter_id}\n"
            text += f"Reserve Number: {self.reserve_number.text()}\n"
            text += f"Customer: {self.customer_name.text()}\n"
            text += f"Driver: {self.driver_combo.currentText()}\n"
            text += f"Vehicle: {self.vehicle_combo.currentText()}\n"
            text += f"Date: {datetime.now().strftime('%m/%d/%Y')}\n\n"
            
            text += "BEVERAGE LOAD VERIFICATION (SNAPSHOT)\n"
            text += "Check off each item as it is loaded into the vehicle\n"
            text += "─" * 70 + "\n\n"
            
            for i, (item_name, qty) in enumerate(items, 1):
                text += f"☐ {i}. {item_name:<50}\n"
                text += f"   Quantity: {qty} units\n"
                text += f"   ✓ Verified at load time: ________  Initials: ____\n\n"
            
            text += "═" * 70 + "\n"
            text += "DRIVER ACKNOWLEDGMENT\n"
            text += "─" * 70 + "\n"
            text += "I confirm that all beverage items listed above have been loaded\n"
            text += "into the vehicle and are ready for delivery.\n\n"
            text += f"Driver Name (Print): _________________________________\n"
            text += f"Driver Signature: ____________________________________\n"
            text += f"Date: ____________________  Time: ____________________\n\n"
            text += "Temperature Check (if perishable): ____°C\n"
            text += "═" * 70 + "\n"
            
            # Display
            self.show_print_dialog("Driver Beverage Verification Sheet", text)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate driver sheet: {e}")
    
    def show_print_dialog(self, title, text):
        """Display print preview in dialog with copy/print options"""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"🖨️ {title}")
        dialog.setGeometry(50, 50, 800, 600)
        layout = QVBoxLayout()
        
        # Preview text
        text_edit = QTextEdit()
        text_edit.setText(text)
        text_edit.setFont(QFont("Courier New", 9))
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        copy_btn = QPushButton("📋 Copy to Clipboard")
        copy_btn.clicked.connect(lambda: self.copy_to_clipboard(text))
        button_layout.addWidget(copy_btn)
        
        print_btn = QPushButton("🖨️ Print")
        print_btn.clicked.connect(lambda: self.print_text(title, text))
        button_layout.addWidget(print_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec()
    
    def copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        from PyQt6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text)
        QMessageBox.information(self, "Copied", "✅ Text copied to clipboard")
    
    def print_text(self, title, text):
        """Print text to printer"""
        from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
        
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                from PyQt6.QtGui import QTextDocument
                doc = QTextDocument()
                doc.setPlainText(text)
                doc.print(printer)
                QMessageBox.information(self, "Success", "✅ Sent to printer")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Print failed: {e}")

    def save_charter_routes(self, cur):
        """
        Save all route lines from UI to charter_routes table.
        CRITICAL: Without this, route data is LOST!
        """
        if not self.charter_id:
            return  # Can't save routes without charter_id

        try:
            # Delete existing routes for this charter
            cur.execute("DELETE FROM charter_routes WHERE charter_id = %s", (self.charter_id,))

            # Insert all routes from UI table
            for row_idx in range(self.route_table.rowCount()):
                # Fallback: read from item() if cellWidget() missing
                def _read_cell_text(table, r, c):
                    w = table.cellWidget(r, c)
                    if w and hasattr(w, 'text'):
                        return w.text()
                    itm = table.item(r, c)
                    return itm.text() if itm else ""

                pickup_loc = _read_cell_text(self.route_table, row_idx, 0)
                pickup_time = _read_cell_text(self.route_table, row_idx, 1)
                dropoff_loc = _read_cell_text(self.route_table, row_idx, 2)
                dropoff_time = _read_cell_text(self.route_table, row_idx, 3)

                cur.execute(
                    """
                    INSERT INTO charter_routes 
                    (charter_id, sequence_order, pickup_location, pickup_time, dropoff_location, dropoff_time)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (self.charter_id, row_idx + 1, pickup_loc, pickup_time, dropoff_loc, dropoff_time)
                )

            print(f"✅ Saved {self.route_table.rowCount()} routes for charter {self.charter_id}")
        except Exception as e:
            print(f"❌ Error saving routes: {e}")
            raise

    def save_charter_charges(self, cur):
        """
        Save all charge lines from UI to charter_charges table.
        CRITICAL: Without this, billing data is LOST!
        """
        if not self.charter_id:
            return  # Can't save charges without charter_id

        try:
            # Delete existing charges for this charter
            cur.execute("DELETE FROM charter_charges WHERE charter_id = %s", (self.charter_id,))

            # Insert all charges from UI table
            for row_idx in range(self.charges_table.rowCount()):
                # Read description with fallback
                desc_widget = self.charges_table.cellWidget(row_idx, 0)
                description = desc_widget.text() if desc_widget and hasattr(desc_widget, 'text') else (
                    self.charges_table.item(row_idx, 0).text() if self.charges_table.item(row_idx, 0) else ""
                )

                # Quantity may be a spinbox or plain text/item
                qty_widget = self.charges_table.cellWidget(row_idx, 1)
                if qty_widget and hasattr(qty_widget, 'value'):
                    quantity = int(qty_widget.value())
                else:
                    qty_item = self.charges_table.item(row_idx, 1)
                    try:
                        quantity = int(qty_item.text()) if qty_item else 1
                    except Exception:
                        quantity = 1

                # Amount may be an input or item; normalize currency
                amt_widget = self.charges_table.cellWidget(row_idx, 2)
                amt_text = None
                if amt_widget and hasattr(amt_widget, 'text'):
                    amt_text = amt_widget.text()
                else:
                    amt_item = self.charges_table.item(row_idx, 2)
                    amt_text = amt_item.text() if amt_item else None

                try:
                    amount = float((amt_text or "0").replace('$', '').replace(',', '').strip())
                except Exception:
                    amount = 0.0

                cur.execute(
                    """
                    INSERT INTO charter_charges 
                    (charter_id, line_item_order, description, quantity, unit_price, total_amount)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (self.charter_id, row_idx + 1, description, quantity, amount, amount * quantity)
                )

            print(f"✅ Saved {self.charges_table.rowCount()} charges for charter {self.charter_id}")
        except Exception as e:
            print(f"❌ Error saving charges: {e}")
            raise

    def load_charter_routes(self, charter_id: int, cur):
        """Load routes from charter_routes table into UI"""
        try:
            cur.execute(
                """
                SELECT pickup_location, pickup_time, dropoff_location, dropoff_time
                FROM charter_routes
                WHERE charter_id = %s
                ORDER BY sequence_order
                """,
                (charter_id,)
            )

            self.route_table.setRowCount(0)
            for row in cur.fetchall():
                self.add_route_line()
                row_idx = self.route_table.rowCount() - 1

                if self.route_table.cellWidget(row_idx, 0):
                    self.route_table.cellWidget(row_idx, 0).setText(row[0] or "")
                if self.route_table.cellWidget(row_idx, 1):
                    self.route_table.cellWidget(row_idx, 1).setText(row[1] or "")
                if self.route_table.cellWidget(row_idx, 2):
                    self.route_table.cellWidget(row_idx, 2).setText(row[2] or "")
                if self.route_table.cellWidget(row_idx, 3):
                    self.route_table.cellWidget(row_idx, 3).setText(row[3] or "")

            print(f"✅ Loaded {self.route_table.rowCount()} routes")
        except Exception as e:
            print(f"❌ Error loading routes: {e}")

    def load_charter_charges(self, charter_id: int, cur):
        """Load charges from charter_charges table into UI"""
        try:
            cur.execute(
                """
                SELECT description, quantity, unit_price, total_amount
                FROM charter_charges
                WHERE charter_id = %s
                ORDER BY line_item_order
                """,
                (charter_id,)
            )

            self.charges_table.setRowCount(0)
            for row in cur.fetchall():
                self.add_charge_line()
                row_idx = self.charges_table.rowCount() - 1

                if self.charges_table.cellWidget(row_idx, 0):
                    self.charges_table.cellWidget(row_idx, 0).setText(row[0] or "")
                if self.charges_table.cellWidget(row_idx, 1):
                    self.charges_table.cellWidget(row_idx, 1).setValue(int(row[1] or 1))
                if self.charges_table.cellWidget(row_idx, 2):
                    self.charges_table.cellWidget(row_idx, 2).setText(f"${row[2]:.2f}" if row[2] else "$0.00")
                if self.charges_table.cellWidget(row_idx, 3):
                    self.charges_table.cellWidget(row_idx, 3).setText(f"${row[3]:.2f}" if row[3] else "$0.00")

            self.calculate_totals()
            print(f"✅ Loaded {self.charges_table.rowCount()} charges")
        except Exception as e:
            print(f"❌ Error loading charges: {e}")
    
    def load_charter_beverages(self, charter_id: int, cur):
        """
        Load saved beverages from charter_beverages table (SNAPSHOT DATA)
        Populates the beverage cart so user can edit if needed
        Shows locked prices but allows quantity adjustments
        """
        try:
            cur.execute("""
                SELECT id, item_name, quantity, unit_price_charged, unit_our_cost, 
                       deposit_per_unit, line_amount_charged, line_cost, notes
                FROM charter_beverages
                WHERE charter_id = %s
                ORDER BY created_at
            """, (charter_id,))
            
            beverages = cur.fetchall()
            if not beverages:
                print(f"ℹ️  No beverages saved for charter {charter_id}")
                return
            
            # Clear any existing beverage items in UI (if applicable)
            # Note: We don't clear charges_table since beverages are separate
            
            # Display beverages in a summary view (print to console for now)
            print(f"\n🍷 SAVED BEVERAGES FOR CHARTER {charter_id}:")
            print("─" * 80)
            print(f"{'Item':<40} {'Qty':<5} {'Unit Price':<12} {'Total':<12} {'Notes':<15}")
            print("─" * 80)
            
            for bev_id, item_name, qty, unit_price, unit_cost, deposit, total_charged, total_cost, notes in beverages:
                print(f"{item_name:<40} {qty:<5} ${unit_price:<11.2f} ${total_charged:<11.2f} {notes or '':<15}")
            
            print("─" * 80)
            print(f"✅ Loaded {len(beverages)} beverage item(s)")
            print("\n💡 Tip: Click 'Edit Beverages' button to modify quantities/prices per charter\n")
            
        except Exception as e:
            print(f"❌ Error loading beverages: {e}")


# ============================================================================
# ACCOUNTING & RECEIPTS WIDGET
# ============================================================================

class AccountingReceiptsWidget(QWidget):
    """Receipts entry with GST + GL code selection, recent list, and search/match."""

    def __init__(self, db: DatabaseConnection, parent_tab_widget=None):
        super().__init__()
        self.db = db
        self.parent_tab_widget = parent_tab_widget
        self.gl_accounts: Dict[str, str] = {}
        self.vehicles: Dict[int, str] = {}
        # Initialize combo boxes early to prevent errors in load methods
        self.gl_combo = QComboBox()
        self.gl_combo.addItem("", "")
        self.vehicle_combo = QComboBox()
        self.vehicle_combo.addItem("", None)
        try:
            self.init_ui()
        except Exception as e:
            print(f"Error in AccountingReceiptsWidget.init_ui(): {e}")
            import traceback
            traceback.print_exc()
        try:
            self.load_chart_accounts()
        except Exception as e:
            print(f"Error in load_chart_accounts(): {e}")
        try:
            self.load_vehicles()
        except Exception as e:
            print(f"Error in load_vehicles(): {e}")
        try:
            self.load_receipts()
        except Exception as e:
            print(f"Error in load_receipts(): {e}")

    def _create_simplified_receipts_tab(self) -> QWidget:
        """Create a simplified receipts interface without the crashing ReceiptSearchMatchWidget"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Header
        header = QLabel("💰 Receipts & Invoices")
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)
        
        # Search area
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        search_input = QLineEdit()
        search_input.setPlaceholderText("Vendor name or amount...")
        search_layout.addWidget(search_input)
        add_btn = QPushButton("➕ Add Receipt")
        search_layout.addWidget(add_btn)
        layout.addLayout(search_layout)
        
        # Receipts table
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["Date", "Vendor", "Amount", "GST", "GL Code", "ID"])
        
        try:
            cur = self.db.conn.cursor()
            cur.execute("""
                SELECT receipt_date, vendor_name, gross_amount, gst_amount, pay_account, receipt_id 
                FROM receipts 
                ORDER BY receipt_date DESC 
                LIMIT 200
            """)
            rows = cur.fetchall()
            cur.close()
            
            table.setRowCount(len(rows))
            for i, row in enumerate(rows):
                for j, value in enumerate(row):
                    item = QTableWidgetItem(str(value) if value is not None else "")
                    if j in [2, 3]:  # Amount columns - right align
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
                    table.setItem(i, j, item)
            
            table.resizeColumnsToContents()
            table.horizontalHeader().setStretchLastSection(False)
        except Exception as e:
            print(f"Error loading receipts: {e}")
        
        layout.addWidget(table)
        return widget

    def init_ui(self):
        # Single comprehensive Search & Match widget handles all receipt/invoice operations
        main_layout = QVBoxLayout()
        
        tabs = QTabWidget()
        
        # Store tab reference for cross-tab navigation
        self.accounting_tabs = tabs
        
        print("    >> [init_ui] Creating ReceiptSearchMatchWidget...", flush=True)
        # Tab 1: Search & Match (comprehensive - search, add receipts/invoices, edit, match to banking)
        print("    >> [init_ui] Passing db connection...", flush=True)
        try:
            search_match_widget = ReceiptSearchMatchWidget(self.db.conn)
        except Exception as e:
            import traceback
            print(f"    >> ❌ ReceiptSearchMatchWidget failed to init: {e}", flush=True)
            traceback.print_exc()
            raise
        print("    >> [init_ui] ReceiptSearchMatchWidget created, setting parent_tab_widget...", flush=True)
        search_match_widget.parent_tab_widget = self.parent_tab_widget
        print("    >> [init_ui] Adding to tabs...", flush=True)
        tabs.addTab(search_match_widget, "🔍 Search, Match & Add")
        print("    >> [init_ui] ReceiptSearchMatchWidget tab added OK", flush=True)
        
        try:
            # Tab 2: Recent Receipts (quick view/edit table)
            recent_tab = self._create_recent_receipts_tab()
            tabs.addTab(recent_tab, "📋 Recent List")
        except Exception as e:
            print(f"Error creating recent receipts tab: {e}")
            import traceback
            traceback.print_exc()
            error_label = QLabel(f"Error loading Recent Receipts: {e}")
            error_label.setStyleSheet("color: red;")
            tabs.addTab(error_label, "📋 Recent List")
        
        main_layout.addWidget(tabs)
        self.setLayout(main_layout)
    
    def _create_add_receipt_tab(self):
        """Create the add receipt form tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        form_box = QGroupBox("Add New Receipt")
        form_layout = QFormLayout()

        # ============================================================================
        # PHASE 3: UNDO/REDO SUPPORT
        # ============================================================================
        self.undo_stack = QUndoStack(self)

        # Keypad-friendly date input
        self.date_edit = DateInput()

        # Smart vendor selector with historical lookup
        self.vendor_input = VendorSelector(self.db.conn)
        self.vendor_input.currentTextChanged.connect(self._on_vendor_selected)

        # Currency input field - works with numeric keypad and keyboard
        self.amount_input = CurrencyInput()
        self.amount_input.textChanged.connect(self._on_amount_changed)

        self.gst_display = QLabel("$0.00")
        self.gst_display.setToolTip("GST amount (auto-calculated, 5% of amount - tax inclusive)")
        
        # Tax Jurisdiction selector for out-of-province/US purchases
        self.tax_jurisdiction = QComboBox()
        self.tax_jurisdiction.addItems([
            "AB (GST 5%)",           # Alberta - default
            "BC (GST 5% + PST 7%)",  # British Columbia
            "SK (GST 5% + PST 6%)",  # Saskatchewan
            "MB (GST 5% + PST 7%)",  # Manitoba
            "ON (HST 13%)",          # Ontario
            "QC (GST 5% + PST 9.975%)",  # Quebec
            "NB (HST 15%)",          # New Brunswick
            "NS (HST 15%)",          # Nova Scotia
            "PE (HST 15%)",          # Prince Edward Island
            "NL (HST 15%)",          # Newfoundland & Labrador
            "YT (GST 5%)",           # Yukon
            "NT (GST 5%)",           # Northwest Territories
            "NU (GST 5%)",           # Nunavut
            "US (varies by state)",  # United States
            "Other (manual entry)",  # Manual override
        ])
        self.tax_jurisdiction.setToolTip("<b>Tax Jurisdiction</b><br>Select province/state for automatic tax calculation.<br>Default: AB (GST 5%)")
        self.tax_jurisdiction.currentTextChanged.connect(self.auto_calc_gst)
        
        # PST/Additional Sales Tax input (for US or other provinces)
        self.pst_input = CurrencyInput()
        self.pst_input.setMaximumWidth(150)
        self.pst_input.setText("0.00")
        self.pst_input.setToolTip("<b>PST / Additional Sales Tax</b><br>Enter PST (BC, SK, MB, QC) or US state sales tax.<br>Auto-calculated for Canadian provinces.")
        self.pst_input.textChanged.connect(self.auto_calc_gst)
        self.pst_input.setEnabled(False)  # Auto-calculated by default
        
        # ============================================================================
        # PHASE 3: RECENT ITEMS TRACKING
        # ============================================================================
        self.settings = QSettings("ArrowLimo", "Desktop")

        self.gl_combo = QComboBox()
        self.gl_combo.addItem("", "")
        self.gl_combo.setToolTip("<b>GL Account Code</b><br>General Ledger account for accounting.<br>Auto-filled from vendor history if available.")

        self.vehicle_combo = QComboBox()
        self.vehicle_combo.addItem("", None)
        self.vehicle_combo.setToolTip("<b>Vehicle</b><br>Optional: Link expense to specific vehicle<br>(e.g., for fuel or maintenance)")

        self.description_input = QTextEdit()
        self.description_input.setFixedHeight(60)
        self.description_input.setToolTip("Enter details about this receipt.\nExample: 'Diesel fuel for vehicles 1-3'")

        self.personal_check = QCheckBox("Personal / owner draw")
        self.personal_check.setToolTip("Check if this is a personal expense or owner withdrawal")
        self.personal_check.stateChanged.connect(self.auto_calc_gst)
        
        self.driver_personal_check = QCheckBox("Driver personal (exclude GST)")
        self.driver_personal_check.setToolTip("Check if this is a driver's personal expense (no GST calculation)")
        self.driver_personal_check.stateChanged.connect(self.auto_calc_gst)
        
        self.gst_exempt_check = QCheckBox("GST Exempt")
        self.gst_exempt_check.setToolTip("Check for GST-exempt items (e.g., WCB, government services, basic groceries)")
        self.gst_exempt_check.stateChanged.connect(self.auto_calc_gst)

        self.save_btn = QPushButton("💾 Save Receipt")
        self.save_btn.setToolTip("Save receipt to database [Ctrl+S]")
        self.save_btn.clicked.connect(self.save_receipt)

        # Add format indicators for date
        date_layout = QVBoxLayout()
        date_layout.addWidget(self.date_edit)
        date_hint = QLabel("📅 Format: MM/dd/yyyy, MM-dd-yyyy, or yyyymmdd")
        date_hint.setStyleSheet("font-size: 9px; color: #666; margin-top: -5px;")
        date_layout.addWidget(date_hint)
        date_layout.setContentsMargins(0, 0, 0, 5)
        
        # Add format indicators for amount
        amount_layout = QVBoxLayout()
        amount_layout.addWidget(self.amount_input)
        amount_hint = QLabel("💵 Format: 10 (=10.00), 10.50, or .50 (=0.50)")
        amount_hint.setStyleSheet("font-size: 9px; color: #666; margin-top: -5px;")
        amount_layout.addWidget(amount_hint)
        amount_layout.setContentsMargins(0, 0, 0, 5)
        
        form_layout.addRow("Date", date_layout)
        form_layout.addRow("Vendor", self.vendor_input)
        form_layout.addRow("Amount (tax incl)", amount_layout)
        form_layout.addRow("Tax Jurisdiction", self.tax_jurisdiction)
        form_layout.addRow("GST (auto)", self.gst_display)
        form_layout.addRow("PST / Sales Tax", self.pst_input)
        form_layout.addRow("GL Account", self.gl_combo)
        form_layout.addRow("Vehicle", self.vehicle_combo)
        form_layout.addRow("Description", self.description_input)
        form_layout.addRow(self.personal_check)
        form_layout.addRow(self.driver_personal_check)
        form_layout.addRow(self.gst_exempt_check)
        
        # Undo/Redo buttons
        undo_redo_layout = QHBoxLayout()
        undo_btn = QPushButton("⎌ Undo (Ctrl+Z)")
        undo_btn.clicked.connect(self.undo_stack.undo)
        undo_btn.setShortcut(QKeySequence.StandardKey.Undo)
        redo_btn = QPushButton("⎌ Redo (Ctrl+Y)")
        redo_btn.clicked.connect(self.undo_stack.redo)
        redo_btn.setShortcut(QKeySequence.StandardKey.Redo)
        undo_redo_layout.addWidget(undo_btn)
        undo_redo_layout.addWidget(redo_btn)
        undo_redo_layout.addStretch()
        undo_redo_layout.addWidget(self.save_btn)
        form_layout.addRow(undo_redo_layout)

        form_box.setLayout(form_layout)
        layout.addWidget(form_box)
        
        widget.setLayout(layout)
        
        # ============================================================================
        # PHASE 1 UX UPGRADE - TAB ORDER OPTIMIZATION
        # ============================================================================
        # Optimize form navigation: Date → Vendor → Amount → GL → Save
        self.date_edit.setFocus()
        QWidget.setTabOrder(self.date_edit, self.vendor_input)
        QWidget.setTabOrder(self.vendor_input, self.amount_input)
        QWidget.setTabOrder(self.amount_input, self.gl_combo)
        QWidget.setTabOrder(self.gl_combo, self.vehicle_combo)
        QWidget.setTabOrder(self.vehicle_combo, self.description_input)
        QWidget.setTabOrder(self.description_input, self.personal_check)
        QWidget.setTabOrder(self.personal_check, self.driver_personal_check)
        QWidget.setTabOrder(self.driver_personal_check, self.gst_exempt_check)
        QWidget.setTabOrder(self.gst_exempt_check, self.save_btn)
        
        return widget
    
    def _create_recent_receipts_tab(self):
        """Create the recent receipts table tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Bulk operations toolbar
        bulk_toolbar = QHBoxLayout()
        bulk_toolbar.setSpacing(6)
        self.bulk_select_all_btn = QPushButton("☑ Select All")
        self.bulk_clear_selection_btn = QPushButton("☐ Clear")
        self.bulk_verify_btn = QPushButton("✅ Mark Verified")
        self.bulk_delete_btn = QPushButton("🗑️ Delete Selected")
        self.bulk_select_all_btn.clicked.connect(self._bulk_select_all)
        self.bulk_clear_selection_btn.clicked.connect(self._bulk_clear_selection)
        self.bulk_verify_btn.clicked.connect(self._bulk_mark_verified)
        self.bulk_delete_btn.clicked.connect(self._bulk_delete)
        bulk_toolbar.addWidget(QLabel("Bulk Actions:"))
        bulk_toolbar.addWidget(self.bulk_select_all_btn)
        bulk_toolbar.addWidget(self.bulk_clear_selection_btn)
        bulk_toolbar.addWidget(self.bulk_verify_btn)
        bulk_toolbar.addWidget(self.bulk_delete_btn)
        bulk_toolbar.addStretch()
        layout.addLayout(bulk_toolbar)

        # Quick filter bar
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(6)
        self.filter_vendor = QLineEdit()
        self.filter_vendor.setPlaceholderText("Vendor contains...")
        self.filter_gl = QComboBox()
        self.filter_gl.setEditable(False)
        self.filter_gl.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.filter_gl.setToolTip("Filter by GL Account Code")
        # Load GL accounts from database
        gl_accounts = [
            "",
            "6000 - Advertising",
            "6005 - Donations",
            "6100 - Office Rent",
            "6101 - Interest & Late Chgs Expense",
            "6200 - Utilities",
            "6300 - Repairs & Maintenance",
            "6350 - Equipment Repairs",
            "6400 - Insurance",
            "6480 - Membership",
            "6500 - Bank Fees",
            "6500 - Meals and Entertainment",
            "6550 - Office Supplies",
            "6610 - Wages/Salaries",
            "6625 - Professional Fees",
            "6751 - Hospitality Supplies",
            "6750 - Supplies",
            "6800 - Telephone",
            "6826 - Parking & Misc. Ticket Expenses",
            "6900 - Vehicle R&M",
            "6925 - Fuel",
            "6950 - WCB",
            "Administrative",
            "ADVERTISING",
            "Bank Charges",
            "Bank Charges & Interest",
            "Bank Fees",
            "Business expense",
            "Client Entertainment",
            "communication",
            "entertainment_beverages",
            "equipment_lease",
            "fuel",
            "Fuel",
            "FUEL",
            "Government Fees",
            "government_fees",
            "hospitality_supplies",
            "insurance",
            "Insurance",
            "Insurance - Vehicle Liability",
            "licenses",
            "Liquor/Entertainment",
            "maintenance",
            "meals_entertainment",
            "mixed_use",
            "office rent",
            "office_supplies",
            "owner_draws",
            "petty_cash",
            "rent",
            "Supplies",
            "uncategorized_expenses",
            "utilities",
            "Vehicle Maintenance",
            "Vehicle Rental",
        ]
        self.filter_amount_min = QLineEdit()
        self.filter_amount_min.setPlaceholderText("Min $")
        self.filter_amount_max = QLineEdit()
        self.filter_amount_max.setPlaceholderText("Max $")
        self.filter_date_from = DateInput()
        self.filter_date_from.setToolTip("Filter from date (optional)")
        self.filter_date_to = DateInput()
        self.filter_date_to.setToolTip("Filter to date (optional)")
        self.filter_date_from.setText("")
        self.filter_date_to.setText("")
        self.filter_apply_btn = QPushButton("Apply Filters")
        self.filter_clear_btn = QPushButton("Clear")
        self.filter_apply_btn.clicked.connect(self.apply_receipt_filters)
        self.filter_clear_btn.clicked.connect(self.clear_receipt_filters)
        filter_layout.addWidget(QLabel("Vendor"))
        filter_layout.addWidget(self.filter_vendor)
        filter_layout.addWidget(QLabel("GL Account"))
        filter_layout.addWidget(self.filter_gl)
        filter_layout.addWidget(QLabel("Amount"))
        filter_layout.addWidget(self.filter_amount_min)
        filter_layout.addWidget(QLabel("to"))
        filter_layout.addWidget(self.filter_amount_max)
        filter_layout.addWidget(QLabel("Date"))
        filter_layout.addWidget(self.filter_date_from)
        filter_layout.addWidget(QLabel("to"))
        filter_layout.addWidget(self.filter_date_to)
        filter_layout.addWidget(self.filter_apply_btn)
        filter_layout.addWidget(self.filter_clear_btn)
        layout.addLayout(filter_layout)

        # Recent receipts table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "☑", "Date", "Vendor", "GL Account", "Amount", "GST", "Type"
        ])
        self._expanded_rows = set()  # Track expanded rows for detail view
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(500)  # Show at least 12-15 rows
        self.table.setAlternatingRowColors(True)  # Better visibility
        
        # ============================================================================
        # PHASE 1 UX UPGRADE - CONTEXT MENUS (RIGHT-CLICK)
        # ============================================================================
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_receipt_context_menu)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.cellDoubleClicked.connect(self._toggle_row_expansion)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.table.cellChanged.connect(self._on_receipt_cell_changed)
        # Keyboard helpers for navigation
        self.table.keyPressEvent = lambda event: self._receipt_table_keypress(event)
        
        layout.addWidget(self.table)

        widget.setLayout(layout)
        return widget
    
    # ============================================================================
    # CONTEXT MENU HANDLERS
    # ============================================================================
    def _show_receipt_context_menu(self, position):
        """Show right-click context menu for receipt table"""
        item = self.table.itemAt(position)
        if not item:
            return
        
        row = item.row()
        menu = QMenu(self)
        
        # Context menu actions
        expand_action = menu.addAction("📂 Expand/Collapse Details")
        menu.addSeparator()
        link_action = menu.addAction("🔗 Link to Payment")
        dup_action = menu.addAction("📋 Duplicate Receipt")
        verify_action = menu.addAction("✅ Mark as Verified")
        menu.addSeparator()
        view_action = menu.addAction("📄 View Original")
        menu.addSeparator()
        delete_action = menu.addAction("🗑️ Delete Receipt")
        
        action = menu.exec(self.table.mapToGlobal(position))
        
        if action == expand_action:
            self._toggle_row_expansion(row, 0)
        elif action == link_action:
            QMessageBox.information(self, "Link Payment", f"Linking receipt from row {row}...\n[Full implementation pending]")
        elif action == dup_action:
            self._duplicate_receipt(row)
        elif action == verify_action:
            self._mark_receipt_verified(row)
        elif action == view_action:
            QMessageBox.information(self, "View Document", f"Opening original document for receipt {row}...\n[PDF viewer pending]")
        elif action == delete_action:
            self._delete_receipt_row(row)

    def _on_vendor_selected(self, vendor_name):
        """When vendor selected, auto-populate GL code from history"""
        if not vendor_name:
            return
        
        # Get suggested GL code from VendorSelector
        suggested_gl_code = self.vendor_input.get_suggested_gl_code()
        
        # Auto-populate GL code if found
        if suggested_gl_code:
            index = self.gl_combo.findData(suggested_gl_code)
            if index >= 0:
                self.gl_combo.setCurrentIndex(index)

    def _on_amount_changed(self, text):
        """Handle amount field changes - convert to float and recalculate GST"""
        # Delegate to auto_calc_gst which now handles PST too
        self.auto_calc_gst()

    def auto_calc_gst(self):
        """Calculate GST and PST based on jurisdiction"""
        try:
            # Get amount
            amount_text = self.amount_input.text()
            if not amount_text or amount_text == "":
                self.gst_display.setText("$0.00")
                self.pst_input.setText("0.00")
                return
            
            amount = float(amount_text)
            
            # Check if GST/PST should be excluded
            if self.driver_personal_check.isChecked() or self.gst_exempt_check.isChecked():
                self.gst_display.setText("$0.00")
                self.pst_input.setText("0.00")
                self.pst_input.setEnabled(False)
                return
            
            # Get jurisdiction
            jurisdiction = self.tax_jurisdiction.currentText()
            
            # Calculate based on jurisdiction (tax-inclusive)
            if "AB" in jurisdiction or "YT" in jurisdiction or "NT" in jurisdiction or "NU" in jurisdiction:
                # Alberta/Territories: GST 5% only
                gst = amount * 0.05 / 1.05
                pst = 0.0
                self.pst_input.setEnabled(False)
            elif "BC" in jurisdiction:
                # BC: GST 5% + PST 7% = 12% total (tax-inclusive)
                total_tax_rate = 0.12
                total_tax = amount * total_tax_rate / (1 + total_tax_rate)
                gst = amount * 0.05 / (1 + total_tax_rate)
                pst = total_tax - gst
                self.pst_input.setEnabled(False)
            elif "SK" in jurisdiction:
                # Saskatchewan: GST 5% + PST 6% = 11% total
                total_tax_rate = 0.11
                total_tax = amount * total_tax_rate / (1 + total_tax_rate)
                gst = amount * 0.05 / (1 + total_tax_rate)
                pst = total_tax - gst
                self.pst_input.setEnabled(False)
            elif "MB" in jurisdiction:
                # Manitoba: GST 5% + PST 7% = 12% total
                total_tax_rate = 0.12
                total_tax = amount * total_tax_rate / (1 + total_tax_rate)
                gst = amount * 0.05 / (1 + total_tax_rate)
                pst = total_tax - gst
                self.pst_input.setEnabled(False)
            elif "QC" in jurisdiction:
                # Quebec: GST 5% + QST 9.975% = 14.975% total
                total_tax_rate = 0.14975
                total_tax = amount * total_tax_rate / (1 + total_tax_rate)
                gst = amount * 0.05 / (1 + total_tax_rate)
                pst = total_tax - gst
                self.pst_input.setEnabled(False)
            elif "HST" in jurisdiction:
                # HST provinces (ON 13%, NB/NS/PE/NL 15%)
                if "ON" in jurisdiction:
                    hst_rate = 0.13
                else:
                    hst_rate = 0.15
                gst = amount * hst_rate / (1 + hst_rate)  # HST = combined GST+PST
                pst = 0.0
                self.pst_input.setEnabled(False)
            elif "US" in jurisdiction:
                # US: Manual entry (rates vary by state)
                gst = 0.0  # No Canadian GST on US purchases
                self.pst_input.setEnabled(True)  # Manual sales tax entry
                # Keep current PST value (user enters US sales tax)
                pst_str = self.pst_input.get_value() if hasattr(self.pst_input, 'get_value') else "0.00"
                pst = float(pst_str) if pst_str else 0.0
            elif "Other" in jurisdiction:
                # Manual entry
                gst = 0.0
                self.pst_input.setEnabled(True)
                pst_str = self.pst_input.get_value() if hasattr(self.pst_input, 'get_value') else "0.00"
                pst = float(pst_str) if pst_str else 0.0
            else:
                # Default to Alberta
                gst = amount * 0.05 / 1.05
                pst = 0.0
                self.pst_input.setEnabled(False)
            
            self.gst_display.setText(f"${gst:.2f}")
            if not self.pst_input.isEnabled():
                self.pst_input.setText(f"{pst:.2f}")
            
        except (ValueError, AttributeError) as e:
            # Not a valid number yet, ignore
            pass

    def load_chart_accounts(self):
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            cur.execute(
                """
                SELECT account_code, account_name
                FROM chart_of_accounts
                ORDER BY account_code
                """
            )
            rows = cur.fetchall()
            self.gl_accounts = {r[0]: r[1] for r in rows if r[0]}
            self.gl_combo.clear()
            self.gl_combo.addItem("", "")
            for code, name in self.gl_accounts.items():
                self.gl_combo.addItem(f"{code} — {name}", code)
        except Exception as e:
            QMessageBox.warning(self, "Chart of Accounts", f"Failed to load accounts: {e}")

    def load_vehicles(self):
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            cur.execute(
                """
                SELECT vehicle_id, COALESCE(unit_number, 'Vehicle ' || vehicle_id) as nickname, COALESCE(license_plate, '') as license_plate
                FROM vehicles
                WHERE status = 'active' OR status IS NULL
                ORDER BY vehicle_id
                """
            )
            rows = cur.fetchall()
            self.vehicles = {r[0]: f"{r[1]} ({r[2]})" if r[1] and r[2] else r[1] or f"Vehicle {r[0]}" for r in rows}
            self.vehicle_combo.clear()
            self.vehicle_combo.addItem("", None)
            for vid, label in self.vehicles.items():
                self.vehicle_combo.addItem(label, vid)
        except Exception as e:
            QMessageBox.warning(self, "Vehicles", f"Failed to load vehicles: {e}")

    def load_receipts(self, filters=None):
        """Load receipts with optional filters and support inline editing"""
        self._current_receipt_filters = filters
        self._loading_receipts = True
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            base_query = (
                "SELECT receipt_id, receipt_date, vendor_name, category, gl_account_code, "
                "gross_amount, gst_amount, gst_code "
                "FROM receipts "
            )
            conditions = []
            params = []
            if filters:
                vendor = filters.get("vendor")
                if vendor:
                    conditions.append("vendor_name ILIKE %s")
                    params.append(f"%{vendor}%")
                category = filters.get("category")
                if category:
                    conditions.append("category = %s")
                    params.append(category)
                amt_min = filters.get("amount_min")
                if amt_min is not None:
                    conditions.append("gross_amount >= %s")
                    params.append(amt_min)
                amt_max = filters.get("amount_max")
                if amt_max is not None:
                    conditions.append("gross_amount <= %s")
                    params.append(amt_max)
                date_from = filters.get("date_from")
                if date_from:
                    conditions.append("receipt_date >= %s")
                    params.append(date_from)
                date_to = filters.get("date_to")
                if date_to:
                    conditions.append("receipt_date <= %s")
                    params.append(date_to)
            if conditions:
                base_query += "WHERE " + " AND ".join(conditions) + " "
            base_query += "ORDER BY receipt_date DESC, receipt_id DESC LIMIT 200"
            cur.execute(base_query, params)
            rows = cur.fetchall()
            self.table.blockSignals(True)
            self.table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                receipt_id = r[0]
                receipt_date = r[1]
                vendor = r[2]
                category = r[3]
                gl_code = r[4]
                amt = float(r[5]) if r[5] else 0
                gst = float(r[6]) if r[6] else 0
                gst_code = r[7]

                # Checkbox column
                checkbox = QTableWidgetItem()
                checkbox.setCheckState(Qt.CheckState.Unchecked)
                checkbox.setData(Qt.ItemDataRole.UserRole, receipt_id)
                self.table.setItem(i, 0, checkbox)

                date_item = QTableWidgetItem(receipt_date.strftime("%Y-%m-%d") if receipt_date else "")
                self.table.setItem(i, 1, date_item)
                self.table.setItem(i, 2, QTableWidgetItem(vendor or ""))
                self.table.setItem(i, 3, QTableWidgetItem(category or ""))
                self.table.setItem(i, 4, QTableWidgetItem(gl_code or ""))
                self.table.setItem(i, 5, QTableWidgetItem(f"${amt:.2f}"))
                self.table.setItem(i, 6, QTableWidgetItem(f"${gst:.2f}"))
                receipt_type = "Driver" if (gst_code == "DRIVER_PERSONAL") else "Personal" if gst == 0 and amt > 0 and gst_code else "Business"
                self.table.setItem(i, 7, QTableWidgetItem(receipt_type))
            self.table.blockSignals(False)
        except Exception as e:
            self.table.blockSignals(False)
            QMessageBox.warning(self, "Receipts", f"Failed to load receipts: {e}")
        finally:
            self._loading_receipts = False

    def apply_receipt_filters(self):
        """Gather filter inputs and reload receipts"""
        filters = {}
        vendor = self.filter_vendor.text().strip()
        if vendor:
            filters["vendor"] = vendor
        gl_code = self.filter_gl.currentData()
        if gl_code:
            filters["gl_code"] = gl_code
        amt_min_text = self.filter_amount_min.text().replace("$", "").replace(",", "").strip()
        if amt_min_text:
            try:
                filters["amount_min"] = Decimal(amt_min_text)
            except:
                QMessageBox.warning(self, "Filter", "Amount min is invalid")
                return
        amt_max_text = self.filter_amount_max.text().replace("$", "").replace(",", "").strip()
        if amt_max_text:
            try:
                filters["amount_max"] = Decimal(amt_max_text)
            except:
                QMessageBox.warning(self, "Filter", "Amount max is invalid")
                return
        date_from_text = self.filter_date_from.text().strip()
        if date_from_text:
            parsed = self._parse_date_value(date_from_text)
            if parsed:
                filters["date_from"] = parsed
            else:
                QMessageBox.warning(self, "Filter", "From date is invalid")
                return
        date_to_text = self.filter_date_to.text().strip()
        if date_to_text:
            parsed = self._parse_date_value(date_to_text)
            if parsed:
                filters["date_to"] = parsed
            else:
                QMessageBox.warning(self, "Filter", "To date is invalid")
                return
        self.load_receipts(filters)

    def clear_receipt_filters(self):
        self.filter_vendor.clear()
        self.filter_gl.setCurrentIndex(0)
        self.filter_amount_min.clear()
        self.filter_amount_max.clear()
        self.filter_date_from.setText("")
        self.filter_date_to.setText("")
        self.load_receipts()

    def _get_receipt_id(self, row):
        item = self.table.item(row, 0)
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _parse_date_value(self, text):
        text = text.strip()
        if not text:
            return None
        fmts = ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%m%d%Y", "%m%d%y", "%Y/%m/%d"]
        for fmt in fmts:
            try:
                return datetime.strptime(text, fmt).date()
            except:
                continue
        return None

    def _parse_amount_value(self, text):
        cleaned = text.replace("$", "").replace(",", "").strip()
        if not cleaned:
            return Decimal("0")
        return Decimal(cleaned)

    def _reload_receipts(self):
        self.load_receipts(self._current_receipt_filters)

    def _on_receipt_cell_changed(self, row, column):
        if self._loading_receipts:
            return
        receipt_id = self._get_receipt_id(row)
        if not receipt_id:
            return
        column_map = {
            1: ("receipt_date", self._parse_date_value),
            2: ("vendor_name", lambda v: v.strip().upper() if v else None),
            3: ("gl_account_code", lambda v: v.strip() if v else None),
            4: ("gross_amount", self._parse_amount_value),
            5: ("gst_amount", self._parse_amount_value),
        }
        if column not in column_map:
            return
        field, parser = column_map[column]
        value_text = self.table.item(row, column).text() if self.table.item(row, column) else ""
        try:
            parsed_value = parser(value_text)
        except Exception:
            QMessageBox.warning(self, "Update", "Invalid value")
            self._reload_receipts()
            return
        if field == "receipt_date" and not parsed_value:
            QMessageBox.warning(self, "Update", "Invalid date format")
            self._reload_receipts()
            return
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            cur.execute(f"UPDATE receipts SET {field} = %s WHERE receipt_id = %s", (parsed_value, receipt_id))
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Update Failed", f"Could not update receipt: {e}")
        self._reload_receipts()

    def _receipt_table_keypress(self, event):
        key = event.key()
        mods = event.modifiers()
        current = self.table.currentItem()
        if current:
            row = current.row()
            col = current.column()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.table.editItem(current)
                return
            if key == Qt.Key.Key_Space:
                self.table.selectRow(row)
                return
            if mods & Qt.KeyboardModifier.ControlModifier:
                if key == Qt.Key.Key_Down:
                    self.table.setCurrentCell(self.table.rowCount() - 1, col)
                    return
                if key == Qt.Key.Key_Up:
                    self.table.setCurrentCell(0, col)
                    return
        QTableWidget.keyPressEvent(self.table, event)

    # ============================================================================
    # PHASE 3: BULK OPERATIONS
    # ============================================================================
    def _bulk_select_all(self):
        """Select all receipts in table"""
        for row in range(self.table.rowCount()):
            checkbox = self.table.item(row, 0)
            if isinstance(checkbox, QTableWidgetItem):
                checkbox.setCheckState(Qt.CheckState.Checked)

    def _bulk_clear_selection(self):
        """Clear all selections"""
        for row in range(self.table.rowCount()):
            checkbox = self.table.item(row, 0)
            if isinstance(checkbox, QTableWidgetItem):
                checkbox.setCheckState(Qt.CheckState.Unchecked)

    def _get_selected_receipt_rows(self):
        """Get rows with checkboxes checked"""
        selected = []
        for row in range(self.table.rowCount()):
            checkbox = self.table.item(row, 0)
            if isinstance(checkbox, QTableWidgetItem) and checkbox.checkState() == Qt.CheckState.Checked:
                selected.append(row)
        return selected

    def _bulk_change_category(self):
        """Change category for multiple receipts"""
        rows = self._get_selected_receipt_rows()
        if not rows:
            QMessageBox.information(self, "Bulk Category", "No receipts selected")
            return

        categories = ["fuel", "maintenance", "insurance", "office", "meals", "other"]
        category, ok = QInputDialog.getItem(self, "Batch Category", "Select new category:", categories, 0, False)
        if not ok or not category:
            return

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            for row in rows:
                receipt_id = self._get_receipt_id(row)
                if receipt_id:
                    cur.execute("UPDATE receipts SET category = %s WHERE receipt_id = %s", (category, receipt_id))
            self.db.commit()
            QMessageBox.information(self, "Success", f"Updated {len(rows)} receipts")
            self._reload_receipts()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Failed", f"Batch update failed: {e}")

    def _bulk_mark_verified(self):
        """Mark multiple receipts as verified"""
        rows = self._get_selected_receipt_rows()
        if not rows:
            QMessageBox.information(self, "Bulk Verify", "No receipts selected")
            return

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            for row in rows:
                receipt_id = self._get_receipt_id(row)
                if receipt_id:
                    cur.execute("UPDATE receipts SET reviewed = TRUE WHERE receipt_id = %s", (receipt_id,))
                    # Visual feedback
                    for col in range(1, self.table.columnCount()):
                        item = self.table.item(row, col)
                        if item:
                            item.setBackground(QBrush(QColor(200, 255, 200)))
            self.db.commit()
            QMessageBox.information(self, "Success", f"Marked {len(rows)} receipts as verified")
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Failed", f"Batch verify failed: {e}")

    def _bulk_delete(self):
        """Delete multiple receipts"""
        rows = self._get_selected_receipt_rows()
        if not rows:
            QMessageBox.information(self, "Bulk Delete", "No receipts selected")
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete {len(rows)} selected receipts? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            for row in rows:
                receipt_id = self._get_receipt_id(row)
                if receipt_id:
                    cur.execute("DELETE FROM receipts WHERE receipt_id = %s", (receipt_id,))
            self.db.commit()
            QMessageBox.information(self, "Success", f"Deleted {len(rows)} receipts")
            self._reload_receipts()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Failed", f"Batch delete failed: {e}")

    # ============================================================================
    # PHASE 3: ROW EXPANSION / DETAIL VIEW
    # ============================================================================
    def _toggle_row_expansion(self, row, column):
        """Expand or collapse row to show full details"""
        if row in self._expanded_rows:
            # Collapse: remove detail row
            self._expanded_rows.discard(row)
            if row + 1 < self.table.rowCount():
                detail_item = self.table.item(row + 1, 0)
                if detail_item and detail_item.text().startswith("  [Details]"):
                    self.table.removeRow(row + 1)
        else:
            # Expand: insert detail row
            self._expanded_rows.add(row)
            receipt_id = self._get_receipt_id(row)
            if not receipt_id:
                return

            try:
                # Rollback any failed transactions first
                try:
                    self.db.rollback()
                except:
                    pass
                
                cur = self.db.get_cursor()
                cur.execute(
                    """
                    SELECT description, gl_account_code, gl_account_name,
                           source_system, reviewed, created_from_banking, banking_transaction_id
                    FROM receipts
                    WHERE receipt_id = %s
                    """,
                    (receipt_id,)
                )
                result = cur.fetchone()
                if not result:
                    return

                desc = result[0] or "N/A"
                gl_code = result[1] or "N/A"
                gl_name = result[2] or "N/A"
                source = result[3] or "Manual Entry"
                reviewed = "✅ Verified" if result[4] else "⚠️ Unverified"
                banking = "🏦 From Banking" if result[5] else "Manual"
                bank_tx = result[6]

                detail_text = (
                    f"  [Details] Description: {desc} | GL Account: {gl_code} - {gl_name} | "
                    f"Source: {source} | Status: {reviewed} | Type: {banking}"
                )
                if bank_tx:
                    detail_text += f" | Bank TX: {bank_tx}"

                # Insert new row below current
                self.table.insertRow(row + 1)
                detail_item = QTableWidgetItem(detail_text)
                detail_item.setBackground(QBrush(QColor(240, 240, 240)))
                self.table.setItem(row + 1, 0, detail_item)
                self.table.setSpan(row + 1, 0, 1, self.table.columnCount())

            except Exception as e:
                QMessageBox.warning(self, "Expand", f"Failed to load details: {e}")

    # ============================================================================
    # PHASE 3: CONTEXT MENU HELPER ACTIONS
    # ============================================================================
    def _duplicate_receipt(self, row):
        """Duplicate a receipt (copy values to new row)"""
        receipt_id = self._get_receipt_id(row)
        if not receipt_id:
            return

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            cur.execute(
                """
                INSERT INTO receipts (
                    receipt_date, vendor_name, canonical_vendor, gross_amount, gst_amount,
                    category, description, gl_account_code, gl_account_name
                )
                SELECT receipt_date, vendor_name, canonical_vendor, gross_amount, gst_amount,
                       category, description, gl_account_code, gl_account_name
                FROM receipts
                WHERE receipt_id = %s
                RETURNING receipt_id
                """,
                (receipt_id,)
            )
            new_id = cur.fetchone()[0]
            self.db.commit()
            QMessageBox.information(self, "Duplicated", f"Receipt duplicated as ID {new_id}")
            self._reload_receipts()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Failed", f"Duplicate failed: {e}")

    def _change_receipt_category(self, row):
        """Change category for a single receipt"""
        receipt_id = self._get_receipt_id(row)
        if not receipt_id:
            return

        categories = ["fuel", "maintenance", "insurance", "office", "meals", "other"]
        category, ok = QInputDialog.getItem(self, "Change Category", "Select category:", categories, 0, False)
        if not ok or not category:
            return

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            cur.execute("UPDATE receipts SET category = %s WHERE receipt_id = %s", (category, receipt_id))
            self.db.commit()
            self._reload_receipts()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Failed", f"Update failed: {e}")

    def _mark_receipt_verified(self, row):
        """Mark single receipt as verified"""
        receipt_id = self._get_receipt_id(row)
        if not receipt_id:
            return

        try:
            cur = self.db.get_cursor()
            cur.execute("UPDATE receipts SET reviewed = TRUE WHERE receipt_id = %s", (receipt_id,))
            self.db.commit()
            # Visual feedback
            for col in range(1, self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    item.setBackground(QBrush(QColor(200, 255, 200)))
            QMessageBox.information(self, "Verified", "Receipt marked as verified")
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Failed", f"Verify failed: {e}")

    def _delete_receipt_row(self, row):
        """Delete single receipt"""
        receipt_id = self._get_receipt_id(row)
        if not receipt_id:
            return

        reply = QMessageBox.question(
            self, "Delete",
            f"Delete receipt ID {receipt_id}? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            cur.execute("DELETE FROM receipts WHERE receipt_id = %s", (receipt_id,))
            self.db.commit()
            QMessageBox.information(self, "Deleted", "Receipt deleted")
            self._reload_receipts()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Failed", f"Delete failed: {e}")


    def save_receipt(self):
        # Show progress indicator
        progress = QMessageBox(self)
        progress.setWindowTitle("Saving...")
        progress.setText("Saving receipt to database...")
        progress.setStandardButtons(QMessageBox.StandardButton.NoButton)
        progress.show()
        QApplication.processEvents()
        
        # Get vendor in UPPERCASE from VendorSelector
        vendor = self.vendor_input.get_vendor()
        if not vendor:
            progress.close()
            QMessageBox.warning(self, "Validation", "Vendor is required")
            return

        # Parse amount from currency input field
        try:
            amount = Decimal(str(self.amount_input.get_value()))
        except:
            progress.close()
            QMessageBox.warning(self, "Validation", "Amount must be a valid number")
            return
            
        gst_val = Decimal(str(self.gst_display.text().replace('$', '').replace(',', '') or '0'))
        pst_val = Decimal(str(self.pst_input.get_value())) if hasattr(self.pst_input, 'get_value') else Decimal('0')
        gl_code = self.gl_combo.currentData()
        gl_name = self.gl_accounts.get(gl_code, None) if gl_code else None
        vehicle_id = self.vehicle_combo.currentData()
        vehicle_id = int(vehicle_id) if vehicle_id else None
        is_driver_personal = self.driver_personal_check.isChecked()
        is_gst_exempt = self.gst_exempt_check.isChecked()
        is_personal = self.personal_check.isChecked()

        canonical_vendor = vendor.upper()
        owner_personal_amount = amount if is_personal and not is_driver_personal else Decimal("0")
        
        # Determine GST code based on checkboxes
        if is_driver_personal:
            gst_code = "DRIVER_PERSONAL"
        elif is_gst_exempt:
            gst_code = "GST_EXEMPT"
        else:
            gst_code = "GST_INCL_5"
            
        if is_driver_personal or is_gst_exempt:
            gst_val = Decimal("0")

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            cur.execute(
                """
                INSERT INTO receipts (
                    receipt_date, vendor_name, canonical_vendor,
                    gross_amount, gst_amount, gst_code, sales_tax,
                    description, vehicle_id, owner_personal_amount,
                    gl_account_code, gl_account_name
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING receipt_id
                """,
                (
                    self.date_edit.getDate().toPyDate(),
                    vendor,
                    canonical_vendor,
                    amount,
                    gst_val,
                    gst_code,
                    pst_val,
                    tax_jurisdiction,
                    category,
                    self.description_input.toPlainText().strip() or None,
                    vehicle_id,
                    owner_personal_amount,
                    gl_code,
                    gl_name,
                ),
            )
            receipt_id = cur.fetchone()[0]
            self.db.commit()
            progress.close()
            QMessageBox.information(self, "Saved", f"Receipt #{receipt_id} saved")
            self._track_category_usage(category)
            self.undo_stack.clear()
            self.reset_form()
            self.load_receipts()
        except Exception as e:
            self.db.rollback()
            progress.close()
            QMessageBox.critical(self, "Save Failed", f"Could not save receipt:\n{e}")

    def reset_form(self):
        self.date_edit.setDate(QDate.currentDate())
        self.vendor_input.clear()
        self.amount_input.setValue(0.0)
        self.gst_display.setText("$0.00")
        self.pst_input.setText("0.00")
        self.tax_jurisdiction.setCurrentIndex(0)  # Reset to AB (GST 5%)
        self.gl_combo.setCurrentIndex(0)
        self.vehicle_combo.setCurrentIndex(0)
        self.description_input.clear()
        self.personal_check.setChecked(False)
        self.driver_personal_check.setChecked(False)
        self.gst_exempt_check.setChecked(False)


# ============================================================================
# CUSTOMERS WIDGET
# ============================================================================

class CustomersWidget(QWidget):
    """Customer management with search, add/edit form, and recent list."""

    def __init__(self, db: DatabaseConnection):
        super().__init__()
        self.db = db
        self.current_customer_id = None
        self.init_ui()
        self.load_customers()
        self.setFixedSize(520, 420)

        # Apply branded styling and optional background
        self.setStyleSheet(
            """
            QDialog {
                background-color: #0b1727;
            }
            QLabel#BrandTitle {
                color: #e6f0ff;
                font-size: 22px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }
            QLabel#BrandSubtitle {
                color: #9ab4d0;
                font-size: 12px;
            }
            QFrame#LoginCard {
                background: rgba(255, 255, 255, 0.94);
                border-radius: 12px;
                padding: 16px 18px;
            }
            QLineEdit {
                padding: 8px 10px;
                border: 1px solid #d0d7e2;
                border-radius: 6px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
            QPushButton {
                padding: 8px 14px;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton#PrimaryLogin {
                background-color: #2563eb;
                color: white;
            }
            QPushButton#PrimaryLogin:hover {
                background-color: #1d4ed8;
            }
            QPushButton#SecondaryCancel {
                background: #e5e7eb;
                color: #111827;
            }
            QLabel#ErrorLabel {
                color: #d32f2f;
                font-weight: 600;
            }
            """
        )

        bg_candidates = [
            Path(current_dir) / "login_background.jpg",
            Path("L:/limo/photo/Fleet photo 2018.jpg"),
        ]
        for bg_path in bg_candidates:
            if bg_path.exists():
                try:
                    pix = QPixmap(str(bg_path))
                    pal = self.palette()
                    pal.setBrush(
                        self.backgroundRole(),
                        QBrush(
                            pix.scaled(
                                self.size(),
                                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                Qt.TransformationMode.SmoothTransformation,
                            )
                        ),
                    )
                    self.setPalette(pal)
                    self.setAutoFillBackground(True)
                except Exception:
                    pass
                break

    def init_ui(self):
        layout = QVBoxLayout()

        # Search & add buttons
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Name, phone, or email...")
        self.search_input.textChanged.connect(self.load_customers)
        search_layout.addWidget(self.search_input)
        self.add_btn = QPushButton("➕ New Customer")
        self.add_btn.clicked.connect(self.new_customer)
        search_layout.addWidget(self.add_btn)
        layout.addLayout(search_layout)

        # Form section
        form_box = QGroupBox("Customer Details")
        form_layout = QFormLayout()

        self.name_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.email_input = QLineEdit()
        self.address_input = QTextEdit()
        self.address_input.setFixedHeight(60)

        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(60)
        self.notes_input.setPlaceholderText("Special instructions, preferences, etc.")

        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 Save Customer")
        self.save_btn.clicked.connect(self.save_customer)
        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self.delete_customer)
        self.clear_btn = QPushButton("Clear Form")
        self.clear_btn.clicked.connect(self.new_customer)
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.delete_btn)
        button_layout.addWidget(self.clear_btn)
        button_layout.addStretch()

        form_layout.addRow("Name*", self.name_input)
        form_layout.addRow("Phone", self.phone_input)
        form_layout.addRow("Email", self.email_input)
        form_layout.addRow("Address", self.address_input)
        form_layout.addRow("Notes", self.notes_input)
        form_layout.addRow(button_layout)

        form_box.setLayout(form_layout)
        layout.addWidget(form_box)

        # Recent customers table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Name", "Phone", "Email", "Address", "# Charters"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.load_selected_customer)
        layout.addWidget(self.table)

        self.setLayout(layout)
        self.new_customer()

    def new_customer(self):
        """Clear form for new customer entry"""
        self.current_customer_id = None
        self.name_input.clear()
        self.phone_input.clear()
        self.email_input.clear()
        self.address_input.clear()
        self.notes_input.clear()
        self.delete_btn.setEnabled(False)
        self.name_input.setFocus()

    def load_selected_customer(self):
        """Load selected customer from table into form"""
        selected = self.table.selectedItems()
        if not selected:
            return

        row = self.table.row(selected[0])
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            name = self.table.item(row, 0).text()
            cur.execute(
                """
                SELECT client_id, company_name, primary_phone, email, address_line1, contact_info
                FROM clients
                WHERE company_name = %s
                LIMIT 1
                """,
                (name,)
            )
            result = cur.fetchone()
            if result:
                self.current_customer_id = result[0]
                self.name_input.setText(result[1] or "")
                self.phone_input.setText(result[2] or "")
                self.email_input.setText(result[3] or "")
                self.address_input.setText(result[4] or "")
                self.notes_input.setText(result[5] or "")
                self.delete_btn.setEnabled(True)
        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Failed to load customer: {e}")

    def load_customers(self):
        """Load customers matching search criteria"""
        search_text = self.search_input.text().strip()
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            if search_text:
                cur.execute(
                    """
                    SELECT c.client_id, c.company_name, c.primary_phone, c.email, c.address_line1,
                           COUNT(ch.charter_id) as charter_count
                    FROM clients c
                    LEFT JOIN charters ch ON ch.client_id = c.client_id
                    WHERE c.company_name ILIKE %s OR c.primary_phone ILIKE %s OR c.email ILIKE %s
                    GROUP BY c.client_id, c.company_name, c.primary_phone, c.email, c.address_line1
                    ORDER BY c.company_name
                    LIMIT 100
                    """,
                    (f"%{search_text}%", f"%{search_text}%", f"%{search_text}%")
                )
            else:
                cur.execute(
                    """
                    SELECT c.client_id, c.company_name, c.primary_phone, c.email, c.address_line1,
                           COUNT(ch.charter_id) as charter_count
                    FROM clients c
                    LEFT JOIN charters ch ON ch.client_id = c.client_id
                    GROUP BY c.client_id, c.company_name, c.primary_phone, c.email, c.address_line1
                    ORDER BY c.company_name
                    LIMIT 100
                    """
                )
            rows = cur.fetchall()
            self.table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                self.table.setItem(i, 0, QTableWidgetItem(r[1] or ""))
                self.table.setItem(i, 1, QTableWidgetItem(r[2] or ""))
                self.table.setItem(i, 2, QTableWidgetItem(r[3] or ""))
                self.table.setItem(i, 3, QTableWidgetItem(r[4] or ""))
                self.table.setItem(i, 4, QTableWidgetItem(str(r[5] or 0)))
        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Failed to load customers: {e}")

    def save_customer(self):
        """Save or update customer"""
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Customer name is required")
            self.name_input.setFocus()
            return

        phone = self.phone_input.text().strip() or None
        email = self.email_input.text().strip() or None
        address = self.address_input.toPlainText().strip() or None
        notes = self.notes_input.toPlainText().strip() or None

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            if self.current_customer_id:
                cur.execute(
                    """
                    UPDATE clients
                    SET company_name = %s, primary_phone = %s, email = %s, address_line1 = %s, contact_info = %s
                    WHERE client_id = %s
                    """,
                    (name, phone, email, address, notes, self.current_customer_id)
                )
                self.db.commit()
                QMessageBox.information(self, "Saved", f"Customer #{self.current_customer_id} updated")
            else:
                cur.execute(
                    """
                    INSERT INTO clients (company_name, primary_phone, email, address_line1, contact_info)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING client_id
                    """,
                    (name, phone, email, address, notes)
                )
                customer_id = cur.fetchone()[0]
                self.db.commit()
                self.current_customer_id = customer_id
                QMessageBox.information(self, "Saved", f"Customer #{customer_id} created")
            self.load_customers()
            self.search_input.clear()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Save Failed", f"Could not save customer:\n{e}")

    def delete_customer(self):
        """Delete customer (with confirmation)"""
        if not self.current_customer_id:
            return

        response = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete customer #{self.current_customer_id}?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if response == QMessageBox.StandardButton.Yes:
            try:
                # Rollback any failed transactions first
                try:
                    self.db.rollback()
                except:
                    pass
                
                cur = self.db.get_cursor()
                cur.execute("DELETE FROM clients WHERE client_id = %s", (self.current_customer_id,))
                self.db.commit()
                QMessageBox.information(self, "Deleted", "Customer deleted")
                self.new_customer()
                self.load_customers()
            except Exception as e:
                self.db.rollback()
                QMessageBox.critical(self, "Delete Failed", f"Could not delete customer:\n{e}")


# ============================================================================
# MAIN APPLICATION WINDOW
# ============================================================================

class MainWindow(QMainWindow):
    """Main application window with tab-based interface"""
    
    def __init__(self, db: Optional[DatabaseConnection] = None, auth_user: Optional[Dict] = None):
        print("MainWindow.__init__ START", flush=True)
        super().__init__()
        print("  1. super().__init__() OK", flush=True)

        self.auth_user = auth_user or {}
        user_suffix = f" - {self.auth_user.get('username')}" if self.auth_user.get("username") else ""
        self.setWindowTitle(f"Arrow Limousine Management System (Desktop){user_suffix}")
        self.setGeometry(50, 50, 1600, 1000)
        self._loading_receipts = False
        self._current_receipt_filters = None
        print("  2. Basic init OK", flush=True)
        
        # Initialize database
        try:
            print("  3. Creating DatabaseConnection...", flush=True)
            self.db = db if db else DatabaseConnection()
            print("  4. DatabaseConnection OK", flush=True)
        except Exception as e:
            print(f"  ❌ Database Error: {e}", flush=True)
            QMessageBox.critical(self, "Database Error", f"Cannot connect to database:\n{e}")
            sys.exit(1)
        
        print("  5. Creating central widget...", flush=True)
        # Wrapper widget to host global search + tabs
        central = QWidget()
        central_layout = QVBoxLayout()
        central_layout.setContentsMargins(5, 5, 5, 5)
        central_layout.setSpacing(6)

        # Global search bar (multi-table)
        search_bar = QHBoxLayout()
        search_bar.setSpacing(6)
        search_label = QLabel("Global Search:")
        self.global_search_input = QLineEdit()
        self.global_search_input.setPlaceholderText("Search receipts, charters, clients...")
        self.global_search_button = QPushButton("Search")
        self.global_search_button.clicked.connect(self.global_search)
        search_bar.addWidget(search_label)
        search_bar.addWidget(self.global_search_input, 1)
        search_bar.addWidget(self.global_search_button)
        central_layout.addLayout(search_bar)
        print("  6. Search bar OK", flush=True)

        # Create tab interface
        print("  7. Creating main QTabWidget...", flush=True)
        self.tabs = QTabWidget()
        central_layout.addWidget(self.tabs)
        central.setLayout(central_layout)
        self.setCentralWidget(central)
        self.status_bar = QStatusBar()
        user_display = self.auth_user.get("username", "Guest")
        role_display = self.auth_user.get("role", "unknown")
        self.status_bar.showMessage(f"User: {user_display} | Role: {role_display}")
        self.setStatusBar(self.status_bar)
        
        # Session timeout (30 minutes of inactivity)
        self._last_activity = datetime.now()
        self._session_timer = QTimer()
        self._session_timer.timeout.connect(self._check_session_timeout)
        self._session_timer.start(60000)  # Check every minute
        
        # Add logout menu
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        logout_action = QAction("Logout", self)
        logout_action.triggered.connect(self._logout)
        file_menu.addAction(logout_action)
        
        print("  8. Main tab widget created", flush=True)
        
        # Step 2 & 3: Create mega menu and add as first tab
        print("  9. Creating MegaMenuWidget...", flush=True)
        try:
            self.mega_menu = MegaMenuWidget(
                preferences_file=Path.home() / ".limo_dashboard_prefs.json"
            )
            self.mega_menu.widget_selected.connect(self.launch_dashboard_from_menu)
            self.tabs.insertTab(0, self.mega_menu, "🗂️ Navigator")
            print("  10. MegaMenuWidget OK", flush=True)
        except Exception as e:
            print(f"  ❌ MegaMenuWidget Error: {e}", flush=True)
            raise

        # Report explorer tab (query/report style)
        print("  11. Creating ReportExplorerWidget...", flush=True)
        try:
            self.report_explorer = ReportExplorerWidget()
            self.report_explorer.report_selected.connect(self.launch_dashboard_from_menu)
            self.tabs.insertTab(1, self.report_explorer, "📑 Reports")
            print("  12. ReportExplorerWidget OK", flush=True)
        except Exception as e:
            print(f"  ❌ ReportExplorerWidget Error: {e}", flush=True)
            raise
        
        # Consolidated parent tabs with sub-tabs
        print("  13. Creating Operations tab...", flush=True)
        try:
            self.tabs.addTab(self.create_operations_parent_tab(), "🚀 Operations")
            print("  14. Operations tab OK", flush=True)
        except Exception as e:
            print(f"  ❌ Operations tab Error: {e}", flush=True)
            raise
        
        print("  15. Creating Fleet Management tab...", flush=True)
        try:
            self.tabs.addTab(self.create_fleet_people_parent_tab(), "🚗 Fleet Management")
            print("  16. Fleet Management tab OK", flush=True)
        except Exception as e:
            print(f"  ❌ Fleet Management tab Error: {e}", flush=True)
            raise
        
        print("  17. Creating Accounting tab...", flush=True)
        try:
            self.tabs.addTab(self.create_accounting_parent_tab(), "💰 Accounting & Finance")
            print("  18. Accounting tab OK", flush=True)
        except Exception as e:
            print(f"  ❌ Accounting tab Error: {e}", flush=True)
            raise
        
        print("  19. Creating Admin tab...", flush=True)
        try:
            admin_tab = self.create_admin_parent_tab()
            admin_index = self.tabs.addTab(admin_tab, "⚙️ Admin & Settings")
            allowed_admin_roles = {"admin", "management", "manager", "super_user"}
            if self.auth_user and str(self.auth_user.get("role", "")).lower() not in allowed_admin_roles:
                self.tabs.setTabEnabled(admin_index, False)
            print("  20. Admin tab OK", flush=True)
        except Exception as e:
            print(f"  ❌ Admin tab Error: {e}", flush=True)
            raise
        
        # ============================================================================
        # PHASE 1 UX UPGRADES - KEYBOARD SHORTCUTS
        # ============================================================================
        # Global keyboard shortcuts for power users
        QShortcut(QKeySequence("Ctrl+N"), self, self.new_receipt)  # New receipt
        QShortcut(QKeySequence("Ctrl+S"), self, self.save_current_form)  # Save
        QShortcut(QKeySequence("Ctrl+F"), self, self.open_find)  # Find
        QShortcut(QKeySequence("Ctrl+E"), self, self.export_table)  # Export
        QShortcut(QKeySequence("Ctrl+P"), self, self.print_document)  # Print
        QShortcut(QKeySequence("Ctrl+Z"), self, self.undo_action)  # Undo (stub)
        QShortcut(QKeySequence("Ctrl+D"), self, self.duplicate_record)  # Duplicate
        QShortcut(QKeySequence("Delete"), self, self.delete_record)  # Delete
        QShortcut(QKeySequence("F5"), self, self.refresh_data)  # Refresh
        QShortcut(QKeySequence("Escape"), self, self.close_current_tab)  # Close tab
        
        self.show()
    
    # ============================================================================
    # KEYBOARD SHORTCUT HANDLERS
    # ============================================================================
    def new_receipt(self):
        """Ctrl+N: Create new receipt"""
        # Navigate to Receipts tab and clear form
        self.tabs.setCurrentIndex(2)  # Accounting tab
        QMessageBox.information(self, "New Receipt", "New receipt form ready\n[Focus on Receipt entry area]")
    
    def save_current_form(self):
        """Ctrl+S: Save current form"""
        QMessageBox.information(self, "Save", "Saving current form...\n[Implementation context-specific]")
    
    def export_table(self):
        """Ctrl+E: Export current table"""
        QMessageBox.information(self, "Export", "Exporting table to CSV...\n[Full implementation pending]")
    
    def print_document(self):
        """Ctrl+P: Print current view - routes to appropriate print function"""
        current_tab = self.tabs.currentWidget()
        if not current_tab:
            QMessageBox.information(self, "Print", "No document to print")
            return
        
        # Determine what to print based on current tab
        tab_name = self.tabs.tabText(self.tabs.currentIndex())
        
        if "Charter" in tab_name or "Booking" in tab_name:
            # Show print options for charter
            reply = QMessageBox.question(
                self, "Print Charter",
                "What would you like to print?\n\n"
                "Click 'Yes' for Invoice\n"
                "Click 'No' for Confirmation",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.print_invoice()
            else:
                self.print_confirmation()
        elif "Quote" in tab_name:
            QMessageBox.information(self, "Print", "Use the Quote tab's Print Quote button")
        elif "Beverage" in tab_name:
            QMessageBox.information(self, "Print", "Use beverage print options in the charter form")
        else:
            QMessageBox.information(self, "Print", f"Printing for {tab_name} tab\n[Custom printing to be implemented]")
    
    def undo_action(self):
        """Ctrl+Z: Undo last action"""
        QMessageBox.information(self, "Undo", "Undo functionality coming soon\n[Undo stack pending]")
    
    def duplicate_record(self):
        """Ctrl+D: Duplicate selected record"""
        QMessageBox.information(self, "Duplicate", "Duplicate record...\n[Full implementation pending]")
    
    def delete_record(self):
        """Delete: Delete selected record"""
        reply = QMessageBox.question(self, "Delete", "Delete selected record? This cannot be undone.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(self, "Deleted", "Record deleted.\n[Full implementation pending]")
    
    def close_current_tab(self):
        """Escape: Close current tab"""
        current = self.tabs.currentIndex()
        if current > 0:  # Don't close Navigator
            self.tabs.removeTab(current)
    
    def _check_session_timeout(self):
        """Check for session timeout (30 min inactivity)"""
        if (datetime.now() - self._last_activity).total_seconds() > 1800:  # 30 min
            QMessageBox.warning(self, "Session Timeout", "Your session has timed out due to inactivity.")
            self._logout()
    
    def _logout(self):
        """Logout and return to login screen"""
        reply = QMessageBox.question(
            self, "Logout",
            "Are you sure you want to logout?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.close()
            QApplication.quit()
    
    def mousePressEvent(self, event):
        """Track user activity"""
        self._last_activity = datetime.now()
        super().mousePressEvent(event)
    
    def keyPressEvent(self, event):
        """Track user activity"""
        self._last_activity = datetime.now()
        super().keyPressEvent(event)
    
    def safe_add_tab(self, tabs: QTabWidget, tab_widget: QWidget, tab_name: str) -> None:
        """
        Safely add a tab with error handling.
        If widget creation fails, shows error message instead of crashing.
        """
        try:
            if tab_widget is None:
                raise ValueError(f"Widget creation returned None for {tab_name}")
            tabs.addTab(tab_widget, tab_name)
        except Exception as e:
            # Create error label if widget fails
            error_label = QLabel(f"❌ Error loading {tab_name}:\n{str(e)[:100]}")
            error_label.setStyleSheet("color: red; font-weight: bold; padding: 20px;")
            error_label.setWordWrap(True)
            tabs.addTab(error_label, tab_name)
            print(f"⚠️  Error loading {tab_name}: {e}")
    
    def launch_dashboard_from_menu(self, class_name: str, display_name: str):
        """Step 4: Signal handler to launch dashboard from mega menu"""
        try:
            import dashboards_core, dashboards_operations, dashboards_predictive
            import dashboards_optimization, dashboards_customer, dashboards_analytics, dashboards_ml
            import accounting_reports, payroll_entry_widget, wcb_rate_widget, roe_form_widget
            
            all_modules = [
                dashboards_core, dashboards_operations, dashboards_predictive,
                dashboards_optimization, dashboards_customer, dashboards_analytics, dashboards_ml,
                accounting_reports,
                payroll_entry_widget,
                wcb_rate_widget,
                roe_form_widget,
            ]
            
            widget_class = None
            for module in all_modules:
                widget_class = getattr(module, class_name, None)
                if widget_class:
                    break
            
            if widget_class:
                widget = widget_class(self.db)
                tab_idx = self.tabs.addTab(widget, display_name)
                self.tabs.setCurrentIndex(tab_idx)
                print(f"✅ Launched: {display_name} ({class_name})")
            else:
                QMessageBox.warning(self, "Widget Not Found", f"Cannot find widget class: {class_name}")
                print(f"❌ Widget not found: {class_name}")
        except Exception as e:
            QMessageBox.critical(self, "Launch Error", f"Error launching {display_name}:\n{e}")
            print(f"❌ Error launching {display_name}: {e}")
    
    def create_operations_parent_tab(self) -> QWidget:
        """Consolidated Operations: Charters, Dispatch, Customers, Documents"""
        parent = QWidget()
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        
        tabs = QTabWidget()
        tabs.addTab(self.create_charter_tab(), "📅 Bookings")
        tabs.addTab(self.create_enhanced_charter_tab(), "📋 Charter List")
        tabs.addTab(self.create_dispatch_tab(), "📡 Dispatch")
        tabs.addTab(self.create_customers_tab(), "👥 Customers")
        tabs.addTab(self.create_enhanced_client_tab(), "🏢 Client List")
        tabs.addTab(self.create_documents_tab(), "📄 Documents")
        
        layout.addWidget(tabs)
        return parent
    
    def create_fleet_people_parent_tab(self) -> QWidget:
        """Consolidated Fleet & People: Vehicles, Employees"""
        parent = QWidget()
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        
        tabs = QTabWidget()
        tabs.addTab(self.create_vehicles_tab(), "🚐 Vehicles")
        tabs.addTab(self.create_enhanced_vehicle_tab(), "🚗 Fleet List")
        tabs.addTab(self.create_employees_tab(), "👔 Employees")
        tabs.addTab(self.create_enhanced_employee_tab(), "👥 Employee List")
        tabs.addTab(self.create_payroll_entry_tab(), "🧾 Payroll Entry")
        
        layout.addWidget(tabs)
        return parent
    
    def create_accounting_parent_tab(self) -> QWidget:
        """Consolidated Accounting & Finance: Receipts, Tax, Business, Financial Reports"""
        parent = QWidget()
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        
        tabs = QTabWidget()
        
        # Create accounting widget and pass parent tabs for navigation
        accounting_receipts = self.create_accounting_tab_with_parent(tabs)
        
        self.safe_add_tab(tabs, accounting_receipts, "💰 Receipts & Invoices")
        self.safe_add_tab(tabs, VendorInvoiceManager(self.db), "📋 Vendor Invoice Manager")
        self.safe_add_tab(tabs, self.create_tax_management_tab(), "🏛️ Tax Management")
        self.safe_add_tab(tabs, WCBRateEntryWidget(self.db), "🛡️ WCB Rates")
        self.safe_add_tab(tabs, self.create_business_entity_tab(), "🏢 Business Entity")
        self.safe_add_tab(tabs, AssetManagementWidget(), "📦 Asset Inventory")
        self.safe_add_tab(tabs, self.create_reports_tab(), "📊 Financial Reports")
        
        layout.addWidget(tabs)
        return parent
    
    def create_admin_parent_tab(self) -> QWidget:
        """Consolidated Admin: Settings and System Controls"""
        parent = QWidget()
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        
        tabs = QTabWidget()
        self.safe_add_tab(tabs, self.create_admin_tab(), "⚙️ Admin Controls")
        self.safe_add_tab(tabs, self.create_settings_tab(), "🔧 Settings")
        self.safe_add_tab(tabs, BeverageManagementWidget(self.db), "🍷 Beverage Management")
        
        layout.addWidget(tabs)
        return parent
    
    def create_operations_parent_tab(self) -> QWidget:
        """Consolidated Operations: Charters, Dispatch, Customers, Documents"""
        parent = QWidget()
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        
        tabs = QTabWidget()
        tabs.addTab(self.create_charter_tab(), "📅 Bookings")
        tabs.addTab(self.create_enhanced_charter_tab(), "📋 Charter List")
        tabs.addTab(self.create_dispatch_tab(), "📡 Dispatch")
        tabs.addTab(self.create_customers_tab(), "👥 Customers")
        tabs.addTab(self.create_enhanced_client_tab(), "🏢 Client List")
        tabs.addTab(self.create_documents_tab(), "📄 Documents")
        
        layout.addWidget(tabs)
        return parent
    
    def create_fleet_people_parent_tab(self) -> QWidget:
        """Consolidated Fleet & People: Vehicles, Employees"""
        parent = QWidget()
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        
        tabs = QTabWidget()
        tabs.addTab(self.create_vehicles_tab(), "🚐 Vehicles")
        tabs.addTab(self.create_enhanced_vehicle_tab(), "🚗 Fleet List")
        tabs.addTab(self.create_employees_tab(), "👔 Employees")
        tabs.addTab(self.create_enhanced_employee_tab(), "👥 Employee List")
        
        layout.addWidget(tabs)
        return parent

    def create_charter_tab(self) -> QWidget:
        """Charter/booking management tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        self.charter_form = CharterFormWidget(self.db)
        layout.addWidget(self.charter_form)
        
        widget.setLayout(layout)
        return widget
    
    def create_customers_tab(self) -> QWidget:
        """Customer management tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        self.customers_widget = CustomersWidget(self.db)
        layout.addWidget(self.customers_widget)
        widget.setLayout(layout)
        return widget
    
    def create_vehicles_tab(self) -> QWidget:
        """Vehicle management tab with maintenance tracking"""
        widget = QWidget()
        layout = QVBoxLayout()
        self.vehicles_widget = VehicleManagementWidget(self.db)
        layout.addWidget(self.vehicles_widget)
        widget.setLayout(layout)
        return widget
    
    def create_employees_tab(self) -> QWidget:
        """Employee management tab with HOS compliance"""
        widget = QWidget()
        layout = QVBoxLayout()
        self.employees_widget = EmployeeManagementWidget(self.db)
        layout.addWidget(self.employees_widget)
        widget.setLayout(layout)
        return widget

    def create_payroll_entry_tab(self) -> QWidget:
        """Manual payroll entry tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        self.payroll_entry_widget = PayrollEntryWidget(self.db)
        layout.addWidget(self.payroll_entry_widget)
        widget.setLayout(layout)
        return widget
    
    def create_dispatch_tab(self) -> QWidget:
        """Dispatch management and real-time booking"""
        widget = QWidget()
        layout = QVBoxLayout()
        self.dispatch_widget = DispatchManagementWidget(self.db)
        layout.addWidget(self.dispatch_widget)
        widget.setLayout(layout)
        return widget
    
    def create_documents_tab(self) -> QWidget:
        """Document management and upload"""
        widget = QWidget()
        layout = QVBoxLayout()
        self.documents_widget = DocumentManagementWidget(self.db)
        layout.addWidget(self.documents_widget)
        widget.setLayout(layout)
        return widget
    
    def create_admin_tab(self) -> QWidget:
        """Admin and system management"""
        widget = QWidget()
        layout = QVBoxLayout()
        self.admin_widget = AdminManagementWidget(self.db)
        layout.addWidget(self.admin_widget)
        widget.setLayout(layout)
        return widget
    
    def create_enhanced_charter_tab(self) -> QWidget:
        """Enhanced charter list with drill-down capability"""
        widget = QWidget()
        layout = QVBoxLayout()
        self.enhanced_charter_widget = EnhancedCharterListWidget(self.db)
        layout.addWidget(self.enhanced_charter_widget)
        widget.setLayout(layout)
        return widget
    
    def create_enhanced_employee_tab(self) -> QWidget:
        """Enhanced employee list with comprehensive drill-down"""
        widget = QWidget()
        layout = QVBoxLayout()
        self.enhanced_employee_widget = EnhancedEmployeeListWidget(self.db)
        layout.addWidget(self.enhanced_employee_widget)
        widget.setLayout(layout)
        return widget
    
    def create_enhanced_vehicle_tab(self) -> QWidget:
        """Enhanced vehicle list with maintenance and cost tracking"""
        widget = QWidget()
        layout = QVBoxLayout()
        self.enhanced_vehicle_widget = EnhancedVehicleListWidget(self.db)
        layout.addWidget(self.enhanced_vehicle_widget)
        widget.setLayout(layout)
        return widget
    
    def create_enhanced_client_tab(self) -> QWidget:
        """Enhanced client list with payment and charter history"""
        widget = QWidget()
        layout = QVBoxLayout()
        self.enhanced_client_widget = EnhancedClientListWidget(self.db)
        layout.addWidget(self.enhanced_client_widget)
        widget.setLayout(layout)
        return widget
    
    def create_tax_management_tab(self) -> QWidget:
        """CRA Tax Management - Multi-year tax filing, payroll, GST, owner income tracking"""
        widget = QWidget()
        layout = QVBoxLayout()
        self.tax_management_widget = TaxManagementWidget(self.db)
        layout.addWidget(self.tax_management_widget)
        widget.setLayout(layout)
        return widget
    
    def create_business_entity_tab(self) -> QWidget:
        """Business entity management - overall company view"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Add button to open business entity dialog
        header = QLabel("<h2>🏢 Business Entity Management</h2>")
        layout.addWidget(header)
        
        info_label = QLabel("""
        <p>Manage Arrow Limousine as a business entity:</p>
        <ul>
        <li>Company registration and legal documents</li>
        <li>Financial overview (P&L, balance sheet)</li>
        <li>Tax filings and compliance</li>
        <li>Business licenses and insurance policies</li>
        <li>Bank accounts and credit facilities</li>
        <li>Loans, assets, and vendor relationships</li>
        <li>Strategic planning and goals</li>
        </ul>
        """)
        layout.addWidget(info_label)
        
        open_btn = QPushButton("🏢 Open Business Management Dashboard")
        open_btn.setMinimumHeight(50)
        open_btn.setStyleSheet("font-size: 14px; font-weight: bold;")
        open_btn.clicked.connect(self.open_business_entity_dialog)
        layout.addWidget(open_btn)
        
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget
    
    def open_business_entity_dialog(self):
        """Open the business entity management dialog"""
        dialog = BusinessEntityDialog(self.db, self)
        dialog.exec()
    
    def create_accounting_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()
        self.accounting_widget = AccountingReceiptsWidget(self.db)
        layout.addWidget(self.accounting_widget)
        widget.setLayout(layout)
        return widget
    
    def create_accounting_tab_with_parent(self, parent_tabs) -> QWidget:
        """Create accounting tab with parent tabs reference for navigation"""
        widget = QWidget()
        layout = QVBoxLayout()
        self.accounting_widget = AccountingReceiptsWidget(self.db, parent_tab_widget=parent_tabs)
        layout.addWidget(self.accounting_widget)
        widget.setLayout(layout)
        return widget
    
    def create_reports_tab(self) -> QWidget:
        """Reports & analytics tab with Phase 1, 2, 3 dashboards"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create sub-tabs for different reports (11 total dashboards)
        report_tabs = QTabWidget()
        
        # ===== PHASE 1: CORE DASHBOARDS (4) =====
        # Fleet Management
        self.fleet_widget = FleetManagementWidget(self.db)
        report_tabs.addTab(self.fleet_widget, "🚐 Fleet Management")
        
        # Driver Performance
        self.driver_widget = DriverPerformanceWidget(self.db)
        report_tabs.addTab(self.driver_widget, "👤 Driver Performance")
        
        # Financial Dashboard
        self.financial_widget = FinancialDashboardWidget(self.db)
        report_tabs.addTab(self.financial_widget, "📈 Financial Reports")
        
        # Payment Reconciliation
        self.payment_widget = PaymentReconciliationWidget(self.db)
        report_tabs.addTab(self.payment_widget, "💳 Payment Reconciliation")
        
        # ===== PHASE 2: ADVANCED ANALYTICS (4) =====
        # Advanced Vehicle Analytics
        self.vehicle_analytics_widget = VehicleAnalyticsWidget(self.db)
        report_tabs.addTab(self.vehicle_analytics_widget, "🚗 Vehicle Analytics")
        
        # Employee Payroll Audit
        self.payroll_audit_widget = EmployeePayrollAuditWidget(self.db)
        report_tabs.addTab(self.payroll_audit_widget, "👔 Payroll Audit")
        
        # QuickBooks Reconciliation
        self.qb_recon_widget = QuickBooksReconciliationWidget(self.db)
        report_tabs.addTab(self.qb_recon_widget, "📊 QB Reconciliation")
        
        # Charter Analytics
        self.charter_analytics_widget = CharterAnalyticsWidget(self.db)
        report_tabs.addTab(self.charter_analytics_widget, "📈 Charter Analytics")
        
        # ===== PHASE 3: COMPLIANCE & BUDGET (3) =====
        # Compliance Tracking
        self.compliance_widget = ComplianceTrackingWidget(self.db)
        report_tabs.addTab(self.compliance_widget, "✅ Compliance")
        
        # Budget vs Actual
        self.budget_widget = BudgetAnalysisWidget(self.db)
        report_tabs.addTab(self.budget_widget, "💰 Budget vs Actual")
        
        # Insurance Tracking
        self.insurance_widget = InsuranceTrackingWidget(self.db)
        report_tabs.addTab(self.insurance_widget, "🛡️ Insurance")
        
        # ===== PHASE 4: FLEET MANAGEMENT (5) =====
        # Vehicle Fleet Cost Analysis
        self.fleet_cost_widget = VehicleFleetCostAnalysisWidget(self.db)
        report_tabs.addTab(self.fleet_cost_widget, "🚗 Fleet Cost Analysis")
        
        # Vehicle Maintenance Tracking
        self.maintenance_widget = VehicleMaintenanceTrackingWidget(self.db)
        report_tabs.addTab(self.maintenance_widget, "🔧 Maintenance Tracking")
        
        # Fuel Efficiency Tracking
        self.fuel_efficiency_widget = FuelEfficiencyTrackingWidget(self.db)
        report_tabs.addTab(self.fuel_efficiency_widget, "⛽ Fuel Efficiency")
        
        # Vehicle Utilization
        self.utilization_widget = VehicleUtilizationWidget(self.db)
        report_tabs.addTab(self.utilization_widget, "📊 Vehicle Utilization")
        
        # Fleet Age Analysis
        self.fleet_age_widget = FleetAgeAnalysisWidget(self.db)
        report_tabs.addTab(self.fleet_age_widget, "📈 Fleet Age Analysis")
        
        # ===== PHASE 5: EMPLOYEE/PAYROLL (5) =====
        # Driver Pay Analysis
        self.driver_pay_widget = DriverPayAnalysisWidget(self.db)
        report_tabs.addTab(self.driver_pay_widget, "💰 Driver Pay Analysis")
        
        # Employee Performance Metrics
        self.perf_metrics_widget = EmployeePerformanceMetricsWidget(self.db)
        report_tabs.addTab(self.perf_metrics_widget, "⭐ Performance Metrics")
        
        # Payroll Tax Compliance
        self.tax_compliance_widget = PayrollTaxComplianceWidget(self.db)
        report_tabs.addTab(self.tax_compliance_widget, "📋 Tax Compliance")
        
        # Driver Schedule Management
        self.schedule_widget = DriverScheduleManagementWidget(self.db)
        report_tabs.addTab(self.schedule_widget, "📅 Driver Schedule")
        # Driver Calendar (operational)
        self.driver_calendar_widget = DriverCalendarWidget(self.db)
        report_tabs.addTab(self.driver_calendar_widget, "🗓️ Driver Calendar")
        self.dispatcher_calendar_widget = DispatcherCalendarWidget(self.db)
        report_tabs.addTab(self.dispatcher_calendar_widget, "🗓️ Dispatcher Calendar")
        
        # ===== PHASE 6: PAYMENTS & FINANCIAL (5) =====
        # Payment Reconciliation (Advanced)
        self.payment_adv_widget = PaymentReconciliationAdvancedWidget(self.db)
        report_tabs.addTab(self.payment_adv_widget, "💳 Payments (Advanced)")
        
        # AR Aging Dashboard
        self.ar_aging_widget = ARAgingDashboardWidget(self.db)
        report_tabs.addTab(self.ar_aging_widget, "📊 AR Aging")
        
        # Cash Flow Report
        self.cashflow_widget = CashFlowReportWidget(self.db)
        report_tabs.addTab(self.cashflow_widget, "💸 Cash Flow")
        
        # Profit & Loss Report
        self.pl_widget = ProfitLossReportWidget(self.db)
        report_tabs.addTab(self.pl_widget, "📊 Profit & Loss")
        
        # Charter Analytics (Advanced)
        self.charter_adv_widget = CharterAnalyticsAdvancedWidget(self.db)
        report_tabs.addTab(self.charter_adv_widget, "📈 Charter Analytics+")
        
        # ===== PHASE 7: CHARTER & CUSTOMER ANALYTICS (8) =====
        # Charter Management
        self.charter_mgmt_widget = CharterManagementDashboardWidget(self.db)
        report_tabs.addTab(self.charter_mgmt_widget, "📅 Charter Management")
        
        # Customer Lifetime Value
        self.clv_widget = CustomerLifetimeValueWidget(self.db)
        report_tabs.addTab(self.clv_widget, "💰 Customer LTV")
        
        # Charter Cancellation Analysis
        self.cancel_widget = CharterCancellationAnalysisWidget(self.db)
        report_tabs.addTab(self.cancel_widget, "📊 Cancellation Analysis")
        
        # Booking Lead Time
        self.leadtime_widget = BookingLeadTimeAnalysisWidget(self.db)
        report_tabs.addTab(self.leadtime_widget, "⏱️ Lead Time")
        
        # Customer Segmentation
        self.segment_widget = CustomerSegmentationWidget(self.db)
        report_tabs.addTab(self.segment_widget, "🎯 Segmentation")
        
        # Route Profitability
        self.route_widget = RouteProfitabilityWidget(self.db)
        report_tabs.addTab(self.route_widget, "🛣️ Route Profitability")
        
        # Geographic Distribution
        self.geo_widget = GeographicRevenueDistributionWidget(self.db)
        report_tabs.addTab(self.geo_widget, "🗺️ Geographic Revenue")
        
        # ===== PHASE 8: COMPLIANCE, MAINTENANCE, MONITORING (8) =====
        # HOS Compliance
        self.hos_widget = HosComplianceTrackingWidget(self.db)
        report_tabs.addTab(self.hos_widget, "⚖️ HOS Compliance")
        
        # Advanced Maintenance
        self.maint_adv_widget = AdvancedMaintenanceScheduleWidget(self.db)
        report_tabs.addTab(self.maint_adv_widget, "🔧 Maintenance (Advanced)")
        
        # Safety Incidents
        self.safety_widget = SafetyIncidentTrackingWidget(self.db)
        report_tabs.addTab(self.safety_widget, "⚠️ Safety Incidents")
        
        # Vendor Performance
        self.vendor_widget = VendorPerformanceWidget(self.db)
        report_tabs.addTab(self.vendor_widget, "🤝 Vendor Performance")
        
        # Real-Time Monitoring
        self.monitor_widget = RealTimeFleetMonitoringWidget(self.db)
        report_tabs.addTab(self.monitor_widget, "📡 Fleet Monitoring")
        
        # System Health
        self.health_widget = SystemHealthDashboardWidget(self.db)
        report_tabs.addTab(self.health_widget, "🏥 System Health")
        
        # Data Quality Audit
        self.quality_widget = DataQualityAuditWidget(self.db)
        report_tabs.addTab(self.quality_widget, "📋 Data Quality")
        
        # ===== PHASE 9: PREDICTIVE & ADVANCED ANALYTICS (15) =====
        # Demand Forecasting
        self.demand_widget = DemandForecastingWidget(self.db)
        report_tabs.addTab(self.demand_widget, "📈 Demand Forecasting")
        
        # Churn Prediction
        self.churn_widget = ChurnPredictionWidget(self.db)
        report_tabs.addTab(self.churn_widget, "⚠️ Churn Prediction")
        
        # Revenue Optimization
        self.revenue_opt_widget = RevenueOptimizationWidget(self.db)
        report_tabs.addTab(self.revenue_opt_widget, "💰 Revenue Optimization")
        
        # Customer Worth (RFM)
        self.customer_worth_widget = CustomerWorthWidget(self.db)
        report_tabs.addTab(self.customer_worth_widget, "⭐ Customer Worth (RFM)")
        
        # Next Best Action
        self.nba_widget = NextBestActionWidget(self.db)
        report_tabs.addTab(self.nba_widget, "🎯 Next Best Action")
        
        # Seasonality Analysis
        self.seasonality_widget = SeasonalityAnalysisWidget(self.db)
        report_tabs.addTab(self.seasonality_widget, "📊 Seasonality")
        
        # Cost Behavior Analysis
        self.cost_behavior_widget = CostBehaviorAnalysisWidget(self.db)
        report_tabs.addTab(self.cost_behavior_widget, "💡 Cost Behavior")
        
        # Break-Even Analysis
        self.breakeven_widget = BreakEvenAnalysisWidget(self.db)
        report_tabs.addTab(self.breakeven_widget, "📊 Break-Even")
        
        # Email Campaign Performance
        self.email_widget = EmailCampaignPerformanceWidget(self.db)
        report_tabs.addTab(self.email_widget, "📧 Email Campaigns")
        
        # Customer Journey
        self.journey_widget = CustomerJourneyAnalysisWidget(self.db)
        report_tabs.addTab(self.journey_widget, "🛣️ Customer Journey")
        
        # Competitive Intelligence
        self.competitive_widget = CompetitiveIntelligenceWidget(self.db)
        report_tabs.addTab(self.competitive_widget, "🎯 Competitive Intel")
        
        # Regulatory Compliance
        self.regulatory_widget = RegulatoryComplianceTrackingWidget(self.db)
        report_tabs.addTab(self.regulatory_widget, "⚖️ Regulatory Compliance")
        
        # CRA Compliance Report
        self.cra_widget = CRAComplianceReportWidget(self.db)
        report_tabs.addTab(self.cra_widget, "📋 CRA Compliance")
        
        # Employee Productivity
        self.productivity_widget = EmployeeProductivityTrackingWidget(self.db)
        report_tabs.addTab(self.productivity_widget, "👥 Employee Productivity")
        
        # Promotional Effectiveness
        self.promo_widget = PromotionalEffectivenessWidget(self.db)
        report_tabs.addTab(self.promo_widget, "🎁 Promotional Effectiveness")
        
        # ===== PHASE 10: REAL-TIME & ADVANCED CHARTS (13) =====
        # Real-Time Fleet Tracking
        self.realtime_tracking_widget = RealTimeFleetTrackingMapWidget(self.db)
        report_tabs.addTab(self.realtime_tracking_widget, "🗺️ Fleet Tracking Map")
        
        # Live Dispatch Monitor
        self.dispatch_widget = LiveDispatchMonitorWidget(self.db)
        report_tabs.addTab(self.dispatch_widget, "📡 Live Dispatch")
        
        # Mobile Customer Portal
        self.mobile_customer_widget = MobileCustomerPortalWidget(self.db)
        report_tabs.addTab(self.mobile_customer_widget, "📱 Mobile Portal")
        
        # Mobile Driver Dashboard
        self.mobile_driver_widget = MobileDriverDashboardWidget(self.db)
        report_tabs.addTab(self.mobile_driver_widget, "🚗 Mobile Driver")
        
        # API Endpoint Performance
        self.api_perf_widget = APIEndpointPerformanceWidget(self.db)
        report_tabs.addTab(self.api_perf_widget, "⚙️ API Performance")
        
        # Third Party Integrations
        self.integration_widget = ThirdPartyIntegrationMonitorWidget(self.db)
        report_tabs.addTab(self.integration_widget, "🔗 Integrations")
        
        # Advanced Time Series
        self.timeseries_widget = AdvancedTimeSeriesChartWidget(self.db)
        report_tabs.addTab(self.timeseries_widget, "📊 Time Series")
        
        # Interactive Heatmap
        self.heatmap_widget = InteractiveHeatmapWidget(self.db)
        report_tabs.addTab(self.heatmap_widget, "🔥 Heatmap")
        
        # Comparative Analysis
        self.comparative_widget = ComparativeAnalysisChartWidget(self.db)
        report_tabs.addTab(self.comparative_widget, "🔄 Comparative Analysis")
        
        # Distribution Analysis
        self.distribution_widget = DistributionAnalysisChartWidget(self.db)
        report_tabs.addTab(self.distribution_widget, "📈 Distribution")
        
        # Correlation Matrix
        self.correlation_widget = CorrelationMatrixWidget(self.db)
        report_tabs.addTab(self.correlation_widget, "🔗 Correlation Matrix")
        
        # Automation Workflows
        self.automation_widget = AutomationWorkflowsWidget(self.db)
        report_tabs.addTab(self.automation_widget, "⚡ Automation")
        
        # Alert Management
        self.alerts_widget = AlertManagementWidget(self.db)
        report_tabs.addTab(self.alerts_widget, "🔔 Alerts")
        
        # ===== PHASE 11: ADVANCED SCHEDULING & OPTIMIZATION (12) =====
        # Driver Shift Optimization
        self.shift_opt_widget = DriverShiftOptimizationWidget(self.db)
        report_tabs.addTab(self.shift_opt_widget, "📅 Shift Optimization")
        
        # Route Scheduling
        self.route_sched_widget = RouteSchedulingWidget(self.db)
        report_tabs.addTab(self.route_sched_widget, "🛣️ Route Scheduling")
        
        # Vehicle Assignment Planner
        self.vehicle_assign_widget = VehicleAssignmentPlannerWidget(self.db)
        report_tabs.addTab(self.vehicle_assign_widget, "🚗 Vehicle Assignment")
        
        # Calendar Forecasting
        self.calendar_forecast_widget = CalendarForecasitngWidget(self.db)
        report_tabs.addTab(self.calendar_forecast_widget, "📆 Calendar Forecast")
        
        # Break Compliance Schedule
        self.break_compliance_widget = BreakComplianceScheduleWidget(self.db)
        report_tabs.addTab(self.break_compliance_widget, "⏰ Break Compliance")
        
        # Maintenance Scheduling
        self.maint_sched_widget = MaintenanceSchedulingWidget(self.db)
        report_tabs.addTab(self.maint_sched_widget, "🔧 Maintenance Sched")
        
        # Crew Rotation Analysis
        self.crew_rotation_widget = CrewRotationAnalysisWidget(self.db)
        report_tabs.addTab(self.crew_rotation_widget, "👥 Crew Rotation")
        
        # Load Balancing
        self.load_balance_widget = LoadBalancingOptimizerWidget(self.db)
        report_tabs.addTab(self.load_balance_widget, "⚖️ Load Balancing")
        
        # Dynamic Pricing Schedule
        self.dyn_pricing_widget = DynamicPricingScheduleWidget(self.db)
        report_tabs.addTab(self.dyn_pricing_widget, "💰 Dynamic Pricing")
        
        # Historical Patterns
        self.hist_patterns_widget = HistoricalSchedulingPatternsWidget(self.db)
        report_tabs.addTab(self.hist_patterns_widget, "📊 Historical Patterns")
        
        # Predictive Scheduling
        self.pred_sched_widget = PredictiveSchedulingWidget(self.db)
        report_tabs.addTab(self.pred_sched_widget, "🤖 Predictive Schedule")
        
        # Capacity Utilization
        self.capacity_widget = CapacityUtilizationWidget(self.db)
        report_tabs.addTab(self.capacity_widget, "📦 Capacity Planning")
        
        # ===== PHASE 12: MULTI-PROPERTY MANAGEMENT (15) =====
        # Branch Consolidation
        self.branch_consol_widget = BranchLocationConsolidationWidget(self.db)
        report_tabs.addTab(self.branch_consol_widget, "🏢 Branch Consolidation")
        
        # Inter-Branch Comparison
        self.inter_branch_widget = InterBranchPerformanceComparisonWidget(self.db)
        report_tabs.addTab(self.inter_branch_widget, "📊 Inter-Branch Comparison")
        
        # Consolidated P&L
        self.consol_pl_widget = ConsolidatedProfitLossWidget(self.db)
        report_tabs.addTab(self.consol_pl_widget, "💰 Consolidated P&L")
        
        # Resource Allocation
        self.resource_alloc_widget = ResourceAllocationAcrossPropertiesWidget(self.db)
        report_tabs.addTab(self.resource_alloc_widget, "🔄 Resource Allocation")
        
        # Cross-Branch Chartering
        self.cross_branch_widget = CrossBranchCharteringWidget(self.db)
        report_tabs.addTab(self.cross_branch_widget, "🚐 Cross-Branch")
        
        # Shared Vehicle Tracking
        self.shared_vehicle_widget = SharedVehicleTrackingWidget(self.db)
        report_tabs.addTab(self.shared_vehicle_widget, "🚗 Shared Vehicles")
        
        # Unified Inventory
        self.inventory_widget = UnifiedInventoryManagementWidget(self.db)
        report_tabs.addTab(self.inventory_widget, "📦 Unified Inventory")
        
        # Multi-Location Payroll
        self.multi_payroll_widget = MultiLocationPayrollWidget(self.db)
        report_tabs.addTab(self.multi_payroll_widget, "💳 Multi-Location Payroll")
        
        # Territory Mapping
        self.territory_widget = TerritoryMappingWidget(self.db)
        report_tabs.addTab(self.territory_widget, "🗺️ Territory Mapping")
        
        # Market Overlap
        self.overlap_widget = MarketOverlapAnalysisWidget(self.db)
        report_tabs.addTab(self.overlap_widget, "📊 Market Overlap")
        
        # Regional Performance
        self.regional_widget = RegionalPerformanceMetricsWidget(self.db)
        report_tabs.addTab(self.regional_widget, "📈 Regional Performance")
        
        # Property-Level KPIs
        self.property_kpi_widget = PropertyLevelKPIWidget(self.db)
        report_tabs.addTab(self.property_kpi_widget, "📊 Property KPIs")
        
        # Franchise Integration
        self.franchise_widget = FranchiseIntegrationWidget(self.db)
        report_tabs.addTab(self.franchise_widget, "🏢 Franchise Integration")
        
        # License Tracking
        self.license_widget = LicenseTrackingWidget(self.db)
        report_tabs.addTab(self.license_widget, "📜 License Tracking")
        
        # Operations Consolidation
        self.ops_consol_widget = OperationsConsolidationWidget(self.db)
        report_tabs.addTab(self.ops_consol_widget, "⚙️ Operations Consolidation")
        
        # Phase 13 tabs (18 widgets - Customer Portal Enhancements)
        
        # Self-Service Booking Portal
        self.booking_portal_widget = SelfServiceBookingPortalWidget(self.db)
        report_tabs.addTab(self.booking_portal_widget, "📱 Self-Service Booking")
        
        # Trip History
        self.trip_history_widget = TripHistoryWidget(self.db)
        report_tabs.addTab(self.trip_history_widget, "📜 Trip History")
        
        # Invoice & Receipt Management
        self.invoice_widget = InvoiceReceiptManagementWidget(self.db)
        report_tabs.addTab(self.invoice_widget, "📄 Invoice Management")
        
        # Account Settings
        self.account_settings_widget = AccountSettingsWidget(self.db)
        report_tabs.addTab(self.account_settings_widget, "⚙️ Account Settings")
        
        # Loyalty Program Tracking
        self.loyalty_widget = LoyaltyProgramTrackingWidget(self.db)
        report_tabs.addTab(self.loyalty_widget, "🎁 Loyalty Program")
        
        # Referral Analytics
        self.referral_widget = ReferralAnalyticsWidget(self.db)
        report_tabs.addTab(self.referral_widget, "👥 Referral Analytics")
        
        # Subscription Management
        self.subscription_widget = SubscriptionManagementWidget(self.db)
        report_tabs.addTab(self.subscription_widget, "🔄 Subscription Management")
        
        # Corporate Account Management
        self.corporate_widget = CorporateAccountManagementWidget(self.db)
        report_tabs.addTab(self.corporate_widget, "🏢 Corporate Accounts")
        
        # Recurring Booking Management
        self.recurring_widget = RecurringBookingManagementWidget(self.db)
        report_tabs.addTab(self.recurring_widget, "📅 Recurring Bookings")
        
        # Automated Quote Generator
        self.quote_widget = AutomatedQuoteGeneratorWidget(self.db)
        report_tabs.addTab(self.quote_widget, "💰 Quote Generator")
        
        # Chat Integration
        self.chat_widget = ChatIntegrationWidget(self.db)
        report_tabs.addTab(self.chat_widget, "💬 Customer Chat")
        
        # Support Ticket Management
        self.support_widget = SupportTicketManagementWidget(self.db)
        report_tabs.addTab(self.support_widget, "🎫 Support Tickets")
        
        # Rating & Review Management
        self.rating_widget = RatingReviewManagementWidget(self.db)
        report_tabs.addTab(self.rating_widget, "⭐ Ratings & Reviews")
        
        # Saved Preferences
        self.preferences_widget = SavedPreferencesWidget(self.db)
        report_tabs.addTab(self.preferences_widget, "❤️ Saved Preferences")
        
        # Fleet Preferences
        self.fleet_pref_widget = FleetPreferencesWidget(self.db)
        report_tabs.addTab(self.fleet_pref_widget, "🚗 Fleet Preferences")
        
        # Driver Feedback
        self.driver_feedback_widget = DriverFeedbackWidget(self.db)
        report_tabs.addTab(self.driver_feedback_widget, "👤 Driver Feedback")
        
        # Customer Communications
        self.comms_widget = CustomerCommunicationsWidget(self.db)
        report_tabs.addTab(self.comms_widget, "📧 Communications")
        
        # Phase 14 tabs (15 widgets - Advanced Reporting)
        
        # Custom Report Builder
        self.custom_report_widget = CustomReportBuilderWidget(self.db)
        report_tabs.addTab(self.custom_report_widget, "🛠️ Custom Reports")
        
        # Executive Dashboard
        self.executive_widget = ExecutiveDashboardWidget(self.db)
        report_tabs.addTab(self.executive_widget, "👔 Executive Dashboard")
        
        # Budget vs Actual
        self.budget_widget = BudgetVsActualWidget(self.db)
        report_tabs.addTab(self.budget_widget, "💵 Budget vs Actual")
        
        # Trend Analysis
        self.trend_widget = TrendAnalysisWidget(self.db)
        report_tabs.addTab(self.trend_widget, "📊 Trend Analysis")
        
        # Anomaly Detection
        self.anomaly_widget = AnomalyDetectionWidget(self.db)
        report_tabs.addTab(self.anomaly_widget, "🚨 Anomaly Detection")
        
        # Segmentation Analysis
        self.segment_widget = SegmentationAnalysisWidget(self.db)
        report_tabs.addTab(self.segment_widget, "📍 Segmentation Analysis")
        
        # Competitive Analysis
        self.competitive_widget = CompetitiveAnalysisWidget(self.db)
        report_tabs.addTab(self.competitive_widget, "⚔️ Competitive Analysis")
        
        # Operational Metrics
        self.operational_widget = OperationalMetricsWidget(self.db)
        report_tabs.addTab(self.operational_widget, "📈 Operational Metrics")
        
        # Data Quality Report
        self.quality_widget = DataQualityReportWidget(self.db)
        report_tabs.addTab(self.quality_widget, "✅ Data Quality")
        
        # ROI Analysis
        self.roi_widget = ROIAnalysisWidget(self.db)
        report_tabs.addTab(self.roi_widget, "💰 ROI Analysis")
        
        # Forecasting
        self.forecast_widget = ForecastingWidget(self.db)
        report_tabs.addTab(self.forecast_widget, "🔮 Forecasting")
        
        # Report Scheduler
        self.scheduler_widget = ReportSchedulerWidget(self.db)
        report_tabs.addTab(self.scheduler_widget, "📅 Report Scheduler")
        
        # Compliance Reporting
        self.compliance_widget = ComplianceReportingWidget(self.db)
        report_tabs.addTab(self.compliance_widget, "📋 Compliance Reporting")
        
        # Export Management
        self.export_widget = ExportManagementWidget(self.db)
        report_tabs.addTab(self.export_widget, "💾 Export Management")
        
        # Audit Trail
        self.audit_widget = AuditTrailWidget(self.db)
        report_tabs.addTab(self.audit_widget, "🔐 Audit Trail")
        
        # Phase 15 tabs (10 widgets - ML Integration)
        
        # Demand Forecasting ML
        self.demand_ml_widget = DemandForecastingMLWidget(self.db)
        report_tabs.addTab(self.demand_ml_widget, "🤖 Demand Forecasting ML")
        
        # Churn Prediction ML
        self.churn_ml_widget = ChurnPredictionMLWidget(self.db)
        report_tabs.addTab(self.churn_ml_widget, "⚠️ Churn Prediction ML")
        
        # Pricing Optimization ML
        self.pricing_ml_widget = PricingOptimizationMLWidget(self.db)
        report_tabs.addTab(self.pricing_ml_widget, "💲 Pricing Optimization ML")
        
        # Customer Clustering ML
        self.cluster_ml_widget = CustomerClusteringMLWidget(self.db)
        report_tabs.addTab(self.cluster_ml_widget, "👥 Customer Clustering ML")
        
        # Anomaly Detection ML
        self.anomaly_ml_widget = AnomalyDetectionMLWidget(self.db)
        report_tabs.addTab(self.anomaly_ml_widget, "🚨 Anomaly Detection ML")
        
        # Recommendation Engine ML
        self.rec_ml_widget = RecommendationEngineWidget(self.db)
        report_tabs.addTab(self.rec_ml_widget, "🎯 Recommendation Engine ML")
        
        # Resource Optimization ML
        self.resource_ml_widget = ResourceOptimizationMLWidget(self.db)
        report_tabs.addTab(self.resource_ml_widget, "⚡ Resource Optimization ML")
        
        # Marketing Optimization ML
        self.marketing_ml_widget = MarketingMLWidget(self.db)
        report_tabs.addTab(self.marketing_ml_widget, "📢 Marketing Optimization ML")
        
        # Model Performance
        self.model_perf_widget = ModelPerformanceWidget(self.db)
        report_tabs.addTab(self.model_perf_widget, "📊 Model Performance")
        
        # Predictive Maintenance ML
        self.predict_maint_widget = PredictiveMaintenanceMLWidget(self.db)
        report_tabs.addTab(self.predict_maint_widget, "🔧 Predictive Maintenance ML")
        
        layout.addWidget(report_tabs)
        widget.setLayout(layout)
        return widget

    
    def create_settings_tab(self) -> QWidget:
        """Settings tab (stub)"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        info = QLabel("""
        <h3>Arrow Limousine Management System</h3>
        <p><b>Version:</b> 1.0 (Desktop)</p>
        <p><b>Database:</b> PostgreSQL (almsdata)</p>
        <p><b>Framework:</b> PyQt6</p>
        
        <h4>Keyboard Shortcuts:</h4>
        <ul>
        <li><b>Ctrl+S</b> - Save current form</li>
        <li><b>Ctrl+N</b> - New charter</li>
        <li><b>Ctrl+P</b> - Print document</li>
        <li><b>Ctrl+F</b> - Find/Search</li>
        <li><b>F5</b> - Refresh data</li>
        </ul>
        
        <h4>Business Rules Implemented:</h4>
        <ul>
        <li>✅ reserve_number is business key for charter-payment matching</li>
        <li>✅ GST is tax-included (5% Alberta rate)</li>
        <li>✅ All database changes auto-committed</li>
        <li>✅ Duplicate prevention on imports</li>
        <li>✅ Protected receipt patterns preserved</li>
        </ul>>
        """)
        layout.addWidget(info)
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def refresh_data(self):
        """Refresh all displayed data (F5)"""
        QMessageBox.information(self, "Refresh", "Data refreshed\n[Full implementation pending]")
    
    def open_find(self):
        """Open find/search dialog (Ctrl+F)"""
        text, ok = QInputDialog.getText(self, "Find", "Search for:")
        if ok and text:
            QMessageBox.information(self, "Search", f'Searching for "{text}"\n[Full implementation pending]')

    def global_search(self):
        """Global search across receipts, charters, and clients"""
        query = self.global_search_input.text().strip()
        if len(query) < 2:
            QMessageBox.information(self, "Search", "Enter at least 2 characters to search")
            return

        pattern = f"%{query}%"
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()

            cur.execute(
                """
                SELECT receipt_id, receipt_date, vendor_name, description, gross_amount
                FROM receipts
                WHERE vendor_name ILIKE %s OR description ILIKE %s
                ORDER BY receipt_date DESC NULLS LAST
                LIMIT 50
                """,
                (pattern, pattern),
            )
            receipts = cur.fetchall()

            cur.execute(
                """
                SELECT charter_id, reserve_number, charter_date, client_display_name, booking_notes
                FROM charters
                WHERE COALESCE(reserve_number,'') ILIKE %s OR COALESCE(booking_notes,'') ILIKE %s
                ORDER BY charter_date DESC NULLS LAST
                LIMIT 50
                """,
                (pattern, pattern),
            )
            charters = cur.fetchall()

            cur.execute(
                """
                SELECT client_id, company_name, primary_phone, email
                FROM clients
                WHERE company_name ILIKE %s OR primary_phone ILIKE %s OR email ILIKE %s
                ORDER BY company_name
                LIMIT 50
                """,
                (pattern, pattern, pattern),
            )
            clients = cur.fetchall()

            cur.close()

            self._show_global_results(query, receipts, charters, clients)
        except Exception as e:
            QMessageBox.critical(self, "Search Failed", f"Search error: {e}")

    def _show_global_results(self, query: str, receipts, charters, clients):
        """Render search results in a tabbed dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Search Results: {query}")
        layout = QVBoxLayout()

        summary = QLabel(
            f"Receipts: {len(receipts)} | Charters: {len(charters)} | Clients: {len(clients)}"
        )
        layout.addWidget(summary)

        tabs = QTabWidget()
        tabs.addTab(
            self._build_results_table(
                ["Date", "Vendor", "Description", "Amount", "ID"],
                [
                    [
                        (r[1] or ""),
                        (r[2] or ""),
                        (r[3] or ""),
                        f"{r[4]:,.2f}" if r[4] is not None else "",
                        str(r[0]),
                    ]
                    for r in receipts
                ],
            ),
            "Receipts",
        )
        tabs.addTab(
            self._build_results_table(
                ["Date", "Reserve #", "Client", "Notes", "ID"],
                [
                    [
                        (c[2] or ""),
                        (c[1] or ""),
                        (c[3] or ""),
                        (c[4] or ""),
                        str(c[0]),
                    ]
                    for c in charters
                ],
            ),
            "Charters",
        )
        tabs.addTab(
            self._build_results_table(
                ["Name", "Phone", "Email", "ID"],
                [
                    [
                        (cl[1] or ""),
                        (cl[2] or ""),
                        (cl[3] or ""),
                        str(cl[0]),
                    ]
                    for cl in clients
                ],
            ),
            "Clients",
        )

        layout.addWidget(tabs)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dialog.setLayout(layout)
        dialog.resize(900, 500)
        dialog.exec()

    def _build_results_table(self, headers, rows):
        """Helper to create read-only results tables"""
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(rows))

        for row_idx, row_data in enumerate(rows):
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row_idx, col_idx, item)

        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        return table


# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================


def main():
    """Main application entry point"""
    try:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")  # Modern look
        
        db = DatabaseConnection()
        window = MainWindow()
        window.show()
        
        sys.exit(app.exec())
    except Exception as e:
        print(f"Fatal error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


