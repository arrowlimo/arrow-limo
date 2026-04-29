import ast
import re
from pathlib import Path

SRC = Path('desktop_app/t2_data_entry_widget.py')
MAX = 79


def parse_ok(lines):
    try:
        ast.parse(''.join(lines))
        return True
    except SyntaxError:
        return False


def split_at_space(text, limit):
    if len(text) <= limit:
        return None
    idx = text.rfind(' ', 0, limit)
    if idx <= 0:
        idx = text.find(' ', limit)
    if idx <= 0 or idx >= len(text) - 1:
        return None
    return text[:idx], text[idx + 1:]


def cand_comment(line):
    m = re.match(r'^(\s*)#\s?(.*)\n?$', line)
    if not m:
        return None
    indent, body = m.groups()
    if len(line.rstrip('\n')) <= MAX:
        return None
    limit = MAX - len(indent) - 2
    sp = split_at_space(body, limit)
    if not sp:
        return None
    a, b = sp
    return [f"{indent}# {a}\n", f"{indent}# {b}\n"]


def cand_doc_open(line):
    # Starts a multi-line docstring and line is too long.
    m = re.match(r'^(\s*)([rRuU]{0,2})("""|\'\'\')(.*)\n?$', line)
    if not m:
        return None
    indent, prefix, q, body = m.groups()
    if len(line.rstrip('\n')) <= MAX:
        return None
    # ignore single-line docstrings with closing on same line
    if body.endswith(q):
        return None
    limit = MAX - len(indent) - len(prefix) - len(q)
    sp = split_at_space(body, limit)
    if not sp:
        return None
    a, b = sp
    return [f"{indent}{prefix}{q}{a}\n", f"{indent}{b}\n"]


def cand_doc_mid(line):
    # Middle line inside docstring (plain text), split by space.
    if len(line.rstrip('\n')) <= MAX:
        return None
    if '"' in line or "'" in line:
        return None
    m = re.match(r'^(\s*)(\S.*)\n?$', line)
    if not m:
        return None
    indent, body = m.groups()
    # Skip obvious code lines
    if any(tok in body for tok in ['=', '(', ')', ':', '[', ']', '{', '}']):
        return None
    limit = MAX - len(indent)
    sp = split_at_space(body, limit)
    if not sp:
        return None
    a, b = sp
    return [f"{indent}{a}\n", f"{indent}{b}\n"]


def cand_string_literal(line):
    # standalone quoted literal line with optional prefix and trailing comma/parens
    m = re.match(r'^(\s*)([fFrRuUbB]{0,2})([\"\'])(.*)(\3)(\s*[,\)]?\s*)\n?$', line)
    if not m:
        return None
    indent, prefix, q, body, _, suffix = m.groups()
    if len(line.rstrip('\n')) <= MAX:
        return None
    limit = MAX - len(indent) - len(prefix) - 2
    sp = split_at_space(body, limit)
    if not sp:
        return None
    a, b = sp
    return [
        f"{indent}{prefix}{q}{a}{q}\n",
        f"{indent}{prefix}{q}{b}{q}{suffix}\n",
    ]


def cand_sql_or_text(line):
    # Generic split for long plain text lines (e.g., SQL inside triple quotes)
    s = line.rstrip('\n')
    if len(s) <= MAX:
        return None
    if '"' in s or "'" in s:
        return None
    indent = len(s) - len(s.lstrip())
    body = s[indent:]
    # If looks like code, skip
    if body.startswith(('def ', 'class ', 'if ', 'for ', 'while ', 'return ')):
        return None
    # Prefer split at comma first
    idx = body.rfind(',', 0, MAX - indent)
    if idx > 10 and idx < len(body) - 2:
        left = body[:idx + 1]
        right = body[idx + 2:] if body[idx + 1] == ' ' else body[idx + 1:]
        return [f"{' ' * indent}{left}\n", f"{' ' * indent}{right}\n"]
    sp = split_at_space(body, MAX - indent)
    if not sp:
        return None
    a, b = sp
    return [f"{' ' * indent}{a}\n", f"{' ' * indent}{b}\n"]


def cand_between(line):
    s = line.rstrip('\n')
    if len(s) <= MAX:
        return None
    if ' BETWEEN ' not in s:
        return None
    idx = s.find(' BETWEEN ')
    if idx <= 0:
        return None
    indent = ' ' * (len(s) - len(s.lstrip()))
    left = s[:idx]
    right = s[idx + 1:]  # keep BETWEEN at start of continuation
    return [left + '\n', indent + right.lstrip() + '\n']


lines = SRC.read_text(encoding='utf-8').splitlines(keepends=True)
if not parse_ok(lines):
    raise SystemExit('Source not parseable at start')

changed = 0
max_passes = 2000
for _ in range(max_passes):
    made_change = False
    for i, line in enumerate(lines):
        if len(line.rstrip('\n')) <= MAX:
            continue
        candidates = [
            cand_between(line),
            cand_comment(line),
            cand_doc_open(line),
            cand_string_literal(line),
            cand_sql_or_text(line),
            cand_doc_mid(line),
        ]
        for cand in candidates:
            if not cand:
                continue
            trial = lines[:i] + cand + lines[i + 1:]
            if parse_ok(trial):
                lines = trial
                changed += 1
                made_change = True
                break
        if made_change:
            break
    if not made_change:
        break

SRC.write_text(''.join(lines), encoding='utf-8')
print(f'CHANGED={changed}')
print(f'SYNTAX_OK={parse_ok(lines)}')
remaining = sum(1 for l in lines if len(l.rstrip('\n')) > MAX)
print(f'REMAINING_RAW_LONG_LINES={remaining}')
