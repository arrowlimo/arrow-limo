# COMPLETE TESTING & VALIDATION FRAMEWORK
## Arrow Limousine Management System - Copilot Code Review Checklist

**Purpose:** Comprehensive validation of all queries, UI components, data filtering, display logic, and functionality before production deployment.

---

## PART 1: DATABASE SCHEMA REFERENCE UPDATE

**Status:** Add UI sizing info to [docs/DATABASE_SCHEMA_REFERENCE.md](docs/DATABASE_SCHEMA_REFERENCE.md)
- Include field widths, data types, sample max lengths for each column
- Add "UI Widget Type" recommendations per field
- Include validation rules (required/optional, regex patterns, ranges)

---

## PART 2: DATA VALIDATION & FILTERING

### 2.1 Query Code Reviews (Every SQL query must pass)
- [ ] Check column names match actual database schema (no typos, no deprecated columns)
- [ ] Verify all JOINs use business keys (reserve_number for charters, client_id relationships, employee_id)
- [ ] Confirm WHERE clauses filter valid data (e.g., `WHERE is_active = true`, `WHERE status != 'cancelled'`)
- [ ] Check for NULL handling (COALESCE, IS NULL, IS NOT NULL as needed)
- [ ] Verify aggregate functions (SUM, COUNT, AVG) are correctly grouped
- [ ] Confirm date comparisons use YYYY-MM-DD format
- [ ] Check decimal/numeric fields for proper DECIMAL(12,2) handling

### 2.2 Form Input Validation (Client-side & server-side)
- [ ] Required fields marked with * and enforced before submit
- [ ] Email fields validated for format (regex or built-in validator)
- [ ] Phone fields accept valid formats (international, local, with/without dashes)
- [ ] Date fields only accept valid YYYY-MM-DD
- [ ] Numeric fields reject non-numeric input
- [ ] Text fields respect max length (truncate or warn)
- [ ] Dropdown/select lists show only valid options (pulled from DB)
- [ ] Name fields reject special characters unless needed
- [ ] Duplicate record checks (e.g., same employee_number, reserve_number)

### 2.3 Data Filtering in Forms
- [ ] Filter controls start matching at 1 character (NOT 3)
- [ ] As user types, filtered list updates in real-time (debounced, no lag)
- [ ] Show "No results" message if filter matches nothing
- [ ] Has "Add New" button if user wants to create new entry (not just filter)
- [ ] Can clear filter to show all options again
- [ ] Multi-select filters work correctly (AND/OR logic specified)
- [ ] Date range filters work (from_date <= value <= to_date)
- [ ] Status filters show only active/inactive as appropriate

---

## PART 3: DISPLAY & DASHBOARD VALIDATION

### 3.1 Management Dashboards - New Columns Visible
- [ ] Clients dashboard displays: first_name, last_name, corporate_parent_id, corporate_role, company_name, warning_flag
- [ ] Employees dashboard displays: employee_number (NOT driver_code), first_name, last_name, all compliance fields (proserve_*, vulnerable_sector_*, drivers_abstract_*, chauffeur_permit_*, medical_fitness_*, license_class, restrictions, qualification_1-5_dates)
- [ ] Charters dashboard displays: reserve_number, charter_date, client_name, assigned_driver, vehicle, total_amount_due, payment_status
- [ ] Vehicles dashboard displays: vehicle_number, vin, year, make, model, cvip_date, cvip_expiry
- [ ] Payments dashboard displays: reserve_number, payment_date, amount, payment_method, balance_remaining

### 3.2 Column Visibility & Sorting
- [ ] Each dashboard allows hiding/showing columns (user preference saved)
- [ ] Sort by any column (ascending/descending)
- [ ] Date columns sort by actual date (not alphabetically)
- [ ] Numeric columns sort numerically (not as strings)
- [ ] Null values sort to bottom (or top, consistently)
- [ ] Sort indicators show which column is sorted and direction

