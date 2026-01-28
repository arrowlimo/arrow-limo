-- Add employee_id foreign key to charters table
-- Date: 2025-09-21
-- Purpose: Link charters to employees table for proper driver/chauffeur relational data integrity

-- Add employee_id column with foreign key constraint
ALTER TABLE charters 
ADD COLUMN employee_id INTEGER;

-- Add foreign key constraint to employees table
ALTER TABLE charters 
ADD CONSTRAINT fk_charters_employee_id 
FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE SET NULL;

-- Create index for performance
CREATE INDEX idx_charters_employee_id ON charters(employee_id);

-- Add comment for documentation
COMMENT ON COLUMN charters.employee_id IS 'Foreign key reference to employees.employee_id for proper driver/chauffeur relational linking';