# How the Program Handles Split Receipts

## 1. DATABASE STORAGE (Parent-Child Model)

### Parent Receipt
```sql
receipt_id: 145318
is_split_receipt: TRUE
parent_receipt_id: NULL
split_key: "2012-09-15|FUEL STATION|135.00"
split_group_total: $135.00 (original physical receipt total)
```

### Child Receipts (linked to parent)
```sql
receipt_id: 145319 (Jerry Can)
parent_receipt_id: 145318
is_split_receipt: TRUE
split_key: same as parent
split_group_total: $135.00 (copy of parent total)

receipt_id: 145320 (L-2)
parent_receipt_id: 145318
vehicle_id: 2
is_split_receipt: TRUE

receipt_id: 145321 (L-7)
parent_receipt_id: 145318
vehicle_id: 7
is_split_receipt: TRUE
```

---

## 2. BACKEND PROCESSING (FastAPI Routes)

### File: `modern_backend/app/routers/receipts.py`

#### A. When Getting a Receipt with parent_receipt_id
```python
def get_receipt(receipt_id):
    # Get main receipt
    SELECT * FROM receipts WHERE receipt_id = receipt_id
    
    # Check if it's a PARENT (parent_receipt_id IS NULL)
    IF is_split_receipt = TRUE AND parent_receipt_id = NULL:
        # Fetch all CHILDREN
        SELECT * FROM receipts WHERE parent_receipt_id = receipt_id
        
        # Return structure:
        {
            "receipt_id": 145318,
            "amount": 135.00,
            "is_split": true,
            "split_components": [
                {"receipt_id": 145319, "amount": 4.00, "description": "Jerry Can"},
                {"receipt_id": 145320, "amount": 36.01, "vehicle_id": 2},
                {"receipt_id": 145321, "amount": 94.99, "vehicle_id": 7}
            ]
        }
```

#### B. When Querying All Receipts
```python
def list_receipts():
    # Filter out CHILDREN (parent_receipt_id IS NOT NULL)
    SELECT * FROM receipts 
    WHERE parent_receipt_id IS NULL  # Only show parents
    
    # Children are HIDDEN in list view
    # User sees only 1 line: Parent with amount $135.00
```

#### C. When Deleting a Parent Receipt
```python
def delete_receipt(receipt_id):
    # Step 1: Delete all CHILD receipts first
    DELETE FROM receipts WHERE parent_receipt_id = receipt_id
    
    # Step 2: Delete the PARENT
    DELETE FROM receipts WHERE receipt_id = receipt_id
```

---

## 3. FRONTEND DISPLAY (Vue Components)

### File: `frontend/src/views/Accounting.vue`

#### A. Receipt List Display
```
Search Results:
─────────────────────────────────────────────────────
Date        Vendor            Amount      Category
─────────────────────────────────────────────────────
2012-09-15  FUEL STATION      $135.00     Fuel ⭐ SPLIT
  ├─ Jerry Can (Pending)     $4.00
  ├─ L-2 Vehicle            $36.01  
  └─ L-7 Vehicle            $94.99
─────────────────────────────────────────────────────
```

#### B. Split Toggle Checkbox
When adding a receipt:
```html
☑️ Split this receipt (business/personal, vehicles, rebates)

When CHECKED → Show split component entry section:
  Component 1: Amount=$4.00  | Category=Jerry Can | Description=...
  Component 2: Amount=$36.01 | Vehicle=L-2       | Description=...
  Component 3: Amount=$94.99 | Vehicle=L-7       | Description=...
  
  ⚠️  Components must sum to receipt total ($135.00)
```

#### C. Auto-Calculation
```javascript
// As user enters components:
total_entered = 4.00 + 36.01 + 94.99 = 135.00
receipt_total = 135.00

if (total_entered === receipt_total) {
    button.save.enabled = true  // ✅ Can save
    message.show("All amounts matched ✓")
} else {
    button.save.enabled = false  // ❌ Blocked
    message.warn(`Need $${receipt_total - total_entered} more`)
}
```

---

## 4. REPORTING/ANALYTICS

