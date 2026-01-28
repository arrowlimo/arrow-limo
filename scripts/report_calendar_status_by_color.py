#!/usr/bin/env python3
"""
Report calendar sync status by color for a specific year.
Shows charters grouped by sync status with color indicators.
"""

import psycopg2
import os
import argparse
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")


def report_calendar_status(year=2026, color_filter=None, limit=20):
    """
    Generate color-coded calendar sync status report.
    """
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print(f"=" * 90)
    print(f"CALENDAR SYNC STATUS REPORT - {year}")
    print(f"=" * 90)
    
    # Get summary counts
    cur.execute("""
        SELECT calendar_color, COUNT(*) as count
        FROM charters
        WHERE EXTRACT(YEAR FROM charter_date) = %s
        GROUP BY calendar_color
        ORDER BY 
            CASE calendar_color
                WHEN 'green' THEN 1
                WHEN 'blue' THEN 2
                WHEN 'yellow' THEN 3
                WHEN 'red' THEN 4
                WHEN 'gray' THEN 5
                ELSE 6
            END
    """, (year,))
    
    summary = cur.fetchall()
    
    print("\nSUMMARY BY COLOR:")
    print("-" * 90)
    
    color_symbols = {
        'green': '🟢',
        'red': '🔴',
        'yellow': '🟡',
        'blue': '🔵',
        'gray': '⚫',
        None: '⚪'
    }
    
    color_names = {
        'green': 'Synced (Perfect Match)',
        'red': 'Not in Calendar (Missing)',
        'yellow': 'Mismatch (Data Differs)',
        'blue': 'Recently Updated',
        'gray': 'Cancelled',
        None: 'Not Synced'
    }
    
    total = 0
    for color, count in summary:
        symbol = color_symbols.get(color, '⚪')
        name = color_names.get(color, 'Unknown')
        print(f"{symbol} {name:30s} {count:5d} charters")
        total += count
    
    print("-" * 90)
    print(f"{'TOTAL':32s} {total:5d} charters")
    print("=" * 90)
    
    # Detailed listings
    if color_filter:
        colors_to_show = [color_filter]
    else:
        colors_to_show = ['red', 'yellow', 'blue', 'green']
    
    for color in colors_to_show:
        cur.execute("""
            SELECT c.charter_date, c.reserve_number, c.client_name,
                   c.driver_name, c.total_amount_due, c.paid_amount,
                   c.calendar_notes, v.vehicle_name
            FROM charters c
            LEFT JOIN vehicles v ON c.assigned_vehicle_id = v.vehicle_id
            WHERE EXTRACT(YEAR FROM c.charter_date) = %s
              AND calendar_color = %s
            ORDER BY c.charter_date, c.reserve_number
            LIMIT %s
        """, (year, color, limit))
        
        rows = cur.fetchall()
        
        if len(rows) == 0:
            continue
        
        symbol = color_symbols.get(color, '⚪')
        name = color_names.get(color, 'Unknown')
        
        print(f"\n{symbol} {name.upper()}")
        print("-" * 90)
        print(f"{'Date':12s} {'Reserve':8s} {'Client':25s} {'Driver':15s} {'Amount':10s} {'Notes':20s}")
        print("-" * 90)
        
        for row in rows:
            charter_date, reserve_num, client, driver, amount_due, paid, notes, vehicle = row
            
            # Calculate balance
            balance = (amount_due or 0) - (paid or 0)
            
            # Format amount
            if amount_due:
                if balance > 0:
                    amount_str = f"${amount_due:.0f} (${balance:.0f})"
                else:
                    amount_str = f"${amount_due:.0f} PAID"
            else:
                amount_str = "-"
            
            # Truncate long fields
            client_short = (client or 'Unknown')[:24]
            driver_short = (driver or '')[:14]
            notes_short = (notes or '')[:19]
            
            print(f"{charter_date.strftime('%Y-%m-%d'):12s} {reserve_num:8s} {client_short:25s} "
                  f"{driver_short:15s} {amount_str:10s} {notes_short:20s}")
        
        # Show count if limited
        cur.execute("""
            SELECT COUNT(*)
            FROM charters
            WHERE EXTRACT(YEAR FROM charter_date) = %s
              AND calendar_color = %s
        """, (year, color))
        
        total_count = cur.fetchone()[0]
        
        if total_count > limit:
            print(f"\n... and {total_count - limit} more {color} charters (use --limit to see more)")
    
    print("\n" + "=" * 90)
    print("ACTIONS:")
    print("-" * 90)
    print("🔴 Red (Not in Calendar):")
    print("   → Run: python scripts/create_missing_outlook_appointments.py --year 2026 --write")
    print()
    print("🟡 Yellow (Mismatch):")
    print("   → Review manually and update either calendar or database")
    print()
    print("🟢 Green (Synced):")
    print("   → No action needed")
    print("=" * 90)
    
    cur.close()
    conn.close()


def main():
    parser = argparse.ArgumentParser(description='Report calendar sync status by color')
    parser.add_argument('--year', type=int, default=2026,
                        help='Year to report (default: 2026)')
    parser.add_argument('--color', choices=['green', 'red', 'yellow', 'blue', 'gray'],
                        help='Filter to specific color only')
    parser.add_argument('--limit', type=int, default=20,
                        help='Max charters to show per color (default: 20)')
    
    args = parser.parse_args()
    
    report_calendar_status(year=args.year, color_filter=args.color, limit=args.limit)


if __name__ == '__main__':
    main()
