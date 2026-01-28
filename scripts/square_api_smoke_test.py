#!/usr/bin/env python3
"""
Square API Smoke Test

Reads SQUARE_ACCESS_TOKEN and SQUARE_ENV (sandbox|production) from environment variables
and performs a couple of safe, read-only calls to verify connectivity:
- List a few recent payments (with processing fee totals when present)
- List a few recent payouts (bank deposits)

No secrets are printed. Only aggregated numbers and last-4 IDs are shown.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime

# Optionally load a local .env file if present (decouples from terminal env)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

try:
    # pip install squareup
    from square.client import Square, SquareEnvironment  # type: ignore
except Exception as e:
    print("Missing Square SDK. Install with: pip install squareup")
    print(str(e))
    sys.exit(1)


def mask(s: str, show: int = 4) -> str:
    if not s:
        return ""
    return ("*" * max(0, len(s) - show)) + s[-show:]


def main() -> None:
    access_token = os.getenv("SQUARE_ACCESS_TOKEN")
    environment = os.getenv("SQUARE_ENV", "sandbox").lower()
    if environment not in {"sandbox", "production"}:
        environment = "sandbox"

    if not access_token:
        print("SQUARE_ACCESS_TOKEN not set.")
        print("Set it in your shell OR add it to your .env file and re-run.")
        print("PowerShell example:")
        print("  $env:SQUARE_ACCESS_TOKEN = 'YOUR_TOKEN_HERE'")
        print("  $env:SQUARE_ENV = 'sandbox'  # or 'production'")
        print("")
        print(".env example (file: l:/limo/.env):")
        print("  SQUARE_ENV=production")
        print("  SQUARE_ACCESS_TOKEN=EAAA...YOUR_TOKEN...")
        sys.exit(1)

    # Initialize client (new SDK interface)
    env_enum = SquareEnvironment.SANDBOX if environment == "sandbox" else SquareEnvironment.PRODUCTION
    client = Square(token=access_token, environment=env_enum, timeout=20)

    print(f"Square API smoke test | env={environment} | token_len={len(access_token)}")

    # 0) Quick locations check (fast, validates token)
    try:
        locs = list(client.locations.list(limit=50))
        print(f"Locations: {len(locs)}")
        for loc in locs[:5]:
            d = getattr(loc, "model_dump", lambda: {})()
            print(f"  location {mask(d.get('id',''))} | name={d.get('name','')}")
    except Exception as e:
        print(f"Locations call failed: {e}")

    # 1) List recent payments
    try:
        pager = client.payments.list(limit=5)
        payments = list(pager)
        total_gross = 0
        total_fee = 0
        for p in payments:
            # p is a typed model; convert to dict for convenience
            d = getattr(p, "model_dump", lambda: {})()
            amt = ((d.get("amount_money") or {}).get("amount") or 0) or 0
            total_gross += amt
            for fee in (d.get("processing_fee") or []) or []:
                f = ((fee.get("amount_money") or {}).get("amount") or 0) or 0
                total_fee += f
        print(f"Payments: {len(payments)} | gross={total_gross/100:.2f} | fees={total_fee/100:.2f}")
        # Show masked ids & dates for quick sanity
        for p in payments:
            d = getattr(p, "model_dump", lambda: {})()
            pid = d.get("id", "")
            created_at = d.get("created_at", "") or ""
            print(f"  payment {mask(pid)} at {created_at}")
    except Exception as e:
        print(f"Payments call failed: {e}")

    # 2) List recent payouts (bank deposits)
    try:
        pager = client.payouts.list(limit=5)
        payouts = list(pager)
        total_payout = 0
        for po in payouts:
            d = getattr(po, "model_dump", lambda: {})()
            amt = ((d.get("amount_money") or {}).get("amount") or 0) or 0
            total_payout += amt
        print(f"Payouts: {len(payouts)} | total={total_payout/100:.2f}")
        for po in payouts:
            d = getattr(po, "model_dump", lambda: {})()
            print(f"  payout {mask(d.get('id',''))} on {d.get('arrival_date','')}")
    except Exception as e:
        print(f"Payouts call failed: {e}")


if __name__ == "__main__":
    main()