### Fuel Efficiency Report
```sql
SELECT 
    vehicle_id,
    SUM(fuel_amount) as total_liters,
    SUM(gross_amount) as total_cost,
    SUM(gross_amount) / SUM(fuel_amount) as cost_per_liter
FROM receipts
WHERE 
    category = 'Fuel' 
    AND parent_receipt_id IS NULL  -- Only count parents (no double-counting children)
    AND vehicle_id IS NOT NULL     -- Must have vehicle assigned
GROUP BY vehicle_id

Results:
Vehicle 2: 29.53 LT, $36.01  → $1.22/LT
Vehicle 7: 77.94 LT, $94.99  → $1.22/LT
```

### Expense Summary
```sql
SELECT 
    category,
    SUM(gross_amount) as total
FROM receipts
WHERE parent_receipt_id IS NULL  -- Only parents
GROUP BY category

Results:
Fuel:     $135.00 (counted once, not 3 times)
```

---

## 5. KEY RULES (How System Avoids Duplication)

### ✅ RULE 1: List Views Filter Children
```sql
WHERE parent_receipt_id IS NULL  -- Children hidden
```

### ✅ RULE 2: Sum Operations Skip Children
```sql
WHERE parent_receipt_id IS NULL  -- Don't count children
```

### ✅ RULE 3: Delete Cascades
```python
DELETE FROM receipts WHERE parent_receipt_id = parent_id  # Children first
DELETE FROM receipts WHERE receipt_id = parent_id        # Then parent
```

### ✅ RULE 4: Vehicle Assignment on Children Only
```sql
receipt_id: 145319 → vehicle_id: NULL    (Jerry Can - no vehicle yet)
receipt_id: 145320 → vehicle_id: 2       (L-2 assigned)
receipt_id: 145321 → vehicle_id: 7       (L-7 assigned)
```

---

## 6. EXAMPLE QUERY FLOW

**User searches:** "Shell 09/15/2012"

```python
# Backend searches parent receipts
SELECT * FROM receipts 
WHERE vendor_name LIKE '%Shell%'
  AND DATE(receipt_date) = '2012-09-15'
  AND parent_receipt_id IS NULL      # Only parents

# Results: 1 row (parent 145318)

# Frontend displays:
Receipt #145318: FUEL STATION $135.00 [SPLIT - 3 components]

# User clicks "View Details" → Backend runs:
SELECT * FROM receipts WHERE receipt_id = 145318
  UNION ALL
SELECT * FROM receipts WHERE parent_receipt_id = 145318

# Returns: 1 parent + 3 children
# Frontend renders:
  Parent: $135.00 (total)
  ├─ Child 1: $4.00 (Jerry Can)
  ├─ Child 2: $36.01 (L-2)
  └─ Child 3: $94.99 (L-7)
```

---

## 7. VEHICLE REPORTING

### Fuel Cost per Vehicle Report
```sql
SELECT 
    v.vehicle_id,
    v.vehicle_name,
    SUM(r.fuel_amount) as liters_purchased,
    SUM(r.gross_amount) as total_spent,
    SUM(r.gross_amount) / SUM(r.fuel_amount) as cost_per_liter
FROM receipts r
JOIN vehicles v ON r.vehicle_id = v.vehicle_id
WHERE 
    r.category = 'Fuel'
    AND r.parent_receipt_id IS NULL  -- Only count parents once
    AND r.vehicle_id IS NOT NULL
    AND YEAR(r.receipt_date) = 2012
GROUP BY v.vehicle_id, v.vehicle_name
ORDER BY v.vehicle_name

Results:
L-2:  29.53 LT  | $36.01  | $1.22/LT
L-7:  77.94 LT  | $94.99  | $1.22/LT
(Jerry Can not shown - vehicle_id NULL)
```

---

## 8. SUMMARY: 3 Split Receipts Handling

| Step | What Happens |
|------|--------------|
| **Insert** | 4 rows created (1 parent + 3 children) |
| **List** | Only parent shown ($135.00) |
| **Detail** | Parent + all 3 children shown |
| **Report** | Aggregated once (parent counted only) |
| **Delete** | All 4 rows deleted (parent + children) |
| **Vehicle Tracking** | L-2 and L-7 get fuel data; Jerry Can hidden |
