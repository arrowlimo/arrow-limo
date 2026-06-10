-- Shared sequence for clients.account_number
--
-- Both the web backend (modern_backend/app/routers/bookings.py) and the desktop
-- app (desktop_app/client_drill_down.py) previously generated new account
-- numbers with `MAX(CAST(account_number AS INTEGER)) + 1`. That is a full-table
-- scan and is race-prone: two concurrent client creations can pick the same
-- number (clients.account_number has a UNIQUE constraint, so the loser errors).
--
-- This sequence is the single source of new account numbers for BOTH apps. The
-- application code calls `nextval('account_number_seq')` and only falls back to
-- MAX+1 if the sequence is unavailable (guarded by a SAVEPOINT so the
-- surrounding transaction is not aborted).
--
-- Idempotent: safe to run multiple times.

CREATE SEQUENCE IF NOT EXISTS account_number_seq;

-- Advance the sequence to the current max numeric account_number so the next
-- value is MAX+1 and never collides with existing rows. GREATEST(...) ensures
-- re-running never moves the sequence backwards.
SELECT setval(
    'account_number_seq',
    GREATEST(
        (
            SELECT COALESCE(MAX(CAST(account_number AS INTEGER)), 7604)
            FROM clients
            WHERE account_number ~ '^[0-9]+$'
        ),
        (SELECT last_value FROM account_number_seq)
    ),
    true
);
