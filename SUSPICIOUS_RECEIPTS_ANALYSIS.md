# SUSPICIOUS RECEIPT ANALYSIS & DELETION RECOMMENDATIONS

**Date:** January 18, 2026  
**Analysis:** Banking-to-Receipt Reconciliation

---

## CLEAR DELETION CANDIDATES (25 receipts, $52,966)

These are obvious import errors/duplicates with NO valid business purpose:

### 1. JOURNAL ENTRY - FAKE/DUPLICATE ENTRIES (3 receipts, $49,887)
- **Reason:** These are internal accounting journal entries, not actual business transactions
- **Receipts:** 145280 ($25,300), 145279 ($17,409), 140974 ($7,177)
- **Action:** DELETE - Can re-add from original data if needed
- **All have banking matches** - but entries themselves are duplicates

### 2. HEFFNER AUTO FINANCE - NULL AMOUNT (19 receipts, no amount)
- **Reason:** Import error - amount field is completely empty
- **Issue:** No banking transaction match either
- **Duplicate of:** Valid Heffner entries that DO have amounts
- **Action:** DELETE - These are duplicates of properly recorded payments

### 3. OPENING BALANCE ENTRIES (2 receipts, $0)
- **Reason:** Opening balance entries should be manual/reconciliation entries only
- **Issue:** No banking match - obsolete system entries
- **Action:** DELETE - Use manual reconciliation process instead

### 4. DUPLICATE TELUS SERVICE (1 receipt, $3,080)
- **Reason:** Marked in vendor name as "[DUPLICATE - IGNORE]"
- **Amount:** $3,079.80
- **No banking match** - import artifact
- **Action:** DELETE

**Total Clear Deletion: 25 receipts ($52,966)**

---

## CONDITIONAL DELETE/REVIEW CANDIDATES

### A. BANK ACCOUNT NUMBERS AS VENDOR (57 receipts, $78,567)

**Problem:** OCR error - bank account numbers captured as vendor names
- Examples: `000000171208777`, `000000017141031`, `000000017673981`, etc.
- Pattern: All 8-12 digits, no recognizable vendor name

**Status:** All 57 have banking transaction matches (BT:xxxxx)

**Action Required:**
1. The banking transaction has the REAL vendor info in description field
2. Need to extract vendor name from banking description
3. Examples: Large ones are finance/vehicle payments (likely Heffner, IFS, etc.)
4. Recommendation: **Do NOT delete - Fix vendor name by extracting from banking description**

**Recovery Process:**
```sql
-- Get banking description for each receipt
SELECT r.receipt_id, r.vendor_name, bt.description
FROM receipts r
JOIN banking_transactions bt ON bt.transaction_id = r.banking_transaction_id
WHERE r.vendor_name LIKE '000000%'
```

Then update with correct vendor name from banking description.

---

### B. ORPHAN RECEIPTS (2,568 receipts, $1,352,461)

**Problem:** Receipts with NO banking transaction match

**Categories:**
1. **CMB Insurance Brokers** (5 receipts, $327K) - Policy premiums, yearly audits - likely valid but no bank match
2. **TD Insurance** (3 receipts, $23K) - Insurance policies
3. **HEFFNER AUTO FINANCE** (50+ receipts) - Many valid but missing from banking?
4. **Miscellaneous vendors** (1000+ receipts) - Various small vendors

**Root Cause Analysis:**
- These receipts were created without being linked to banking transactions
- Possible: Created from invoices/statements that don't appear in banking
- Possible: Imported from QBO/LMS but never reconciled to actual banking
- Possible: Created as accruals or estimates

**Action Required - DO NOT DELETE BLINDLY:**
1. Check if vendor appears in banking_transactions at all
2. If vendor exists in banking, link receipt to correct banking transaction
3. If vendor does NOT exist in banking, determine if:
   - Valid accrual (should keep)
   - Estimate (keep but mark)
   - Orphan error (can delete)

