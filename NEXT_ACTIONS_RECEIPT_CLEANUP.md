# ACTION PLAN - Receipt Data Cleanup Continuation

**Date:** December 23, 2025  
**Priority Level:** Complete 5 remaining problem categories (403-537 receipts)

---

## 📌 Problem Categories & Actions

### 1. EMAIL TRANSFER - Generic Recipients (HIGH PRIORITY)
**Status:** 403 receipts, $187,900 (incomplete vendor extraction)  
**Root Cause:** Recipient names not extracted from banking descriptions

**What We Did:**
```python
# First pass extracted 100/503 EMAIL TRANSFER recipients
# 403 remain as just "EMAIL TRANSFER" without recipient name
```

**What's Needed:**
Create deeper extraction script that:
1. Queries banking_transactions for EMAIL TRANSFER receipts
2. Uses enhanced regex patterns:
   - "E-TRANSFER TO [NAME]"
   - "E-TRANSFER FROM [NAME]"
   - "EMAIL TRANSFER [NAME]"
   - Payment instruction variations
3. Extract recipient and update receipts.vendor_name
4. Log success/failure metrics

**Success Criteria:**
- At least 80% of 403 receipts get recipient names
- Update ~320+ EMAIL TRANSFER records
- Reduce generic "EMAIL TRANSFER" to <100 records

**Estimated Time:** 20 minutes (10 min scripting + 10 min execution/review)

**Impact:** Improves vendor clarity for reconciliation

---

### 2. CHEQUE ERRORS - OCR & Large Amounts (HIGH PRIORITY)
**Status:** 118 unknown + 2 large = $273,449 total

#### Part A: Large Cheque Verification
**CHEQUE 955.46:** $195,406
- Status: In banking_transactions (verified, locked)
- Issue: Cheque number "955.46" looks like an amount, not a cheque #
- Action: Verify if this is correct OR should be named differently

**CHEQUE WO -120.00:** $158,363
- Status: In banking_transactions (verified, locked)
- Issue: "WO -120.00" is nonsensical
- Action: Verify if this is a real cheque or banking description error

**Next Step:** Show these to user for verification

#### Part B: 118 Unknown Cheque Payees
**Issue:** Cheque numbers extracted from OCR but payee names not identified
**Pattern:** "CHEQUE 12345" without payee

**Action:**
1. Extract cheque numbers from receipts.vendor_name
2. Check if cheque register has matching cheque numbers
3. Link to actual payee names in cheque register
4. Update vendor_name with real payee

**Query Needed:**
```sql
SELECT r.receipt_id, r.vendor_name, 
       SUBSTRING(r.vendor_name, '[0-9]+') as cheque_number
FROM receipts r
WHERE r.vendor_name LIKE 'CHEQUE%'
AND r.gross_amount BETWEEN 100 AND 20000
```

**Success Criteria:**
- Link 90%+ of 118 unknown cheques to cheque register
- Extract real payee names
- 2 large cheques verified by user

**Estimated Time:** 15 minutes (user review) + 10 minutes (scripting) = 25 minutes total

**Impact:** Identifies actual payment recipients for all cheque transactions

---

### 3. BILL PAYMENT - Vendor Extraction (MEDIUM PRIORITY)
**Status:** 6 receipts, $15,025

**Details:**
```
Receipt 140422: $4,400.19
Receipt 139912: $3,496.08
Receipt 140062: $3,360.26
Receipt 139996: $3,181.17
Receipt 140028: $500.00
Receipt 139621: $87.45
```

**Issue:** Vendor name is "BILL PAYMENT" without actual payee

**Action:**
1. Query banking_transactions for matching transactions
2. Extract payee from banking description (after "Bill Payment" text)
3. Common patterns:
   - "Bill Payment (Cheque) - VENDOR NAME"
   - "Bill Payment VENDOR #ACCOUNT"
4. Update vendor_name in receipts

**Success Criteria:**
- Extract vendor names for all 6 receipts
- Update to specific payees (e.g., "BILL PAYMENT - LANDLORD")

**Estimated Time:** 8 minutes

