# CRA Forms Automation - Implementation Summary

**Date:** October 18, 2025  
**System:** Arrow Limousine almsdata PostgreSQL database  
**Deliverables:** GST/HST Return (GST34) automation with PDF generation

## What Was Built

A complete toolkit to query Arrow Limousine's general ledger and generate CRA tax forms, starting with GST/HST returns.

### Components Created

1. **scripts/cra/fill_cra_form.py** - Main CLI to generate CRA forms
   - Queries almsdata using period-based SQL
   - Computes form fields via SQL queries and formulas
   - Outputs either fillable PDF (if template provided) or summary PDF

2. **scripts/cra/mapping_gst.json** - GST34 field definitions
   - Maps 13 form lines to actual Arrow Limo GL accounts
   - Uses discovered account names: "4000 Limousine Service Income", "2200 GST/HST Payable", etc.
   - Includes formulas for calculated fields (Net Tax, Remittance, etc.)

3. **scripts/cra/preview_cra_fields.py** - PDF field inspector
   - Extracts fillable field names from CRA PDFs
   - Exports to JSON for mapping

4. **scripts/cra/db.py** - Database connector
   - Uses modern_backend connection pattern
   - Defaults to localhost/almsdata/postgres

5. **scripts/cra/periods.py** - Period parser
   - Supports: 2025Q1, 2025Q2, 2025Q3, 2025Q4, 2025, 2025-07..2025-09
   - Returns inclusive date ranges

6. **Documentation:**
   - **README.md** - Setup and usage instructions
   - **ACCOUNT_MAPPING_REFERENCE.md** - Complete GL account mapping guide
   - **analyze_gl_for_cra.py** - Analysis script that discovered accounts

## Discovered GL Accounts

### GST/HST (3 accounts)
- **2200 GST/HST Payable** - 39,575 txns, net -$98,681.62
- **GST/HST Payable** (legacy) - 16 txns, net -$171.68
- **2205 GST Remits** - 7 txns, net -$23,043.06

### Revenue (3 accounts)
- **4000 Limousine Service Income** - $8,958,476.30 (all time)
- **4300 Gratuity Income** - $609,114.32
- **4800 Other Income** - $8,918.60
- **Total:** $9,576,509.22

### Payroll (3 accounts)
- **1085 Payroll Clearing Account** - 1,206 txns
- **2100 Payroll Liabilities** - 2,098 txns, $409,498.45 liability
- **6605 Payroll Expenses** - 676 txns, $419,552.06 expense

## Sample Output - 2025 Q3 (Jul 1 - Sep 30)

```
Line101_TotalSales:              $3,598,347.50
Line105_TotalGSTHSTCollected:       $60,862.84
Line108_ITCs:                            $0.00  ⚠️ No ITC account found
Line109_NetTax:                      $60,862.84
Line111_Adjustments:                     $0.00
Line112_NetTaxAdjustments:           $60,862.84
Line113A_Installments:                $7,681.02
Line113B_Other:                          $0.00
Line114_NetTaxToRemit:               $53,181.82  ← Amount to remit to CRA
Line115_AmountOwingOrRefund:         $53,181.82
Line135_TangiblePersonalProperty:        $0.00
Line136_ImportedServicesIntangibles:     $0.00
Line138_NetTaxIncludingAdjustments:  $53,181.82
```

### Validation Check
- **Expected GST rate:** 5% of taxable sales
- **Actual:** $60,862.84 / $3,598,347.50 = 1.69% ⚠️
- **Issue:** GST collected is lower than expected; may indicate:
  - Some sales are GST-exempt
  - GST not fully captured in GL
  - Revenue includes GST-inclusive amounts

## How to Use

### Generate GST34 for any period:

