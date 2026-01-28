"""
Receipts staging workflow: import → calculate → validate → finalize
Demonstrates best-practice pipeline for canonicalization.
"""
import os
import psycopg2

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

finalize = os.environ.get('FINALIZE_RECEIPTS', '0') == '1'
conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# 1) Ensure staging table exists
cur.execute(
    """
    CREATE TABLE IF NOT EXISTS receipts_staging (
      staging_id SERIAL PRIMARY KEY,
      source_file TEXT,
      source_hash TEXT,
      receipt_date DATE,
      vendor_name TEXT,
      gross_amount NUMERIC(12,2),
      gst_rate NUMERIC(5,4) DEFAULT 0.05,
      calculated_gst NUMERIC(12,2),
      calculated_net NUMERIC(12,2),
      pay_method TEXT,
      mapped_bank_account_id INTEGER,
      notes TEXT,
      created_at TIMESTAMP DEFAULT NOW()
    );
    """
)

# 2) Calculate provisional GST/net in staging (example update)
cur.execute(
    """
    UPDATE receipts_staging
    SET calculated_gst = ROUND(gross_amount * gst_rate / (1 + gst_rate), 2),
        calculated_net = ROUND(gross_amount - (gross_amount * gst_rate / (1 + gst_rate)), 2)
    WHERE calculated_gst IS NULL OR calculated_net IS NULL;
    """
)

# 3) Validate against banking (placeholder)
# In practice, join to banking_transactions by date and amount to confirm matches

# 4) Finalize: insert into canonical receipts and lock via verification flags
cur.execute(
    """
    INSERT INTO receipts (
      receipt_date, vendor_name, gross_amount, gst_amount, net_amount, payment_method,
      mapped_bank_account_id, created_from_banking, is_verified_banking, verified_at
    )
    SELECT
      s.receipt_date,
      s.vendor_name,
      s.gross_amount,
      s.calculated_gst,
      s.calculated_net,
      s.pay_method,
      s.mapped_bank_account_id,
      FALSE,                                -- restoration mode: do not flag created_from_banking
      CASE WHEN %s THEN TRUE ELSE FALSE END, -- gate verification by env flag
      CASE WHEN %s THEN NOW() ELSE NULL END  -- verified_at only when FINALIZE_RECEIPTS=1
    FROM receipts_staging s
    ON CONFLICT DO NOTHING;
    """,
    (finalize, finalize)
)

conn.commit()
cur.close()
conn.close()
