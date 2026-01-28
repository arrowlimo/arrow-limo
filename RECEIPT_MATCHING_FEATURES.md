# Receipt Matching & Banking Integration - Feature Summary

**Date:** December 23, 2025
**Status:** ✅ Complete and Ready for Testing

## New Features Added

### 1. 🔍 Duplicate Receipt Detection

**Endpoint:** `GET /api/receipts-simple/check-duplicates`

**Purpose:** Find existing receipts that might be duplicates based on:
- Vendor name (fuzzy match)
- Exact amount (±$0.01)
- Date range (default 7 days, configurable)

**Parameters:**
```
vendor: string (required)
amount: float (required)
date: date (required)
days_window: int (optional, default=7)
```

**Response:**
```json
[
  {
    "receipt_id": 145281,
    "receipt_date": "2025-12-23",
    "vendor_name": "TEST VENDOR - AUTOMATED",
    "gross_amount": 100.00,
    "gst_amount": 4.76,
    "category": "fuel",
    "description": "Test from API",
    "banking_transaction_id": null,
    "is_matched": false
  }
]
```

**Visual Indicator:**
- ⚠️ **Warning box** appears when duplicates found
- Shows: Receipt #, Date, Vendor, Amount
- Badge: ✓ Matched to Banking or ○ Not Matched

---

### 2. 🏦 Banking Transaction Matching

**Endpoint:** `GET /api/receipts-simple/match-banking`

**Purpose:** Find banking transactions that could match this receipt:
- Exact amount match (±$0.01) on debit OR credit
- Date range (default 7 days, configurable)
- Optional vendor/description filtering

**Parameters:**
```
amount: float (required)
date: date (required)
vendor: string (optional - filters by description)
days_window: int (optional, default=7)
```

**Example:**
```bash
GET /api/receipts-simple/match-banking?amount=100&date=2015-01-01&days_window=365
```

**Response:**
```json
[
  {
    "transaction_id": 12345,
    "transaction_date": "2014-11-13",
    "description": "INTERAC E-TRANSFER",
    "debit_amount": 100.00,
    "credit_amount": 0.00,
    "account_number": "0228362",
    "already_matched": false,
    "existing_receipt_id": null
  }
]
```

**Visual Indicator:**
- 🏦 **Info box** appears when banking matches found
- Shows: Account, Date, Description, Amount
- Badge: ✓ Already Linked or ○ Available
- **Link button** to connect receipt to banking

---

### 3. 🔗 Link Receipt to Banking

**Endpoint:** `POST /api/receipts-simple/{receipt_id}/link-banking/{transaction_id}`

**Purpose:** Create the connection between a receipt and a banking transaction

**How it works:**
1. Save receipt → Get receipt_id
2. System shows matching banking transactions
3. Click "Link to This Receipt" button
4. Updates `banking_transactions.receipt_id` field

**Example:**
```bash
POST /api/receipts-simple/145281/link-banking/12345
```

**Workflow:**
```
Receipt saved → Banking matches appear → Click "Link" → Connection created
```

---

### 4. 🏷️ Vendor Name Standardization

**Endpoint:** `GET /api/receipts-simple/vendors` (enhanced)

**Purpose:** Show both raw and standardized vendor names

**Old Format:**
```json
["Fas Gas", "FasGas", "FASGAS"]
```

**New Format:**
```json
[
  {
    "name": "Fas Gas",
    "canonical": "FAS GAS"
  },
  {
    "name": "FasGas", 
    "canonical": "FAS GAS"
  },
  {
    "name": "FASGAS",
    "canonical": "FAS GAS"
  }
]
```

**Visual Display:**
In autocomplete dropdown:
```
Fas Gas
  → Standardized: FAS GAS

FasGas
  → Standardized: FAS GAS
```

**Database Field:**
- `receipts.vendor_name` = User-entered name
- `receipts.canonical_vendor` = Standardized name (used for grouping/reporting)

---

## How It Works: Complete User Journey

### Scenario: Adding a $100 fuel receipt

1. **User enters receipt details:**
   - Date: 2025-12-23
   - Vendor: "Fas Gas" (types "fas" → autocomplete shows suggestions with standardized names)
   - Category: Fuel
   - Amount: $100.00

2. **Auto-calculations trigger:**
   - GST calculated: $4.76 (5% included)
   - System checks for duplicates (7-day window)
   - System checks for banking matches (7-day window)

3. **Duplicate warning appears (if found):**
   ```
   ⚠️ Potential Duplicate Receipts Found
   
   Receipt #145281 - 2025-12-23 - TEST VENDOR - $100.00
   ○ Not Matched
   ```

4. **Banking matches appear (if found):**
   ```
   🏦 Matching Banking Transactions Found
   
   Account 0228362 - 2025-12-20
   INTERAC E-TRANSFER - $100.00
   ○ Available
   
   [Link to This Receipt]
   ```

5. **User saves receipt:**
   - Click "Save Receipt"
   - Receipt #145282 created
   - Success message shows