**Impact:** Clarifies bill payment recipients

---

### 4. HEFFNER ACCRUAL VERIFICATION (MEDIUM PRIORITY)
**Status:** 1,926 receipts, $878,936 (largest orphan category)

**Background:** These are NOT true orphans - they're in banking_transactions.receipt_id

**Questions to Answer:**
1. Are these legitimate Heffner Auto Finance vehicle lease charges?
2. Should they remain as GL 2100 (Lease Obligation)?
3. Any payment terms/frequency consistency?

**Analysis To Do:**
```python
# Check Heffner transaction dates for patterns
SELECT vendor_name, receipt_date, gross_amount, 
       DATE_TRUNC('month', receipt_date) as month,
       COUNT(*) as count
FROM receipts
WHERE vendor_name LIKE 'HEFFNER%'
GROUP BY DATE_TRUNC('month', receipt_date)
ORDER BY receipt_date
```

**Expected Finding:** Regular monthly charges = legitimate recurring finance payments

**Success Criteria:**
- Confirm regular payment pattern
- Verify GL 2100 (Lease Obligation) is correct
- Document that these are expected system entries

**Estimated Time:** 15 minutes

**Impact:** Justifies ~$879K in liabilities

---

### 5. INSURANCE PREMIUM VERIFICATION (MEDIUM PRIORITY)
**Status:** 9 receipts, $389,003

**Companies:**
- CMB Insurance Brokers: 6 policies, $356,934 (2019-2024)
- TD Insurance: 3 policies, $32,069 (2018-2020)

**Issue:** No banking transaction match - payment status unclear

**Action:**
1. Contact insurance brokers
2. Ask: "Were these premiums paid or are they accrual estimates?"
3. If paid, find banking match (may be from different account/payment method)
4. If accrual, verify GL 6400 (Insurance Expense) is appropriate

**Contact Info Needed:**
- CMB Insurance Brokers: Find contact details
- TD Insurance: Find policy holder contact

**Success Criteria:**
- Get payment confirmation from brokers
- If paid, link to banking transactions
- If accrual, document as pending payment

**Estimated Time:** 30-60 minutes (phone/email back-and-forth)

**Impact:** Clarifies ~$389K in potential liabilities

---

## 📊 Implementation Sequence

### Session 1 (Next 30-40 minutes):
1. ✅ EMAIL TRANSFER deeper extraction (20 min)
2. ✅ BILL PAYMENT vendor extraction (8 min)
3. ✅ CHEQUE error verification (show 2 large to user) (5 min)

### Session 2 (30-40 minutes):
4. ✅ CHEQUE 118 unknown - link to cheque register (20 min)
5. ✅ HEFFNER accrual verification (15 min)

### Session 3 (After user contact):
6. ⏱️ Insurance premium verification (30-60 min, mostly waiting for brokers)

---

## 🎯 Success Metrics

**After EMAIL TRANSFER + BILL PAYMENT + CHEQUE fixes:**
- Reduce NULL/generic vendors from 537 to ~50
- Improve vendor name clarity by ~95%
- Clear up $213K in ambiguous transactions

**After HEFFNER + Insurance verification:**
- Confirm ~$1.27M in legitimate expenses/liabilities
- Justify all remaining orphan categories
- Achieve 95%+ transaction clarity

---

## 📋 Ready-To-Execute Scripts

The following are ready to run:
- `scripts/extract_email_transfer_recipients_v2.py` (needs to be created)
- `scripts/extract_bill_payment_vendors.py` (needs to be created)
- `scripts/verify_heffner_pattern.py` (needs to be created)

---

## ⚠️ Important Notes

1. **HEFFNER NULL entries are NOT deletable** - they have banking references
2. **All remaining orphans are likely legitimate** - no more obvious errors to delete
3. **92.5% banking match is excellent** - most data is valid
4. **GL categorization at 91.7%** - very good coverage
5. **Next focus: Vendor clarity, not data deletion**

---

**Session Status:** Phase 2 Complete ✅  
**Next Action:** Execute EMAIL TRANSFER + BILL PAYMENT extraction scripts
