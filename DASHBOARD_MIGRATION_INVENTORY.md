# Dashboard & Module Migration Inventory
**Generated:** December 8, 2025  
**Status:** Comprehensive Inventory of All Legacy & Backend Dashboards Not Yet in Desktop App

---

## 🎯 Quick Summary

**Total Dashboards/Modules Found:** 125+ reporting scripts  
**Desktop App Status:**
- ✅ **Implemented in PyQt6:** Charters, Customers, Accounting & Receipts  
- ❌ **Missing in Desktop:** Vehicle Fleet, Employee/Driver, Payment Analysis, Financial Reports  
- ⚠️ **Partially Integrated:** Reports tab (stub), Settings tab (stub)

**Backend API Endpoints Ready:** `/api/reports/*`, `/api/accounting/reports/*`  
**Frontend Views Ready:** Admin.vue (5 tabs), Reports.vue (Financial reports)

---

## 📊 FLEET MANAGEMENT DASHBOARDS

### Vehicle Fleet Cost Analysis
**Status:** ❌ Legacy scripts only (not in desktop app)  
**Files:**
- [final_vehicle_breakdown_with_insurance.py](final_vehicle_breakdown_with_insurance.py) - Complete vehicle cost analysis with insurance
- [corrected_vehicle_breakdown_with_insurance.py](corrected_vehicle_breakdown_with_insurance.py) - Corrected schema mapping
- [complete_vehicle_breakdown.py](complete_vehicle_breakdown.py) - Vehicle completeness check
- [calculate_vehicle_final_costs.py](calculate_vehicle_final_costs.py) - Final cost calculations
- [vehicle_completeness_analysis.py](vehicle_completeness_analysis.py) - Missing data identification

**Data Available:**
- Purchase price & financing data
- Insurance costs & policy tracking
- Maintenance & repair costs (from receipts)
- Fuel expenses per vehicle
- Loan payments & interest
- Vehicle ownership timeline
- Fleet financial summary view

**Purpose:** Track per-vehicle total cost of ownership, financing status, insurance claims, maintenance history

**Database Views:**
- `vehicle_fuel_expenses` - Fuel costs by vehicle
- `vehicle_maintenance_expenses` - Maintenance/repair costs
- `vehicle_insurance_expenses` - Insurance costs by vehicle
- `fleet_financial_summary` - Fleet-wide financial totals
- `vehicle_maintenance_dashboard` - Active vehicle maintenance overview

---

### Vehicle Maintenance Tracking
**Status:** ❌ Database schema exists, but no desktop app dashboard  
**Tables:**
- `maintenance_records` - Service dates, odometer, labor/parts costs
- `maintenance_schedules` - Next service due date/km
- `vehicle_fuel_log` - Fuel purchases linked to vehicles
- `vehicle_odometer_log` - Odometer readings by trip

**Missing from Desktop:**
- Maintenance due list (by date/km)
- Overdue service notifications
- Cost trends per vehicle
- Fuel efficiency tracking
- Service history timeline

---

### Vehicle Fleet Positioning
**Status:** ⚠️ Partial (data exists, no UI)  
**Tables:**
- `vehicle_fleet_history` - Fleet position assignments (L-1, L-2, etc.)
- `fleet_position_status` - Current position availability

**Issue:** Vehicle numbering (L-1, L-4) doesn't match physical VINs—need historical tracking

---

## 👥 EMPLOYEE & DRIVER DASHBOARDS

### Driver Pay & Expense Analysis
**Status:** ❌ Legacy scripts only (not in desktop app)  
**Files:**
- [comprehensive_driver_pay_by_year_report.py](comprehensive_driver_pay_by_year_report.py) - Driver pay by year/month
- [comprehensive_employee_pay_by_year_report.py](comprehensive_employee_pay_by_year_report.py) - Employee lifetime pay analysis
- [printable_pay_report_by_driver.py](printable_pay_report_by_driver.py) - Driver-specific pay statements
- [analyze_2012_driver_pay_vs_t4.py](scripts/analyze_2012_driver_pay_vs_t4.py) - T4 reconciliation

**Data Available:**
- Gross pay (hourly, salary, gratuities)
- Tax deductions (CPP, EI, income tax)
- Company contributions (CPP, EI, benefits)
- Expense reimbursements
- Vacation accruals
- YTD payroll tracking

