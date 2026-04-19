"""Download T2 Corporation Income Tax Return forms for all available years."""

import requests
import os
from pathlib import Path

# Create directory
output_dir = Path(r"L:\limo\tax_forms\T2")
output_dir.mkdir(parents=True, exist_ok=True)

base_url = "https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-fill-{}e.pdf"

# Try years from 2012 to 2025 (based on your data coverage)
years = list(range(12, 26))  # 12 = 2012, 25 = 2025

print("="*70)
print("DOWNLOADING T2 CORPORATION INCOME TAX RETURN FORMS")
print("="*70)

downloaded = []
failed = []

for year in years:
    year_str = f"{year:02d}"
    url = base_url.format(year_str)
    filename = f"T2-20{year_str}.pdf"
    filepath = output_dir / filename
    
    try:
        print(f"\nDownloading 20{year_str}...", end=" ")
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            size_kb = len(response.content) / 1024
            print(f"OK ({size_kb:.1f} KB)")
            downloaded.append((f"20{year_str}", filename, size_kb))
        else:
            print(f"FAILED (HTTP {response.status_code})")
            failed.append((f"20{year_str}", response.status_code))
            
    except Exception as e:
        print(f"ERROR: {e}")
        failed.append((f"20{year_str}", str(e)))

print("\n" + "="*70)
print("DOWNLOAD SUMMARY")
print("="*70)

if downloaded:
    print(f"\nSuccessfully downloaded {len(downloaded)} forms:")
    print("-" * 70)
    for year, filename, size in downloaded:
        print(f"  {year}: {filename:20s} ({size:>6.1f} KB)")

if failed:
    print(f"\nFailed to download {len(failed)} forms:")
    print("-" * 70)
    for year, error in failed:
        print(f"  {year}: {error}")

print(f"\nFiles saved to: {output_dir}")
print("="*70)
