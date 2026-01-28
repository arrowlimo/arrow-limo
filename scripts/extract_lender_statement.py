# Extract lender statement transactions from PDF/DOCX screenshot format
# Usage: python extract_lender_statement.py <input_file>

import re
import sys
from datetime import datetime


# Requires: pip install python-docx
from docx import Document

def parse_docx_table(docx_path):
    doc = Document(docx_path)
    transactions = []
    for table in doc.tables:
        # Assume the first row is header
        for row in table.rows[1:]:
            cells = row.cells
            if len(cells) < 4:
                continue
            date_str = cells[0].text.strip()
            desc = cells[1].text.strip()
            amount_str = cells[2].text.strip().replace(",", "")
            balance_str = cells[3].text.strip().replace(",", "")
            try:
                date = datetime.strptime(date_str, "%m/%d/%Y").date()
                amount = float(amount_str) if amount_str else 0.0
                balance = float(balance_str) if balance_str else 0.0
            except Exception:
                continue
            transactions.append({
                "date": date,
                "description": desc,
                "amount": amount,
                "balance": balance
            })
    return transactions

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_lender_statement.py <input_docx_file>")
        sys.exit(1)
    input_file = sys.argv[1]
    transactions = parse_docx_table(input_file)
    for t in transactions:
        print(f"{t['date']}, {t['description']}, {t['amount']}, {t['balance']}")
