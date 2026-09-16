-- CRA reporting classification: distinguish vendors paid to an incorporated
-- business (no CRA information slip required - the corporation reports its
-- own business income) from unincorporated individuals/sole proprietors paid
-- for services, who may require a T4A (fees for services) or, in the
-- construction industry specifically, a T5018 (Statement of Contract
-- Payments). This is a distinct classification from T4 (employment income),
-- which only applies to actual employees on payroll.
--
-- CAL RED TECHNICAL CONSULTING is Gordon Deans' own incorporated company.
-- Arrow Limo pays the corporation for driving services; this is a vendor/
-- subcontractor expense, not employment income (no T4) and, because the
-- payee is incorporated, not a T4A/T5018 situation either (no CRA slip is
-- required at all - the corporation reports the income on its own T2).
--
-- Adds structured, queryable CRA classification fields to vendor_accounts
-- so this determination doesn't rely on free-text notes alone, and applies
-- them to Cal Red Technical Consulting.

BEGIN;

ALTER TABLE vendor_accounts
    ADD COLUMN IF NOT EXISTS is_incorporated boolean,
    ADD COLUMN IF NOT EXISTS cra_tax_slip_type character varying(10),
    ADD COLUMN IF NOT EXISTS cra_classification_notes text;

COMMENT ON COLUMN vendor_accounts.is_incorporated IS
    'TRUE if the vendor is a corporation (payments need no CRA info slip; '
    'the corporation reports its own income). FALSE/NULL for individuals '
    'or unincorporated sole proprietors, who may need a T4A or T5018.';
COMMENT ON COLUMN vendor_accounts.cra_tax_slip_type IS
    'CRA information slip required for payments to this vendor: '
    'NONE (incorporated vendor / no slip required), T4A (fees for '
    'services to an individual/unincorporated payee), T5018 (construction '
    'industry contract payments), or T4 (this vendor is actually an '
    'employee - should not normally apply to vendor_accounts rows).';

UPDATE vendor_accounts
SET is_incorporated = TRUE,
    cra_tax_slip_type = 'NONE',
    cra_classification_notes =
        'Gordon Deans'' own incorporated company (CAL RED TECHNICAL '
        || 'CONSULTING). Paid as a vendor/subcontractor for driving '
        || 'services - NOT a T4 employee. Because the payee is '
        || 'incorporated, no T4A/T5018 CRA information slip is required; '
        || 'the corporation reports this income on its own T2 return.'
WHERE canonical_vendor = 'CAL RED TECHNICAL CONSULTING';

DO $$
DECLARE
    classified_count integer;
BEGIN
    SELECT COUNT(*)
    INTO classified_count
    FROM vendor_accounts
    WHERE canonical_vendor = 'CAL RED TECHNICAL CONSULTING'
      AND is_incorporated IS TRUE
      AND cra_tax_slip_type = 'NONE';

    IF classified_count <> 1 THEN
        RAISE EXCEPTION
            'Expected the CAL RED vendor record to be CRA-classified as '
            'incorporated/no-slip, found %',
            classified_count;
    END IF;
END
$$;

COMMIT;
