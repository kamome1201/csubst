import ast
with open("./csubst/__init__.py") as f:
    tree = ast.parse(f.read())
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        if getattr(node.targets[0], "id", None) == "__version__":
            print(node.value.s)
            break
