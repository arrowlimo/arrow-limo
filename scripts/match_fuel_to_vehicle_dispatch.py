#!/usr/bin/env python3
"""
Match fuel purchases without a vehicle to likely dispatched vehicles.
- For each fuel receipt with no vehicle_id, find vehicles dispatched on the same day (or within a window, e.g. ±2 days) that do not already have fuel recorded for that period.
- Output a CSV with suggested vehicle assignments for review.

Assumptions:
- Receipts table has: receipt_id, receipt_date, vendor_name, gross_amount, fuel, vehicle_id
- Dispatch log is available as CSV: 'reports/vehicle_dispatch_log.csv' with vehicle_id, dispatch_date
- Fuel log: receipts with fuel > 0 and vehicle_id assigned
"""
import pandas as pd
import os
from datetime import timedelta

RECEIPTS_PATH = r"L:\limo\reports\receipts_import_preview.csv"
DISPATCH_PATH = r"L:\limo\reports\vehicle_dispatch_log.csv"
OUTPUT_PATH = r"L:\limo\reports\fuel_vehicle_suggestions.csv"

# Configurable window for matching (days before/after fuel purchase)
WINDOW_DAYS = 2

def main():
    if not os.path.exists(RECEIPTS_PATH) or not os.path.exists(DISPATCH_PATH):
        print("Missing receipts or dispatch log CSV.")
        return
    receipts = pd.read_csv(RECEIPTS_PATH, parse_dates=['receipt_date'])
    dispatch = pd.read_csv(DISPATCH_PATH, parse_dates=['dispatch_date'])

    # Only fuel purchases with no vehicle assigned
    fuel_no_vehicle = receipts[(receipts['fuel'].notna()) & (receipts['fuel'] > 0) & (receipts['vehicle_id'].isna() | (receipts['vehicle_id'] == ''))]

    # Fuel log: receipts with vehicle assigned
    fuel_with_vehicle = receipts[(receipts['fuel'].notna()) & (receipts['fuel'] > 0) & (receipts['vehicle_id'].notna()) & (receipts['vehicle_id'] != '')]

    # For each fuel_no_vehicle, find dispatched vehicles on same/nearby day without fuel
    suggestions = []
    for idx, row in fuel_no_vehicle.iterrows():
        rdate = row['receipt_date']
        # Vehicles dispatched within window
        window_start = rdate - timedelta(days=WINDOW_DAYS)
        window_end = rdate + timedelta(days=WINDOW_DAYS)
        dispatched = dispatch[(dispatch['dispatch_date'] >= window_start) & (dispatch['dispatch_date'] <= window_end)]
        # Exclude vehicles that already have fuel for that day
        vehicles_with_fuel = set(fuel_with_vehicle[fuel_with_vehicle['receipt_date'] == rdate]['vehicle_id'])
        candidates = [v for v in dispatched['vehicle_id'] if v not in vehicles_with_fuel]
        suggestions.append({
            'receipt_id': row['receipt_id'],
            'receipt_date': rdate,
            'vendor_name': row.get('vendor_name'),
            'fuel_amount': row['fuel'],
            'suggested_vehicles': ';'.join(str(v) for v in candidates) if candidates else '',
            'num_candidates': len(candidates)
        })
    pd.DataFrame(suggestions).to_csv(OUTPUT_PATH, index=False)
    print(f"Suggestions written to {OUTPUT_PATH}")

if __name__ == '__main__':
    main()
