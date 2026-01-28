#!/usr/bin/env python3
"""
Check status of T2 form downloads across all years (2012-2024)
"""
import os
from pathlib import Path

# CRA form URLs from generate_t2_return.py
CRA_FORM_URLS = {
    2012: {
        't2': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-12e.pdf',
        'schedule_125': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-12e.pdf'
    },
    2013: {
        't2': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-13e.pdf',
        'schedule_125': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-13e.pdf'
    },
    2014: {
        't2': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-14e.pdf',
        'schedule_125': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-14e.pdf'
    },
    2015: {
        't2': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-15e.pdf',
        'schedule_125': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-15e.pdf'
    },
    2016: {
        't2': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-16e.pdf',
        'schedule_125': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-16e.pdf'
    },
    2017: {
        't2': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-17e.pdf',
        'schedule_125': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-17e.pdf'
    },
    2018: {
        't2': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-18e.pdf',
        'schedule_125': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-18e.pdf'
    },
    2019: {
        't2': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-19e.pdf',
        'schedule_125': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-19e.pdf'
    },
    2020: {
        't2': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-20e.pdf',
        'schedule_125': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-20e.pdf'
    },
    2021: {
        't2': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-21e.pdf',
        'schedule_125': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-21e.pdf'
    },
    2022: {
        't2': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-22e.pdf',
        'schedule_125': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-22e.pdf'
    },
    2023: {
        't2': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-23e.pdf',
        'schedule_125': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-23e.pdf'
    },
    2024: {
        't2': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2/t2-24e.pdf',
        'schedule_125': 'https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/t2sch125/t2sch125-24e.pdf'
    }
}

def main():
    cache_dir = Path('L:/limo/pdf/cra_forms')
    
    print("\n" + "="*70)
    print("T2 CORPORATE TAX RETURN FORMS - DOWNLOAD STATUS")
    print("="*70)
    print(f"\nCache directory: {cache_dir}")
    print(f"Cache exists: {cache_dir.exists()}")
    
    if cache_dir.exists():
        cached_files = list(cache_dir.glob('*.pdf'))
        print(f"Cached PDFs: {len(cached_files)}")
        for file in sorted(cached_files):
            size_kb = file.stat().st_size / 1024
            print(f"  - {file.name} ({size_kb:.1f} KB)")
    else:
        print("Cache directory not found")
    
    print("\n" + "="*70)
    print("AVAILABLE T2 FORMS BY YEAR (2012-2024)")
    print("="*70)
    print(f"{'Year':<8} {'Downloaded':<12} {'T2 URL':<60}")
    print("-"*70)
    
    for year in sorted(CRA_FORM_URLS.keys()):
        t2_url = CRA_FORM_URLS[year]['t2']
        filename = f"t2_{year}e.pdf"
        filepath = cache_dir / filename
        downloaded = "[OK] YES" if filepath.exists() else "[FAIL] NO"
        
        print(f"{year:<8} {downloaded:<12} {t2_url}")
    
    print("\n" + "="*70)
    print("DOWNLOAD INSTRUCTIONS")
    print("="*70)
    print("\nTo download T2 forms for any year:")
    print("  python scripts/generate_t2_return.py --year YYYY --download")
    print("\nExamples:")
    print("  python scripts/generate_t2_return.py --year 2013 --download")
    print("  python scripts/generate_t2_return.py --year 2020 --download")
    print("\nTo generate T2 return with financial data:")
    print("  python scripts/generate_t2_return.py --year YYYY --download")
    print("\nNote: Currently only 2012 has been downloaded.")

if __name__ == "__main__":
    main()
