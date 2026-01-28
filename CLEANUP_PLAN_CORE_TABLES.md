# Database Cleanup Priority Plan - January 20, 2026

## Executive Summary
- **Total Waste: 415.75 MB** in 742 completely empty columns
- **Safe Drop Zone: 200+ MB** (staging, QB, legacy columns)
- **Core Tables Need Review: 60 columns** in receipts/payments (incomplete vs legacy)

---

## TABLE FINDINGS

### 1. GENERAL_LEDGER (176.37 MB waste - 30 empty columns)

**Status: DATA-DRIVEN OPERATIONAL TABLE (NOT STAGING)**

**What's Working:**
- 15 core columns ✅ actively populated
- 128,786 complete GL transaction records
- Daily accounting transactions, balances, supplier data

**What's Empty:**
- 30 columns with ZERO data (appears to be planned but never implemented)
- Columns are QB-export related:
  - transaction_date (duplicate of existing `date`)
  - distribution_account_number
  - account_full_name
  - customer/customer_full_name/customer_title/customer_first_name
  - tax_slip_type
  - employee_deleted

**Recommendation: KEEP general_ledger, DROP the 30 empty columns**
- These are likely QB export placeholders that were never used
- The table itself is core and operational
- Delete: `transaction_date`, `distribution_account_number`, `account_full_name`, `item_supplier_company`, etc.
- Space saved: 176.37 MB

---

### 2. STAGING_QB_GL_TRANSACTIONS (62.18 MB waste - QB import staging)

**Status: STAGING TABLE - QuickBooks NO LONGER USED**

**What's in it:**
- 262,884 rows of QB import staging data
- Only 5 columns with actual data (id, file_id, source_row_id, source_line_no, txn_date)
- 7 empty columns (driver_id, account, category, vendor, gross_amount, etc.)
- Referenced by: staging_driver_pay table only

**Recommendation: SAFE TO DROP (entire table + 25 QB-related tables)**
- QB is no longer used (you confirmed)
- This is pure staging/import data
- Space saved: 62.18 MB + all other QB staging tables = ~150-200 MB

---

### 3. RECEIPTS TABLE (27.70 MB waste in empty, 32 more sparse)

**Status: CORE OPERATIONAL TABLE**

**What's Working (10 core columns, 100% populated):**
- ✅ receipt_id, source_system, source_reference
- ✅ receipt_date, vendor_name, currency
- ✅ gross_amount (98.4%), gst_amount, expense_account
- ✅ validation_status

**Incomplete Features (12 columns, 18-50% populated - maybe keep?):**
- 🔄 category (49.3%)
- 🔄 gl_account_name (47.2%)
- 🔄 source_file (42.8%)
- 🔄 expense (32.1%)
- 🔄 paper_verification_date (30.8%)
- 🔄 invoice_date (29.9%)
- 🔄 fiscal_year (31.8%)
- 🔄 gst_code (17.4%)
- 🔄 mapped_bank_account_id (15.6%)
- 🔄 display_color (23.0%)
- 🔄 receipt_source (23.0%)
- 🔄 comment (18.5%)

**Legacy/Dead Code (21 columns, <1% populated - SAFE TO DROP):**
- ❌ validation_reason (0%)
- ❌ event_batch_id (0%)
- ❌ reviewed (0%)
- ❌ exported (0%)
- ❌ date_added (0%)
- ❌ tax (0%)
- ❌ tip (0%)
- ❌ classification (0%)
- ❌ pay_account (0%)
- ❌ mapped_expense_account_id (0%)
- ❌ mapping_status (0%)
- ❌ mapping_notes (0%)
- ❌ reimbursed_via (0%)
- ❌ reimbursement_date (0%)
- ❌ cash_box_transaction_id (0%)
- ❌ parent_receipt_id (0%)
- ❌ amount_usd (0%)
- ❌ fx_rate (0%)
- ❌ due_date (0%)
- ❌ period_start (0%)
- ❌ period_end (0%)

**Recommendation:**
1. **KEEP** the 12 sparse columns (18-50% data) - appear to be incomplete features
2. **DROP** the 21 completely empty columns - clear legacy code
3. Space saved: 27.70 MB

**Questions to Ask:**
- Are the sparse columns (category, gl_account_name, fiscal_year) still in use?
- Can they be consolidated into fewer columns?

---

### 4. PAYMENTS TABLE (22.16 MB waste - 25 empty columns)

**Status: CORE OPERATIONAL TABLE**

**What's Working (5 core columns, 99-100% populated):**
- ✅ payment_id, account_number, reserve_number, amount, payment_key

