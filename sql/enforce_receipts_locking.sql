-- Enforce locking of canonical receipt fields after verification

CREATE OR REPLACE FUNCTION receipts_lock_guard()
RETURNS TRIGGER AS $$
BEGIN
  -- Enforce only when accounting lock is enabled
  IF get_accounting_lock_state() = TRUE THEN
    -- If receipt is verified, prevent updates to canonical fields
    IF (OLD.is_verified_banking = TRUE) OR (OLD.verified_at IS NOT NULL) OR (OLD.created_from_banking = TRUE AND OLD.verified_source IS NOT NULL) THEN
    IF (NEW.balance IS DISTINCT FROM OLD.balance)
       OR (NEW.gross_amount IS DISTINCT FROM OLD.gross_amount)
       OR (NEW.net_amount IS DISTINCT FROM OLD.net_amount)
       OR (NEW.gst_amount IS DISTINCT FROM OLD.gst_amount)
       OR (NEW.revenue IS DISTINCT FROM OLD.revenue)
       OR (NEW.vendor_name IS DISTINCT FROM OLD.vendor_name)
       OR (NEW.payment_method IS DISTINCT FROM OLD.payment_method) THEN
        RAISE EXCEPTION 'Receipts canonical fields are locked after verification';
      END IF;
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_receipts_lock_guard ON receipts;
CREATE TRIGGER trg_receipts_lock_guard
BEFORE UPDATE ON receipts
FOR EACH ROW
EXECUTE FUNCTION receipts_lock_guard();
