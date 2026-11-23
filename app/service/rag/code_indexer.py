
import ast
from pathlib import Path


def index_python_file(file_path: str, content: str) -> dict:
    """
    Extract structural information from a Python source file.
    """

    try:
        tree = ast.parse(content)
    except SyntaxError as error:
        return {
            "file_path": file_path,
            "status": "failed",
            "error": str(error),
            "imports": [],
            "classes": [],
            "functions": [],
        }

    imports = []
    classes = []
    functions = []

    for node in ast.walk(tree):

        # Extract imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""

            imports.append({
                "module": module,
                "names": [alias.name for alias in node.names],
                "level": node.level,
            })

        # Extract classes
        elif isinstance(node, ast.ClassDef):
            classes.append({
                "name": node.name,
                "line_start": node.lineno,
                "line_end": node.end_lineno,
                "methods": [
                    child.name
                    for child in node.body
                    if isinstance(
                        child,
                        (ast.FunctionDef, ast.AsyncFunctionDef)
                    )
                ],
                "docstring": ast.get_docstring(node),
            })

        # Extract functions
        elif isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            functions.append({
                "name": node.name,
                "line_start": node.lineno,
                "line_end": node.end_lineno,
                "is_async": isinstance(
                    node,
                    ast.AsyncFunctionDef
                ),
                "docstring": ast.get_docstring(node),
            })

    return {
        "file_path": file_path,
        "status": "success",
        "imports": imports,
        "classes": classes,
        "functions": functions,
    }
