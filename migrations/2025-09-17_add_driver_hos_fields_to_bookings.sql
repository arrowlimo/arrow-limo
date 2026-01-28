-- Migration: Add driver HOS duty log fields to bookings table
-- Adds fields for workshift start/end, and a JSONB duty log for HOS compliance

ALTER TABLE bookings
ADD COLUMN IF NOT EXISTS driver_name VARCHAR(100),
ADD COLUMN IF NOT EXISTS workshift_start TIMESTAMP,
ADD COLUMN IF NOT EXISTS workshift_end TIMESTAMP,
ADD COLUMN IF NOT EXISTS duty_log JSONB;
