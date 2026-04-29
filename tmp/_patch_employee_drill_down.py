"""Patch remaining 9 E501 lines in employee_drill_down.py."""
import ast
from pathlib import Path

p = Path("desktop_app/employee_drill_down.py")
src = p.read_text(encoding="utf-8")

# ── patch 1: line 965 ─────────────────────────────────────────────────────────
old1 = (
    '                qual_text = """\\n\\n--- VEHICLE QUALIFICATIONS ---\\n'
    "Qualified Types: {', '.join(qualified_types)}\\n"
    "Endorsements: {', '.join(endorsements)}\\n"
    "Notes: {self.qual_notes.toPlainText()}\\n"
    'Updated: {datetime.now().strftime(\'%Y-%m-%d %H:%M\')}"""'
)
new1 = (
    "                qual_text = (\n"
    '                    "\\n\\n--- VEHICLE QUALIFICATIONS ---\\n"\n'
    '                    "Qualified Types: {\', \'.join(qualified_types)}\\n"\n'
    '                    "Endorsements: {\', \'.join(endorsements)}\\n"\n'
    '                    "Notes: {self.qual_notes.toPlainText()}\\n"\n'
    '                    "Updated: {datetime.now().strftime(\'%Y-%m-%d %H:%M\')}"\n'
    "                )"
)
src = src.replace(old1, new1, 1)

# ── patch 2: line 1422 ────────────────────────────────────────────────────────
old2 = (
    "                        f\"\\n\\n--- PROVINCIAL COMPLIANCE ---\\n"
    "{', '.join(compliance_items)}\\n"
    "Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\","
)
new2 = (
    "                        (\n"
    '                            "\\n\\n--- PROVINCIAL COMPLIANCE ---\\n"\n'
    '                            + ", ".join(compliance_items)\n'
    '                            + "\\nUpdated: "\n'
    '                            + datetime.now().strftime(\n'
    '                                "%Y-%m-%d %H:%M"\n'
    "                            )\n"
    "                        ),"
)
src = src.replace(old2, new2, 1)

# ── patch 3: line 1486 ────────────────────────────────────────────────────────
old3 = (
    "                        f\"\\n\\n--- RED DEER BYLAW COMPLIANCE ---\\n"
    "{', '.join(compliance_items)}\\n"
    "Notes: {self.rd_notes.toPlainText()}\\n"
    "Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\","
)
new3 = (
    "                        (\n"
    '                            "\\n\\n--- RED DEER BYLAW COMPLIANCE ---\\n"\n'
    '                            + ", ".join(compliance_items)\n'
    '                            + "\\nNotes: "\n'
    "                            + self.rd_notes.toPlainText()\n"
    '                            + "\\nUpdated: "\n'
    '                            + datetime.now().strftime(\n'
    '                                "%Y-%m-%d %H:%M"\n'
    "                            )\n"
    "                        ),"
)
src = src.replace(old3, new3, 1)

# ── patch 4: line 2027 ────────────────────────────────────────────────────────
old4 = "                            notes = COALESCE(notes, '') || '\\n\\nTermination: ' || %s"
new4 = (
    "                            notes = COALESCE(notes, '') ||\n"
    "                                '\\n\\nTermination: ' || %s"
)
src = src.replace(old4, new4, 1)

# ── patch 5: line 2557 ────────────────────────────────────────────────────────
old5 = "                        AND pay_date >= (SELECT termination_date FROM employees WHERE employee_id = %s) - INTERVAL '52 weeks'"
new5 = (
    "                        AND pay_date >= (\n"
    "                            SELECT termination_date FROM employees\n"
    "                            WHERE employee_id = %s\n"
    "                        ) - INTERVAL '52 weeks'"
)
src = src.replace(old5, new5, 1)

# ── patch 6: line 2643 ────────────────────────────────────────────────────────
old6 = "This Employment Agreement is entered into on {datetime.now().strftime('%B %d, %Y')}"
new6 = (
    "This Employment Agreement is entered into on\n"
    "{datetime.now().strftime('%B %d, %Y')}"
)
src = src.replace(old6, new6, 1)

# ── patch 7: line 2684 ────────────────────────────────────────────────────────
old7 = (
    "            file_path = os.path.join(\n"
    "                forms_dir,\n"
    "                f\"{form_type}_{self.employee_id}_{datetime.now().strftime('%Y%m%d')}.txt\",\n"
    "            )"
)
new7 = (
    "            _ts = datetime.now().strftime(\"%Y%m%d\")\n"
    "            file_path = os.path.join(\n"
    "                forms_dir,\n"
    "                f\"{form_type}_{self.employee_id}_{_ts}.txt\",\n"
    "            )"
)
src = src.replace(old7, new7, 1)

# ── patch 8: line 2696 ────────────────────────────────────────────────────────
old8 = '                "Employment": "other",  # Employment contracts -> "other" category'
new8 = '                "Employment": "other",  # Employment -> "other"'
src = src.replace(old8, new8, 1)

# ── patch 9: line 2791 ────────────────────────────────────────────────────────
old9 = "                        VALUES (%s, %s, 'PAY_ADVANCE', %s, %s, 'Outstanding', NOW())"
new9 = (
    "                        VALUES (\n"
    "                            %s, %s, 'PAY_ADVANCE', %s, %s,\n"
    "                            'Outstanding', NOW())"
)
src = src.replace(old9, new9, 1)

p.write_text(src, encoding="utf-8")

# Verify syntax
try:
    ast.parse(src)
    print("AST_OK")
except SyntaxError as e:
    print(f"AST_FAIL: {e}")
