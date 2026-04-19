import json
from pathlib import Path
import requests

ENV_PATH = Path(r"L:\limo\.env")
PAYMENT_ID = "dKL1X1ituPOJ2gQp5MKEqzMF"


def load_token(path: Path) -> str:
    token = None
    if not path.exists():
        raise FileNotFoundError(f"Missing env file: {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == "SQUARE_ACCESS_TOKEN":
            token = v.strip()
            break
    if not token:
        raise RuntimeError("SQUARE_ACCESS_TOKEN not found in .env")
    return token


def square_get(url: str, token: str, params=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Square-Version": "2024-01-18",
        "Content-Type": "application/json",
    }
    r = requests.get(url, headers=headers, params=params, timeout=30)
    return r.status_code, r.text


def main():
    token = load_token(ENV_PATH)

    print("Checking payment by ID from receipt URL...")
    s, t = square_get(f"https://connect.squareup.com/v2/payments/{PAYMENT_ID}", token)
    print("payment status:", s)
    if s == 200:
        data = json.loads(t)
        p = data.get("payment", {})
        amt = (((p.get("amount_money") or {}).get("amount") or 0) / 100)
        print("payment.id:", p.get("id"))
        print("payment.created_at:", p.get("created_at"))
        print("payment.status:", p.get("status"))
        print("payment.total_money:", amt)
        print("payment.reference_id:", p.get("reference_id"))
        print("payment.receipt_number:", p.get("receipt_number"))
        print("payment.receipt_url:", p.get("receipt_url"))
        print("payment.card_brand:", ((p.get("card_details") or {}).get("card") or {}).get("card_brand"))
        print("payment.last4:", ((p.get("card_details") or {}).get("card") or {}).get("last_4"))
    else:
        print(t[:1000])

    print("\nSearching disputes (all pages, up to 200 records)...")
    cursor = None
    seen = 0
    matched = []
    for _ in range(20):
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        s, t = square_get("https://connect.squareup.com/v2/disputes", token, params=params)
        print("disputes page status:", s)
        if s != 200:
            print(t[:1200])
            return
        data = json.loads(t)
        ds = data.get("disputes", [])
        seen += len(ds)
        for d in ds:
            amt = (((d.get("amount_money") or {}).get("amount") or 0) / 100)
            reason = d.get("reason")
            state = d.get("state")
            payment_id = d.get("payment_id")
            if payment_id == PAYMENT_ID or abs(amt - 808.50) < 0.001:
                matched.append({
                    "id": d.get("id"),
                    "payment_id": payment_id,
                    "amount": amt,
                    "state": state,
                    "reason": reason,
                    "created_at": d.get("created_at"),
                    "due_at": d.get("due_at"),
                    "card_brand": d.get("card_brand"),
                })
        cursor = data.get("cursor")
        if not cursor:
            break

    print("total disputes scanned:", seen)
    print("matches by payment_id or amount 808.50:", len(matched))
    for m in matched:
        print(m)


if __name__ == "__main__":
    main()
