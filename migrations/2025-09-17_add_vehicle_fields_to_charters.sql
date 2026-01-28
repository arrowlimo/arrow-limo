-- Migration: Add vehicle, odometer, fuel, and retainer fields to charters table
-- Adds all new fields required for advanced reporting and tracking

ALTER TABLE charters
ADD COLUMN vehicle_booked_id INTEGER,
ADD COLUMN vehicle_type_requested VARCHAR(100),
ADD COLUMN vehicle_description VARCHAR(255),
ADD COLUMN passenger_load INTEGER,
ADD COLUMN odometer_start NUMERIC(10,1),
ADD COLUMN odometer_end NUMERIC(10,1),
ADD COLUMN total_kms NUMERIC(10,1),
ADD COLUMN fuel_added NUMERIC(8,2),
ADD COLUMN vehicle_notes TEXT,
ADD COLUMN retainer NUMERIC(12,2) DEFAULT 0,
ADD COLUMN charter_data JSONB;
