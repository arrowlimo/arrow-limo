-- Lock completed banking years to prevent modifications
-- Years: 2012 through 2023

CREATE TABLE IF NOT EXISTS system_locked_years (
    year integer PRIMARY KEY,
    locked boolean NOT NULL DEFAULT true,
    locked_at timestamptz NOT NULL DEFAULT now(),
    locked_by text
);

INSERT INTO system_locked_years(year) VALUES 
    (2012),(2013),(2014),(2015),(2016),(2017),(2018),(2019),(2020),(2021),(2022),(2023)
ON CONFLICT (year) DO NOTHING;

CREATE OR REPLACE FUNCTION enforce_banking_lock()
RETURNS trigger AS $$
BEGIN
    -- For INSERT: check NEW.transaction_date
    IF (TG_OP = 'INSERT') THEN
        IF EXISTS (
            SELECT 1 FROM system_locked_years l
            WHERE l.locked = true
              AND EXTRACT(YEAR FROM NEW.transaction_date) = l.year
        ) THEN
            RAISE EXCEPTION 'Banking data for year % is locked; no INSERT allowed', EXTRACT(YEAR FROM NEW.transaction_date);
        END IF;
        RETURN NEW;
    END IF;

    -- For UPDATE: check both OLD and NEW
    IF (TG_OP = 'UPDATE') THEN
        IF EXISTS (
            SELECT 1 FROM system_locked_years l
            WHERE l.locked = true
              AND (EXTRACT(YEAR FROM COALESCE(NEW.transaction_date, OLD.transaction_date)) = l.year
                   OR EXTRACT(YEAR FROM OLD.transaction_date) = l.year)
        ) THEN
            RAISE EXCEPTION 'Banking data for year % is locked; no UPDATE allowed', EXTRACT(YEAR FROM COALESCE(NEW.transaction_date, OLD.transaction_date));
        END IF;
        RETURN NEW;
    END IF;

    -- For DELETE: check OLD.transaction_date
    IF (TG_OP = 'DELETE') THEN
        IF EXISTS (
            SELECT 1 FROM system_locked_years l
            WHERE l.locked = true
              AND EXTRACT(YEAR FROM OLD.transaction_date) = l.year
        ) THEN
            RAISE EXCEPTION 'Banking data for year % is locked; no DELETE allowed', EXTRACT(YEAR FROM OLD.transaction_date);
        END IF;
        RETURN OLD;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_banking_transactions_lock ON banking_transactions;
CREATE TRIGGER trg_banking_transactions_lock
BEFORE INSERT OR UPDATE OR DELETE ON banking_transactions
FOR EACH ROW EXECUTE FUNCTION enforce_banking_lock();
