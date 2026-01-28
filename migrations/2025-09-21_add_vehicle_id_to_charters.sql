-- Add vehicle_id foreign key to charters table
-- Date: 2025-09-21
-- Purpose: Link charters to vehicles table for proper relational data integrity

-- Add vehicle_id column with foreign key constraint
ALTER TABLE charters 
ADD COLUMN vehicle_id INTEGER;

-- Add foreign key constraint to vehicles table
ALTER TABLE charters 
ADD CONSTRAINT fk_charters_vehicle_id 
FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id) ON DELETE SET NULL;

-- Create index for performance
CREATE INDEX idx_charters_vehicle_id ON charters(vehicle_id);

-- Add comment for documentation
COMMENT ON COLUMN charters.vehicle_id IS 'Foreign key reference to vehicles.vehicle_id for proper relational linking';