# CRA Forms Quick Start Guide

## What You Have

A working system to generate CRA GST/HST returns (GST34) directly from your almsdata PostgreSQL database.

## Generate Your First Form

```powershell
# Generate GST34 for 2025 Q3 (July-September)
l:\limo\.venv\Scripts\python.exe scripts\cra\fill_cra_form.py `
  --form gst `
  --period 2025Q3 `
  --output "L:\reports\GST34_2025Q3.pdf"
```

**Output:** A summary PDF with all 13 GST34 form lines filled with your actual data.

## Your 2025 Q3 Numbers (Jul 1 - Sep 30)

```
Total Sales (Line 101):              $3,598,347.50
GST/HST Collected (Line 105):           $60,862.84
Input Tax Credits (Line 108):                $0.00  ⚠️
Net Tax (Line 109):                      $60,862.84
Installments Paid (Line 113A):            $7,681.02
───────────────────────────────────────────────────
Amount to Remit (Line 114):              $53,181.82
```

## Important Findings

### ⚠️ GST Accounting Issue Detected

Your revenue shows $3.6M but GST collected is only $60K (1.69% instead of expected 5%).

**Expected GST at 5%:** $179,917.38  
**Actual GST collected:** $60,862.84  
**Shortfall:** $119,054.54

**Likely explanation:** Revenue figures may already include GST (GST-inclusive pricing), meaning:
- If revenue is GST-inclusive, actual pre-tax revenue ≈ $3,598,347.50 / 1.05 = $3,427,000
- GST component would be: $3,427,000 × 0.05 = $171,350
- This would explain why GL shows lower GST (transactions may be splitting revenue vs. GST differently)

**Action needed:** Review how revenue and GST are recorded in your bookkeeping.

### ⚠️ No Input Tax Credits (ITCs)

Line 108 shows $0 because no "GST Paid" or "GST Recoverable" account was found.

This means you're potentially:
- Not claiming GST paid on business expenses
- Missing out on significant tax recovery
- Remitting more GST than necessary

**Action needed:** Verify if purchase GST is being tracked; may need to review expense transactions.

## GL Accounts Used

### Revenue (Line 101)
- 4000 Limousine Service Income
- 4300 Gratuity Income  
- 4800 Other Income

### GST Collected (Line 105)
- 2200 GST/HST Payable
- GST/HST Payable

### GST Remitted (Line 113A)
- 2205 GST Remits

## More Examples

```powershell
# Full year 2025
l:\limo\.venv\Scripts\python.exe scripts\cra\fill_cra_form.py `
  --form gst --period 2025 `
  --output "L:\reports\GST34_2025_annual.pdf"

# Specific month range
l:\limo\.venv\Scripts\python.exe scripts\cra\fill_cra_form.py `
  --form gst --period 2025-04..2025-06 `
  --output "L:\reports\GST34_2025_Apr-Jun.pdf"

# Q4 2024
l:\limo\.venv\Scripts\python.exe scripts\cra\fill_cra_form.py `
  --form gst --period 2024Q4 `
  --output "L:\reports\GST34_2024Q4.pdf"
```

## Validation Tools

```powershell
# Check GST rate
l:\limo\.venv\Scripts\python.exe scripts\cra\validate_gst_rate_fixed.py

# Analyze all GL accounts
l:\limo\.venv\Scripts\python.exe scripts\cra\analyze_gl_for_cra.py
```

## Files & Documentation

- **IMPLEMENTATION_SUMMARY.md** - Complete technical details
- **ACCOUNT_MAPPING_REFERENCE.md** - All GL accounts mapped
- **README.md** - Setup and customization guide
- **mapping_gst.json** - Field definitions (can be edited)

## Next Steps

1. **Review GST accounting** with your bookkeeper to understand the 1.69% vs 5% discrepancy
2. **Identify ITC tracking** - you may be missing significant tax recovery
3. **Validate with actual CRA filings** - compare generated numbers to past returns
4. **Add PD7A** - source deduction automation (CPP, EI, Income Tax)

## Questions?

See **IMPLEMENTATION_SUMMARY.md** for technical details, known issues, and SQL queries to investigate data quality.
