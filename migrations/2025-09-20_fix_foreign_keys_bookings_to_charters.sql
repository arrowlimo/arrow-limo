-- Migration: Fix foreign key references from bookings to charters
-- The vehicle logging tables currently reference bookings.id but we're using charters.charter_id
-- This migration updates the foreign key constraints to point to charters table

-- First, drop the existing foreign key constraints
ALTER TABLE vehicle_odometer_log DROP CONSTRAINT IF EXISTS vehicle_odometer_log_booking_id_fkey;
ALTER TABLE vehicle_fuel_log DROP CONSTRAINT IF EXISTS vehicle_fuel_log_booking_id_fkey;

-- Rename the columns to be more accurate
ALTER TABLE vehicle_odometer_log RENAME COLUMN booking_id TO charter_id;
ALTER TABLE vehicle_fuel_log RENAME COLUMN booking_id TO charter_id;

-- Add new foreign key constraints pointing to charters table
ALTER TABLE vehicle_odometer_log 
ADD CONSTRAINT vehicle_odometer_log_charter_id_fkey 
FOREIGN KEY (charter_id) REFERENCES charters(charter_id);

ALTER TABLE vehicle_fuel_log 
ADD CONSTRAINT vehicle_fuel_log_charter_id_fkey 
FOREIGN KEY (charter_id) REFERENCES charters(charter_id);

-- Update any existing data that might reference bookings.id to use charter_id instead
-- Note: This assumes any existing booking_id values should map to charter_id values
-- In practice, this might need more complex data migration logic