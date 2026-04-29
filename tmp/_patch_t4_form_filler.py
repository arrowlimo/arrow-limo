"""Patch remaining E501 lines in t4_official_form_filler.py by line number."""
from pathlib import Path

p = Path("desktop_app/t4_official_form_filler.py")
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)


def mk(s):
    return s + "\n"


fixes = {
    253: mk(
        "                    f\"{b}.EmployersName[0].Slip1EmployersName[0]\": (\n"
        "                        self._employer_display_name()\n"
        "                    ),"
    ),
    255: mk(
        "                    f\"{b}.EmployersAccount[0].Slip1Box54[0]\": (\n"
        "                        self.EMPLOYER_PAYROLL_ACCOUNT\n"
        "                    ),"
    ),
    263: mk(
        "                    f\"{b}.Box14[0].Slip1Box14[0]\": (\n"
        "                        f\"{float(t4_vals.get('box14', 0)):.2f}\"\n"
        "                    ),"
    ),
    264: mk(
        "                    f\"{b}.Box22[0].Slip1Box22[0]\": (\n"
        "                        f\"{float(t4_vals.get('box22', 0)):.2f}\"\n"
        "                    ),"
    ),
    265: mk(
        "                    f\"{b}.Box16[0].Slip1Box16[0]\": (\n"
        "                        f\"{float(t4_vals.get('box16', 0)):.2f}\"\n"
        "                    ),"
    ),
    266: mk(
        "                    f\"{b}.Box18[0].Slip1Box18[0]\": (\n"
        "                        f\"{float(t4_vals.get('box18', 0)):.2f}\"\n"
        "                    ),"
    ),
    267: mk(
        "                    f\"{b}.Box24[0].Slip1Box24[0]\": (\n"
        "                        f\"{float(t4_vals.get('box24', 0)):.2f}\"\n"
        "                    ),"
    ),
    268: mk(
        "                    f\"{b}.Box26[0].Slip1Box26[0]\": (\n"
        "                        f\"{float(t4_vals.get('box26', 0)):.2f}\"\n"
        "                    ),"
    ),
    270: mk(
        "                    f\"{b}.Employee[0].FirstName[0].Slip1FirstName[0]\": (\n"
        "                        first_name\n"
        "                    ),"
    ),
    288: mk(
        "                    f\"{b}.Box28[0].EI_CheckBox[0].Slip1EI[0]\": (\n"
        "                        ei_checkbox_value\n"
        "                    ),"
    ),
    394: mk(
        "                    f\"{b}.EmployersName[0].Slip1EmployersName[0]\": (\n"
        "                        self._employer_display_name()\n"
        "                    ),"
    ),
    396: mk(
        "                    f\"{b}.EmployersAccount[0].Slip1Box54[0]\": (\n"
        "                        self.EMPLOYER_PAYROLL_ACCOUNT\n"
        "                    ),"
    ),
    404: mk(
        "                    f\"{b}.Box14[0].Slip1Box14[0]\": (\n"
        "                        f\"{float(t4_vals.get('box14', 0)):.2f}\"\n"
        "                    ),"
    ),
    405: mk(
        "                    f\"{b}.Box22[0].Slip1Box22[0]\": (\n"
        "                        f\"{float(t4_vals.get('box22', 0)):.2f}\"\n"
        "                    ),"
    ),
    406: mk(
        "                    f\"{b}.Box16[0].Slip1Box16[0]\": (\n"
        "                        f\"{float(t4_vals.get('box16', 0)):.2f}\"\n"
        "                    ),"
    ),
    407: mk(
        "                    f\"{b}.Box18[0].Slip1Box18[0]\": (\n"
        "                        f\"{float(t4_vals.get('box18', 0)):.2f}\"\n"
        "                    ),"
    ),
    408: mk(
        "                    f\"{b}.Box24[0].Slip1Box24[0]\": (\n"
        "                        f\"{float(t4_vals.get('box24', 0)):.2f}\"\n"
        "                    ),"
    ),
    409: mk(
        "                    f\"{b}.Box26[0].Slip1Box26[0]\": (\n"
        "                        f\"{float(t4_vals.get('box26', 0)):.2f}\"\n"
        "                    ),"
    ),
    411: mk(
        "                    f\"{b}.Employee[0].FirstName[0].Slip1FirstName[0]\": (\n"
        "                        first_name\n"
        "                    ),"
    ),
    429: mk(
        "                    f\"{b}.Box28[0].EI_CheckBox[0].Slip1EI[0]\": (\n"
        "                        ei_checkbox_value\n"
        "                    ),"
    ),
}

for n in sorted(fixes.keys(), reverse=True):
    lines[n - 1] = fixes[n]

p.write_text("".join(lines), encoding="utf-8")
print(f"Patched {len(fixes)} lines.")
