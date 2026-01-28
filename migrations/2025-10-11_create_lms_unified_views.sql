-- Create unified LMS views for easy mapping inside Postgres
-- Depends on: lms_staging_reserve, lms_staging_payment (JSONB) and lms_deposits (imported CSV)

-- 1) Flatten LMS staging payments into a queryable view
CREATE OR REPLACE VIEW lms_payments AS
SELECT
  (NULLIF(raw_data->>'PaymentID',''))::int               AS payment_id,
  NULLIF(raw_data->>'Reserve_No','')                     AS reserve_no,
  (NULLIF(raw_data->>'Amount',''))::numeric              AS amount,
  NULLIF(raw_data->>'Date','')                           AS payment_date_text,
  NULLIF(raw_data->>'Key','')                            AS deposit_key,
  last_updated                                           AS last_updated
FROM lms_staging_payment;

-- 2) Flatten LMS staging reserves into a queryable view
CREATE OR REPLACE VIEW lms_reserves AS
SELECT
  s.reserve_no                                           AS reserve_no,
  NULLIF(s.raw_data->>'PU_Date','')                      AS pu_date_text,
  (NULLIF(s.raw_data->>'Rate',''))::numeric              AS rate,
  (NULLIF(s.raw_data->>'Balance',''))::numeric           AS balance,
  (NULLIF(s.raw_data->>'Deposit',''))::numeric           AS deposit,
  NULLIF(s.raw_data->>'Status','')                       AS status,
  NULLIF(s.raw_data->>'Pymt_Type','')                    AS pymt_type,
  s.last_updated                                         AS last_updated
FROM lms_staging_reserve s;

-- 3) Enrich imported LMS deposits with reserve_no by joining on deposit_key via lms_payments
--    Normalize column names to what our Python scripts expect for mapping/lookups
CREATE OR REPLACE VIEW lms_deposits_enriched AS
WITH payment_by_key AS (
  SELECT deposit_key, MAX(reserve_no) AS reserve_no
  FROM lms_payments
  WHERE deposit_key IS NOT NULL AND reserve_no IS NOT NULL
  GROUP BY deposit_key
)
SELECT
  d.id,
  d.cb_no,
  d.dep_date                          AS deposit_date,
  d.dep_key                           AS deposit_key,
  d.number,
  d.total                             AS amount,
  d.transact,
  d.type                              AS payment_method,
  d.last_updated,
  d.last_updated_by,
  d.row_hash,
  d.created_at,
  p.reserve_no,
  -- Provide a consistent synthetic payment_key used by some scripts/searches
  CASE 
    WHEN d.dep_key IS NOT NULL THEN 'LMSDEP:' || d.dep_key || ':' || COALESCE(p.reserve_no,'')
    ELSE NULL
  END                                 AS payment_key
FROM lms_deposits d
LEFT JOIN payment_by_key p ON p.deposit_key = d.dep_key;

-- 4) Convenience mapping view: one row per payment-to-deposit context with reserve
CREATE OR REPLACE VIEW lms_unified_map AS
SELECT 
  p.payment_id,
  p.reserve_no,
  p.amount            AS payment_amount,
  p.payment_date_text AS payment_date_text,
  p.deposit_key,
  d.number,
  d.amount            AS deposit_total,
  d.deposit_date,
  d.payment_method,
  d.payment_key
FROM lms_payments p
LEFT JOIN lms_deposits_enriched d ON d.deposit_key = p.deposit_key;
