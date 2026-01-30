"""
CRA Audit Reports Generator

Generates CRA-required financial statements and supporting reports.
Outputs Excel workbook + CSVs + notes placeholders.

Reports included:
1) Core Financial Statements
   - Balance Sheet (as of date)
   - Income Statement (period)
   - Cash Flow Statement (period)
   - Trial Balance (as of date)
   - General Ledger Detail (period)
   - Journal Entry Report (period)

2) Sales, Revenue & Receivables
   - Sales Summary
   - Detailed Sales Ledger (per reserve/customer)
   - Accounts Receivable Aging
   - Customer Statements
   - Deposit Logs (banking)

3) Expense, Payables & Vendor
   - Expense Summary
   - Detailed Expense Ledger
   - Accounts Payable Aging
   - Vendor Purchase History
   - Bank/Credit Card Expense Mapping
   - Petty Cash Log (cash expenses)

4) Bank & Cash Reconciliation
   - Bank Reconciliation Transactions (banking ledger)
   - Credit Card Reconciliation (receipt-based)
   - Cash Reconciliation Logs (receipt-based)
   - Bank Deposit Reports (banking)

5) GST/HST
   - GST Collected Summary (tax-included, 5%)
   - Input Tax Credits (ITC) Detail (from receipts)
   - GST Return Summary (collected - ITC)

6) Payroll
   - Payroll Register
   - T4 Summary
   - CPP/EI/Tax Remittance Summary
   - Timesheet Summary (hours worked)

7) Vehicle & Assets (best-effort)
   - Vehicle/Fuel/Maintenance Expense Logs (receipt-based)
   - Asset Register (chart of accounts)

Notes:
- Uses reserve_number as business key for charter/payment matching.
- Some reports are placeholders if data is not available in DB.
"""

import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
import psycopg2


DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

GST_RATE = Decimal("0.05")


def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def to_decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def format_currency(value) -> str:
    return f"${value:,.2f}"


def ensure_output_dir(base_dir: Path, year: int) -> Path:
    out_dir = base_dir / f"cra_audit_{year}"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def export_df(df: pd.DataFrame, out_dir: Path, name: str, writer=None):
    csv_path = out_dir / f"{name}.csv"
    df.to_csv(csv_path, index=False)
    if writer is not None:
        df.to_excel(writer, sheet_name=name[:31], index=False)


def parse_args():
    if len(sys.argv) >= 2:
        year = int(sys.argv[1])
    else:
        year = datetime.now().year

    if len(sys.argv) >= 4:
        start = datetime.strptime(sys.argv[2], "%Y-%m-%d").date()
        end = datetime.strptime(sys.argv[3], "%Y-%m-%d").date()
    else:
        start = date(year, 1, 1)
        end = date(year, 12, 31)

    return year, start, end


def load_sales_summary(conn, start, end):
    query = """
        SELECT 
            DATE_TRUNC('month', charter_date)::date AS period,
            COUNT(*) AS charter_count,
            COALESCE(SUM(total_amount_due), 0) AS revenue
        FROM charters
        WHERE charter_date BETWEEN %s AND %s
        GROUP BY 1
        ORDER BY 1
    """
    return pd.read_sql_query(query, conn, params=(start, end))


def load_sales_ledger(conn, start, end):
    query = """
        SELECT
            charter_date,
            reserve_number,
            client_display_name AS customer,
            total_amount_due,
            paid_amount,
            (total_amount_due - COALESCE(paid_amount, 0)) AS balance
        FROM charters
        WHERE charter_date BETWEEN %s AND %s
        ORDER BY charter_date DESC
    """
    return pd.read_sql_query(query, conn, params=(start, end))


def load_ar_aging(conn, as_of):
    query = """
        SELECT
            client_display_name AS customer,
            reserve_number,
            charter_date,
            total_amount_due,
            COALESCE(paid_amount, 0) AS paid_amount,
            (total_amount_due - COALESCE(paid_amount, 0)) AS balance,
            (DATE %s - charter_date) AS days_outstanding,
            CASE
                WHEN (DATE %s - charter_date) <= 30 THEN 'Current'
                WHEN (DATE %s - charter_date) <= 60 THEN '31-60'
                WHEN (DATE %s - charter_date) <= 90 THEN '61-90'
                ELSE '90+'
            END AS aging_bucket
        FROM charters
        WHERE charter_date <= %s
          AND (total_amount_due - COALESCE(paid_amount, 0)) > 0.01
          AND COALESCE(cancelled, false) = false
        ORDER BY days_outstanding DESC
    """
    return pd.read_sql_query(query, conn, params=(as_of, as_of, as_of, as_of, as_of))


