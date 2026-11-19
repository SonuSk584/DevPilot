
from pathlib import Path

from app.schemas.coding import Filechange, CodeProposal


MAX_FILE_SIZE = 1_000_000  # 1 MB


def apply_file_change(
    workspace_path: str,
    change: Filechange
) -> dict:
    """
    Apply one proposed file change inside an isolated workspace.
    Supports create, modify, and delete operations.
    """

    root = Path(workspace_path).resolve()

    if not root.exists() or not root.is_dir():
        raise FileNotFoundError("Workspace does not exist")

    relative_path = Path(change.file_path)

    # Reject absolute paths and path traversal.
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError("Invalid file path")

    if not relative_path.parts:
        raise ValueError("File path cannot be empty")

    target = root / relative_path

    # Reject symlinks in the path.
    current = root

    for part in relative_path.parts:
        current = current / part

        if current.is_symlink():
            raise ValueError("Symbolic links are not allowed")

    # Ensure the resolved path stays inside the workspace.
    if not target.resolve().is_relative_to(root):
        raise ValueError("File path is outside the workspace")

    if change.change_type == "create":
        if target.exists():
            raise FileExistsError(
                f"File already exists: {change.file_path}"
            )

        if change.proposed_content is None:
            raise ValueError("Content is required to create a file")

        if len(change.proposed_content.encode("utf-8")) > MAX_FILE_SIZE:
            raise ValueError("Proposed file exceeds the 1 MB limit")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(change.proposed_content, encoding="utf-8")

        return {
            "file_path": change.file_path,
            "operation": "create",
            "status": "success"
        }

    elif change.change_type == "modify":
        if not target.is_file():
            raise FileNotFoundError(
                f"File does not exist: {change.file_path}"
            )

        if change.proposed_content is None:
            raise ValueError("Content is required to modify a file")

        if target.stat().st_size > MAX_FILE_SIZE:
            raise ValueError("Existing file exceeds the 1 MB limit")

        if len(change.proposed_content.encode("utf-8")) > MAX_FILE_SIZE:
            raise ValueError("Proposed file exceeds the 1 MB limit")

        target.write_text(change.proposed_content, encoding="utf-8")

        return {
            "file_path": change.file_path,
            "operation": "modify",
            "status": "success"
        }

    elif change.change_type == "delete":
        if not target.is_file():
            raise FileNotFoundError(
                f"File does not exist: {change.file_path}"
            )

        target.unlink()

        return {
            "file_path": change.file_path,
            "operation": "delete",
            "status": "success"
        }

    else:
        raise ValueError(
            f"Unsupported change type: {change.change_type}"
        )



def _validate_proposal(
    workspace_path: str,
    proposal: CodeProposal
) -> list[Path]:
    """
    Validate every proposed change before modifying the workspace.
    """

    root = Path(workspace_path).resolve()

    if not root.is_dir():
        raise FileNotFoundError("Workspace does not exist")

    validated_paths = []
    seen_paths = set()

    for change in proposal.changes:
        relative_path = Path(change.file_path)

        if (
            not change.file_path.strip()
            or relative_path.is_absolute()
            or ".." in relative_path.parts
        ):
            raise ValueError(f"Invalid file path: {change.file_path}")

        if not relative_path.parts:
            raise ValueError("File path cannot be empty")

        normalized_path = relative_path.as_posix()

        if normalized_path in seen_paths:
            raise ValueError(
                f"Duplicate file change: {normalized_path}"
            )

        seen_paths.add(normalized_path)

        target = root / relative_path

        current = root

        for part in relative_path.parts:
            current = current / part

            if current.is_symlink():
                raise ValueError(
                    f"Symbolic links are not allowed: {change.file_path}"
                )

        if not target.resolve().is_relative_to(root):
            raise ValueError("File path is outside the workspace")

        if change.change_type not in ("create", "modify", "delete"):
            raise ValueError(
                f"Unsupported operation: {change.change_type}"
            )

        if change.change_type == "create":
            if target.exists():
                raise FileExistsError(
                    f"File already exists: {change.file_path}"
                )

            if change.proposed_content is None:
                raise ValueError("Content is required to create a file")

        elif change.change_type in ("modify", "delete"):
            if not target.is_file():
                raise FileNotFoundError(
                    f"File does not exist: {change.file_path}"
                )

            if target.stat().st_size > MAX_FILE_SIZE:
                raise ValueError(
                    f"Existing file exceeds the size limit: {change.file_path}"
                )

            if change.change_type == "modify":
                if change.proposed_content is None:
                    raise ValueError("Content is required to modify a file")

        if change.proposed_content is not None:
            content_size = len(
                change.proposed_content.encode("utf-8")
            )

            if content_size > MAX_FILE_SIZE:
                raise ValueError(
                    f"Proposed file exceeds the size limit: {change.file_path}"
                )

        validated_paths.append(target)

    return validated_paths


def apply_code_proposal(
    workspace_path: str,
    proposal: CodeProposal
) -> list[dict]:
    """
    Apply all changes in a CodeProposal.

    Validates the complete proposal first.
    Attempts rollback if any operation fails.
    """

    # Validate everything before making changes.
    targets = _validate_proposal(workspace_path, proposal)

    # Keep original file contents for rollback.
    snapshots = {}

    results = []

    try:
        for change, target in zip(proposal.changes, targets):

            # Save the original content before applying the change.
            if target.is_file():
                snapshots[target] = target.read_bytes()
            else:
                snapshots[target] = None

            result = apply_file_change(
                workspace_path,
                change
            )

            results.append(result)

        return results

    except Exception:
        # Restore all files to their original state.
        for target, original_content in reversed(
            list(snapshots.items())
        ):
            try:
                if original_content is None:
                    if target.is_file():
                        target.unlink()
                else:
                    target.parent.mkdir(
                        parents=True,
                        exist_ok=True
                    )

                    target.write_bytes(original_content)

            except OSError:
                # Preserve the original operation error.
                pass

        raise
