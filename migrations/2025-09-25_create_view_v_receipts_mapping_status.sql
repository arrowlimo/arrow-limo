CREATE OR REPLACE VIEW v_receipts_mapping_status AS
SELECT r.id,
       r.receipt_date,
       r.vendor_name,
       r.gross_amount,
       r.gst_amount,
       r.classification,
       r.pay_account,
       r.pay_method,
       r.mapping_status,
       r.mapped_expense_account_id AS expense_account_id,
       ca1.account_name AS expense_account_name,
       ecm.mapped_cash_flow_category AS expense_cash_flow_category,
       r.mapped_bank_account_id AS bank_account_id,
       ca2.account_name AS bank_account_name,
       COALESCE(r.canonical_pay_method, em.canonical_method) AS canonical_method
FROM receipts r
LEFT JOIN epson_classifications_map ecm ON COALESCE(TRIM(r.classification),'') = ecm.epson_classification
LEFT JOIN chart_of_accounts ca1 ON ca1.account_id = r.mapped_expense_account_id
LEFT JOIN epson_pay_accounts_map epm ON COALESCE(TRIM(r.pay_account),'') = epm.epson_pay_account
LEFT JOIN chart_of_accounts ca2 ON ca2.account_id = r.mapped_bank_account_id
LEFT JOIN epson_pay_methods_map em ON COALESCE(TRIM(r.pay_method),'') = em.epson_pay_method;
