
import os
import subprocess
import time
import uuid
from pathlib import Path


DOCKER_IMAGE = "python:3.12-slim"
MAX_INSTALL_TIMEOUT = 300
VENV_NAME = ".devpilot-venv"


def install_project_dependencies(
    workspace_path: str,
    timeout: int = 300
) -> dict:
    """
    Install dependencies from requirements.txt inside a Docker container.

    Creates a virtual environment inside the isolated workspace.
    Network is enabled only during dependency installation.
    """

    root = Path(workspace_path).resolve()

    if not root.is_dir():
        raise FileNotFoundError("Workspace does not exist")

    requirements_file = root / "requirements.txt"

    if requirements_file.is_symlink():
        raise ValueError("Symbolic requirements files are not allowed")

    if not requirements_file.is_file():
        return {
            "status": "skipped",
            "message": "No requirements.txt found",
            "venv_path": None
        }

    if requirements_file.stat().st_size > 100_000:
        raise ValueError("requirements.txt exceeds the 100 KB limit")

    if timeout < 1 or timeout > MAX_INSTALL_TIMEOUT:
        raise ValueError(
            f"Timeout must be between 1 and {MAX_INSTALL_TIMEOUT} seconds"
        )

    venv_path = root / VENV_NAME

    if venv_path.exists():
        raise FileExistsError(
            "DevPilot virtual environment already exists in this workspace"
        )

    uid = os.getuid()
    gid = os.getgid()

    container_name = f"devpilot-install-{uuid.uuid4().hex[:12]}"

    # This script is fixed application code, not user-supplied shell input.
    install_script = (
    "import subprocess, sys\n"
    "venv = '/workspace/.devpilot-venv'\n"
    "subprocess.run([sys.executable, '-m', 'venv', venv], check=True)\n"
    "pip = venv + '/bin/python'\n"
    "subprocess.run([pip, '-m', 'pip', 'install', "
    "'--no-cache-dir', '-r', '/workspace/requirements.txt'], check=True)\n"
    )
    print("INSTALL SCRIPT:")
    print(install_script)

    # Correct the fixed script's pip arguments.
    install_script = install_script.replace(
        "'--no-cache-dir'",
        "'--no-cache-dir'"
    )

    docker_command = [
        "docker", "run", "--rm",
        "--name", container_name,
        "--network", "bridge",
        "--memory", "512m",
        "--cpus", "1",
        "--pids-limit", "64",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", f"{uid}:{gid}",
        "--tmpfs", "/tmp:rw,nosuid,size=128m",
        "--mount",
        f"type=bind,source={root},target=/workspace",
        "--workdir", "/workspace",
        DOCKER_IMAGE,
        "python", "-c", install_script
    ]

    start_time = time.monotonic()

    try:
        result = subprocess.run(
            docker_command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )

        duration = round(time.monotonic() - start_time, 3)

        return {
            "status": "success" if result.returncode == 0 else "failed",
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_seconds": duration,
            "venv_path": str(venv_path) if result.returncode == 0 else None
        }

    except subprocess.TimeoutExpired:
        cleanup = subprocess.run(
            ["docker", "rm", "-f", container_name],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )

        return {
            "status": "timeout",
            "exit_code": None,
            "stdout": "",
            "stderr": "Dependency installation timed out",
            "duration_seconds": round(time.monotonic() - start_time, 3),
            "venv_path": None,
            "container_cleanup_success": cleanup.returncode == 0
        }
