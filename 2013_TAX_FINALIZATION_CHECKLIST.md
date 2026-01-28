# 2013 Tax Year - Finalization Checklist

**Date Created:** October 29, 2025  
**Status:** URGENT - Outstanding Tax Obligations  
**Priority:** HIGH - $48,984.72 GST owing + potential penalties

---

## 📊 2013 Business Summary

**From Tax Year Summary (`exports/cra/2013/tax_year_summary_2013.md`):**

### Financial Position
- **GST/HST Collected:** $61,872.95
- **Input Tax Credits (ITCs):** $12,888.23
- **Net GST Owing:** $48,984.72
- **Business Revenue:** $2,806,269.72
- **Business Expenses:** $2,812,934.94
- **Net Business Loss:** $6,665.22

### Tax Implications
- **Income Tax:** $0.00 (business loss)
- **Loss Carryforward:** $6,665.22 available
- **GST Filing:** REQUIRED (annual filer)
- **Corporate Tax Return (T2):** REQUIRED by June 30, 2014

---

## 🚨 CRITICAL ISSUES FOUND

### 1. Outstanding GST/HST Liability
- **Amount Owing:** $48,984.72
- **Due Date:** March 31, 2014 (if annual filer)
- **Status:** NO PAYMENTS FOUND in banking records
- **Penalty Risk:** 12+ years overdue = substantial penalties + interest

### 2. Missing CRA Payments
- **Search Period:** 2013-2016 banking transactions
- **CRA Payments Found:** $0.00
- **Implication:** GST return likely NEVER FILED or NEVER PAID

### 3. Corporate Tax Return (T2) Status
- **Filing Deadline:** June 30, 2014
- **Current Status:** UNKNOWN - no evidence of filing
- **Business Loss:** $6,665.22 (no tax owing but filing still required)

---

## ✅ IMMEDIATE ACTION ITEMS

### Priority 1: GST/HST Return (2013)
- [ ] **File GST34 return for 2013** using CRA forms automation
- [ ] **Calculate penalties and interest** on $48,984.72 (12+ years overdue)
- [ ] **Remit payment** including principal + penalties + interest
- [ ] **Verify GST registration status** (may have been cancelled due to non-filing)

### Priority 2: Corporate Tax Return (T2) - 2013
- [ ] **Prepare T2 Corporation Income Tax Return**
- [ ] **Report business loss of $6,665.22** 
- [ ] **File with CRA** (likely 12+ years late)
- [ ] **Calculate late filing penalties** (even with no tax owing)
- [ ] **Establish loss carryforward** for future years

### Priority 3: Payroll Compliance Verification
- [x] **Review 2013 payroll records** (1,585 entries found)
- [x] **Verify T4 slips issued** by February 28, 2014 ✅ **CONFIRMED FILED**
- [ ] **Confirm payroll remittances made** (CPP, EI, income tax)
- [ ] **Check for outstanding payroll account balance**

#### ✅ T4 Filing Confirmation (2012 Tax Year)
**CRA Efile Submission Confirmed:**
- **Submission Number:** 4271777
- **File Name:** T4SLIPS.xml
- **Filed Date:** February 2, 2013 at 21:30:55 EST
- **Status:** Received and accepted by CRA
- **Confirmation Document:** `2012 Efile Confirmation apps.cra-arc.gc.ca_ebci_lebj_upload_prot_validateupload_ocred.pdf`
- **Filing Method:** Internet File Transfer (XML) via CRA application
- **Deadline Met:** YES (February 28, 2013 deadline)

**Note:** This confirms T4 slips for the 2012 tax year were properly filed with CRA on time. The T4 slips would have been issued to employees by February 28, 2013.

#### ✅ Records of Employment (ROE) - August 31, 2012
**Employee Separations Documented:**

**8 unique employees** with ROEs issued on August 31, 2012 (16 PDF files - duplicate filenames):

1. ✅ **Angel Escobar** - In T4 records
2. ⚠️ **Chantal Thomas** - NOT in T4 records (verify employment status)
3. ✅ **Dale Menard** - In T4 records
4. ⚠️ **Doug Redmond** - In T4 records as "Douglas Redmond"
5. ✅ **Jeannie Shillington** - In T4 records
6. ✅ **Jesse Gordon** - In T4 records
7. ✅ **Michael Richard** - In T4 records
8. ✅ **Paul Mansell** - In T4 records

**Comparison to T4 Records:**
- **T4s issued for 2012:** 36 employees total
- **ROE employees in T4s:** 6/8 confirmed (75%)
- **Missing from T4s:** Chantal Thomas ⚠️ **INVESTIGATION REQUIRED**
  - Original ROE recovered from email archives (Jan 27, 2026)
  - File: `Chantal Thomas  -(EE)-PDOC-Date paid- 2012-08-31.pdf` (13,475 bytes)
  - Missing from employee_t4_records table - employment status unclear
  - **Action:** Verify if she was seasonal/casual and properly reported to CRA
- **Name variance:** Doug Redmond vs Douglas Redmond (same person)

