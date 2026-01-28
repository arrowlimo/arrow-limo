# QuickBooks Export Quick Reference

## One-Click Export URLs

### Individual Views (Save directly from browser)

**A/R Aging:**
```
http://127.0.0.1:8000/api/reports/quickbooks/export/qb_export_ar_aging
```

**Balance Sheet:**
```
http://127.0.0.1:8000/api/reports/quickbooks/export/qb_export_balance_sheet
```

**Customers:**
```
http://127.0.0.1:8000/api/reports/quickbooks/export/qb_export_customers
```

**Employees:**
```
http://127.0.0.1:8000/api/reports/quickbooks/export/qb_export_employees
```

**Invoices (Charters):**
```
http://127.0.0.1:8000/api/reports/quickbooks/export/qb_export_invoices
```

**Profit & Loss:**
```
http://127.0.0.1:8000/api/reports/quickbooks/export/qb_export_profit_loss
```

**Vehicles:**
```
http://127.0.0.1:8000/api/reports/quickbooks/export/qb_export_vehicles
```

**Vendors:**
```
http://127.0.0.1:8000/api/reports/quickbooks/export/qb_export_vendors
```

---

## Complete Export (All Files as ZIP)

### No Date Filter (All Time):
```
http://127.0.0.1:8000/api/reports/quickbooks/export-all
```

### Year 2024:
```
http://127.0.0.1:8000/api/reports/quickbooks/export-all?start_date=2024-01-01&end_date=2024-12-31
```

### Year 2023:
```
http://127.0.0.1:8000/api/reports/quickbooks/export-all?start_date=2023-01-01&end_date=2023-12-31
```

### Year 2022:
```
http://127.0.0.1:8000/api/reports/quickbooks/export-all?start_date=2022-01-01&end_date=2022-12-31
```

### Custom Date Range (Q1 2024):
```
http://127.0.0.1:8000/api/reports/quickbooks/export-all?start_date=2024-01-01&end_date=2024-03-31
```

### Last 6 Months:
```
http://127.0.0.1:8000/api/reports/quickbooks/export-all?start_date=2024-07-23&end_date=2024-12-23
```

---

## How to Use

### Step 1: Copy URL
1. Copy the URL above for what you want to export
2. Paste into browser address bar
3. Press Enter

### Step 2: Download File
1. Browser downloads CSV (individual) or ZIP (complete)
2. Save file to your computer

### Step 3: Import to QuickBooks
1. Open QuickBooks Desktop
2. Go to: **File → Utilities → Import → Excel Files**
3. Select the CSV file
4. Follow the import wizard
5. QuickBooks column mapping should be automatic

### Step 4: Verify
1. In QB, check one of the imported reports
2. Verify records appear correctly
3. Check balances match expected amounts

---

## What Each Export Contains

| View | Use For | Recommended Order |
|------|---------|-------------------|
| customers | Customer list sync | 3rd (after COA & vendors) |
| vendors | Vendor list sync | 2nd (after COA) |
| employees | Employee list sync | 2nd (after COA) |
| invoices | Charge/income records | 4th (last) |
| ar_aging | Aged receivables report | Report only (don't import) |
| balance_sheet | Account balances | Verify only (don't import) |
| profit_loss | P&L report | Verify only (don't import) |
| vehicles | Asset list | 2nd (after COA) |

---

## Import Order (If Importing Complete ZIP)

1. Start with **Chart of Accounts** (if needed)
2. Then **Vendors** (suppliers)
3. Then **Customers** (clients)
4. Then **Employees** (staff)
5. Finally **Invoices** (transactions)

Note: Use the included README.txt in ZIP for detailed instructions.

---

## Technical Details

**Format:** CSV (Comma-Separated Values)
**Encoding:** UTF-8
**Delimiter:** Comma
**Headers:** Yes (included)
**Compatibility:** QB 2016 and newer
**Size:** ~5-20 MB per year
**Records:** See ACCOUNTING_EXPORT_CAPABILITIES.md

---

## Common Issues & Solutions

**Q: File won't import**
- A: Make sure file is .csv not .txt
- A: Try saving with UTF-8 encoding
- A: Check column count matches QB expected

**Q: Data looks wrong**
- A: Verify date range was correct
- A: Check filter applied properly
- A: Export again and compare

**Q: Missing data**
- A: Check start_date and end_date parameters
- A: Verify data exists in source database
- A: Run complete export without date filter

**Q: QB says "Invalid format"**
- A: Redownload file (might be corrupted)
- A: Try different QB version
- A: Contact support if persists

---

## Example Workflow

### Annual Year-End Export

```
Step 1: Create folders
  L:\Accounting\2024_QB_Export\

Step 2: Export all data for 2024
  http://127.0.0.1:8000/api/reports/quickbooks/export-all?start_date=2024-01-01&end_date=2024-12-31
  Download: QuickBooks_Export_20250101_2024-01-01_to_2024-12-31.zip
  Extract to: L:\Accounting\2024_QB_Export\

Step 3: Verify files
  Customers_20.csv - 6565 records
  Vendors.csv - 42597 records
  Invoices.csv - 18622 records
  etc.

Step 4: Import to QB Desktop
  File → Utilities → Import → Excel Files
  Import in order: Vendors → Customers → Invoices

Step 5: Archive
  Keep all CSVs in 2024_QB_Export folder for records

Step 6: Next year
  Repeat with 2025 dates
```

---

## Available Data Summary

✅ **6,565** Customers with contact info  
✅ **42,597** Vendors with accounts  
✅ **142** Employees with pay info  
✅ **26** Vehicles with specs  
✅ **18,622** Invoices (Charters) with amounts  
✅ **330** A/R Aging records  

All data current as of: **2025-12-23**

---

**Need more help?** See ACCOUNTING_EXPORT_CAPABILITIES.md for detailed information.
