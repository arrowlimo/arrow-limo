-- Add booking_status column to charters for quote-to-charter logic
ALTER TABLE charters ADD COLUMN booking_status VARCHAR(20) DEFAULT 'quote';
-- Add retainer column to charters table for non-refundable retainer tracking
ALTER TABLE charters ADD COLUMN retainer NUMERIC(10,2) DEFAULT 0;
