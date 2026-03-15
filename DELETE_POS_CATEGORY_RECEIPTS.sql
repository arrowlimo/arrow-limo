-- DELETE POS CATEGORY JUNK RECEIPTS
-- Run this in pgAdmin to remove $0.00 "POS CATEGORY" receipts

-- STEP 1: Preview what will be deleted (RUN THIS FIRST)
SELECT 
    receipt_id,
    receipt_date,
    vendor_name,
    gross_amount,
    category,
    description
FROM receipts
WHERE vendor_name = 'POS CATEGORY'
  AND gross_amount = 0.00
  AND receipt_date >= '2026-02-13'
ORDER BY receipt_id;

-- Review the results above. If you're SURE you want to delete them, continue below.

-- STEP 2: Delete the receipts (UNCOMMENT THE LINES BELOW TO RUN)
/*
BEGIN;

DELETE FROM receipts
WHERE vendor_name = 'POS CATEGORY'
  AND gross_amount = 0.00
  AND receipt_date >= '2026-02-13';

-- This will show how many were deleted
SELECT 'Deleted ' || ROW_COUNT() || ' POS CATEGORY receipts' as result;

COMMIT;
*/

-- STEP 3: After deleting, verify they're gone
/*
SELECT COUNT(*) as remaining_pos_category_receipts
FROM receipts
WHERE vendor_name = 'POS CATEGORY';
*/
