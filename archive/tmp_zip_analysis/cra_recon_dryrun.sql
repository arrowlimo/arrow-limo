-- CRA vs almsdata dry-run validation SQL (SELECT only)
-- Source zip: CRAauditexport__2002-01-01_2025-12-31__20251019T204151.zip

SELECT count(*) AS total_rows_in_unified_general_ledger FROM public.unified_general_ledger;

WITH unmatched(cra_txn_id,cra_sequence,cra_date,cra_amount,cra_account_name,cra_description,suggested_action,reason) AS (
  SELECT '14633'::text, '0'::text, NULLIF('2012-04-03','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14633'::text, '1'::text, NULLIF('2012-04-03','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14629'::text, '0'::text, NULLIF('2012-04-11','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14629'::text, '1'::text, NULLIF('2012-04-11','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14652'::text, '0'::text, NULLIF('2012-04-11','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14652'::text, '1'::text, NULLIF('2012-04-11','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14614'::text, '0'::text, NULLIF('2012-04-12','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14614'::text, '1'::text, NULLIF('2012-04-12','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14632'::text, '0'::text, NULLIF('2012-04-15','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14632'::text, '1'::text, NULLIF('2012-04-15','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14619'::text, '0'::text, NULLIF('2012-05-31','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14619'::text, '1'::text, NULLIF('2012-05-31','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14609'::text, '0'::text, NULLIF('2012-11-29','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14609'::text, '1'::text, NULLIF('2012-11-29','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14635'::text, '0'::text, NULLIF('2012-12-19','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14635'::text, '1'::text, NULLIF('2012-12-19','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14621'::text, '0'::text, NULLIF('2013-02-28','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14621'::text, '1'::text, NULLIF('2013-02-28','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14586'::text, '0'::text, NULLIF('2013-03-31','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14586'::text, '1'::text, NULLIF('2013-03-31','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14610'::text, '0'::text, NULLIF('2013-04-30','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14610'::text, '1'::text, NULLIF('2013-04-30','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14654'::text, '0'::text, NULLIF('2013-05-03','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14654'::text, '1'::text, NULLIF('2013-05-03','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14634'::text, '0'::text, NULLIF('2013-05-07','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14634'::text, '1'::text, NULLIF('2013-05-07','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14646'::text, '0'::text, NULLIF('2013-06-12','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14646'::text, '1'::text, NULLIF('2013-06-12','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14582'::text, '0'::text, NULLIF('2013-07-08','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14582'::text, '1'::text, NULLIF('2013-07-08','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14600'::text, '0'::text, NULLIF('2013-07-08','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14600'::text, '1'::text, NULLIF('2013-07-08','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14604'::text, '0'::text, NULLIF('2013-07-18','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14604'::text, '1'::text, NULLIF('2013-07-18','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14608'::text, '0'::text, NULLIF('2013-12-17','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14608'::text, '1'::text, NULLIF('2013-12-17','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14615'::text, '0'::text, NULLIF('2013-12-17','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14615'::text, '1'::text, NULLIF('2013-12-17','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14625'::text, '0'::text, NULLIF('2013-12-17','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14625'::text, '1'::text, NULLIF('2013-12-17','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14640'::text, '0'::text, NULLIF('2013-12-17','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14640'::text, '1'::text, NULLIF('2013-12-17','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14599'::text, '0'::text, NULLIF('2014-02-07','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14599'::text, '1'::text, NULLIF('2014-02-07','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14590'::text, '0'::text, NULLIF('2014-02-17','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14590'::text, '1'::text, NULLIF('2014-02-17','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14598'::text, '0'::text, NULLIF('2014-05-19','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14598'::text, '1'::text, NULLIF('2014-05-19','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14617'::text, '0'::text, NULLIF('2014-05-19','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14617'::text, '1'::text, NULLIF('2014-05-19','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14592'::text, '0'::text, NULLIF('2015-05-19','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14592'::text, '1'::text, NULLIF('2015-05-19','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14620'::text, '0'::text, NULLIF('2015-05-19','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14620'::text, '1'::text, NULLIF('2015-05-19','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14639'::text, '0'::text, NULLIF('2015-06-19','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14639'::text, '1'::text, NULLIF('2015-06-19','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14602'::text, '0'::text, NULLIF('2016-01-10','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14602'::text, '1'::text, NULLIF('2016-01-10','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14638'::text, '0'::text, NULLIF('2016-01-10','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14638'::text, '1'::text, NULLIF('2016-01-10','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14653'::text, '0'::text, NULLIF('2016-05-17','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14653'::text, '1'::text, NULLIF('2016-05-17','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14648'::text, '0'::text, NULLIF('2016-07-15','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14648'::text, '1'::text, NULLIF('2016-07-15','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14650'::text, '0'::text, NULLIF('2016-08-02','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14650'::text, '1'::text, NULLIF('2016-08-02','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14583'::text, '0'::text, NULLIF('2016-10-06','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14583'::text, '1'::text, NULLIF('2016-10-06','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14630'::text, '0'::text, NULLIF('2016-10-06','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14630'::text, '1'::text, NULLIF('2016-10-06','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14585'::text, '0'::text, NULLIF('2016-11-17','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14585'::text, '1'::text, NULLIF('2016-11-17','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14595'::text, '0'::text, NULLIF('2016-11-17','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14595'::text, '1'::text, NULLIF('2016-11-17','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14622'::text, '0'::text, NULLIF('2016-11-17','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14622'::text, '1'::text, NULLIF('2016-11-17','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14643'::text, '0'::text, NULLIF('2016-11-17','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14643'::text, '1'::text, NULLIF('2016-11-17','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14649'::text, '0'::text, NULLIF('2016-11-17','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14649'::text, '1'::text, NULLIF('2016-11-17','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14589'::text, '0'::text, NULLIF('2016-11-28','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14589'::text, '1'::text, NULLIF('2016-11-28','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14624'::text, '0'::text, NULLIF('2016-11-28','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14624'::text, '1'::text, NULLIF('2016-11-28','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14594'::text, '0'::text, NULLIF('2016-12-19','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14594'::text, '1'::text, NULLIF('2016-12-19','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14597'::text, '0'::text, NULLIF('2016-12-19','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14597'::text, '1'::text, NULLIF('2016-12-19','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14603'::text, '0'::text, NULLIF('2016-12-19','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14603'::text, '1'::text, NULLIF('2016-12-19','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14612'::text, '0'::text, NULLIF('2016-12-19','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14612'::text, '1'::text, NULLIF('2016-12-19','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14613'::text, '0'::text, NULLIF('2016-12-19','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14613'::text, '1'::text, NULLIF('2016-12-19','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14618'::text, '0'::text, NULLIF('2016-12-19','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14618'::text, '1'::text, NULLIF('2016-12-19','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14623'::text, '0'::text, NULLIF('2016-12-19','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14623'::text, '1'::text, NULLIF('2016-12-19','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14636'::text, '0'::text, NULLIF('2016-12-19','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14636'::text, '1'::text, NULLIF('2016-12-19','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14642'::text, '0'::text, NULLIF('2016-12-19','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14642'::text, '1'::text, NULLIF('2016-12-19','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14645'::text, '0'::text, NULLIF('2016-12-19','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14645'::text, '1'::text, NULLIF('2016-12-19','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14641'::text, '0'::text, NULLIF('2017-01-11','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14641'::text, '1'::text, NULLIF('2017-01-11','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14588'::text, '0'::text, NULLIF('2017-02-22','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14588'::text, '1'::text, NULLIF('2017-02-22','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14591'::text, '0'::text, NULLIF('2017-02-22','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14591'::text, '1'::text, NULLIF('2017-02-22','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14584'::text, '0'::text, NULLIF('2017-02-23','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14584'::text, '1'::text, NULLIF('2017-02-23','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14593'::text, '0'::text, NULLIF('2017-02-23','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14593'::text, '1'::text, NULLIF('2017-02-23','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14601'::text, '0'::text, NULLIF('2017-02-23','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14601'::text, '1'::text, NULLIF('2017-02-23','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14611'::text, '0'::text, NULLIF('2017-02-23','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14611'::text, '1'::text, NULLIF('2017-02-23','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14651'::text, '0'::text, NULLIF('2017-02-23','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14651'::text, '1'::text, NULLIF('2017-02-23','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14616'::text, '0'::text, NULLIF('2017-04-10','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14616'::text, '1'::text, NULLIF('2017-04-10','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14631'::text, '0'::text, NULLIF('2017-05-01','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14631'::text, '1'::text, NULLIF('2017-05-01','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14605'::text, '0'::text, NULLIF('2017-06-29','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14605'::text, '1'::text, NULLIF('2017-06-29','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14626'::text, '0'::text, NULLIF('2017-06-29','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14626'::text, '1'::text, NULLIF('2017-06-29','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14637'::text, '0'::text, NULLIF('2017-08-10','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14637'::text, '1'::text, NULLIF('2017-08-10','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14587'::text, '0'::text, NULLIF('2017-08-23','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14587'::text, '1'::text, NULLIF('2017-08-23','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14606'::text, '0'::text, NULLIF('2017-08-23','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14606'::text, '1'::text, NULLIF('2017-08-23','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14627'::text, '0'::text, NULLIF('2017-08-23','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14627'::text, '1'::text, NULLIF('2017-08-23','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14644'::text, '0'::text, NULLIF('2017-08-23','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14644'::text, '1'::text, NULLIF('2017-08-23','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14607'::text, '0'::text, NULLIF('2017-08-25','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14607'::text, '1'::text, NULLIF('2017-08-25','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14628'::text, '0'::text, NULLIF('2017-08-25','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14628'::text, '1'::text, NULLIF('2017-08-25','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14596'::text, '0'::text, NULLIF('2017-09-19','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14596'::text, '1'::text, NULLIF('2017-09-19','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14647'::text, '0'::text, NULLIF('2017-09-27','')::date, NULLIF('','')::numeric, ''::text, 'Bill Payment (Cheque)'::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
UNION ALL
  SELECT '14647'::text, '1'::text, NULLIF('2017-09-27','')::date, NULLIF('','')::numeric, '2000 Accounts Payable'::text, ''::text, 'REVIEW_MAPPING'::text, 'Missing CRA date or amount; cannot safely match'::text
)
SELECT * FROM unmatched ORDER BY abs(COALESCE(cra_amount,0)) DESC, cra_date NULLS LAST LIMIT 200;

SELECT EXTRACT(YEAR FROM COALESCE(transaction_date, created_at::date))::int AS year,
       count(*) AS ledger_count,
       round(sum(COALESCE((debit_amount-credit_amount),0))::numeric,2) AS ledger_total
FROM public.unified_general_ledger
GROUP BY 1 ORDER BY 1;
