import pdfplumber
import re
import csv
from pathlib import Path

PDF_PATH = r"L:\limo\excluded_files\Clean Payroll UP.pdf"
CSV_OUT = r"L:\limo\employee_hire_quit_dates.csv"

# Patterns for name, hire, quit dates (customize as needed)
name_pattern = re.compile(r"([A-Z][a-z]+\s+[A-Z][a-z]+)")
hire_pattern = re.compile(r"Hire(?:d| Date)?[:\s]+(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})")
quit_pattern = re.compile(r"Quit(?: Date)?[:\s]+(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})")

def extract_dates():
    results = []
    with pdfplumber.open(PDF_PATH) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                name = None
                hire = None
                quit = None
                name_m = name_pattern.search(line)
                hire_m = hire_pattern.search(line)
                quit_m = quit_pattern.search(line)
                if name_m:
                    name = name_m.group(1)
                if hire_m:
                    hire = hire_m.group(1)
                if quit_m:
                    quit = quit_m.group(1)
                if name and (hire or quit):
                    results.append({"name": name, "hire_date": hire, "quit_date": quit})
    # Write to CSV
    with open(CSV_OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "hire_date", "quit_date"])
        writer.writeheader()
        writer.writerows(results)
    print(f"Extracted {len(results)} employee records to {CSV_OUT}")

if __name__ == "__main__":
    extract_dates()