### 3.3 Export/Print Functionality
- [ ] Export to CSV preserves data integrity (quoted strings, proper delimiters)
- [ ] Print layout is portrait-friendly (columns fit without horizontal scrolling)
- [ ] Print preview shows headers on each page
- [ ] Print respects column width settings (fixed widths, not auto)

---

## PART 4: FORM WIDGETS & INTERACTIONS

### 4.1 CRUD Operations (Create, Read, Update, Delete)
- [ ] **Create form:** All required fields present, validation works, submit saves to DB
- [ ] **Read/View:** Shows all column data correctly, formatting matches DB type (dates, currency)
- [ ] **Edit form:** Pre-fills existing data, changes save, can cancel without saving
- [ ] **Delete:** Confirmation dialog shown, deletes from DB, related records handled (cascade or prevent)
- [ ] **List/Grid:** Shows paginated results (50/100/500 rows per page option)

### 4.2 Filter/Search Bar (Every list must have one)
- [ ] Fuzzy search works on text fields (first 1 character triggers, includes substring matches)
- [ ] Results update in real-time as user types
- [ ] Shows number of results ("12 matches found")
- [ ] Can use multiple filters (e.g., "Name = 'Smith' AND Status = 'active'")
- [ ] Filter reset button clears all filters
- [ ] Saves filter preferences for future sessions (optional)

### 4.3 Add/New Button
- [ ] Present on every list/grid that allows creation
- [ ] Opens new form with blank fields
- [ ] Form has "Save" and "Cancel" buttons
- [ ] Successfully created record appears in list after save
- [ ] Duplicate prevention check runs before save

### 4.4 Edit Button (Every row, if applicable)
- [ ] Opens record in edit form
- [ ] Pre-fills all existing data
- [ ] Changes save without full page reload (if possible)
- [ ] Shows "unsaved changes" warning if user tries to leave
- [ ] Edit history/audit log records who changed what when (optional)

### 4.5 Delete Button (Every row, if applicable)
- [ ] Confirmation dialog: "Are you sure?" with details of record being deleted
- [ ] Shows cascade consequences (e.g., "This will delete 5 related payments")
- [ ] Prevents delete if referenced by other records (if no cascade)
- [ ] Logs deletion in audit trail

### 4.6 Sort Controls
- [ ] Clickable column headers for single-column sort
- [ ] Multi-column sort via UI (drag columns or checkbox selector)
- [ ] Sort direction indicator (↑ for ASC, ↓ for DESC)
- [ ] Preserves sort when filtering
- [ ] Remembers user's last sort preference

---

## PART 5: MASTER DROPDOWN/LOOKUP MANAGERS

### 5.1 Master Data Management Tab (Under Admin)
Create a central management interface for all dropdown/lookup lists:

**Tables to manage:**
- Payment methods (cash, check, credit_card, debit_card, bank_transfer, trade_of_services, unknown)
- Employee categories (driver, dispatcher, accountant, office, owner)
- Charter statuses (pending, confirmed, in_progress, completed, cancelled, no_show)
- Vehicle statuses (available, in_service, maintenance, retired)
- Client statuses (active, inactive, suspended, bad_debt)
- Exemption types (GST, PST, etc.)
- Compliance statuses (compliant, non_compliant, unknown, pending_review)
- License classes (1, 2, 4, 5)
- Qualification types (custom names for qualification_1-5)

**For each dropdown:**
- [ ] Add new value button
- [ ] Edit existing value (name, description, active/inactive)
- [ ] Delete value (with cascade warning)
- [ ] Reorder/sort values (drag-drop or up/down arrows)
- [ ] Bulk import from CSV
- [ ] Bulk export to CSV
- [ ] Show usage count ("This value used in X records")
- [ ] Warn before deleting if in use

### 5.2 Color Coding Manager (Under Admin)
- [ ] Define custom color schemes per field/status
- [ ] Examples:
  - Charter status: pending=yellow, confirmed=green, cancelled=red, no_show=gray
  - Compliance status: compliant=green, non_compliant=red, pending_review=yellow
  - Payment status: paid=green, partial=yellow, overdue=red
  - Warning flag: true=red, false=default
