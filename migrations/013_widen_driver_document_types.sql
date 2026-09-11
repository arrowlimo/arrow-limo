-- 013: widen the driver_documents document_type vocabulary.
--
-- The original CHECK constraint predates the Red Deer compliance work and is
-- missing document kinds the business is legally required to keep: ProServe
-- certification, driver abstracts, vulnerable sector checks and the payroll
-- forms produced when someone is hired or leaves.
--
-- Without this, the PC app's qualifications and documents editor could not
-- save any of those record types -- the insert was rejected by the database.
--
-- Note this table is the office's record of a qualification. It is separate
-- from employee_document_uploads, which stores the scanned file a driver
-- submits through the portal and has its own vocabulary.
--
-- Existing rows all use 'license' and are unaffected.

BEGIN;

ALTER TABLE driver_documents
    DROP CONSTRAINT IF EXISTS driver_documents_document_type_check;

ALTER TABLE driver_documents
    ADD CONSTRAINT driver_documents_document_type_check
    CHECK (document_type IN (
        'license',
        'chauffeur_permit',
        'proserve',
        'medical_certificate',
        'driver_abstract',
        'vulnerable_sector',
        'background_check',
        'drug_test',
        'training_certificate',
        'insurance',
        't4',
        'employment_contract',
        'roe',
        'other'
    ));

COMMIT;