**Major Orphans to Investigate First:**
- CMB INSURANCE BROKERS: $327K - likely valid annual policies
- HEFFNER variants: $195K+ - finance lease payments (probably valid)
- TD INSURANCE: $23K - insurance (probably valid)
- RED DEER HEALTH FOUNDATION: $4.3K - donation (verify)

---

## SPECIAL CASES MENTIONED BY USER

### BERGLUND LOUISE (Accountant)
- **Status:** Found 5 entries
- **Amount:** $1,683 + $6,000 + e-transfer variants
- **Issue:** Mixed GL codes - some GL:1010, some GL:9999, some GL:6900, some NULL
- **Action:** 
  - Consolidate all Louise Berglund entries
  - Assign proper GL code for accountant services (possibly GL 6800 or 6900)
  - Create consistent vendor name

### 000000171208777 (Bank Account/POS)
- **Status:** Found 1 receipt
- **Amount:** $6,000
- **Issue:** Bank account number used as vendor name
- **Banking Match:** YES (BT:57410)
- **Action:** Extract real vendor from banking description and update

### EMAIL TRANSFER (Missing Recipient)
- **Status:** 503 receipts ($246K) with just "EMAIL TRANSFER" (no recipient name)
- **Issue:** Should be "EMAIL TRANSFER - [RECIPIENT NAME]"
- **Action:** 
  - Look up banking transaction description
  - Extract recipient name
  - Update vendor_name to "EMAIL TRANSFER - ACTUAL RECIPIENT"

---

## RECOMMENDED ACTION PLAN

### Phase 1: DELETE OBVIOUS ERRORS (Safe, No Risk)
- [ ] Delete 3 JOURNAL ENTRY receipts ($49,887)
- [ ] Delete 19 HEFFNER NULL receipts (no amount)
- [ ] Delete 2 OPENING BALANCE ($0)
- [ ] Delete 1 TELUS DUPLICATE ($3,080)
- **Total: 25 receipts deleted**

### Phase 2: FIX BANK ACCOUNT VENDORS (Medium Effort, High Value)
- [ ] For each of 57 bank account vendor receipts:
  - Extract real vendor from banking transaction description
  - Update vendor_name
  - Verify GL code is correct
- **Total: 57 receipts fixed**

### Phase 3: INVESTIGATE ORPHAN RECEIPTS (High Effort, High Value)
- [ ] Find largest orphans (>$5K)
- [ ] Check if vendor exists in banking_transactions
- [ ] Either:
  - Link receipt to banking transaction (if match found)
  - Keep as valid accrual (if no banking match but business-justified)
  - Delete as orphan error (if no match and no justification)

### Phase 4: FIX EMAIL TRANSFER RECIPIENTS (Low Effort, Medium Value)
- [ ] For each "EMAIL TRANSFER" receipt without recipient:
  - Get banking transaction description
  - Extract recipient name
  - Update vendor_name to include recipient

### Phase 5: CONSOLIDATE SPECIAL CASES
- [ ] Louise Berglund entries → Consistent name + GL code
- [ ] 000000171208777 → Fix to real vendor name

---

## CURRENT STATISTICS

| Status | Receipts | Amount | % of Total |
|--------|----------|--------|-----------|
| Linked to Banking | 31,415 | $17,041,891 | 92.5% |
| Orphan (No Banking) | 2,568 | $1,352,461 | 7.5% |
| **TOTAL** | **33,983** | **$18,394,352** | **100%** |

**Of Orphans:**
- Clear deletion candidates: 25 ($52,966) - 1% of orphans
- Bank account vendor errors: 57 ($78,567) - 6% of orphans
- Real orphans needing investigation: 2,486 ($1,220,928) - 90% of orphans

---

## NEXT ACTIONS

✅ **Ready to Execute:** Delete 25 obvious errors (JOURNAL ENTRY, HEFFNER NULL, OPENING BALANCE)

🔍 **Needs Review:** 57 bank account vendors - extract real vendor name from banking

❓ **Needs Investigation:** 2,568 orphan receipts - determine if valid or error

User should confirm deletion of Phase 1 items before proceeding.
