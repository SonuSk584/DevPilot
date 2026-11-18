
from pathlib import Path
import os


IGNORED_DIRECTORIES = {
    ".git",
    "venv",
    ".venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
}

IGNORED_FILES = {
    ".env",
    ".env.local",
    "id_rsa",
    "id_ed25519",
}


def scan_repository(root_path: str) -> list[str]:
    root = Path(root_path).resolve()

    if not root.exists():
        raise FileNotFoundError("Repository path does not exist")

    if not root.is_dir():
        raise NotADirectoryError("Provided path is not a directory")

    discovered_files = []

    for current_root, directories, files in os.walk(
        root,
        followlinks=False
    ):
        # Ignore unnecessary directories
        directories[:] = [
            directory
            for directory in directories
            if directory not in IGNORED_DIRECTORIES
            and not (Path(current_root) / directory).is_symlink()
        ]

        for filename in files:
            file_path = Path(current_root) / filename

            # Ignore sensitive files and symbolic links
            if filename in IGNORED_FILES or file_path.is_symlink():
                continue

            # Ignore private key and certificate files
            if file_path.suffix.lower() in {".pem", ".key", ".p12"}:
                continue

            # Ignore very large files
            if file_path.stat().st_size > 1_000_000:
                continue

            relative_path = file_path.relative_to(root)
            discovered_files.append(relative_path.as_posix())

    return sorted(discovered_files)
