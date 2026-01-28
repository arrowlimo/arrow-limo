-- Migration: Add vehicle and trip fields to bookings table
ALTER TABLE bookings
ADD COLUMN vehicle_booked_id TEXT,
ADD COLUMN vehicle_type_requested TEXT,
ADD COLUMN vehicle_description TEXT,
ADD COLUMN passenger_load INTEGER,
ADD COLUMN default_hourly_price NUMERIC(10,2),
ADD COLUMN package_rate NUMERIC(10,2),
ADD COLUMN extra_time_rate NUMERIC(10,2),
ADD COLUMN airport_dropoff_price NUMERIC(10,2),
ADD COLUMN airport_pickup_price NUMERIC(10,2),
ADD COLUMN odometer_start NUMERIC(10,1),
ADD COLUMN odometer_end NUMERIC(10,1),
ADD COLUMN total_kms NUMERIC(10,1),
ADD COLUMN fuel_added NUMERIC(10,2),
ADD COLUMN vehicle_notes TEXT;

-- Odometer log table
CREATE TABLE IF NOT EXISTS vehicle_odometer_log (
    id SERIAL PRIMARY KEY,
    vehicle_id TEXT NOT NULL,
    reading NUMERIC(10,1) NOT NULL,
    reading_type TEXT NOT NULL, -- 'start' or 'end'
    booking_id INTEGER REFERENCES bookings(id),
    recorded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    recorded_by TEXT
);

-- Fuel log table
CREATE TABLE IF NOT EXISTS vehicle_fuel_log (
    id SERIAL PRIMARY KEY,
    vehicle_id TEXT NOT NULL,
    amount NUMERIC(10,2) NOT NULL,
    booking_id INTEGER REFERENCES bookings(id),
    receipt_id INTEGER,
    recorded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    recorded_by TEXT
);
