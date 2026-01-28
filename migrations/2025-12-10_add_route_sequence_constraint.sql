-- Migration: Add CHECK constraint for route_sequence to prevent negative values
-- This ensures data integrity when reordering routes

-- Add CHECK constraint to ensure route_sequence is always positive
ALTER TABLE charter_routes 
ADD CONSTRAINT route_sequence_positive 
CHECK (route_sequence > 0);

COMMENT ON CONSTRAINT route_sequence_positive ON charter_routes 
IS 'Ensures route_sequence is always a positive integer (1, 2, 3, ...)';
