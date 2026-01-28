-- Swap first_name and last_name columns in employees table
-- Date: 2025-09-21
-- Purpose: Correct data migration error where first_name and last_name were swapped

-- Rename columns
ALTER TABLE employees RENAME COLUMN first_name TO temp_last_name;
ALTER TABLE employees RENAME COLUMN last_name TO first_name;
ALTER TABLE employees RENAME COLUMN temp_last_name TO last_name;

-- Add comment for documentation
COMMENT ON COLUMN employees.first_name IS 'Corrected: now stores first name';
COMMENT ON COLUMN employees.last_name IS 'Corrected: now stores last name';
