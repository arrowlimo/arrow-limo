# Complete Drill-Down System Documentation
**Arrow Limousine Management System - Enhanced Data Access**

## Overview

The drill-down system provides comprehensive master-detail views for all major entities in the system:
- **Charters** (bookings)
- **Employees** (staff management)
- **Vehicles** (fleet management)
- **Clients** (customer relationships)
- **Business Entity** (company-level management)

---

## 🚗 1. Charter Drill-Down System

**Files:**
- `drill_down_widgets.py` - CharterDetailDialog (4 tabs)
- `enhanced_charter_widget.py` - EnhancedCharterListWidget

### Features (4 Tabs)

#### Tab 1: Charter Details
- Reserve number, client, date/time
- Pickup location, destination
- Driver, vehicle assignment
- Status (Pending, Confirmed, Complete, Cancelled)
- Total amount due, balance calculation
- Notes and special instructions

#### Tab 2: Orders & Beverages
- Product/beverage orders table
- Add/edit/delete orders
- Price calculation
- Special requests

#### Tab 3: Routing & Charges
- Stop-by-stop routing
- Charge breakdown:
  - Base fare
  - Distance charges
  - Service charges
  - GST (5% Alberta, tax-included)
  - Total calculation

#### Tab 4: Payments
- Payment history table
- Payment date, amount, method
- Reconciliation status
- Add new payment
- Auto-calculate balance: `balance = total - SUM(payments)`

### List View Features
- Filters: Reserve #, Min Balance Due, Status dropdown
- Columns: Reserve #, Client, Date, Driver, Vehicle, Status, Total Due, Balance Due
- Actions: New Charter, Edit, Lock, Cancel, Refresh
- Double-click opens detail dialog
- Auto-refresh after changes

### Database Tables Used
```sql
- charters (main table)
- clients (customer info)
- employees (driver assignment)
- vehicles (vehicle assignment)
- charter_orders (beverage orders)
- payments (payment history via reserve_number)
```

---

## 👥 2. Employee Drill-Down System

**Files:**
- `employee_drill_down.py` - EmployeeDetailDialog (10 tabs)
- `enhanced_employee_widget.py` - EnhancedEmployeeListWidget

### Features (10 Tabs)

#### Tab 1: Personal Info
- Full name, SIN, date of birth
- Address, phone, email
- Emergency contacts

#### Tab 2: Employment
- Hire date, position, is_chauffeur flag
- Hourly rate, annual salary
- Vacation days (allocated, used, remaining)

#### Tab 3: Training & Qualifications
- **Training Table:** Course, completion date, expiry date, certificate #
- **Qualifications Table:** License type, issue date, expiry date
- Alerts for expiring certifications

#### Tab 4: Documents & Forms
- PDF document list
- Upload, view, edit, delete documents
- Generate forms: T4, T4A, TD1, Employment Contract
- Form-fill capability (future: PyMuPDF integration)

#### Tab 5: Pay & Advances
- **Pay History Table:** Date, gross, deductions, net, YTD totals
- **Advances Table:** Date, amount, reason, repaid, balance, status
- YTD summary calculations

#### Tab 6: Deductions & Tax
- CPP rate, EI rate, income tax rate
- **Gratuity Table:** Split percentage tracking
- **Custom Deductions:** Type, amount, frequency, start/end dates

#### Tab 7: Floats & Cash (Accountability)
- **Float Table:** Issue date, amount, purpose, return date, **receipts submitted**, **variance**, status
- **Variance Calculation:** `variance = issued_amount - receipts_submitted`
- Summary: Total floats out, unreturned amount
- Visual alerts for unreturned floats

**Example:**
```
Float issued: $200.00
Receipts:     $185.00
Variance:     $15.00  ← FLAGGED
```

#### Tab 8: Expenses & Receipts
- **Expense Table:** Date, category, amount, receipt?, approved, reimbursed
- **Missing Receipts Alert Table:** Amount, days overdue
- Approval workflow
- Reimbursement tracking

