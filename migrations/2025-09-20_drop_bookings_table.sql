-- Migration: Drop the empty bookings table to avoid confusion
-- All data has been migrated to charters table and foreign keys have been updated
-- The bookings table is empty and no longer needed

-- First, ensure no foreign key constraints reference bookings table
-- (should be none after previous migration, but let's be safe)

-- Drop the bookings table
DROP TABLE IF EXISTS bookings CASCADE;

-- Verify the table is gone
-- This will be checked in the verification script