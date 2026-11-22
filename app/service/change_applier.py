
from pathlib import Path
from git import Repo, InvalidGitRepositoryError
import shutil
import uuid


def validate_file_path(
    repository_path: str,
    relative_path: str
) -> Path:
    """
    Resolve a relative file path and ensure it stays
    inside the original repository without following symlinks.
    """

    root = Path(repository_path).resolve()

    if not root.is_dir():
        raise FileNotFoundError(
            "Original repository does not exist."
        )

    relative = Path(relative_path)

    if relative.is_absolute():
        raise ValueError(
            "Absolute file paths are not allowed."
        )

    # Reject symbolic links in any path component.
    current = root

    for part in relative.parts:
        current = current / part

        if current.is_symlink():
            raise ValueError(
                "Symbolic links are not allowed in approved file paths."
            )

    target = (root / relative).resolve()

    if not target.is_relative_to(root):
        raise ValueError(
            "File path escapes the original repository."
        )

    if target == root:
        raise ValueError(
            "Repository root cannot be used as a file path."
        )

    return target


def check_repository_conflict(
    repository_path: str,
    original_head_commit: str
) -> bool:
    """
    Return True if the original repository has changed
    since the workspace was created.

    Checks both the Git commit and working-tree changes.
    """

    try:
        repo = Repo(
            repository_path,
            search_parent_directories=False
        )
    except InvalidGitRepositoryError:
        raise ValueError(
            "Original repository is not a valid Git repository."
        )

    current_commit = repo.head.commit.hexsha

    if current_commit != original_head_commit:
        return True

    if repo.is_dirty(untracked_files=True):
        return True

    return False



def backup_files(
    repository_path: str,
    relative_paths: list[str],
    backup_root: str
) -> dict:
    """
    Back up existing files before applying approved changes.

    Preserves relative directory structure.
    Records missing files so they can be restored
    or removed during rollback.
    """

    repository = Path(repository_path).resolve()
    backup_id = uuid.uuid4().hex
    backup_dir = Path(backup_root).resolve() / backup_id

    backup_dir.mkdir(parents=True, exist_ok=False)

    backed_up = []
    missing_files = []

    try:
        for relative_path in relative_paths:
            source = validate_file_path(
                str(repository),
                relative_path
            )

            if not source.exists():
                missing_files.append(relative_path)
                continue

            if not source.is_file():
                raise ValueError(
                    f"Only regular files can be backed up: {relative_path}"
                )

            destination = backup_dir / relative_path
            destination.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            shutil.copy2(source, destination)
            backed_up.append(relative_path)

        return {
            "backup_id": backup_id,
            "backup_path": str(backup_dir),
            "backed_up_files": backed_up,
            "missing_files": missing_files,
            "status": "success"
        }

    except Exception:
        shutil.rmtree(backup_dir, ignore_errors=True)
        raise


def rollback_files(
    repository_path: str,
    backup_result: dict
) -> dict:
    """
    Restore original files from a backup.

    Files that did not exist before application are removed.
    """

    repository = Path(repository_path).resolve()
    backup_dir = Path(backup_result["backup_path"]).resolve()

    restored_files = []
    removed_files = []

    for relative_path in backup_result["backed_up_files"]:
        destination = validate_file_path(
            str(repository),
            relative_path
        )

        backup_file = backup_dir / relative_path

        if not backup_file.is_file():
            raise FileNotFoundError(
                f"Backup file missing: {relative_path}"
            )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        shutil.copy2(backup_file, destination)
        restored_files.append(relative_path)

    for relative_path in backup_result["missing_files"]:
        destination = validate_file_path(
            str(repository),
            relative_path
        )

        if destination.is_file() or destination.is_symlink():
            destination.unlink()
            removed_files.append(relative_path)

    return {
        "status": "success",
        "restored_files": restored_files,
        "removed_files": removed_files
    }



def apply_approved_changes(
    repository_path: str,
    workspace_path: str,
    diff_result: dict,
    original_head_commit: str,
    backup_root: str
) -> dict:
    """
    Apply human-approved workspace changes to the original repository.

    Supports added, modified, and deleted files.
    Renamed files are rejected until the diff manager preserves
    both the old and new paths.
    """

    repository = Path(repository_path).resolve()
    workspace = Path(workspace_path).resolve()

    if not workspace.is_dir():
        raise FileNotFoundError("Workspace does not exist.")

    if diff_result.get("status") != "success":
        raise ValueError("Cannot apply an unsuccessful diff.")

    files = diff_result.get("files", [])

    if not files:
        return {
            "status": "success",
            "message": "No changes to apply.",
            "applied_files": []
        }

    # Never overwrite a repository that changed after workspace creation.
    if check_repository_conflict(
        str(repository),
        original_head_commit
    ):
        raise RuntimeError(
            "Original repository changed since workspace creation."
        )

    supported_types = {"added", "modified", "deleted"}

    # Validate every file before making any changes.
    relative_paths = []

    for item in files:
        relative_path = item["file_path"]
        change_type = item["change_type"]

        if change_type not in supported_types:
            raise ValueError(
                f"Unsupported change type: {change_type}"
            )

        destination = validate_file_path(
            str(repository),
            relative_path
        )

        if change_type in {"modified", "deleted"}:
            if not destination.is_file():
                raise FileNotFoundError(
                    f"Original file does not exist: {relative_path}"
                )

        if change_type == "added" and destination.exists():
            raise FileExistsError(
                f"Cannot add file because it already exists: {relative_path}"
            )

        if change_type in {"added", "modified"}:
            source = validate_file_path(
                str(workspace),
                relative_path
            )

            if not source.is_file():
                raise FileNotFoundError(
                    f"Workspace file does not exist: {relative_path}"
                )

        relative_paths.append(relative_path)

    # Back up all affected original paths before applying anything.
    backup_result = backup_files(
        str(repository),
        relative_paths,
        backup_root
    )

    applied_files = []

    try:
        for item in files:
            relative_path = item["file_path"]
            change_type = item["change_type"]

            destination = validate_file_path(
                str(repository),
                relative_path
            )

            if change_type == "deleted":
                destination.unlink()

            else:
                source = validate_file_path(
                    str(workspace),
                    relative_path
                )

                destination.parent.mkdir(
                    parents=True,
                    exist_ok=True
                )

                shutil.copy2(source, destination)

            applied_files.append(relative_path)

        return {
            "status": "success",
            "message": "Approved changes applied successfully.",
            "applied_files": applied_files,
            "backup": backup_result
        }

    except Exception as error:
        rollback_result = rollback_files(
            str(repository),
            backup_result
        )

        raise RuntimeError(
            f"Application failed: {error}. "
            f"Rollback result: {rollback_result}"
        ) from error
