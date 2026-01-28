#!/usr/bin/env python3
import sys, os
from dotenv import load_dotenv

try:
    import pandas as pd
except Exception:
    print('pandas not installed')
    sys.exit(1)

def preview(path):
    print(f"\n=== {path} ===")
    try:
        xls = pd.ExcelFile(path)
    except Exception as e:
        print('Open error:', e)
        return
    for sheet in xls.sheet_names:
        try:
            df = xls.parse(sheet_name=sheet, header=None)
            print(f"-- Sheet: {sheet} shape={df.shape}")
            print(df.head(10).to_string(index=False))
        except Exception as e:
            print(f"  sheet read error {sheet}: {e}")

if __name__ == '__main__':
    for p in sys.argv[1:]:
        if os.path.exists(p):
            preview(p)
        else:
            print('Missing:', p)
