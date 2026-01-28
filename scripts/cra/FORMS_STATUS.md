# CRA Forms Status Summary

## ✅ GST/HST Return (GST34) - READY TO USE

### Status: **Production Ready**

The GST34 automation is complete and generates professional PDFs with:
- ✅ All 13 form lines calculated from almsdata
- ✅ Visual flags (⚠️) for issues (low GST rate, missing ITCs)
- ✅ Issues summary section with severity levels
- ✅ Recommendations for each flagged item
- ✅ Period-flexible (quarters, years, custom ranges)

### How to Generate GST34

```powershell
l:\limo\.venv\Scripts\python.exe scripts\cra\fill_cra_form.py `
  --form gst --period 2025Q3 `
  --output "L:\reports\GST34_2025Q3.pdf"
```

### What's Included in the PDF

**Form Fields:**
- Line 101: Total Sales ($3,598,347.50 for 2025Q3)
- Line 105: GST/HST Collected ($60,862.84)
- Line 108: ITCs ($0.00) ⚠️
- Lines 109-115: Net tax calculations
- Line 114: **Net Tax to Remit ($53,181.82)**

**Issues Detected (automatically flagged):**
1. **[HIGH]** GST rate is 1.69% (expected ~5%)
   - Revenue may be GST-inclusive or partially exempt
   - Recommendation: Review revenue composition and GST accounting

2. **[HIGH]** No Input Tax Credits claimed
   - Missing significant tax recovery on business expenses
   - Recommendation: Verify GST paid tracking

### Files
- `scripts/cra/fill_cra_form.py` - Main generator
- `scripts/cra/mapping_gst.json` - Field definitions
- `scripts/cra/QUICKSTART.md` - Usage guide
- `scripts/cra/ACCOUNT_MAPPING_REFERENCE.md` - GL account details

---

## 🚧 T2 Corporation Income Tax Return - IN PROGRESS

### Status: **Development / Requires Professional Review**

The T2 form has been downloaded and inspected:
- ✅ Form analyzed: **376 fillable fields** identified
- ✅ Template saved: `L:\limo\quickbooks\t2-fill-25e.pdf`
- ✅ Fields exported: `scripts/cra/t2_fields.json`
- ⚠️ Draft mapping created: `mapping_t2_draft.json`

### Why T2 is More Complex

The T2 Corporation Income Tax Return includes:
1. **Income Statement (Page 3)** - Lines 300-360
   - Revenue, expenses, cost of sales
   - Net income before taxes
   
2. **Balance Sheet (Pages 4-5)** - Assets, liabilities, equity
   - Cash, receivables, inventory
   - Fixed assets and CCA (depreciation)
   - Liabilities and shareholder equity

3. **Tax Calculation (Pages 6-8)**
   - Federal and provincial tax
   - Small business deduction
   - Tax credits and rebates

4. **Schedules (15+ attached forms)**
   - Schedule 1: Net Income
   - Schedule 8: Capital Cost Allowance (CCA)
   - Schedule 50: Shareholder Information
   - And many more...

### What's Needed for T2 Automation

#### 1. Chart of Accounts Mapping
Currently we have:
- Revenue accounts: ✅ Mapped (4000, 4300, 4800)
- Expense accounts: ⚠️ Need full breakdown by type
- Asset accounts: ⚠️ Need breakdown (cash, AR, fixed assets)
- Liability accounts: ⚠️ Need breakdown (AP, loans, payroll)
- Equity accounts: ⚠️ Need share capital and retained earnings

#### 2. Tax-Specific Data
- Capital Cost Allowance (CCA) - depreciation classes and rates
- Shareholder information and dividends
- Related party transactions
- Tax loss carryforwards
- Investment income and expenses
- Inter-corporate dividends

#### 3. Professional Requirements
⚠️ **CRITICAL:** T2 returns are legally binding tax documents that require:
- Professional accountant review
- CRA compliance verification
- Supporting schedules and documentation
- Signature by authorized officer
- Proper tax planning considerations

### Recommended Approach for T2

**Option 1: Partial Automation (Recommended)**
- Use automation to **generate draft numbers** from GL
- Export to Excel or PDF for accountant review
- Accountant completes schedules and filing
- Maintains professional oversight

**Option 2: Full Automation (Complex)**
- Requires complete GL account mapping
- Need all tax schedules automated
- Requires tax law compliance engine
- Still requires professional review before filing
- Estimated effort: 40-60 hours of development

**Option 3: Use Professional Tax Software (Most Common)**
- QuickBooks Desktop has built-in T2 preparation
- Dedicated tax software (TaxCycle, ProFile, etc.)
- Import GL trial balance from almsdata
- Professional handles complex tax calculations

### What I Can Build Next

If you want T2 automation, I can create:

1. **T2 Draft Generator** (8-12 hours)
   - Income statement (Lines 300-360)
   - Basic balance sheet
   - Summary PDF for accountant review
   - Flag missing data/accounts

2. **GL Account Analyzer** (2-3 hours)
   - Map all expense accounts to T2 line items
   - Identify missing accounts for balance sheet
   - Generate account mapping template

3. **T2 Data Export** (3-4 hours)
   - Export all T2-ready data to Excel
   - Format for tax software import
   - Include reconciliation notes

### Current Recommendation

**For GST34:** ✅ Use the automation - it's ready and reliable

**For T2:** 
1. Use the GST automation to verify revenue accuracy first
2. Run `analyze_gl_for_cra.py` to see all GL accounts
3. Decide on approach (partial automation vs. tax software)
4. If building automation, start with draft generator for accountant review

---

## Summary Table

| Form | Status | Complexity | Ready to File? | Estimated Completion |
|------|--------|------------|----------------|---------------------|
| **GST34 (GST/HST Return)** | ✅ Complete | Low | Yes (with review) | Done |
| **T2 (Corporation Tax)** | 🚧 Draft | Very High | No | 40-60 hours + professional review |
| **PD7A (Source Deductions)** | ⏸️ Not Started | Medium | N/A | 8-12 hours |
| **T4/T4A (Payroll Slips)** | ⏸️ Not Started | Medium | N/A | 12-16 hours |

## Next Steps

1. **Immediate:** Use GST34 automation for current/past quarters
2. **Review:** Investigate the GST rate issue (1.69% vs 5%)
3. **Decide:** Approach for T2 (automation vs. tax software)
4. **Optional:** Build PD7A automation for source deductions

---

**Questions? See:**
- GST: `scripts/cra/QUICKSTART.md`
- Technical: `scripts/cra/IMPLEMENTATION_SUMMARY.md`
- Accounts: `scripts/cra/ACCOUNT_MAPPING_REFERENCE.md`
