# Arrow Limousine - Complete Accounting Export Capabilities

**Status:** ✅ **COMPLETE** - Multiple export formats available

---

## 1. QuickBooks Desktop Export (CSV Format)

### Available Now
You have **8 QuickBooks Export Views** ready for import into QB Desktop:

| Export Type | Records | Format | Import Path |
|-------------|---------|--------|-------------|
| ✅ AR Aging | 330 | CSV (QB format) | File → Utilities → Import → Excel Files |
| ✅ Balance Sheet | Ready | CSV (QB format) | File → Utilities → Import → Excel Files |
| ✅ Customers | 6,565 | CSV (QB format) | File → Utilities → Import → Excel Files |
| ✅ Employees | 142 | CSV (QB format) | File → Utilities → Import → Excel Files |
| ✅ Invoices | 18,622 | CSV (QB format) | File → Utilities → Import → Excel Files |
| ✅ Profit & Loss | Ready | CSV (QB format) | File → Utilities → Import → Excel Files |
| ✅ Vehicles | 26 | CSV (QB format) | File → Utilities → Import → Excel Files |
| ✅ Vendors | 42,597 | CSV (QB format) | File → Utilities → Import → Excel Files |

### How to Export to QuickBooks

**Option 1: Individual View Export (Single File)**
```
GET http://127.0.0.1:8000/api/reports/quickbooks/export/{view_name}
```
- `view_name` = one of: ar_aging, balance_sheet, customers, employees, invoices, profit_loss, vehicles, vendors
- `format` = csv (default)
- `start_date` and `end_date` optional (YYYY-MM-DD format)

**Example:**
```
GET http://127.0.0.1:8000/api/reports/quickbooks/export/qb_export_invoices
```
Returns: Single CSV file ready for QB Desktop import

**Option 2: Complete Export (All Views as ZIP)**
```
GET http://127.0.0.1:8000/api/reports/quickbooks/export-all
```
- Returns: All 8 views in a single ZIP file
- Includes: README.txt with import instructions
- Optional: start_date and end_date for filtering

**Example:**
```
GET http://127.0.0.1:8000/api/reports/quickbooks/export-all?start_date=2024-01-01&end_date=2024-12-31
```
Returns: `QuickBooks_Export_20250101_120000_2024-01-01_to_2024-12-31.zip`

---

## 2. Annual Accounting Reports (Per Year)

### Accounting Reports Available

| Report | Endpoint | Format | Date Range Support | Status |
|--------|----------|--------|-------------------|--------|
| Trial Balance | `/api/reports/trial-balance` | JSON | By date | ✅ Ready |
| General Ledger / Journals | `/api/reports/journals` | JSON | By date range | ✅ Ready |
| Profit & Loss | `/api/reports/pl-summary` | JSON | Monthly/Quarterly/Annual | ✅ Ready |
| Bank Reconciliation | `/api/reports/bank-reconciliation` | JSON | By date | ✅ Ready |
| Customer A/R Aging | `/api/reports/ar-aging` | JSON | Current | ✅ Ready |

### Export These Reports to CSV

You can export any accounting report to CSV format:

```
GET http://127.0.0.1:8000/api/reports/export?type=revenue-summary&format=csv&start_date=2024-01-01&end_date=2024-12-31
```

Returns: CSV file with annual data

---

## 3. Desktop Application Export

### From the Desktop App

All financial reports in the desktop app include:
- ✅ **CSV Export** - Click "Export to CSV" button
- ✅ **Print to PDF** - Click "Print Report" → Print to PDF printer
- ✅ **View Source Data** - Click any row to see detail

### Reports Available in Desktop App

**Navigation Tab:** Navigator → Select any report
- Trial Balance
- General Ledger / Journals
- Profit & Loss
- Bank Reconciliation  
- Vehicle Performance
- Driver Costs
- Customer Payments
- Receivables Aging
- Account Analysis

---

## 4. Summary of Export Formats

| Format | Use Case | Where | Annual | Per-Year | Status |
|--------|----------|-------|--------|----------|--------|
| **CSV** | QB Desktop Import | API & Desktop App | ✅ Yes | ✅ Yes | ✅ Ready |
| **CSV** | Generic Data Analysis | All reports | ✅ Yes | ✅ Yes | ✅ Ready |
| **PDF** | Printing / Archiving | Desktop App | ✅ Yes | ✅ Yes | ✅ Ready |
| **JSON** | API Consumption | All endpoints | ✅ Yes | ✅ Yes | ✅ Ready |
| **IIF** (QB Interchange) | QB Classic | Not implemented | - | - | ❌ Future |
| **QBO** (QB Online) | QB Online Sync | Not implemented | - | - | ❌ Future |
| **XML** | Accounting Software | Not implemented | - | - | ❌ Future |

---

## 5. Specific Use Cases

### Use Case 1: Annual Trial Balance to QB Desktop
```
1. Go to: http://127.0.0.1:8000/api/reports/quickbooks/export/qb_export_balance_sheet
2. Save as: Trial_Balance_2024.csv
3. Open QB Desktop
4. File → Utilities → Import → Excel Files
5. Select Trial_Balance_2024.csv
6. Follow import wizard
```

