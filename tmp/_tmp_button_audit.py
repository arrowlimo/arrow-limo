import ast
from pathlib import Path

root = Path('desktop_app')
issues = []

for p in root.rglob('*.py'):
    sp = str(p).replace('\\', '/').lower()
    if 'deployment_package/' in sp or '/build/' in sp or '/staging/' in sp:
        continue

    try:
        src = p.read_text(encoding='utf-8')
    except Exception as e:
        issues.append((str(p), 0, f'read_error: {e}'))
        continue

    try:
        tree = ast.parse(src)
    except Exception as e:
        issues.append((str(p), 0, f'parse_error: {e}'))
        continue

    class_methods = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
            class_methods[node.name] = methods

    class ConnectVisitor(ast.NodeVisitor):
        def __init__(self):
            self.class_stack = []

        def visit_ClassDef(self, node):
            self.class_stack.append(node.name)
            self.generic_visit(node)
            self.class_stack.pop()

        def visit_Call(self, node):
            try:
                if isinstance(node.func, ast.Attribute) and node.func.attr == 'connect' and node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name) and arg.value.id == 'self':
                        if self.class_stack:
                            cls = self.class_stack[-1]
                            if arg.attr not in class_methods.get(cls, set()):
                                issues.append((str(p), node.lineno, f'missing_handler: {cls}.self.{arg.attr}'))
            except Exception:
                pass
            self.generic_visit(node)

    ConnectVisitor().visit(tree)

out = Path('tmp/button_handler_audit.txt')
out.parent.mkdir(parents=True, exist_ok=True)
with out.open('w', encoding='utf-8') as f:
    if not issues:
        f.write('OK: no missing self.* connect handlers found\n')
    else:
        for file_path, line_no, msg in sorted(issues):
            f.write(f'{file_path}:{line_no}: {msg}\n')

print(f'Wrote {out} with {len(issues)} issue(s)')