- [ ] Apply colors in:
  - List/grid views (background or text color)
  - Form fields (border or background highlight)
  - Dashboard widgets (status badges)
- [ ] Allow per-user color preference override (optional)
- [ ] Export/import color scheme templates

---

## PART 6: USER INTERFACE - LAYOUT & USABILITY

### 6.1 Scrollbars & Overflow
- [ ] Long forms have vertical scrollbar (height: fixed or max-height)
- [ ] Wide tables have horizontal scrollbar (freeze first column if possible)
- [ ] Scrollbars appear only when needed (overflow: auto)
- [ ] Scrollbar styling consistent across app
- [ ] Keyboard shortcuts for scroll (Page Up/Down, Home/End work)

### 6.2 Fixed Widths (NO auto-width)
- [ ] Text inputs: fixed width per field (30-100px based on data length)
- [ ] Date inputs: fixed 150px width (date picker)
- [ ] Numeric inputs: fixed 80-120px width
- [ ] Dropdown selects: fixed width matching expected content
- [ ] Buttons: consistent width (80-120px)
- [ ] Column widths in grids: fixed (resizable but not auto)
- [ ] Form layout: 2-4 columns max (depends on screen, but predictable)
- [ ] Mobile responsive: switches to 1 column (still fixed, just narrower)

### 6.3 Color Coding (Consistent & Accessible)
- [ ] All status colors accessible (WCAG AA contrast ratio)
- [ ] Color legend visible on dashboards
- [ ] No reliance on color alone (include text labels)
- [ ] Red for errors/urgent, green for success, yellow for warning, gray for inactive
- [ ] Custom color scheme via Master Dropdown Manager (see 5.2)

### 6.4 Responsive Design (If applicable)
- [ ] Tested on: Desktop (1920x1080), Laptop (1366x768), Tablet (768x1024)
- [ ] Form fields stay readable on all sizes
- [ ] Tables readable on mobile (or switch to card view)
- [ ] Buttons clickable on touch (48px minimum)

---

## PART 7: DOCUMENT MANAGEMENT & FOLDERS

### 7.1 Document Structure (Auto-create if missing)
Each entity type has a linked folder:

**Employees:**
```
documents/employees/[employee_number]/
  ├── hire_documents/
  ├── certifications/  (ProServe, VSC, Medical, etc.)
  ├── pay_stubs/
  ├── t4_forms/
  └── employment_records/
```

**Clients:**
```
documents/clients/[client_id]/
  ├── quotes/
  ├── contracts/
  ├── invoices/
  ├── payment_records/
  └── correspondence/
```

**Vehicles:**
```
documents/vehicles/[vehicle_id]/
  ├── registration/
  ├── insurance/
  ├── maintenance_records/
  ├── cvip_documents/
  └── inspection_reports/
```

**Charters/Dispatches:**
```
documents/dispatches/[dispatch_id]/
  ├── charter_letters/
  ├── route_details/
  ├── signed_forms/
  └── special_requirements/
```

### 7.2 Document Management UI
- [ ] View linked folder button (opens file manager)
- [ ] Upload document button (drag-drop or file picker)
- [ ] File list shows: filename, upload date, file size
- [ ] Preview thumbnails for images/PDFs
- [ ] Download button for each file
- [ ] Delete button with confirmation
- [ ] File type restrictions (e.g., only PDF, DOC, images)
- [ ] Auto-create folder if missing on first upload

### 7.3 Form Document Generation
- [ ] **Charter Letter:** Auto-fill template with charter details, print/PDF/email
- [ ] **Quote:** Generate from charter, customize, send to client email
- [ ] **Invoice:** Auto-generate from payment records, track sent/paid status
- [ ] **Employee Documents:**
  - T4 forms (annual)
  - Pay stubs (per-pay-period)
  - Employment agreement
