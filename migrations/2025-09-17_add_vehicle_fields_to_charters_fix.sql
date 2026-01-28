-- Migration: Add missing vehicle, odometer, fuel, and charter_data fields to charters table (no retainer)
-- Only adds fields not already present

ALTER TABLE charters
ADD COLUMN IF NOT EXISTS vehicle_booked_id INTEGER,
ADD COLUMN IF NOT EXISTS vehicle_type_requested VARCHAR(100),
ADD COLUMN IF NOT EXISTS vehicle_description VARCHAR(255),
ADD COLUMN IF NOT EXISTS passenger_load INTEGER,
ADD COLUMN IF NOT EXISTS odometer_start NUMERIC(10,1),
ADD COLUMN IF NOT EXISTS odometer_end NUMERIC(10,1),
ADD COLUMN IF NOT EXISTS total_kms NUMERIC(10,1),
ADD COLUMN IF NOT EXISTS fuel_added NUMERIC(8,2),
ADD COLUMN IF NOT EXISTS vehicle_notes TEXT,
ADD COLUMN IF NOT EXISTS charter_data JSONB;