**Database Tables:**
- `driver_payroll` - Main payroll records (18,499 records, $1.25M total)
- `staging_driver_pay` - Staging data (262,884 records)
- `employees` - Employee master records
- `driver_employee_mapping` - Map driver_id → employee_id

**Purpose:** Track driver pay, reconcile to charters, identify overpayments/discrepancies

---

### Employee Performance Metrics
**Status:** ❌ Schema exists, no dashboard yet  
**Tables:**
- `driver_performance_metrics` - Performance evaluation data
- `driver_schedules` - Shift/charter assignments
- `employee_time_tracking` - Hours tracking

**Missing:** Performance ratings, hours vs. pay variance, quality metrics

---

### Payroll Tax Compliance
**Status:** ⚠️ Partial calculations available, no UI  
**Missing:**
- T4 generation by year
- CPP/EI year-to-date tracking
- Federal/Alberta tax calculation
- Payroll summary by month
- Tax deduction audit trail

**File:** [Payroll_Tax_Calculation_Status_Report.md](Payroll_Tax_Calculation_Status_Report.md) - Service blueprint

---

## 💰 PAYMENT & FINANCIAL DASHBOARDS

### Payment Reconciliation
**Status:** ❌ API endpoints exist, no desktop UI  
**Database Tables:**
- `payments` - Payment records (reserve_number is business key)
- `payment_imports` - Imported payment records (Square, etc.)
- `payment_matches` - Charter-to-payment matching
- `comprehensive_payment_reconciliation` - Reconciliation status

**API Endpoints:**
- `GET /api/charters/{charter_id}/payments` - Payments for charter
- Backend logic uses `reserve_number` as primary key (NOT charter_id)

**Missing Dashboard Features:**
- Outstanding payment list
- Payment method breakdown (cash, check, card, e-transfer)
- NSF charge tracking
- Payment aging (days overdue)
- Customer payment history

---

### Accounts Receivable & Invoice Aging
**Status:** ⚠️ API partially implemented, no desktop UI  
**Database Tables:**
- `invoices` - QB-compatible invoices
- `accounts_receivable` - AR aging tracking
- `financial_reconciliation_status` - Invoice payment status

**API Endpoint:**
- `GET /api/accounting/reports/ar-aging` - Returns aging buckets

**Missing from Desktop:**
- Outstanding invoice list
- Customer payment terms
- Past due notifications
- Credit limits by customer
- Invoice aging report

---

### Cash Flow Tracking
**Status:** ⚠️ Schema exists, no dashboard  
**Tables:**
- `cash_flow_tracking` - Transaction cash in/out
- `cash_flow_categories` - Flow categorization
- `cash_box_ledger` - Cash box transactions

**API Endpoint:**
- `GET /api/accounting/reports/cash-flow` - Cash in vs. out by period

**Missing:**
- Daily/weekly/monthly cash flow view
- Cash position forecast
- Cash requirements by activity
- Float management

---

## 📈 FINANCIAL REPORTING DASHBOARDS

### Profit & Loss Report
**Status:** ⚠️ API implemented, frontend stub exists  
**API Endpoint:**
- `GET /api/accounting/reports/profit-loss` - Revenue, expenses, net profit

**Frontend Location:** [frontend/src/views/Reports.vue](frontend/src/views/Reports.vue) (export button exists)

**Data Provided:**
- Revenue by month/quarter/year
- Expenses by category
- GST collected vs. paid
- Net profit calculation

**Missing from Desktop:**
- Income statement display
- Expense breakdown by account
- Year-over-year comparison
- Budget vs. actual
- Variance analysis

---

### Balance Sheet
**Status:** ❌ Schema exists, no API endpoint  
**Database View:** `qb_export_balance_sheet` (QB export)

**Missing:**
- Assets (vehicles, furniture, etc.)
- Liabilities (loans, accounts payable)
- Equity breakdown
- Comparative balance sheets

---

### Charter Analysis Reports
**Status:** ❌ Legacy scripts only  
**Files:**
- [charter_mega_report.py](charter_mega_report.py) - Comprehensive charter analysis
- [charter_detailed_report.py](charter_detailed_report.py) - Detailed charter data
- [charter_client_detailed_report.py](charter_client_detailed_report.py) - Charter by client
- [charter_vehicle_linking_analysis_report.py](charter_vehicle_linking_analysis_report.py) - Vehicle-charter mapping

