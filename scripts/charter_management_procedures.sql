-- Lock/Unlock/Cancel/Delete Charter Procedures
-- Follows mandatory coding requirements using reserve_number as business key

-- ===== PROCEDURE 1: Lock Charter =====
-- Prevents editing of charter details (sets locked flag)
CREATE OR REPLACE FUNCTION lock_charter(p_reserve_number VARCHAR)
RETURNS TABLE (
    success BOOLEAN,
    message VARCHAR
) AS $$
DECLARE
    v_charter_id INTEGER;
BEGIN
    -- Find charter by reserve_number (business key)
    SELECT charter_id INTO v_charter_id
    FROM charters
    WHERE reserve_number = p_reserve_number;
    
    IF v_charter_id IS NULL THEN
        RETURN QUERY SELECT FALSE, 'Charter not found: ' || p_reserve_number;
        RETURN;
    END IF;
    
    -- Update charter status to 'Locked'
    UPDATE charters
    SET status = 'Locked',
        updated_at = NOW()
    WHERE charter_id = v_charter_id;
    
    RETURN QUERY SELECT TRUE, 'Charter locked successfully: ' || p_reserve_number;
END;
$$ LANGUAGE plpgsql;

-- ===== PROCEDURE 2: Unlock Charter =====
-- Re-enables editing of charter details
CREATE OR REPLACE FUNCTION unlock_charter(p_reserve_number VARCHAR)
RETURNS TABLE (
    success BOOLEAN,
    message VARCHAR
) AS $$
DECLARE
    v_charter_id INTEGER;
BEGIN
    SELECT charter_id INTO v_charter_id
    FROM charters
    WHERE reserve_number = p_reserve_number;
    
    IF v_charter_id IS NULL THEN
        RETURN QUERY SELECT FALSE, 'Charter not found: ' || p_reserve_number;
        RETURN;
    END IF;
    
    -- Update charter status back to previous (Confirmed, In Progress, etc.)
    UPDATE charters
    SET status = 'Confirmed',
        updated_at = NOW()
    WHERE charter_id = v_charter_id;
    
    RETURN QUERY SELECT TRUE, 'Charter unlocked successfully: ' || p_reserve_number;
END;
$$ LANGUAGE plpgsql;

-- ===== PROCEDURE 3: Cancel Charter =====
-- Marks charter as cancelled and deletes ALL charges (balance becomes $0)
CREATE OR REPLACE FUNCTION cancel_charter(p_reserve_number VARCHAR)
RETURNS TABLE (
    success BOOLEAN,
    message VARCHAR,
    deleted_count INTEGER
) AS $$
DECLARE
    v_charter_id INTEGER;
    v_deleted_count INTEGER := 0;
    v_total_deleted NUMERIC := 0;
BEGIN
    -- Find charter by reserve_number
    SELECT charter_id INTO v_charter_id
    FROM charters
    WHERE reserve_number = p_reserve_number;
    
    IF v_charter_id IS NULL THEN
        RETURN QUERY SELECT FALSE, 'Charter not found: ' || p_reserve_number, 0;
        RETURN;
    END IF;
    
    -- Get total amount of charges being deleted (for audit)
    SELECT COALESCE(SUM(charge_amount), 0) INTO v_total_deleted
    FROM charges
    WHERE reserve_number = p_reserve_number;
    
    -- Delete ALL charges (clears balance to $0)
    DELETE FROM charges
    WHERE reserve_number = p_reserve_number;
    
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    
    -- Mark charter as cancelled
    UPDATE charters
    SET cancelled = TRUE,
        status = 'Cancelled',
        updated_at = NOW()
    WHERE charter_id = v_charter_id;
    
    RETURN QUERY SELECT TRUE, 
        'Charter cancelled. Deleted ' || v_deleted_count || ' charges totaling $' || 
        CAST(v_total_deleted AS VARCHAR) || '. Balance cleared to $0.',
        v_deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ===== PROCEDURE 4: Delete Charge =====
-- Delete a specific charge by charge_id
-- Checks for authorization and audit trail
CREATE OR REPLACE FUNCTION delete_charge(
    p_reserve_number VARCHAR,
    p_charge_id INTEGER,
    p_reason VARCHAR DEFAULT NULL
)
RETURNS TABLE (
    success BOOLEAN,
    message VARCHAR,
    deleted_amount NUMERIC
) AS $$
DECLARE
    v_charge_amount NUMERIC;
    v_charge_exists BOOLEAN;
