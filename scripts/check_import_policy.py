#!/usr/bin/env python3
"""Preflight guard for import policy.

Usage:
    python -X utf8 scripts/check_import_policy.py --source-system quickbooks --action import

- Reads config/import_policy.json.
- If QuickBooks import is attempted while disabled, exits non-zero.
- Scanning/analysis is allowed even when import is disabled.
"""
import argparse
import json
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(ROOT_DIR, "config", "import_policy.json")


def load_policy():
    if not os.path.exists(CONFIG_PATH):
        return {"quickbooks_import_allowed": True}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-system", required=True, help="e.g., quickbooks, bank, email, manual")
    ap.add_argument("--action", required=True, choices=["import", "scan", "analyze"], help="intent: import/scan/analyze")
    args = ap.parse_args()

    policy = load_policy()
    src = (args.source_system or "").strip().lower()
    act = (args.action or "").strip().lower()

    if src == "quickbooks" and act == "import":
        allowed = bool(policy.get("quickbooks_import_allowed", True))
        if not allowed:
            print("❌ Import blocked: QuickBooks entries are prohibited by policy.")
            print(f"Policy file: {CONFIG_PATH}")
            print("Scanning/analyzing is permitted; importing is not.")
            sys.exit(2)

    print("✅ Policy check passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
