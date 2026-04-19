"""Download T2 Corporation Income Tax Return forms - comprehensive attempt."""

import requests
import os
from pathlib import Path
import time

# Create directory
output_dir = Path(r"L:\limo\tax_forms\T2")
output_dir.mkdir(parents=True, exist_ok=True)

base_url = "https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-{}e.pdf"

# Years 2012-2025 (excluding 2017 - not available on CRA website)
years = list(range(12, 26))  # 12 = 2012, 25 = 2025
years.remove(17)  # 2017 is not available

print("="*70)
print("DOWNLOADING T2 CORPORATION INCOME TAX RETURN FORMS")
print("Years 2012-2025 (2017 excluded - not available on CRA)")
print("="*70)

downloaded = []
failed = []

for year in years:
    year_str = f"{year:02d}"
    full_year = f"20{year_str}"
    url = base_url.format(year_str)
    filename = f"T2-{full_year}.pdf"
    filepath = output_dir / filename
    
    # Skip if already exists and is > 100 KB (valid file)
    if filepath.exists() and filepath.stat().st_size > 100000:
        size_kb = filepath.stat().st_size / 1024
        print(f"{full_year}: Already exists ({size_kb:.1f} KB) - SKIP")
        downloaded.append((full_year, filename, size_kb))
        continue
    
    try:
        print(f"{full_year}: Downloading...", end=" ", flush=True)
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200 and len(response.content) > 100000:
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            size_kb = len(response.content) / 1024
            print(f"OK ({size_kb:.1f} KB)")
            downloaded.append((full_year, filename, size_kb))
            time.sleep(0.5)  # Be nice to the server
        else:
            if response.status_code == 404:
                print(f"NOT AVAILABLE (404)")
            else:
                print(f"FAILED (HTTP {response.status_code}, {len(response.content)} bytes)")
            failed.append((full_year, f"HTTP {response.status_code}"))
            
    except requests.exceptions.Timeout:
        print(f"TIMEOUT")
        failed.append((full_year, "Timeout"))
    except Exception as e:
        print(f"ERROR: {str(e)[:50]}")
        failed.append((full_year, str(e)[:50]))

print("\n" + "="*70)
print("DOWNLOAD SUMMARY")
print("="*70)

if downloaded:
    print(f"\nSuccessfully obtained {len(downloaded)} forms:")
    print("-" * 70)
    for year, filename, size in sorted(downloaded):
        print(f"  {year}: {filename:20s} {size:>8.1f} KB")

if failed:
    print(f"\nNot available ({len(failed)} years):")
    print("-" * 70)
    for year, error in sorted(failed):
        print(f"  {year}: {error}")

print(f"\nFiles location: {output_dir}")
print("="*70)