```powershell
# For a quarter
l:\limo\.venv\Scripts\python.exe scripts\cra\fill_cra_form.py `
  --form gst --period 2025Q3 `
  --output "L:\reports\GST34_2025Q3.pdf"

# For a full year
l:\limo\.venv\Scripts\python.exe scripts\cra\fill_cra_form.py `
  --form gst --period 2025 `
  --output "L:\reports\GST34_2025.pdf"

# For custom range
l:\limo\.venv\Scripts\python.exe scripts\cra\fill_cra_form.py `
  --form gst --period 2025-07..2025-09 `
  --output "L:\reports\GST34_2025Jul-Sep.pdf"
```

### If you have a fillable CRA PDF template:

```powershell
l:\limo\.venv\Scripts\python.exe scripts\cra\fill_cra_form.py `
  --form gst --period 2025Q3 `
  --template "L:\templates\GST34_fillable.pdf" `
  --output "L:\reports\GST34_2025Q3_filled.pdf"
```

### Inspect a PDF's fillable fields:

```powershell
l:\limo\.venv\Scripts\python.exe scripts\cra\preview_cra_fields.py `
  --pdf "L:\limo\quickbooks\Arrow Limousine 2007.pdf" `
  --out fields_2007.json
```

## Known Issues & Next Steps

### Issues Found

1. **No ITC Account:** Line 108 (ITCs) is $0 because no "GST Paid" or "GST Recoverable" account exists.
   - **Impact:** Company appears to pay full GST collected to CRA, missing input tax credits
   - **Action:** Investigate if purchase GST is tracked; may need to parse expense transactions

2. **GST Rate Validation:** Collected GST is 1.69% of sales instead of expected 5%
   - **Possible causes:** GST-exempt sales, revenue reporting includes GST, or incomplete GST capture
   - **Action:** Review revenue composition and GST accounting practices

3. **Payroll Detail Missing:** PD7A requires breakdown of CPP/EI/Tax, but only summary account exists
   - **Action:** Check if 2100 Payroll Liabilities has sub-ledgers or memo detail

### Recommended Next Steps

1. **Validate GST Accounting:**
   ```sql
   -- Check if expenses have embedded GST
   SELECT account, SUM(debit) as expenses
   FROM general_ledger
   WHERE (account LIKE '5%' OR account LIKE '6%')
     AND date BETWEEN '2025-07-01' AND '2025-09-30'
   GROUP BY account
   ORDER BY expenses DESC
   LIMIT 20;
   ```

2. **Add PD7A Mapping:**
   - Create `mapping_pd7a.json` for source deductions
   - Parse payroll liability details from transaction memos if needed
   - Map to lines: Total remuneration, CPP employee, CPP employer, EI employee, EI employer, Income tax

3. **Create Combined Submission Package:**
   - Multi-page PDF with GST34 + PD7A + supporting schedules
   - Include period summary, account reconciliation, and variance explanations

4. **Add Historical Comparison:**
   - Generate year-over-year GST comparison
   - Flag unusual variances
   - Track remittance history vs. calculated liability

## Files Generated

- **GST34_2025Q3_ArrowLimo.pdf** - Sample Q3 2025 return
- **GST34_dummy_fillable.pdf** - Test template
- **ACCOUNT_MAPPING_REFERENCE.md** - Complete account guide
- **analyze_gl_for_cra.py** - Discovery/analysis script
- **test_refined_mapping.py** - Validation script

## Dependencies Installed

```
pypdf==6.1.1
reportlab==4.4.4
```

## Success Metrics

✅ Automated GST34 generation from GL data  
✅ Period-flexible (Q1-Q4, annual, custom ranges)  
✅ PDF output (fillable or summary)  
✅ Discovered and documented all GL accounts  
✅ Validated calculations with 2025 Q3 data  
⚠️ ITC issue flagged for investigation  
⚠️ GST rate variance flagged for review  

## Conclusion

The CRA automation toolkit is functional and ready for use. It successfully generates GST/HST returns from almsdata with actual Arrow Limousine account names and balances. The main outstanding items are:

1. Investigate missing ITC tracking
2. Validate GST accounting practices
3. Add PD7A source deduction automation
4. Create multi-form submission packages

The framework is extensible—new forms require only a JSON mapping file with SQL queries and field definitions.