def load_customer_statements(conn, as_of):
    query = """
        SELECT
            client_display_name AS customer,
            COUNT(*) AS open_invoices,
            COALESCE(SUM(total_amount_due - COALESCE(paid_amount, 0)), 0) AS balance
        FROM charters
        WHERE charter_date <= %s
          AND (total_amount_due - COALESCE(paid_amount, 0)) > 0.01
          AND COALESCE(cancelled, false) = false
        GROUP BY client_display_name
        ORDER BY balance DESC
    """
    return pd.read_sql_query(query, conn, params=(as_of,))


def load_deposit_logs(conn, start, end):
    query = """
        SELECT
            transaction_date,
            account_number,
            description,
            credit_amount AS deposit_amount,
            balance
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s AND %s
          AND credit_amount > 0
        ORDER BY transaction_date DESC
    """
    return pd.read_sql_query(query, conn, params=(start, end))


def load_expense_summary(conn, start, end):
    query = """
        SELECT
            COALESCE(expense_account, 'Uncategorized') AS expense_account,
            COUNT(*) AS receipt_count,
            COALESCE(SUM(gross_amount), 0) AS total_gross,
            COALESCE(SUM(gst_amount), 0) AS total_gst
        FROM receipts
        WHERE receipt_date BETWEEN %s AND %s
        GROUP BY 1
        ORDER BY total_gross DESC
    """
    return pd.read_sql_query(query, conn, params=(start, end))


def load_expense_ledger(conn, start, end):
    query = """
        SELECT
            receipt_date,
            vendor_name,
            description,
            expense_account,
            payment_method,
            gross_amount,
            gst_amount
        FROM receipts
        WHERE receipt_date BETWEEN %s AND %s
        ORDER BY receipt_date DESC
    """
    return pd.read_sql_query(query, conn, params=(start, end))


def load_ap_aging(conn, as_of):
    query = """
        SELECT
            vendor_name,
            invoice_number,
            invoice_date,
            due_date,
            amount,
            status,
            (DATE %s - invoice_date) AS days_outstanding,
            CASE
                WHEN (DATE %s - invoice_date) <= 30 THEN 'Current'
                WHEN (DATE %s - invoice_date) <= 60 THEN '31-60'
                WHEN (DATE %s - invoice_date) <= 90 THEN '61-90'
                ELSE '90+'
            END AS aging_bucket
        FROM payables
        WHERE invoice_date <= %s
          AND COALESCE(status, '') NOT ILIKE 'paid'
        ORDER BY days_outstanding DESC
    """
    return pd.read_sql_query(query, conn, params=(as_of, as_of, as_of, as_of, as_of))


def load_vendor_purchase_history(conn, start, end):
    query = """
        SELECT
            vendor_name,
            COUNT(*) AS invoice_count,
            COALESCE(SUM(amount), 0) AS total_amount,
            COALESCE(SUM(tax_amount), 0) AS total_tax
        FROM payables
        WHERE invoice_date BETWEEN %s AND %s
        GROUP BY vendor_name
        ORDER BY total_amount DESC
    """
    return pd.read_sql_query(query, conn, params=(start, end))


def load_bank_reconciliation(conn, start, end):
    query = """
        SELECT
            account_number,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            reconciliation_status,
            balance
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s AND %s
        ORDER BY transaction_date, transaction_id
    """
    return pd.read_sql_query(query, conn, params=(start, end))


def load_cash_reconciliation(conn, start, end):
    query = """
        SELECT
            receipt_date,
            vendor_name,
            description,
            gross_amount,
            payment_method
        FROM receipts
        WHERE receipt_date BETWEEN %s AND %s
          AND COALESCE(payment_method, '') ILIKE 'cash'
        ORDER BY receipt_date DESC
    """
    return pd.read_sql_query(query, conn, params=(start, end))


