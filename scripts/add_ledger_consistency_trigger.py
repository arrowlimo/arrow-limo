#!/usr/bin/env python3
"""
Add an idempotent trigger to ensure banking_receipt_matching_ledger is consistent with receipts updates.

Behavior:
- After INSERT or UPDATE OF banking_transaction_id on receipts, create corresponding ledger row if missing.
- Sets match_type='auto_generated', match_status='linked', match_confidence='auto'.
- match_date uses receipts.receipt_date if present else NOW().

This script can be re-run safely.
"""

import os
import sys
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

SQL = """
CREATE OR REPLACE FUNCTION ensure_ledger_on_receipts_update() RETURNS trigger AS $$
BEGIN
  IF NEW.banking_transaction_id IS NOT NULL THEN
    IF NOT EXISTS (
      SELECT 1 FROM banking_receipt_matching_ledger brml
      WHERE brml.receipt_id = NEW.receipt_id
        AND brml.banking_transaction_id = NEW.banking_transaction_id
    ) THEN
      INSERT INTO banking_receipt_matching_ledger (
        banking_transaction_id, receipt_id, match_date,
        match_type, match_status, match_confidence, notes, created_by
      ) VALUES (
        NEW.banking_transaction_id,
        NEW.receipt_id,
        COALESCE(NEW.receipt_date, NOW()),
        'auto_generated', 'linked', 'auto',
        'Trigger: auto-created from receipts change', 'trigger'
      );
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS receipts_banking_link_consistency ON receipts;
CREATE TRIGGER receipts_banking_link_consistency
AFTER INSERT OR UPDATE OF banking_transaction_id ON receipts
FOR EACH ROW EXECUTE FUNCTION ensure_ledger_on_receipts_update();
"""


def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    try:
        cur.execute(SQL)
        conn.commit()
        print("Trigger installed: receipts_banking_link_consistency")
    except Exception as e:
        conn.rollback()
        print(f"ERROR installing trigger: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
