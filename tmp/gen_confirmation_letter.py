from __future__ import annotations
import os, sys
from pathlib import Path

ROOT = Path(r"l:\limo")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tmp.generate_best_2012_run_charter_pdf import load_charter_payload
from modern_backend.app.services.pdf_generator import generate_confirmation_letter_pdf

def main():
    charter_id = 4945
    reserve = "005996"
    payload = load_charter_payload(charter_id)
    pdf_bytes = generate_confirmation_letter_pdf(payload)
    out = ROOT / "tmp" / f"confirmation_letter_{reserve}_v2.pdf"
    out.write_bytes(pdf_bytes)
    print(f"output_pdf={out}")

if __name__ == "__main__":
    main()
