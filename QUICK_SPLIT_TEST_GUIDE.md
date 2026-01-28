# 🧪 SPLIT RECEIPT UI TESTING GUIDE

## How to Test Split Detection in Desktop App

---

## ✅ PREREQUISITES

- ✓ Desktop app running (started automatically)
- ✓ All 52 split groups linked in database (verified)
- ✓ split_receipt_details_widget.py updated with split_group_id logic
- ✓ 108 receipts ready to test

---

## 🎯 QUICK START TEST

### Test Receipt: #157740 (FAS GAS, $128.00 + $38.89)

**Steps:**
1. Open desktop app (should be running)
2. Go to **Receipt Search** widget
3. Enter receipt ID: `157740`
4. **Expected:** Red banner "📦 Split into 2 linked receipt(s)"
5. Click **[View Details]**
6. **Expected:** Side-by-side layout showing:
   - Left: Receipt #157740 | FAS GAS | $128.00
   - Right: Receipt #140760 | FAS GAS | $38.89
   - Footer: **Total: $166.89**

**✅ If all above works = UI is functioning correctly!**

---

## 📋 OTHER KEY TEST CASES

### Test 2: Multi-part Split
- **Receipt:** #1365 (RUN'N ON EMPTY)
- **Expected:** 4 parts, Total $174.44
- **Parts:** #1365, #1367, #1366, #1368

### Test 3: High-Value
- **Receipt:** #1217 (PLENTY OF LIQUOR)
- **Expected:** 2 parts, Total $282.11

### Test 4: 2012 Pattern
- **Receipt:** #140690 (CENTEX)
- **Expected:** [SPLIT with #145329] format
- **Parts:** #140690 ($120), #145329 ($50.01)

---

## 📞 ISSUES TO REPORT

If banner **does NOT appear** for #157740:
```sql
-- Check: Is split_group_id set?
SELECT receipt_id, split_group_id FROM receipts WHERE receipt_id = 157740;
-- Should return: 157740 | 157740

-- Check: Are both receipts linked?
SELECT COUNT(*) FROM receipts WHERE split_group_id = 157740;
-- Should return: 2
```

If numbers **don't match:**
- Cross-check with SPLIT_GROUP_REFERENCE.md
- All expected amounts listed there

---

## 📊 SUMMARY

- **121 receipts analyzed** with SPLIT pattern
- **52 split groups created**
- **108 receipts linked** permanently
- **$4,155.75 combined** in split amounts
- **0 errors found** during analysis
- **All verification passed** ✓

**Status: Ready for UI testing. Start with receipt #157740!**
