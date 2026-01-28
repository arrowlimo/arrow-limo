# Split Group Reference Quick Lookup

## All 52 Split Groups by Vendor (sorted by total amount)

### High-Value Splits (>$100)

**PLENTY OF LIQUOR - 2019-05-10**
```
Group ID: 1217
Receipt #1218 | $242.11
Receipt #1217 | $40.00
─────────────────────
TOTAL: $282.11
```

**RUN'N ON EMPTY - 2019-08-31**
```
Group ID: 1527
Receipt #1527 | $156.00
Receipt #1528 | $21.06
─────────────────────
TOTAL: $177.06
```

**RUN'N ON EMPTY - 2019-06-25** ⭐ Multi-part split
```
Group ID: 1365
Receipt #1365 | $87.00
Receipt #1367 | $62.01
Receipt #1366 | $15.54
Receipt #1368 | $9.89
─────────────────────
TOTAL: $174.44
```

**RUN'N ON EMPTY - 2019-06-14**
```
Group ID: 1321
Receipt #1321 | $106.00
Receipt #1322 | $29.30
─────────────────────
TOTAL: $135.30
```

**RUN'N ON EMPTY - 2019-07-20**
```
Group ID: 1434
Receipt #1434 | $115.00
Receipt #1435 | $19.11
─────────────────────
TOTAL: $134.11
```

**RUN'N ON EMPTY - 2019-08-10**
```
Group ID: 1466
Receipt #1466 | $116.00
Receipt #1467 | $18.85
─────────────────────
TOTAL: $134.85
```

### Medium-Value Splits ($50-100)

**RUN'N ON EMPTY - 2019-03-25**
```
Group ID: 1135
Receipt #1135 | $37.50
Receipt #1136 | $22.30
─────────────────────
TOTAL: $59.80
```

**RUN'N ON EMPTY - 2019-03-28**
```
Group ID: 1138
Receipt #1138 | $36.00
Receipt #1139 | $23.80
─────────────────────
TOTAL: $59.80
```

**RUN'N ON EMPTY - 2019-03-19**
```
Group ID: 1122
Receipt #1122 | $40.01
Receipt #1123 | $19.54
─────────────────────
TOTAL: $59.55
```

**FAS GAS - 2019-01-09** ⭐ Multi-part split
```
Group ID: 940
Receipt #943 | $80.00
Receipt #940 | $40.20
Receipt #941 | $5.76
─────────────────────
TOTAL: $125.96
```

### Standard 2-Part Splits (Showing Sample)

**FAS GAS - 2019-02-20**
```
Group ID: 1022
Receipt #1022 | $20.00
Receipt #1023 | $14.90
─────────────────────
TOTAL: $34.90
```

**CENTEX - 2012-09-24** (Pattern: [SPLIT with #])
```
Group ID: 140690
Receipt #140690 | $120.00
Receipt #145329 | $50.01
─────────────────────
TOTAL: $170.01
```

### Small-Value Splits (<$30)

**FAS GAS - 2019-05-02**
```
Group ID: 1195
Receipt #1195 | $10.00
Receipt #1196 | $2.93
─────────────────────
TOTAL: $12.93
```

---

## By Vendor Summary

**FAS GAS** (16 groups, ~130 total)
- Key feature: Fuel rebates (cash + card split)
- 2019 dominant (all groups from 2019)
- Typical: $60-80 + $5-15 pattern

**RUN'N ON EMPTY** (21 groups, ~1,200+ total)
- Largest vendor with splits
- Mix of 2-part and 3-4 part splits
- Highest individual: $177.06 (2019-08-31)
- Lowest individual: $28.05 (2019-01-09)

**PLENTY OF LIQUOR** (6 groups, ~850+ total)
- Highest individual split: $282.11 (2019-05-10)
- Consistent 2-part pattern

**BURNT LAKE GAS/LIQUOR** (2 groups, ~94 total)
- Both from 2019
- Liquor + gas combo vendor

**Other Vendors** (7 groups)
- ESSO: 2 groups
- CENTEX: 2 groups (one 2012, one 2019)
- SHELL: 1 group (2012)
- PETRO CANADA: 1 group
- SPRINGS LIQUOR: 1 group

---

## Quick Test Cases (in recommended order)

### Test 1: Original Test Case (2-part)
```
Receipt #157740 | FAS GAS | $128.00 | split_group_id=157740
Receipt #140760 | FAS GAS | $38.89  | split_group_id=157740
Total: $166.89
Status: Known working ✓
```

### Test 2: Multi-part Split (4 parts)
```
Group ID: 1365
Display: Should show 4 receipts in side-by-side layout
Expected: RUN'N ON EMPTY split from 2019-06-25
```

### Test 3: Another Multi-part (3 parts)
```
Group ID: 940
Display: Should show 3 receipts in side-by-side layout
Expected: FAS GAS split from 2019-01-09
```

### Test 4: High-value Split
```
Group ID: 1217
Display: PLENTY OF LIQUOR $282.11 total
Expected: 2 receipts ($242.11 + $40.00)
```

---

## Database Query Reference

**Find all splits for a receipt:**
```sql
SELECT receipt_id, vendor_name, gross_amount, description
FROM receipts
WHERE split_group_id = 157740
ORDER BY gross_amount DESC;
```

**Count total receipts in each split:**
```sql
SELECT split_group_id, COUNT(*) as parts, SUM(gross_amount) as total
FROM receipts
WHERE split_group_id IS NOT NULL
GROUP BY split_group_id
ORDER BY total DESC;
```

**Find all receipts that are part of ANY split:**
```sql
SELECT COUNT(*) as split_receipts
FROM receipts
WHERE split_group_id IS NOT NULL;
```

**Find splits by vendor:**
```sql
SELECT split_group_id, vendor_name, COUNT(*) as parts, SUM(gross_amount) as total
FROM receipts
WHERE split_group_id IS NOT NULL
GROUP BY split_group_id, vendor_name
ORDER BY vendor_name, total DESC;
```

---

## Notes for User Testing

1. **UI Visual Indicator**: Red banner should appear: "📦 Split into N linked receipt(s)"
2. **Buttons**: [View Details] should open split receipt widget
3. **Side-by-side**: Each part shown in separate panel with amount and details
4. **Colors**: Highest amount first (cash payment), remainder amounts last
5. **Total**: Always shows sum of all parts
6. **Navigation**: Should be able to click any linked receipt to view it separately

**Status**: ✅ All 108 receipts linked to 52 groups. Ready for comprehensive UI testing.
