-- ============================================================
-- Migration: Auto-recalculate charter totals on charge/payment changes
-- Applied: 2026-05-19
-- Tables: charter_charges, charter_payments, payments
-- ============================================================

-- -------------------------------------------------------
-- TRIGGER 1: Refresh charter totals when charges change
-- -------------------------------------------------------
CREATE OR REPLACE FUNCTION refresh_charter_totals_from_charges()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_charter_id INTEGER;
BEGIN
    -- Handle both OLD and NEW rows (DELETE uses OLD)
    IF TG_OP = 'DELETE' THEN
        v_charter_id := OLD.charter_id;
    ELSE
        v_charter_id := NEW.charter_id;
    END IF;

    IF v_charter_id IS NULL THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    UPDATE charters
    SET
        grand_total = (
            SELECT COALESCE(SUM(amount), 0)
            FROM charter_charges
            WHERE charter_id = v_charter_id
        ),
        subtotal = (
            SELECT COALESCE(SUM(amount), 0)
            FROM charter_charges
            WHERE charter_id = v_charter_id
            AND charge_type NOT IN ('tax', 'gst', 'hst', 'gratuity')
        ),
        gst_amount = (
            SELECT COALESCE(SUM(amount), 0)
            FROM charter_charges
            WHERE charter_id = v_charter_id
            AND charge_type = 'tax'
        ),
        balance_owing = (
            SELECT COALESCE(SUM(cc.amount), 0)
            FROM charter_charges cc
            WHERE cc.charter_id = v_charter_id
        ) - COALESCE(amount_paid, 0),
        updated_at = NOW()
    WHERE charter_id = v_charter_id;

    RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS trg_charter_charges_refresh_totals ON charter_charges;
CREATE TRIGGER trg_charter_charges_refresh_totals
AFTER INSERT OR UPDATE OR DELETE ON charter_charges
FOR EACH ROW EXECUTE FUNCTION refresh_charter_totals_from_charges();


-- -------------------------------------------------------
-- TRIGGER 2: Refresh charter amount_paid/balance when charter_payments change
-- -------------------------------------------------------
CREATE OR REPLACE FUNCTION refresh_charter_totals_from_payments()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_charter_id_raw TEXT;
    v_charter_id_int INTEGER;
BEGIN
    IF TG_OP = 'DELETE' THEN
        v_charter_id_raw := OLD.charter_id;
    ELSE
        v_charter_id_raw := NEW.charter_id;
    END IF;

    -- charter_payments.charter_id is stored as TEXT (varchar)
    BEGIN
        v_charter_id_int := v_charter_id_raw::INTEGER;
    EXCEPTION WHEN others THEN
        RETURN COALESCE(NEW, OLD);
    END;

    IF v_charter_id_int IS NULL THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    UPDATE charters
    SET
        amount_paid = (
            SELECT COALESCE(SUM(cp.amount), 0)
            FROM charter_payments cp
            WHERE cp.charter_id::INTEGER = v_charter_id_int
        ),
        balance_owing = COALESCE(grand_total, 0) - (
            SELECT COALESCE(SUM(cp.amount), 0)
            FROM charter_payments cp
            WHERE cp.charter_id::INTEGER = v_charter_id_int
        ),
        updated_at = NOW()
    WHERE charter_id = v_charter_id_int;

    RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS trg_charter_payments_refresh_totals ON charter_payments;
CREATE TRIGGER trg_charter_payments_refresh_totals
AFTER INSERT OR UPDATE OR DELETE ON charter_payments
FOR EACH ROW EXECUTE FUNCTION refresh_charter_totals_from_payments();


-- -------------------------------------------------------
-- TRIGGER 3: Refresh receipts.net_amount when gross/gst changes
-- -------------------------------------------------------
CREATE OR REPLACE FUNCTION refresh_receipt_net_amount()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.net_amount := ROUND(
        COALESCE(NEW.gross_amount, 0) - COALESCE(NEW.gst_amount, 0),
        2
    );
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_receipts_net_amount ON receipts;
CREATE TRIGGER trg_receipts_net_amount
BEFORE INSERT OR UPDATE OF gross_amount, gst_amount ON receipts
FOR EACH ROW EXECUTE FUNCTION refresh_receipt_net_amount();


-- -------------------------------------------------------
-- Verify backfill results
-- -------------------------------------------------------
SELECT 'charters.subtotal populated' AS check_name,
    COUNT(*) total, SUM(CASE WHEN subtotal > 0 THEN 1 ELSE 0 END) populated
FROM charters;

SELECT 'receipts.net_amount populated' AS check_name,
    COUNT(*) total,
    SUM(CASE WHEN net_amount > 0 THEN 1 ELSE 0 END) populated,
    SUM(CASE WHEN net_amount = 0 AND gross_amount > 0 THEN 1 ELSE 0 END) still_zero
FROM receipts;
