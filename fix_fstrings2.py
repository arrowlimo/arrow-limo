import os, sys, ast

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

path = r'l:\limo\desktop_app\charter_form_widget.py'
with open(path, encoding='utf-8') as fh:
    lines = fh.readlines()

def has_fstring_start(s):
    return 'f"' in s or "f'" in s

# Find broken f-string lines: contain f-string start AND end with unescaped {
def is_broken(stripped):
    return (has_fstring_start(stripped) and
            stripped.endswith('{') and
            not stripped.endswith('{{'))

broken_count = 0
new_lines = list(lines)
i = 0
fixed_at = []

while i < len(new_lines):
    line = new_lines[i]
    stripped = line.rstrip('\n').rstrip('\r')
    if is_broken(stripped):
        broken_count += 1
        fixed_at.append(i + 1)
        # Merge subsequent lines until no longer ends with {
        merged = stripped
        j = i + 1
        while merged.rstrip().endswith('{') and not merged.rstrip().endswith('{{'):
            if j >= len(new_lines):
                break
            cont = new_lines[j].rstrip('\n').rstrip('\r').strip()
            merged = merged.rstrip() + cont
            j += 1
        # Replace lines i..j-1 with merged
        new_lines[i] = merged + '\n'
        for k in range(i+1, j):
            new_lines[k] = None
        i = j
    else:
        i += 1

new_lines = [l for l in new_lines if l is not None]

with open(path, 'w', encoding='utf-8') as fh:
    fh.writelines(new_lines)

print(f"Broken f-strings found and fixed: {broken_count}")
print(f"Fixed at original lines: {fixed_at}")

try:
    with open(path, encoding='utf-8') as fh:
        src = fh.read()
    ast.parse(src)
    print("Syntax OK")
except SyntaxError as e:
    print(f"Still broken at line {e.lineno}: {e.msg}")
    # Show context
    with open(path, encoding='utf-8') as fh:
        ls = fh.readlines()
    for ln in range(max(0, e.lineno-3), min(len(ls), e.lineno+2)):
        print(f"  {ln+1}: {repr(ls[ln])}")
