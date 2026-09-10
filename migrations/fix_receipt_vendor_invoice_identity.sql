CREATE OR REPLACE FUNCTION public.receipts_auto_vendor_invoice()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    v_vendor TEXT;
    v_invoice_num TEXT;
    v_date DATE;
    v_amount NUMERIC;
    v_raw TEXT;
BEGIN
    IF NEW.gross_amount IS NULL OR NEW.gross_amount <= 0 THEN
        RETURN NEW;
    END IF;

    IF NEW.vendor_account_id = 1 THEN
        RETURN NEW;
    END IF;

    v_raw := COALESCE(
        UPPER(TRIM(NEW.canonical_vendor)),
        UPPER(TRIM(NEW.vendor_name))
    );
    IF v_raw IS NULL OR v_raw = '' THEN
        RETURN NEW;
    END IF;

    SELECT canonical_vendor INTO v_vendor
    FROM vendor_accounts
    WHERE canonical_vendor = v_raw
    LIMIT 1;

    IF v_vendor IS NULL THEN
        SELECT canonical_vendor INTO v_vendor
        FROM vendor_accounts
        WHERE v_raw ILIKE '%' || canonical_vendor || '%'
        ORDER BY LENGTH(canonical_vendor) DESC
        LIMIT 1;
    END IF;

    IF v_vendor IS NULL THEN
        RETURN NEW;
    END IF;

    v_invoice_num := NEW.source_reference;
    v_date := NEW.receipt_date;
    v_amount := NEW.gross_amount;

    -- A source receipt identifies one generated vendor invoice even if its
    -- vendor classification is corrected later.
    IF EXISTS (
        SELECT 1
        FROM vendor_invoices
        WHERE source_receipt_id = NEW.receipt_id
    ) THEN
        UPDATE vendor_invoices
        SET vendor_name = v_vendor,
            invoice_amount = v_amount,
            invoice_date = v_date,
            invoice_number = COALESCE(v_invoice_num, invoice_number),
            updated_at = NOW()
        WHERE source_receipt_id = NEW.receipt_id;
        RETURN NEW;
    END IF;

    IF v_invoice_num IS NOT NULL AND EXISTS (
        SELECT 1
        FROM vendor_invoices
        WHERE vendor_name = v_vendor
          AND invoice_number = v_invoice_num
          AND source_receipt_id IS NULL
    ) THEN
        UPDATE vendor_invoices
        SET source_receipt_id = NEW.receipt_id,
            updated_at = NOW()
        WHERE vendor_name = v_vendor
          AND invoice_number = v_invoice_num
          AND source_receipt_id IS NULL;
        RETURN NEW;
    END IF;

    INSERT INTO vendor_invoices (
        vendor_name,
        invoice_number,
        invoice_date,
        invoice_amount,
        source_receipt_id,
        created_at,
        updated_at
    )
    VALUES (
        v_vendor,
        v_invoice_num,
        v_date,
        v_amount,
        NEW.receipt_id,
        NOW(),
        NOW()
    );

    RETURN NEW;
END;
$function$;
