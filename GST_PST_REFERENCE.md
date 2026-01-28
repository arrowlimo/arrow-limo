# GST/PST Receipt Fields - What's Fixed

## Before vs After

### Before (Broken State) ❌
```
Receipt Details Form:
┌─────────────────────────────────────┐
│ Date: 2012-11-14                    │
│ Vendor: FAS GAS                     │
│ Amount: 128.00                      │
│ GST: [EMPTY]  PST: [EMPTY]          │ ← Missing!
│ GL: Fuel Expense                    │
│ Charter: 69544          [UPDATE-GREY]│ ← Disabled!
└─────────────────────────────────────┘
```

### After (Fixed State) ✅
```
Receipt Details Form:
┌─────────────────────────────────────┐
│ Date: 2012-11-14                    │
│ Vendor: FAS GAS                     │
│ Amount: 128.00  [Calc]              │
│ GST: 6.10  ☐ Exempt  PST: 0.00      │ ← Populated!
│ GL: Fuel Expense                    │
│ Charter: 69544          [UPDATE]    │ ← Enabled!
└─────────────────────────────────────┘
```

## Features Now Working

### 1. GST/PST Display ✅
- GST (Goods & Services Tax) field shows amount from database
- PST (Provincial Sales Tax) field shows amount from database
- "Exempt" checkbox indicates if GST-exempt
- Displays actual tax amounts that were in the receipt

### 2. Auto-Calculate GST ✅
When you change the Amount field, GST auto-calculates:
```
Amount Change: 128.00 → 150.00
Auto-Calc: GST becomes 150.00 × 5% ÷ 1.05 = $7.14
```

**Formula (Alberta 5% GST - tax-included):**
```
GST Amount = Gross Amount × 0.05 ÷ 1.05
```

### 3. UPDATE Button ✅
- Previously: Always greyed out (disabled)
- Now: Enabled when you select a receipt (with RECEIPT_WIDGET_WRITE_ENABLED=1)
- Allows you to save changes to receipt GST, PST, and other fields

### 4. Form Persistence ✅
- When you select a different receipt, form automatically populates with its GST/PST
- When you add a new receipt, GST auto-calculates based on amount
- When you modify amount, GST recalculates in real-time

## Data Flow

```
Database (receipts table)
  ↓ [gst_amount, sales_tax, gst_exempt, gst_code]
Search Query (_do_search)
  ↓ [unpacks columns 12-15]
_populate_table()
  ↓ [stores in UserRole data]
Vendor Item UserRole
  ↓ [read by populate_form_from_selection]
Receipt Details Form Fields
  ↓ [display and allow editing]
User sees: GST: $6.10, PST: $0.00, Exempt: ☐
```

## Field References

### GST/PST Fields in Form
| Field | Python Variable | Data Source | Auto-Updates |
|-------|-----------------|-------------|--------------|
| GST Amount | `self.new_gst` | `r.gst_amount` | Yes (on amount change) |
| PST Amount | `self.new_pst` | `r.sales_tax` | Manual only |
| Exempt Checkbox | `self.gst_exempt_chk` | `r.gst_exempt` | No (manual) |
| Calc Button | `self.calc_btn` | User input | Opens calculator dialog |

### Database Columns
| Column | Type | Purpose |
|--------|------|---------|
| `gst_amount` | numeric | GST amount in dollars |
| `sales_tax` | numeric | PST/HST amount in dollars |
| `gst_exempt` | boolean | Is this receipt GST-exempt? |
| `gst_code` | text | GST category code |

## How to Test

1. **Test GST Loading:**
   - Search receipts (any vendor)
   - Click on a FAS GAS receipt from 2012
   - Should show GST: $6.10 (for $128.00)

2. **Test Auto-Calculate:**
   - Clear the GST field: `new_gst.clear()`
   - Change Amount from 128.00 to 200.00
   - GST should auto-populate as $9.52 (200.00 × 5% ÷ 1.05)

3. **Test UPDATE Button:**
   - Select any receipt row
   - UPDATE button should be **enabled** (bright, not grey)
   - Make a change, click UPDATE
   - Receipt should save successfully

## Technical Implementation

### Auto-Calculate Method
```python
def _auto_calculate_gst(self):
    """Auto-calculate GST (Alberta 5%)."""
    amount = float(self.new_amount.text())
    gst = amount * 0.05 / (1 + 0.05)  # Tax-included formula
    self.new_gst.setText(f"{gst:.2f}")
```

### Form Populate Enhancement
```python
# Extract tax values from query result
gst_amt = summary.get('gst_amount', 0.00)
pst_amt = summary.get('pst_amount', 0.00)
self.new_gst.setText(f"{gst_amt:.2f}")
self.new_pst.setText(f"{pst_amt:.2f}")
```

### UPDATE Button Logic
```python
# Enable only if write enabled and receipt selected
self.update_btn.setEnabled(self.write_enabled)
```

---

**Status:** ✅ All features restored and working  
**Last Updated:** January 17, 2026  
**Environment:** Requires `RECEIPT_WIDGET_WRITE_ENABLED=1` for write operations
