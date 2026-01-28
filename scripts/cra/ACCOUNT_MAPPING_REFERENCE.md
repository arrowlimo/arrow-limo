# Arrow Limousine Chart of Accounts - CRA Mapping Reference

**Generated:** October 18, 2025  
**Database:** almsdata.general_ledger  
**Purpose:** Document GL accounts discovered for CRA form automation

## GST/HST Accounts

### 2200 GST/HST Payable
- **Transactions:** 39,575
- **Debits:** $6,448,168.83
- **Credits:** $6,349,487.21
- **Net Balance:** -$98,681.62 (liability)
- **CRA Usage:** Line 105 (GST/HST Collected)

### GST/HST Payable (duplicate/legacy)
- **Transactions:** 16
- **Debits:** $171.68
- **Credits:** $0.00
- **Net Balance:** -$171.68
- **CRA Usage:** Line 105 (GST/HST Collected) - consolidate with 2200

### 2205 GST Remits
- **Transactions:** 7
- **Debits:** $23,043.06
- **Credits:** $0.00
- **Net Balance:** -$23,043.06
- **CRA Usage:** Line 113A (Installments Paid)

## Revenue Accounts

### 4000 Limousine Service Income
- **Transactions:** 53
- **Net Revenue:** $8,958,476.30
- **CRA Usage:** Line 101 (Total Sales)

### 4300 Gratuity Income
- **Transactions:** 21
- **Net Revenue:** $609,114.32
- **CRA Usage:** Line 101 (Total Sales)

### 4800 Other Income
- **Transactions:** 25
- **Net Revenue:** $8,918.60
- **CRA Usage:** Line 101 (Total Sales)

**Total Revenue (all time):** $9,576,509.22

## Payroll/Source Deduction Accounts

### 1085 Payroll Clearing Account
- **Transactions:** 1,206
- **Debits:** $906,377.20
- **Credits:** $1,020,344.21
- **Net Balance:** $113,967.01
- **CRA Usage:** Intermediate clearing for payroll processing

### 2100 Payroll Liabilities
- **Transactions:** 2,098
- **Debits:** $104,707.71
- **Credits:** $514,206.16
- **Net Balance:** $409,498.45 (liability)
- **CRA Usage:** PD7A source deductions (CPP, EI, Income Tax withheld)

### 6605 Payroll Expenses
- **Transactions:** 676
- **Debits:** $419,552.06
- **Credits:** $0.00
- **Net Balance:** -$419,552.06 (expense)
- **CRA Usage:** Employer portion of CPP/EI

## 2025 Summary (Jan 1 - Sep 30)

### GST/HST
- **Total Revenue/Sales:** $3,598,633.21
- **GST/HST Collected:** $53,505.97
- **ITCs (GST Paid):** $0.00 *(no ITC account found)*
- **Net GST/HST Owing:** $53,505.97

### Notes
1. **No ITC Account Found:** The company may not be tracking GST paid on expenses separately, or ITCs may be netted directly against `2200 GST/HST Payable`. Need to verify if expense GST is being captured.

2. **Payroll Detail Missing:** The `2100 Payroll Liabilities` account appears to be a summary. Need to check if CPP employee, CPP employer, EI employee, EI employer, and Income Tax withholdings are tracked in sub-accounts or memo fields.

3. **Account Numbering:** Some accounts have numeric prefixes (e.g., "2200"), others don't (e.g., "GST/HST Payable"). Should standardize.

## Next Steps for CRA Automation

1. **GST34 Mapping:** ✅ Complete with current accounts
   - Line 101: Sum of 4000, 4300, 4800
   - Line 105: Sum of 2200 + GST/HST Payable
   - Line 108: $0 (no ITC account) - **needs investigation**
   - Line 113A: 2205 GST Remits

2. **PD7A Mapping:** Requires breakdown of 2100 Payroll Liabilities
   - Need to identify CPP employee vs employer
   - Need to identify EI employee vs employer
   - Need to identify Income Tax withheld
   - May require transaction-level analysis or memo parsing

3. **Data Quality:**
   - Investigate why ITCs are $0 (are purchases tracked elsewhere?)
   - Check if payroll liabilities have sub-ledgers or detail in memo fields
   - Verify GST rate (should be 5% of taxable sales)

## Verification Queries

```sql
-- Check if GST/HST Payable balance makes sense (should be ~5% of revenue)
SELECT 
    SUM(COALESCE(credit,0) - COALESCE(debit,0)) as revenue,
    (SELECT SUM(COALESCE(credit,0) - COALESCE(debit,0)) 
     FROM general_ledger 
     WHERE account IN ('2200 GST/HST Payable', 'GST/HST Payable')
     AND date BETWEEN '2025-01-01' AND '2025-09-30') as gst_collected,
    (SELECT SUM(COALESCE(credit,0) - COALESCE(debit,0)) 
     FROM general_ledger 
     WHERE account IN ('2200 GST/HST Payable', 'GST/HST Payable')
     AND date BETWEEN '2025-01-01' AND '2025-09-30') / 
    SUM(COALESCE(credit,0) - COALESCE(debit,0)) * 100 as gst_percentage
FROM general_ledger
WHERE account IN ('4000 Limousine Service Income', '4300 Gratuity Income', '4800 Other Income')
AND date BETWEEN '2025-01-01' AND '2025-09-30';

-- Check for expense accounts that might have GST embedded
SELECT DISTINCT account
FROM general_ledger
WHERE (account LIKE '5%' OR account LIKE '6%')
  AND account NOT LIKE '%Payroll%'
ORDER BY account;
```
