"""
Restore the incorrectly deleted \"\"\")\n lines.
These were `cur.execute(\"\"\"...\"\"\")\n` closings that got removed.
Find all unclosed triple-quote SQL blocks and restore them.
"""
import ast

SRC = 'desktop_app/charter_form_widget.py'

with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find all triple-quoted string openings with cur.execute that aren't closed
# Strategy: track triple-quote state and find where it goes unterminated

insertions = []  # list of (line_index_after_which_to_insert, text_to_insert)

in_triple_double = False
triple_start_line = -1
triple_indent = ""

for i, line in enumerate(lines):
    stripped = line.rstrip()
    
    # Count triple-double-quote occurrences
    count = stripped.count('"""')
    
    if not in_triple_double:
        if count % 2 == 1:  # odd number opens a triple string
            in_triple_double = True
            triple_start_line = i
            # Get the indentation of the cur.execute line
            triple_indent = ' ' * (len(line) - len(line.lstrip()))
    else:
        if count % 2 == 1:  # odd number closes a triple string
            in_triple_double = False
            triple_start_line = -1
        elif count % 2 == 0 and count > 0:
            pass  # even number: opened and closed in same line, state unchanged
        # Check for pattern: next line starts with something that can't be in a string
        # (i.e., code statement)
        next_stripped = stripped.lstrip()
        if (not in_triple_double and count == 0):
            # Still in triple but no quotes - check if this line looks like code
            is_code_line = (
                next_stripped.startswith('table_exists')
                or next_stripped.startswith('row_exists')
                or next_stripped.startswith('cur.execute')
                or next_stripped.startswith('conn.')
                or next_stripped.startswith('result')
                or next_stripped.startswith('rows')
                or (next_stripped.startswith(('if ', 'for ', 'with ', 'try:', 
                                               'except', 'self.', 'return',
                                               'max_val', 'new_'))
                    and triple_start_line >= 0
                    and i - triple_start_line > 2)
            )
            if is_code_line:
                # Triple string was never closed - insert """) before this line
                call_indent = triple_indent
                print(f"MISSING \"\"\"): before line {i+1} (triple opened at {triple_start_line+1})")
                print(f"  Code line: {next_stripped[:60]}")
                insertions.append((i, f'{call_indent}""")\n'))
                in_triple_double = False

print(f"\nPlanned insertions: {len(insertions)}")

# Apply insertions in reverse order to preserve indices
for idx, text in reversed(insertions):
    lines.insert(idx, text)
    print(f"Inserted \"\"\")\") before line {idx+1}")

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