- [ ] **Vehicle Documents:**
  - Registration renewal notice
  - Insurance summary
  - CVIP report

### 7.4 Document Generation Format Options
For each form:
- [ ] **Preview:** Show rendered document before save/print
- [ ] **Print:** Print directly to printer (landscape/portrait choice)
- [ ] **PDF:** Save as PDF to linked folder
- [ ] **RTF/Word:** Generate editable RTF (for customization before send)
- [ ] **Email:** Send directly to recipient email address
- [ ] **Save for Later:** Store draft, reopen to finish/send

### 7.5 Linked Folder Manager
- [ ] Admin can change base folder path (settings)
- [ ] Auto-create missing folders (configurable)
- [ ] Archive old folders (move to dated folder like `2024_archive/`)
- [ ] Bulk delete empty folders
- [ ] File storage warnings (e.g., "10GB used of 100GB")

---

## PART 8: COMMUNICATION & WORKFLOW

### 8.1 Inbox (Messages/Notifications)
- [ ] System notifications (new charter, payment received, compliance expiring)
- [ ] User-to-user messages
- [ ] Read/unread status
- [ ] Archive/delete messages
- [ ] Search/filter messages
- [ ] Notification preferences (email, on-screen, silent)

### 8.2 Outbox (Sent Items)
- [ ] History of all sent documents (quotes, invoices, emails)
- [ ] Filter by recipient, date, document type
- [ ] Resend button
- [ ] View original content
- [ ] Status: sent, opened, failed

### 8.3 To-Do / Task List
- [ ] Create tasks linked to charters, employees, clients, vehicles
- [ ] Set due dates with reminders (1 day before, on date, overdue)
- [ ] Assign to employee
- [ ] Mark complete
- [ ] Task categories (compliance renewal, maintenance, follow-up, etc.)
- [ ] View by assignee, due date, category
- [ ] Dashboard widget: show overdue tasks in red
- [ ] Weekly task summary (email)

### 8.4 Dispatch Workflow
- [ ] Create dispatch from charter
- [ ] Assign driver + vehicle
- [ ] Dispatch status: assigned, en_route, completed, issues
- [ ] Driver app: real-time GPS, pickup/dropoff confirmation
- [ ] Communication: send message to driver
- [ ] Post-dispatch: collect driver notes, fuel consumption, issues

---

## PART 9: ERROR HANDLING & REPORTING

### 9.1 Application Errors
- [ ] Error logging: every exception logged with timestamp, user, query
- [ ] Error display: user-friendly message (hide technical details in UI)
- [ ] Error recovery: "Try again" button, fallback to previous state
- [ ] Email alert: critical errors (500 status) alert admin immediately

### 9.2 Data Validation Errors
- [ ] Required field missing: highlight field, show error message below
- [ ] Invalid format (email, phone, date): show expected format in error
- [ ] Duplicate record: show which field is duplicated, option to view existing
- [ ] Constraint violation: explain why (e.g., "Cannot delete charter with payments")

### 9.3 Query Execution Errors
- [ ] Database connection failure: "Database unavailable, try again in 1 minute"
- [ ] Timeout (long query): "Request taking too long, try a smaller date range"
- [ ] Lock conflict: "Record being edited by another user, try again soon"

### 9.4 Error Report Dashboard (Admin only)
- [ ] List of all errors from today/week/month
- [ ] Error frequency (how many times per day)
- [ ] Affected users
- [ ] Stack trace (for developers)
- [ ] Mark as "reviewed" to hide from dashboard
- [ ] Export error log to CSV

---

## PART 10: OFFICE FUNCTIONS & INTEGRATIONS

