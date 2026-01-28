# QUICK SPLIT RECEIPT REFERENCE

## Your Receipt #140678 ($58.24 SAFEWAY)

| GL Code | Description | Amount | Notes |
|---------|-------------|--------|-------|
| **6900** | Vehicle R&M | **$28.05** | Fuel/supplies |
| **6500** | Meals & Entertainment | **$30.19** | Driver meal |
| | **TOTAL** | **$58.24** | ✅ Matches |

---

## 3-Click Process

### Click 1️⃣ : Find Receipt
```
Accounting & Finance → Receipts & Invoices → Search, Match & Add
↓
"Find Receipt by ID" → Enter 140678 → 🔍 Search
```

### Click 2️⃣ : Open Split Manager
```
Receipt #140678 appears in table
↓
Double-click row (or click row, then "Manage Splits" button)
↓
Split Receipt Manager dialog opens
```

### Click 3️⃣ : Create Splits & Save
```
GL Splits tab:
├─ "➕ Add Split" → GL: 6900 | Amount: $28.05 | Notes: Vehicle
├─ "➕ Add Split" → GL: 6500 | Amount: $30.19 | Notes: Driver Meal
└─ "✅ Save All & Reconcile" 

Result: Receipt split, dialog closes, receipt marked as split_reconciled
```

---

## What Happens Under the Hood

```sql
-- Before Split (original receipt)
receipts:
├─ receipt_id: 140678
├─ vendor_name: SAFEWAY
├─ gross_amount: $58.24
└─ gl_account_code: NULL (was unspecified)

-- After Split (new entries created)
receipts: (unchanged, preserved for audit)
└─ receipt_id: 140678, gross_amount: $58.24

receipt_splits: (NEW entries)
├─ split_id: 1, gl_code: 6900, amount: $28.05 ← Vehicle R&M
└─ split_id: 2, gl_code: 6500, amount: $30.19 ← Driver Meal
```

**CRA Compliant**: Original receipt preserved, splits tracked separately

---

## If You Have Issues

| Problem | Solution |
|---------|----------|
| "Manage Splits" button disabled | Restart app - button now enabled by default |
| Amount doesn't match | Recalculate: Must sum to $58.24 exactly |
| Can't add split lines | Click "➕ Add Split" button in the GL Splits tab |
| Save button doesn't work | Use "✅ Save All & Reconcile" (green button) |
| Want to undo | Delete splits from database or create new allocation |

---

## GL Codes You'll Need

For **Vehicle Maintenance & Repairs**:
- `6900` - Vehicle R&M
- `6300` - Repairs & Maintenance (if different)

For **Driver Meals on Duty**:
- `6500` - Meals and Entertainment
- `6751` - Hospitality Supplies (if different)

Check your chart of accounts in the app for exact codes.

---

## NO COMBINE FEATURE (Yet)

Current system:
- ✅ **Split** one receipt into multiple GL codes
- ❌ **Combine** multiple receipts into one (not implemented)

**Workaround for combining**:
If you have 2 separate SAFEWAY receipts that should be 1:
1. Keep both separate
2. Assign both same GL code
3. Financial reports will consolidate at GL level
4. Or manually merge in database (advanced)

---

## After You Split

1. **Close Split Manager** (splits auto-saved)
2. **Check Recent List** - receipt shows `split_reconciled`
3. **Run GL Reports** - see $28.05 under 6900 and $30.19 under 6500
4. **Done!** ✅

---

**Updated**: Split Manager now has working "Save This Split" button (routes to "Save All & Reconcile")