def load_credit_card_reconciliation(conn, start, end):
    query = """
        SELECT
            receipt_date,
            vendor_name,
            description,
            gross_amount,
            payment_method
        FROM receipts
        WHERE receipt_date BETWEEN %s AND %s
          AND COALESCE(payment_method, '') ILIKE '%card%'
        ORDER BY receipt_date DESC
    """
    return pd.read_sql_query(query, conn, params=(start, end))


def load_gst_collected(conn, start, end):
    query = """
        SELECT
            charter_date,
            reserve_number,
            client_display_name AS customer,
            total_amount_due
        FROM charters
        WHERE charter_date BETWEEN %s AND %s
    """
    df = pd.read_sql_query(query, conn, params=(start, end))
    if df.empty:
        df["gst_amount"] = []
        return df

    df["gst_amount"] = df["total_amount_due"].apply(lambda v: float(to_decimal(v) * GST_RATE / (Decimal("1.0") + GST_RATE)))
    return df


def load_itc_detail(conn, start, end):
    query = """
        SELECT
            receipt_date,
            vendor_name,
            description,
            gross_amount,
            gst_amount,
            expense_account
        FROM receipts
        WHERE receipt_date BETWEEN %s AND %s
          AND COALESCE(gst_amount, 0) > 0
        ORDER BY receipt_date DESC
    """
    return pd.read_sql_query(query, conn, params=(start, end))


def load_payroll_register(conn, start, end):
    query = """
        SELECT
            p.pay_date,
            p.employee_id,
            e.full_name,
            p.gross_pay,
            p.cpp,
            p.ei,
            p.tax,
            p.net_pay,
            p.hours_worked
        FROM driver_payroll p
        LEFT JOIN employees e ON e.employee_id = p.employee_id
        WHERE p.pay_date BETWEEN %s AND %s
        ORDER BY p.pay_date DESC
    """
    return pd.read_sql_query(query, conn, params=(start, end))


def load_t4_summary(conn, year):
    query = """
        SELECT
            p.employee_id,
            e.full_name,
            COALESCE(SUM(p.t4_box_14), 0) AS box_14,
            COALESCE(SUM(p.t4_box_16), 0) AS box_16,
            COALESCE(SUM(p.t4_box_18), 0) AS box_18,
            COALESCE(SUM(p.t4_box_22), 0) AS box_22,
            COALESCE(SUM(p.t4_box_24), 0) AS box_24,
            COALESCE(SUM(p.t4_box_26), 0) AS box_26,
            COALESCE(SUM(p.t4_box_44), 0) AS box_44,
            COALESCE(SUM(p.t4_box_46), 0) AS box_46,
            COALESCE(SUM(p.t4_box_52), 0) AS box_52
        FROM driver_payroll p
        LEFT JOIN employees e ON e.employee_id = p.employee_id
        WHERE p.year = %s
        GROUP BY p.employee_id, e.full_name
        ORDER BY e.full_name
    """
    return pd.read_sql_query(query, conn, params=(year,))


def load_remittance_summary(conn, start, end):
    query = """
        SELECT
            DATE_TRUNC('month', pay_date)::date AS period,
            COALESCE(SUM(cpp), 0) AS cpp_total,
            COALESCE(SUM(ei), 0) AS ei_total,
            COALESCE(SUM(tax), 0) AS tax_total
        FROM driver_payroll
        WHERE pay_date BETWEEN %s AND %s
        GROUP BY 1
        ORDER BY 1
    """
    return pd.read_sql_query(query, conn, params=(start, end))


def load_balance_sheet(conn, as_of):
    query = """
        SELECT
            account_number AS account,
            account_name,
            account_type,
            COALESCE(SUM(debit), 0) AS total_debit,
            COALESCE(SUM(credit), 0) AS total_credit,
            COALESCE(SUM(debit) - SUM(credit), 0) AS balance
        FROM general_ledger
        WHERE date <= %s
        GROUP BY account_number, account_name, account_type
        ORDER BY account_number
    """
    df = pd.read_sql_query(query, conn, params=(as_of,))
    if df.empty:
        return df

    def classify(account_type):
        val = (account_type or "").lower()
        if "asset" in val:
            return "Assets"
        if "liab" in val or "payable" in val:
            return "Liabilities"
        if "equity" in val:
            return "Equity"
        return "Other"

    df["section"] = df["account_type"].apply(classify)
    return df


