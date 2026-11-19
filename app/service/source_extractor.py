
from pathlib import Path


MAX_FILE_SIZE = 1_000_000  # 1 MB
SUPPORTED_EXTENSIONS = {".py"}


def extract_source_code(
    root_path: str,
    file_paths: list[str]
) -> list[dict[str, str]]:

    root = Path(root_path).resolve()

    if not root.exists() or not root.is_dir():
        raise ValueError("Invalid repository directory")

    extracted_files = []

    for relative_path in file_paths:

        relative = Path(relative_path)

        # Reject absolute paths and path traversal
        if relative.is_absolute() or ".." in relative.parts:
            continue

        file_path = root / relative

        # Only extract Python files
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        # Ignore symbolic links
        if file_path.is_symlink():
            continue

        try:
            resolved_path = file_path.resolve(strict=True)

            # Ensure the file is inside the repository
            if not resolved_path.is_relative_to(root):
                continue

            if not resolved_path.is_file():
                continue

            # Ignore oversized files
            if resolved_path.stat().st_size > MAX_FILE_SIZE:
                continue

            # Read source code
            content = resolved_path.read_text(encoding="utf-8")

            extracted_files.append({
                "path": relative.as_posix(),
                "content": content
            })

        except (OSError, UnicodeDecodeError):
            continue

    return extracted_files
