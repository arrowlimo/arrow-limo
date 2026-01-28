# FINAL EMPLOYEE CONSOLIDATION PLAN - Complete Strategy

## Current State (Post-Analysis)

```
Total Employees:                    1,003 records
├─ REAL (from XLS):                  136 records  ✓ Verified
├─ QBO_IMPORT / OTHER:               195 records  
├─ LEGACY_METADATA:                  799 records  (address/phone/PDF fragments)
│  ├─ Safe to delete (no FK):         789 records ✓
│  └─ Unsafe (referenced):              10 records ✗ Referenced in charters
└─ PLACEHOLDER:                        2 records  ✗ "Dead Employee File", etc.

Foreign Key Dependencies:
├─ driver_payroll:                   130 employees
├─ charters (assigned_driver_id):    141 employees
└─ employee_expenses:                  0 employees

Critical Issue: 10 LEGACY records ARE referenced by charters!
└─ These must be merged/fixed BEFORE deletion
```

## The 10 "Unsafe" LEGACY Records (Must Handle)

These are referenced by charter records - cannot delete directly:

```
ID=201 | LEGACY-054c93 | "Phone numbers"
ID=202 | LEGACY-ce8ae9 | "Email"
ID=211 | LEGACY-231098 | "Crystal Matychuk"              ← Real person? (same as ID=151)
ID=213 | LEGACY-178a2c | "PO Box 2913 Blackfalds AB..."
ID=259 | LEGACY-40a0fe | "PAYROLL INPUT SHEET FOR..."   ← PDF caption
ID=290 | LEGACY-73fee7 | "Of03 Tammy Pettitt Wages..."   ← Real person? (same as ID=151)
ID=293 | LEGACY-8fa2ff | "Employee Paystub Cheque..."    ← PDF caption
ID=336 | LEGACY-af47db | "REALIZING that the employee..."  ← T4 Supplement text
ID=337 | LEGACY-e0e3cd | "RECOGNIZING that employees..." ← T4 Supplement text
ID=347 | LEGACY-663b7a | "Pay period frequency..."        ← T4 Supplement text
```

## Phase-by-Phase Strategy

### Phase 1: Identify & Merge Duplicate LEGACY Records (10 unsafe)

For each of the 10 unsafe records:
1. Check if it's a real person (Crystal Matychuk, Tammy Pettitt) by matching against XLS
2. If REAL PERSON → Find the primary REAL record, update charters FK, then delete
3. If NOT REAL → These are metadata/captions - need different handling

```sql
-- Example: ID=211 "Crystal Matychuk" is LEGACY-231098
-- Find primary: SELECT * FROM employees WHERE full_name LIKE '%Matychuk%' AND employee_number != 'LEGACY-%'
-- Update: UPDATE charters SET assigned_driver_id = :primary_id WHERE assigned_driver_id = 211
-- Delete: DELETE FROM employees WHERE employee_id = 211
```

### Phase 2: Delete 789 Safe LEGACY Records

```sql
DELETE FROM employees 
WHERE employee_number LIKE 'LEGACY-%'
  AND NOT EXISTS (SELECT 1 FROM driver_payroll WHERE employee_id = employees.employee_id)
  AND NOT EXISTS (SELECT 1 FROM charters WHERE assigned_driver_id = employees.employee_id)
  AND NOT EXISTS (SELECT 1 FROM employee_expenses WHERE employee_id = employees.employee_id)
```

Result: 214 employees remain (1003 - 789)

### Phase 3: Clean QBO/Duplicate Records (195 records)

```
Current: 195 "OTHER" records (many are QBO imports)
├─ 122 WITH payroll refs (keep, they're linked to business)
└─ 73 WITHOUT payroll refs (review for deletion)

Strategy:
1. For each QBO record with payroll: Keep as-is (business reference)
2. For each QBO record WITHOUT payroll: Check if duplicate of REAL
   - If duplicate: Merge non-NULL fields into primary, then delete
   - If unique: Keep (might be needed for audit trail)
```

### Phase 4: Delete/Fix Metadata-Only Records (IDs: 259, 293, 336, 337, 347)

These 5 records are clearly PDF captions/T4 text, not employees:
```sql
-- After clearing charters FKs (set to NULL or move to valid employee)
DELETE FROM employees 
WHERE employee_id IN (259, 293, 336, 337, 347)
```

### Phase 5: Archive 100% NULL Columns

15 columns are completely empty across all records:

```sql
ALTER TABLE employees DROP COLUMN phone_number CASCADE;
ALTER TABLE employees DROP COLUMN email_address CASCADE;
ALTER TABLE employees DROP COLUMN driver_license_number CASCADE;
ALTER TABLE employees DROP COLUMN driver_license_expiry CASCADE;
ALTER TABLE employees DROP COLUMN license_expiry CASCADE;
ALTER TABLE employees DROP COLUMN medical_cert_expiry CASCADE;
ALTER TABLE employees DROP COLUMN chauffeur_permit_expiry CASCADE;
ALTER TABLE employees DROP COLUMN average_rating CASCADE;
ALTER TABLE employees DROP COLUMN last_login CASCADE;
ALTER TABLE employees DROP COLUMN payroll_id CASCADE;
ALTER TABLE employees DROP COLUMN tax_exemption_code CASCADE;
ALTER TABLE employees DROP COLUMN year_to_date_pay CASCADE;
ALTER TABLE employees DROP COLUMN ytd_cpp CASCADE;
ALTER TABLE employees DROP COLUMN ytd_ei CASCADE;
ALTER TABLE employees DROP COLUMN ytd_tax CASCADE;
```

Reduces schema from 58 to 43 columns.

## Data Migration JSON

✓ **Backup created**: `reports/employees_backup_before_migration.json`

All 1,003 records exported before ANY changes. Can restore individual records if needed.

## Expected Final Result

```
Before:  1,003 records (79% noise)
After:   ~180 records (clean)
├─ 136 REAL employees (from XLS) ✓
├─ 130 employees WITH payroll ✓
├─ 141 employees in charters ✓
├─ 43 columns (vs 58, removed empty ones)
└─ No LEGACY_METADATA
└─ No orphaned FKs
└─ Fully reconciled with business reality
```

## Implementation Scripts to Create

1. ✓ `analyze_employee_duplicates.py` - Analysis
2. ✓ `check_legacy_fks.py` - FK dependency check
3. **TODO**: `phase1_merge_unsafe_legacy.py` - Handle 10 unsafe LEGACY records
4. **TODO**: `phase2_delete_safe_legacy.py` - Delete 789 safe LEGACY records
5. **TODO**: `phase3_dedup_qbo_records.py` - Handle 195 QBO imports
6. **TODO**: `phase4_cleanup_metadata.py` - Delete/fix 5 PDF caption records
7. **TODO**: `phase5_drop_null_columns.py` - Remove 15 empty columns

## Safety & Rollback

- JSON backup before any deletion
- All changes in transactions (can rollback)
- Check FK integrity before/after each phase
- Test on backup first, then production
- Keep 2-week retention on JSON backup

## Timeline

- Phase 1 (unsafe legacy): 1 script + manual review
- Phase 2 (safe legacy): Automated, single query
- Phase 3 (QBO dedup): Requires matching logic
- Phase 4 (metadata): Automated, 1 query per record
- Phase 5 (schema cleanup): Automated, 15 ALTER statements

**Total effort**: ~2-3 hours manual work + 5 hours script development