**Example:**
```
⚠️ Sarah: $90.50 in expenses, NO RECEIPTS, 7 days overdue
```

#### Tab 9: Lunch Tracking
- **Meal Table:** Date, meal type, vendor, cost, reimbursable, notes
- Track what employees ate (per user's "what they had for lunch" requirement)

**Example:**
```
Dec 5 - Lunch - Subway - Foot-long sub - $12.50 - Not reimbursable
```

#### Tab 10: Performance
- **Review Table:** Date, rating, reviewer, strengths, improvements
- Manager notes textarea

### List View Features
- Filters: Name search, Position dropdown, Status dropdown, Chauffeur-only checkbox
- Columns: Employee ID, Name, Position, Hire Date, Status, Chauffeur?, YTD Pay, **Unreturned Floats**, **Missing Receipts**
- **Visual Alerts:** Red background (QColor(255, 200, 200)) for unreturned floats and missing receipts
- Actions: New Employee, Edit, Terminate, Generate Reports, Refresh
- Double-click opens detail dialog

### "Pepper vs Fly Shit" Accountability Examples

**Float Accountability:**
```
Driver: John Smith
Float issued: $200 on Dec 1
Receipts submitted: $185
VARIANCE: $15 ← Where did this go?
Status: FLAGGED for manager review
```

**Receipt Tracking:**
```
Driver: Sarah Jones
Expense: $90.50 on Dec 10
Receipt: MISSING
Days overdue: 7
Status: ⚠️ ALERT - Follow up required
```

**Lunch Tracking:**
```
Driver: Mike Brown
Dec 15: McDonald's - Big Mac Combo - $11.25
Dec 16: Tim Hortons - Coffee & donut - $5.50
Dec 17: Home packed lunch - $0.00
Monthly food spend: $127.50
```

### Database Tables Used
```sql
- employees (main table)
- driver_payroll (pay history)
- employee_training (courses, certifications)
- employee_documents (PDF files)
- employee_advances (cash advances)
- employee_floats (float tracking - NEW TABLE NEEDED)
- employee_expenses (expense claims - NEW TABLE NEEDED)
- employee_meals (lunch tracking - NEW TABLE NEEDED)
```

---

## 🚗 3. Vehicle Drill-Down System

**Files:**
- `vehicle_drill_down.py` - VehicleDetailDialog (10 tabs)
- `enhanced_vehicle_widget.py` - EnhancedVehicleListWidget

### Features (10 Tabs)

#### Tab 1: Vehicle Info
- Vehicle #, license plate, VIN
- Year, make, model
- Type (Sedan, SUV, Limo, Stretch Limo, Van, Bus)
- Color, passenger capacity
- Current mileage
- Registration expiry
- Status (Active, In Service, Out of Service, Retired, Sold)

#### Tab 2: Maintenance
- **Upcoming Maintenance Alerts:** Service type, due date, due mileage, days until due
- **Maintenance History Table:** Date, type, description, mileage, cost, vendor, next due
- Actions: Add service record, Schedule service

#### Tab 3: Fuel Logs
- **Summary:** Avg L/100km, total fuel cost, last fillup date
- **Fuel Table:** Date, odometer, liters, cost, $/L, L/100km, driver, location
- Efficiency tracking over time

#### Tab 4: Insurance
- **Current Policy:** Policy #, insurer, expiry, coverage amount, annual premium
- **Claims History Table:** Date, claim #, type, amount, status, notes
- Actions: File claim

#### Tab 5: Accidents/Damage
- **Accident Table:** Date, driver, type, severity, fault, repair cost, status
- Actions: Report accident, View photos

#### Tab 6: Assignment History
- **Current Assignment:** Current driver, current charter
- **History Table:** Charter date, reserve #, driver, client, revenue, notes
- Track who drove what when

#### Tab 7: Cost Tracking (TCO)
- **Cost Summary:**
  - Purchase price
  - Total fuel
  - Total maintenance
  - Total insurance
  - **TOTAL COST OF OWNERSHIP**
  - **Cost per kilometer**
- **Cost Breakdown Table:** Category, total cost, % of total, avg per month

#### Tab 8: Documents
- Registration PDF
- Insurance policy PDF
- Inspection certificates
- Upload, view, delete documents

#### Tab 9: Inspections
- **Inspection Table:** Date, type (safety, emissions), result, inspector, next due, certificate #
- Actions: Add inspection

#### Tab 10: Depreciation
- Original purchase price
- Current book value (calculated)
- Total depreciation
- Depreciation rate (%)
- **Depreciation Schedule Table:** Year, beginning value, depreciation, ending value

### List View Features
- Filters: Make, Type, Status, Service Alerts Only
- Columns: Vehicle #, Plate, Make/Model, Year, Type, Mileage, Status, Next Service Due, Alerts
- **Visual Alerts:** Red for overdue service, yellow for upcoming service
- Actions: New Vehicle, Edit, Retire, Refresh
- Double-click opens detail dialog

### Database Tables Used
```sql
- vehicles (main table)
- charters (assignment history via vehicle_id)
- vehicle_maintenance (NEW TABLE NEEDED)
- vehicle_fuel_logs (NEW TABLE NEEDED)
- vehicle_insurance (NEW TABLE NEEDED)
- vehicle_accidents (NEW TABLE NEEDED)
- vehicle_inspections (NEW TABLE NEEDED)
- vehicle_documents (NEW TABLE NEEDED)
```

---

## 👥 4. Client Drill-Down System

**Files:**
- `client_drill_down.py` - ClientDetailDialog (9 tabs)
- `enhanced_client_widget.py` - EnhancedClientListWidget

### Features (9 Tabs)

#### Tab 1: Contact Info
- Company name, contact person
- Phone, email, address
- City, province, postal code
- **Billing Info:** Billing email, tax ID/GST #, payment terms, preferred payment method
- Status (Active, Inactive, Suspended, VIP, Blacklisted)
- Notes

#### Tab 2: Charter History
- **Summary Stats:** Total charters, total revenue, avg charter value, last charter date
- **Charter Table:** Date, reserve #, pickup, destination, driver, vehicle, amount, status
- Actions: New charter, View charter detail

#### Tab 3: Payments
- **Summary:** Total paid, outstanding balance, overdue amount
- **Payment Table:** Date, reserve #, amount, method, reference, reconciled, notes
- Actions: Record payment, Send statement

#### Tab 4: Credit & Terms
- Credit limit, credit used, available credit
- Deposit required checkbox, deposit %
- Last credit check date
- Credit rating (Excellent, Good, Fair, Poor, Not Rated)

#### Tab 5: Preferences
- **Favorite Drivers List:** Add/remove favorite drivers
- **Favorite Vehicles List:** Add/remove favorite vehicles
- **Special Requirements:** Wheelchair accessible, child seats, etc.

#### Tab 6: Communications
- **Communication Table:** Date/time, type (call/email/meeting), subject, staff, notes
- Actions: Log call, Log email

#### Tab 7: Documents
- Service agreements
- Credit applications
- Signed contracts
- Upload, view, delete documents

#### Tab 8: Disputes
- **Dispute Table:** Date, charter #, issue type, amount, status, resolution
- Actions: Log dispute, Resolve dispute

#### Tab 9: Client Metrics
- **Lifetime value** (total revenue)
- **Avg monthly revenue**
- **Charter frequency** (charters/month)
- **First charter date**
- **Client since** (days)
- **Payment reliability** (%)
- **Cancellation rate** (%)

### List View Features
- Filters: Name search, Status dropdown, Outstanding Balance Only checkbox
- Columns: Client ID, Company, Contact, Phone, Email, Total Revenue, **Outstanding**, Last Charter, Status
- **Visual Alerts:** Red background for outstanding balance
- Actions: New Client, Edit, Suspend, Send Statement, Refresh
- Double-click opens detail dialog

### Database Tables Used
```sql
- clients (main table)
- charters (charter history via client_id)
- payments (payment history via reserve_number join charters)
- client_preferences (NEW TABLE NEEDED)
- client_communications (NEW TABLE NEEDED)
- client_documents (NEW TABLE NEEDED)
- client_disputes (NEW TABLE NEEDED)
```

---

## 🏢 5. Business Entity Drill-Down System

**File:** `business_entity_drill_down.py` - BusinessEntityDialog (12 tabs)

### Features (12 Tabs)

#### Tab 1: Company Info
- Legal name, DBA/trade name
- Business number, GST registration #
- Incorporation date, province
- Business address, phone, email, website
- Ownership (owner name, ownership %)

#### Tab 2: Financials
- **Key Metrics (Current Year):**
  - Total revenue
  - Total expenses
  - Net profit
  - Profit margin (%)
- **Balance Sheet Snapshot:**
  - Total assets
  - Total liabilities
  - Owner's equity
- **Monthly Revenue Trend Table:** Month, revenue, expenses, profit

#### Tab 3: Tax Filings
- **Upcoming Tax Deadlines Table:** Type, period, due date, days until due, status
- **Filing History Table:** Year, type, filed date, amount paid/refund, status, confirmation #
- Actions: Log tax filing, GST remittance

#### Tab 4: Licenses & Permits
- **License Table:** License type, number, issue date, expiry date, status, renewal cost
- Actions: Add license, Renew license

#### Tab 5: Insurance
- **Insurance Table:** Policy type, insurer, policy #, coverage, premium, expiry, status
- Types: General liability, fleet insurance, property insurance, professional liability
- Actions: Add policy, File claim

#### Tab 6: Banking
- **Bank Accounts Table:** Bank, account type, account #, current balance, status, purpose
- **Credit Facilities Table:** Type (line of credit, overdraft), limit, used, available, interest rate
- Actions: Add account, Reconcile account

#### Tab 7: Loans & Liabilities
- **Summary:** Total debt, monthly payments
- **Loan Table:** Lender, type, original amount, current balance, interest rate, monthly payment, maturity date, status
- Actions: Add loan, Record payment

#### Tab 8: Assets
- **Summary:** Vehicles value, property value, equipment value, total assets
- **Asset Table:** Asset type, description, purchase date, original cost, current value, depreciation, status
- Actions: Add asset, Dispose asset

#### Tab 9: Vendors
- **Vendor Table:** Vendor name, category, contact, payment terms, YTD spend, outstanding, status
- Actions: Add vendor, View transactions

#### Tab 10: Compliance
- **Compliance Table:** Requirement, category, last review, next review, status
- Examples: CRA reporting, safety inspections, employment standards
- Actions: Add requirement, Mark reviewed

#### Tab 11: Documents
- Articles of incorporation
- Business license PDFs
- GST registration
- Insurance policies
- Contracts, leases
- Upload, view, delete documents

#### Tab 12: Strategic Planning
- **Goals Table:** Goal, category, target date, progress (%), status, notes
- Actions: Add goal, Update progress

### Access Method
- **Tab:** "🏢 Business Entity" in main navigation
- **Button:** "Open Business Management Dashboard" launches dialog
- Single dialog (no list view - there's only one business entity)

### Database Integration
- Loads actual revenue from `charters.total_amount_due`
- Loads actual expenses from `receipts.amount`
- Calculates profit and margin
- Shows bank accounts from `banking_transactions.mapped_bank_account_id`
- CIBC account (id=1), Scotia account (id=2)

---

## Implementation Guide

### 1. Integration into Main App

All drill-down systems are integrated in `main.py`:

```python
# Imports (top of file)
from enhanced_charter_widget import EnhancedCharterListWidget
from enhanced_employee_widget import EnhancedEmployeeListWidget
from enhanced_vehicle_widget import EnhancedVehicleListWidget
from enhanced_client_widget import EnhancedClientListWidget
from business_entity_drill_down import BusinessEntityDialog

# Tab creation in MainWindow.__init__
self.tabs.addTab(self.create_enhanced_charter_tab(), "📋 Charter List (Enhanced)")
self.tabs.addTab(self.create_enhanced_employee_tab(), "👥 Employee List (Enhanced)")
self.tabs.addTab(self.create_enhanced_vehicle_tab(), "🚗 Fleet List (Enhanced)")
self.tabs.addTab(self.create_enhanced_client_tab(), "🏢 Client List (Enhanced)")
self.tabs.addTab(self.create_business_entity_tab(), "🏢 Business Entity")
```

### 2. Database Connection Pattern

All widgets use the shared `DatabaseConnection` class:

```python
class MyWidget(QWidget):
    def __init__(self, db: DatabaseConnection):
        super().__init__()
        self.db = db
        
    def load_data(self):
        cur = self.db.get_cursor()
        cur.execute("SELECT ...")
        rows = cur.fetchall()
        cur.close()
```

### 3. Signal/Slot Pattern for Refresh

Detail dialogs emit `saved` signal when changes are made:

```python
class DetailDialog(QDialog):
    saved = pyqtSignal(dict)
    
    def save(self):
        # ... save to database ...
        self.saved.emit({"id": self.id})

# List widget connects to signal
dialog = DetailDialog(self.db, item_id)
dialog.saved.connect(lambda data: self.refresh())
dialog.exec()
```

### 4. Double-Click Integration

Use `DrillDownTableMixin` for automatic double-click handling:

```python
from table_mixins import DrillDownTableMixin

class MyListWidget(QWidget, DrillDownTableMixin):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.table = QTableWidget()
        # ... setup table ...
        self.enable_drill_down(self.table, key_column=0, detail_callback=self.open_detail)
    
    def open_detail(self, key_value):
        dialog = DetailDialog(self.db, key_value, self)
        dialog.exec()
```

### 5. Visual Alert Pattern

Use QColor backgrounds for accountability alerts:

```python
# Red alert for issues
if float(unreturned_floats) > 0:
    item = QTableWidgetItem(f"${unreturned_floats:.2f}")
    item.setBackground(QColor(255, 200, 200))  # Light red
    table.setItem(row, col, item)

# Yellow for warnings
if days_until_due <= 7:
    item.setBackground(QColor(255, 255, 200))  # Light yellow
```

---

## Database Schema Requirements

### New Tables Needed

```sql
-- Employee float tracking
CREATE TABLE employee_floats (
    float_id SERIAL PRIMARY KEY,
    employee_id INTEGER REFERENCES employees,
    issue_date DATE NOT NULL,
    amount NUMERIC(10,2) NOT NULL,
    purpose TEXT,
    return_date DATE,
    receipts_amount NUMERIC(10,2) DEFAULT 0,
    variance NUMERIC(10,2) GENERATED ALWAYS AS (amount - COALESCE(receipts_amount, 0)) STORED,
    status VARCHAR(20) DEFAULT 'Outstanding'
);

-- Employee expenses
CREATE TABLE employee_expenses (
    expense_id SERIAL PRIMARY KEY,
    employee_id INTEGER REFERENCES employees,
    expense_date DATE NOT NULL,
    category VARCHAR(100),
    amount NUMERIC(10,2) NOT NULL,
    has_receipt BOOLEAN DEFAULT FALSE,
    approved BOOLEAN DEFAULT FALSE,
    reimbursed BOOLEAN DEFAULT FALSE,
    notes TEXT
);

-- Employee meals
CREATE TABLE employee_meals (
    meal_id SERIAL PRIMARY KEY,
    employee_id INTEGER REFERENCES employees,
    meal_date DATE NOT NULL,
    meal_type VARCHAR(50),
    vendor VARCHAR(200),
    cost NUMERIC(10,2),
    reimbursable BOOLEAN DEFAULT FALSE,
    notes TEXT
);

-- Vehicle maintenance
CREATE TABLE vehicle_maintenance (
    maintenance_id SERIAL PRIMARY KEY,
    vehicle_id INTEGER REFERENCES vehicles,
    service_date DATE NOT NULL,
    service_type VARCHAR(100),
    description TEXT,
    mileage INTEGER,
    cost NUMERIC(10,2),
    vendor VARCHAR(200),
    next_due_date DATE,
    next_due_mileage INTEGER
);

-- Vehicle fuel logs
CREATE TABLE vehicle_fuel_logs (
    fuel_id SERIAL PRIMARY KEY,
    vehicle_id INTEGER REFERENCES vehicles,
    fill_date DATE NOT NULL,
    odometer INTEGER,
    liters NUMERIC(10,2),
    cost NUMERIC(10,2),
    price_per_liter NUMERIC(10,3),
    efficiency NUMERIC(10,2),
    driver_id INTEGER REFERENCES employees,
    location VARCHAR(200)
);

-- Client preferences
CREATE TABLE client_preferences (
    preference_id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients,
    favorite_driver_ids INTEGER[],
    favorite_vehicle_ids INTEGER[],
    special_requirements TEXT
);

-- Client communications
CREATE TABLE client_communications (
    comm_id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients,
    comm_datetime TIMESTAMP NOT NULL,
    comm_type VARCHAR(50),
    subject TEXT,
    staff_name VARCHAR(200),
    notes TEXT
);

-- Client disputes
CREATE TABLE client_disputes (
    dispute_id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients,
    charter_id INTEGER REFERENCES charters,
    dispute_date DATE NOT NULL,
    issue_type VARCHAR(100),
    amount NUMERIC(10,2),
    status VARCHAR(50),
    resolution TEXT
);
```

---

## Testing Checklist

### Charter Drill-Down
- [ ] List view loads charters with correct balance calculation
- [ ] Double-click opens charter detail
- [ ] All 4 tabs display correctly
- [ ] Payment entry updates balance in real-time
- [ ] Lock/unlock charter functionality
- [ ] Cancel charter with confirmation
- [ ] Save button commits changes to database

### Employee Drill-Down
- [ ] List view shows unreturned floats and missing receipts
- [ ] Red backgrounds appear for accountability issues
- [ ] Double-click opens employee detail
- [ ] All 10 tabs display correctly
- [ ] Float variance calculation works: `issued - receipts = variance`
- [ ] Missing receipt alerts show days overdue
- [ ] Lunch tracking table populated
- [ ] Document upload/view works

### Vehicle Drill-Down
- [ ] List view shows maintenance alerts
- [ ] Visual alerts for overdue service (red/yellow)
- [ ] Double-click opens vehicle detail
- [ ] All 10 tabs display correctly
- [ ] TCO calculation accurate
- [ ] Fuel efficiency tracked
- [ ] Assignment history shows charters
- [ ] Depreciation schedule calculated

### Client Drill-Down
- [ ] List view shows outstanding balance
- [ ] Red backgrounds for overdue clients
- [ ] Double-click opens client detail
- [ ] All 9 tabs display correctly
- [ ] Charter history loads correctly
- [ ] Payment history accurate
- [ ] Lifetime value calculated
- [ ] Dispute tracking works

### Business Entity
- [ ] Tab shows button to open dialog
- [ ] Button opens BusinessEntityDialog
- [ ] All 12 tabs display correctly
- [ ] Revenue/expense loaded from actual database
- [ ] Profit margin calculated correctly
- [ ] Bank accounts shown (CIBC, Scotia)
- [ ] Document list populated

---

## Future Enhancements

1. **PDF Form Filling:** Integrate PyMuPDF for actual PDF editing
2. **Real-time Dashboards:** Add charts/graphs to detail views
3. **Automated Alerts:** Email notifications for overdue items
4. **Mobile Access:** Responsive design for tablets
5. **Bulk Operations:** Multi-select for batch updates
6. **Export to Excel:** Export list views to spreadsheet
7. **Audit Trail:** Log all changes for compliance
8. **API Integration:** REST API for external access

---

**Last Updated:** December 24, 2025  
**System Version:** 1.0  
**Total Tabs:** 45 (Charter: 4, Employee: 10, Vehicle: 10, Client: 9, Business: 12)  
**Status:** ✅ Complete and integrated into main application