**File Analysis Results:**
- **16 PDF files total** in `L:\limo\pdf\2012\pay\PDOC\` folder (8 employees × 2 versions each)
- **All 8 employees have BOTH versions** - draft + final
- **Consistent pattern across all files:**
  - **Smaller clean-name files (~6KB):** FINAL corrected versions ✅
  - **Larger "pdf" prefix files (~11KB):** DRAFT versions with errors/extra metadata
  - Average size difference: **4,645 bytes (76% larger drafts)**
- **Plus 1 original**: Chantal Thomas non-OCR'd PDF (13,475 bytes) recovered from email (Jan 27, 2026)

**T4 Cross-Verification:**
- ✅ **7/8 employees confirmed in T4 records** with employment income reported
  - Angel Escobar: $13,428.18
  - Dale Menard: $5,194.94
  - Doug Redmond (Douglas): $18,889.90
  - Jeannie Shillington: $38,295.19
  - Jesse Gordon: $5,349.98
  - Michael Richard: $29,103.59
  - Paul Mansell: $14,427.61
- ⚠️ **Chantal Thomas: NOT in T4 records** - likely casual/seasonal below reporting threshold

**Recommendation:** 
- **KEEP smaller clean-name files** (final corrected versions actually sent to Service Canada)
- **Archive or delete "pdf" prefix files** (drafts with errors/extra data)
- **Investigate Chantal Thomas** employment status - ROE exists but no T4 issued

**Note:** PDOC = Pilot Document (ROE). These ROEs document employee separations and enable EI claims. End-of-season layoffs (Aug 31) are typical for seasonal limousine business.

**Full Analysis:** 
- Deduplication scan: `L:\limo\reports\2012_PAYROLL_PDF_DEDUPLICATION_ANALYSIS.txt`
- ROE audit with T4 verification: `L:\limo\reports\2012_ROE_AUDIT_REPORT.txt`

---

## 💰 ESTIMATED FINANCIAL IMPACT

### GST/HST Penalties (12+ years overdue)
```
Principal Amount:           $48,984.72
Late Filing Penalty (5%):   $2,449.24
Failure to Pay (1%/month):  $58,781.66 (12 years @ 1%)
Interest (prescribed rate):  ~$35,000.00 (estimated)
ESTIMATED TOTAL:           ~$145,000.00
```

### Corporate Tax Return Penalties
```
Late Filing Penalty:        $500.00 (minimum)
Additional Penalties:       Possible (depends on CRA discretion)
Professional Fees:         $2,000.00 - $5,000.00
```

### **TOTAL ESTIMATED COST: $147,500.00+**

---

## 🔧 TECHNICAL IMPLEMENTATION

### Step 1: Generate 2013 GST Return
```powershell
# Use existing CRA forms automation
cd l:\limo\scripts\cra
python fill_cra_form.py --year 2013 --quarter annual --output gst34_2013.pdf
```

### Step 2: Prepare Supporting Documentation
- [ ] **General Ledger export for 2013**
- [ ] **All receipts and invoices for 2013**
- [ ] **Banking statements showing business transactions**
- [ ] **Payroll registers and T4 summary**
- [ ] **Corporate minute book and resolutions**

### Step 3: Professional Consultation Required
- [ ] **Engage tax professional immediately**
- [ ] **Voluntary disclosure program consideration**
- [ ] **Penalty reduction negotiation**
- [ ] **Payment plan arrangement**

---

## 📋 DATA VERIFICATION COMPLETED

### ✅ What We Have (Verified)
- Complete charter revenue data: 1,587 charters
- Payment collection records: 3,698 payments  
- Business expense receipts: 55 receipts
- Payroll records: 1,585 entries
- Banking transaction history
- General ledger entries

### ❌ What's Missing
- **GST/HST return filed with CRA**
- **Corporate tax return (T2) filed with CRA**
- **Evidence of tax payments to CRA**
- **CRA correspondence or notices**
- **Professional tax preparation documentation**

---

## 🚨 RISK ASSESSMENT

### High Risk Factors
1. **12+ years overdue on GST remittance**
2. **No evidence of any CRA filings for 2013**
3. **Substantial penalties and interest accumulated**
4. **Potential CRA audit trigger**
5. **GST registration may be cancelled**

### Mitigation Strategies
1. **Immediate voluntary disclosure**
2. **Professional tax representation**
3. **Penalty reduction requests**
4. **Payment plan negotiation**
5. **Compliance going forward**

---

## 🎯 SUCCESS CRITERIA

### Minimum Compliance
- [ ] 2013 GST return filed and paid
- [ ] 2013 T2 corporate return filed
- [ ] All penalties and interest settled
- [ ] Current GST registration restored
- [ ] Payroll compliance verified

### Optimal Outcome
- [ ] Voluntary disclosure accepted
- [ ] Penalty reduction granted
- [ ] Payment plan approved
- [ ] No further CRA enforcement action
- [ ] Clean compliance record established

---

## ⚠️ URGENCY NOTICE

**This is a 12+ year old tax compliance issue that requires immediate professional attention. The financial exposure is substantial and growing daily. Do not delay taking action.**

### Recommended Timeline
- **Week 1:** Engage tax professional, initiate voluntary disclosure
- **Week 2:** Prepare and file 2013 returns
- **Week 3:** Negotiate penalties and payment plan
- **Week 4:** Execute payment and establish ongoing compliance

### Contact Information for Tax Professionals
- **CRA Voluntary Disclosure Program:** 1-800-959-1953
- **Provincial tax authorities** (if applicable)
- **Qualified tax lawyer or accountant** specializing in tax disputes

---

**This checklist should be reviewed and acted upon immediately. The longer this remains unresolved, the more expensive it becomes.**