6. **User links to banking (optional):**
   - Click "Link to This Receipt" on matching transaction
   - Connection created
   - Badge updates: ✓ Already Linked (Receipt #145282)

7. **Auto-matching workflow:**
   - Duplicates prevent re-entry
   - Banking matches streamline reconciliation
   - Standardized vendor names ensure consistency

---

## Extended Query Features

### Adjustable Time Windows

**7-day window (default):**
```javascript
checkForMatches() // Uses 7-day window
```

**Extended window (30 days):**
```javascript
// Modify API call in frontend:
const dupResponse = await fetch(
  `...&days_window=30`  // Changed from 7 to 30
);
```

**Custom date range:**
Can be implemented by calling:
```
GET /receipts-simple/?start_date=2025-12-01&end_date=2025-12-31
```

### Grouping by Vendor

**All receipts for a vendor:**
```sql
SELECT vendor_name, canonical_vendor, 
       COUNT(*), SUM(gross_amount)
FROM receipts
WHERE canonical_vendor = 'FAS GAS'
GROUP BY vendor_name, canonical_vendor;
```

**Matched vs. Unmatched:**
```sql
SELECT 
  CASE WHEN banking_transaction_id IS NULL 
    THEN 'Unmatched' ELSE 'Matched' 
  END as status,
  COUNT(*), SUM(gross_amount)
FROM receipts
WHERE canonical_vendor = 'FAS GAS'
GROUP BY status;
```

---

## Auto-Matching Queue (Future Enhancement)

**Concept:**
1. Receipt saved → Queued for matching
2. Background job finds potential matches
3. User reviews suggestions
4. Bulk approve/reject

**Implementation sketch:**
```sql
CREATE TABLE receipt_match_queue (
  queue_id SERIAL PRIMARY KEY,
  receipt_id INTEGER REFERENCES receipts(receipt_id),
  suggested_transaction_id INTEGER REFERENCES banking_transactions(transaction_id),
  confidence_score DECIMAL(3,2), -- 0.00 to 1.00
  match_reason TEXT, -- 'exact_amount_and_date', 'vendor_match', etc.
  status VARCHAR(20) DEFAULT 'pending', -- pending, approved, rejected
  created_at TIMESTAMP DEFAULT NOW()
);
```

**Auto-match logic:**
- Exact amount + date within 3 days + vendor match → confidence 0.95
- Exact amount + date within 7 days → confidence 0.70
- Amount within $1 + vendor match → confidence 0.60

---

## Vendor Standardization Strategy

### Q: Do vendors get standardized naming?

**A: Two-tier approach:**

1. **Input flexibility** (fuzzy dropdown):
   - User types "fas" → sees all variants ("Fas Gas", "FasGas", "FASGAS")
   - User can type new name
   - No forced standardization at input

2. **Storage standardization** (canonical_vendor field):
   - When receipt saved, `canonical_vendor` computed or assigned
   - Used for reporting, grouping, analytics
   - Original `vendor_name` preserved for reference

### Banking Description Standardization

**Currently:**
- Banking descriptions stored as-is from PDF/import
- No standardization applied

**Proposed workflow:**
1. Import banking: `description = "POS PURCHASE - FASGAS #123"`
2. Match to receipt: `vendor_name = "Fas Gas"`, `canonical_vendor = "FAS GAS"`
3. Update banking: `canonical_vendor = "FAS GAS"` (derived from matched receipt)

**Benefits:**
- Banking data integrity maintained
- Standardized names used for matching and reporting
- Historical data searchable by canonical name

---

## Testing Checklist

### Test 1: Duplicate Detection
- [ ] Enter receipt with same vendor/amount as existing
- [ ] Verify duplicate warning appears
- [ ] Check 7-day window vs. extended window
- [ ] Verify "Matched" badge shows for receipts already linked to banking

### Test 2: Banking Match
- [ ] Enter receipt amount that exists in banking
- [ ] Verify banking matches appear
- [ ] Check "Available" vs. "Already Linked" badges
- [ ] Try different date ranges (7 days vs. 30 days)

### Test 3: Linking Receipt to Banking
- [ ] Save new receipt
- [ ] Click "Link to This Receipt" on banking match
- [ ] Verify success message
- [ ] Refresh page - badge should show "Already Linked"

### Test 4: Vendor Standardization
- [ ] Type "fas" in vendor field
- [ ] Verify dropdown shows variants with standardized names
- [ ] Select vendor - check canonical name displayed
- [ ] Save receipt - verify both vendor_name and canonical_vendor saved

### Test 5: Extended Query
- [ ] Search receipts by date range (30+ days)
- [ ] Filter by vendor (should match all variants via canonical)
- [ ] Group by canonical_vendor in reports

---

## API Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/receipts-simple/vendors` | GET | Get vendor list with standardization |
| `/api/receipts-simple/check-duplicates` | GET | Find duplicate receipts |
| `/api/receipts-simple/match-banking` | GET | Find matching banking transactions |
| `/api/receipts-simple/{id}/link-banking/{tx_id}` | POST | Link receipt to banking |
| `/api/receipts-simple/` | GET | Get receipts (supports date range) |
| `/api/receipts-simple/` | POST | Create receipt (triggers auto-match) |

---

## Database Schema Changes

**No schema changes required!** Uses existing fields:
- `receipts.vendor_name` - Raw input
- `receipts.canonical_vendor` - Standardized (already exists)
- `receipts.banking_transaction_id` - Link to banking (already exists)
- `banking_transactions.receipt_id` - Link to receipt (already exists)

---

## Next Steps

1. **Test the matching features** at http://localhost:8080/#/receipts
2. **Add bulk matching UI** (review queue, approve multiple)
3. **Add vendor canonicalization script** (standardize existing vendors)
4. **Add confidence scoring** (auto-match high-confidence pairs)
5. **Add match audit trail** (who linked what when)

---

## Quick Start

**Test duplicate detection:**
```bash
curl "http://127.0.0.1:8000/api/receipts-simple/check-duplicates?vendor=TEST&amount=100&date=2025-12-23&days_window=7"
```

**Test banking match:**
```bash
curl "http://127.0.0.1:8000/api/receipts-simple/match-banking?amount=100&date=2015-01-01&days_window=365"
```

**Link receipt to banking:**
```bash
curl -X POST "http://127.0.0.1:8000/api/receipts-simple/145281/link-banking/12345"
```

---

**Status:** ✅ All features implemented and ready for testing!