### Use Case 2: Annual P&L Statement to QB Desktop
```
1. Go to: http://127.0.0.1:8000/api/reports/quickbooks/export/qb_export_profit_loss
2. Save as: P&L_2024.csv
3. Open QB Desktop
4. File → Utilities → Import → Excel Files
5. Select P&L_2024.csv
```

### Use Case 3: Customer List to QB Desktop
```
1. Go to: http://127.0.0.1:8000/api/reports/quickbooks/export/qb_export_customers
2. Save as: Customers_2024.csv
3. Open QB Desktop
4. File → Utilities → Import → Excel Files
5. Select Customers_2024.csv
```

### Use Case 4: Complete Annual Export (All Tables)
```
1. Go to: http://127.0.0.1:8000/api/reports/quickbooks/export-all?start_date=2024-01-01&end_date=2024-12-31
2. Download: QuickBooks_Export_20250101_*.zip
3. Extract ZIP file
4. Import each CSV one at a time into QB Desktop
5. Use README.txt for import order (Chart of Accounts → Customers/Vendors → Transactions)
```

### Use Case 5: Export from Desktop App for Email/Sharing
```
1. Open Desktop App
2. Select any report (Trial Balance, P&L, etc.)
3. Click "Export to CSV" → Save to file
4. OR Click "Print Report" → Print to PDF → Save PDF
5. Share file via email
```

---

## 6. Data Available for Export

### Complete Financial Data
✅ **Customers**: 6,565 records  
✅ **Vendors**: 42,597 records  
✅ **Employees**: 142 records  
✅ **Vehicles**: 26 records  
✅ **Invoices/Charters**: 18,622 records  
✅ **A/R Aging**: 330 records  

### Accounting Ledgers
✅ **Trial Balance** - Per date  
✅ **General Ledger** - Transaction detail  
✅ **Profit & Loss** - Monthly/Quarterly/Annual  
✅ **Bank Reconciliation** - Bank statements vs ledger  

---

## 7. Recommended Workflow

### Annual Accounting Cycle

1. **Mid-Year** - Export current data to QB
   ```
   GET .../quickbooks/export-all (no date filter)
   ```

2. **Year-End** - Export complete annual data
   ```
   GET .../quickbooks/export-all?start_date=2024-01-01&end_date=2024-12-31
   ```

3. **Archival** - Save exported CSVs in year folder
   ```
   2024/
      ├── QB_Export_Customers_2024.csv
      ├── QB_Export_Vendors_2024.csv
      ├── QB_Export_Invoices_2024.csv
      ├── QB_Export_TrialBalance_2024.csv
      └── QB_Export_PL_2024.csv
   ```

4. **Verification** - Compare QB desktop balances with exported data

5. **Audit** - Review exported CSVs for accuracy before final import

---

## 8. Technical Information

### Backend API
- **Server**: FastAPI (http://127.0.0.1:8000)
- **Database**: PostgreSQL (almsdata)
- **QB Export Views**: 8 views (pre-built SQL)
- **Endpoints**: 15+ reporting endpoints

### Desktop App
- **Framework**: PyQt6
- **Export Formats**: CSV, PDF (Print)
- **Data Sources**: All 9 report types

### QB Integration
- **Status**: Export-ready (import scripts exist from previous session)
- **Format**: CSV (QB Desktop native format)
- **Support**: All QB Desktop versions (2016+)
- **Migration**: Previously imported QB data (April 2012+)

---

## 9. What's NOT Implemented (Future Enhancements)

| Feature | Status | Why | Effort |
|---------|--------|-----|--------|
| IIF Format (.iif) | Not planned | QB deprecated in favor of CSV | Medium |
| QBO Format | Not planned | QB Online is cloud-only | High |
| XML Export | On request | For integrations with other software | Medium |
| Multi-currency | Not applicable | USD only | - |
| Real-time sync | Not planned | QB doesn't support bidirectional | High |

---

## 10. Quick Start

### To Test QB Export Right Now:

1. **Start the backend** (if not running):
   ```
   cd L:\limo
   python -m uvicorn modern_backend.app.main:app --host 127.0.0.1 --port 8000
   ```

2. **Download complete QB export**:
   - Open browser: `http://127.0.0.1:8000/api/reports/quickbooks/export-all`
   - Save ZIP file
   - Extract all CSVs

3. **Open QuickBooks Desktop**:
   - File → Utilities → Import → Excel Files
   - Select first CSV (Customers recommended)
   - Follow import wizard

---

## Summary

✅ **You have complete accounting export capability:**
- ✅ Annual exports by year
- ✅ QB Desktop CSV format (ready to import)
- ✅ All accounting reports (Trial Balance, P&L, GL, etc.)
- ✅ Customer/Vendor/Employee lists
- ✅ Per-year filtering support
- ✅ PDF/Print capability
- ✅ 8 specialized QB export views

**Missing:**
- ❌ QB Online (QBO) - requires separate implementation
- ❌ IIF format - deprecated by Intuit
- ❌ XML export - can be added on request

**Recommendation:** Use CSV exports → QB Desktop is your best option right now.

---

**Last Updated:** December 23, 2025  
**Database:** almsdata (PostgreSQL)  
**Status:** Production Ready
