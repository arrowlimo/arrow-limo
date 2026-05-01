import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

SUMMARY_PATH = Path(r"l:\limo\tmp\widget_constructor_smoke_results.json")
PROBE_PATH = r"l:\limo\tmp\widget_constructor_probe.py"
PYTHON_PATH = r"l:\limo\.venv\Scripts\python.exe"
TIMEOUT_SEC = 120

TARGETS = [
    ("desktop_app.charter_form_widget", "CharterFormWidget"),
    ("desktop_app.dashboard_classes", "FleetManagementWidget"),
    ("desktop_app.dashboard_classes", "FinancialDashboardWidget"),
]


def run_probe(module_name: str, class_name: str) -> dict:
    started = time.time()
    try:
        proc = subprocess.run(
            [PYTHON_PATH, PROBE_PATH, module_name, class_name],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEC,
            env=os.environ.copy(),
        )
        raw = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        match = re.search(r"^(PASS|FAIL)\|([^|]+)\|([^\n]+)$", raw, flags=re.MULTILINE)
        if match:
            status, detail = match.group(1), match.group(3).strip()
            return {
                "status": status,
                "strategy": detail if status == "PASS" else None,
                "error": None if status == "PASS" else detail,
                "exit_code": proc.returncode,
                "duration_sec": round(time.time() - started, 2),
                "raw_excerpt": raw[-1000:],
            }

        return {
            "status": "FAIL",
            "strategy": None,
            "error": f"No PASS/FAIL marker. Exit={proc.returncode}",
            "exit_code": proc.returncode,
            "duration_sec": round(time.time() - started, 2),
            "raw_excerpt": raw[-1000:],
        }
    except subprocess.TimeoutExpired as exc:
        raw = (((exc.stdout or "") + "\n" + (exc.stderr or "")).strip())
        return {
            "status": "FAIL",
            "strategy": None,
            "error": f"timeout>{TIMEOUT_SEC}s",
            "exit_code": None,
            "duration_sec": round(time.time() - started, 2),
            "raw_excerpt": raw[-1000:],
        }


def main() -> int:
    if not SUMMARY_PATH.exists():
        raise FileNotFoundError(f"Missing summary JSON: {SUMMARY_PATH}")

    data = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    index = {(row["module"], row["class_name"]): row for row in data.get("results", [])}

    for module_name, class_name in TARGETS:
        result = run_probe(module_name, class_name)
        row = index.get((module_name, class_name), {
            "module": module_name,
            "class_name": class_name,
        })
        row.update(result)
        row["revalidated_at"] = datetime.now().isoformat(timespec="seconds")
        index[(module_name, class_name)] = row
        print(f"RECHECK|{module_name}:{class_name}|{row['status']}|{row.get('strategy') or row.get('error')}")

    data["results"] = sorted(index.values(), key=lambda r: (r["module"], r["class_name"]))
    data["generated_at"] = datetime.now().isoformat(timespec="seconds")
    data["source"] = "consolidated + direct revalidation for timeout-prone targets"
    data["pass"] = sum(1 for row in data["results"] if row.get("status") == "PASS")
    data["fail"] = sum(1 for row in data["results"] if row.get("status") != "PASS")

    SUMMARY_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"UPDATED|{SUMMARY_PATH}")
    print(f"SUMMARY|{data['pass']}/{data['total']} PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