def load_income_statement(conn, start, end):
    revenue_query = """
        SELECT
            COALESCE(SUM(total_amount_due), 0) AS revenue
        FROM charters
        WHERE charter_date BETWEEN %s AND %s
    """
    expense_query = """
        SELECT
            COALESCE(SUM(gross_amount), 0) AS expenses
        FROM receipts
        WHERE receipt_date BETWEEN %s AND %s
    """
    rev = pd.read_sql_query(revenue_query, conn, params=(start, end)).iloc[0][0]
    exp = pd.read_sql_query(expense_query, conn, params=(start, end)).iloc[0][0]

    data = {
        "Metric": ["Revenue", "Expenses", "Net Income"],
        "Amount": [float(rev or 0), float(exp or 0), float((rev or 0) - (exp or 0))],
    }
    return pd.DataFrame(data)


def load_cash_flow_statement(conn, start, end):
    query = """
        SELECT
            COALESCE(SUM(credit_amount), 0) AS cash_in,
            COALESCE(SUM(debit_amount), 0) AS cash_out
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s AND %s
    """
    row = pd.read_sql_query(query, conn, params=(start, end)).iloc[0]
    cash_in = float(row[0] or 0)
    cash_out = float(row[1] or 0)
    data = {
        "Metric": ["Cash In", "Cash Out", "Net Cash Flow"],
        "Amount": [cash_in, cash_out, cash_in - cash_out],
    }
    return pd.DataFrame(data)


def load_trial_balance(conn, as_of):
    query = """
        SELECT
            account_number AS account,
            account_name,
            account_type,
            COALESCE(SUM(debit), 0) AS total_debit,
            COALESCE(SUM(credit), 0) AS total_credit,
            COALESCE(SUM(debit) - SUM(credit), 0) AS balance
        FROM general_ledger
        WHERE date <= %s
        GROUP BY account_number, account_name, account_type
        ORDER BY account_number
    """
    return pd.read_sql_query(query, conn, params=(as_of,))


def load_general_ledger_detail(conn, start, end):
    query = """
        SELECT
            date,
            transaction_type,
            num,
            name,
            account_name,
            account_number,
            memo_description AS memo,
            supplier,
            employee,
            customer,
            debit,
            credit,
            balance
        FROM general_ledger
        WHERE date BETWEEN %s AND %s
        ORDER BY date, id
    """
    return pd.read_sql_query(query, conn, params=(start, end))


def load_journal_entries(conn, start, end):
    query = """
        SELECT
            date,
            transaction_type,
            num,
            name,
            account_name,
            debit,
            credit,
            memo_description AS memo
        FROM general_ledger
        WHERE date BETWEEN %s AND %s
        ORDER BY date, id
    """
    return pd.read_sql_query(query, conn, params=(start, end))


def load_vehicle_expense_log(conn, start, end):
    query = """
        SELECT
            receipt_date,
            vendor_name,
            description,
            expense_account,
            gross_amount
        FROM receipts
        WHERE receipt_date BETWEEN %s AND %s
          AND (
            COALESCE(expense_account, '') ILIKE '%fuel%'
            OR COALESCE(expense_account, '') ILIKE '%maintenance%'
            OR COALESCE(expense_account, '') ILIKE '%vehicle%'
          )
        ORDER BY receipt_date DESC
    """
    return pd.read_sql_query(query, conn, params=(start, end))


def load_asset_register(conn):
    query = """
        SELECT
            account_code,
            account_name,
            account_type,
            description,
            current_balance
        FROM chart_of_accounts
        WHERE account_type ILIKE '%asset%'
        ORDER BY account_code
    """
    return pd.read_sql_query(query, conn)


def write_notes_placeholder(out_dir: Path, year: int):
    note_path = out_dir / "notes_to_financial_statements.txt"
    if note_path.exists():
        return
    content = (
        "NOTES TO FINANCIAL STATEMENTS (PLACEHOLDER)\n"
        f"Year: {year}\n\n"
        "Required disclosures (fill manually):\n"
        "- Significant accounting policies\n"
        "- Depreciation methods and rates\n"
        "- Investments and related-party transactions\n"
        "- Commitments, contingencies, and leases\n"
        "- Subsequent events\n"
    )
    note_path.write_text(content, encoding="utf-8")


