-- Migration: Add missing fields to charters table that were added to bookings
-- Adds driver HOS fields and pricing fields to match bookings table schema

-- Driver HOS duty log fields
ALTER TABLE charters
ADD COLUMN IF NOT EXISTS driver_name VARCHAR(100),
ADD COLUMN IF NOT EXISTS workshift_start TIMESTAMP,
ADD COLUMN IF NOT EXISTS workshift_end TIMESTAMP,
ADD COLUMN IF NOT EXISTS duty_log JSONB;

-- Pricing fields
ALTER TABLE charters
ADD COLUMN IF NOT EXISTS default_hourly_price NUMERIC(10,2),
ADD COLUMN IF NOT EXISTS package_rate NUMERIC(10,2),
ADD COLUMN IF NOT EXISTS extra_time_rate NUMERIC(10,2),
ADD COLUMN IF NOT EXISTS airport_dropoff_price NUMERIC(10,2),
ADD COLUMN IF NOT EXISTS airport_pickup_price NUMERIC(10,2);