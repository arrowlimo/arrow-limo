-- Route Event Types admin table for tracking charter events with billing implications
-- Used in route_table dropdown to standardize event documentation

CREATE TABLE IF NOT EXISTS route_event_types (
    event_type_id SERIAL PRIMARY KEY,
    event_code VARCHAR(50) UNIQUE NOT NULL,
    event_name VARCHAR(100) NOT NULL,
    description TEXT,
    clock_action VARCHAR(20) DEFAULT 'none' CHECK (clock_action IN ('start', 'stop', 'pause', 'resume', 'none')),
    affects_billing BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    display_order INTEGER DEFAULT 100,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE route_event_types IS 'Standardized event types for charter routing timeline - used for accurate billing documentation';
COMMENT ON COLUMN route_event_types.clock_action IS 'Billing clock action: start (begin billing), stop (end billing), pause (temporarily stop), resume (restart after pause), none (informational only)';
COMMENT ON COLUMN route_event_types.affects_billing IS 'Whether this event type impacts billable time calculations';

-- Seed default event types
INSERT INTO route_event_types (event_code, event_name, description, clock_action, affects_billing, display_order) VALUES
    ('pickup', 'Pickup', 'Customer pickup location', 'start', TRUE, 10),
    ('dropoff', 'Drop-off', 'Customer drop-off location', 'stop', TRUE, 20),
    ('split_start', 'Split Run - Start', 'First leg of split run (depart Red Deer)', 'start', TRUE, 30),
    ('split_end', 'Split Run - End', 'Return leg of split run (arrive Red Deer)', 'stop', TRUE, 40),
    ('driver_waiting', 'Driver Waiting', 'Driver standby during event (billed at standby rate)', 'pause', TRUE, 50),
    ('resume_service', 'Resume Service', 'Service resumes after waiting period', 'resume', TRUE, 60),
    ('vehicle_available', 'Vehicle Available/Drop-off', 'Drop-off with vehicle available (no charge until next pickup)', 'stop', FALSE, 70),
    ('breakdown', 'Vehicle Breakdown', 'Mechanical issue - billing paused', 'pause', FALSE, 80),
    ('replacement', 'Replacement Vehicle Arrived', 'Replacement vehicle on scene - does NOT restart billing clock', 'none', FALSE, 90),
    ('custom', 'Custom Event', 'User-defined event marker', 'none', FALSE, 100)
ON CONFLICT (event_code) DO NOTHING;

-- Create index for active events lookup
CREATE INDEX IF NOT EXISTS idx_route_event_types_active ON route_event_types(is_active, display_order) WHERE is_active = TRUE;