def write_gifi_placeholder(out_dir: Path, year: int):
    note_path = out_dir / "gifi_mapping_placeholder.txt"
    if note_path.exists():
        return
    content = (
        "GIFI MAPPING PLACEHOLDER\n"
        f"Year: {year}\n\n"
        "Map chart_of_accounts to GIFI codes for T2 filing.\n"
        "This file is a placeholder until GIFI mapping is defined.\n"
    )
    note_path.write_text(content, encoding="utf-8")


def write_compliance_placeholders(out_dir: Path, year: int):
    placeholders = {
        "pd7a_remittance_placeholder.txt": (
            "CRA PD7A REMITTANCE (PLACEHOLDER)\n"
            f"Year: {year}\n\n"
            "Use Payroll Remittance Summary (sheet: Remittance_Summary) for CPP/EI/Tax totals.\n"
            "Filing frequency depends on CRA remitter type.\n"
            "Due dates: Monthly (15th), Quarterly (15th of month following quarter), or Annually.\n"
        ),
        "gst34_return_placeholder.txt": (
            "GST34 RETURN (PLACEHOLDER)\n"
            f"Year: {year}\n\n"
            "Use GST_Return_Summary sheet for GST collected, ITCs, and net GST due.\n"
            "Filing frequency: Monthly, quarterly, or annually based on revenue.\n"
            "Due: One month after reporting period ends.\n"
        ),
        "t4a_placeholder.txt": (
            "T4A SUMMARY (PLACEHOLDER)\n"
            f"Year: {year}\n\n"
            "No contractor slip data found in database. Add contractor payment records if applicable.\n"
            "T4A required for contractors paid $500+ in calendar year.\n"
            "Due: Last day of February following tax year.\n"
        ),
        "roe_placeholder.txt": (
            "RECORDS OF EMPLOYMENT (PLACEHOLDER)\n"
            f"Year: {year}\n\n"
            "ROE is issued per employee on separation. Not generated from current tables.\n"
            "Submit via ROE Web within 5 calendar days of interruption of earnings.\n"
        ),
        "t2_corporate_tax_placeholder.txt": (
            "T2 CORPORATE INCOME TAX RETURN (PLACEHOLDER)\n"
            f"Year: {year}\n\n"
            "Federal corporate tax return for limited companies. Use Income_Statement, Balance_Sheet, and GIFI mapping.\n"
            "Due: 6 months after fiscal year-end.\n"
            "Tax payment due: 2-3 months after fiscal year-end (depending on CCPC status).\n"
        ),
        "at1_alberta_tax_placeholder.txt": (
            "AT1 ALBERTA CORPORATE TAX RETURN (PLACEHOLDER)\n"
            f"Year: {year}\n\n"
            "Alberta provincial corporate tax return - REQUIRED for Ltd companies in Alberta.\n"
            "Filed together with federal T2. Alberta collects 8% corporate tax on taxable income.\n"
            "Due: Same as T2 (6 months after fiscal year-end).\n"
        ),
        "reg3062_alberta_registry_placeholder.txt": (
            "REG3062 ALBERTA CORPORATE REGISTRY ANNUAL RETURN (PLACEHOLDER)\n"
            f"Year: {year}\n\n"
            "Alberta corporate registry annual filing - REQUIRED for all Alberta corporations.\n"
            "Due: Within 60 days of anniversary date.\n"
            "Confirms directors, registered office, share structure.\n"
        ),
        "t5018_contractor_payments_placeholder.txt": (
            "T5018 STATEMENT OF CONTRACT PAYMENTS (PLACEHOLDER)\n"
            f"Year: {year}\n\n"
            "Required if paid contractors for construction services.\n"
            "Check receipts for construction/renovation expenses.\n"
            "Due: Last day of February following tax year.\n"
        ),
    }

    for filename, content in placeholders.items():
        path = out_dir / filename
        if not path.exists():
            path.write_text(content, encoding="utf-8")