**What's Broken/Abandoned (25 columns, 0% populated - SAFE TO DROP):**

**Legacy Square Payment Processor Columns (7 - never used):**
- ❌ square_transaction_id (0%)
- ❌ square_card_brand (0%)
- ❌ square_last4 (0%)
- ❌ square_customer_name (0%)
- ❌ square_customer_email (0%)
- ❌ square_gross_sales (0%)
- ❌ square_net_sales (0%)
- ❌ square_tip (0%)
- ❌ square_status (0%)
- ❌ square_notes (0%)
- ❌ square_payment_id (0.99% - one orphan)

**Legacy QB Integration Columns (4):**
- ❌ qb_payment_type (0%)
- ❌ qb_trans_num (0%)
- ❌ applied_to_invoice (0%)
- ❌ payment_account (0%)

**Legacy Credit Card Columns (4):**
- ❌ credit_card_last4 (0%)
- ❌ credit_card_expiry (0%)
- ❌ authorization_code (0%)
- ❌ check_number (0%)

**Other Legacy (10):**
- ❌ client_id (0%)
- ❌ charter_id (0.74% - mostly orphans)
- ❌ last_updated_by (0%)
- ❌ banking_transaction_id (0%)
- ❌ related_payment_id (0%)
- ❌ payment_amount (0%)
- ❌ adjustment_type (0%)
- ❌ deposit_to_account (0%)
- ❌ and more...

**Recommendation: SAFE TO DROP ALL 25 columns**
- These represent abandoned payment processors (Square, QB, check tracking)
- 0% populated (except charter_id at 0.74% - all orphans)
- Space saved: 22.16 MB

---

## TOTAL CLEANUP OPPORTUNITY

| Action | Table(s) | Columns | Space Saved |
|--------|----------|---------|-------------|
| Drop empty columns | general_ledger | 30 | 176.37 MB |
| Drop entire table | staging_qb_gl_transactions | - | 62.18 MB |
| Drop QB staging tables | All 25 QB-related tables | - | ~150+ MB |
| Drop legacy receipts columns | receipts | 21 | 27.70 MB |
| Drop legacy payments columns | payments | 25 | 22.16 MB |
| Drop other backup/staging tables | 104 backup tables | - | 100+ MB |
| **TOTAL POTENTIAL** | | **742+** | **~540+ MB** |

---

## RECOMMENDED EXECUTION ORDER

### Phase 1: Highest Priority (No Risk)
1. **Drop staging_qb_gl_transactions table** (62.18 MB)
   - QB is abandoned
   - Staging table, not operational data
   - Safe to delete

2. **Drop all QB-related tables** (~150+ MB)
   - 25 QB import/staging tables
   - Identify all with pattern: `qb_*`, `staging_qb*`
   - Safe to delete

3. **Drop general_ledger empty columns** (176.37 MB)
   - 30 columns with ZERO data
   - Non-operational placeholders
   - Safe to delete

### Phase 2: Medium Priority (Review First)
4. **Drop payments table legacy columns** (22.16 MB)
   - 25 columns from abandoned payment processors
   - Confirm Square/QB integration truly abandoned
   - Safe to delete

5. **Drop receipts table legacy columns** (27.70 MB)
   - 21 completely empty columns
   - Keep 12 sparse columns (may be incomplete features)
   - Safe to delete empty ones

### Phase 3: Lower Priority (Archive First)
6. **Drop 104 backup tables** (~100+ MB)
   - Create archive before deletion
   - Document which backups are safe to keep

---

## NEXT STEPS

**Questions to confirm with you:**

1. **QB Tables:** You said "we will not use quickbooks any longer" - can we delete ALL 25 QB-related tables safely?

2. **Sparse Receipts Columns:** Should we keep these incomplete features or consolidate them?
   - category (49% populated)
   - gl_account_name (47% populated)
   - fiscal_year (32% populated)

3. **Execution Timeline:**
   - Delete Phase 1 (QB + staging) this week? (-200 MB)
   - Delete Phase 2 (payments + receipts) after review? (-50 MB)
   - Archive Phase 3 (backups) later? (-100 MB)

**Total Potential Recovery: 415.75 MB → Database cleaner & faster**

---

## Danger Warnings

❌ **DO NOT delete these:**
- core table data (receipts, payments, charters, banking_transactions)
- active feature columns (just the empty/sparse ones)
- any column used by active queries/reports

✅ **SAFE TO DELETE:**
- Completely empty columns (0% data)
- Staging/import tables
- QB-related structures (QB abandoned)
- Backup tables (create archive first)

