
import ast


def chunk_python_file(file_path: str, content: str) -> dict:
    """
    Divide a Python file into meaningful AST-based code chunks.

    Each top-level function, class, or module-level statement
    becomes one chunk. Class methods remain inside their class
    chunk, preventing duplicate method chunks.
    """

    try:
        tree = ast.parse(content)
    except SyntaxError as error:
        return {
            "file_path": file_path,
            "status": "failed",
            "error": str(error),
            "chunks": [],
        }

    lines = content.splitlines()
    chunks = []

    for node in tree.body:

        # Include decorators in the extracted source.
        start_line = node.lineno

        if hasattr(node, "decorator_list") and node.decorator_list:
            start_line = min(
                start_line,
                *(decorator.lineno for decorator in node.decorator_list)
            )

        end_line = node.end_lineno

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            chunk_type = "function"
            symbol_name = node.name
            methods = []

        elif isinstance(node, ast.ClassDef):
            chunk_type = "class"
            symbol_name = node.name
            methods = [
                child.name
                for child in node.body
                if isinstance(
                    child,
                    (ast.FunctionDef, ast.AsyncFunctionDef)
                )
            ]

        else:
            chunk_type = "module_statement"
            symbol_name = None
            methods = []

        code = "\n".join(lines[start_line - 1:end_line])

        chunks.append({
            "chunk_id": f"{file_path}:{start_line}-{end_line}",
            "file_path": file_path,
            "chunk_type": chunk_type,
            "symbol_name": symbol_name,
            "methods": methods,
            "line_start": start_line,
            "line_end": end_line,
            "content": code,
        })

    return {
        "file_path": file_path,
        "status": "success",
        "chunks": chunks,
    }