### 10.1 Email Integration
- [ ] SMTP configured (outbound)
- [ ] POP3/IMAP configured (inbound, optional)
- [ ] Test email button (sends test to admin)
- [ ] Email templates: quote, invoice, charter letter, receipt, confirmation
- [ ] Merge fields in templates (e.g., {{client_name}}, {{charter_date}})
- [ ] Bulk email: send to multiple clients
- [ ] Track open/click status (optional, if service integrated)
- [ ] Bounce handling: remove invalid addresses, alert admin

### 10.2 Print Functions
- [ ] Print preview before printing
- [ ] Landscape/portrait selection
- [ ] Paper size selection (letter, legal, A4)
- [ ] Margin/scaling options
- [ ] Print to file (PDF)
- [ ] Printer selection dialog
- [ ] Remember last printer selection

### 10.3 PDF Form Filling (vs RTF Generation)
**Recommendation:** Use PDF forms (easier, more professional, fillable)
- [ ] Create master PDF forms (quote template, invoice template, charter letter)
- [ ] Merge data into PDF fields automatically
- [ ] Support signature fields (e.g., client sign-off)
- [ ] Flatten PDF after filling (remove editability if needed)
- [ ] Generate fillable PDF (keep fields editable)

### 10.4 RTF/Word Export
- [ ] Alternative if client wants editable document
- [ ] Maintain formatting (fonts, colors, tables)
- [ ] Include images (logo, signatures)
- [ ] Merge fields preserved or pre-filled (user's choice)

### 10.5 T4/T2 Tax Forms
- [ ] Auto-generate T4 from employee pay records (annual)
- [ ] Auto-generate T2 (corporate tax form) if applicable
- [ ] CRA-compliant formatting
- [ ] E-file integration (optional, if supported)
- [ ] Print + NETFILE readiness

---

## PART 11: COMPLIANCE & BYLAW VALIDATION

### 11.1 Red Deer Driver-for-Hire Bylaw Checker
Create automated compliance audit:
- [ ] Every chauffeur (is_chauffeur = true):
  - ProServe number + expiry date valid
  - Vulnerable Sector Check date within 5 years
  - Driver's abstract date within 1 year (or as per bylaw)
  - Valid driver's license class (4 or 5 for Red Deer, typically)
  - No license restrictions that prevent commercial driving
  - Medical fitness certificate (if required) valid
  - Chauffeur permit/bylaw badge current

### 11.2 Compliance Dashboard
- [ ] Show each chauffeur's compliance status
- [ ] **Compliant (green):** All requirements met
- [ ] **Expiring Soon (yellow):** Any certificate expires within 30 days
- [ ] **Non-Compliant (red):** Any requirement missing or expired
- [ ] Alert system: email driver 30 days before expiry
- [ ] Prevent assignment: cannot book with non-compliant driver

### 11.3 License Class Restrictions
- [ ] **Class 5:** Standard license, can only drive personal-use vehicles (PREVENT from limo bookings)
- [ ] **Class 4:** Can drive small commercial vehicles (allow limo bookings)
- [ ] **Class 2:** Can drive buses (allow all bookings if required)
- [ ] **Class 1:** Commercial (allow all)
- [ ] Store restriction in driver_license_class, enforce in booking validation

---

## PART 12: TESTING CHECKLIST - BY FEATURE

### 12.1 Clients Management
- [ ] List view: shows all clients, can filter by name/company, sort by status
- [ ] Add client: required fields validated, duplicate check works
- [ ] Edit client: shows current data, changes saved
- [ ] Delete client: warns about related charters
- [ ] View corporate hierarchy: parent_id shows which clients are employees of which company
- [ ] Color coding: warning_flag = true shows red badge
- [ ] New fields visible: first_name, last_name, company_name, corporate_parent_id, corporate_role

### 12.2 Employees Management
- [ ] List view: shows all employees, filter by name, sort by hire_date
- [ ] Add employee: email validated, employee_number unique, no driver_code field (removed)
- [ ] Edit employee: all compliance fields editable (proserve_*, vulnerable_sector_*, etc.)
- [ ] Qualifications section: shows 5 date fields (qualification_1-5_date), user can add dates as needed
- [ ] Compliance badge: green/yellow/red based on expiry dates
- [ ] Driver assignment: cannot select non-compliant driver
- [ ] View documents: linked folder button, upload certifications

### 12.3 Charters Management
- [ ] Create charter: required fields (client, date, time, vehicle, driver) validated
- [ ] Client lookup: starts filtering at 1 character, shows results as typed
- [ ] Driver lookup: can only select compliant drivers, shows warning if trying to assign non-compliant
- [ ] Vehicle lookup: shows availability for selected date/time
- [ ] Payment status: shows balance_remaining correctly
- [ ] Payments list: filtered by reserve_number, shows all related payments
- [ ] Generate documents: quote, charter letter, invoice buttons work

### 12.4 Vehicles Management
- [ ] List: shows all vehicles, filter by status, sort by vehicle_number
- [ ] CVIP tracking: cvip_date, cvip_expiry visible, alert if expiring
- [ ] Maintenance log: linked to vehicle, shows history
- [ ] Availability calendar: shows booked dates, prevents double-booking
- [ ] Documents: registration, insurance, cvip reports linked

### 12.5 Payments Management
- [ ] List: filter by payment_method, date range, client_name
- [ ] Add payment: validate amount, date, method
- [ ] Balance recalculation: total_amount_due - sum(payments) = balance
- [ ] Payment methods dropdown: shows only valid options
- [ ] Partial payment support: allow multiple payments per charter
- [ ] Overdue alert: color code overdue invoices red

---

## PART 13: QUERY VALIDATION CHECKLIST

**For each query in the codebase, verify:**

- [ ] Column names exist (check against SCHEMA_REFERENCE.md)
- [ ] Table names spelled correctly
- [ ] JOINs use correct foreign keys (e.g., charters.client_id = clients.client_id)
- [ ] Business key used for matching (reserve_number for charters, client_id for clients, employee_id for employees)
- [ ] WHERE clause filters valid data (no impossible conditions)
- [ ] ORDER BY clause sorts logically (dates ascending/descending, numbers numeric not string)
- [ ] GROUP BY includes all non-aggregated columns
- [ ] HAVING clause used correctly (for aggregate filters)
- [ ] NULL handling: COALESCE or CASE WHEN as needed
- [ ] Subqueries have alias (SELECT ... FROM (SELECT ...) AS alias)
- [ ] DISTINCT used only if necessary (check for duplicates first)
- [ ] LIMIT and OFFSET for pagination
- [ ] No SELECT * (always specify columns)
- [ ] Comments explain complex logic

---

## PART 14: NEXT STEPS

**Phase 1: Database Schema Reference Update** (Copilot can do)
- [ ] Add UI widget types to each column
- [ ] Add field widths and validation rules
- [ ] Document example data for each field type

**Phase 2: Admin Interface Setup** (Requires development)
- [ ] Master dropdown manager (see 5.1)
- [ ] Color coding manager (see 5.2)
- [ ] Error report dashboard (see 9.4)
- [ ] Compliance audit dashboard (see 11.2)

**Phase 3: Core Testing** (Manual testing required)
- [ ] Run through all test cases in Part 12
- [ ] Test all queries against sample data
- [ ] Verify error handling (Part 9)

**Phase 4: Document Management** (Setup required)
- [ ] Create folder structure (see 7.1)
- [ ] Create form templates (PDF or RTF)
- [ ] Test document generation and email

**Phase 5: Go-Live** (After all tests pass)
- [ ] User training
- [ ] Production database backup
- [ ] Monitoring dashboard setup

---

## Error Reporting Summary

**Current system:** Errors logged; refer to error_report_dashboard (Part 9.4)

**To check errors:**
1. Login as admin
2. Navigate to Admin → Error Reports
3. Filter by date, severity, user
4. Review stack trace for developers
5. Mark as reviewed to hide from dashboard

---

**Last Updated:** January 24, 2026
**Prepared for:** Copilot Code Review
