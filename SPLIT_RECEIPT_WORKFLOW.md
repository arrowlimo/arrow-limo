# Split Receipt Workflow - Receipt #140678 ($58.24 SAFEWAY)

## Your Scenario
You have a SAFEWAY receipt for $58.24 that needs to be split into:
- **Vehicle Maintenance & Repairs**: $28.05 (part of the $58.24)
- **Driver Meal on Duty**: $30.19 (remaining part)
- **Total**: $58.24 ✓

## Step-by-Step Instructions

### Step 1: Locate the Receipt
1. In the **Receipts & Invoices** tab, use **Search, Match & Add**
2. In the left panel, click "Find Receipt by ID"
3. Enter receipt ID: **140678**
4. Click "🔍 Search"

### Step 2: Open the Split Manager
1. Receipt #140678 appears in the results table
2. **Double-click the row** to select it
3. Form populates on the right with receipt details
4. Look for the **"Manage Splits"** button (should be enabled now)
5. Click **"Manage Splits"**

### Step 3: Create Split Allocations
In the **Split Receipt Manager** dialog that opens:

**Tab: "GL Splits"**
1. Click **"➕ Add Split"** to create first split line
   - GL Code: **6900 - Vehicle R&M** (or the exact code for Vehicle Maintenance)
   - Amount: **$28.05**
   - Payment Method: credit/debit_card
   - Notes: "Vehicle fuel/supplies portion"

2. Click **"➕ Add Split"** again for second split line
   - GL Code: **6500 - Meals and Entertainment** (or Driver Meal on Duty code)
   - Amount: **$30.19**
   - Payment Method: credit/debit_card
   - Notes: "Driver meal during shift"

3. **Verify validation**: You should see ✅ "Splits sum correctly to $58.24"

### Step 4: Save the Splits
1. Click **"✅ Save All & Reconcile"** button (green button at bottom)
2. System creates entries in `receipt_splits` table
3. Receipt marked as `split_reconciled`
4. Dialog closes and signal emitted

---

## If You Need to COMBINE Multiple Receipts

Currently, we don't have a built-in combine feature, but here's the workaround:

### Manual Combine Approach:
1. **Note the two receipt IDs** you want to combine (e.g., 140678 and another ID)
2. **In the database** (if needed):
   ```sql
   -- Check if they can be combined
   SELECT receipt_id, receipt_date, vendor_name, gross_amount 
   FROM receipts 
   WHERE receipt_id IN (140678, OTHER_ID);
   
   -- If they should be one combined receipt, manually delete the child
   -- and update parent GL code, then use Manage Splits
   ```

### Or: Treat as Separate Receipts With Same GL Code
If you have two SAFEWAY receipts that should both be Vehicle Maintenance:
- Receipt 1: $28.05 → Vehicle Maintenance
- Receipt 2: $30.19 → Vehicle Maintenance
- Both tagged with same GL = Combined in accounting reports

---

## Troubleshooting

### Issue: "Update" Button Not Working
**Solution**: 
- Use **"✅ Save All & Reconcile"** instead of individual update
- Ensure all splits sum to receipt total before saving
- Check GL codes are valid in chart_of_accounts

### Issue: Can't Link to Receipt #8
**Note**: Receipts are standalone in this system
- One receipt = multiple GL splits (via receipt_splits table)
- If you need different receipt records, keep them separate
- Accounting consolidation happens at report level

### Issue: Amount Mismatch
If $28.05 + $30.19 = $58.24:
- ✅ Add split 1: $28.05
- ✅ Add split 2: $30.19
- ✅ System validates total before save

If amounts don't match receipt total:
- ❌ System prevents save
- 🔴 Validation shows red/yellow error
- Adjust amounts until they sum to receipt total

---

## Database Tables

```sql
-- Original receipt (parent)
SELECT * FROM receipts WHERE receipt_id = 140678;

-- New splits table (created when you save splits)
SELECT * FROM receipt_splits WHERE receipt_id = 140678;

-- This is CRA-compliant: original receipt preserved, splits tracked separately
```

---

## Next Steps After Split

1. **Close** the Split Manager (splits are saved)
2. **Verify** in Recent List that split_status shows "split_reconciled"
3. **Run reports** - GL codes now reflect split allocation
4. **Reconciliation** - Both GL codes appear in financial reports separately

---

**Note**: The split feature creates an audit trail. Original receipt data is preserved, split allocations are tracked in `receipt_splits` table for CRA compliance.
