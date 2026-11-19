
from pathlib import Path

from app.service.repository_scanner import scan_repository
from app.service.source_extractor import extract_source_code


IMPORTANT_FILES = {
    "README.md",
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "Pipfile",
    "Pipfile.lock",
}

MAX_CONTEXT_CHARS = 100_000

def read_project_file(root: Path, relative_path: str) -> str | None:
    relative = Path(relative_path)

    if relative.is_absolute() or ".." in relative.parts:
        return None

    file_path = root / relative

    try:
        if file_path.is_symlink():
            return None

        resolved_path = file_path.resolve(strict=True)

        if not resolved_path.is_relative_to(root):
            return None

        if not resolved_path.is_file():
            return None

        if resolved_path.stat().st_size > 1_000_000:
            return None

        return resolved_path.read_text(encoding="utf-8")

    except (OSError, UnicodeDecodeError):
        return None



def build_repository_context(root_path: str) -> str:

    root = Path(root_path).resolve()

    # Step 1: Discover repository files
    discovered_files = scan_repository(str(root))

    # Step 2: Select Python files and important project files
    selected_files = [
        file_path
        for file_path in discovered_files
        if Path(file_path).suffix.lower() == ".py"
        or Path(file_path).name in IMPORTANT_FILES
    ]

    # Step 3: Extract Python source files
    extracted_files = extract_source_code(
        str(root),
        selected_files
    )

    # Step 4: Read important non-Python files
    extracted_paths = {
        file["path"] for file in extracted_files
    }

    for relative_path in selected_files:

        if relative_path in extracted_paths:
            continue

        content = read_project_file(root, relative_path)
        if content is None:
            continue

        extracted_files.append({
        "path": relative_path,
        "content": content
    })


    # Step 5: Build formatted context
    context_parts = []
    total_chars = 0

    for file in extracted_files:

        file_section = (
            f"\n{'=' * 60}\n"
            f"FILE: {file['path']}\n"
            f"{'=' * 60}\n"
            f"{file['content']}\n"
        )

        if total_chars + len(file_section) > MAX_CONTEXT_CHARS:
            break

        context_parts.append(file_section)
        total_chars += len(file_section)

    return "\n".join(context_parts)
