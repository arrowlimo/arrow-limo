path = r'l:\limo\desktop_app\charter_form_widget.py'
with open(path, encoding='utf-8') as fh:
    lines = fh.readlines()

broken_indices = []
for i, line in enumerate(lines):
    stripped = line.rstrip()
    has_fstring = ('f"' in stripped or "f'" in stripped)
    ends_open = stripped.endswith('{') and not stripped.endswith('{{')
    if has_fstring and ends_open:
        broken_indices.append(i)
        nxt = lines[i+1].rstrip() if i+1 < len(lines) else ''
        print(f"Line {i+1}: {repr(stripped)}")
        print(f"Line {i+2}: {repr(nxt)}")
        print()

print(f"Total broken f-strings found: {len(broken_indices)}")

# Now fix: join line i and line i+1 by merging the expression
new_lines = list(lines)
# Process in reverse so indices stay valid
for i in reversed(broken_indices):
    line1 = lines[i]
    line2 = lines[i+1]
    indent = len(line1) - len(line1.lstrip())
    # line1 ends with "{\n", line2 has "    expr}\n"
    # We want: line1_stripped + expr_stripped + "\n"
    merged = line1.rstrip() + line2.strip() + "\n"
    new_lines[i] = merged
    new_lines[i+1] = None  # mark for removal

new_lines = [l for l in new_lines if l is not None]

with open(path, 'w', encoding='utf-8') as fh:
    fh.writelines(new_lines)

print("File written.")

import ast
try:
    with open(path, encoding='utf-8') as fh:
        src = fh.read()
    ast.parse(src)
    print("Syntax OK")
except SyntaxError as e:
    print(f"Still broken at line {e.lineno}: {e.msg}")
