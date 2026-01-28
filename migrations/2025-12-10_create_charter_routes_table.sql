-- Migration: Create charter_routes table for parent-child route management
-- This replaces the JSON charter_data.routing structure with proper relational data

-- Create charter_routes table
CREATE TABLE IF NOT EXISTS charter_routes (
    route_id SERIAL PRIMARY KEY,
    charter_id INTEGER NOT NULL REFERENCES charters(charter_id) ON DELETE CASCADE,
    route_sequence INTEGER NOT NULL DEFAULT 1,
    
    -- Route details
    pickup_location TEXT,
    pickup_time TIME,
    dropoff_location TEXT,
    dropoff_time TIME,
    
    -- Time calculations
    estimated_duration_minutes INTEGER,  -- Calculated field
    actual_duration_minutes INTEGER,     -- Actual time taken
    
    -- Distance
    estimated_distance_km NUMERIC(10, 2),
    actual_distance_km NUMERIC(10, 2),
    
    -- Pricing
    route_price NUMERIC(10, 2),
    route_notes TEXT,
    
    -- Status tracking
    route_status VARCHAR(50) DEFAULT 'pending',  -- pending, in_progress, completed, cancelled
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Ensure routes are ordered per charter
    UNIQUE(charter_id, route_sequence)
);

-- Create indexes for performance
CREATE INDEX idx_charter_routes_charter_id ON charter_routes(charter_id);
CREATE INDEX idx_charter_routes_sequence ON charter_routes(charter_id, route_sequence);
CREATE INDEX idx_charter_routes_status ON charter_routes(route_status);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_charter_routes_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER charter_routes_updated_at
    BEFORE UPDATE ON charter_routes
    FOR EACH ROW
    EXECUTE FUNCTION update_charter_routes_timestamp();

-- Create view for charter summary with route totals
CREATE OR REPLACE VIEW charter_with_route_totals AS
SELECT 
    c.*,
    COUNT(r.route_id) as total_routes,
    SUM(r.estimated_duration_minutes) as total_estimated_minutes,
    SUM(r.actual_duration_minutes) as total_actual_minutes,
    SUM(r.estimated_distance_km) as total_estimated_km,
    SUM(r.actual_distance_km) as total_actual_km,
    SUM(r.route_price) as total_route_price
FROM charters c
LEFT JOIN charter_routes r ON c.charter_id = r.charter_id
GROUP BY c.charter_id;

COMMENT ON TABLE charter_routes IS 'Individual route segments for each charter booking';
COMMENT ON COLUMN charter_routes.route_sequence IS 'Order of routes within a charter (1, 2, 3, ...)';
COMMENT ON COLUMN charter_routes.estimated_duration_minutes IS 'Calculated time for this route segment in minutes';
COMMENT ON COLUMN charter_routes.actual_duration_minutes IS 'Actual time taken for this route segment';
COMMENT ON COLUMN charter_routes.route_status IS 'Status: pending, in_progress, completed, cancelled';
