# EMPLOYEE TABLE CLEANUP & CONSOLIDATION PLAN

## Current State Analysis

```
Total Employees in DB:  1,003 rows
├─ REAL (from XLS):           136 records  ✓ Verified
├─ OTHER (QBO/mixed):         195 records  (130 with payroll)
├─ LEGACY_METADATA:           799 records  ✗ Duplicate addresses, phone fragments, PDF captions
└─ PLACEHOLDER:                 2 records  ✗ "Dead Employee File", "Invoice Purposes"

Payroll Dependencies:   130 employees have driver_payroll records
Orphans (no payroll):   873 employees (mostly LEGACY_METADATA noise)
```

## The Problem

**1. LEGACY_METADATA Bloat (799 rows)**
- From QuickBooks/PDF extraction during migration
- Each contains fragments: addresses, phone numbers, names, payroll captions
- Examples: `LEGACY-7a638c | 101 MacKenzie Cres Lacombe AB T4L 0B2 Canada`
- All 799 rows have **ZERO payroll records** → safe to delete

**2. Completely Empty Columns**
- 15 columns with 100% NULL values (none ever populated)
  - `phone_number`, `email_address`, `driver_license_number`
  - `driver_license_expiry`, `license_expiry`, `medical_cert_expiry`
  - `chauffeur_permit_expiry`, `average_rating`, `last_login`
  - `payroll_id`, `tax_exemption_code`, `year_to_date_pay`, `ytd_cpp`, `ytd_ei`, `ytd_tax`
- Can be cleared/archived before cleanup

**3. Duplicate QBO Imports (54 QBO_IMPORT records)**
- Records with IDs like `8000001B-1412267705`, `QB-xxx`
- Many are duplicates of REAL employees (same names, different IDs)
- Example: Paul D Richard appears as REAL + QBO_IMPORT (both have same address/email)

## Consolidation Strategy

### Phase 1: Safe Deletions (No Data Loss)
```
DELETE FROM employees 
WHERE employee_number LIKE 'LEGACY-%' 
  AND NOT EXISTS (SELECT 1 FROM driver_payroll dp WHERE dp.employee_id = employees.employee_id)
Result: 799 rows deleted, 0 foreign key violations
```

### Phase 2: Identify QBO/Real Duplicates
```sql
-- Find duplicate names (same person, multiple IDs)
SELECT full_name, COUNT(*) as cnt, array_agg(employee_id) as ids
FROM employees
WHERE employee_number IN (SELECT DISTINCT employee_number FROM employees WHERE employee_number LIKE '8000%' OR employee_number LIKE 'QB-%')
GROUP BY full_name
HAVING COUNT(*) > 1
ORDER BY cnt DESC;
```

### Phase 3: Merge Strategy (For Real Duplicates)
For each duplicate identified:
1. **Keep** the record with most non-NULL values (primary record)
2. **Merge** non-NULL fields from secondary records into primary
3. **Update Foreign Keys**:
   ```sql
   UPDATE driver_payroll 
   SET employee_id = :primary_id 
   WHERE employee_id = :secondary_id;
   ```
4. **Delete** secondary records (after FK updates)

### Phase 4: Null Column Cleanup
```sql
-- Archive empty columns (all 100% NULL)
ALTER TABLE employees DROP COLUMN phone_number CASCADE;
ALTER TABLE employees DROP COLUMN email_address CASCADE;
-- ... repeat for other 13 empty columns
```

## JSON Backup (Reversible)

✓ **Already created**: `reports/employees_backup_before_migration.json`
- All 1,003 employee records exported with full field values
- Can restore any deleted data if needed

## Implementation Order

1. ✓ Export JSON backup → `employees_backup_before_migration.json`
2. Delete LEGACY_METADATA (799 rows) → **869 rows remain**
3. Identify QBO duplicates of REAL employees
4. Merge QBO records into REAL records (taking non-NULL values)
5. Delete QBO secondary records
6. Drop empty columns (100% NULL)
7. Validate referential integrity
8. Final result: ~150-170 clean, consolidated employee records

## Safety Measures

1. **JSON Backup**: Full data export before any deletion
2. **Transaction Rollback**: All changes in single transaction
3. **FK Validation**: Check for orphaned records before/after
4. **Dual Verification**:
   - Compare to employeelistbasic.xls (135 real names)
   - Verify driver_payroll records still accessible

## Expected Result

```
Before: 1,003 employees (79% noise)
├─ 799 LEGACY_METADATA (addresses, phone fragments)
├─ 54 QBO_IMPORT (duplicates of real employees)
├─ 2 PLACEHOLDER (Dead Employee File, Invoice Purposes)
└─ 136+ REAL/UNKNOWN (actual employees)

After: ~150 clean, consolidated employees
├─ All 130 payroll-linked employees preserved
├─ All duplicate data merged into single records
├─ All fragmented metadata cleaned
└─ Referential integrity maintained
```

## Files Created

- `reports/employees_backup_before_migration.json` - Full backup (1,003 records)
- `scripts/analyze_employee_duplicates.py` - Analysis script
- `scripts/consolidate_employees_phase1.py` - Safe deletion script (TO CREATE)
- `scripts/consolidate_employees_phase2.py` - QBO deduplication script (TO CREATE)
- `scripts/consolidate_employees_phase3.py` - Merge & cleanup script (TO CREATE)
