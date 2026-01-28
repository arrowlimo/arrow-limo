# Arrow Limousine Desktop Application

**Form-based desktop ERP system** with tab navigation, auto-fill, drill-down reports, and document generation.

## Features

### ✅ Charter/Booking Management
- **Grouped form sections**: Customer → Itinerary → Invoicing → Notes
- **Tab navigation**: Press Tab to move through fields
- **Auto-fill**: Type customer name, auto-populates phone/email/address
- **Line-by-line routing**: Add multiple pickup/dropoff locations
- **Beverage itemized lookup**: Search and add beverage items to invoice
- **Print**: Confirmation forms and invoices

### ✅ Invoice Management
- Add charge lines with quantity, price, GST auto-calculation
- Separate invoice creation or attach to charter
- Print professional invoices

### ✅ Vehicle Management
- Maintenance tracking with PDF storage
- CVIP certificates, bill of sale documents
- Service history logs

### ✅ Employee/Driver Management
- Employee status: Current, Fired, Retired
- Payroll processing
- HOS (Hours of Service) tracking
- Driver assignment to charters

### ✅ Accounting & CRA
- Receipts entry with GST tracking
- Expense categorization
- GST remittance reports
- T4 generation
- Personal vs business expense splitting

### ✅ Advanced Reporting
- **Drill-down reports**: Double-click to expand Year → Month → Week → Charter → Charges
- **Arrow collapse/expand**: Navigate with keyboard
- **"Open All"**: See every detail at once
- **JSON export**: Mass query data for external analysis
- **Excel export**: Formatted reports with formulas
- **Custom report designer**: Build your own reports

## Installation

```powershell
cd l:\limo\desktop_app
pip install -r requirements.txt
python main.py
```

## Database Connection

Uses existing PostgreSQL database (almsdata):
- Host: localhost
- Port: 5432
- Database: almsdata
- User: postgres
- Password: ***REMOVED***

## Keyboard Shortcuts

- **Ctrl+S**: Save current form
- **Ctrl+P**: Print current document
- **Ctrl+N**: New record
- **Tab**: Navigate to next field
- **Shift+Tab**: Navigate to previous field
- **F5**: Refresh data
- **Ctrl+F**: Search/Find

## Packaging as .EXE

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --icon=arrow.ico main.py
```

This creates a single .exe file in `dist/` folder that can run on any Windows machine without Python installed.

## Report Types

### Revenue Drill-Down
- Year → Month → Week → Customer → Charter → Charge Lines
- Shows revenue breakdown at every level
- Export to JSON for mass analysis

### Expense Drill-Down
- Year → Month → Category → Vendor → Receipt
- Track business vs personal expenses
- GST analysis

### Customer Activity
- Customer → Charters → Payments → Balance
- Identify top customers
- Payment history

### Vehicle Utilization
- Vehicle → Year → Month → Charters → Revenue
- Maintenance costs vs revenue
- ROI analysis

### Driver Performance
- Driver → Month → Charters → Hours → Pay
- HOS compliance tracking
- Performance metrics

## Form Field Auto-Fill Rules

**Customer Search**:
- Type 3+ characters → Auto-fill name, phone, email, address from database
- Shows top 5 matches
- Tab to accept, continue typing to refine

**Vehicle Assignment**:
- Auto-filter available vehicles based on charter date/time
- Show maintenance status warnings

**Driver Assignment**:
- Auto-filter drivers with proper licenses
- Check HOS availability
- Show conflicts if double-booked

**Beverage Lookup**:
- Search by name or category
- Shows current inventory
- Auto-add to invoice with pricing

## Document Generation

**Confirmation Forms**:
- Professional PDF with company logo
- Itinerary details, vehicle info, driver name
- Payment terms and cancellation policy

**Invoices**:
- Itemized charges with GST breakdown
- Payment history if partial payment
- Outstanding balance highlighted

**Receipts**:
- Expense receipts for accounting
- GST-compliant format
- Attach scanned receipt images

## Next Steps

1. Complete customer management tab
2. Add vehicle maintenance tracking
3. Build employee payroll module
4. Implement PDF document storage browser
5. Create custom report designer
6. Add email integration for confirmations/invoices
