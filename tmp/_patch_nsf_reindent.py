"""Fix over-indented OR clauses in nsf_pair_manager_widget.py"""
import ast
from pathlib import Path

p = Path("desktop_app/nsf_pair_manager_widget.py")
src = p.read_text(encoding="utf-8")

# The lines have 72 spaces prefix; we want 36 (matching lines 220-222)
old_lines = [
    "                                                                        OR bt.description ILIKE '%%CANCEL%%'",
    "                                                                        OR bt.description ILIKE '%%REVERS%%'",
    "                                                                        OR bt.description ILIKE '%%REVERSE%%'",
    "                                                                        OR bt.description ILIKE '%%E-TRANSFER%%'",
    "                                                                        OR bt.description ILIKE '%%ETRANSFER%%'",
]
new_lines = [
    "                                    OR bt.description ILIKE '%%CANCEL%%'",
    "                                    OR bt.description ILIKE '%%REVERS%%'",
    "                                    OR bt.description ILIKE '%%REVERSE%%'",
    "                                    OR bt.description ILIKE '%%E-TRANSFER%%'",
    "                                    OR bt.description ILIKE '%%ETRANSFER%%'",
]

lines = src.splitlines(keepends=True)
found = 0
result = []
i = 0
while i < len(lines):
    stripped = lines[i].rstrip("\n").rstrip("\r")
    if stripped == old_lines[0] and i + 4 < len(lines):
        # Check all 5 lines
        match = all(
            lines[i+j].rstrip("\n").rstrip("\r") == old_lines[j]
            for j in range(5)
        )
        if match:
            for j in range(5):
                result.append(new_lines[j] + "\n")
            i += 5
            found += 1
            continue
    result.append(lines[i])
    i += 1

print(f"Found and replaced: {found}")
new_src = "".join(result)
p.write_text(new_src, encoding="utf-8")
try:
    ast.parse(new_src)
    print("AST_OK")
except SyntaxError as e:
    print(f"AST_FAIL: {e}")
