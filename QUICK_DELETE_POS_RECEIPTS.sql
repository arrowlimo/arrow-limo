-- QUICK DELETE - POS CATEGORY RECEIPTS
-- Copy and paste this entire script into pgAdmin and press F5

-- Step 1: Show what will be deleted
SELECT 'FOUND ' || COUNT(*) || ' POS CATEGORY receipts with $0.00 to delete' as preview
FROM receipts
WHERE vendor_name = 'POS CATEGORY' AND gross_amount = 0.00;

-- Step 2: Delete them
DELETE FROM receipts
WHERE vendor_name = 'POS CATEGORY' 
  AND gross_amount = 0.00;

-- Step 3: Confirm deletion
SELECT 'DELETED! POS CATEGORY receipts are now gone.' as result;

-- Step 4: Verify
SELECT COUNT(*) as remaining_pos_category_count
FROM receipts
WHERE vendor_name = 'POS CATEGORY';

-- DONE! Go back to your desktop app and refresh (F5) to see them disappear.
