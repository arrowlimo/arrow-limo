"""
Fix all remaining missing \"\"\")\n using indentation-based heuristic.
If we're in a triple-quoted string (from cur.execute) and encounter a line
with indentation <= the opener's indentation, it's code - insert \"\"\") before it.
"""
import ast

SRC = 'desktop_app/charter_form_widget.py'

with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

insertions = []

in_triple = False
triple_open_line = -1
triple_open_indent_len = 0

i = 0
while i < len(lines):
    line = lines[i]
    stripped = line.strip()
    
    # Count triple-quote occurrences
    tq_count = line.count('"""')
    
    if not in_triple:
        if tq_count % 2 == 1:  # opens a triple string
            # Only track cur.execute(""" patterns
            if 'cur.execute(' in line or 'cur.execute(f' in line:
                in_triple = True
                triple_open_line = i
                triple_open_indent_len = len(line) - len(line.lstrip())
    else:
        # We're inside a triple string
        if tq_count % 2 == 1:  # closes the triple string
            in_triple = False
        elif stripped:  # non-empty, no triple-quote
            # Check indentation: if this line has indentation <= opener, it's code
            curr_indent = len(line) - len(line.lstrip())
            if curr_indent <= triple_open_indent_len:
                # This is Python code, not SQL
                ind_str = ' ' * triple_open_indent_len
                planned = (i, f'{ind_str}""")\n')
                if planned not in insertions:
                    print(f"Missing \"\"\"): before line {i+1} (opened at {triple_open_line+1})")
                    print(f"  indent={curr_indent} <= opener_indent={triple_open_indent_len}: {stripped[:60]}")
                    insertions.append(planned)
                in_triple = False
    i += 1

print(f"\nTotal insertions: {len(insertions)}")

for idx, text in sorted(insertions, key=lambda x: x[0], reverse=True):
    lines.insert(idx, text)
    print(f"Inserted at line {idx+1}: {text.rstrip()[:60]}")

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
