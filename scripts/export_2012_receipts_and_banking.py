#!/usr/bin/env python3
"""
Export 2012 receipts (all columns) and 2012 banking transactions (all accounts) into a single Excel workbook
with two sheets to support receipt creation/matching.
"""

import os
from datetime import datetime

import pandas as pd
import psycopg2
from openpyxl.utils import get_column_letter

DB_SETTINGS = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "almsdata"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "***REDACTED***"),
}

OUTPUT_PATH = os.path.join("reports", "2012_receipts_and_banking.xlsx")
START_DATE = "2012-01-01"
END_DATE = "2012-12-31"


def fetch_df(sql: str, params=None) -> pd.DataFrame:
    conn = psycopg2.connect(**DB_SETTINGS)
    try:
        df = pd.read_sql(sql, conn, params=params)
        return df
    finally:
        conn.close()


def strip_timezones(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with timezone info removed for Excel compatibility."""
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            if getattr(out[col].dtype, "tz", None) is not None:
                out[col] = out[col].dt.tz_convert(None)
        # Handle object columns that may contain pandas Timestamps with tz
        elif out[col].apply(lambda x: hasattr(x, "tzinfo") and x.tzinfo is not None).any():
            out[col] = out[col].apply(lambda x: x.tz_convert(None) if hasattr(x, "tz_convert") else x.replace(tzinfo=None) if hasattr(x, "tzinfo") else x)
    return out


def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    account_labels = {
        '0228362': ('CIBC 0228362', 'BLUE'),
        '903990106011': ('Scotia 903990106011', 'GREEN'),
        '3648117': ('CIBC Business Deposit 3648117', 'ORANGE'),
    }

    receipts_sql = """
        SELECT *
        FROM receipts
        WHERE receipt_date >= %s AND receipt_date <= %s
        ORDER BY receipt_date, receipt_id
    """

    banking_sql = """
        SELECT transaction_id,
               account_number,
               transaction_date,
               description,
               debit_amount,
               credit_amount,
               balance,
               category,
               source_file,
               source_hash,
               created_at
        FROM banking_transactions
        WHERE transaction_date >= %s AND transaction_date <= %s
        ORDER BY transaction_date, transaction_id
    """

    print("Fetching 2012 receipts...")
    receipts_df = strip_timezones(fetch_df(receipts_sql, params=(START_DATE, END_DATE)))
    print(f"  ✓ {len(receipts_df):,} receipt rows")

    print("Fetching 2012 banking (all accounts)...")
    banking_df = strip_timezones(fetch_df(banking_sql, params=(START_DATE, END_DATE)))
    if not banking_df.empty:
        banking_df['account_number'] = banking_df['account_number'].astype(str)
        banking_df['account_label'] = banking_df['account_number'].map(lambda x: account_labels.get(x, (x, ''))[0])
        banking_df['account_color'] = banking_df['account_number'].map(lambda x: account_labels.get(x, (x, ''))[1])
    print(f"  ✓ {len(banking_df):,} banking rows")

    print(f"Writing Excel -> {OUTPUT_PATH}...")
    with pd.ExcelWriter(OUTPUT_PATH, engine="openpyxl") as writer:
        receipts_df.to_excel(writer, sheet_name="Receipts 2012", index=False)
        banking_df.to_excel(writer, sheet_name="Banking 2012", index=False)

        # Adjust simple column widths for readability
        for sheet_name, df in [("Receipts 2012", receipts_df), ("Banking 2012", banking_df)]:
            ws = writer.sheets[sheet_name]
            for idx, col in enumerate(df.columns, start=1):
                max_len = min(50, max(len(str(col)), df[col].astype(str).map(len).max() if not df.empty else 0) + 2)
                ws.column_dimensions[get_column_letter(idx)].width = max_len

    print("Done.")
    print(f"Receipts date range: {receipts_df['receipt_date'].min()} to {receipts_df['receipt_date'].max()}")
    print(f"Banking date range: {banking_df['transaction_date'].min()} to {banking_df['transaction_date'].max()}")


if __name__ == "__main__":
    main()
