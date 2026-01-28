#!/usr/bin/env python3
"""
Find receipts that share the same receipt_date and gross_amount with similar vendor names.
Writes CSV: reports/similar_vendor_amount_date.csv
This is read-only (no DB changes).
"""
import csv
import os
import re
from difflib import SequenceMatcher
import psycopg2

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'reports', 'similar_vendor_amount_date.csv')
SIM_THRESHOLD = 0.80  # similarity ratio threshold

def normalize_vendor(name: str) -> str:
    if not name:
        return ''
    s = name.lower().strip()
    # remove store/location codes like '#12345'
    s = re.sub(r"#\d+", "", s)
    # remove bracket markers for uncertain vendors
    s = s.replace('[', '').replace(']', '')
    # collapse whitespace and remove punctuation commonly seen in vendor names
    s = re.sub(r"[\-\.&'\"]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute(
    """
    SELECT receipt_id, receipt_date, gross_amount, vendor_name,
           description, source_reference, source_file, source_system,
           canonical_vendor
    FROM receipts
    WHERE gross_amount IS NOT NULL
    ORDER BY receipt_date, gross_amount, receipt_id
    """
)
rows = cur.fetchall()
cur.close(); conn.close()

# Group by (date, amount)
from collections import defaultdict
by_key = defaultdict(list)
for rid, rdate, amt, vname, desc, sref, sfile, ssys, cvendor in rows:
    by_key[(rdate, float(amt))].append((rid, vname, desc, sref, sfile, ssys, cvendor))

pairs = []
for (rdate, amt), items in by_key.items():
    if len(items) < 2:
        continue
    # compute pairs
    n = len(items)
    for i in range(n):
        rid1, v1, d1, ref1, file1, sys1, cv1 = items[i]
        v1n = normalize_vendor(cv1 or v1)
        for j in range(i+1, n):
            rid2, v2, d2, ref2, file2, sys2, cv2 = items[j]
            v2n = normalize_vendor(cv2 or v2)
            # similarity ratio
            sim = SequenceMatcher(None, v1n, v2n).ratio()
            if sim >= SIM_THRESHOLD:
                pairs.append([
                    rdate, amt,
                    rid1, v1 or '', d1 or '', ref1 or '',
                    rid2, v2 or '', d2 or '', ref2 or '',
                    round(sim, 3)
                ])

os.makedirs(os.path.join(os.path.dirname(__file__), '..', 'reports'), exist_ok=True)
with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow([
        'receipt_date', 'gross_amount',
        'receipt_id_1', 'vendor_1', 'description_1', 'source_ref_1',
        'receipt_id_2', 'vendor_2', 'description_2', 'source_ref_2',
        'similarity'
    ])
    for row in pairs:
        w.writerow(row)

print(f"Similar vendor duplicates: {len(pairs)}")
print(f"Output: {OUTPUT_PATH}")
