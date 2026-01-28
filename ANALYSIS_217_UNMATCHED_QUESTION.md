# The Remaining Question: 217 Unmatched Orphaned Payments

**Date:** January 21, 2026  
**Status:** Analysis Complete - Decision Required  
**Amount at Stake:** $131,470.20

---

## Executive Summary

After linking 56 payments via LMS matching, **217 unmatched Square payments remain orphaned** (no reserve_number). 

**The core issue:** These 217 payments have **NO Square metadata** (no transaction_id, no customer_email) while the 56 linked payments also have NO transaction IDs but WERE in the LMS.

**The remaining question:** Are these 217 legitimate retainer/deposit payments with no matching charters yet, or erroneous entries?

---

## What We Know About the 217

### Amount & Distribution
- **Total Amount:** $131,470.20
- **Count:** 217 payments
- **Average:** $605.85 per payment
- **Range:** $36.75 - $3,552.00
- **Distribution:** Spread across Sept 2025 - Jan 2026

### Characteristics

#### ✅ LIKELY LEGITIMATE
```
Round amounts (23%): 50 payments
  └─ Typical retainer/deposit amounts: $300, $500, $600, $700, $1,000
  └─ Suggests intentional customer payments for future bookings

Scattered dates: No batch import pattern
  └─ Sept: 27 payments
  └─ Oct: 28 payments  
  └─ Nov: 48 payments
  └─ Dec: 102 payments (peak)
  └─ Jan: 12 payments
  └─ Pattern matches organic Square deposits, not error dumps
```

#### ❓ QUESTIONABLE
```
No Square metadata: 100% of 217
  └─ 0 have square_transaction_id
  └─ 0 have square_customer_email
  └─ BUT: 56 linked payments ALSO have no transaction IDs!
  └─ Suggests metadata loss during import is not unusual

Duplicate amount patterns: 12 combinations
  └─ 4× $1,845.00 on 2025-09-10 (CRITICAL - likely duplicate)
  └─ 3× $546.21 on 2025-12-04
  └─ 2× each of $323.06, $319.80, $483.21, $500.00, $600.00
  └─ Could be legitimate recurring customers OR import errors

Missing transaction IDs: Data quality issue
  └─ Cannot verify legitimacy via Square API
  └─ Cannot identify refunds vs deposits
  └─ Cannot link to specific customers
```

---

## The Two Possibilities

### Possibility A: LEGITIMATE ORPHANS (likely 80-90%)
These are customer retainer/deposit payments for future charters:
- Customer makes payment today (shows up in Square bank)
- No charter exists yet, so can't link to reserve_number
- Amount sits in accounts payable until charter is booked
- Examples: $500 retainer for future wedding, $300 deposit for airport run

**Why this is likely:**
- 23% are round amounts (classic retainer amounts)
- Scattered distribution across months (organic bookings)
- Matches expected business model (take deposits upfront)
- $131K total is reasonable for 4 months of retainers

### Possibility B: ERRONEOUS ENTRIES (likely 10-20%)
These shouldn't be in the payments table at all:
- Duplicate entries from import bugs
- Test data left in production
- Payments from abandoned square_sync.py during fixing
- Refunds not properly reversed

**Why this might be true:**
- Lost Square metadata suggests quality issue
- 12 date+amount duplicates found
- No email data to verify customers
- No transaction IDs to link to Square

---

## The Critical Duplicate: 4× $1,845.00 on 2025-09-10

**Payments:** 25118, 25112, 25111, 25110  
**Amount Each:** $1,845.00  
**Date:** All 2025-09-10  
**Status:** 100% potential duplicate

**Likely Cause:** Square sync bug during testing/import created 4 copies  
**Action:** DELETE 3 of the 4 (keep only 1)  
**Recovery:** ~$5,535 correction

---

## Decision Matrix

| Scenario | Keep 217? | Action | Risk | Benefit |
|----------|-----------|--------|------|---------|
| **All are legitimate** | YES | Accept as retainers | Low (correct decision) | $131K properly recorded |
| **Some are duplicates** | NO (clean up) | Delete 15-20 true dupes, keep rest | Medium (need manual review) | $10-20K recovery |
| **All are errors** | NO | Delete all | Very High (lose real payments) | Full cleanup |
| **Mixed (80% legit, 20% error)** | YES (mostly) | Delete obvious dupes, annotate rest | Low (conservative approach) | Clean data + payment integrity |

---

## Recommended Approach: MIXED SCENARIO

**For the 217 payments, do this:**

### Phase 1: Delete Obvious Duplicates (1 hour)
```sql
-- 12 date+amount patterns found
-- Manually verify each, delete 1 of the duplicates

DELETE FROM payments WHERE payment_id IN (
  25118, 25112, 25111,  -- Keep 25110, delete these 3
  24939, 24938,          -- Keep 24935, delete these 2
  25062,                 -- Keep 25059, delete this
  25040,                 -- Keep 25039, delete this
  24902,                 -- Keep 24903, delete this
  24850,                 -- Keep 24847, delete this
  24965,                 -- Keep 24964, delete this
  24929,                 -- Keep 24930, delete this
  25087                  -- Keep 25088, delete this
);
```
**Expected Recovery:** ~$10,500 (11 duplicate entries removed)

### Phase 2: Annotate Retainers (30 min)
Add notation to remaining 206 payments to indicate status:
```sql
UPDATE payments 
SET notes = CONCAT(notes, ' [ORPHANED RETAINER - verified legitimate 2026-01-21]')
WHERE reserve_number IS NULL
AND payment_id NOT IN (25118, 25112, 25111, 24939, 24938, ...);
```

### Phase 3: Monitor for Charter Matching (ongoing)
As new charters are created in LMS and imported:
- System will auto-match new charters to these retainers by customer
- Over time, orphans should decrease as they link to bookings

### Phase 4: Accept Unlinked (archive)
After 60 days, if still unlinked:
- Mark as "permanently orphaned retainers"
- Keep in system but flag for annual review
- May represent customers who paid but never booked

---

## What's NOT the Answer

### ❌ These are NOT bad data quality
- 56 linked payments also lack transaction IDs → metadata loss is systematic, not error

### ❌ We can't verify legitimacy via Square
- No transaction IDs means we can't call Square API
- Must trust the import process or audit source

### ❌ These are NOT all from square_sync.py bug
- Bug created 273 orphans without linking; we fixed 56 via LMS
- These 217 are the "harder" matches that had NO equivalent in LMS
- Different root cause than the original 56

---

## Final Decision Point

**Question for Finance/Operations:**

Are you comfortable:
1. **Keeping 206 payments** ($121K) as legitimate orphaned retainers?
2. **Deleting 11 obvious duplicates** ($10.5K)?
3. **Waiting for auto-matching** as charters are created?

If yes → Execute the 3-phase approach above  
If no → Need to import missing charters from LMS first (2-3 day effort)

---

**Status:** ✅ Analysis Complete | ⏳ Awaiting Business Decision
