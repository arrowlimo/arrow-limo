"""Fix client_notes_input broken pattern and more."""
import ast

SRC = 'desktop_app/charter_form_widget.py'

with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and fix client_notes broken pattern
# Current (approx lines 7030-7033):
#   client_notes = (
#       self.client_notes_input.toPlainText().strip()
#                                              "client_notes_i"
#                                              "nput") else ""
# Correct:
#   client_notes = (
#       self.client_notes_input.toPlainText().strip()
#       if hasattr(self, 'client_notes_input') else "")
for i in range(len(lines)):
    if ("client_notes = (\n" == lines[i].lstrip()
            and i + 3 < len(lines)):
        l1 = lines[i+1].strip()
        l2 = lines[i+2].strip()
        l3 = lines[i+3].strip()
        if ('self.client_notes_input.toPlainText().strip()' in l1
                and '"client_notes_i"' in l2
                and 'nput") else ""' in l3):
            indent = len(lines[i]) - len(lines[i].lstrip())
            ind_str = ' ' * indent
            lines[i] = f'{ind_str}client_notes = (\n'
            lines[i+1] = f'{ind_str}    self.client_notes_input.toPlainText().strip()\n'
            lines[i+2] = f"{ind_str}    if hasattr(self, 'client_notes_input') else \"\")\n"
            lines[i+3] = '\n'
            print(f"Fixed client_notes at lines {i+1}-{i+4}")
            break

with open(SRC, 'w', encoding='utf-8') as f:
    f.writelines(lines)

# Check
with open(SRC, 'r', encoding='utf-8') as f:
    src = f.read()
try:
    ast.parse(src)
    print("SYNTAX OK!")
except SyntaxError as e:
    src_lines = src.splitlines()
    print(f"SyntaxError at line {e.lineno}: {e.msg}")
    for j in range(max(0, e.lineno - 5), min(len(src_lines), e.lineno + 5)):
        marker = " >>> " if j == e.lineno - 1 else "     "
        print(f"{marker}{j+1}: {src_lines[j][:100]}")
