-- Add standard client columns and backfill from existing fields
-- Date: 2025-11-13

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='clients') THEN
        -- Add billing_address if missing
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' AND column_name='billing_address'
        ) THEN
            EXECUTE 'ALTER TABLE clients ADD COLUMN billing_address VARCHAR(500)';
        END IF;
        -- Add contact_info if missing
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' AND column_name='contact_info'
        ) THEN
            EXECUTE 'ALTER TABLE clients ADD COLUMN contact_info VARCHAR(200)';
        END IF;

        -- Backfill billing_address if source columns exist
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' AND column_name='address_line1') THEN
            -- Concatenate with commas using COALESCE to avoid NULL propagation
            EXECUTE 'UPDATE clients 
                     SET billing_address = 
                         NULLIF(
                           COALESCE(address_line1, '''') ||
                           CASE WHEN COALESCE(city, '''') <> '''' THEN '', '' || city ELSE '''' END ||
                           CASE WHEN COALESCE(province, '''') <> '''' THEN '', '' || province ELSE '''' END ||
                           CASE WHEN COALESCE(zip_code, '''') <> '''' THEN '', '' || zip_code ELSE '''' END,
                           ''''
                         )
                     WHERE billing_address IS NULL';
        END IF;

        -- Backfill contact_info from primary_phone if present
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clients' AND column_name='primary_phone') THEN
            EXECUTE 'UPDATE clients SET contact_info = primary_phone WHERE contact_info IS NULL';
        END IF;
    END IF;
END $$;
