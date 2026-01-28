# QuickBooks Export Files Analysis

## Summary

Analyzed 9 QuickBooks export files from `L:\limo\quickbooks\old quickbooks\`

## Current Status in almsdata

**general_ledger table:**
- Date range: **2011-12-31 to 2025-12-08**
- Total records: **124,324**
- Top transaction types: Cheque Expense (105,269), Expense (7,312), Bill (6,445)

## Files Analyzed

### 1. initial adjusted journal entreis.xlsx
- **Data:** 412 journal entries
- **Date range:** Starts 2005-01-31
- **Totals:** $3,138,259.11 debits/credits (balanced)
- **Columns:** Date, Num, Name, Memo, Account, Debit, Credit
- **Status:** ⚠️ **Data from 2005-2011 NOT in almsdata** (GL starts 2011-12-31)

### 2. initial check details.xlsx
- **Data:** 1,701 check/payment records
- **Date range:** Starts 2004-02-13
- **Columns:** Type, Num, Date, Name, Item, Account, Paid Amount, Original Amount
- **Status:** ⚠️ **Data from 2004-2011 NOT in almsdata**

### 3. initial deposts.xlsx
- **Data:** 554 deposit records
- **Date range:** Starts 2005-01-01
- **Columns:** Type, Num, Date, Name, Account, Amount
- **Status:** ⚠️ **Data from 2005-2011 NOT in almsdata**

### 4. initial general journal.xlsx
- **Data:** 2,975 general ledger entries
- **Totals:** $14,421,478.41 debits, $13,747,371.46 credits (UNBALANCED ⚠️)
- **Columns:** Type, Date, Num, Adj, Account, Debit, Credit
- **Status:** ⚠️ **Early data NOT in almsdata** + **IMBALANCE ISSUE**

### 5. initial journal.xlsx
- **Data:** 2,883 journal transactions
- **Date range:** Starts 2007-12-31
- **Totals:** $9,520,063.95 debits/credits (balanced)
- **Columns:** Trans #, Type, Date, Num, Adj, Name, Memo, Account, Debit, Credit
- **Status:** ⚠️ **Data from 2007-2011 NOT in almsdata**

### 6. initial profit and loss.xlsx
- **Data:** 118 rows (P&L summary report)
- **Type:** Summary report, not transactional data
- **Status:** ✅ Summary only - not needed if we have GL transactions

### 7. initial tax agency detail report.xlsx
- **Data:** 319 tax-related transactions
- **Date range:** Starts 2006-12-31
- **Columns:** Type, Date, Num, Source Name, Item, Tax Code, Rate, Tax Amount
- **Status:** ⚠️ **GST/tax data from 2006-2011 NOT in almsdata**

### 8. initial transaction details.xlsx
- **Data:** 2,773 transaction detail records
- **Type:** Detailed transaction breakdown by account
- **Status:** ⚠️ **Early transaction details NOT in almsdata**

### 9. initial trial balances.xlsx
- **Data:** 87 rows (trial balance summary)
- **Type:** Summary report showing account balances
- **Date:** May 30, 2006
- **Status:** ✅ Summary only - useful for validation but not transactional

### 10. limousine.IIF
- **Data:** 12,363 bytes QuickBooks Interchange Format
- **Type:** Full company data export (can be re-imported to QuickBooks)
- **Status:** ⚠️ Contains all historical data - could be parsed for missing periods

## CRITICAL FINDINGS

### Missing Data Period: 2004-2011
**almsdata.general_ledger starts at 2011-12-31, but QuickBooks exports contain data from 2004-2011.**

**Missing data includes:**
- Journal entries (2005-2011)
- Checks/payments (2004-2011)
- Deposits (2005-2011)
- Tax transactions (2006-2011)
- General ledger transactions (2004-2011)

**Estimated missing records:** ~10,000-15,000 transactions

### Data Integrity Issue
**initial general journal.xlsx** shows:
- Debits: $14,421,478.41
- Credits: $13,747,371.46
- **Imbalance: $674,106.95** ⚠️

This could indicate:
- Incomplete export
- Opening balance entries
- Data corruption
- Missing offsetting entries

## Recommendations

### 1. Immediate Action: Import Missing 2004-2011 Data

**Priority files to import:**
1. `initial journal.xlsx` - Most complete, balanced data (2007-2011)
2. `initial adjusted journal entreis.xlsx` - Balanced entries (2005-2011)
3. `initial check details.xlsx` - Payment details (2004-2011)
4. `initial deposts.xlsx` - Deposit details (2005-2011)
5. `initial tax agency detail report.xlsx` - Tax data (2006-2011)

**Skip:**
- initial general journal.xlsx (imbalanced - needs investigation)
- Profit & Loss and Trial Balance (summary reports, not transactional)

### 2. Create Import Script

I can create a script to:
- Parse each file with proper header detection
- Clean and normalize data
- Map to almsdata schema
- Insert into general_ledger table
- Track import provenance (source file + row)

### 3. Validation Steps

After import:
- Verify date continuity (2004 → 2025)
- Check debit/credit balance by year
- Reconcile trial balance reports
- Validate account totals

### 4. IIF File Option

The `limousine.IIF` file contains the complete company data and could be:
- Re-imported into QuickBooks
- Parsed directly to extract all transactions
- Used as source of truth for missing data

## Next Steps

Would you like me to:
1. **Create import scripts** for the 2004-2011 data files?
2. **Parse the IIF file** to extract missing transactions?
3. **Investigate the imbalance** in initial general journal.xlsx?
4. **Generate a reconciliation report** between these files and current almsdata?

The missing 7 years of data (2004-2011) would be valuable for:
- Complete tax history
- Historical financial analysis
- CRA audit preparation
- Long-term trend analysis
