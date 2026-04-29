"""Patch 4 remaining E501 lines in dashboards_phase13 and print_export_helper."""
import ast
from pathlib import Path

patches = {
    "desktop_app/dashboards_phase13.py": [
        (
            "                    WHERE e.is_chauffeur = true AND e.employment_status = 'active'",
            "                    WHERE e.is_chauffeur = true\n"
            "                        AND e.employment_status = 'active'",
        ),
    ],
    "desktop_app/print_export_helper.py": [
        (
            "                f\"Orientation: {'Landscape' if use_landscape else 'Portrait'}\\n\"",
            "                f\"Orientation: \"\n"
            "                f\"{'Landscape' if use_landscape else 'Portrait'}\\n\"",
        ),
        (
            "            f\"🔄 Auto-Detect ({num_cols} columns → {'Landscape' if num_cols > 7 else 'Portrait'})\",",
            "            (\n"
            "                f\"🔄 Auto-Detect ({num_cols} columns → \"\n"
            "                f\"{'Landscape' if num_cols > 7 else 'Portrait'})\"\n"
            "            ),",
        ),
        (
            "                    f\"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\"",
            "                    \"Generated: \"\n"
            "                    + datetime.now().strftime('%Y-%m-%d %H:%M:%S')",
        ),
    ],
}

for path, fixes in patches.items():
    p = Path(path)
    src = p.read_text(encoding="utf-8")
    for old, new in fixes:
        if old not in src:
            print(f"WARN not found in {path}: {old[:70]!r}")
        src = src.replace(old, new, 1)
    p.write_text(src, encoding="utf-8")
    try:
        ast.parse(src)
        print(f"AST_OK  {path}")
    except SyntaxError as e:
        print(f"AST_FAIL {path}: {e}")
