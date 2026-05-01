import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

PY = r"l:\\limo\\.venv\\Scripts\\python.exe"
PROBE = r"l:\\limo\\tmp\\widget_constructor_probe.py"
OUT = Path(r"l:\\limo\\tmp\\widget_constructor_smoke_results.json")
TIMEOUT = 45

TARGETS = [
    ("desktop_app.mega_menu_widget", "MegaMenuWidget"),
    ("desktop_app.report_explorer_widget", "ReportExplorerWidget"),
    ("desktop_app.employee_management_widget", "EmployeeManagementWidget"),
    ("desktop_app.vehicle_management_widget", "VehicleManagementWidget"),
    ("desktop_app.dispatch_management_widget", "DispatchManagementWidget"),
    ("desktop_app.document_management_widget", "DocumentManagementWidget"),
    ("desktop_app.charter_form_widget", "CharterFormWidget"),
    ("desktop_app.manage_banking_widget", "ManageBankingWidget"),
    ("desktop_app.manage_cash_box_widget", "ManageCashBoxWidget"),
    ("desktop_app.report_management_widget", "ReportManagementWidget"),
    ("desktop_app.roe_form_widget", "ROEFormWidget"),
    ("desktop_app.fleet_management_widget", "FleetManagementWidget"),
    ("desktop_app.financial_dashboard_widget", "FinancialDashboardWidget"),
]


def run_target(module_name: str, class_name: str) -> dict:
    start = time.time()
    cmd = [PY, PROBE, module_name, class_name]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=os.environ.copy(),
        )
        raw = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        match = re.search(r"^(PASS|FAIL)\|([^|]+)\|([^\n]+)$", raw, flags=re.MULTILINE)

        if match:
            status, target, detail = match.group(1), match.group(2), match.group(3).strip()
            strategy = detail if status == "PASS" else None
            error_text = detail if status == "FAIL" else None
        else:
            status = "FAIL"
            target = f"{module_name}:{class_name}"
            strategy = None
            error_text = f"No PASS/FAIL marker. Exit={proc.returncode}"

        return {
            "module": module_name,
            "class_name": class_name,
            "target": target,
            "status": status,
            "strategy": strategy,
            "error": error_text,
            "exit_code": proc.returncode,
            "duration_sec": round(time.time() - start, 2),
            "raw_excerpt": raw[-1200:],
        }
    except subprocess.TimeoutExpired as exc:
        raw = (((exc.stdout or "") + "\n" + (exc.stderr or "")).strip())
        return {
            "module": module_name,
            "class_name": class_name,
            "target": f"{module_name}:{class_name}",
            "status": "FAIL",
            "strategy": None,
            "error": f"timeout>{TIMEOUT}s",
            "exit_code": None,
            "duration_sec": round(time.time() - start, 2),
            "raw_excerpt": raw[-1200:],
        }


def main() -> int:
    results = []
    for module_name, class_name in TARGETS:
        row = run_target(module_name, class_name)
        results.append(row)
        print(
            f"TARGET|{row['target']}|{row['status']}|"
            f"{row['strategy'] or row['error']}"
        )

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "workspace": r"l:\\limo",
        "probe_script": PROBE,
        "timeout_sec_per_target": TIMEOUT,
        "total": len(results),
        "pass": sum(1 for r in results if r["status"] == "PASS"),
        "fail": sum(1 for r in results if r["status"] != "PASS"),
        "results": results,
    }

    OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"WROTE|{OUT}")
    print(f"SUMMARY|{summary['pass']}/{summary['total']} PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
