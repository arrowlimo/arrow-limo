import ast
import re
import textwrap
from pathlib import Path

SRC = Path('desktop_app/receipt_search_match_widget.py')
MAX = 79


def parse_ok(lines):
    try:
        ast.parse(''.join(lines))
        return True
    except SyntaxError:
        return False


def wrap_comment_line(line):
    m = re.match(r'^(\s*)#\s?(.*)\n?$', line)
    if not m:
        return None
    indent, text = m.groups()
    width = MAX - len(indent) - 2
    if width < 20:
        return None
    wrapped = textwrap.wrap(text, width=width)
    if len(wrapped) <= 1:
        return None
    out = ''.join(f"{indent}# {part}\n" for part in wrapped)
    return out


def wrap_single_line_docstring(line):
    m = re.match(r'^(\s*)([rRuU]{0,2})(\"\"\"|\'\'\')(.*)(\3)\s*\n?$', line)
    if not m:
        return None
    indent, prefix, quote, content, _ = m.groups()
    if len(line.rstrip('\n')) <= MAX:
        return None
    width = MAX - len(indent)
    parts = textwrap.wrap(content, width=max(20, width - 3))
    if len(parts) <= 1:
        return None
    out_lines = [f"{indent}{prefix}{quote}{parts[0]}\n"]
    out_lines.extend(f"{indent}{p}\n" for p in parts[1:])
    out_lines.append(f"{indent}{quote}\n")
    return ''.join(out_lines)


def split_standalone_string_line(line):
    # Matches lines that are ONLY a (possibly prefixed) string literal plus optional suffix , ) ]
    # Examples:
    #   "...",
    #   f"..."),
    #   '...')
    m = re.match(r'^(\s*)([fFrRbBuU]{0,2})([\"\'])(.*)(\3)(\s*[,\)\]]?\s*)\n?$', line)
    if not m:
        return None
    indent, prefix, quote, content, _, suffix = m.groups()
    if len(line.rstrip('\n')) <= MAX:
        return None
    if not content.strip():
        return None

    # Try split at a space close to target width
    room = MAX - len(indent) - len(prefix) - 2
    if room < 20:
        return None
    split_at = content.rfind(' ', 0, room)
    if split_at <= 0:
        split_at = content.find(' ', room)
    if split_at <= 0 or split_at >= len(content) - 1:
        return None

    left = content[:split_at + 1]
    right = content[split_at + 1:]

    l1 = f"{indent}{prefix}{quote}{left}{quote}\n"
    l2 = f"{indent}{prefix}{quote}{right}{quote}{suffix}\n"

    if len(l1.rstrip('\n')) > MAX or len(l2.rstrip('\n')) > MAX:
        # One more attempt by splitting earlier
        split_at2 = content.rfind(' ', 0, max(20, room - 10))
        if split_at2 <= 0 or split_at2 >= len(content) - 1:
            return None
        left = content[:split_at2 + 1]
        right = content[split_at2 + 1:]
        l1 = f"{indent}{prefix}{quote}{left}{quote}\n"
        l2 = f"{indent}{prefix}{quote}{right}{quote}{suffix}\n"
        if len(l1.rstrip('\n')) > MAX or len(l2.rstrip('\n')) > MAX:
            return None

    return l1 + l2


def split_from_import_line(line):
    m = re.match(r'^(\s*from\s+\S+\s+import\s+)(.+)\n?$', line)
    if not m:
        return None
    if len(line.rstrip('\n')) <= MAX:
        return None
    head, names = m.groups()
    parts = [p.strip() for p in names.split(',')]
    if len(parts) < 2:
        return None
    indent = ' ' * (len(head) - len(head.lstrip()))
    out = f"{head}(\n"
    out += ''.join(f"{indent}    {p},\n" for p in parts)
    out += f"{indent})\n"
    return out


lines = SRC.read_text(encoding='utf-8').splitlines(keepends=True)
if not parse_ok(lines):
    raise SystemExit('Source is not parseable before edits; aborting')

changed = 0
i = 0
while i < len(lines):
    line = lines[i]
    if len(line.rstrip('\n')) <= MAX:
        i += 1
        continue

    candidates = [
        split_from_import_line(line),
        wrap_comment_line(line),
        wrap_single_line_docstring(line),
        split_standalone_string_line(line),
    ]

    applied = False
    for cand in candidates:
        if not cand:
            continue
        repl = cand.splitlines(keepends=True)
        trial = lines[:i] + repl + lines[i + 1:]
        if parse_ok(trial):
            lines = trial
            changed += 1
            i += len(repl)
            applied = True
            break

    if not applied:
        i += 1

SRC.write_text(''.join(lines), encoding='utf-8')

# Final checks
ok = parse_ok(lines)
print(f'Changed lines: {changed}')
print(f'Syntax OK: {ok}')

violations = [
    (idx + 1, len(l.rstrip('\n')))
    for idx, l in enumerate(lines)
    if len(l.rstrip('\n')) > MAX
]
print(f'Remaining long lines: {len(violations)}')