def main():
    year, start, end = parse_args()
    base_dir = Path("L:/limo/reports")
    out_dir = ensure_output_dir(base_dir, year)

    conn = get_conn()

    output_xlsx = out_dir / f"cra_audit_reports_{year}.xlsx"
    with pd.ExcelWriter(output_xlsx, engine="xlsxwriter") as writer:
        # Core statements
        export_df(load_balance_sheet(conn, end), out_dir, "Balance_Sheet", writer)
        export_df(load_income_statement(conn, start, end), out_dir, "Income_Statement", writer)
        export_df(load_cash_flow_statement(conn, start, end), out_dir, "Cash_Flow_Statement", writer)
        export_df(load_trial_balance(conn, end), out_dir, "Trial_Balance", writer)
        export_df(load_general_ledger_detail(conn, start, end), out_dir, "General_Ledger_Detail", writer)
        export_df(load_journal_entries(conn, start, end), out_dir, "Journal_Entries", writer)

        # Sales & receivables
        export_df(load_sales_summary(conn, start, end), out_dir, "Sales_Summary", writer)
        export_df(load_sales_ledger(conn, start, end), out_dir, "Sales_Ledger", writer)
        export_df(load_ar_aging(conn, end), out_dir, "AR_Aging", writer)
        export_df(load_customer_statements(conn, end), out_dir, "Customer_Statements", writer)
        export_df(load_deposit_logs(conn, start, end), out_dir, "Deposit_Logs", writer)

        # Expenses & payables
        export_df(load_expense_summary(conn, start, end), out_dir, "Expense_Summary", writer)
        export_df(load_expense_ledger(conn, start, end), out_dir, "Expense_Ledger", writer)
        export_df(load_ap_aging(conn, end), out_dir, "AP_Aging", writer)
        export_df(load_vendor_purchase_history(conn, start, end), out_dir, "Vendor_Purchase_History", writer)
        export_df(load_cash_reconciliation(conn, start, end), out_dir, "Petty_Cash_Log", writer)

        # Bank & cash reconciliation
        export_df(load_bank_reconciliation(conn, start, end), out_dir, "Bank_Reconciliation", writer)
        export_df(load_credit_card_reconciliation(conn, start, end), out_dir, "Credit_Card_Recon", writer)
        export_df(load_cash_reconciliation(conn, start, end), out_dir, "Cash_Recon", writer)

        # GST/HST
        gst_collected = load_gst_collected(conn, start, end)
        export_df(gst_collected, out_dir, "GST_Collected_Detail", writer)
        export_df(load_itc_detail(conn, start, end), out_dir, "GST_ITC_Detail", writer)

        gst_summary = pd.DataFrame([
            {
                "period_start": start,
                "period_end": end,
                "gst_collected": float(gst_collected["gst_amount"].sum() if not gst_collected.empty else 0),
                "itc_total": float(load_itc_detail(conn, start, end)["gst_amount"].sum() if not load_itc_detail(conn, start, end).empty else 0),
            }
        ])
        gst_summary["net_gst_due"] = gst_summary["gst_collected"] - gst_summary["itc_total"]
        export_df(gst_summary, out_dir, "GST_Return_Summary", writer)
        export_df(gst_summary, out_dir, "GST34_Return", writer)

        # Payroll
        payroll_register = load_payroll_register(conn, start, end)
        export_df(payroll_register, out_dir, "Payroll_Register", writer)
        export_df(load_t4_summary(conn, year), out_dir, "T4_Summary", writer)
        remittance_summary = load_remittance_summary(conn, start, end)
        export_df(remittance_summary, out_dir, "Remittance_Summary", writer)
        export_df(remittance_summary, out_dir, "PD7A_Remittance", writer)

        # Vehicle/Assets
        export_df(load_vehicle_expense_log(conn, start, end), out_dir, "Vehicle_Expense_Log", writer)
        export_df(load_asset_register(conn), out_dir, "Asset_Register", writer)

    write_notes_placeholder(out_dir, year)
    write_gifi_placeholder(out_dir, year)
    write_compliance_placeholders(out_dir, year)

    conn.close()
    print(f"CRA audit reports generated: {output_xlsx}")
    print(f"Output directory: {out_dir}")


if __name__ == "__main__":
    main()