**Missing Dashboard:**
- Charter volume by month/year
- Revenue by route/client
- Utilization rate (booked vs. available)
- Average charter value
- Charter cancellation analysis

---

### QuickBooks Integration Reports
**Status:** ⚠️ Exports exist, no live sync  
**Files:**
- [qb_integration_report.py](qb_integration_report.py) - QB integration status
- [report_qb_account_migration_gaps.py](report_qb_account_migration_gaps.py) - Account mapping gaps

**QB Export Tables:**
- `qb_export_chart_of_accounts` - GL accounts
- `qb_export_profit_loss` - P&L export
- `qb_export_balance_sheet` - Balance sheet export
- `qb_export_ar_aging` - AR aging
- `qb_export_customers` - Customer list
- `qb_export_employees` - Employee list

**Missing:**
- Live QB sync status
- Reconciliation variance report
- Account mapping completeness
- Transaction classification audit

---

## 📋 EXISTING BACKEND API ENDPOINTS

**Base URL:** `http://127.0.0.1:8000/api/`

### Accounting Routes
- `GET /accounting/stats` - Basic stats (revenue, expenses)
- `GET /accounting/gst/summary` - GST collected vs. paid
- `GET /accounting/chart-of-accounts` - GL account list
- `GET /accounting/reports/profit-loss` - P&L report (date range)
- `GET /accounting/reports/cash-flow` - Cash flow report (date range)
- `GET /accounting/reports/ar-aging` - AR aging buckets

### Reports Routes
- `GET /reports/export?type=booking-trends&format=csv` - Booking trends
- `GET /reports/export?type=revenue-summary` - Revenue summary
- `GET /reports/export?type=driver-hours` - Driver hours
- `GET /reports/cra-audit-export` - CRA audit format export

### Charter Routes
- `GET /charters` - All charters
- `GET /charters/{id}` - Single charter
- `GET /charters/{id}/routes` - Charter itinerary
- `GET /charters/{id}/payments` - Charter payments

### Invoices Routes
- `GET /invoices` - All invoices
- `GET /invoices/{id}` - Single invoice
- `GET /invoices/stats/summary` - Invoice summary stats

### Payments Routes
- `GET /charters/{id}/payments` - Charter payment list
- `POST /payments` - Create payment

---

## 🎨 EXISTING FRONTEND DASHBOARDS

### Admin.vue (Web Frontend)
**Location:** [frontend/src/views/Admin.vue](frontend/src/views/Admin.vue)

**Tabs:**
1. **Overview** - System stats, activity feed, health status
2. **Users** - User management, add/edit/delete
3. **Settings** - Company info, GST rate, timezone, notifications
4. **Reports** - Report generation buttons (not yet implemented)
5. **Backup** - Backup/restore functionality (not yet implemented)

**Status:** Stubs only—no actual functionality, mock data

---

### Reports.vue (Web Frontend)
**Location:** [frontend/src/views/Reports.vue](frontend/src/views/Reports.vue)

**Report Cards Defined:**
- 💼 Customer Reports
- 📅 Booking Reports  
- 👤 Driver/Employee Reports
- 🚗 Vehicle Reports
- 💰 Financial Reports (P&L, Balance Sheet, AR Aging)
- 📊 Accounting Reports

**Status:** Export buttons exist, actual report generation not hooked up

---

## ⚙️ DATABASE VIEWS FOR DASHBOARDS

**Existing Views (in `almsdata` DB):**

### Vehicle Views
- `vehicle_fuel_expenses` - Fuel costs by vehicle
- `vehicle_maintenance_expenses` - Maintenance costs by vehicle
- `vehicle_insurance_expenses` - Insurance costs by vehicle
- `vehicle_maintenance_dashboard` - Active maintenance status
- `fleet_financial_summary` - Fleet totals

### Driver Views
- `driver_expense_vs_payroll` - Charter expenses vs. payroll
- `driver_expense_discrepancies` - Expense/payroll variance
- `comprehensive_driver_reconciliation` - Driver-by-month reconciliation
- `driver_pay_validation_view` - Pay validation data

### Payment Views
- `square_etransfer_reconciliation_dashboard` - e-Transfer/Square matching
- `payment_reconciliation` - Payment matching status

### Financial Views
- `accounts_receivable` - AR aging
- `charter_reconciliation_status` - Charter payment status
- `cash_flow_tracking` - Cash in/out tracking
- `financial_reconciliation_status` - Financial reconciliation status

---

