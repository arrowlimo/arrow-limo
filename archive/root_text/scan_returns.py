import ast
import sys

def get_signature(node):
    args = []
    # posonlyargs
    for arg in node.args.posonlyargs:
        args.append(arg.arg)
    # args
    for arg in node.args.args:
        args.append(arg.arg)
    if node.args.vararg:
        args.append(f"*{node.args.vararg.arg}")
    # kwonlyargs
    for arg in node.args.kwonlyargs:
        args.append(arg.arg)
    if node.args.kwarg:
        args.append(f"**{node.args.kwarg.arg}")
    
    return f"{node.name}({', '.join(args)})"

def scan_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=filepath)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is None:
                signature = get_signature(node)
                print(f"Line {node.lineno}: {signature}")

if __name__ == "__main__":
    scan_file(sys.argv[1])