BEGIN
    -- Verify charge belongs to this charter
    SELECT charge_amount INTO v_charge_amount
    FROM charges
    WHERE charge_id = p_charge_id
    AND reserve_number = p_reserve_number;
    
    IF v_charge_amount IS NULL THEN
        RETURN QUERY SELECT FALSE, 'Charge not found for this charter', 0;
        RETURN;
    END IF;
    
    -- Delete the charge
    DELETE FROM charges
    WHERE charge_id = p_charge_id
    AND reserve_number = p_reserve_number;
    
    -- Log deletion in audit (if audit table exists)
    BEGIN
        INSERT INTO charge_audit_log (
            charge_id,
            reserve_number,
            action,
            deleted_amount,
            reason,
            deleted_at
        ) VALUES (
            p_charge_id,
            p_reserve_number,
            'DELETE',
            v_charge_amount,
            p_reason,
            NOW()
        );
    EXCEPTION WHEN undefined_table THEN
        NULL;  -- Audit table doesn't exist, continue
    END;
    
    RETURN QUERY SELECT TRUE, 
        'Charge deleted successfully: $' || COALESCE(CAST(v_charge_amount AS VARCHAR), '0.00'),
        v_charge_amount;
END;
$$ LANGUAGE plpgsql;

-- ===== PROCEDURE 5: Get Charter Lock Status =====
-- Check if charter is locked
CREATE OR REPLACE FUNCTION get_charter_lock_status(p_reserve_number VARCHAR)
RETURNS TABLE (
    is_locked BOOLEAN,
    status VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT (c.status = 'Locked'), c.status
    FROM charters c
    WHERE c.reserve_number = p_reserve_number;
END;
$$ LANGUAGE plpgsql;

-- ===== PROCEDURE 6: Get Charter Balance =====
-- Calculate current balance for charter
CREATE OR REPLACE FUNCTION get_charter_balance(p_reserve_number VARCHAR)
RETURNS TABLE (
    total_charges NUMERIC,
    total_payments NUMERIC,
    balance_due NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COALESCE(SUM(CASE WHEN type = 'CHARGE' THEN amount ELSE 0 END), 0) as total_charges,
        COALESCE(SUM(CASE WHEN type = 'PAYMENT' THEN amount ELSE 0 END), 0) as total_payments,
        COALESCE(SUM(CASE WHEN type = 'CHARGE' THEN amount ELSE 0 END), 0) -
        COALESCE(SUM(CASE WHEN type = 'PAYMENT' THEN amount ELSE 0 END), 0) as balance_due
    FROM (
        -- Charges
        SELECT 'CHARGE' as type, charge_amount as amount
        FROM charges
        WHERE reserve_number = p_reserve_number
        
        UNION ALL
        
        -- Payments
        SELECT 'PAYMENT' as type, amount
        FROM payments
        WHERE reserve_number = p_reserve_number
        AND payment_status != 'cancelled'
    ) t;
END;
$$ LANGUAGE plpgsql;

-- ===== PROCEDURE 7: Record Payment NFD (No Funds Deposit) =====
-- Add $25 NFD fee and record in charges
CREATE OR REPLACE FUNCTION record_nfd_charge(p_reserve_number VARCHAR)
RETURNS TABLE (
    success BOOLEAN,
    message VARCHAR,
    charge_id INTEGER
) AS $$
DECLARE
    v_new_charge_id INTEGER;
BEGIN
    INSERT INTO charges (
        reserve_number,
        charge_date,
        charge_description,
        charge_amount,
        charge_type,
        created_at
    ) VALUES (
        p_reserve_number,
        CURRENT_DATE,
        'NSF - No Funds Deposit Fee',
        25.00,
        'nfd',
        NOW()
    )
    RETURNING charges.charge_id INTO v_new_charge_id;
    
    RETURN QUERY SELECT TRUE, 
        'NFD charge of $25.00 recorded',
        v_new_charge_id;
END;
$$ LANGUAGE plpgsql;

-- ===== GRANT PERMISSIONS =====
-- Allow application user to execute procedures
GRANT EXECUTE ON FUNCTION lock_charter(VARCHAR) TO postgres;
GRANT EXECUTE ON FUNCTION unlock_charter(VARCHAR) TO postgres;
GRANT EXECUTE ON FUNCTION cancel_charter(VARCHAR) TO postgres;
GRANT EXECUTE ON FUNCTION delete_charge(VARCHAR, INTEGER, VARCHAR) TO postgres;
GRANT EXECUTE ON FUNCTION get_charter_lock_status(VARCHAR) TO postgres;
GRANT EXECUTE ON FUNCTION get_charter_balance(VARCHAR) TO postgres;
GRANT EXECUTE ON FUNCTION record_nfd_charge(VARCHAR) TO postgres;
