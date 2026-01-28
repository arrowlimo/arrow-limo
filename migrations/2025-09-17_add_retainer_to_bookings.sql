-- Migration: Add retainer column to bookings table
-- Adds a numeric retainer column for tracking non-refundable retainers on bookings

ALTER TABLE bookings
ADD COLUMN retainer NUMERIC(12,2) DEFAULT 0;
