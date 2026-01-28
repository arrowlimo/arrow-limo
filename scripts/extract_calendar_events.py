"""
Extract Calendar_0 events from a PST and output JSON
====================================================

Reads the provided PST (Outlook) file, locates a calendar folder named
exactly "Calendar_0" (or closest match containing that suffix), and
exports events with key fields. It also parses reserve numbers from
subject/body and emits split segments for appointments that cross midnight.

Usage:
  python -X utf8 scripts/extract_calendar_events.py "L:\\limo\\outlook backup\\info@arrowlimo.ca.pst" \
      --output reports/calendar_0_events.json
"""

import argparse
import json
import os
import re
from datetime import datetime, timedelta

import pythoncom
import win32com.client


RESERVE_RE = re.compile(r"\b(\d{6})\b")


def ensure_store(namespace, pst_path: str):
    try:
        namespace.AddStore(pst_path)
    except Exception:
        # already added
        pass


def find_calendar_0(namespace):
    # Prefer Stores API
    stores = getattr(namespace, "Stores", None)
    candidates = []
    if stores is not None:
        for store in stores:
            try:
                root = store.GetRootFolder()
                stack = [root]
                while stack:
                    f = stack.pop()
                    try:
                        name = f.Name or ""
                        if name == "Calendar_0" or ("calendar_0" in name.lower()):
                            return f
                        # Some installs label as Calendar
                        if name.lower() == "calendar_0":
                            return f
                        for sub in f.Folders:
                            stack.append(sub)
                    except Exception:
                        continue
            except Exception:
                continue
    # Fallback naive scan
    for root in namespace.Folders:
        stack = [root]
        while stack:
            f = stack.pop()
            try:
                name = f.Name or ""
                if name == "Calendar_0" or ("calendar_0" in name.lower()):
                    return f
                for sub in f.Folders:
                    stack.append(sub)
            except Exception:
                continue
    return None


def split_midnight_segments(start: datetime, end: datetime):
    if not start or not end or end <= start:
        return [(start.isoformat() if start else None, end.isoformat() if end else None)]
    # If same day, single segment
    if start.date() == end.date():
        return [(start.isoformat(), end.isoformat())]
    # Split at midnight boundaries across days
    segments = []
    cur_start = start
    while cur_start.date() < end.date():
        next_midnight = (cur_start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
        segments.append((cur_start.isoformat(), next_midnight.isoformat()))
        cur_start = next_midnight
    segments.append((cur_start.isoformat(), end.isoformat()))
    return segments


def parse_reserve_numbers(text: str):
    if not text:
        return []
    return list(sorted(set(RESERVE_RE.findall(text))))


def main():
    ap = argparse.ArgumentParser(description="Extract Calendar_0 events from PST")
    ap.add_argument("pst", help="Path to PST file")
    ap.add_argument("--output", default="reports/calendar_0_events.json", help="Output JSON path")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    pythoncom.CoInitialize()
    try:
        outlook = win32com.client.gencache.EnsureDispatch("Outlook.Application")
        ns = outlook.GetNamespace("MAPI")
        ensure_store(ns, args.pst)
        cal = find_calendar_0(ns)
        if not cal:
            print("Calendar_0 not found in PST")
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump({"calendar": "Calendar_0", "events": []}, f, indent=2)
            return

        # Collect items
        events = []
        items = getattr(cal, "Items", None)
        count = 0
        if items is not None:
            count = items.Count
            for i in range(1, count + 1):
                try:
                    it = items.Item(i)
                    # Some PSTs report a different Class; accept items with Start/End fields
                    subject = str(getattr(it, "Subject", "") or "")
                    location = str(getattr(it, "Location", "") or "")
                    body = str(getattr(it, "Body", "") or "")
                    start = getattr(it, "Start", None)
                    end = getattr(it, "End", None)
                    start_dt = None
                    end_dt = None
                    try:
                        # Start/End are COM datetimes; convert via Python
                        start_dt = datetime.fromtimestamp(float(start)) if isinstance(start, (int, float)) else start
                        end_dt = datetime.fromtimestamp(float(end)) if isinstance(end, (int, float)) else end
                    except Exception:
                        start_dt = start
                        end_dt = end

                    reserve_numbers = sorted(
                        set(parse_reserve_numbers(subject) + parse_reserve_numbers(body))
                    )
                    segments = split_midnight_segments(start_dt, end_dt)
                    events.append(
                        {
                            "subject": subject,
                            "location": location,
                            "body": body,
                            "start": start_dt.isoformat() if start_dt else None,
                            "end": end_dt.isoformat() if end_dt else None,
                            "is_all_day": bool(getattr(it, "AllDayEvent", False)),
                            "categories": str(getattr(it, "Categories", "") or ""),
                            "reserve_numbers": reserve_numbers,
                            "segments": [{"start": s, "end": e} for s, e in segments],
                        }
                    )
                except Exception:
                    continue

        with open(args.output, "w", encoding="utf-8") as f:
            json.dump({"calendar": "Calendar_0", "count": len(events), "events": events}, f, indent=2)
        print(f"Extracted {len(events)} events from Calendar_0 (items={count})")

    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


if __name__ == "__main__":
    main()
