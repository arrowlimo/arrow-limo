_normalized_gl_view_initialized = False


def _ensure_normalized_general_ledger_view(cur) -> bool:
    """Create or refresh a normalized ledger view for reporting."""

    global _normalized_gl_view_initialized

    cur.execute("SELECT to_regclass('public.general_ledger')")
    if cur.fetchone()[0] is None:
        return False

    if _normalized_gl_view_initialized:
        return True

    cur.execute(
        """
        CREATE OR REPLACE VIEW general_ledger_normalized AS
        WITH base AS (
            SELECT
                gl.*,
                COALESCE(gl.transaction_date, gl.date) AS entry_date,
                TRIM(COALESCE(gl.account, '')) AS raw_account,
                CASE
                    WHEN TRIM(COALESCE(gl.account, '')) ~ '^\\d+'
                        THEN SUBSTRING(TRIM(gl.account) FROM '^\\d+')
                    ELSE NULL
                END AS leading_digits,
                CASE
                    WHEN TRIM(COALESCE(gl.account, '')) ~ '^\\d+\\s+'
                        THEN BTRIM(REGEXP_REPLACE(
                            TRIM(gl.account), '^\\d+\\s*', ''))
                    ELSE NULL
                END AS name_after_digits
            FROM general_ledger gl
        ),
        resolved AS (
            SELECT
                b.*,
                COALESCE(
                    coa_code.account_code,
                    coa_bank.account_code,
                    coa_name_after.account_code,
                    coa_name.account_code,
                    CASE
                        WHEN b.raw_account ~ '^\\d+'
                        THEN SUBSTRING(b.raw_account FROM '^\\d+')
                        ELSE NULL
                    END,
                    NULLIF(b.raw_account, ''),
                    'NO-ACCOUNT'
                ) AS normalized_account_code,
                COALESCE(
                    NULLIF(b.name_after_digits, ''),
                    coa_code.account_name,
                    coa_bank.account_name,
                    coa_name_after.account_name,
                    coa_name.account_name,
                    NULLIF(b.raw_account, ''),
                    'Uncategorized'
                ) AS normalized_account_name,
                COALESCE(
                    coa_code.account_name,
                    coa_bank.account_name,
                    coa_name_after.account_name,
                    coa_name.account_name,
                    NULLIF(b.name_after_digits, ''),
                    NULLIF(b.raw_account, ''),
                    'Uncategorized'
                ) AS canonical_account_name,
                COALESCE(
                    NULLIF(TRIM(b.account_type), ''),
                    coa_code.account_type,
                    coa_bank.account_type,
                    coa_name_after.account_type,
                    coa_name.account_type,
                    'Unknown'
                ) AS normalized_account_type
            FROM base b
            LEFT JOIN chart_of_accounts coa_code
                ON coa_code.account_code = b.leading_digits
            LEFT JOIN chart_of_accounts coa_bank
                ON coa_bank.bank_account_number = b.leading_digits
            LEFT JOIN chart_of_accounts coa_name
                ON LOWER(coa_name.account_name) = LOWER(b.raw_account)
            LEFT JOIN chart_of_accounts coa_name_after
                ON b.name_after_digits IS NOT NULL
               AND LOWER(coa_name_after.account_name)
               = LOWER(b.name_after_digits)
        )
        SELECT
            id AS gl_id,
            entry_date,
            raw_account,
            normalized_account_code AS account_code,
            normalized_account_name AS account_name,
            canonical_account_name,
            normalized_account_type AS account_type,
            CASE
                WHEN normalized_account_code ~ '^1' THEN 'Asset'
                WHEN normalized_account_code ~ '^2' THEN 'Liability'
                WHEN normalized_account_code ~ '^3' THEN 'Equity'
                WHEN normalized_account_code ~ '^4' THEN 'Revenue'
                WHEN normalized_account_code ~ '^[5-8]' THEN 'Expense'
                WHEN LOWER(canonical_account_name) LIKE '%payable%'
                    THEN 'Liability'
                WHEN LOWER(canonical_account_name) LIKE '%loan%'
                    THEN 'Liability'
                WHEN LOWER(canonical_account_name) LIKE '%visa%'
                    THEN 'Liability'
                WHEN LOWER(canonical_account_name) LIKE '%mastercard%'
                    THEN 'Liability'
                WHEN LOWER(canonical_account_name) LIKE '%gst/hst%'
                    THEN 'Liability'
                WHEN LOWER(canonical_account_name) LIKE '%tax payable%'
                    THEN 'Liability'
                WHEN LOWER(canonical_account_name) LIKE '%bank%'
                    THEN 'Asset'
                WHEN LOWER(canonical_account_name) LIKE '%checking%'
                    THEN 'Asset'
                WHEN LOWER(canonical_account_name) LIKE '%deposit account%'
                    THEN 'Asset'
                WHEN LOWER(canonical_account_name) LIKE '%cash%'
                    THEN 'Asset'
                WHEN LOWER(canonical_account_name) LIKE '%petty cash%'
                    THEN 'Asset'
                WHEN LOWER(canonical_account_name) LIKE '%prepaid%'
                    THEN 'Asset'
                WHEN LOWER(canonical_account_name) LIKE '%receivable%'
                    THEN 'Asset'
                WHEN LOWER(canonical_account_name) LIKE 'limousines & busses%'
                    THEN 'Asset'
                WHEN LOWER(canonical_account_name) LIKE '%amort%'
                    THEN 'Asset'
                WHEN LOWER(canonical_account_name) LIKE '%vehicle%'
                    THEN 'Asset'
                WHEN LOWER(canonical_account_name) LIKE '%supplies%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name) LIKE '%fuel%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name) LIKE '%rent%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name) LIKE '%expense%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name) LIKE '%travel%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name) LIKE '%utilities%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name) LIKE '%materials%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name) LIKE '%parking%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name) LIKE '%hospitality%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name)
                    LIKE '%charter client purchases%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name) = 'auto'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name) LIKE '%income%'
                    THEN 'Revenue'
                WHEN LOWER(canonical_account_name) LIKE '%revenue%'
                    THEN 'Revenue'
                WHEN LOWER(canonical_account_name) LIKE '%expense%'
                    THEN 'Expense'
                WHEN LOWER(canonical_account_name) LIKE '%asset%'
                    THEN 'Asset'
                WHEN LOWER(canonical_account_name) LIKE '%liabil%'
                    THEN 'Liability'
                WHEN LOWER(canonical_account_name) LIKE '%equity%'
                    THEN 'Equity'
                ELSE 'Uncategorized'
            END AS normalized_account_class
        FROM resolved
        """
    )
    _normalized_gl_view_initialized = True
    return True
