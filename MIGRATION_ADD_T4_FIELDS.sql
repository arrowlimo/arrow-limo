-- Migration: Add T4 Tax Form Fields to employee_pay_master
-- Date: 2025-01-XX
-- Purpose: Add total_income_tax (T4-22), ei_insurable (T4-24), cpp_pensionable (T4-26)
--          Remove unused fields: float_draw, radio_dues, voucher_deductions, misc_deductions

-- Step 1: Add new T4 columns
ALTER TABLE employee_pay_master 
    ADD COLUMN IF NOT EXISTS total_income_tax DECIMAL(10, 2) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS ei_insurable DECIMAL(10, 2) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS cpp_pensionable DECIMAL(10, 2) DEFAULT 0;

-- Step 2: Backfill total_income_tax from existing data (federal + provincial)
UPDATE employee_pay_master 
SET total_income_tax = COALESCE(federal_tax, 0) + COALESCE(provincial_tax, 0)
WHERE total_income_tax = 0 OR total_income_tax IS NULL;

-- Step 3: Backfill ei_insurable and cpp_pensionable (typically = gross_pay)
UPDATE employee_pay_master 
SET ei_insurable = COALESCE(gross_pay, 0),
    cpp_pensionable = COALESCE(gross_pay, 0)
WHERE (ei_insurable = 0 OR ei_insurable IS NULL)
  AND (cpp_pensionable = 0 OR cpp_pensionable IS NULL);

-- Step 4: Drop old unused columns (if they exist)
-- WARNING: Only run this AFTER verifying no critical data exists in these columns
-- ALTER TABLE employee_pay_master 
--     DROP COLUMN IF EXISTS float_draw,
--     DROP COLUMN IF EXISTS radio_dues,
--     DROP COLUMN IF EXISTS voucher_deductions,
--     DROP COLUMN IF EXISTS misc_deductions;

-- Step 5: Verify migration
SELECT 'Migration complete. Sample records:' AS status;
SELECT 
    employee_id,
    pay_period_id,
    gross_pay,
    federal_tax,
    provincial_tax,
    total_income_tax,
    ei_insurable,
    cpp_pensionable
FROM employee_pay_master 
ORDER BY pay_period_id DESC 
LIMIT 5;

-- Step 6: Check for any old unused field data (before dropping columns)
-- SELECT 
--     COUNT(*) as records_with_float_draw
-- FROM employee_pay_master 
-- WHERE float_draw > 0;

-- SELECT 
--     COUNT(*) as records_with_radio_dues
-- FROM employee_pay_master 
-- WHERE radio_dues > 0;

-- SELECT 
--     COUNT(*) as records_with_voucher_deductions
-- FROM employee_pay_master 
-- WHERE voucher_deductions > 0;

-- SELECT 
--     COUNT(*) as records_with_misc_deductions
-- FROM employee_pay_master 
-- WHERE misc_deductions > 0;

COMMIT;