## 📊 PRIORITY IMPLEMENTATION PLAN

### PHASE 1: High Priority (This Month)
**Estimated Effort:** 30-40 hours

1. **Fleet Management Tab** (8 hours)
   - Vehicle list with cost summary
   - Fuel efficiency tracking
   - Maintenance schedule (overdue/upcoming)
   - Insurance policy tracking
   - Vehicle utilization by charter
   - Data source: `vehicle_maintenance_dashboard` view

2. **Driver Performance Tab** (8 hours)
   - Driver list with YTD earnings
   - Hours worked vs. pay variance
   - Charter count & average pay
   - Expense reimbursement tracking
   - Performance metrics (if available)
   - Data source: `driver_expense_vs_payroll` view + `driver_payroll` table

3. **Financial Dashboard Tab** (8 hours)
   - P&L summary (revenue, expenses, profit)
   - Cash flow (in vs. out)
   - AR aging (outstanding invoices)
   - Monthly revenue trend
   - Expense breakdown by category
   - Data source: Existing API endpoints + views

4. **Payment Reconciliation Tab** (6 hours)
   - Outstanding payment list
   - Payment by method breakdown
   - NSF charge tracking
   - Customer payment history
   - Data source: `payments` + `payment_reconciliation` tables

### PHASE 2: Medium Priority (Next Month)
**Estimated Effort:** 20-30 hours

5. **Advanced Vehicle Analytics** (6 hours)
   - Cost per mile
   - ROI analysis
   - Depreciation tracking
   - Maintenance trend analysis

6. **Employee Payroll Audit** (8 hours)
   - T4 generation
   - Tax deduction summary
   - Payroll variance report
   - Deduction audit trail

7. **QuickBooks Reconciliation** (6 hours)
   - QB sync status
   - Account mapping completeness
   - Variance between systems

8. **Charter Analytics** (8 hours)
   - Booking trends
   - Route profitability
   - Customer analysis
   - Cancellation patterns

### PHASE 3: Low Priority (Next Quarter)
- Budget vs. actual analysis
- KPI dashboard
- Insurance renewal alerts
- Loss analysis reports

---

## 🔗 MIGRATION STEPS

### For Each Dashboard:

1. **Identify Data Sources**
   - Which tables/views needed?
   - What API endpoints available?
   - Date range requirements?

2. **Create PyQt6 Tab**
   - Inherit from `QWidget`
   - Add data loading methods
   - Implement table/chart displays
   - Add filters/date ranges

3. **Connect to Backend API**
   - Use `requests` library
   - Cache results appropriately
   - Handle errors gracefully

4. **Add to main.py**
   - Add tab to `self.tabs`
   - Add case in `on_tab_changed()`
   - Initialize on first access

5. **Test End-to-End**
   - Verify data loads
   - Test date range filtering
   - Check performance (large result sets)

---

## 📝 NOTES

**Reserve Number as Business Key:**
All payment/invoice matching uses `reserve_number` (NOT `charter_id`). Many legacy payments have NULL `charter_id`.

**Vehicle Schema Issues:**
- Vehicle numbering (L-1, L-4) reused across decades
- Need historical vehicle mapping
- VIN-to-L-number mapping missing for 2010-2015 period

**GST Calculation:**
- 5% GST is INCLUDED in amounts (Alberta)
- Use `gst_amount = gross_amount * 0.05 / 1.05`
- Net = gross - gst

**Outstanding Balance Sources:**
- `charters.balance` field
- `invoices.balance_due` (QB-compatible)
- `accounts_receivable` table

---

## ✅ CHECKLIST FOR DESKTOP APP COMPLETION

- [ ] Fleet Management Tab
  - [ ] Vehicle list with cost breakdown
  - [ ] Maintenance due list
  - [ ] Insurance tracking
- [ ] Driver Performance Tab  
  - [ ] Driver list with earnings
  - [ ] Hours/pay reconciliation
  - [ ] Expense tracking
- [ ] Financial Reports Tab
  - [ ] P&L statement
  - [ ] Cash flow report
  - [ ] AR aging
- [ ] Payment Reconciliation Tab
  - [ ] Outstanding list
  - [ ] NSF charges
  - [ ] Payment methods
- [ ] Export functionality (CSV/Excel)
- [ ] Date range filtering for all reports
- [ ] Performance optimization (caching)

---

**Last Updated:** December 8, 2025  
**Next Review:** After Phase 1 implementation

