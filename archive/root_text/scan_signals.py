import ast
import os
import re

def check_signals(directory):
    pattern = re.compile(r"(\.bak|backup|\.CLEAN_)")
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py') and not pattern.search(file) and not pattern.search(root):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        tree = ast.parse(f.read(), filename=path)
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            methods = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
                            for subnode in ast.walk(node):
                                if (isinstance(subnode, ast.Call) and 
                                    isinstance(subnode.func, ast.Attribute) and 
                                    subnode.func.attr == 'connect'):
                                    
                                    if len(subnode.args) > 0:
                                        arg = subnode.args[0]
                                        if (isinstance(arg, ast.Attribute) and 
                                            isinstance(arg.value, ast.Name) and 
                                            arg.value.id == 'self'):
                                            method_name = arg.attr
                                            if method_name not in methods:
                                                # Check if inherited - for simplicity, we flag for manual review if not in current class body
                                                print(f"{path}:{subnode.lineno}: Signal connect to self.{method_name} - not found in class definition.")
                except Exception as e:
                    pass

check_signals('L:/limo/desktop_app')
