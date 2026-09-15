-- Fix v_three_way_bank_verification false BANK_NO_CHECKBOOK results.
--
-- Root cause: the view used substring checks like memo NOT ILIKE '%NSF%'.
-- That accidentally treats ordinary words containing those letters as NSF.
-- Most importantly, "TRANSFER" contains "NSF" (traNSFer), so cleared
-- inter-account transfer cheques that were already in cheque_register were
-- excluded from the cheque side and displayed as BANK_NO_CHECKBOOK.
--
-- Replace the substring checks with word-boundary regexes so only actual NSF
-- and VOID words are excluded.

DO $$
DECLARE
    view_sql text;
BEGIN
    SELECT pg_get_viewdef('v_three_way_bank_verification'::regclass, true)
    INTO view_sql;

    view_sql := replace(
        view_sql,
        'COALESCE(bt_1.description, ''''::text) !~~* ''%NSF%''::text',
        'COALESCE(bt_1.description, ''''::text) !~* ''\mNSF\M''::text'
    );

    view_sql := replace(
        view_sql,
        'COALESCE(cr.status, ''''::character varying)::text !~~* ''%VOID%''::text',
        'COALESCE(cr.status, ''''::character varying)::text !~* ''\mVOID\M''::text'
    );

    view_sql := replace(
        view_sql,
        'COALESCE(cr.status, ''''::character varying)::text !~~* ''%NSF%''::text',
        'COALESCE(cr.status, ''''::character varying)::text !~* ''\mNSF\M''::text'
    );

    view_sql := replace(
        view_sql,
        'COALESCE(cr.memo, ''''::text) !~~* ''%NSF%''::text',
        'COALESCE(cr.memo, ''''::text) !~* ''\mNSF\M''::text'
    );

    EXECUTE 'CREATE OR REPLACE VIEW v_three_way_bank_verification AS ' || view_sql;
END $$;
